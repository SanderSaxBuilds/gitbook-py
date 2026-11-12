"""Users, organizations, spaces and collections (sync client)."""

from __future__ import annotations

import json

import pytest
import respx

from gitbook_api import GitBook

from .conftest import load


def body(route: respx.Route) -> object:
    return json.loads(route.calls.last.request.content)


# -- users ---------------------------------------------------------------------


def test_users_me(client: GitBook, api: respx.MockRouter) -> None:
    api.get("/user").respond(json=load("user.json"))
    me = client.users.me()
    assert me["object"] == "user"
    assert me["email"] == "ada@example.com"


def test_users_get_encodes_id(client: GitBook, api: respx.MockRouter) -> None:
    route = api.get("/users/u%2F1").respond(json=load("user.json"))
    client.users.get("u/1")
    assert route.called


def test_users_get_rejects_empty_id(client: GitBook) -> None:
    with pytest.raises(ValueError, match="user_id"):
        client.users.get("")


# -- organizations -------------------------------------------------------------


def test_organizations_get(client: GitBook, api: respx.MockRouter) -> None:
    api.get("/orgs/Kq8Zx1aBcDeFgHiJkLmN").respond(json=load("organization.json"))
    org = client.organizations.get("Kq8Zx1aBcDeFgHiJkLmN")
    assert org["title"] == "Example Inc"
    assert org["permissions"]["admin"] is True


def test_organizations_list_sort(client: GitBook, api: respx.MockRouter) -> None:
    route = api.get("/orgs").respond(json=load("organizations_page2.json"))
    client.organizations.list(sort="lastSeenAt").to_list()
    assert route.calls.last.request.url.params["sort"] == "lastSeenAt"


def test_organizations_list_members(client: GitBook, api: respx.MockRouter) -> None:
    route = api.get("/orgs/o1/members").respond(json=load("members.json"))
    members = client.organizations.list_members(
        "o1", role="admin", search="ada", sort="name", order="asc", limit=10
    ).to_list()
    params = route.calls.last.request.url.params
    assert dict(params) == {"role": "admin", "search": "ada", "sort": "name", "order": "asc", "limit": "10"}
    assert members[0]["user"]["displayName"] == "Ada Lovelace"
    assert members[1]["role"] is None


def test_organizations_members_guest_filter(client: GitBook, api: respx.MockRouter) -> None:
    route = api.get("/orgs/o1/members").respond(json=load("members.json"))
    client.organizations.list_members("o1", role="guest").first_page()
    assert route.calls.last.request.url.params["role"] == "guest"


# -- spaces --------------------------------------------------------------------


def test_spaces_get(client: GitBook, api: respx.MockRouter) -> None:
    route = api.get("/spaces/s1").respond(json=load("space.json"))
    space = client.spaces.get("s1")
    assert space["title"] == "Example API docs"
    assert "shareKey" not in route.calls.last.request.url.params


def test_spaces_get_with_share_key(client: GitBook, api: respx.MockRouter) -> None:
    route = api.get("/spaces/s1", params={"shareKey": "k1"}).respond(json=load("space.json"))
    client.spaces.get("s1", share_key="k1")
    assert route.called


def test_spaces_list(client: GitBook, api: respx.MockRouter) -> None:
    api.get("/orgs/o1/spaces", params={"page": "c3AyCg"}).respond(json=load("spaces_page2.json"))
    api.get("/orgs/o1/spaces").respond(json=load("spaces_page1.json"))
    titles = [s["title"] for s in client.spaces.list("o1")]
    assert titles == ["Example API docs", "Internal handbook"]


def test_spaces_create(client: GitBook, api: respx.MockRouter) -> None:
    route = api.post("/orgs/o1/spaces").respond(201, json=load("space.json"))
    client.spaces.create(
        "o1", title="API", emoji="1f4d8", parent="c1", language="en", edit_mode="locked", empty=True
    )
    assert body(route) == {
        "title": "API",
        "emoji": "1f4d8",
        "parent": "c1",
        "language": "en",
        "editMode": "locked",
        "empty": True,
    }


def test_spaces_create_minimal_body(client: GitBook, api: respx.MockRouter) -> None:
    route = api.post("/orgs/o1/spaces").respond(201, json=load("space.json"))
    client.spaces.create("o1")
    assert body(route) == {}


def test_spaces_create_title_limit(client: GitBook) -> None:
    with pytest.raises(ValueError, match="50"):
        client.spaces.create("o1", title="x" * 51)


def test_spaces_update_sends_only_given_fields(client: GitBook, api: respx.MockRouter) -> None:
    route = api.patch("/spaces/s1").respond(json=load("space.json"))
    client.spaces.update("s1", title="Renamed", default_level=None)
    assert body(route) == {"title": "Renamed", "defaultLevel": None}


def test_spaces_update_clear_icon(client: GitBook, api: respx.MockRouter) -> None:
    route = api.patch("/spaces/s1").respond(json=load("space.json"))
    client.spaces.update("s1", emoji=None, icon=None, edit_mode="live", language="fr")
    assert body(route) == {"emoji": None, "icon": None, "editMode": "live", "language": "fr"}


def test_spaces_update_rejects_emoji_and_icon(client: GitBook) -> None:
    with pytest.raises(ValueError, match="emoji or icon"):
        client.spaces.update("s1", emoji="1f600", icon="https://x/icon.png")


def test_spaces_update_needs_a_field(client: GitBook) -> None:
    with pytest.raises(ValueError, match="at least one"):
        client.spaces.update("s1")


def test_spaces_delete_returns_none(client: GitBook, api: respx.MockRouter) -> None:
    route = api.delete("/spaces/s1").respond(204)
    client.spaces.delete("s1")
    assert route.called


def test_spaces_delete_205(client: GitBook, api: respx.MockRouter) -> None:
    route = api.delete("/spaces/s1").respond(205)
    client.spaces.delete("s1")
    assert route.call_count == 1


def test_spaces_restore_and_duplicate(client: GitBook, api: respx.MockRouter) -> None:
    api.post("/spaces/s1/restore").respond(json=load("space.json"))
    api.post("/spaces/s1/duplicate").respond(201, json=load("space.json"))
    assert client.spaces.restore("s1")["id"] == client.spaces.duplicate("s1")["id"]


def test_spaces_move_to_root_with_position(client: GitBook, api: respx.MockRouter) -> None:
    route = api.post("/spaces/s1/move").respond(json=load("space.json"))
    client.spaces.move("s1", parent=None, position={"after": {"type": "space", "space": "s2"}})
    assert body(route) == {"parent": None, "position": {"after": {"type": "space", "space": "s2"}}}


def test_spaces_move_needs_target(client: GitBook) -> None:
    with pytest.raises(ValueError, match="parent"):
        client.spaces.move("s1")


def test_spaces_current_revision(client: GitBook, api: respx.MockRouter) -> None:
    route = api.get("/spaces/s1/content").respond(json=load("revision.json"))
    revision = client.spaces.get_current_revision("s1", metadata=False, computed=True)
    assert revision["type"] == "edits"
    assert dict(route.calls.last.request.url.params) == {"metadata": "false", "computed": "true"}


def test_spaces_get_revision(client: GitBook, api: respx.MockRouter) -> None:
    api.get("/spaces/s1/revisions/r1").respond(json=load("revision.json"))
    assert client.spaces.get_revision("s1", "r1")["files"][0]["name"] == "diagram.png"


# -- collections ---------------------------------------------------------------


def test_collections_list_nested(client: GitBook, api: respx.MockRouter) -> None:
    route = api.get("/orgs/o1/collections").respond(json=load("collections.json"))
    items = client.collections.list("o1", nested=False).to_list()
    assert route.calls.last.request.url.params["nested"] == "false"
    assert [c["title"] for c in items] == ["Developer docs", "SDKs"]


def test_collections_get(client: GitBook, api: respx.MockRouter) -> None:
    api.get("/collections/c1").respond(json=load("collection.json"))
    assert client.collections.get("c1")["object"] == "collection"


def test_collections_create(client: GitBook, api: respx.MockRouter) -> None:
    route = api.post("/orgs/o1/collections").respond(201, json=load("collection.json"))
    client.collections.create("o1", title="Developer docs", parent="c0")
    assert body(route) == {"title": "Developer docs", "parent": "c0"}


def test_collections_update(client: GitBook, api: respx.MockRouter) -> None:
    route = api.patch("/collections/c1").respond(json=load("collection.json"))
    client.collections.update("c1", description="New", default_level="read")
    assert body(route) == {"description": "New", "defaultLevel": "read"}


def test_collections_update_needs_a_field(client: GitBook) -> None:
    with pytest.raises(ValueError):
        client.collections.update("c1")


def test_collections_delete(client: GitBook, api: respx.MockRouter) -> None:
    route = api.delete("/collections/c1").respond(204)
    client.collections.delete("c1")
    assert route.called


def test_collections_move(client: GitBook, api: respx.MockRouter) -> None:
    route = api.post("/collections/c1/move").respond(json=load("collection.json"))
    client.collections.move("c1", parent="c0")
    assert body(route) == {"parent": "c0"}


def test_collections_list_spaces(client: GitBook, api: respx.MockRouter) -> None:
    route = api.get("/collections/c1/spaces").respond(json=load("spaces_page2.json"))
    spaces = client.collections.list_spaces("c1", limit=25).to_list()
    assert route.calls.last.request.url.params["limit"] == "25"
    assert spaces[0]["parent"] == "C7hJkLmNoPqRsTuVwX12"
