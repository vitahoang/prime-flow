"""Exceptions used across taskmill."""

from __future__ import annotations


class TaskmillError(Exception):
    """Base class for taskmill's own errors."""


class ConfigError(TaskmillError):
    """The config file is missing a value or has a bad one."""


class UnknownJobKind(TaskmillError):
    """No handler is registered for a job's kind."""

    def __init__(self, kind: str):
        super().__init__(f"no handler registered for job kind {kind!r}")
        self.kind = kind


class JobNotFound(TaskmillError):
    def __init__(self, job_id: int):
        super().__init__(f"job #{job_id} not found")
        self.job_id = job_id


class InvalidTransition(TaskmillError):
    """A CLI action was asked for that the job's current status doesn't allow."""


class PermanentError(TaskmillError):
    """Raise from a handler when running the job again can never succeed:
    the payload is malformed, the record it points at was deleted, and so on.
    """


class RateLimited(TaskmillError):
    """The remote side told us to slow down.

    ``retry_after`` is how many seconds the remote asked us to wait (from a
    ``Retry-After`` header, for example).
    """

    def __init__(self, retry_after: float, message: str = ""):
        self.retry_after = float(retry_after)
        super().__init__(message or f"rate limited; retry after {self.retry_after:g}s")
