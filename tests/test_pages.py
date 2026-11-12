from __future__ import annotations

import pytest
import respx

from gitbook_api import GitBook, iter_pages

from .conftest import load


def test_list_pages_live(client: GitBook, api: respx.MockRouter) -> None:
    route = api.get("/spaces/s1/content/pages").respond(json=load("pages.json"))
    pages = client.pages.list("s1", metadata=False)
    assert [p["title"] for p in pages] == ["Quickstart", "Guides"]
    assert route.calls.last.request.url.params["metadata"] == "false"


def test_list_pages_in_change_request(client: GitBook, api: respx.MockRouter) -> None:
    route = api.get("/spaces/s1/change-requests/cr1/content/pages").respond(json=load("pages.json"))
    client.pages.list("s1", change_request_id="cr1")
    assert route.called


def test_list_pages_in_revision(client: GitBook, api: respx.MockRouter) -> None:
    route = api.get("/spaces/s1/revisions/r1/pages").respond(json=load("pages.json"))
    client.pages.list("s1", revision_id="r1")
    assert route.called


def test_list_pages_rejects_both_sources(client: GitBook) -> None:
    with pytest.raises(ValueError, match="not both"):
        client.pages.list("s1", change_request_id="cr1", revision_id="r1")


def test_list_pages_bad_body(client: GitBook, api: respx.MockRouter) -> None:
    api.get("/spaces/s1/content/pages").respond(json={"items": []})
    with pytest.raises(TypeError):
        client.pages.list("s1")


def test_iter_pages_flattens_tree() -> None:
    pages = load("pages.json")["pages"]
    titles = [p["title"] for p in iter_pages(pages)]
    assert titles == ["Quickstart", "Install", "Guides", "Authentication", "Status page"]


def test_get_page_markdown_format(client: GitBook, api: respx.MockRouter) -> None:
    route = api.get("/spaces/s1/content/page/p1").respond(json=load("page_markdown.json"))
    page = client.pages.get("s1", "p1", format="markdown", markdown_refs="stable", dereferenced=True)
    params = dict(route.calls.last.request.url.params)
    assert params == {"format": "markdown", "format.markdown.refs": "stable", "dereferenced": "true"}
    assert page["type"] == "document"
    assert page.get("markdown", "").startswith("# Authentication")


def test_get_page_evaluated_string_option(client: GitBook, api: respx.MockRouter) -> None:
    route = api.get("/spaces/s1/content/page/p1").respond(json=load("page_document.json"))
    client.pages.get("s1", "p1", format="document", evaluated="deterministic-only", computed=False)
    params = route.calls.last.request.url.params
    assert params["evaluated"] == "deterministic-only"
    assert params["computed"] == "false"


def test_get_page_in_change_request(client: GitBook, api: respx.MockRouter) -> None:
    route = api.get("/spaces/s1/change-requests/cr1/content/page/p1").respond(
        json=load("page_markdown.json")
    )
    client.pages.get("s1", "p1", change_request_id="cr1")
    assert route.called


def test_get_page_in_revision(client: GitBook, api: respx.MockRouter) -> None:
    route = api.get("/spaces/s1/revisions/r1/page/p1").respond(json=load("page_markdown.json"))
    client.pages.get("s1", "p1", revision_id="r1")
    assert route.called


def test_get_by_path_keeps_slashes(client: GitBook, api: respx.MockRouter) -> None:
    route = api.get("/spaces/s1/content/path/guides/authentication").respond(
        json=load("page_markdown.json")
    )
    page = client.pages.get_by_path("s1", "/guides/authentication", format="markdown")
    assert page["id"] == "P3aUtHaBcDeFgHiJkL01"
    assert route.calls.last.request.url.params["format"] == "markdown"


def test_get_by_path_returns_group(client: GitBook, api: respx.MockRouter) -> None:
    api.get("/spaces/s1/content/path/guides").respond(json=load("page_group.json"))
    page = client.pages.get_by_path("s1", "guides")
    assert page["type"] == "group"


def test_get_by_path_change_request_and_revision(client: GitBook, api: respx.MockRouter) -> None:
    cr = api.get("/spaces/s1/change-requests/cr1/content/path/guides").respond(
        json=load("page_group.json")
    )
    rev = api.get("/spaces/s1/revisions/r1/path/guides").respond(json=load("page_group.json"))
    client.pages.get_by_path("s1", "guides", change_request_id="cr1")
    client.pages.get_by_path("s1", "guides", revision_id="r1")
    assert cr.called and rev.called


def test_get_by_path_rejects_empty(client: GitBook) -> None:
    with pytest.raises(ValueError):
        client.pages.get_by_path("s1", "/")


def test_get_markdown(client: GitBook, api: respx.MockRouter) -> None:
    route = api.get("/spaces/s1/content/page/p1").respond(json=load("page_markdown.json"))
    md = client.pages.get_markdown("s1", "p1")
    assert "Never commit **tokens** to git." in md
    assert route.calls.last.request.url.params["format"] == "markdown"


def test_get_markdown_of_group_is_empty(client: GitBook, api: respx.MockRouter) -> None:
    api.get("/spaces/s1/content/page/g1").respond(json=load("page_group.json"))
    assert client.pages.get_markdown("s1", "g1") == ""


def test_get_document(client: GitBook, api: respx.MockRouter) -> None:
    route = api.get("/spaces/s1/revisions/r1/page/p1/document").respond(
        json=load("json_document.json")
    )
    doc = client.pages.get_document("s1", "p1", revision_id="r1", dereferenced="reusable-contents")
    assert doc["object"] == "document"
    assert route.calls.last.request.url.params["dereferenced"] == "reusable-contents"
