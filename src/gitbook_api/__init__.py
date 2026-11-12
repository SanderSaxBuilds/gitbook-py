"""Typed Python client for the GitBook API.

    from gitbook_api import GitBook

    with GitBook() as client:          # reads GITBOOK_TOKEN
        print(client.users.me()["displayName"])
"""

from ._base import NOT_GIVEN, NotGiven
from ._client import AsyncGitBook, GitBook
from ._version import __version__
from .errors import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    AuthenticationError,
    BadRequestError,
    ConflictError,
    FeatureNotAvailableError,
    GitBookError,
    InternalServerError,
    NotFoundError,
    PermissionDeniedError,
    PreconditionFailedError,
    RateLimitError,
    UnprocessableEntityError,
)
from .pagination import AsyncPaginator, Page, SyncPaginator
from .resources import SEARCH_TOOL, format_results, iter_pages
from .retry import RetryPolicy
from .text import document_to_text, make_snippet, markdown_to_text

__all__ = [
    "APIConnectionError",
    "APIStatusError",
    "APITimeoutError",
    "AsyncGitBook",
    "AsyncPaginator",
    "AuthenticationError",
    "BadRequestError",
    "ConflictError",
    "FeatureNotAvailableError",
    "GitBook",
    "GitBookError",
    "InternalServerError",
    "NOT_GIVEN",
    "NotFoundError",
    "NotGiven",
    "Page",
    "PermissionDeniedError",
    "PreconditionFailedError",
    "RateLimitError",
    "RetryPolicy",
    "SEARCH_TOOL",
    "SyncPaginator",
    "UnprocessableEntityError",
    "__version__",
    "document_to_text",
    "format_results",
    "iter_pages",
    "make_snippet",
    "markdown_to_text",
]
