"""Retry policy: which failures to retry and how long to wait.

The GitBook API answers 429 when a token goes over its rate limit and
reports the window in ``X-RateLimit-Limit``, ``X-RateLimit-Remaining`` and
``X-RateLimit-Reset`` (UTC epoch seconds). The client waits for the time
the server asks for, in this order:

1. ``Retry-After`` (seconds or an HTTP date), when present.
2. ``X-RateLimit-Reset`` on a 429 response.
3. Exponential backoff with jitter.

429 and 503 mean the server did not process the request, so they are
retried for every method. Other 5xx responses, timeouts and connection
errors are retried only for idempotent methods (GET, HEAD, OPTIONS, PUT,
DELETE), so a POST that may have reached the server is never sent twice
unless ``retry_non_idempotent`` is turned on.
"""

from __future__ import annotations

import datetime
import email.utils
import random
import time
from dataclasses import dataclass, field
from typing import Callable, FrozenSet, Mapping, Optional

__all__ = ["RetryPolicy", "parse_retry_after"]

IDEMPOTENT_METHODS: FrozenSet[str] = frozenset({"GET", "HEAD", "OPTIONS", "PUT", "DELETE"})
ALWAYS_RETRY_STATUSES: FrozenSet[int] = frozenset({429, 503})


@dataclass(frozen=True)
class RetryPolicy:
    """How the client retries failed requests.

    Attributes:
        max_retries: Retries after the first attempt. ``0`` turns retries off.
        backoff_factor: Base delay in seconds. Attempt ``n`` (from 0) waits
            about ``backoff_factor * 2 ** n``.
        max_backoff: Upper bound for a computed backoff delay.
        max_retry_after: Longest server-requested wait the client accepts.
            If ``Retry-After`` asks for more, the error is raised at once
            instead of blocking the caller.
        retry_statuses: Status codes that may be retried.
        retry_non_idempotent: Also retry POST and PATCH on 5xx and
            connection errors.
        jitter: Multiply computed backoff by a random factor in ``[0.5, 1]``.
    """

    max_retries: int = 3
    backoff_factor: float = 0.5
    max_backoff: float = 30.0
    max_retry_after: float = 120.0
    retry_statuses: FrozenSet[int] = frozenset({429, 500, 502, 503, 504})
    retry_non_idempotent: bool = False
    jitter: bool = True
    random: Callable[[], float] = field(default=random.random, repr=False, compare=False)

    def __post_init__(self) -> None:
        if self.max_retries < 0:
            raise ValueError("max_retries must be 0 or more")
        if self.backoff_factor < 0 or self.max_backoff < 0 or self.max_retry_after < 0:
            raise ValueError("delays must be 0 or more")

    def should_retry_status(self, method: str, status: int, attempt: int) -> bool:
        """Whether a response with ``status`` on try ``attempt`` (from 0) is retried."""
        if attempt >= self.max_retries or status not in self.retry_statuses:
            return False
        if status in ALWAYS_RETRY_STATUSES:
            return True
        return self._method_ok(method)

    def should_retry_error(self, method: str, attempt: int) -> bool:
        """Whether a timeout or connection error on try ``attempt`` is retried."""
        return attempt < self.max_retries and self._method_ok(method)

    def backoff(self, attempt: int) -> float:
        """Computed delay before retry number ``attempt + 1``."""
        delay = min(self.max_backoff, self.backoff_factor * (2.0**attempt))
        if self.jitter:
            delay *= 0.5 + self.random() / 2.0
        return delay

    def _method_ok(self, method: str) -> bool:
        return self.retry_non_idempotent or method.upper() in IDEMPOTENT_METHODS


def parse_retry_after(
    headers: Mapping[str, str],
    status: int,
    *,
    now: Optional[float] = None,
) -> Optional[float]:
    """Seconds the server asked the client to wait, or ``None``.

    Reads ``Retry-After`` as delta-seconds or an HTTP date, then falls back
    to ``X-RateLimit-Reset`` for a 429. Past times give ``0.0``.
    """
    current = time.time() if now is None else now
    raw = headers.get("retry-after")
    if raw is not None:
        raw = raw.strip()
        try:
            return max(0.0, float(raw))
        except ValueError:
            pass
        try:
            parsed = email.utils.parsedate_to_datetime(raw)
        except (TypeError, ValueError, IndexError):
            parsed = None
        if parsed is not None:
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=datetime.timezone.utc)
            return max(0.0, parsed.timestamp() - current)
    if status == 429:
        reset = headers.get("x-ratelimit-reset")
        if reset is not None:
            try:
                return max(0.0, float(reset.strip()) - current)
            except ValueError:
                return None
    return None
