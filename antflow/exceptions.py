class AntFlowError(Exception):
    """Base exception for all antflow errors."""
    pass


class ExecutorShutdownError(AntFlowError):
    """Raised when attempting to use an executor that has been shut down."""
    pass


class PipelineError(AntFlowError):
    """Base exception for pipeline-specific errors."""
    pass


class StageValidationError(PipelineError):
    """Raised when a stage configuration is invalid."""
    pass


class TaskFailedError(AntFlowError):
    """Wrapper for task failures that preserves the original exception."""

    def __init__(self, task_name: str, original_exception: Exception):
        self.task_name          = task_name
        self.original_exception = original_exception
        super().__init__(f"Task '{task_name}' failed: {original_exception}")
