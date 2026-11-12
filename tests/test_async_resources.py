"""The async client exposes the same resources as the sync one."""

from __future__ import annotations

import json

import pytest
import respx

from gitbook_api import AsyncGitBook

from .conftest import load


def body(route: respx.Route) -> object:
    return json.loads(route.calls.last.request.content)


async def test_users(aclient: AsyncGitBook, api: respx.MockRouter) -> None:
    api.get("/user").respond(json=load("user.json"))
    api.get("/users/u1").respond(json=load("user.json"))
    assert (await aclient.users.me())["id"] == (await aclient.users.get("u1"))["id"]


async def test_organizations(aclient: AsyncGitBook, api: respx.MockRouter) -> None:
    api.get("/orgs/o1").respond(json=load("organization.json"))
    members = api.get("/orgs/o1/members").respond(json=load("members.json"))
    api.get("/orgs").respond(json=load("organizations_page2.json"))
    assert (await aclient.organizations.get("o1"))["title"] == "Example Inc"
    assert len(await aclient.organizations.list_members("o1", sort="joinedAt").to_list()) == 2
    assert members.calls.last.request.url.params["sort"] == "joinedAt"
    assert len(await aclient.organizations.list(sort="lastSeenAt").to_list()) == 1


async def test_spaces_read(aclient: AsyncGitBook, api: respx.MockRouter) -> None:
    api.get("/spaces/s1").respond(json=load("space.json"))
    api.get("/orgs/o1/spaces").respond(json=load("spaces_page2.json"))
    api.get("/spaces/s1/content").respond(json=load("revision.json"))
    api.get("/spaces/s1/revisions/r1").respond(json=load("revision.json"))
    assert (await aclient.spaces.get("s1", share_key=None))["object"] == "space"
    assert len(await aclient.spaces.list("o1").to_list()) == 1
    assert (await aclient.spaces.get_current_revision("s1"))["object"] == "revision"
    assert (await aclient.spaces.get_revision("s1", "r1", metadata=True))["id"]


async def test_spaces_write(aclient: AsyncGitBook, api: respx.MockRouter) -> None:
    create = api.post("/orgs/o1/spaces").respond(201, json=load("space.json"))
    update = api.patch("/spaces/s1").respond(json=load("space.json"))
    delete = api.delete("/spaces/s1").respond(204)
    api.post("/spaces/s1/restore").respond(json=load("space.json"))
    api.post("/spaces/s1/duplicate").respond(201, json=load("space.json"))
    move = api.post("/spaces/s1/move").respond(json=load("space.json"))
    await aclient.spaces.create("o1", title="New", empty=True)
    await aclient.spaces.update("s1", title="Renamed")
    await aclient.spaces.delete("s1")
    await aclient.spaces.restore("s1")
    await aclient.spaces.duplicate("s1")
    await aclient.spaces.move("s1", parent="c1")
    assert body(create) == {"title": "New", "empty": True}
    assert body(update) == {"title": "Renamed"}
    assert body(move) == {"parent": "c1"}
    assert delete.called


async def test_collections(aclient: AsyncGitBook, api: respx.MockRouter) -> None:
    api.get("/orgs/o1/collections").respond(json=load("collections.json"))
    api.get("/collections/c1").respond(json=load("collection.json"))
    create = api.post("/orgs/o1/collections").respond(201, json=load("collection.json"))
    update = api.patch("/collections/c1").respond(json=load("collection.json"))
    delete = api.delete("/collections/c1").respond(204)
    move = api.post("/collections/c1/move").respond(json=load("collection.json"))
    api.get("/collections/c1/spaces").respond(json=load("spaces_page2.json"))
    assert len(await aclient.collections.list("o1").to_list()) == 2
    assert (await aclient.collections.get("c1"))["title"] == "Developer docs"
    await aclient.collections.create("o1", title="SDKs")
    await aclient.collections.update("c1", title="Docs")
    await aclient.collections.delete("c1")
    assert delete.called
    await aclient.collections.move("c1", position={"before": {"type": "collection", "collection": "c2"}})
    assert len(await aclient.collections.list_spaces("c1").to_list()) == 1
    assert body(create) == {"title": "SDKs"}
    assert body(update) == {"title": "Docs"}
    assert body(move) == {"position": {"before": {"type": "collection", "collection": "c2"}}}


async def test_pages(aclient: AsyncGitBook, api: respx.MockRouter) -> None:
    api.get("/spaces/s1/content/pages").respond(json=load("pages.json"))
    api.get("/spaces/s1/content/page/p1").respond(json=load("page_markdown.json"))
    api.get("/spaces/s1/revisions/r1/path/guides/authentication").respond(
        json=load("page_markdown.json")
    )
    api.get("/spaces/s1/revisions/r1/page/p1/document").respond(json=load("json_document.json"))
    assert len(await aclient.pages.list("s1")) == 2
    assert (await aclient.pages.get("s1", "p1"))["title"] == "Authentication"
    page = await aclient.pages.get_by_path("s1", "guides/authentication", revision_id="r1")
    assert page["id"] == "P3aUtHaBcDeFgHiJkL01"
    assert (await aclient.pages.get_markdown("s1", "p1")).startswith("# Authentication")
    assert (await aclient.pages.get_document("s1", "p1", revision_id="r1"))["object"] == "document"


async def test_change_requests(aclient: AsyncGitBook, api: respx.MockRouter) -> None:
    api.get("/spaces/s1/change-requests").respond(json=load("change_requests_page2.json"))
    org = api.get("/orgs/o1/change-requests").respond(json=load("change_requests_page2.json"))
    api.get("/spaces/s1/change-requests/cr1").respond(json=load("change_request.json"))
    create = api.post("/spaces/s1/change-requests").respond(201, json=load("change_request.json"))
    update = api.patch("/spaces/s1/change-requests/cr1").respond(json=load("change_request.json"))
    api.post("/spaces/s1/change-requests/cr1/merge").respond(json=load("merge_result.json"))
    api.post("/spaces/s1/change-requests/cr1/update").respond(json=load("merge_result.json"))
    api.get("/spaces/s1/change-requests/cr1/reviews").respond(json={"items": [load("review.json")]})
    review = api.post("/spaces/s1/change-requests/cr1/reviews").respond(201, json=load("review.json"))

    assert len(await aclient.change_requests.list("s1", status="draft").to_list()) == 1
    await aclient.change_requests.list_for_organization("o1", status=("open",)).to_list()
    assert org.calls.last.request.url.params.get_list("status") == ["open"]
    assert (await aclient.change_requests.get("s1", "cr1"))["number"] == 42
    await aclient.change_requests.create("s1", subject="New")
    await aclient.change_requests.update("s1", "cr1", status="open")
    assert (await aclient.change_requests.merge("s1", "cr1"))["result"] == "merge"
    assert (await aclient.change_requests.sync("s1", "cr1"))["revision"]
    assert len(await aclient.change_requests.list_reviews("s1", "cr1").to_list()) == 1
    await aclient.change_requests.submit_review("s1", "cr1", status="approved", comment="ok")
    assert body(create) == {"subject": "New"}
    assert body(update) == {"status": "open"}
    assert body(review) == {"status": "approved", "comment": {"markdown": "ok"}}


async def test_async_validation_errors(aclient: AsyncGitBook) -> None:
    with pytest.raises(ValueError):
        await aclient.spaces.update("s1")
    with pytest.raises(ValueError):
        await aclient.collections.update("c1")
    with pytest.raises(ValueError):
        await aclient.change_requests.update("s1", "cr1")
    with pytest.raises(ValueError):
        await aclient.pages.get("s1", "p1", change_request_id="cr1", revision_id="r1")
