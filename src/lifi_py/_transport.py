"""Shared HTTP plumbing: rate-limit tracking, proactive throttling, 429 backoff.

The logic here is transport-agnostic. ``RateLimitState`` parses the
``ratelimit-*`` headers LI.FI returns; ``compute_*`` helpers decide how long to
wait. The sync and async clients call into these so retry/throttle behavior is
identical and tested once.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Optional

import httpx

from .exceptions import LifiAPIError, LifiRateLimitError

# Re-exported so tests can monkeypatch ``_transport.time.sleep``.
__all__ = ["RateLimit", "RateLimitState", "build_query", "parse_response", "time"]

DEFAULT_BASE_URL = "https://li.quest/v1"


@dataclass
class RateLimit:
    """Snapshot of the API's rate-limit headers from the last response."""

    limit: Optional[int] = None
    remaining: Optional[int] = None
    reset: Optional[float] = None


def _to_int(value: Optional[str]) -> Optional[int]:
    if value is None:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def _to_float(value: Optional[str]) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except ValueError:
        return None


class RateLimitState:
    """Tracks rate-limit headers and computes wait times for throttling."""

    def __init__(self) -> None:
        self.current = RateLimit()

    def update(self, headers: httpx.Headers) -> None:
        self.current = RateLimit(
            limit=_to_int(headers.get("ratelimit-limit")),
            remaining=_to_int(headers.get("ratelimit-remaining")),
            reset=_to_float(headers.get("ratelimit-reset")),
        )

    def proactive_wait(self) -> float:
        """Seconds to sleep before the next request to avoid hitting 429.

        Returns the reset window when the quota is exhausted, else 0.
        """
        rl = self.current
        if rl.remaining is not None and rl.remaining <= 0 and rl.reset:
            return float(rl.reset)
        return 0.0


def retry_after_seconds(response: httpx.Response) -> Optional[float]:
    """Best-effort wait window from a 429 response's headers."""
    reset = _to_float(response.headers.get("ratelimit-reset"))
    if reset is not None:
        return reset
    return _to_float(response.headers.get("retry-after"))


def backoff_seconds(attempt: int, response: httpx.Response) -> float:
    """How long to wait before retry ``attempt`` (0-indexed) after a 429.

    Honors the server's reset window when present; otherwise exponential
    backoff (1, 2, 4, ... capped at 30s).
    """
    server = retry_after_seconds(response)
    if server is not None:
        return max(server, 1.0)
    return float(min(2**attempt, 30))


def build_query(**params: Any) -> dict[str, str]:
    """Drop ``None`` values and stringify the rest for a query string."""
    out: dict[str, str] = {}
    for key, value in params.items():
        if value is None:
            continue
        out[key] = str(value)
    return out


def _error_message(response: httpx.Response, body: Any) -> str:
    if isinstance(body, dict):
        for key in ("message", "error", "detail"):
            msg = body.get(key)
            if isinstance(msg, str):
                return msg
    return f"HTTP {response.status_code} from {response.request.url}"


def parse_response(response: httpx.Response) -> Any:
    """Validate status and return parsed JSON, raising typed errors.

    429 raises ``LifiRateLimitError`` (with ``retry_after``); any other non-2xx
    raises ``LifiAPIError``.
    """
    body: Any
    try:
        body = response.json()
    except ValueError:
        body = None

    if response.status_code == 429:
        raise LifiRateLimitError(
            _error_message(response, body) or "Rate limit exceeded",
            retry_after=retry_after_seconds(response),
            response_body=body,
        )
    if response.status_code >= 400:
        raise LifiAPIError(
            _error_message(response, body),
            status_code=response.status_code,
            response_body=body,
        )
    return body
