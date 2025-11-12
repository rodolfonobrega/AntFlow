from __future__ import annotations

import asyncio
from enum import Enum
from typing import Any, AsyncIterator, Callable, Iterable, Set, Tuple, TypeVar

from .exceptions import ExecutorShutdownError
from .utils import setup_logger

T = TypeVar("T")
R = TypeVar("R")

logger = setup_logger(__name__)


class WaitStrategy(Enum):
    """Strategy for waiting on multiple futures."""
    FIRST_COMPLETED = "FIRST_COMPLETED"
    FIRST_EXCEPTION = "FIRST_EXCEPTION"
    ALL_COMPLETED = "ALL_COMPLETED"


class AsyncFuture:
    """
    An async-compatible future that holds the result of an async task.
    Similar to concurrent.futures.Future but for asyncio.
    """

    def __init__(self, sequence_id: int):
        self.sequence_id = sequence_id
        self._result: Any = None
        self._exception: Exception | None = None
        self._done_event = asyncio.Event()

    def set_result(self, result: Any) -> None:
        """Set the result and mark the future as done."""
        self._result = result
        self._done_event.set()

    def set_exception(self, exception: Exception) -> None:
        """Set an exception and mark the future as done."""
        self._exception = exception
        self._done_event.set()

    async def result(self, timeout: float | None = None) -> Any:
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
        return self._result

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

            try:
                logger.debug(f"Worker {worker_id} executing task {future.sequence_id}")
                result = await fn(*args, **kwargs)
                future.set_result(result)
                logger.debug(f"Worker {worker_id} completed task {future.sequence_id}")
            except Exception as e:
                logger.debug(f"Worker {worker_id} task {future.sequence_id} failed: {e}")
                future.set_exception(e)
            finally:
                self._queue.task_done()

        logger.debug(f"Worker {worker_id} stopped")

    async def _ensure_workers_started(self) -> None:
        """Start worker tasks if not already started."""
        if not self._workers_started:
            self._worker_tasks = [
                asyncio.create_task(self._worker(i))
                for i in range(self.max_workers)
            ]
            self._workers_started = True

    def submit(
        self,
        fn: Callable[..., Any],
        *args: Any,
        **kwargs: Any
    ) -> AsyncFuture:
        """
        Submit a task for execution.

        Args:
            fn: Async callable to execute
            *args: Positional arguments for fn
            **kwargs: Keyword arguments for fn

        Returns:
            AsyncFuture that can be awaited for the result

        Raises:
            ExecutorShutdownError: If executor has been shut down
        """
        if self._shutdown:
            raise ExecutorShutdownError("Cannot submit tasks to a shutdown executor")

        future = AsyncFuture(self._sequence_counter)
        self._sequence_counter += 1
        self._queue.put_nowait((future, fn, args, kwargs))

        return future

    async def map(
        self,
        fn: Callable[[T], Any],
        *iterables: Iterable[T],
        timeout: float | None = None
    ) -> AsyncIterator[R]:
        """
        Map an async function over iterables, yielding results in input order.

        Args:
            fn: Async callable to map
            *iterables: Iterables to map over
            timeout: Maximum time to wait for each result

        Yields:
            Results from fn applied to each input

        Raises:
            ExecutorShutdownError: If executor has been shut down
        """
        if self._shutdown:
            raise ExecutorShutdownError("Cannot use map on a shutdown executor")

        await self._ensure_workers_started()

        futures = []
        for args in zip(*iterables):
            if len(args) == 1:
                future = self.submit(fn, args[0])
            else:
                future = self.submit(fn, *args)
            futures.append(future)

        for future in futures:
            yield await future.result(timeout=timeout)

    async def as_completed(
        self,
        futures: list[AsyncFuture],
        timeout: float | None = None
    ) -> AsyncIterator[AsyncFuture]:
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
        pending = set(futures)

        async def wait_for_any():
            while pending:
                done_tasks = [
                    asyncio.create_task(f._done_event.wait())
                    for f in pending
                ]

                done, _ = await asyncio.wait(
                    done_tasks,
                    return_when=asyncio.FIRST_COMPLETED,
                    timeout=timeout
                )

                if not done:
                    for task in done_tasks:
                        task.cancel()
                    raise asyncio.TimeoutError()

                for task in done_tasks:
                    if not task.done():
                        task.cancel()

                completed = [f for f in pending if f.done()]
                for future in completed:
                    pending.remove(future)
                    yield future

        async for future in wait_for_any():
            yield future

    async def wait(
        self,
        futures: Iterable[AsyncFuture[R]],
        timeout: float | None = None,
        return_when: WaitStrategy = WaitStrategy.ALL_COMPLETED
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

        start_time = asyncio.get_event_loop().time() if timeout else None

        async def wait_for_event(future: AsyncFuture[R]) -> AsyncFuture[R]:
            await future._done_event.wait()
            return future

        while pending:
            # Calculate remaining timeout
            remaining_timeout = None
            if timeout is not None and start_time is not None:
                elapsed = asyncio.get_event_loop().time() - start_time
                remaining_timeout = max(0, timeout - elapsed)
                if remaining_timeout <= 0:
                    if return_when == WaitStrategy.ALL_COMPLETED:
                        raise asyncio.TimeoutError()
                    break

            # Create wait tasks for pending futures
            wait_tasks = {
                asyncio.create_task(wait_for_event(f)): f
                for f in pending
            }

            try:
                completed_tasks, _ = await asyncio.wait(
                    wait_tasks.keys(),
                    timeout=remaining_timeout,
                    return_when=asyncio.FIRST_COMPLETED
                )

                # Process completed futures
                for task in completed_tasks:
                    future = wait_tasks[task]
                    pending.discard(future)
                    done.add(future)

                    # Check return strategy
                    if return_when == WaitStrategy.FIRST_COMPLETED:
                        # Cancel remaining tasks
                        for t in wait_tasks.keys():
                            if not t.done():
                                t.cancel()
                        return done, pending

                    if return_when == WaitStrategy.FIRST_EXCEPTION:
                        if future.exception() is not None:
                            # Cancel remaining tasks
                            for t in wait_tasks.keys():
                                if not t.done():
                                    t.cancel()
                            return done, pending

                # Cancel incomplete tasks
                for task in wait_tasks.keys():
                    if not task.done():
                        task.cancel()

            except asyncio.TimeoutError:
                # Timeout occurred
                for task in wait_tasks.keys():
                    task.cancel()
                if return_when == WaitStrategy.ALL_COMPLETED:
                    raise
                break

        return done, pending

    async def shutdown(self, wait: bool = True, cancel_futures: bool = False) -> None:
        """
        Shut down the executor.

        Args:
            wait: If True, wait for all pending tasks to complete
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

        if self._workers_started:
            await asyncio.gather(*self._worker_tasks, return_exceptions=True)

        logger.debug("Executor shutdown complete")

    async def __aenter__(self) -> "AsyncExecutor":
        """Context manager entry."""
        await self._ensure_workers_started()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit with automatic shutdown."""
        await self.shutdown(wait=True)
