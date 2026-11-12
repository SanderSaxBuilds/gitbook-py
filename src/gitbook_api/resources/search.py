"""Content search in a space or across an organization, plus a helper for LLM tools."""

from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Optional, Sequence, cast

from .._base import segment
from ..errors import NotFoundError
from ..pagination import AsyncPaginator, SyncPaginator
from ..text import make_snippet, markdown_to_text
from ..types import LLMSearchResult, SearchPageResult, SearchSpaceResult
from ._resource import AsyncResource, SyncResource
from .pages import _markdown_of

__all__ = [
    "AsyncSearchResource",
    "SEARCH_TOOL",
    "SearchResource",
    "format_results",
]

SEARCH_TOOL: Dict[str, Any] = {
    "name": "search_docs",
    "description": (
        "Search the product documentation and return the most relevant pages, "
        "each with its title, path, a plain-text excerpt and a link. Use it "
        "before answering questions about how the product works."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Words or a short question to search for.",
            },
            "limit": {
                "type": "integer",
                "minimum": 1,
                "maximum": 20,
                "description": "How many pages to return, 5 if left out.",
            },
        },
        "required": ["query"],
    },
}
"""A provider-neutral tool definition for :meth:`SearchResource.for_llm`.

``parameters`` is plain JSON Schema. Rename the key to whatever your model
API expects, for example ``input_schema``.
"""


def _check_query(query: str) -> str:
    if not isinstance(query, str) or not query.strip():
        raise ValueError("query must be a non-empty string")
    return query.strip()


def _section_text(result: SearchPageResult) -> str:
    sections = sorted(
        result.get("sections") or [], key=lambda s: s.get("score", 0.0), reverse=True
    )
    parts = [markdown_to_text(s.get("body") or "") for s in sections]
    return " ".join(p for p in parts if p)


def _hit(result: SearchPageResult, snippet: str) -> LLMSearchResult:
    urls = result.get("urls") or {}
    return {
        "title": result.get("title", ""),
        "path": result.get("path", ""),
        "snippet": snippet,
        "url": cast(Dict[str, str], urls).get("app", ""),
        "page_id": result.get("id", ""),
        "score": float(result.get("score", 0.0)),
    }


def _snippet(text: str, result: SearchPageResult, query: str, max_chars: int) -> str:
    source = text or _section_text(result) or markdown_to_text(result.get("description") or "")
    return make_snippet(source, query, max_chars) if source else ""


def format_results(results: Sequence[LLMSearchResult]) -> str:
    """Render ``for_llm`` results as compact text for a tool-call reply."""
    if not results:
        return "No matching pages."
    blocks = []
    for n, r in enumerate(results, 1):
        lines = [f"{n}. {r['title']} ({r['path']})"]
        if r["snippet"]:
            lines.append(f"   {r['snippet']}")
        if r["url"]:
            lines.append(f"   {r['url']}")
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks)


def _check_llm_args(limit: int, snippet_chars: int) -> None:
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 100:
        raise ValueError("limit must be an integer from 1 to 100")
    if snippet_chars < 20:
        raise ValueError("snippet_chars must be at least 20")


class SearchResource(SyncResource):
    def space(
        self,
        space_id: str,
        query: str,
        *,
        limit: Optional[int] = None,
        max_items: Optional[int] = None,
    ) -> SyncPaginator[SearchPageResult]:
        """Full-text search over the pages of one space (``searchSpaceContent``)."""
        path = f"/spaces/{segment(space_id, 'space_id')}/search"
        return self._client.paginate(
            path, {"query": _check_query(query)}, limit=limit, max_items=max_items
        )

    def organization(
        self,
        organization_id: str,
        query: str,
        *,
        limit: Optional[int] = None,
        max_items: Optional[int] = None,
    ) -> SyncPaginator[SearchSpaceResult]:
        """Search every space of an organization (``searchOrganizationContent``).

        Each item is a space with its matching ``pages``.
        """
        path = f"/orgs/{segment(organization_id, 'organization_id')}/search"
        return self._client.paginate(
            path, {"query": _check_query(query)}, limit=limit, max_items=max_items
        )

    def for_llm(
        self,
        space_id: str,
        query: str,
        *,
        limit: int = 5,
        snippet_chars: int = 320,
        fetch_content: bool = False,
    ) -> List[LLMSearchResult]:
        """Search a space and return flat results ready for an LLM tool call.

        Each result has ``title``, ``path``, ``snippet`` (plain text, no
        Markdown), ``url``, ``page_id`` and ``score``. The snippet comes from
        the matching sections of the search response. With
        ``fetch_content=True`` the client also reads each page as Markdown
        and cuts the snippet from the full text around the query, at the
        cost of one extra request per result.
        """
        _check_llm_args(limit, snippet_chars)
        page = self.space(space_id, query, limit=limit).first_page()
        hits: List[LLMSearchResult] = []
        for result in page.items[:limit]:
            text = ""
            if fetch_content:
                try:
                    md = _markdown_of(
                        self._client.pages.get(space_id, result["id"], format="markdown")
                    )
                except NotFoundError:
                    md = ""
                text = markdown_to_text(md)
            hits.append(_hit(result, _snippet(text, result, query, snippet_chars)))
        return hits


class AsyncSearchResource(AsyncResource):
    def space(
        self,
        space_id: str,
        query: str,
        *,
        limit: Optional[int] = None,
        max_items: Optional[int] = None,
    ) -> AsyncPaginator[SearchPageResult]:
        """Full-text search over the pages of one space."""
        path = f"/spaces/{segment(space_id, 'space_id')}/search"
        return self._client.paginate(
            path, {"query": _check_query(query)}, limit=limit, max_items=max_items
        )

    def organization(
        self,
        organization_id: str,
        query: str,
        *,
        limit: Optional[int] = None,
        max_items: Optional[int] = None,
    ) -> AsyncPaginator[SearchSpaceResult]:
        """Search every space of an organization."""
        path = f"/orgs/{segment(organization_id, 'organization_id')}/search"
        return self._client.paginate(
            path, {"query": _check_query(query)}, limit=limit, max_items=max_items
        )

    async def for_llm(
        self,
        space_id: str,
        query: str,
        *,
        limit: int = 5,
        snippet_chars: int = 320,
        fetch_content: bool = False,
    ) -> List[LLMSearchResult]:
        """Async version of :meth:`SearchResource.for_llm`.

        With ``fetch_content=True`` the page reads run concurrently.
        """
        _check_llm_args(limit, snippet_chars)
        page = await self.space(space_id, query, limit=limit).first_page()
        results = page.items[:limit]

        async def page_text(result: SearchPageResult) -> str:
            try:
                fetched = await self._client.pages.get(space_id, result["id"], format="markdown")
            except NotFoundError:
                return ""
            return markdown_to_text(_markdown_of(fetched))

        if fetch_content:
            texts = list(await asyncio.gather(*(page_text(r) for r in results)))
        else:
            texts = [""] * len(results)
        return [
            _hit(result, _snippet(text, result, query, snippet_chars))
            for result, text in zip(results, texts)
        ]
