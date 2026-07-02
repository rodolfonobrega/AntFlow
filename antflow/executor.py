from __future__ import annotations

import asyncio
from enum import Enum
from types import TracebackType
from typing import (
    Any,
    AsyncIterator,
    Awaitable,
    Callable,
    Generic,
    Iterable,
    List,
    Set,
    Tuple,
    TypeVar,
    cast,
)

from .exceptions import ExecutorShutdownError
from .utils import setup_logger
from .telemetry import get_tracer, is_enabled

T = TypeVar("T")
R = TypeVar("R")

logger = setup_logger(__name__)


class WaitStrategy(Enum):
    """Strategy for waiting on multiple futures."""

    FIRST_COMPLETED = "FIRST_COMPLETED"
    FIRST_EXCEPTION = "FIRST_EXCEPTION"
    ALL_COMPLETED = "ALL_COMPLETED"


class AsyncFuture(Generic[R]):
    """
    An async-compatible future that holds the result of an async task.
    Similar to concurrent.futures.Future but for asyncio.
    """

    def __init__(self, sequence_id: int):
        self.sequence_id = sequence_id
        self._result: Any = None
        self._exception: Exception | None = None
        self._done_event = asyncio.Event()

    def set_result(self, result: R) -> None:
        """Set the result and mark the future as done."""
        self._result = result
        self._done_event.set()

    def set_exception(self, exception: Exception) -> None:
        """Set an exception and mark the future as done."""
        self._exception = exception
        self._done_event.set()

    async def result(self, timeout: float | None = None) -> R:
        """
        Wait for and return the result.

        Args:
            timeout: Maximum time to wait in seconds

        Returns:
            The task result

        Raises:
            asyncio.TimeoutError: If timeout is exceeded
            Exception: The exception set by set_exception()
        """
        if timeout is not None:
            await asyncio.wait_for(self._done_event.wait(), timeout=timeout)
        else:
            await self._done_event.wait()

        if self._exception is not None:
            raise self._exception
        return cast(R, self._result)

    def done(self) -> bool:
        """Return True if the future is done."""
        return self._done_event.is_set()

    def exception(self) -> Exception | None:
        """Return the exception set on this future, or None."""
        return self._exception


class AsyncExecutor:
    """
    An async executor with concurrent.futures-style API.
    Manages a pool of workers that execute async tasks concurrently.
    """

    def __init__(self, max_workers: int = 5):
        """
        Initialize the executor.

        Args:
            max_workers: Maximum number of concurrent workers
        """
        if max_workers < 1:
            raise ValueError("max_workers must be at least 1")

        self.max_workers = max_workers
        self._queue: asyncio.Queue = asyncio.Queue()
        self._stop_event = asyncio.Event()
        self._shutdown = False
        self._workers_started = False
        self._worker_tasks: list[asyncio.Task] = []
        self._sequence_counter = 0

    async def _worker(self, worker_id: int) -> None:
        """
        Worker coroutine that processes tasks from the queue.

        Args:
            worker_id: Unique identifier for this worker
        """
        logger.debug(f"Worker {worker_id} started")

        while not self._stop_event.is_set() or not self._queue.empty():
            try:
                item = await asyncio.wait_for(self._queue.get(), timeout=0.1)
            except asyncio.TimeoutError:
                continue

            future, fn, args, kwargs = item

            tracer = get_tracer()
            with tracer.start_as_current_span("antflow.executor.task") as span:
                if is_enabled():
                    span.set_attribute("antflow.executor.worker_id", worker_id)
                    span.set_attribute("antflow.executor.task_id", future.sequence_id)
                try:
                    logger.debug(f"Worker {worker_id} executing task {future.sequence_id}")
                    result = await fn(*args, **kwargs)
                    future.set_result(result)
                    logger.debug(f"Worker {worker_id} completed task {future.sequence_id}")
                except BaseException as e:
                    logger.debug(f"Worker {worker_id} task {future.sequence_id} failed: {e}")
                    if is_enabled():
                        span.record_exception(e)
                    future.set_exception(e)
                finally:
                    self._queue.task_done()

        logger.debug(f"Worker {worker_id} stopped")

    def _ensure_workers_started(self) -> None:
        """Start worker tasks if not already started."""
        if not self._workers_started:
            self._worker_tasks = [
                asyncio.create_task(self._worker(i)) for i in range(self.max_workers)
            ]
            self._workers_started = True

    def submit(
        self,
        fn: Callable[..., Awaitable[R]],
        *args: Any,
        retries: int = 0,
        retry_delay: float = 0.1,
        semaphore: asyncio.Semaphore | None = None,
        **kwargs: Any,
    ) -> AsyncFuture[R]:
        """
        Submit a task for execution.

        Args:
            fn: Async callable to execute
            *args: Positional arguments for fn
            retries: Number of retries on failure
            retry_delay: Delay between retries in seconds
            semaphore: Optional semaphore to limit concurrency
            **kwargs: Keyword arguments for fn

        Returns:
            AsyncFuture that can be awaited for the result

        Raises:
            ExecutorShutdownError: If executor has been shut down
        """
        if self._shutdown:
            raise ExecutorShutdownError("Cannot submit tasks to a shutdown executor")

        # Wrap function with semaphore if provided
        if semaphore:
            original_fn = fn

            async def semaphore_wrapper(*a, **kw):
                async with semaphore:
                    return await original_fn(*a, **kw)

            fn = semaphore_wrapper

        if retries > 0:
            from tenacity import retry, stop_after_attempt, wait_exponential

            @retry(
                stop=stop_after_attempt(retries + 1),
                wait=wait_exponential(multiplier=retry_delay),
                reraise=True,
            )
            async def wrapped_fn(*a, **kw):
                return await fn(*a, **kw)

            task_fn = wrapped_fn
        else:
            task_fn = fn

        self._ensure_workers_started()

        future: AsyncFuture[R] = AsyncFuture(self._sequence_counter)
        self._sequence_counter += 1
        self._queue.put_nowait((future, task_fn, args, kwargs))

        return future

    async def map(
        self,
        fn: Callable[..., Awaitable[R]],
        *iterables: Iterable[T],
        timeout: float | None = None,
        retries: int = 0,
        retry_delay: float = 0.1,
    ) -> List[R]:
        """
        Map an async function over iterables and return results as a list.

        Similar to `concurrent.futures.Executor.map()`, but returns a list directly
        instead of an iterator (since `list(executor.map(...))` is the common pattern).

        Args:
            fn: Async callable to map
            *iterables: Iterables to map over
            timeout: Maximum time to wait for each result
            retries: Number of retries on failure
            retry_delay: Delay between retries in seconds

        Returns:
            List of results from fn applied to each input, in input order

        Raises:
            ExecutorShutdownError: If executor has been shut down

        Example:
            ```python
            async with AsyncExecutor(max_workers=5) as executor:
                results = await executor.map(process, range(100))
                print(results)  # [0, 2, 4, 6, ...]
            ```
        """
        results: List[R] = []
        async for result in self.map_iter(
            fn,
            *iterables,
            timeout=timeout,
            retries=retries,
            retry_delay=retry_delay,
        ):
            results.append(result)
        return results

    async def map_iter(
        self,
        fn: Callable[..., Awaitable[R]],
        *iterables: Iterable[T],
        timeout: float | None = None,
        retries: int = 0,
        retry_delay: float = 0.1,
    ) -> AsyncIterator[R]:
        """
        Map an async function over iterables, yielding results in input order.

        Use this instead of `map()` when you need streaming behavior:
        - Process results as they arrive
        - Handle large datasets without loading all results into memory
        - Early exit when a condition is met

        Args:
            fn: Async callable to map
            *iterables: Iterables to map over
            timeout: Maximum time to wait for each result
            retries: Number of retries on failure
            retry_delay: Delay between retries in seconds

        Yields:
            Results from fn applied to each input

        Raises:
            ExecutorShutdownError: If executor has been shut down

        Example:
            ```python
            async with AsyncExecutor(max_workers=5) as executor:
                async for result in executor.map_iter(process, range(100)):
                    print(result)
                    if result > 50:
                        break  # Early exit
            ```
        """
        if self._shutdown:
            raise ExecutorShutdownError("Cannot use map on a shutdown executor")

        self._ensure_workers_started()

        futures: list[AsyncFuture[R]] = []
        for args in zip(*iterables):
            if len(args) == 1:
                future = self.submit(
                    fn,
                    args[0],
                    retries=retries,
                    retry_delay=retry_delay,
                )
            else:
                future = self.submit(
                    fn,
                    *args,
                    retries=retries,
                    retry_delay=retry_delay,
                )
            futures.append(future)

        for future in futures:
            yield await future.result(timeout=timeout)

    async def as_completed(
        self, futures: list[AsyncFuture[R]], timeout: float | None = None
    ) -> AsyncIterator[AsyncFuture[R]]:
        """
        Yield futures as they complete.

        Args:
            futures: List of futures to wait for
            timeout: Maximum time to wait for all futures

        Yields:
            Futures as they complete

        Raises:
            asyncio.TimeoutError: If timeout is exceeded
        """
        # Create exactly one waiter task per future (not one per loop iteration),
        # and always cancel any leftovers in finally so nothing leaks.
        waiters = {asyncio.create_task(f._done_event.wait()): f for f in futures}
        start_time = self._wait_start_time(timeout)
        try:
            while waiters:
                remaining = self._remaining_wait_timeout(timeout, start_time)
                if remaining is not None and remaining <= 0:
                    raise asyncio.TimeoutError()

                done, _ = await asyncio.wait(
                    waiters.keys(), return_when=asyncio.FIRST_COMPLETED, timeout=remaining
                )

                if not done:
                    raise asyncio.TimeoutError()

                for task in done:
                    future = waiters.pop(task)
                    yield future
        finally:
            for task in waiters:
                task.cancel()

    async def _wait_for_future_event(self, future: AsyncFuture[R]) -> AsyncFuture[R]:
        await future._done_event.wait()
        return future

    def _wait_start_time(self, timeout: float | None) -> float | None:
        return asyncio.get_event_loop().time() if timeout is not None else None

    def _remaining_wait_timeout(
        self, timeout: float | None, start_time: float | None
    ) -> float | None:
        if timeout is None or start_time is None:
            return None

        elapsed = asyncio.get_event_loop().time() - start_time
        return max(0, timeout - elapsed)

    def _create_wait_tasks(
        self, pending: Set[AsyncFuture[R]]
    ) -> dict[asyncio.Task[AsyncFuture[R]], AsyncFuture[R]]:
        return {asyncio.create_task(self._wait_for_future_event(f)): f for f in pending}

    def _cancel_wait_tasks(
        self, wait_tasks: dict[asyncio.Task[AsyncFuture[R]], AsyncFuture[R]]
    ) -> None:
        for task in wait_tasks:
            if not task.done():
                task.cancel()

    def _process_completed_wait_tasks(
        self,
        completed_tasks: Set[asyncio.Task[AsyncFuture[R]]],
        wait_tasks: dict[asyncio.Task[AsyncFuture[R]], AsyncFuture[R]],
        done: Set[AsyncFuture[R]],
        pending: Set[AsyncFuture[R]],
    ) -> Set[AsyncFuture[R]]:
        completed_futures: Set[AsyncFuture[R]] = set()
        for task in completed_tasks:
            future = wait_tasks[task]
            pending.discard(future)
            done.add(future)
            completed_futures.add(future)
        return completed_futures

    def _wait_strategy_satisfied(
        self, return_when: WaitStrategy, completed_futures: Set[AsyncFuture[R]]
    ) -> bool:
        if return_when == WaitStrategy.FIRST_COMPLETED:
            return bool(completed_futures)

        if return_when == WaitStrategy.FIRST_EXCEPTION:
            return any(future.exception() is not None for future in completed_futures)

        return False

    async def wait(
        self,
        futures: Iterable[AsyncFuture[R]],
        timeout: float | None = None,
        return_when: WaitStrategy = WaitStrategy.ALL_COMPLETED,
    ) -> Tuple[Set[AsyncFuture[R]], Set[AsyncFuture[R]]]:
        """
        Wait for futures to complete with different strategies.

        Similar to concurrent.futures.wait() but for async operations.

        Args:
            futures: Iterable of AsyncFuture objects to wait for
            timeout: Maximum time to wait in seconds
            return_when: Strategy for when to return:
                - FIRST_COMPLETED: Return when any future completes
                - FIRST_EXCEPTION: Return when any future raises an exception
                - ALL_COMPLETED: Return when all futures complete (default)

        Returns:
            Tuple of (done, not_done) sets of futures

        Raises:
            asyncio.TimeoutError: If timeout is exceeded (with ALL_COMPLETED)

        Example:
            ```python
            futures = [executor.submit(task, i) for i in range(10)]
            done, pending = await executor.wait(
                futures,
                return_when=WaitStrategy.FIRST_EXCEPTION
            )
            ```
        """
        futures_set = set(futures)
        done: Set[AsyncFuture[R]] = set()
        pending = futures_set.copy()

        if not pending:
            return done, pending

        start_time = self._wait_start_time(timeout)

        while pending:
            remaining_timeout = self._remaining_wait_timeout(timeout, start_time)
            if remaining_timeout is not None and remaining_timeout <= 0:
                if return_when == WaitStrategy.ALL_COMPLETED:
                    raise asyncio.TimeoutError()
                break

            wait_tasks = self._create_wait_tasks(pending)

            try:
                completed_tasks, _ = await asyncio.wait(
                    wait_tasks.keys(),
                    timeout=remaining_timeout,
                    return_when=asyncio.FIRST_COMPLETED,
                )

                if not completed_tasks:
                    if return_when == WaitStrategy.ALL_COMPLETED:
                        raise asyncio.TimeoutError()
                    break

                completed_futures = self._process_completed_wait_tasks(
                    completed_tasks, wait_tasks, done, pending
                )
                if self._wait_strategy_satisfied(return_when, completed_futures):
                    return done, pending
            finally:
                self._cancel_wait_tasks(wait_tasks)

        return done, pending

    async def shutdown(self, wait: bool = True, cancel_futures: bool = False) -> None:
        """
        Shut down the executor.

        Args:
            wait: If True, wait for all pending tasks to complete. If False, the
                stop signal is set without draining the queue, so tasks still
                queued (and not picked up before workers exit) may be left
                unprocessed. Use cancel_futures=True to fail them explicitly.
            cancel_futures: If True, cancel all pending futures
        """
        if self._shutdown:
            return

        logger.debug("Shutting down executor")
        self._shutdown = True

        if cancel_futures:
            while not self._queue.empty():
                try:
                    future, _, _, _ = self._queue.get_nowait()
                    future.set_exception(ExecutorShutdownError("Executor shutdown"))
                    self._queue.task_done()
                except asyncio.QueueEmpty:
                    break

        if wait and self._workers_started:
            await self._queue.join()

        self._stop_event.set()

        if wait and self._workers_started:
            await asyncio.gather(*self._worker_tasks, return_exceptions=True)

        logger.debug("Executor shutdown complete")

    async def __aenter__(self) -> "AsyncExecutor":
        """Context manager entry."""
        self._ensure_workers_started()
        return self

    async def __aexit__(
        self,
        _exc_type: type[BaseException] | None,
        _exc_val: BaseException | None,
        _exc_tb: TracebackType | None,
    ) -> None:
        """Context manager exit with automatic shutdown."""
        await self.shutdown(wait=True)
