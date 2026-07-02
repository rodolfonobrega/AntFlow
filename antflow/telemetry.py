from __future__ import annotations

import contextlib
from typing import Any, Callable, Dict, Iterator, Optional, Sequence, Union

_HAS_OTEL = False
_enabled = True

try:
    from opentelemetry import metrics, trace
    from opentelemetry.metrics import Meter
    from opentelemetry.trace import StatusCode, Tracer
    _HAS_OTEL = True
except ImportError:
    # No-op placeholders for OpenTelemetry types when not installed
    class StatusCode:  # type: ignore[no-redef]
        UNSET = 0
        OK = 1
        ERROR = 2

    Tracer = "_NoOpTracer"  # type: ignore[assignment,misc]
    Meter = "_NoOpMeter"  # type: ignore[assignment,misc]


# ---------- Public API ----------

def configure_telemetry(*, enabled: bool = True) -> None:
    """
    Enable or disable OpenTelemetry instrumentation at runtime.

    Args:
        enabled: True to enable, False to disable.
    """
    global _enabled
    _enabled = enabled


def is_enabled() -> bool:
    """Check if OpenTelemetry instrumentation is active and package is installed."""
    return _HAS_OTEL and _enabled


# ---------- Tracer & Meter Accessors ----------

def get_tracer() -> Union[Tracer, _NoOpTracer]:
    """Get the OpenTelemetry tracer, or a no-op tracer if telemetry is disabled."""
    if is_enabled():
        return trace.get_tracer("antflow")
    return _NoOpTracer()


def get_meter() -> Union[Meter, _NoOpMeter]:
    """Get the OpenTelemetry meter, or a no-op meter if telemetry is disabled."""
    if is_enabled():
        return metrics.get_meter("antflow")
    return _NoOpMeter()


# ---------- No-Op Stubs for Telemetry APIs ----------

class _NoOpSpan:
    """No-op stub replacing opentelemetry.trace.Span API."""

    def set_attribute(self, key: str, value: Any) -> _NoOpSpan:
        return self

    def set_status(self, status: Any, description: Optional[str] = None) -> _NoOpSpan:
        return self

    def record_exception(
        self,
        exception: Exception,
        attributes: Optional[Dict[str, Any]] = None,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        pass

    def add_event(
        self,
        name: str,
        attributes: Optional[Dict[str, Any]] = None,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        pass

    def end(self, *args: Any, **kwargs: Any) -> None:
        pass

    def __enter__(self) -> _NoOpSpan:
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        pass


class _NoOpTracer:
    """No-op stub replacing opentelemetry.trace.Tracer API."""

    def start_span(self, name: str, *args: Any, **kwargs: Any) -> _NoOpSpan:
        return _NoOpSpan()

    @contextlib.contextmanager
    def start_as_current_span(self, name: str, *args: Any, **kwargs: Any) -> Iterator[_NoOpSpan]:
        yield _NoOpSpan()


class _NoOpInstrument:
    """No-op stub replacing OpenTelemetry metrics instruments."""

    def add(self, amount: Union[int, float], attributes: Optional[Dict[str, Any]] = None) -> None:
        pass

    def record(self, amount: Union[int, float], attributes: Optional[Dict[str, Any]] = None) -> None:
        pass


class _NoOpMeter:
    """No-op stub replacing opentelemetry.metrics.Meter API."""

    def create_counter(self, name: str, *args: Any, **kwargs: Any) -> _NoOpInstrument:
        return _NoOpInstrument()

    def create_histogram(self, name: str, *args: Any, **kwargs: Any) -> _NoOpInstrument:
        return _NoOpInstrument()

    def create_up_down_counter(self, name: str, *args: Any, **kwargs: Any) -> _NoOpInstrument:
        return _NoOpInstrument()
