"""Organizations: listing, details and members."""

from __future__ import annotations

from typing import Any, Dict, Literal, Optional, Union, cast

from .._base import segment
from ..pagination import AsyncPaginator, SyncPaginator
from ..types import MemberRole, MemberSort, Organization, OrganizationMember, SortOrder
from ._resource import AsyncResource, SyncResource

__all__ = ["AsyncOrganizationsResource", "OrganizationsResource"]

RoleFilter = Union[MemberRole, Literal["guest"]]


def _member_query(
    role: Optional[RoleFilter],
    search: Optional[str],
    sort: Optional[MemberSort],
    order: Optional[SortOrder],
) -> Dict[str, Any]:
    return {"role": role, "search": search, "sort": sort, "order": order}


class OrganizationsResource(SyncResource):
    def list(
        self,
        *,
        sort: Optional[Literal["lastSeenAt"]] = None,
        limit: Optional[int] = None,
        max_items: Optional[int] = None,
    ) -> SyncPaginator[Organization]:
        """Organizations the token's user belongs to (``listOrganizationsForAuthenticatedUser``).

        With ``sort="lastSeenAt"`` the API returns only organizations the user
        has opened, newest first, as a single page.
        """
        return self._client.paginate("/orgs", {"sort": sort}, limit=limit, max_items=max_items)

    def get(self, organization_id: str) -> Organization:
        """One organization by ID (``getOrganizationById``)."""
        path = f"/orgs/{segment(organization_id, 'organization_id')}"
        return cast(Organization, self._client.request("GET", path))

    def list_members(
        self,
        organization_id: str,
        *,
        role: Optional[RoleFilter] = None,
        search: Optional[str] = None,
        sort: Optional[MemberSort] = None,
        order: Optional[SortOrder] = None,
        limit: Optional[int] = None,
        max_items: Optional[int] = None,
    ) -> SyncPaginator[OrganizationMember]:
        """Members of an organization (``listMembersInOrganizationById``)."""
        path = f"/orgs/{segment(organization_id, 'organization_id')}/members"
        return self._client.paginate(
            path, _member_query(role, search, sort, order), limit=limit, max_items=max_items
        )


class AsyncOrganizationsResource(AsyncResource):
    def list(
        self,
        *,
        sort: Optional[Literal["lastSeenAt"]] = None,
        limit: Optional[int] = None,
        max_items: Optional[int] = None,
    ) -> AsyncPaginator[Organization]:
        """Organizations the token's user belongs to."""
        return self._client.paginate("/orgs", {"sort": sort}, limit=limit, max_items=max_items)

    async def get(self, organization_id: str) -> Organization:
        """One organization by ID."""
        path = f"/orgs/{segment(organization_id, 'organization_id')}"
        return cast(Organization, await self._client.request("GET", path))

    def list_members(
        self,
        organization_id: str,
        *,
        role: Optional[RoleFilter] = None,
        search: Optional[str] = None,
        sort: Optional[MemberSort] = None,
        order: Optional[SortOrder] = None,
        limit: Optional[int] = None,
        max_items: Optional[int] = None,
    ) -> AsyncPaginator[OrganizationMember]:
        """Members of an organization."""
        path = f"/orgs/{segment(organization_id, 'organization_id')}/members"
        return self._client.paginate(
            path, _member_query(role, search, sort, order), limit=limit, max_items=max_items
        )
