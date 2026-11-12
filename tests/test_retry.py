from __future__ import annotations

import email.utils

import httpx
import pytest
import respx

from gitbook_api import (
    APIConnectionError,
    AsyncGitBook,
    GitBook,
    InternalServerError,
    RateLimitError,
    RetryPolicy,
)
from gitbook_api.retry import parse_retry_after

from .conftest import TOKEN, SleepRecorder, load

NO_JITTER = RetryPolicy(max_retries=3, backoff_factor=0.5, jitter=False)


def make_client(sleeps: SleepRecorder, policy: RetryPolicy = NO_JITTER) -> GitBook:
    client = GitBook(TOKEN, retry=policy)
    client._sleep = sleeps
    return client


# -- RetryPolicy -------------------------------------------------------------


def test_policy_defaults() -> None:
    policy = RetryPolicy()
    assert policy.max_retries == 3
    assert policy.retry_statuses == frozenset({429, 500, 502, 503, 504})
    assert not policy.retry_non_idempotent


def test_policy_rejects_negative_values() -> None:
    with pytest.raises(ValueError):
        RetryPolicy(max_retries=-1)
    with pytest.raises(ValueError):
        RetryPolicy(backoff_factor=-0.1)


@pytest.mark.parametrize(
    ("method", "status", "expected"),
    [
        ("GET", 429, True),
        ("POST", 429, True),
        ("POST", 503, True),
        ("GET", 500, True),
        ("DELETE", 502, True),
        ("POST", 500, False),
        ("PATCH", 504, False),
        ("GET", 404, False),
        ("GET", 400, False),
    ],
)
def test_should_retry_status(method: str, status: int, expected: bool) -> None:
    assert RetryPolicy().should_retry_status(method, status, 0) is expected


def test_should_retry_stops_at_max() -> None:
    policy = RetryPolicy(max_retries=2)
    assert policy.should_retry_status("GET", 500, 1)
    assert not policy.should_retry_status("GET", 500, 2)
    assert not policy.should_retry_error("GET", 2)


def test_non_idempotent_opt_in() -> None:
    policy = RetryPolicy(retry_non_idempotent=True)
    assert policy.should_retry_status("POST", 500, 0)
    assert policy.should_retry_error("PATCH", 0)
    assert not RetryPolicy().should_retry_error("POST", 0)


def test_backoff_is_exponential_and_capped() -> None:
    policy = RetryPolicy(backoff_factor=1.0, max_backoff=5.0, jitter=False)
    assert [policy.backoff(n) for n in range(5)] == [1.0, 2.0, 4.0, 5.0, 5.0]


def test_backoff_jitter_range() -> None:
    low = RetryPolicy(backoff_factor=2.0, random=lambda: 0.0)
    high = RetryPolicy(backoff_factor=2.0, random=lambda: 1.0)
    assert low.backoff(0) == 1.0
    assert high.backoff(0) == 2.0


# -- parse_retry_after ---------------------------------------------------------


def test_retry_after_seconds() -> None:
    assert parse_retry_after({"retry-after": "7"}, 429) == 7.0
    assert parse_retry_after({"retry-after": " 1.5 "}, 503) == 1.5


def test_retry_after_http_date() -> None:
    now = 1_700_000_000.0
    date = email.utils.formatdate(now + 30, usegmt=True)
    assert parse_retry_after({"retry-after": date}, 429, now=now) == pytest.approx(30.0)


def test_retry_after_date_without_zone_is_utc() -> None:
    now = 1_700_000_000.0
    date = email.utils.formatdate(now + 10, usegmt=True).replace(" GMT", " -0000")
    assert parse_retry_after({"retry-after": date}, 429, now=now) == pytest.approx(10.0)


def test_retry_after_in_past_is_zero() -> None:
    assert parse_retry_after({"retry-after": "-5"}, 429) == 0.0


def test_rate_limit_reset_fallback() -> None:
    headers = {"x-ratelimit-reset": "1700000045", "x-ratelimit-remaining": "0"}
    assert parse_retry_after(headers, 429, now=1_700_000_000.0) == 45.0
    assert parse_retry_after(headers, 503, now=1_700_000_000.0) is None


def test_invalid_headers_ignored() -> None:
    assert parse_retry_after({"retry-after": "soon"}, 429) is None
    assert parse_retry_after({"x-ratelimit-reset": "later"}, 429) is None
    assert parse_retry_after({}, 429) is None


# -- client behavior -----------------------------------------------------------


def test_429_then_success_honors_retry_after(sleeps: SleepRecorder, api: respx.MockRouter) -> None:
    route = api.get("/user")
    route.side_effect = [
        httpx.Response(429, json=load("error_429.json"), headers={"Retry-After": "2"}),
        httpx.Response(200, json=load("user.json")),
    ]
    with make_client(sleeps) as client:
        assert client.users.me()["displayName"] == "Ada Lovelace"
    assert route.call_count == 2
    assert sleeps.calls == [2.0]


def test_429_uses_rate_limit_reset(
    sleeps: SleepRecorder, api: respx.MockRouter, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("gitbook_api.retry.time.time", lambda: 1_700_000_000.0)
    route = api.get("/user")
    route.side_effect = [
        httpx.Response(429, json=load("error_429.json"), headers={"X-RateLimit-Reset": "1700000003"}),
        httpx.Response(200, json=load("user.json")),
    ]
    with make_client(sleeps) as client:
        client.users.me()
    assert sleeps.calls == [3.0]


def test_5xx_get_uses_backoff(sleeps: SleepRecorder, api: respx.MockRouter) -> None:
    route = api.get("/spaces/s1")
    route.side_effect = [
        httpx.Response(500, json=load("error_500.json")),
        httpx.Response(502),
        httpx.Response(200, json=load("space.json")),
    ]
    with make_client(sleeps) as client:
        assert client.spaces.get("s1")["object"] == "space"
    assert sleeps.calls == [0.5, 1.0]


def test_retries_exhausted_raise_last_error(sleeps: SleepRecorder, api: respx.MockRouter) -> None:
    route = api.get("/spaces/s1").respond(503, json=load("error_500.json"))
    with make_client(sleeps) as client:
        with pytest.raises(InternalServerError):
            client.spaces.get("s1")
    assert route.call_count == 4
    assert len(sleeps.calls) == 3


def test_post_500_is_not_retried(sleeps: SleepRecorder, api: respx.MockRouter) -> None:
    route = api.post("/spaces/s1/change-requests/cr1/merge").respond(500, json=load("error_500.json"))
    with make_client(sleeps) as client:
        with pytest.raises(InternalServerError):
            client.change_requests.merge("s1", "cr1")
    assert route.call_count == 1
    assert sleeps.calls == []


def test_post_429_is_retried(sleeps: SleepRecorder, api: respx.MockRouter) -> None:
    route = api.post("/spaces/s1/change-requests")
    route.side_effect = [
        httpx.Response(429, json=load("error_429.json"), headers={"Retry-After": "1"}),
        httpx.Response(201, json=load("change_request.json")),
    ]
    with make_client(sleeps) as client:
        assert client.change_requests.create("s1", subject="x")["number"] == 42
    assert route.call_count == 2


def test_post_500_retried_when_opted_in(sleeps: SleepRecorder, api: respx.MockRouter) -> None:
    route = api.post("/spaces/s1/duplicate")
    route.side_effect = [httpx.Response(500), httpx.Response(201, json=load("space.json"))]
    policy = RetryPolicy(retry_non_idempotent=True, jitter=False)
    with make_client(sleeps, policy) as client:
        client.spaces.duplicate("s1")
    assert route.call_count == 2


def test_long_retry_after_raises_immediately(sleeps: SleepRecorder, api: respx.MockRouter) -> None:
    route = api.get("/user").respond(429, json=load("error_429.json"), headers={"Retry-After": "3600"})
    with make_client(sleeps) as client:
        with pytest.raises(RateLimitError) as info:
            client.users.me()
    assert route.call_count == 1
    assert info.value.retry_after == 3600.0
    assert sleeps.calls == []


def test_max_retries_zero_disables_retries(sleeps: SleepRecorder, api: respx.MockRouter) -> None:
    route = api.get("/user").respond(429, json=load("error_429.json"), headers={"Retry-After": "1"})
    with make_client(sleeps, RetryPolicy(max_retries=0)) as client:
        with pytest.raises(RateLimitError):
            client.users.me()
    assert route.call_count == 1


def test_connection_error_retried_for_get(sleeps: SleepRecorder, api: respx.MockRouter) -> None:
    route = api.get("/user")
    route.side_effect = [httpx.ConnectError("reset"), httpx.Response(200, json=load("user.json"))]
    with make_client(sleeps) as client:
        client.users.me()
    assert route.call_count == 2
    assert sleeps.calls == [0.5]


def test_timeout_retried_then_raised(sleeps: SleepRecorder, api: respx.MockRouter) -> None:
    route = api.get("/user").mock(side_effect=httpx.ReadTimeout("slow"))
    with make_client(sleeps, RetryPolicy(max_retries=2, jitter=False)) as client:
        with pytest.raises(APIConnectionError):
            client.users.me()
    assert route.call_count == 3


def test_connection_error_not_retried_for_post(sleeps: SleepRecorder, api: respx.MockRouter) -> None:
    route = api.post("/spaces/s1/restore").mock(side_effect=httpx.ConnectError("reset"))
    with make_client(sleeps) as client:
        with pytest.raises(APIConnectionError):
            client.spaces.restore("s1")
    assert route.call_count == 1


async def test_async_429_then_success(sleeps: SleepRecorder, api: respx.MockRouter) -> None:
    route = api.get("/user")
    route.side_effect = [
        httpx.Response(429, json=load("error_429.json"), headers={"Retry-After": "4"}),
        httpx.Response(200, json=load("user.json")),
    ]
    client = AsyncGitBook(TOKEN, retry=NO_JITTER)
    client._sleep = sleeps.async_sleep
    async with client:
        await client.users.me()
    assert sleeps.calls == [4.0]


async def test_async_connection_and_timeout_retries(
    sleeps: SleepRecorder, api: respx.MockRouter
) -> None:
    route = api.get("/user")
    route.side_effect = [
        httpx.ConnectError("reset"),
        httpx.ReadTimeout("slow"),
        httpx.Response(200, json=load("user.json")),
    ]
    client = AsyncGitBook(TOKEN, retry=NO_JITTER)
    client._sleep = sleeps.async_sleep
    async with client:
        await client.users.me()
    assert sleeps.calls == [0.5, 1.0]


async def test_async_exhausted_retries(sleeps: SleepRecorder, api: respx.MockRouter) -> None:
    api.get("/spaces/s1").respond(500)
    client = AsyncGitBook(TOKEN, retry=RetryPolicy(max_retries=1, jitter=False))
    client._sleep = sleeps.async_sleep
    async with client:
        with pytest.raises(InternalServerError):
            await client.spaces.get("s1")
    assert len(sleeps.calls) == 1
