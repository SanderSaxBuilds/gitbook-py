from __future__ import annotations

import json

import pytest
import respx

from gitbook_api import GitBook
from gitbook_api.types import JSONDocument

from .conftest import load

DESCRIPTION: JSONDocument = {
    "object": "document",
    "data": {},
    "nodes": [
        {
            "object": "block",
            "type": "paragraph",
            "nodes": [{"object": "text", "leaves": [{"object": "leaf", "text": "Why", "marks": []}]}],
        }
    ],
}


def body(route: respx.Route) -> object:
    return json.loads(route.calls.last.request.content)


def test_list_for_space_with_filters(client: GitBook, api: respx.MockRouter) -> None:
    api.get("/spaces/s1/change-requests", params={"page": "Y3IyCg"}).respond(
        json=load("change_requests_page2.json")
    )
    route = api.get("/spaces/s1/change-requests").respond(json=load("change_requests_page1.json"))
    items = client.change_requests.list(
        "s1",
        status="open",
        creator="u1",
        contributor="u2",
        requested_reviewer="u3",
        topic="t1",
        order_by="createdAt",
    ).to_list()
    assert [c["number"] for c in items] == [42, 41]
    params = dict(route.calls[0].request.url.params)
    assert params == {
        "status": "open",
        "creator": "u1",
        "contributor": "u2",
        "requestedReviewer": "u3",
        "topic": "t1",
        "orderBy": "createdAt",
    }


def test_list_for_organization_repeats_status(client: GitBook, api: respx.MockRouter) -> None:
    route = api.get("/orgs/o1/change-requests").respond(json=load("change_requests_page2.json"))
    client.change_requests.list_for_organization(
        "o1", status=["open", "draft"], site="site1", space="s1"
    ).to_list()
    params = route.calls.last.request.url.params
    assert params.get_list("status") == ["open", "draft"]
    assert params["site"] == "site1"
    assert params["space"] == "s1"


def test_list_for_organization_single_status(client: GitBook, api: respx.MockRouter) -> None:
    route = api.get("/orgs/o1/change-requests").respond(json=load("change_requests_page2.json"))
    client.change_requests.list_for_organization("o1", status="merged").first_page()
    assert route.calls.last.request.url.params.get_list("status") == ["merged"]


def test_get(client: GitBook, api: respx.MockRouter) -> None:
    api.get("/spaces/s1/change-requests/cr1").respond(json=load("change_request.json"))
    cr = client.change_requests.get("s1", "cr1")
    assert cr["subject"] == "Document the search endpoint"
    assert cr["createdBy"]["displayName"] == "Ada Lovelace"


def test_create(client: GitBook, api: respx.MockRouter) -> None:
    route = api.post("/spaces/s1/change-requests").respond(201, json=load("change_request.json"))
    client.change_requests.create("s1", subject="Docs", description=DESCRIPTION)
    assert body(route) == {"subject": "Docs", "description": DESCRIPTION}


def test_create_without_fields(client: GitBook, api: respx.MockRouter) -> None:
    route = api.post("/spaces/s1/change-requests").respond(201, json=load("change_request.json"))
    client.change_requests.create("s1")
    assert body(route) == {}


def test_update_status(client: GitBook, api: respx.MockRouter) -> None:
    route = api.patch("/spaces/s1/change-requests/cr1").respond(json=load("change_request.json"))
    client.change_requests.update("s1", "cr1", status="archived", subject="Old")
    assert body(route) == {"subject": "Old", "status": "archived"}


def test_update_description(client: GitBook, api: respx.MockRouter) -> None:
    route = api.patch("/spaces/s1/change-requests/cr1").respond(json=load("change_request.json"))
    client.change_requests.update("s1", "cr1", description=DESCRIPTION)
    assert body(route) == {"description": DESCRIPTION}


def test_update_rejects_merged_status(client: GitBook) -> None:
    with pytest.raises(ValueError, match="merge"):
        client.change_requests.update("s1", "cr1", status="merged")  # type: ignore[arg-type]


def test_update_needs_a_field(client: GitBook) -> None:
    with pytest.raises(ValueError, match="at least one"):
        client.change_requests.update("s1", "cr1")


def test_merge(client: GitBook, api: respx.MockRouter) -> None:
    route = api.post("/spaces/s1/change-requests/cr1/merge").respond(json=load("merge_result.json"))
    result = client.change_requests.merge("s1", "cr1")
    assert result == {"revision": "R9mErGeDAbCdEfGhIj01", "result": "merge"}
    assert route.calls.last.request.content == b""


def test_sync_hits_update_endpoint(client: GitBook, api: respx.MockRouter) -> None:
    api.post("/spaces/s1/change-requests/cr1/update").respond(json=load("merge_result.json"))
    assert client.change_requests.sync("s1", "cr1")["revision"] == "R9mErGeDAbCdEfGhIj01"


def test_list_reviews(client: GitBook, api: respx.MockRouter) -> None:
    route = api.get("/spaces/s1/change-requests/cr1/reviews").respond(
        json={"items": [load("review.json")]}
    )
    reviews = client.change_requests.list_reviews("s1", "cr1", outdated=False).to_list()
    assert reviews[0]["status"] == "approved"
    assert route.calls.last.request.url.params["outdated"] == "false"


def test_submit_review_with_markdown_comment(client: GitBook, api: respx.MockRouter) -> None:
    route = api.post("/spaces/s1/change-requests/cr1/reviews").respond(201, json=load("review.json"))
    client.change_requests.submit_review("s1", "cr1", status="approved", comment="Looks good")
    assert body(route) == {"status": "approved", "comment": {"markdown": "Looks good"}}


def test_submit_review_with_document_comment(client: GitBook, api: respx.MockRouter) -> None:
    route = api.post("/spaces/s1/change-requests/cr1/reviews").respond(201, json=load("review.json"))
    client.change_requests.submit_review(
        "s1", "cr1", status="changes-requested", comment={"document": DESCRIPTION}
    )
    assert body(route) == {"status": "changes-requested", "comment": {"document": DESCRIPTION}}


def test_submit_review_without_comment(client: GitBook, api: respx.MockRouter) -> None:
    route = api.post("/spaces/s1/change-requests/cr1/reviews").respond(201, json=load("review.json"))
    client.change_requests.submit_review("s1", "cr1", status="approved")
    assert body(route) == {"status": "approved"}


def test_ids_are_validated(client: GitBook) -> None:
    with pytest.raises(ValueError, match="change_request_id"):
        client.change_requests.get("s1", " ")
