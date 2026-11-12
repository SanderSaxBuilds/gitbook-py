"""Users: ``GET /user`` and ``GET /users/{userId}``."""

from __future__ import annotations

from typing import cast

from .._base import segment
from ..types import User
from ._resource import AsyncResource, SyncResource

__all__ = ["AsyncUsersResource", "UsersResource"]


class UsersResource(SyncResource):
    def me(self) -> User:
        """The user who owns the token (``getAuthenticatedUser``)."""
        return cast(User, self._client.request("GET", "/user"))

    def get(self, user_id: str) -> User:
        """A user by ID (``getUserById``)."""
        return cast(User, self._client.request("GET", f"/users/{segment(user_id, 'user_id')}"))


class AsyncUsersResource(AsyncResource):
    async def me(self) -> User:
        """The user who owns the token (``getAuthenticatedUser``)."""
        return cast(User, await self._client.request("GET", "/user"))

    async def get(self, user_id: str) -> User:
        """A user by ID (``getUserById``)."""
        return cast(
            User, await self._client.request("GET", f"/users/{segment(user_id, 'user_id')}")
        )
