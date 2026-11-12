"""Exceptions raised by the client.

Everything derives from :class:`GitBookError`. HTTP failures raise a
subclass of :class:`APIStatusError` chosen by status code, so callers can
catch exactly the case they care about::

    try:
        client.spaces.get("missing")
    except NotFoundError:
        ...
"""

from __future__ import annotations

from typing import Any, Dict, Optional, Type

import httpx

__all__ = [
    "APIConnectionError",
    "APIStatusError",
    "APITimeoutError",
    "AuthenticationError",
    "BadRequestError",
    "ConflictError",
    "FeatureNotAvailableError",
    "GitBookError",
    "InternalServerError",
    "NotFoundError",
    "PermissionDeniedError",
    "PreconditionFailedError",
    "RateLimitError",
    "UnprocessableEntityError",
]


class GitBookError(Exception):
    """Base class for every error this package raises."""


class APIConnectionError(GitBookError):
    """The request never got an HTTP response (DNS, TLS, reset connection)."""

    def __init__(self, message: str, *, request: Optional[httpx.Request] = None) -> None:
        super().__init__(message)
        self.request = request


class APITimeoutError(APIConnectionError):
    """The request timed out before a response arrived."""


class APIStatusError(GitBookError):
    """The API answered with a 4xx or 5xx status.

    Attributes:
        status_code: HTTP status of the response.
        message: ``error.message`` from the body when present, otherwise the
            reason phrase.
        body: Decoded JSON body, or the raw text when it was not JSON.
        response: The underlying ``httpx.Response``.
        request_id: Value of the ``X-Request-Id`` header when the API sent one.
    """

    status_code: int

    def __init__(self, message: str, *, response: httpx.Response, body: Any) -> None:
        super().__init__(message)
        self.message = message
        self.response = response
        self.status_code = response.status_code
        self.body = body
        self.request_id: Optional[str] = response.headers.get("x-request-id")

    @property
    def error_type(self) -> Optional[str]:
        """``error.type`` from the body, set on some errors such as plan limits."""
        error = _error_object(self.body)
        value = error.get("type") if error else None
        return value if isinstance(value, str) else None

    def __str__(self) -> str:
        return f"{self.status_code}: {self.message}"


class BadRequestError(APIStatusError):
    """400, the request was malformed or failed validation."""


class AuthenticationError(APIStatusError):
    """401, the token is missing, invalid or expired."""


class PermissionDeniedError(APIStatusError):
    """403, the token cannot access this resource."""


class FeatureNotAvailableError(PermissionDeniedError):
    """403 with ``error.type == "feature-not-available"``.

    The organization's plan does not include the feature. ``upgrade`` holds
    the ``error.upgrade`` object the API returns, with the required plan.
    """

    @property
    def upgrade(self) -> Dict[str, Any]:
        error = _error_object(self.body)
        value = error.get("upgrade") if error else None
        return value if isinstance(value, dict) else {}


class NotFoundError(APIStatusError):
    """404, the resource does not exist or is not visible to this token."""


class ConflictError(APIStatusError):
    """409, the request conflicts with the current state."""


class PreconditionFailedError(APIStatusError):
    """412, a precondition of the operation was not met."""


class UnprocessableEntityError(APIStatusError):
    """422, the body was understood but could not be processed."""


class RateLimitError(APIStatusError):
    """429, too many requests.

    ``retry_after`` is the number of seconds the API asked the client to
    wait, read from ``Retry-After`` or ``X-RateLimit-Reset``, when known.
    """

    def __init__(
        self,
        message: str,
        *,
        response: httpx.Response,
        body: Any,
        retry_after: Optional[float] = None,
    ) -> None:
        super().__init__(message, response=response, body=body)
        self.retry_after = retry_after


class InternalServerError(APIStatusError):
    """5xx, the API failed while handling the request."""


_STATUS_ERRORS: Dict[int, Type[APIStatusError]] = {
    400: BadRequestError,
    401: AuthenticationError,
    403: PermissionDeniedError,
    404: NotFoundError,
    409: ConflictError,
    412: PreconditionFailedError,
    422: UnprocessableEntityError,
    429: RateLimitError,
}


def _error_object(body: Any) -> Optional[Dict[str, Any]]:
    if isinstance(body, dict):
        error = body.get("error")
        if isinstance(error, dict):
            return error
    return None


def _decode_body(response: httpx.Response) -> Any:
    if not response.content:
        return None
    try:
        return response.json()
    except ValueError:
        return response.text


def make_status_error(
    response: httpx.Response, *, retry_after: Optional[float] = None
) -> APIStatusError:
    """Build the right :class:`APIStatusError` subclass for ``response``."""
    body = _decode_body(response)
    error = _error_object(body)
    message: str
    if error and isinstance(error.get("message"), str):
        message = error["message"]
    elif isinstance(body, str) and body.strip():
        message = body.strip()[:500]
    else:
        message = response.reason_phrase or "HTTP error"

    status = response.status_code
    if status == 429:
        return RateLimitError(message, response=response, body=body, retry_after=retry_after)
    if status == 403 and error and error.get("type") == "feature-not-available":
        return FeatureNotAvailableError(message, response=response, body=body)
    cls = _STATUS_ERRORS.get(status)
    if cls is None:
        cls = InternalServerError if status >= 500 else APIStatusError
    return cls(message, response=response, body=body)
