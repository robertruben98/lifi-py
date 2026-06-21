"""Exception hierarchy for the LI.FI client."""

from __future__ import annotations

from typing import Any, Optional


class LifiError(Exception):
    """Base class for all errors raised by this library."""


class LifiAPIError(LifiError):
    """The API returned a non-2xx response (other than rate limiting)."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int,
        response_body: Optional[Any] = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.response_body = response_body


class LifiRateLimitError(LifiAPIError):
    """HTTP 429: rate limit exceeded.

    ``retry_after`` holds the number of seconds to wait before retrying, derived
    from the ``ratelimit-reset`` or ``retry-after`` response header when present.
    """

    def __init__(
        self,
        message: str,
        *,
        status_code: int = 429,
        retry_after: Optional[float] = None,
        response_body: Optional[Any] = None,
    ) -> None:
        super().__init__(message, status_code=status_code, response_body=response_body)
        self.retry_after = retry_after
