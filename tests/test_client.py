from __future__ import annotations

import httpx
import pytest
import respx

from gitbook_api import NOT_GIVEN, AsyncGitBook, GitBook, GitBookError, NotGiven, RetryPolicy
from gitbook_api._base import clean_query, compact, page_path_segment, segment

from .conftest import BASE_URL, TOKEN, load


def test_missing_token_raises() -> None:
    with pytest.raises(GitBookError, match="GITBOOK_TOKEN"):
        GitBook()


def test_blank_token_raises() -> None:
    with pytest.raises(GitBookError):
        GitBook("   ")


def test_token_from_environment(monkeypatch: pytest.MonkeyPatch, api: respx.MockRouter) -> None:
    monkeypatch.setenv("GITBOOK_TOKEN", "gb_api_from_env")
    route = api.get("/user").respond(json=load("user.json"))
    with GitBook() as client:
        client.users.me()
    assert route.calls.last.request.headers["authorization"] == "Bearer gb_api_from_env"


def test_explicit_token_wins_over_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GITBOOK_TOKEN", "gb_api_from_env")
    client = GitBook("gb_api_explicit")
    assert client._headers()["Authorization"] == "Bearer gb_api_explicit"
    client.close()


def test_default_headers_sent(client: GitBook, api: respx.MockRouter) -> None:
    route = api.get("/user").respond(json=load("user.json"))
    client.users.me()
    headers = route.calls.last.request.headers
    assert headers["authorization"] == f"Bearer {TOKEN}"
    assert headers["accept"] == "application/json"
    assert headers["user-agent"].startswith("gitbook-py/0.2.0 python/")


def test_custom_user_agent_and_headers(api: respx.MockRouter) -> None:
    route = api.get("/user").respond(json=load("user.json"))
    with GitBook(TOKEN, user_agent="my-bot/2.0", default_headers={"X-Trace": "abc"}) as client:
        client.users.me()
    headers = route.calls.last.request.headers
    assert headers["user-agent"] == "my-bot/2.0"
    assert headers["x-trace"] == "abc"


def test_default_headers_cannot_override_authorization(api: respx.MockRouter) -> None:
    route = api.get("/user").respond(json=load("user.json"))
    with GitBook(TOKEN, default_headers={"Authorization": "Bearer other"}) as client:
        client.users.me()
    assert route.calls.last.request.headers["authorization"] == f"Bearer {TOKEN}"


def test_base_url_override() -> None:
    with respx.mock(base_url="https://gitbook.internal/api/v1") as router:
        route = router.get("/user").respond(json=load("user.json"))
        with GitBook(TOKEN, base_url="https://gitbook.internal/api/v1/") as client:
            assert client.base_url == "https://gitbook.internal/api/v1"
            client.users.me()
        assert route.called


def test_base_url_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GITBOOK_BASE_URL", "http://localhost:8787/v1")
    client = GitBook(TOKEN)
    assert client.base_url == "http://localhost:8787/v1"
    assert "localhost:8787" in repr(client)
    client.close()


def test_max_retries_shortcut_keeps_policy() -> None:
    policy = RetryPolicy(max_retries=5, backoff_factor=2.0)
    client = GitBook(TOKEN, retry=policy, max_retries=1)
    assert client.retry.max_retries == 1
    assert client.retry.backoff_factor == 2.0
    client.close()


def test_external_http_client_is_not_closed(api: respx.MockRouter) -> None:
    api.get("/user").respond(json=load("user.json"))
    http = httpx.Client()
    with GitBook(TOKEN, http_client=http) as client:
        client.users.me()
    assert not http.is_closed
    http.close()


def test_owned_http_client_is_closed() -> None:
    client = GitBook(TOKEN)
    client.close()
    assert client._http.is_closed


def test_raw_request_for_uncovered_endpoint(client: GitBook, api: respx.MockRouter) -> None:
    route = api.get("/orgs/org1/subscription").respond(json={"plan": "pro_2024"})
    assert client.request("get", "orgs/org1/subscription") == {"plan": "pro_2024"}
    assert route.calls.last.request.method == "GET"


def test_raw_request_extra_headers(client: GitBook, api: respx.MockRouter) -> None:
    route = api.patch("/spaces/s1/change-requests/cr1").respond(204)
    result = client.request(
        "PATCH",
        "/spaces/s1/change-requests/cr1",
        json={"subject": "x"},
        headers={"Prefer": "return=minimal"},
    )
    assert result is None
    assert route.calls.last.request.headers["prefer"] == "return=minimal"


def test_non_json_success_body_returns_text(client: GitBook, api: respx.MockRouter) -> None:
    api.get("/user").respond(200, text="plain body")
    assert client.request("GET", "/user") == "plain body"


def test_raw_paginate(client: GitBook, api: respx.MockRouter) -> None:
    api.get("/orgs/org1/teams").respond(json={"items": [{"id": "t1"}, {"id": "t2"}]})
    assert [t["id"] for t in client.paginate("/orgs/org1/teams", limit=2)] == ["t1", "t2"]


async def test_async_context_manager(api: respx.MockRouter) -> None:
    api.get("/user").respond(json=load("user.json"))
    async with AsyncGitBook(TOKEN) as client:
        me = await client.users.me()
    assert me["id"] == load("user.json")["id"]
    assert client._http.is_closed


async def test_async_external_http_client_is_not_closed(api: respx.MockRouter) -> None:
    api.get("/user").respond(json=load("user.json"))
    http = httpx.AsyncClient()
    async with AsyncGitBook(TOKEN, http_client=http) as client:
        await client.users.me()
    assert not http.is_closed
    await http.aclose()


async def test_async_raw_request_and_paginate(aclient: AsyncGitBook, api: respx.MockRouter) -> None:
    api.get("/orgs/org1/teams", params={"page": "n2"}).respond(json={"items": [{"id": "t2"}]})
    api.get("/orgs/org1/teams").respond(json={"items": [{"id": "t1"}], "next": {"page": "n2"}})
    items = await aclient.paginate("/orgs/org1/teams").to_list()
    assert [t["id"] for t in items] == ["t1", "t2"]


def test_segment_encodes_and_rejects_empty() -> None:
    assert segment("a/b c") == "a%2Fb%20c"
    with pytest.raises(ValueError, match="space_id"):
        segment("", "space_id")


def test_page_path_segment_keeps_slashes() -> None:
    assert page_path_segment("/guides/getting started/") == "guides/getting%20started"
    with pytest.raises(ValueError):
        page_path_segment("///")


def test_clean_query_formats_values() -> None:
    assert clean_query(
        {"a": None, "b": True, "c": False, "d": 5, "e": "x", "f": ["open", "draft"]}
    ) == [("b", "true"), ("c", "false"), ("d", "5"), ("e", "x"), ("f", "open"), ("f", "draft")]
    assert clean_query(None) == []


def test_not_given_is_a_falsy_singleton() -> None:
    assert NotGiven() is NOT_GIVEN
    assert not NOT_GIVEN
    assert repr(NOT_GIVEN) == "NOT_GIVEN"
    assert compact({"a": NOT_GIVEN, "b": None, "c": 1}) == {"b": None, "c": 1}


def test_requests_go_to_v1_base(client: GitBook, api: respx.MockRouter) -> None:
    route = api.get("/user").respond(json=load("user.json"))
    client.users.me()
    assert str(route.calls.last.request.url) == f"{BASE_URL}/user"
