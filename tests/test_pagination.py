from __future__ import annotations

from typing import List, Optional

import pytest
import respx

from gitbook_api import AsyncGitBook, AsyncPaginator, GitBook, Page, SyncPaginator
from gitbook_api.pagination import page_from_response

from .conftest import load


def test_page_from_response_with_next() -> None:
    page = page_from_response(load("organizations_page1.json"))
    assert page.next_page == "cGFnZTI"
    assert page.count == 2
    assert page.has_next
    assert page.items[0]["object"] == "organization"


def test_page_from_response_last_page() -> None:
    page = page_from_response(load("spaces_page2.json"))
    assert page.next_page is None
    assert page.count is None
    assert not page.has_next


def test_page_from_response_empty_token_is_last() -> None:
    assert page_from_response({"items": [], "next": {"page": ""}}).next_page is None


@pytest.mark.parametrize("bad", [[], {"next": {"page": "x"}}, {"items": "nope"}, None])
def test_page_from_response_rejects_bad_bodies(bad: object) -> None:
    with pytest.raises(TypeError):
        page_from_response(bad)


def test_sync_iterates_across_pages(client: GitBook, api: respx.MockRouter) -> None:
    second = api.get("/orgs", params={"limit": "1", "page": "cGFnZTI"}).respond(
        json=load("organizations_page2.json")
    )
    first = api.get("/orgs", params={"limit": "1"}).respond(json=load("organizations_page1.json"))
    titles = [o["title"] for o in client.organizations.list(limit=1)]
    assert titles == ["Example Inc", "Side Project"]
    assert "page" not in first.calls.last.request.url.params
    assert second.calls.last.request.url.params["page"] == "cGFnZTI"


def test_pagination_is_lazy(client: GitBook, api: respx.MockRouter) -> None:
    route = api.get("/orgs").respond(json=load("organizations_page2.json"))
    paginator = client.organizations.list()
    assert route.call_count == 0
    list(paginator)
    assert route.call_count == 1


def test_pages_yields_page_objects(client: GitBook, api: respx.MockRouter) -> None:
    api.get("/orgs/o1/spaces", params={"page": "c3AyCg"}).respond(json=load("spaces_page2.json"))
    api.get("/orgs/o1/spaces").respond(json=load("spaces_page1.json"))
    pages = list(client.spaces.list("o1").pages())
    assert [len(p.items) for p in pages] == [1, 1]
    assert pages[0].next_page == "c3AyCg"
    assert pages[1].next_page is None


def test_max_items_stops_early(client: GitBook, api: respx.MockRouter) -> None:
    route = api.get("/orgs").respond(json=load("organizations_page1.json"))
    items = client.organizations.list(max_items=1).to_list()
    assert len(items) == 1
    assert route.call_count == 1


def test_max_items_zero_fetches_nothing(client: GitBook, api: respx.MockRouter) -> None:
    api.get("/orgs").respond(json=load("organizations_page1.json"))
    assert client.organizations.list(max_items=0).to_list() == []
    client.organizations.list().first_page()


def test_first_page_and_get_page(client: GitBook, api: respx.MockRouter) -> None:
    api.get("/orgs", params={"page": "cGFnZTI"}).respond(json=load("organizations_page2.json"))
    api.get("/orgs").respond(json=load("organizations_page1.json"))
    paginator = client.organizations.list()
    first = paginator.first_page()
    second = paginator.get_page(first.next_page)
    assert second.items[0]["title"] == "Side Project"


@pytest.mark.parametrize("limit", [0, 1001, -1])
def test_limit_out_of_range(client: GitBook, limit: int) -> None:
    with pytest.raises(ValueError, match="limit"):
        client.organizations.list(limit=limit)


def test_negative_max_items_rejected() -> None:
    with pytest.raises(ValueError):
        SyncPaginator(lambda token: Page(items=[]), max_items=-1)


def test_repeated_token_stops_loop() -> None:
    calls: List[Optional[str]] = []

    def fetch(token: Optional[str]) -> Page[int]:
        calls.append(token)
        return Page(items=[len(calls)], next_page="same")

    assert SyncPaginator(fetch).to_list() == [1, 2]
    assert calls == [None, "same"]


async def test_async_iterates_across_pages(aclient: AsyncGitBook, api: respx.MockRouter) -> None:
    api.get("/orgs", params={"page": "cGFnZTI"}).respond(json=load("organizations_page2.json"))
    api.get("/orgs").respond(json=load("organizations_page1.json"))
    titles = [o["title"] async for o in aclient.organizations.list()]
    assert titles == ["Example Inc", "Side Project"]


async def test_async_pages_first_page_and_max_items(
    aclient: AsyncGitBook, api: respx.MockRouter
) -> None:
    api.get("/orgs", params={"page": "cGFnZTI"}).respond(json=load("organizations_page2.json"))
    api.get("/orgs").respond(json=load("organizations_page1.json"))
    paginator = aclient.organizations.list()
    pages = [p async for p in paginator.pages()]
    assert len(pages) == 2
    first = await paginator.first_page()
    assert (await paginator.get_page(first.next_page)).items[0]["title"] == "Side Project"
    assert len(await aclient.organizations.list(max_items=1).to_list()) == 1


async def test_async_paginator_edge_cases() -> None:
    async def fetch(token: Optional[str]) -> Page[int]:
        return Page(items=[1, 2], next_page="again")

    with pytest.raises(ValueError):
        AsyncPaginator(fetch, max_items=-1)
    assert await AsyncPaginator(fetch, max_items=0).to_list() == []
    assert await AsyncPaginator(fetch).to_list() == [1, 2, 1, 2]
