from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .._client import AsyncGitBook, GitBook


class SyncResource:
    """Base for resource groups on :class:`~gitbook_api.GitBook`."""

    def __init__(self, client: "GitBook") -> None:
        self._client = client


class AsyncResource:
    """Base for resource groups on :class:`~gitbook_api.AsyncGitBook`."""

    def __init__(self, client: "AsyncGitBook") -> None:
        self._client = client
