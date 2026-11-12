"""Resource groups exposed as attributes of the clients."""

from .change_requests import AsyncChangeRequestsResource, ChangeRequestsResource
from .collections import AsyncCollectionsResource, CollectionsResource
from .organizations import AsyncOrganizationsResource, OrganizationsResource
from .pages import AsyncPagesResource, PagesResource, iter_pages
from .search import SEARCH_TOOL, AsyncSearchResource, SearchResource, format_results
from .spaces import AsyncSpacesResource, SpacesResource
from .users import AsyncUsersResource, UsersResource

__all__ = [
    "AsyncChangeRequestsResource",
    "AsyncCollectionsResource",
    "AsyncOrganizationsResource",
    "AsyncPagesResource",
    "AsyncSearchResource",
    "AsyncSpacesResource",
    "AsyncUsersResource",
    "ChangeRequestsResource",
    "CollectionsResource",
    "OrganizationsResource",
    "PagesResource",
    "SEARCH_TOOL",
    "SearchResource",
    "SpacesResource",
    "UsersResource",
    "format_results",
    "iter_pages",
]
