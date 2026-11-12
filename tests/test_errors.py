from __future__ import annotations

from typing import Type

import httpx
import pytest
import respx

from gitbook_api import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    AsyncGitBook,
    AuthenticationError,
    BadRequestError,
    ConflictError,
    FeatureNotAvailableError,
    GitBook,
    GitBookError,
    InternalServerError,
    NotFoundError,
    PermissionDeniedError,
    PreconditionFailedError,
    RateLimitError,
    RetryPolicy,
    UnprocessableEntityError,
)
from gitbook_api.errors import make_status_error

from .conftest import TOKEN, load


@pytest.mark.parametrize(
    ("status", "fixture", "cls"),
    [
        (400, "error_400.json", BadRequestError),
        (401, "error_401.json", AuthenticationError),
        (403, "error_403.json", PermissionDeniedError),
        (404, "error_404.json", NotFoundError),
        (409, "error_409.json", ConflictError),
        (412, "error_412.json", PreconditionFailedError),
        (429, "error_429.json", RateLimitError),
        (500, "error_500.json", InternalServerError),
    ],
)
def test_status_maps_to_error_class(
    api: respx.MockRouter, status: int, fixture: str, cls: Type[APIStatusError]
) -> None:
    body = load(fixture)
    api.get("/spaces/s1").respond(status, json=body)
    with GitBook(TOKEN, max_retries=0) as client:
        with pytest.raises(cls) as info:
            client.spaces.get("s1")
    err = info.value
    assert err.status_code == status
    assert err.message == body["error"]["message"]
    assert err.body == body
    assert str(err) == f"{status}: {body['error']['message']}"
    assert isinstance(err, GitBookError)


def test_feature_not_available(client: GitBook, api: respx.MockRouter) -> None:
    api.post("/spaces/s1/change-requests/cr1/merge").respond(
        403, json=load("error_feature_not_available.json")
    )
    with pytest.raises(FeatureNotAvailableError) as info:
        client.change_requests.merge("s1", "cr1")
    err = info.value
    assert isinstance(err, PermissionDeniedError)
    assert err.error_type == "feature-not-available"
    assert err.upgrade["requiredPlanName"] == "Pro"
    assert err.upgrade["feature"] == "change-requests-merge-rules"


def test_plain_403_has_no_error_type(client: GitBook, api: respx.MockRouter) -> None:
    api.get("/spaces/s1").respond(403, json=load("error_403.json"))
    with pytest.raises(PermissionDeniedError) as info:
        client.spaces.get("s1")
    assert not isinstance(info.value, FeatureNotAvailableError)
    assert info.value.error_type is None


def test_request_id_is_captured(client: GitBook, api: respx.MockRouter) -> None:
    api.get("/spaces/s1").respond(
        404, json=load("error_404.json"), headers={"X-Request-Id": "req_123"}
    )
    with pytest.raises(NotFoundError) as info:
        client.spaces.get("s1")
    assert info.value.request_id == "req_123"
    assert isinstance(info.value.response, httpx.Response)


def test_non_json_error_body(api: respx.MockRouter) -> None:
    api.get("/spaces/s1").respond(502, text="<html>Bad gateway</html>")
    with GitBook(TOKEN, max_retries=0) as c:
        with pytest.raises(InternalServerError) as info:
            c.spaces.get("s1")
    assert info.value.body == "<html>Bad gateway</html>"
    assert "Bad gateway" in info.value.message


def test_empty_error_body_uses_reason_phrase() -> None:
    response = httpx.Response(404, request=httpx.Request("GET", "https://x"))
    err = make_status_error(response)
    assert isinstance(err, NotFoundError)
    assert err.message == "Not Found"
    assert err.body is None


def test_unknown_4xx_is_generic_status_error() -> None:
    response = httpx.Response(418, json={"error": {"code": 418, "message": "teapot"}},
                              request=httpx.Request("GET", "https://x"))
    err = make_status_error(response)
    assert type(err) is APIStatusError
    assert err.message == "teapot"


def test_422_maps_to_unprocessable() -> None:
    response = httpx.Response(422, json={"error": {"code": 422, "message": "bad"}},
                              request=httpx.Request("POST", "https://x"))
    assert isinstance(make_status_error(response), UnprocessableEntityError)


def test_rate_limit_error_carries_retry_after(api: respx.MockRouter) -> None:
    api.get("/user").respond(429, json=load("error_429.json"), headers={"Retry-After": "600"})
    with GitBook(TOKEN) as client:
        with pytest.raises(RateLimitError) as info:
            client.users.me()
    assert info.value.retry_after == 600.0


def test_connection_error_is_wrapped(api: respx.MockRouter) -> None:
    api.get("/user").mock(side_effect=httpx.ConnectError("refused"))
    with GitBook(TOKEN, max_retries=0) as client:
        with pytest.raises(APIConnectionError) as info:
            client.users.me()
    assert not isinstance(info.value, APITimeoutError)
    assert "refused" in str(info.value)
    assert isinstance(info.value.__cause__, httpx.ConnectError)


def test_timeout_is_wrapped(api: respx.MockRouter) -> None:
    api.get("/user").mock(side_effect=httpx.ReadTimeout("slow"))
    with GitBook(TOKEN, retry=RetryPolicy(max_retries=0)) as client:
        with pytest.raises(APITimeoutError):
            client.users.me()


async def test_async_errors_match_sync(api: respx.MockRouter) -> None:
    api.get("/spaces/s1").respond(404, json=load("error_404.json"))
    async with AsyncGitBook(TOKEN) as client:
        with pytest.raises(NotFoundError):
            await client.spaces.get("s1")


async def test_async_connection_and_timeout(api: respx.MockRouter) -> None:
    api.get("/user").mock(side_effect=httpx.ConnectError("refused"))
    api.get("/users/u1").mock(side_effect=httpx.ConnectTimeout("slow"))
    async with AsyncGitBook(TOKEN, max_retries=0) as client:
        with pytest.raises(APIConnectionError):
            await client.users.me()
        with pytest.raises(APITimeoutError):
            await client.users.get("u1")
