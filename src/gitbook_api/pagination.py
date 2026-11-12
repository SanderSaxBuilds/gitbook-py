"""Cursor pagination over GitBook list endpoints.

List endpoints return ``{"items": [...], "next": {"page": "<token>"}, "count": n}``.
The next page is fetched by sending the token back as the ``page`` query
parameter. When ``next`` is missing there are no more pages.

List methods on the client return a paginator. Nothing is requested until
you iterate it::

    for space in client.spaces.list("org_id"):
        print(space["title"])

    for page in client.spaces.list("org_id", limit=50).pages():
        print(len(page.items), page.next_page)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import (
    Any,
    AsyncIterator,
    Awaitable,
    Callable,
    Generic,
    Iterator,
    List,
    Optional,
    TypeVar,
)

__all__ = ["AsyncPaginator", "Page", "SyncPaginator"]

T = TypeVar("T")


@dataclass(frozen=True)
class Page(Generic[T]):
    """One page of a list response.

    Attributes:
        items: Objects on this page.
        next_page: Token for the next page, ``None`` on the last page.
        count: Total count when the API includes it.
    """

    items: List[T]
    next_page: Optional[str] = None
    count: Optional[int] = None

    @property
    def has_next(self) -> bool:
        return self.next_page is not None


def page_from_response(data: Any) -> Page[Any]:
    """Turn a decoded list body into a :class:`Page`."""
    if not isinstance(data, dict):
        raise TypeError(f"expected a list response object, got {type(data).__name__}")
    items = data.get("items")
    if not isinstance(items, list):
        raise TypeError("list response has no 'items' array")
    nxt = data.get("next")
    token = nxt.get("page") if isinstance(nxt, dict) else None
    count = data.get("count")
    return Page(
        items=items,
        next_page=token if isinstance(token, str) and token else None,
        count=int(count) if isinstance(count, (int, float)) else None,
    )


class SyncPaginator(Generic[T]):
    """Lazy iterator over every item of a paginated endpoint.

    Args:
        fetch: Called with the page token (``None`` for the first page).
        max_items: Stop after this many items in total.
    """

    def __init__(
        self,
        fetch: Callable[[Optional[str]], Page[T]],
        *,
        max_items: Optional[int] = None,
    ) -> None:
        if max_items is not None and max_items < 0:
            raise ValueError("max_items must be 0 or more")
        self._fetch = fetch
        self._max_items = max_items

    def first_page(self) -> Page[T]:
        """Fetch only the first page."""
        return self._fetch(None)

    def get_page(self, token: Optional[str]) -> Page[T]:
        """Fetch the page for ``token`` (from :attr:`Page.next_page`)."""
        return self._fetch(token)

    def pages(self) -> Iterator[Page[T]]:
        """Yield whole pages until the last one."""
        token: Optional[str] = None
        seen: set[str] = set()
        while True:
            page = self._fetch(token)
            yield page
            if page.next_page is None or page.next_page in seen:
                return
            seen.add(page.next_page)
            token = page.next_page

    def __iter__(self) -> Iterator[T]:
        remaining = self._max_items
        if remaining == 0:
            return
        for page in self.pages():
            for item in page.items:
                yield item
                if remaining is not None:
                    remaining -= 1
                    if remaining <= 0:
                        return

    def to_list(self) -> List[T]:
        """Fetch every page and return all items."""
        return list(self)


class AsyncPaginator(Generic[T]):
    """Async counterpart of :class:`SyncPaginator`.

    Use ``async for item in paginator`` or ``async for page in paginator.pages()``.
    """

    def __init__(
        self,
        fetch: Callable[[Optional[str]], Awaitable[Page[T]]],
        *,
        max_items: Optional[int] = None,
    ) -> None:
        if max_items is not None and max_items < 0:
            raise ValueError("max_items must be 0 or more")
        self._fetch = fetch
        self._max_items = max_items

    async def first_page(self) -> Page[T]:
        """Fetch only the first page."""
        return await self._fetch(None)

    async def get_page(self, token: Optional[str]) -> Page[T]:
        """Fetch the page for ``token`` (from :attr:`Page.next_page`)."""
        return await self._fetch(token)

    async def pages(self) -> AsyncIterator[Page[T]]:
        """Yield whole pages until the last one."""
        token: Optional[str] = None
        seen: set[str] = set()
        while True:
            page = await self._fetch(token)
            yield page
            if page.next_page is None or page.next_page in seen:
                return
            seen.add(page.next_page)
            token = page.next_page

    async def _items(self) -> AsyncIterator[T]:
        remaining = self._max_items
        if remaining == 0:
            return
        async for page in self.pages():
            for item in page.items:
                yield item
                if remaining is not None:
                    remaining -= 1
                    if remaining <= 0:
                        return

    def __aiter__(self) -> AsyncIterator[T]:
        return self._items()

    async def to_list(self) -> List[T]:
        """Fetch every page and return all items."""
        return [item async for item in self]
