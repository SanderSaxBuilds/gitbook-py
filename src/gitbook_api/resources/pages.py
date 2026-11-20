"""Pages and page content.

Every method reads from one of three sources:

* the live content of a space (default),
* a change request (``change_request_id=...``),
* a historical revision (``revision_id=...``).
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, Iterator, List, Literal, Optional, Sequence, Union, cast

from .._base import page_path_segment, segment
from ..types import JSONDocument, MarkdownRefsFormat, PageFormat, RevisionPage
from ._resource import AsyncResource, SyncResource

__all__ = ["AsyncPagesResource", "PagesResource", "iter_pages"]

Evaluated = Union[bool, Literal["deterministic-only"]]
Dereferenced = Union[bool, Literal["reusable-contents"]]


def iter_pages(pages: Iterable[RevisionPage]) -> Iterator[RevisionPage]:
    """Yield every page in a page tree, parents before children.

    ``pages.list()`` returns the top level with children nested under
    ``pages``. This flattens it in table-of-contents order.
    """
    for page in pages:
        yield page
        children = cast(Dict[str, Any], page).get("pages")
        if isinstance(children, list):
            yield from iter_pages(children)


def _prefix(space_id: str, change_request_id: Optional[str], revision_id: Optional[str]) -> str:
    base = f"/spaces/{segment(space_id, 'space_id')}"
    if change_request_id is not None and revision_id is not None:
        raise ValueError("pass change_request_id or revision_id, not both")
    if change_request_id is not None:
        return f"{base}/change-requests/{segment(change_request_id, 'change_request_id')}/content"
    if revision_id is not None:
        return f"{base}/revisions/{segment(revision_id, 'revision_id')}"
    return f"{base}/content"


def _content_query(
    format: Optional[PageFormat],
    markdown_refs: Optional[MarkdownRefsFormat],
    evaluated: Optional[Evaluated],
    dereferenced: Optional[Dereferenced],
    metadata: Optional[bool],
    computed: Optional[bool],
) -> Dict[str, Any]:
    return {
        "format": format,
        "format.markdown.refs": markdown_refs,
        "evaluated": evaluated,
        "dereferenced": dereferenced,
        "metadata": metadata,
        "computed": computed,
    }


def _markdown_of(page: Any) -> str:
    if isinstance(page, dict) and isinstance(page.get("markdown"), str):
        return cast(str, page["markdown"])
    return ""


def _tag_query(tag: Union[str, Sequence[str], None]) -> Optional[List[str]]:
    """Normalise the ``tag`` filter of the page list endpoints.

    One slug or several, sent as a repeated ``tag`` parameter. The API needs
    at least one non-empty slug when the parameter is present.
    """
    if tag is None:
        return None
    slugs = [tag] if isinstance(tag, str) else list(tag)
    if not slugs or any(not isinstance(s, str) or not s for s in slugs):
        raise ValueError("tag must be a non-empty slug or a non-empty list of slugs")
    return slugs


def _pages_of(data: Any) -> List[RevisionPage]:
    if isinstance(data, dict) and isinstance(data.get("pages"), list):
        return cast(List[RevisionPage], data["pages"])
    raise TypeError("expected an object with a 'pages' array")


class PagesResource(SyncResource):
    def list(
        self,
        space_id: str,
        *,
        change_request_id: Optional[str] = None,
        revision_id: Optional[str] = None,
        metadata: Optional[bool] = None,
        computed: Optional[bool] = None,
        tag: Union[str, Sequence[str], None] = None,
    ) -> List[RevisionPage]:
        """The page tree (``listPages``, ``listPagesInChangeRequest``, ``listPagesInRevisionById``).

        Top-level pages come back with children nested under ``pages``.
        Use :func:`iter_pages` to walk all of them.

        ``tag`` narrows the tree to document pages tagged with any of the
        given tag or category slugs, plus the pages above them. Get the slugs
        from :meth:`SpacesResource.list_tags`.
        """
        path = _prefix(space_id, change_request_id, revision_id) + "/pages"
        data = self._client.request(
            "GET",
            path,
            params={"metadata": metadata, "computed": computed, "tag": _tag_query(tag)},
        )
        return _pages_of(data)

    def get(
        self,
        space_id: str,
        page_id: str,
        *,
        change_request_id: Optional[str] = None,
        revision_id: Optional[str] = None,
        format: Optional[PageFormat] = None,
        markdown_refs: Optional[MarkdownRefsFormat] = None,
        evaluated: Optional[Evaluated] = None,
        dereferenced: Optional[Dereferenced] = None,
        metadata: Optional[bool] = None,
        computed: Optional[bool] = None,
    ) -> RevisionPage:
        """One page by ID (``getPageById`` and its change request and revision forms).

        ``format="markdown"`` puts the body in ``page["markdown"]``;
        ``format="document"`` puts the block tree in ``page["document"]``.
        """
        path = f"{_prefix(space_id, change_request_id, revision_id)}/page/{segment(page_id, 'page_id')}"
        query = _content_query(format, markdown_refs, evaluated, dereferenced, metadata, computed)
        return cast(RevisionPage, self._client.request("GET", path, params=query))

    def get_by_path(
        self,
        space_id: str,
        path: str,
        *,
        change_request_id: Optional[str] = None,
        revision_id: Optional[str] = None,
        format: Optional[PageFormat] = None,
        markdown_refs: Optional[MarkdownRefsFormat] = None,
        evaluated: Optional[Evaluated] = None,
        dereferenced: Optional[Dereferenced] = None,
        metadata: Optional[bool] = None,
        computed: Optional[bool] = None,
    ) -> RevisionPage:
        """One page by its URL path, such as ``"guides/install"`` (``getPageByPath``).

        The API answers with a document page or a group.
        """
        url = f"{_prefix(space_id, change_request_id, revision_id)}/path/{page_path_segment(path)}"
        query = _content_query(format, markdown_refs, evaluated, dereferenced, metadata, computed)
        return cast(RevisionPage, self._client.request("GET", url, params=query))

    def get_markdown(
        self,
        space_id: str,
        page_id: str,
        *,
        change_request_id: Optional[str] = None,
        revision_id: Optional[str] = None,
    ) -> str:
        """A page body as Markdown. Groups and links give an empty string."""
        page = self.get(
            space_id,
            page_id,
            change_request_id=change_request_id,
            revision_id=revision_id,
            format="markdown",
        )
        return _markdown_of(page)

    def get_document(
        self,
        space_id: str,
        page_id: str,
        *,
        revision_id: str,
        evaluated: Optional[Evaluated] = None,
        dereferenced: Optional[Dereferenced] = None,
    ) -> JSONDocument:
        """The raw block tree of a page in a revision (``getPageDocumentInRevisionById``).

        ``space["revision"]`` holds the live revision ID.
        """
        path = (
            f"{_prefix(space_id, None, revision_id)}/page/{segment(page_id, 'page_id')}/document"
        )
        query = {"evaluated": evaluated, "dereferenced": dereferenced}
        return cast(JSONDocument, self._client.request("GET", path, params=query))


class AsyncPagesResource(AsyncResource):
    async def list(
        self,
        space_id: str,
        *,
        change_request_id: Optional[str] = None,
        revision_id: Optional[str] = None,
        metadata: Optional[bool] = None,
        computed: Optional[bool] = None,
        tag: Union[str, Sequence[str], None] = None,
    ) -> List[RevisionPage]:
        """The page tree of a space, change request or revision, optionally narrowed by ``tag``."""
        path = _prefix(space_id, change_request_id, revision_id) + "/pages"
        data = await self._client.request(
            "GET",
            path,
            params={"metadata": metadata, "computed": computed, "tag": _tag_query(tag)},
        )
        return _pages_of(data)

    async def get(
        self,
        space_id: str,
        page_id: str,
        *,
        change_request_id: Optional[str] = None,
        revision_id: Optional[str] = None,
        format: Optional[PageFormat] = None,
        markdown_refs: Optional[MarkdownRefsFormat] = None,
        evaluated: Optional[Evaluated] = None,
        dereferenced: Optional[Dereferenced] = None,
        metadata: Optional[bool] = None,
        computed: Optional[bool] = None,
    ) -> RevisionPage:
        """One page by ID."""
        path = f"{_prefix(space_id, change_request_id, revision_id)}/page/{segment(page_id, 'page_id')}"
        query = _content_query(format, markdown_refs, evaluated, dereferenced, metadata, computed)
        return cast(RevisionPage, await self._client.request("GET", path, params=query))

    async def get_by_path(
        self,
        space_id: str,
        path: str,
        *,
        change_request_id: Optional[str] = None,
        revision_id: Optional[str] = None,
        format: Optional[PageFormat] = None,
        markdown_refs: Optional[MarkdownRefsFormat] = None,
        evaluated: Optional[Evaluated] = None,
        dereferenced: Optional[Dereferenced] = None,
        metadata: Optional[bool] = None,
        computed: Optional[bool] = None,
    ) -> RevisionPage:
        """One page by its URL path."""
        url = f"{_prefix(space_id, change_request_id, revision_id)}/path/{page_path_segment(path)}"
        query = _content_query(format, markdown_refs, evaluated, dereferenced, metadata, computed)
        return cast(RevisionPage, await self._client.request("GET", url, params=query))

    async def get_markdown(
        self,
        space_id: str,
        page_id: str,
        *,
        change_request_id: Optional[str] = None,
        revision_id: Optional[str] = None,
    ) -> str:
        """A page body as Markdown."""
        page = await self.get(
            space_id,
            page_id,
            change_request_id=change_request_id,
            revision_id=revision_id,
            format="markdown",
        )
        return _markdown_of(page)

    async def get_document(
        self,
        space_id: str,
        page_id: str,
        *,
        revision_id: str,
        evaluated: Optional[Evaluated] = None,
        dereferenced: Optional[Dereferenced] = None,
    ) -> JSONDocument:
        """The raw block tree of a page in a revision."""
        path = (
            f"{_prefix(space_id, None, revision_id)}/page/{segment(page_id, 'page_id')}/document"
        )
        query = {"evaluated": evaluated, "dereferenced": dereferenced}
        return cast(JSONDocument, await self._client.request("GET", path, params=query))
