"""The synchronous :class:`GitBook` and asynchronous :class:`AsyncGitBook` clients."""

from __future__ import annotations

import asyncio
import time
from types import TracebackType
from typing import Any, Awaitable, Callable, Dict, Mapping, Optional, Type

import httpx

from ._base import BaseClient, Query, TimeoutTypes, check_limit, clean_query, exc_request, logger
from .errors import APIConnectionError, APITimeoutError
from .pagination import AsyncPaginator, Page, SyncPaginator, page_from_response
from .resources.change_requests import AsyncChangeRequestsResource, ChangeRequestsResource
from .resources.collections import AsyncCollectionsResource, CollectionsResource
from .resources.organizations import AsyncOrganizationsResource, OrganizationsResource
from .resources.pages import AsyncPagesResource, PagesResource
from .resources.search import AsyncSearchResource, SearchResource
from .resources.spaces import AsyncSpacesResource, SpacesResource
from .resources.users import AsyncUsersResource, UsersResource
from .retry import RetryPolicy

__all__ = ["AsyncGitBook", "GitBook"]


class GitBook(BaseClient):
    """Synchronous client for the GitBook REST API.

    Args:
        token: Personal access token. Falls back to ``GITBOOK_TOKEN``.
        base_url: API root, ``https://api.gitbook.com/v1`` by default.
        timeout: Seconds per request, or an ``httpx.Timeout``.
        max_retries: Shortcut for ``RetryPolicy(max_retries=...)``.
        retry: Full :class:`~gitbook_api.retry.RetryPolicy`.
        user_agent: Replaces the default ``gitbook-py/<version>`` agent.
        default_headers: Extra headers sent with every request.
        http_client: Your own ``httpx.Client`` (proxies, transports). The
            client does not close one it did not create.

    Use it as a context manager, or call :meth:`close` when done::

        with GitBook("gb_api_...") as client:
            me = client.users.me()
    """

    def __init__(
        self,
        token: Optional[str] = None,
        *,
        base_url: Optional[str] = None,
        timeout: TimeoutTypes = 30.0,
        max_retries: Optional[int] = None,
        retry: Optional[RetryPolicy] = None,
        user_agent: Optional[str] = None,
        default_headers: Optional[Mapping[str, str]] = None,
        http_client: Optional[httpx.Client] = None,
    ) -> None:
        super().__init__(
            token,
            base_url=base_url,
            timeout=timeout,
            max_retries=max_retries,
            retry=retry,
            user_agent=user_agent,
            default_headers=default_headers,
        )
        self._owns_http = http_client is None
        self._http = http_client or httpx.Client(timeout=timeout)
        self._sleep: Callable[[float], None] = time.sleep

        self.users = UsersResource(self)
        self.organizations = OrganizationsResource(self)
        self.spaces = SpacesResource(self)
        self.pages = PagesResource(self)
        self.search = SearchResource(self)
        self.change_requests = ChangeRequestsResource(self)
        self.collections = CollectionsResource(self)

    def request(
        self,
        method: str,
        path: str,
        *,
        params: Optional[Query] = None,
        json: Optional[Mapping[str, Any]] = None,
        headers: Optional[Mapping[str, str]] = None,
    ) -> Any:
        """Send one API request with retries and return the decoded body.

        ``path`` is relative to ``base_url``, for example ``"/user"``. This is
        also the way to call endpoints the typed resources do not cover.
        Returns ``None`` for empty responses such as 204.
        """
        method = method.upper()
        url = self._url(path)
        query = httpx.QueryParams(tuple(clean_query(params)))
        all_headers: Dict[str, str] = self._headers()
        if headers:
            all_headers.update(headers)
        attempt = 0
        while True:
            try:
                response = self._http.request(
                    method,
                    url,
                    params=query,
                    json=dict(json) if json is not None else None,
                    headers=all_headers,
                    timeout=self.timeout,
                )
            except httpx.TimeoutException as exc:
                if self.retry.should_retry_error(method, attempt):
                    self._backoff_after_error(method, url, attempt, exc)
                    attempt += 1
                    continue
                raise APITimeoutError(f"request timed out: {method} {url}", request=exc_request(exc)) from exc
            except httpx.TransportError as exc:
                if self.retry.should_retry_error(method, attempt):
                    self._backoff_after_error(method, url, attempt, exc)
                    attempt += 1
                    continue
                raise APIConnectionError(
                    f"connection failed: {method} {url}: {exc}", request=exc_request(exc)
                ) from exc

            if response.is_success:
                return self._decode(response)
            delay = self._retry_delay(method, response, attempt)
            if delay is None:
                raise self._status_error(response)
            logger.info(
                "retrying %s %s after HTTP %s in %.2fs (retry %d of %d)",
                method, url, response.status_code, delay, attempt + 1, self.retry.max_retries,
            )
            response.close()
            self._sleep(delay)
            attempt += 1

    def _backoff_after_error(self, method: str, url: str, attempt: int, exc: Exception) -> None:
        delay = self.retry.backoff(attempt)
        logger.info(
            "retrying %s %s after %s in %.2fs (retry %d of %d)",
            method, url, type(exc).__name__, delay, attempt + 1, self.retry.max_retries,
        )
        self._sleep(delay)

    def paginate(
        self,
        path: str,
        params: Optional[Query] = None,
        *,
        limit: Optional[int] = None,
        max_items: Optional[int] = None,
    ) -> SyncPaginator[Any]:
        """Paginator over any list endpoint, for paths without a typed method."""
        base: Dict[str, Any] = dict(params or {})
        if check_limit(limit) is not None:
            base["limit"] = limit

        def fetch(token: Optional[str]) -> Page[Any]:
            query = dict(base)
            if token is not None:
                query["page"] = token
            return page_from_response(self.request("GET", path, params=query))

        return SyncPaginator(fetch, max_items=max_items)

    def close(self) -> None:
        """Close the HTTP connection pool if this client created it."""
        if self._owns_http:
            self._http.close()

    def __enter__(self) -> "GitBook":
        return self

    def __exit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc: Optional[BaseException],
        tb: Optional[TracebackType],
    ) -> None:
        self.close()


class AsyncGitBook(BaseClient):
    """Asynchronous client for the GitBook REST API.

    Takes the same arguments as :class:`GitBook`, with an optional
    ``httpx.AsyncClient`` as ``http_client``::

        async with AsyncGitBook("gb_api_...") as client:
            me = await client.users.me()
            async for space in client.spaces.list(org_id):
                print(space["title"])
    """

    def __init__(
        self,
        token: Optional[str] = None,
        *,
        base_url: Optional[str] = None,
        timeout: TimeoutTypes = 30.0,
        max_retries: Optional[int] = None,
        retry: Optional[RetryPolicy] = None,
        user_agent: Optional[str] = None,
        default_headers: Optional[Mapping[str, str]] = None,
        http_client: Optional[httpx.AsyncClient] = None,
    ) -> None:
        super().__init__(
            token,
            base_url=base_url,
            timeout=timeout,
            max_retries=max_retries,
            retry=retry,
            user_agent=user_agent,
            default_headers=default_headers,
        )
        self._owns_http = http_client is None
        self._http = http_client or httpx.AsyncClient(timeout=timeout)
        self._sleep: Callable[[float], Awaitable[None]] = asyncio.sleep

        self.users = AsyncUsersResource(self)
        self.organizations = AsyncOrganizationsResource(self)
        self.spaces = AsyncSpacesResource(self)
        self.pages = AsyncPagesResource(self)
        self.search = AsyncSearchResource(self)
        self.change_requests = AsyncChangeRequestsResource(self)
        self.collections = AsyncCollectionsResource(self)

    async def request(
        self,
        method: str,
        path: str,
        *,
        params: Optional[Query] = None,
        json: Optional[Mapping[str, Any]] = None,
        headers: Optional[Mapping[str, str]] = None,
    ) -> Any:
        """Async version of :meth:`GitBook.request`."""
        method = method.upper()
        url = self._url(path)
        query = httpx.QueryParams(tuple(clean_query(params)))
        all_headers: Dict[str, str] = self._headers()
        if headers:
            all_headers.update(headers)
        attempt = 0
        while True:
            try:
                response = await self._http.request(
                    method,
                    url,
                    params=query,
                    json=dict(json) if json is not None else None,
                    headers=all_headers,
                    timeout=self.timeout,
                )
            except httpx.TimeoutException as exc:
                if self.retry.should_retry_error(method, attempt):
                    await self._backoff_after_error(method, url, attempt, exc)
                    attempt += 1
                    continue
                raise APITimeoutError(f"request timed out: {method} {url}", request=exc_request(exc)) from exc
            except httpx.TransportError as exc:
                if self.retry.should_retry_error(method, attempt):
                    await self._backoff_after_error(method, url, attempt, exc)
                    attempt += 1
                    continue
                raise APIConnectionError(
                    f"connection failed: {method} {url}: {exc}", request=exc_request(exc)
                ) from exc

            if response.is_success:
                return self._decode(response)
            delay = self._retry_delay(method, response, attempt)
            if delay is None:
                raise self._status_error(response)
            logger.info(
                "retrying %s %s after HTTP %s in %.2fs (retry %d of %d)",
                method, url, response.status_code, delay, attempt + 1, self.retry.max_retries,
            )
            await response.aclose()
            await self._sleep(delay)
            attempt += 1

    async def _backoff_after_error(
        self, method: str, url: str, attempt: int, exc: Exception
    ) -> None:
        delay = self.retry.backoff(attempt)
        logger.info(
            "retrying %s %s after %s in %.2fs (retry %d of %d)",
            method, url, type(exc).__name__, delay, attempt + 1, self.retry.max_retries,
        )
        await self._sleep(delay)

    def paginate(
        self,
        path: str,
        params: Optional[Query] = None,
        *,
        limit: Optional[int] = None,
        max_items: Optional[int] = None,
    ) -> AsyncPaginator[Any]:
        """Async paginator over any list endpoint."""
        base: Dict[str, Any] = dict(params or {})
        if check_limit(limit) is not None:
            base["limit"] = limit

        async def fetch(token: Optional[str]) -> Page[Any]:
            query = dict(base)
            if token is not None:
                query["page"] = token
            return page_from_response(await self.request("GET", path, params=query))

        return AsyncPaginator(fetch, max_items=max_items)

    async def close(self) -> None:
        """Close the HTTP connection pool if this client created it."""
        if self._owns_http:
            await self._http.aclose()

    async def __aenter__(self) -> "AsyncGitBook":
        return self

    async def __aexit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc: Optional[BaseException],
        tb: Optional[TracebackType],
    ) -> None:
        await self.close()
