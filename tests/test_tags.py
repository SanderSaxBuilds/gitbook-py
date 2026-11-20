"""Tags: listTags and the ``tag`` filter on the page list endpoints (API 0.210)."""

from __future__ import annotations

import pytest
import respx

from gitbook_api import AsyncGitBook, GitBook

from .conftest import load


def test_list_tags(client: GitBook, api: respx.MockRouter) -> None:
    route = api.get("/spaces/s1/content/tags").respond(json=load("tags.json"))
    tags = client.spaces.list_tags("s1")
    assert route.called
    assert [t["slug"] for t in tags] == ["platform", "api", "cli", "beta"]
    assert tags[0]["kind"] == "category"
    assert tags[1]["parent"] == "platform"
    assert tags[3]["pageCount"] == 0


def test_list_tags_bad_body(client: GitBook, api: respx.MockRouter) -> None:
    api.get("/spaces/s1/content/tags").respond(json={"items": []})
    with pytest.raises(TypeError):
        client.spaces.list_tags("s1")


def test_pages_one_tag(client: GitBook, api: respx.MockRouter) -> None:
    route = api.get("/spaces/s1/content/pages").respond(json=load("pages.json"))
    client.pages.list("s1", tag="api")
    assert route.calls.last.request.url.params.get_list("tag") == ["api"]


def test_pages_several_tags_repeat_the_parameter(client: GitBook, api: respx.MockRouter) -> None:
    route = api.get("/spaces/s1/content/pages").respond(json=load("pages.json"))
    client.pages.list("s1", tag=["api", "cli"], metadata=False)
    params = route.calls.last.request.url.params
    assert params.get_list("tag") == ["api", "cli"]
    assert params["metadata"] == "false"
    assert "tag=api&tag=cli" in str(route.calls.last.request.url)


def test_pages_no_tag_sends_no_parameter(client: GitBook, api: respx.MockRouter) -> None:
    route = api.get("/spaces/s1/content/pages").respond(json=load("pages.json"))
    client.pages.list("s1")
    assert "tag" not in route.calls.last.request.url.params


def test_pages_tag_on_change_request(client: GitBook, api: respx.MockRouter) -> None:
    route = api.get("/spaces/s1/change-requests/cr1/content/pages").respond(json=load("pages.json"))
    client.pages.list("s1", change_request_id="cr1", tag=("beta",))
    assert route.calls.last.request.url.params.get_list("tag") == ["beta"]


def test_pages_tag_on_revision(client: GitBook, api: respx.MockRouter) -> None:
    route = api.get("/spaces/s1/revisions/r1/pages").respond(json=load("pages.json"))
    client.pages.list("s1", revision_id="r1", tag="beta")
    assert route.calls.last.request.url.params.get_list("tag") == ["beta"]


@pytest.mark.parametrize("bad", ["", [], ["api", ""], [None]])
def test_pages_tag_rejects_empty(client: GitBook, bad: object) -> None:
    with pytest.raises(ValueError, match="tag"):
        client.pages.list("s1", tag=bad)  # type: ignore[arg-type]


def test_merge_revision_from_site_change_request(client: GitBook, api: respx.MockRouter) -> None:
    api.get("/spaces/s1/revisions/r9").respond(json=load("revision_merge_site.json"))
    revision = client.spaces.get_revision("s1", "r9")
    assert revision["type"] == "merge"
    merged = revision["mergedFrom"]
    assert merged["object"] == "site-change-request"
    if merged["object"] == "site-change-request":
        assert merged["site"] == "site_7aBcD"


def test_merge_revision_without_merged_from(client: GitBook, api: respx.MockRouter) -> None:
    data = load("revision_merge_site.json")
    del data["mergedFrom"]
    api.get("/spaces/s1/revisions/r9").respond(json=data)
    revision = client.spaces.get_revision("s1", "r9")
    assert revision.get("mergedFrom") is None


async def test_async_tags(aclient: AsyncGitBook, api: respx.MockRouter) -> None:
    api.get("/spaces/s1/content/tags").respond(json=load("tags.json"))
    route = api.get("/spaces/s1/content/pages").respond(json=load("pages.json"))
    assert len(await aclient.spaces.list_tags("s1")) == 4
    await aclient.pages.list("s1", tag=["platform"])
    assert route.calls.last.request.url.params.get_list("tag") == ["platform"]
    with pytest.raises(ValueError):
        await aclient.pages.list("s1", tag=[])
