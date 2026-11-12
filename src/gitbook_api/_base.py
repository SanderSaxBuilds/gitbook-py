"""Shared request building and response handling for both clients."""

from __future__ import annotations

import dataclasses
import logging
import os
import platform
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple, Union
from urllib.parse import quote

import httpx

from ._version import __version__
from .errors import APIStatusError, GitBookError, make_status_error
from .retry import RetryPolicy, parse_retry_after

logger = logging.getLogger("gitbook_api")

DEFAULT_BASE_URL = "https://api.gitbook.com/v1"
DEFAULT_TIMEOUT = 30.0
TOKEN_ENV_VAR = "GITBOOK_TOKEN"
BASE_URL_ENV_VAR = "GITBOOK_BASE_URL"

QueryValue = Union[str, int, float, bool, None, Sequence[str]]
Query = Mapping[str, QueryValue]
TimeoutTypes = Union[float, httpx.Timeout, None]


class NotGiven:
    """Marks an argument the caller left out, where ``None`` has a meaning.

    For example ``default_level=None`` sets "guest" level, while leaving
    ``default_level`` out does not touch the field.
    """

    _instance: Optional["NotGiven"] = None

    def __new__(cls) -> "NotGiven":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __bool__(self) -> bool:
        return False

    def __repr__(self) -> str:
        return "NOT_GIVEN"


NOT_GIVEN = NotGiven()


def segment(value: str, name: str = "id") -> str:
    """URL-encode one path segment and reject empty IDs."""
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
    return quote(value, safe="")


def page_path_segment(path: str) -> str:
    """Encode a page path like ``guides/install``, keeping its slashes."""
    if not isinstance(path, str):
        raise ValueError("path must be a string")
    cleaned = path.strip().strip("/")
    if not cleaned:
        raise ValueError("path must name a page, for example 'getting-started'")
    return quote(cleaned, safe="/")


def clean_query(params: Optional[Query]) -> List[Tuple[str, str]]:
    """Drop ``None`` values and turn the rest into wire strings.

    Booleans become ``true``/``false`` and sequences repeat the key, which
    is how the official TypeScript client sends array parameters.
    """
    out: List[Tuple[str, str]] = []
    if not params:
        return out
    for key, value in params.items():
        if value is None:
            continue
        if isinstance(value, bool):
            out.append((key, "true" if value else "false"))
        elif isinstance(value, (str, int, float)):
            out.append((key, str(value)))
        else:
            for item in value:
                out.append((key, str(item)))
    return out


def compact(body: Mapping[str, Any]) -> Dict[str, Any]:
    """Remove arguments the caller did not give from a request body."""
    return {k: v for k, v in body.items() if v is not NOT_GIVEN}


class BaseClient:
    """Configuration and plumbing shared by :class:`GitBook` and :class:`AsyncGitBook`."""

    def __init__(
        self,
        token: Optional[str] = None,
        *,
        base_url: Optional[str] = None,
        timeout: TimeoutTypes = DEFAULT_TIMEOUT,
        max_retries: Optional[int] = None,
        retry: Optional[RetryPolicy] = None,
        user_agent: Optional[str] = None,
        default_headers: Optional[Mapping[str, str]] = None,
    ) -> None:
        resolved = token if token is not None else os.environ.get(TOKEN_ENV_VAR)
        if not resolved or not resolved.strip():
            raise GitBookError(
                f"No API token. Pass token=... or set the {TOKEN_ENV_VAR} environment variable."
            )
        self._token = resolved.strip()
        url = base_url or os.environ.get(BASE_URL_ENV_VAR) or DEFAULT_BASE_URL
        self.base_url = url.rstrip("/")
        self.timeout = timeout
        policy = retry or RetryPolicy()
        if max_retries is not None:
            policy = dataclasses.replace(policy, max_retries=max_retries)
        self.retry = policy
        self.user_agent = user_agent or default_user_agent()
        self._default_headers = dict(default_headers or {})

    def __repr__(self) -> str:
        return f"{type(self).__name__}(base_url={self.base_url!r})"

    def _headers(self) -> Dict[str, str]:
        headers = {
            "Accept": "application/json",
            "User-Agent": self.user_agent,
        }
        headers.update(self._default_headers)
        headers["Authorization"] = f"Bearer {self._token}"
        return headers

    def _url(self, path: str) -> str:
        if not path.startswith("/"):
            path = "/" + path
        return self.base_url + path

    def _retry_delay(self, method: str, response: httpx.Response, attempt: int) -> Optional[float]:
        """Seconds to wait before retrying ``response``, or ``None`` to raise."""
        status = response.status_code
        if not self.retry.should_retry_status(method, status, attempt):
            return None
        wait = parse_retry_after(response.headers, status)
        if wait is not None:
            if wait > self.retry.max_retry_after:
                logger.debug("server asked to wait %.1fs, over the limit, not retrying", wait)
                return None
            return wait
        return self.retry.backoff(attempt)

    def _status_error(self, response: httpx.Response) -> APIStatusError:
        return make_status_error(
            response, retry_after=parse_retry_after(response.headers, response.status_code)
        )

    @staticmethod
    def _decode(response: httpx.Response) -> Any:
        if response.status_code in (204, 205) or not response.content:
            return None
        try:
            return response.json()
        except ValueError:
            return response.text


def default_user_agent() -> str:
    return (
        f"gitbook-py/{__version__} "
        f"python/{platform.python_version()} httpx/{httpx.__version__}"
    )


def exc_request(exc: httpx.RequestError) -> Optional[httpx.Request]:
    """The request attached to an httpx error, when httpx set one."""
    try:
        return exc.request
    except RuntimeError:
        return None


def check_limit(limit: Optional[int]) -> Optional[int]:
    """Validate a page size against the spec range (1 to 1000)."""
    if limit is None:
        return None
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 1000:
        raise ValueError("limit must be an integer from 1 to 1000")
    return limit
