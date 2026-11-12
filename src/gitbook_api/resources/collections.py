"""Collections: folders that group spaces inside an organization."""

from __future__ import annotations

from typing import Any, Dict, Optional, Union, cast

from .._base import NOT_GIVEN, NotGiven, compact, segment
from ..pagination import AsyncPaginator, SyncPaginator
from ..types import Collection, ContentPosition, DefaultLevel, Space
from ._resource import AsyncResource, SyncResource
from .spaces import _move_body

__all__ = ["AsyncCollectionsResource", "CollectionsResource"]


def _collection(collection_id: str) -> str:
    return f"/collections/{segment(collection_id, 'collection_id')}"


def _create_body(title: Optional[str], parent: Optional[str]) -> Dict[str, Any]:
    return {k: v for k, v in {"title": title, "parent": parent}.items() if v is not None}


def _update_body(
    title: Union[str, NotGiven],
    description: Union[str, NotGiven],
    default_level: Union[DefaultLevel, NotGiven],
) -> Dict[str, Any]:
    body = compact({"title": title, "description": description, "defaultLevel": default_level})
    if not body:
        raise ValueError("update needs at least one field to change")
    return body


class CollectionsResource(SyncResource):
    def list(
        self,
        organization_id: str,
        *,
        nested: Optional[bool] = None,
        limit: Optional[int] = None,
        max_items: Optional[int] = None,
    ) -> SyncPaginator[Collection]:
        """Collections in an organization (``listCollectionsInOrganizationById``).

        ``nested=False`` limits the list to top-level collections.
        """
        path = f"/orgs/{segment(organization_id, 'organization_id')}/collections"
        return self._client.paginate(path, {"nested": nested}, limit=limit, max_items=max_items)

    def get(self, collection_id: str) -> Collection:
        """One collection by ID (``getCollectionById``)."""
        return cast(Collection, self._client.request("GET", _collection(collection_id)))

    def create(
        self,
        organization_id: str,
        *,
        title: Optional[str] = None,
        parent: Optional[str] = None,
    ) -> Collection:
        """Create a collection, optionally inside ``parent`` (``createCollection``)."""
        path = f"/orgs/{segment(organization_id, 'organization_id')}/collections"
        return cast(
            Collection, self._client.request("POST", path, json=_create_body(title, parent))
        )

    def update(
        self,
        collection_id: str,
        *,
        title: Union[str, NotGiven] = NOT_GIVEN,
        description: Union[str, NotGiven] = NOT_GIVEN,
        default_level: Union[DefaultLevel, NotGiven] = NOT_GIVEN,
    ) -> Collection:
        """Change a collection's title, description or default level (``updateCollectionById``)."""
        body = _update_body(title, description, default_level)
        return cast(Collection, self._client.request("PATCH", _collection(collection_id), json=body))

    def delete(self, collection_id: str) -> None:
        """Delete a collection (``deleteCollectionById``)."""
        self._client.request("DELETE", _collection(collection_id))

    def move(
        self,
        collection_id: str,
        *,
        parent: Union[str, None, NotGiven] = NOT_GIVEN,
        position: Optional[ContentPosition] = None,
    ) -> Collection:
        """Move a collection under another parent or position (``moveCollection``)."""
        body = _move_body(parent, position)
        return cast(
            Collection,
            self._client.request("POST", _collection(collection_id) + "/move", json=body),
        )

    def list_spaces(
        self,
        collection_id: str,
        *,
        limit: Optional[int] = None,
        max_items: Optional[int] = None,
    ) -> SyncPaginator[Space]:
        """Spaces inside a collection (``listSpacesInCollectionById``)."""
        return self._client.paginate(
            _collection(collection_id) + "/spaces", limit=limit, max_items=max_items
        )


class AsyncCollectionsResource(AsyncResource):
    def list(
        self,
        organization_id: str,
        *,
        nested: Optional[bool] = None,
        limit: Optional[int] = None,
        max_items: Optional[int] = None,
    ) -> AsyncPaginator[Collection]:
        """Collections in an organization."""
        path = f"/orgs/{segment(organization_id, 'organization_id')}/collections"
        return self._client.paginate(path, {"nested": nested}, limit=limit, max_items=max_items)

    async def get(self, collection_id: str) -> Collection:
        """One collection by ID."""
        return cast(Collection, await self._client.request("GET", _collection(collection_id)))

    async def create(
        self,
        organization_id: str,
        *,
        title: Optional[str] = None,
        parent: Optional[str] = None,
    ) -> Collection:
        """Create a collection."""
        path = f"/orgs/{segment(organization_id, 'organization_id')}/collections"
        return cast(
            Collection,
            await self._client.request("POST", path, json=_create_body(title, parent)),
        )

    async def update(
        self,
        collection_id: str,
        *,
        title: Union[str, NotGiven] = NOT_GIVEN,
        description: Union[str, NotGiven] = NOT_GIVEN,
        default_level: Union[DefaultLevel, NotGiven] = NOT_GIVEN,
    ) -> Collection:
        """Change a collection's title, description or default level."""
        body = _update_body(title, description, default_level)
        return cast(
            Collection,
            await self._client.request("PATCH", _collection(collection_id), json=body),
        )

    async def delete(self, collection_id: str) -> None:
        """Delete a collection."""
        await self._client.request("DELETE", _collection(collection_id))

    async def move(
        self,
        collection_id: str,
        *,
        parent: Union[str, None, NotGiven] = NOT_GIVEN,
        position: Optional[ContentPosition] = None,
    ) -> Collection:
        """Move a collection under another parent or position."""
        body = _move_body(parent, position)
        return cast(
            Collection,
            await self._client.request("POST", _collection(collection_id) + "/move", json=body),
        )

    def list_spaces(
        self,
        collection_id: str,
        *,
        limit: Optional[int] = None,
        max_items: Optional[int] = None,
    ) -> AsyncPaginator[Space]:
        """Spaces inside a collection."""
        return self._client.paginate(
            _collection(collection_id) + "/spaces", limit=limit, max_items=max_items
        )
