"""Change requests: GitBook's branch and review flow for a space."""

from __future__ import annotations

from typing import Any, Dict, Mapping, Optional, Sequence, Union, cast

from .._base import NOT_GIVEN, NotGiven, compact, segment
from ..pagination import AsyncPaginator, SyncPaginator
from ..types import (
    ChangeRequest,
    ChangeRequestMergeResult,
    ChangeRequestOrderBy,
    ChangeRequestReview,
    ChangeRequestReviewStatus,
    ChangeRequestStatus,
    ChangeRequestUpdateStatus,
    JSONDocument,
)
from ._resource import AsyncResource, SyncResource

__all__ = ["AsyncChangeRequestsResource", "ChangeRequestsResource"]

StatusFilter = Union[ChangeRequestStatus, Sequence[ChangeRequestStatus]]
_UPDATE_STATUSES = ("draft", "open", "archived")


def _cr(space_id: str, change_request_id: str) -> str:
    return (
        f"/spaces/{segment(space_id, 'space_id')}"
        f"/change-requests/{segment(change_request_id, 'change_request_id')}"
    )


def _space_list_query(
    status: Optional[ChangeRequestStatus],
    creator: Optional[str],
    contributor: Optional[str],
    requested_reviewer: Optional[str],
    topic: Optional[str],
    order_by: Optional[ChangeRequestOrderBy],
) -> Dict[str, Any]:
    return {
        "status": status,
        "creator": creator,
        "contributor": contributor,
        "requestedReviewer": requested_reviewer,
        "topic": topic,
        "orderBy": order_by,
    }


def _org_list_query(
    status: Optional[StatusFilter],
    creator: Optional[str],
    contributor: Optional[str],
    requested_reviewer: Optional[str],
    site: Optional[str],
    space: Optional[str],
    topic: Optional[str],
    order_by: Optional[ChangeRequestOrderBy],
) -> Dict[str, Any]:
    statuses = [status] if isinstance(status, str) else (list(status) if status else None)
    return {
        "status": statuses,
        "creator": creator,
        "contributor": contributor,
        "requestedReviewer": requested_reviewer,
        "site": site,
        "space": space,
        "topic": topic,
        "orderBy": order_by,
    }


def _create_body(subject: Optional[str], description: Optional[JSONDocument]) -> Dict[str, Any]:
    body: Dict[str, Any] = {}
    if subject is not None:
        body["subject"] = subject
    if description is not None:
        body["description"] = dict(description)
    return body


def _update_body(
    subject: Union[str, NotGiven],
    description: Union[JSONDocument, NotGiven],
    status: Union[ChangeRequestUpdateStatus, NotGiven],
) -> Dict[str, Any]:
    if isinstance(status, str) and status not in _UPDATE_STATUSES:
        raise ValueError(
            "status must be 'draft', 'open' or 'archived', use merge() to merge"
        )
    body = compact({"subject": subject, "description": description, "status": status})
    if not body:
        raise ValueError("update needs at least one field to change")
    return body


def _review_body(
    status: ChangeRequestReviewStatus, comment: Union[str, Mapping[str, Any], None]
) -> Dict[str, Any]:
    body: Dict[str, Any] = {"status": status}
    if isinstance(comment, str):
        body["comment"] = {"markdown": comment}
    elif comment is not None:
        body["comment"] = dict(comment)
    return body


class ChangeRequestsResource(SyncResource):
    def list(
        self,
        space_id: str,
        *,
        status: Optional[ChangeRequestStatus] = None,
        creator: Optional[str] = None,
        contributor: Optional[str] = None,
        requested_reviewer: Optional[str] = None,
        topic: Optional[str] = None,
        order_by: Optional[ChangeRequestOrderBy] = None,
        limit: Optional[int] = None,
        max_items: Optional[int] = None,
    ) -> SyncPaginator[ChangeRequest]:
        """Change requests of a space (``listChangeRequestsForSpace``)."""
        path = f"/spaces/{segment(space_id, 'space_id')}/change-requests"
        query = _space_list_query(status, creator, contributor, requested_reviewer, topic, order_by)
        return self._client.paginate(path, query, limit=limit, max_items=max_items)

    def list_for_organization(
        self,
        organization_id: str,
        *,
        status: Optional[StatusFilter] = None,
        creator: Optional[str] = None,
        contributor: Optional[str] = None,
        requested_reviewer: Optional[str] = None,
        site: Optional[str] = None,
        space: Optional[str] = None,
        topic: Optional[str] = None,
        order_by: Optional[ChangeRequestOrderBy] = None,
        limit: Optional[int] = None,
        max_items: Optional[int] = None,
    ) -> SyncPaginator[ChangeRequest]:
        """Change requests across an organization (``listChangeRequestsForOrganization``).

        ``status`` takes one status or several, for example ``["open", "draft"]``.
        """
        path = f"/orgs/{segment(organization_id, 'organization_id')}/change-requests"
        query = _org_list_query(
            status, creator, contributor, requested_reviewer, site, space, topic, order_by
        )
        return self._client.paginate(path, query, limit=limit, max_items=max_items)

    def get(self, space_id: str, change_request_id: str) -> ChangeRequest:
        """One change request (``getChangeRequestById``)."""
        return cast(ChangeRequest, self._client.request("GET", _cr(space_id, change_request_id)))

    def create(
        self,
        space_id: str,
        *,
        subject: Optional[str] = None,
        description: Optional[JSONDocument] = None,
    ) -> ChangeRequest:
        """Open a new change request on a space (``createChangeRequest``)."""
        path = f"/spaces/{segment(space_id, 'space_id')}/change-requests"
        return cast(
            ChangeRequest,
            self._client.request("POST", path, json=_create_body(subject, description)),
        )

    def update(
        self,
        space_id: str,
        change_request_id: str,
        *,
        subject: Union[str, NotGiven] = NOT_GIVEN,
        description: Union[JSONDocument, NotGiven] = NOT_GIVEN,
        status: Union[ChangeRequestUpdateStatus, NotGiven] = NOT_GIVEN,
    ) -> ChangeRequest:
        """Change subject, description or status (``updateChangeRequestById``).

        ``status`` can be ``"draft"``, ``"open"`` or ``"archived"``. Merging
        goes through :meth:`merge`.
        """
        body = _update_body(subject, description, status)
        return cast(
            ChangeRequest,
            self._client.request("PATCH", _cr(space_id, change_request_id), json=body),
        )

    def merge(self, space_id: str, change_request_id: str) -> ChangeRequestMergeResult:
        """Merge into the live content (``mergeChangeRequest``).

        The token needs the ``change-request:merge`` scope.
        """
        return cast(
            ChangeRequestMergeResult,
            self._client.request("POST", _cr(space_id, change_request_id) + "/merge"),
        )

    def sync(self, space_id: str, change_request_id: str) -> ChangeRequestMergeResult:
        """Bring the latest live content into the change request (``updateChangeRequest``).

        This is the "Update" button in the GitBook app, the API path ends
        in ``/update``.
        """
        return cast(
            ChangeRequestMergeResult,
            self._client.request("POST", _cr(space_id, change_request_id) + "/update"),
        )

    def list_reviews(
        self,
        space_id: str,
        change_request_id: str,
        *,
        outdated: Optional[bool] = None,
        limit: Optional[int] = None,
        max_items: Optional[int] = None,
    ) -> SyncPaginator[ChangeRequestReview]:
        """Reviews submitted on a change request (``getReviewsByChangeRequestId``)."""
        return self._client.paginate(
            _cr(space_id, change_request_id) + "/reviews",
            {"outdated": outdated},
            limit=limit,
            max_items=max_items,
        )

    def submit_review(
        self,
        space_id: str,
        change_request_id: str,
        *,
        status: ChangeRequestReviewStatus,
        comment: Union[str, Mapping[str, Any], None] = None,
    ) -> ChangeRequestReview:
        """Approve or request changes (``submitChangeRequestReview``).

        A string ``comment`` is sent as Markdown. A dict is sent as given,
        for example ``{"document": {...}}``.
        """
        return cast(
            ChangeRequestReview,
            self._client.request(
                "POST",
                _cr(space_id, change_request_id) + "/reviews",
                json=_review_body(status, comment),
            ),
        )


class AsyncChangeRequestsResource(AsyncResource):
    def list(
        self,
        space_id: str,
        *,
        status: Optional[ChangeRequestStatus] = None,
        creator: Optional[str] = None,
        contributor: Optional[str] = None,
        requested_reviewer: Optional[str] = None,
        topic: Optional[str] = None,
        order_by: Optional[ChangeRequestOrderBy] = None,
        limit: Optional[int] = None,
        max_items: Optional[int] = None,
    ) -> AsyncPaginator[ChangeRequest]:
        """Change requests of a space."""
        path = f"/spaces/{segment(space_id, 'space_id')}/change-requests"
        query = _space_list_query(status, creator, contributor, requested_reviewer, topic, order_by)
        return self._client.paginate(path, query, limit=limit, max_items=max_items)

    def list_for_organization(
        self,
        organization_id: str,
        *,
        status: Optional[StatusFilter] = None,
        creator: Optional[str] = None,
        contributor: Optional[str] = None,
        requested_reviewer: Optional[str] = None,
        site: Optional[str] = None,
        space: Optional[str] = None,
        topic: Optional[str] = None,
        order_by: Optional[ChangeRequestOrderBy] = None,
        limit: Optional[int] = None,
        max_items: Optional[int] = None,
    ) -> AsyncPaginator[ChangeRequest]:
        """Change requests across an organization."""
        path = f"/orgs/{segment(organization_id, 'organization_id')}/change-requests"
        query = _org_list_query(
            status, creator, contributor, requested_reviewer, site, space, topic, order_by
        )
        return self._client.paginate(path, query, limit=limit, max_items=max_items)

    async def get(self, space_id: str, change_request_id: str) -> ChangeRequest:
        """One change request."""
        return cast(
            ChangeRequest, await self._client.request("GET", _cr(space_id, change_request_id))
        )

    async def create(
        self,
        space_id: str,
        *,
        subject: Optional[str] = None,
        description: Optional[JSONDocument] = None,
    ) -> ChangeRequest:
        """Open a new change request on a space."""
        path = f"/spaces/{segment(space_id, 'space_id')}/change-requests"
        return cast(
            ChangeRequest,
            await self._client.request("POST", path, json=_create_body(subject, description)),
        )

    async def update(
        self,
        space_id: str,
        change_request_id: str,
        *,
        subject: Union[str, NotGiven] = NOT_GIVEN,
        description: Union[JSONDocument, NotGiven] = NOT_GIVEN,
        status: Union[ChangeRequestUpdateStatus, NotGiven] = NOT_GIVEN,
    ) -> ChangeRequest:
        """Change subject, description or status."""
        body = _update_body(subject, description, status)
        return cast(
            ChangeRequest,
            await self._client.request("PATCH", _cr(space_id, change_request_id), json=body),
        )

    async def merge(self, space_id: str, change_request_id: str) -> ChangeRequestMergeResult:
        """Merge into the live content."""
        return cast(
            ChangeRequestMergeResult,
            await self._client.request("POST", _cr(space_id, change_request_id) + "/merge"),
        )

    async def sync(self, space_id: str, change_request_id: str) -> ChangeRequestMergeResult:
        """Bring the latest live content into the change request."""
        return cast(
            ChangeRequestMergeResult,
            await self._client.request("POST", _cr(space_id, change_request_id) + "/update"),
        )

    def list_reviews(
        self,
        space_id: str,
        change_request_id: str,
        *,
        outdated: Optional[bool] = None,
        limit: Optional[int] = None,
        max_items: Optional[int] = None,
    ) -> AsyncPaginator[ChangeRequestReview]:
        """Reviews submitted on a change request."""
        return self._client.paginate(
            _cr(space_id, change_request_id) + "/reviews",
            {"outdated": outdated},
            limit=limit,
            max_items=max_items,
        )

    async def submit_review(
        self,
        space_id: str,
        change_request_id: str,
        *,
        status: ChangeRequestReviewStatus,
        comment: Union[str, Mapping[str, Any], None] = None,
    ) -> ChangeRequestReview:
        """Approve or request changes."""
        return cast(
            ChangeRequestReview,
            await self._client.request(
                "POST",
                _cr(space_id, change_request_id) + "/reviews",
                json=_review_body(status, comment),
            ),
        )
