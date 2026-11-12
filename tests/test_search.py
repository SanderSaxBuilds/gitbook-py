from __future__ import annotations

import httpx
import pytest
import respx

from gitbook_api import SEARCH_TOOL, AsyncGitBook, GitBook, format_results

from .conftest import load

AUTH_PAGE = "P3aUtHaBcDeFgHiJkL01"
QUICK_PAGE = "P1qUiCkStArTaBcDeF01"


def test_space_search_paginates(client: GitBook, api: respx.MockRouter) -> None:
    api.get("/spaces/s1/search", params={"page": "c2VhcmNoMg"}).respond(
        json=load("search_space_page2.json")
    )
    route = api.get("/spaces/s1/search").respond(json=load("search_space_page1.json"))
    results = client.search.space("s1", "token", limit=2).to_list()
    assert [r["rank"] for r in results] == [1, 2, 3]
    params = route.calls[0].request.url.params
    assert params["query"] == "token"
    assert params["limit"] == "2"


def test_space_search_strips_query(client: GitBook, api: respx.MockRouter) -> None:
    route = api.get("/spaces/s1/search").respond(json=load("search_space_page2.json"))
    client.search.space("s1", "  install  ").first_page()
    assert route.calls.last.request.url.params["query"] == "install"


@pytest.mark.parametrize("query", ["", "   "])
def test_empty_query_rejected(client: GitBook, query: str) -> None:
    with pytest.raises(ValueError, match="query"):
        client.search.space("s1", query)
    with pytest.raises(ValueError, match="query"):
        client.search.organization("o1", query)


def test_organization_search(client: GitBook, api: respx.MockRouter) -> None:
    route = api.get("/orgs/o1/search").respond(json=load("search_org.json"))
    spaces = client.search.organization("o1", "authentication").to_list()
    assert [s["title"] for s in spaces] == ["Example API docs", "Internal handbook"]
    assert spaces[0]["pages"][0]["path"] == "guides/authentication"
    assert route.calls.last.request.url.params["query"] == "authentication"


def test_for_llm_builds_plain_snippets(client: GitBook, api: respx.MockRouter) -> None:
    route = api.get("/spaces/s1/search").respond(json=load("search_space_page1.json"))
    hits = client.search.for_llm("s1", "token", limit=2)
    assert route.call_count == 1
    assert route.calls.last.request.url.params["limit"] == "2"
    first, second = hits
    assert first["title"] == "Authentication"
    assert first["path"] == "guides/authentication"
    assert first["page_id"] == AUTH_PAGE
    assert first["url"].endswith("/guides/authentication")
    assert first["score"] == 12.5
    # Markdown, code ticks and link URLs are gone, best section comes first.
    assert first["snippet"].startswith("Send your token in the Authorization header")
    assert "**" not in first["snippet"] and "`" not in first["snippet"]
    assert "https://" not in first["snippet"]
    assert "Revoke an old token" in first["snippet"]
    # A page without sections falls back to its description.
    assert second["snippet"] == "Make your first request with a token in five minutes."


def test_for_llm_respects_snippet_length(client: GitBook, api: respx.MockRouter) -> None:
    api.get("/spaces/s1/search").respond(json=load("search_space_page1.json"))
    hits = client.search.for_llm("s1", "revoke", snippet_chars=40)
    assert all(len(h["snippet"]) <= 46 for h in hits)
    assert "Revoke" in hits[0]["snippet"]


def test_for_llm_trims_to_limit(client: GitBook, api: respx.MockRouter) -> None:
    api.get("/spaces/s1/search").respond(json=load("search_space_page1.json"))
    assert len(client.search.for_llm("s1", "token", limit=1)) == 1


def test_for_llm_empty_description_gives_empty_snippet(
    client: GitBook, api: respx.MockRouter
) -> None:
    api.get("/spaces/s1/search").respond(json=load("search_space_page2.json"))
    [hit] = client.search.for_llm("s1", "install")
    assert hit["snippet"] == ""


def test_for_llm_fetch_content(client: GitBook, api: respx.MockRouter) -> None:
    api.get("/spaces/s1/search").respond(json=load("search_space_page1.json"))
    auth = api.get(f"/spaces/s1/content/page/{AUTH_PAGE}").respond(json=load("page_markdown.json"))
    api.get(f"/spaces/s1/content/page/{QUICK_PAGE}").respond(404, json=load("error_404.json"))
    first, second = client.search.for_llm("s1", "commit", fetch_content=True)
    assert auth.calls.last.request.url.params["format"] == "markdown"
    assert "Never commit tokens to git." in first["snippet"]
    assert "{%" not in first["snippet"]
    # The second page is gone, so its search description is used.
    assert second["snippet"].startswith("Make your first request")


@pytest.mark.parametrize(("limit", "chars"), [(0, 320), (101, 320), (5, 10)])
def test_for_llm_argument_checks(client: GitBook, limit: int, chars: int) -> None:
    with pytest.raises(ValueError):
        client.search.for_llm("s1", "x", limit=limit, snippet_chars=chars)


def test_format_results() -> None:
    text = format_results(
        [
            {"title": "Auth", "path": "guides/auth", "snippet": "Use a token.",
             "url": "https://app.gitbook.com/x", "page_id": "p1", "score": 1.0},
            {"title": "Empty", "path": "e", "snippet": "", "url": "", "page_id": "p2", "score": 0.5},
        ]
    )
    assert text == (
        "1. Auth (guides/auth)\n   Use a token.\n   https://app.gitbook.com/x\n\n2. Empty (e)"
    )
    assert format_results([]) == "No matching pages."


def test_search_tool_definition_is_json_schema() -> None:
    assert SEARCH_TOOL["name"] == "search_docs"
    params = SEARCH_TOOL["parameters"]
    assert params["type"] == "object"
    assert params["required"] == ["query"]
    assert set(params["properties"]) == {"query", "limit"}


async def test_async_search(aclient: AsyncGitBook, api: respx.MockRouter) -> None:
    api.get("/spaces/s1/search", params={"page": "c2VhcmNoMg"}).respond(
        json=load("search_space_page2.json")
    )
    api.get("/spaces/s1/search").respond(json=load("search_space_page1.json"))
    api.get("/orgs/o1/search").respond(json=load("search_org.json"))
    assert len([r async for r in aclient.search.space("s1", "token")]) == 3
    assert len(await aclient.search.organization("o1", "token").to_list()) == 2


async def test_async_for_llm_fetches_concurrently(
    aclient: AsyncGitBook, api: respx.MockRouter
) -> None:
    api.get("/spaces/s1/search").respond(json=load("search_space_page1.json"))
    api.get(f"/spaces/s1/content/page/{AUTH_PAGE}").respond(json=load("page_markdown.json"))
    api.get(f"/spaces/s1/content/page/{QUICK_PAGE}").respond(404, json=load("error_404.json"))
    hits = await aclient.search.for_llm("s1", "commit", fetch_content=True)
    assert "Never commit tokens" in hits[0]["snippet"]
    assert hits[1]["snippet"].startswith("Make your first request")


async def test_async_for_llm_without_fetch(aclient: AsyncGitBook, api: respx.MockRouter) -> None:
    api.get("/spaces/s1/search").respond(json=load("search_space_page1.json"))
    hits = await aclient.search.for_llm("s1", "token")
    assert hits[0]["snippet"].startswith("Send your token")


async def test_async_for_llm_propagates_other_errors(
    aclient: AsyncGitBook, api: respx.MockRouter
) -> None:
    api.get("/spaces/s1/search").respond(json=load("search_space_page2.json"))
    api.get("/spaces/s1/content/page/P2inStAlLaBcDeFgHi01").mock(
        return_value=httpx.Response(401, json=load("error_401.json"))
    )
    from gitbook_api import AuthenticationError

    with pytest.raises(AuthenticationError):
        await aclient.search.for_llm("s1", "install", fetch_content=True)
