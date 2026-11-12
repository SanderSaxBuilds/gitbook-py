"""Typed shapes of the GitBook API objects this client returns.

Every type here is a ``TypedDict`` that mirrors a schema in the GitBook
OpenAPI spec (``https://api.gitbook.com/openapi.json``). Responses are the
plain JSON dictionaries the API sends, so fields the spec adds later are
kept and nothing is lost in a conversion step. Keys marked ``Required`` are
listed as required in the spec; everything else may be absent.

Deeply nested structures that the client does not interpret (git sync
state, merge rules, document blocks and similar) are typed as
``dict[str, Any]`` so they stay accessible without pinning the client to
every internal schema.
"""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Union

from typing_extensions import Required, TypedDict

JSONObject = Dict[str, Any]
"""A JSON object the client passes through untouched."""

# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

MemberRole = Literal["admin", "create", "edit", "review", "comment", "read"]
DefaultLevel = Union[MemberRole, Literal["inherit"], None]
ContentVisibility = Literal[
    "public", "unlisted", "share-link", "visitor-auth", "in-collection", "private"
]
SpaceEditMode = Literal["live", "locked"]
ChangeRequestStatus = Literal["draft", "open", "archived", "merged"]
ChangeRequestUpdateStatus = Literal["draft", "open", "archived"]
ChangeRequestOrderBy = Literal["updatedAt", "createdAt"]
ChangeRequestReviewStatus = Literal["changes-requested", "approved"]
PageFormat = Literal["document", "markdown"]
MarkdownRefsFormat = Literal["relative", "stable"]
MemberSort = Literal["joinedAt", "lastSeenAt", "name"]
SortOrder = Literal["asc", "desc"]
TranslationLanguage = Literal[
    "en", "fr", "de", "es", "it", "pt", "pt-br", "ru", "ja", "zh", "zh-tw",
    "yue", "ko", "ar", "hi", "nl", "pl", "tr", "sv", "no", "da", "fi", "el",
    "cs", "hu", "ro", "th", "vi", "id", "ms", "he", "uk", "sk", "bg", "hr",
    "lt", "lv", "et", "sl", "fr-ca", "es-mx", "es-419",
]

# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------


class UserUrls(TypedDict):
    location: str


class User(TypedDict, total=False):
    """``#/components/schemas/User``."""

    object: Required[Literal["user"]]
    id: Required[str]
    displayName: Required[str]
    email: str
    photoURL: str
    urls: Required[UserUrls]


# ---------------------------------------------------------------------------
# Organizations
# ---------------------------------------------------------------------------


class OrganizationUrls(TypedDict, total=False):
    location: Required[str]
    app: Required[str]
    logo: str


class OrganizationPermissions(TypedDict, total=False):
    view: bool
    access: bool
    admin: bool
    ownTeam: bool
    createContent: bool
    createOpenAPISpec: bool
    viewBilling: bool
    listMembers: bool
    listTeams: bool
    listIntegrations: bool
    listInstallations: bool
    installIntegration: bool


class Organization(TypedDict, total=False):
    """``#/components/schemas/Organization``.

    Callers who are not members only receive ``object``, ``id``, ``title``,
    ``sso``, ``inviteLinks`` and ``urls``.
    """

    object: Required[Literal["organization"]]
    id: Required[str]
    title: Required[str]
    createdAt: str
    emailDomains: List[str]
    hostname: str
    type: str
    useCase: str
    communityType: str
    defaultRole: Union[MemberRole, None]
    defaultContent: JSONObject
    sso: bool
    ai: bool
    aiPreference: bool
    aiSettings: JSONObject
    aiPaused: bool
    inviteLinks: Required[bool]
    auditLogs: bool
    plan: str
    billing: JSONObject
    mergeRules: JSONObject
    supportCost: JSONObject
    urls: Required[OrganizationUrls]
    trial: JSONObject
    customHostname: str
    blocked: JSONObject
    permissions: OrganizationPermissions


class OrganizationMember(TypedDict, total=False):
    """``#/components/schemas/OrganizationMember``."""

    object: Required[Literal["member"]]
    id: Required[str]
    role: Required[Union[MemberRole, None]]
    user: Required[User]
    disabled: Required[Union[Literal[False], str]]
    joinedAt: Required[str]
    lastSeenAt: str
    sso: Required[bool]
    spaces: Required[int]
    teams: Required[int]
    sites: Required[int]


# ---------------------------------------------------------------------------
# Spaces and collections
# ---------------------------------------------------------------------------


class SpaceUrls(TypedDict, total=False):
    location: Required[str]
    app: Required[str]
    published: str
    public: str
    icon: str


class SpacePermissions(TypedDict, total=False):
    view: bool
    access: bool
    admin: bool
    viewInviteLinks: bool
    edit: bool
    triggerGitSync: bool
    comment: bool
    merge: bool
    review: bool
    installIntegration: bool


class Space(TypedDict, total=False):
    """``#/components/schemas/Space``."""

    object: Required[Literal["space"]]
    id: Required[str]
    title: Required[str]
    emoji: Required[str]
    visibility: Required[ContentVisibility]
    createdAt: Required[str]
    updatedAt: Required[str]
    deletedAt: str
    editMode: SpaceEditMode
    type: Literal["styleguide"]
    mergeRules: Required[JSONObject]
    urls: Required[SpaceUrls]
    organization: Required[str]
    parent: str
    language: TranslationLanguage
    gitSync: JSONObject
    previousGitSync: JSONObject
    imports: List[JSONObject]
    visitorAuth: JSONObject
    revision: Required[str]
    defaultLevel: Required[DefaultLevel]
    comments: Required[int]
    changeRequests: Required[int]
    changeRequestsOpen: Required[int]
    changeRequestsDraft: Required[int]
    permissions: Required[SpacePermissions]


class CollectionUrls(TypedDict):
    location: str
    app: str


class CollectionPermissions(TypedDict, total=False):
    view: bool
    admin: bool
    viewInviteLinks: bool
    create: bool


class Collection(TypedDict, total=False):
    """``#/components/schemas/Collection``."""

    object: Required[Literal["collection"]]
    id: Required[str]
    title: Required[str]
    description: str
    organization: Required[str]
    parent: str
    defaultLevel: Required[DefaultLevel]
    urls: Required[CollectionUrls]
    permissions: Required[CollectionPermissions]


class SpacePointer(TypedDict):
    type: Literal["space"]
    space: str


class CollectionPointer(TypedDict):
    type: Literal["collection"]
    collection: str


ContentPointer = Union[SpacePointer, CollectionPointer]


class ContentPosition(TypedDict, total=False):
    """Where to insert a moved space or collection among its siblings."""

    before: ContentPointer
    after: ContentPointer


# ---------------------------------------------------------------------------
# Documents, pages and revisions
# ---------------------------------------------------------------------------


class JSONDocument(TypedDict, total=False):
    """``#/components/schemas/JSONDocument``, the block tree of a page."""

    object: Required[Literal["document"]]
    data: Required[JSONObject]
    nodes: Required[List[JSONObject]]
    meta: JSONObject


class PageAncestorTitle(TypedDict):
    title: str


class RevisionPageDocument(TypedDict, total=False):
    """A content page (``#/components/schemas/RevisionPageDocument``).

    With ``format="markdown"`` the API fills ``markdown``; with
    ``format="document"`` it fills ``document``.
    """

    id: Required[str]
    title: Required[str]
    linkTitle: str
    emoji: str
    icon: str
    createdAt: str
    updatedAt: str
    condition: str
    kind: Required[Literal["sheet"]]
    type: Required[Literal["document"]]
    urls: Required[JSONObject]
    slug: Required[str]
    path: Required[str]
    description: str
    tagTitle: str
    pages: Required[List["RevisionPage"]]
    git: JSONObject
    layout: Required[JSONObject]
    cover: JSONObject
    variables: JSONObject
    hidden: bool
    noIndex: bool
    noRobotsIndex: bool
    metaLinks: JSONObject
    tags: Required[List[JSONObject]]
    markdown: str
    document: JSONDocument
    documentId: str
    computed: JSONObject
    computedSeed: str


class RevisionPageGroup(TypedDict, total=False):
    """A group of pages in the table of contents."""

    id: Required[str]
    title: Required[str]
    linkTitle: str
    emoji: str
    icon: str
    createdAt: str
    updatedAt: str
    condition: str
    kind: Required[Literal["group"]]
    type: Required[Literal["group"]]
    slug: Required[str]
    path: Required[str]
    hidden: bool
    noIndex: bool
    noRobotsIndex: bool
    pages: Required[List["RevisionPage"]]


class RevisionPageLink(TypedDict, total=False):
    """A table of contents entry that points somewhere else."""

    id: Required[str]
    title: Required[str]
    linkTitle: str
    emoji: str
    icon: str
    createdAt: str
    updatedAt: str
    condition: str
    kind: Required[Literal["link"]]
    type: Required[Literal["link"]]
    target: Required[JSONObject]
    href: str
    hidden: bool


class RevisionPageComputed(TypedDict, total=False):
    """A page generated from a computed source."""

    id: Required[str]
    title: Required[str]
    linkTitle: str
    emoji: str
    icon: str
    createdAt: str
    updatedAt: str
    condition: str
    type: Required[Literal["computed"]]
    computed: Required[JSONObject]


RevisionPage = Union[
    RevisionPageDocument, RevisionPageGroup, RevisionPageLink, RevisionPageComputed
]
"""``#/components/schemas/RevisionPage``. Check ``page["type"]`` to narrow."""


class PageList(TypedDict):
    pages: List[RevisionPage]


class RevisionUrls(TypedDict, total=False):
    app: Required[str]
    published: str
    public: str


class Revision(TypedDict, total=False):
    """``#/components/schemas/Revision`` (all five revision types)."""

    object: Required[Literal["revision"]]
    id: Required[str]
    type: Required[Literal["edits", "merge", "rollback", "update", "computed"]]
    parents: Required[List[str]]
    pages: Required[List[RevisionPage]]
    files: Required[List[JSONObject]]
    reusableContents: Required[List[JSONObject]]
    tags: Required[List[JSONObject]]
    variables: JSONObject
    createdAt: Required[str]
    git: JSONObject
    urls: Required[RevisionUrls]
    mergedFrom: "ChangeRequest"
    sourceRevision: str


# ---------------------------------------------------------------------------
# Change requests
# ---------------------------------------------------------------------------


class ChangeRequestUrls(TypedDict):
    app: str
    location: str


class ChangeRequest(TypedDict, total=False):
    """``#/components/schemas/ChangeRequest``."""

    object: Required[Literal["change-request"]]
    id: Required[str]
    number: Required[int]
    status: Required[ChangeRequestStatus]
    subject: Required[str]
    description: JSONDocument
    createdBy: Required[User]
    createdAt: Required[str]
    updatedAt: Required[str]
    mergedBy: User
    mergedAt: str
    space: Required[str]
    revision: Required[str]
    revisionInitial: Required[str]
    revisionMergedAncestor: str
    revisionMerged: str
    comments: Required[int]
    changeCounts: JSONObject
    siteTopic: JSONObject
    siteFinding: JSONObject
    siteFindings: List[JSONObject]
    styleguide: JSONObject
    outdated: Required[bool]
    imports: List[JSONObject]
    links: JSONObject
    urls: Required[ChangeRequestUrls]


class ChangeRequestMergeResult(TypedDict):
    """Body returned by the merge and update (sync) endpoints."""

    revision: str
    result: str


class ChangeRequestReview(TypedDict, total=False):
    """``#/components/schemas/ChangeRequestReview``."""

    object: Required[Literal["change-request-review"]]
    id: Required[str]
    revision: Required[str]
    reviewer: Required[User]
    requestedBy: User
    status: Required[ChangeRequestReviewStatus]
    outdated: Required[bool]
    comment: JSONObject
    createdAt: Required[str]
    updatedAt: Required[str]
    urls: Required[UserUrls]


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------


class SearchResultUrls(TypedDict):
    app: str


class SearchSectionResult(TypedDict, total=False):
    """``#/components/schemas/SearchSectionResult``."""

    id: Required[str]
    title: Required[str]
    path: Required[str]
    score: Required[float]
    resultType: Literal["page", "section"]
    body: Required[str]
    urls: Required[SearchResultUrls]


class SearchPageResult(TypedDict, total=False):
    """``#/components/schemas/SearchPageResult``."""

    id: Required[str]
    title: Required[str]
    description: Required[str]
    path: Required[str]
    score: Required[float]
    rank: Required[int]
    resultType: Literal["page", "section"]
    sections: List[SearchSectionResult]
    ancestors: Required[List[PageAncestorTitle]]
    urls: Required[SearchResultUrls]


class SearchSpaceResult(TypedDict):
    """``#/components/schemas/SearchSpaceResult``, one space in an org search."""

    type: Literal["space"]
    id: str
    title: str
    score: float
    pages: List[SearchPageResult]


class LLMSearchResult(TypedDict):
    """One hit from :meth:`SearchResource.for_llm`, flat and JSON-ready."""

    title: str
    path: str
    snippet: str
    url: str
    page_id: str
    score: float


# ---------------------------------------------------------------------------
# Lists
# ---------------------------------------------------------------------------


class ListNext(TypedDict):
    page: str


class ListResponse(TypedDict, total=False):
    """``#/components/schemas/List`` plus its ``items`` array."""

    items: Required[List[Any]]
    next: ListNext
    count: int


__all__ = [
    "ChangeRequest",
    "ChangeRequestMergeResult",
    "ChangeRequestOrderBy",
    "ChangeRequestReview",
    "ChangeRequestReviewStatus",
    "ChangeRequestStatus",
    "ChangeRequestUpdateStatus",
    "Collection",
    "CollectionPointer",
    "ContentPointer",
    "ContentPosition",
    "ContentVisibility",
    "DefaultLevel",
    "JSONDocument",
    "JSONObject",
    "LLMSearchResult",
    "ListResponse",
    "MarkdownRefsFormat",
    "MemberRole",
    "MemberSort",
    "Organization",
    "OrganizationMember",
    "PageFormat",
    "PageList",
    "Revision",
    "RevisionPage",
    "RevisionPageComputed",
    "RevisionPageDocument",
    "RevisionPageGroup",
    "RevisionPageLink",
    "SearchPageResult",
    "SearchSectionResult",
    "SearchSpaceResult",
    "SortOrder",
    "Space",
    "SpaceEditMode",
    "SpacePointer",
    "TranslationLanguage",
    "User",
]
