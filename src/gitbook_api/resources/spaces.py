"""Spaces: create, read, update, delete, move, duplicate, restore, revisions."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Union, cast

from .._base import NOT_GIVEN, NotGiven, compact, segment
from ..pagination import AsyncPaginator, SyncPaginator
from ..types import (
    ContentPosition,
    DefaultLevel,
    Revision,
    RevisionTagWithPageCount,
    Space,
    SpaceEditMode,
    TranslationLanguage,
)
from ._resource import AsyncResource, SyncResource

__all__ = ["AsyncSpacesResource", "SpacesResource"]


def _space(space_id: str) -> str:
    return f"/spaces/{segment(space_id, 'space_id')}"


def _create_body(
    title: Optional[str],
    emoji: Optional[str],
    parent: Optional[str],
    language: Optional[TranslationLanguage],
    edit_mode: Optional[SpaceEditMode],
    empty: bool,
) -> Dict[str, Any]:
    if title is not None and len(title) > 50:
        raise ValueError("title is limited to 50 characters by the API")
    body: Dict[str, Any] = {
        k: v
        for k, v in {
            "title": title,
            "emoji": emoji,
            "parent": parent,
            "language": language,
            "editMode": edit_mode,
        }.items()
        if v is not None
    }
    if empty:
        body["empty"] = True
    return body


def _update_body(
    title: Union[str, NotGiven],
    emoji: Union[str, None, NotGiven],
    icon: Union[str, None, NotGiven],
    edit_mode: Union[SpaceEditMode, NotGiven],
    default_level: Union[DefaultLevel, NotGiven],
    language: Union[TranslationLanguage, NotGiven],
) -> Dict[str, Any]:
    if not isinstance(emoji, NotGiven) and not isinstance(icon, NotGiven):
        if emoji is not None and icon is not None:
            raise ValueError("set either emoji or icon, not both")
    body = compact(
        {
            "title": title,
            "emoji": emoji,
            "icon": icon,
            "editMode": edit_mode,
            "defaultLevel": default_level,
            "language": language,
        }
    )
    if not body:
        raise ValueError("update needs at least one field to change")
    return body


def _move_body(
    parent: Union[str, None, NotGiven], position: Optional[ContentPosition]
) -> Dict[str, Any]:
    body: Dict[str, Any] = compact({"parent": parent})
    if position is not None:
        body["position"] = dict(position)
    if not body:
        raise ValueError("move needs parent, position or both")
    return body


def _revision_query(metadata: Optional[bool], computed: Optional[bool]) -> Dict[str, Any]:
    return {"metadata": metadata, "computed": computed}


def _tags_of(data: Any) -> List[RevisionTagWithPageCount]:
    if isinstance(data, dict) and isinstance(data.get("tags"), list):
        return cast(List[RevisionTagWithPageCount], data["tags"])
    raise TypeError("expected an object with a 'tags' array")


class SpacesResource(SyncResource):
    def list(
        self,
        organization_id: str,
        *,
        limit: Optional[int] = None,
        max_items: Optional[int] = None,
    ) -> SyncPaginator[Space]:
        """Every space in an organization (``listSpacesInOrganizationById``)."""
        path = f"/orgs/{segment(organization_id, 'organization_id')}/spaces"
        return self._client.paginate(path, limit=limit, max_items=max_items)

    def get(self, space_id: str, *, share_key: Optional[str] = None) -> Space:
        """One space by ID (``getSpaceById``). ``share_key`` opens a share link."""
        return cast(
            Space, self._client.request("GET", _space(space_id), params={"shareKey": share_key})
        )

    def create(
        self,
        organization_id: str,
        *,
        title: Optional[str] = None,
        emoji: Optional[str] = None,
        parent: Optional[str] = None,
        language: Optional[TranslationLanguage] = None,
        edit_mode: Optional[SpaceEditMode] = None,
        empty: bool = False,
    ) -> Space:
        """Create a space (``createSpace``).

        ``parent`` is a collection ID. ``empty=True`` creates a space with
        no pages at all.
        """
        path = f"/orgs/{segment(organization_id, 'organization_id')}/spaces"
        body = _create_body(title, emoji, parent, language, edit_mode, empty)
        return cast(Space, self._client.request("POST", path, json=body))

    def update(
        self,
        space_id: str,
        *,
        title: Union[str, NotGiven] = NOT_GIVEN,
        emoji: Union[str, None, NotGiven] = NOT_GIVEN,
        icon: Union[str, None, NotGiven] = NOT_GIVEN,
        edit_mode: Union[SpaceEditMode, NotGiven] = NOT_GIVEN,
        default_level: Union[DefaultLevel, NotGiven] = NOT_GIVEN,
        language: Union[TranslationLanguage, NotGiven] = NOT_GIVEN,
    ) -> Space:
        """Change a space's title, icon or settings (``updateSpaceById``).

        Only the arguments you pass are sent. ``emoji=None, icon=None``
        clears the icon. ``default_level=None`` sets guest level.
        """
        body = _update_body(title, emoji, icon, edit_mode, default_level, language)
        return cast(Space, self._client.request("PATCH", _space(space_id), json=body))

    def delete(self, space_id: str) -> None:
        """Move a space to the trash (``deleteSpaceById``)."""
        self._client.request("DELETE", _space(space_id))

    def restore(self, space_id: str) -> Space:
        """Bring a recently deleted space back (``restoreSpace``)."""
        return cast(Space, self._client.request("POST", _space(space_id) + "/restore"))

    def duplicate(self, space_id: str) -> Space:
        """Copy a space with all its content (``duplicateSpace``)."""
        return cast(Space, self._client.request("POST", _space(space_id) + "/duplicate"))

    def move(
        self,
        space_id: str,
        *,
        parent: Union[str, None, NotGiven] = NOT_GIVEN,
        position: Optional[ContentPosition] = None,
    ) -> Space:
        """Move a space to another collection or position (``moveSpace``).

        ``parent=None`` moves it to the organization root.
        """
        body = _move_body(parent, position)
        return cast(Space, self._client.request("POST", _space(space_id) + "/move", json=body))

    def get_current_revision(
        self,
        space_id: str,
        *,
        metadata: Optional[bool] = None,
        computed: Optional[bool] = None,
    ) -> Revision:
        """The live revision with its page tree and files (``getCurrentRevision``)."""
        return cast(
            Revision,
            self._client.request(
                "GET", _space(space_id) + "/content", params=_revision_query(metadata, computed)
            ),
        )

    def get_revision(
        self,
        space_id: str,
        revision_id: str,
        *,
        metadata: Optional[bool] = None,
        computed: Optional[bool] = None,
    ) -> Revision:
        """A historical revision by ID (``getRevisionById``)."""
        path = f"{_space(space_id)}/revisions/{segment(revision_id, 'revision_id')}"
        return cast(
            Revision,
            self._client.request("GET", path, params=_revision_query(metadata, computed)),
        )

    def list_tags(self, space_id: str) -> List[RevisionTagWithPageCount]:
        """Tags and categories of the published content, with page counts (``listTags``).

        Parents come before children. Pass slugs to ``pages.list(tag=...)``
        to get the pages behind a tag.
        """
        return _tags_of(self._client.request("GET", _space(space_id) + "/content/tags"))


class AsyncSpacesResource(AsyncResource):
    def list(
        self,
        organization_id: str,
        *,
        limit: Optional[int] = None,
        max_items: Optional[int] = None,
    ) -> AsyncPaginator[Space]:
        """Every space in an organization."""
        path = f"/orgs/{segment(organization_id, 'organization_id')}/spaces"
        return self._client.paginate(path, limit=limit, max_items=max_items)

    async def get(self, space_id: str, *, share_key: Optional[str] = None) -> Space:
        """One space by ID."""
        return cast(
            Space,
            await self._client.request("GET", _space(space_id), params={"shareKey": share_key}),
        )

    async def create(
        self,
        organization_id: str,
        *,
        title: Optional[str] = None,
        emoji: Optional[str] = None,
        parent: Optional[str] = None,
        language: Optional[TranslationLanguage] = None,
        edit_mode: Optional[SpaceEditMode] = None,
        empty: bool = False,
    ) -> Space:
        """Create a space."""
        path = f"/orgs/{segment(organization_id, 'organization_id')}/spaces"
        body = _create_body(title, emoji, parent, language, edit_mode, empty)
        return cast(Space, await self._client.request("POST", path, json=body))

    async def update(
        self,
        space_id: str,
        *,
        title: Union[str, NotGiven] = NOT_GIVEN,
        emoji: Union[str, None, NotGiven] = NOT_GIVEN,
        icon: Union[str, None, NotGiven] = NOT_GIVEN,
        edit_mode: Union[SpaceEditMode, NotGiven] = NOT_GIVEN,
        default_level: Union[DefaultLevel, NotGiven] = NOT_GIVEN,
        language: Union[TranslationLanguage, NotGiven] = NOT_GIVEN,
    ) -> Space:
        """Change a space's title, icon or settings."""
        body = _update_body(title, emoji, icon, edit_mode, default_level, language)
        return cast(Space, await self._client.request("PATCH", _space(space_id), json=body))

    async def delete(self, space_id: str) -> None:
        """Move a space to the trash."""
        await self._client.request("DELETE", _space(space_id))

    async def restore(self, space_id: str) -> Space:
        """Bring a recently deleted space back."""
        return cast(Space, await self._client.request("POST", _space(space_id) + "/restore"))

    async def duplicate(self, space_id: str) -> Space:
        """Copy a space with all its content."""
        return cast(Space, await self._client.request("POST", _space(space_id) + "/duplicate"))

    async def move(
        self,
        space_id: str,
        *,
        parent: Union[str, None, NotGiven] = NOT_GIVEN,
        position: Optional[ContentPosition] = None,
    ) -> Space:
        """Move a space to another collection or position."""
        body = _move_body(parent, position)
        return cast(
            Space, await self._client.request("POST", _space(space_id) + "/move", json=body)
        )

    async def get_current_revision(
        self,
        space_id: str,
        *,
        metadata: Optional[bool] = None,
        computed: Optional[bool] = None,
    ) -> Revision:
        """The live revision with its page tree and files."""
        return cast(
            Revision,
            await self._client.request(
                "GET", _space(space_id) + "/content", params=_revision_query(metadata, computed)
            ),
        )

    async def get_revision(
        self,
        space_id: str,
        revision_id: str,
        *,
        metadata: Optional[bool] = None,
        computed: Optional[bool] = None,
    ) -> Revision:
        """A historical revision by ID."""
        path = f"{_space(space_id)}/revisions/{segment(revision_id, 'revision_id')}"
        return cast(
            Revision,
            await self._client.request("GET", path, params=_revision_query(metadata, computed)),
        )

    async def list_tags(self, space_id: str) -> List[RevisionTagWithPageCount]:
        """Tags and categories of the published content, with page counts."""
        return _tags_of(await self._client.request("GET", _space(space_id) + "/content/tags"))
