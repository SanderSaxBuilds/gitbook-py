"""Check every test fixture against the GitBook OpenAPI spec.

Usage:
    python scripts/validate_fixtures.py path/to/openapi.json

Download the spec first from https://api.gitbook.com/openapi.json (or take
``spec/openapi.json`` from the ``@gitbook/api`` npm package). Needs
``jsonschema`` (``pip install jsonschema``). Exits non-zero when a fixture
does not match the schema of the response it stands for.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List

from jsonschema import Draft202012Validator
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT202012

FIXTURES = Path(__file__).resolve().parent.parent / "tests" / "fixtures"
SPEC_URI = "urn:gitbook-openapi"


def response(path: str, method: str, status: str = "200") -> str:
    escaped = path.replace("~", "~0").replace("/", "~1")
    return f"/paths/{escaped}/{method}/responses/{status}/content/application~1json/schema"


def error(name: str) -> str:
    return f"/components/responses/{name}/content/application~1json/schema"


S = "/spaces/{spaceId}"
CR = S + "/change-requests/{changeRequestId}"
TARGETS: Dict[str, str] = {
    "user.json": response("/user", "get"),
    "organization.json": response("/orgs/{organizationId}", "get"),
    "organizations_page1.json": response("/orgs", "get"),
    "organizations_page2.json": response("/orgs", "get"),
    "members.json": response("/orgs/{organizationId}/members", "get"),
    "space.json": response(S, "get"),
    "spaces_page1.json": response("/orgs/{organizationId}/spaces", "get"),
    "spaces_page2.json": response("/orgs/{organizationId}/spaces", "get"),
    "collection.json": response("/collections/{collectionId}", "get"),
    "collections.json": response("/orgs/{organizationId}/collections", "get"),
    "change_request.json": response(CR, "get"),
    "change_requests_page1.json": response(S + "/change-requests", "get"),
    "change_requests_page2.json": response(S + "/change-requests", "get"),
    "merge_result.json": response(CR + "/merge", "post"),
    "review.json": response(CR + "/reviews", "post", "201"),
    "revision.json": response(S + "/content", "get"),
    "pages.json": response(S + "/content/pages", "get"),
    "tags.json": response(S + "/content/tags", "get"),
    "revision_merge_site.json": response(S + "/revisions/{revisionId}", "get"),
    "page_markdown.json": response(S + "/content/page/{pageId}", "get"),
    "page_document.json": response(S + "/content/page/{pageId}", "get"),
    "page_group.json": response(S + "/content/path/{pagePath}", "get"),
    "json_document.json": response(S + "/revisions/{revisionId}/page/{pageId}/document", "get"),
    "search_space_page1.json": response(S + "/search", "get"),
    "search_space_page2.json": response(S + "/search", "get"),
    "search_org.json": response("/orgs/{organizationId}/search", "get"),
    "error_400.json": error("BadRequestError"),
    "error_401.json": error("UnauthorizedError"),
    "error_403.json": error("ForbiddenError"),
    "error_404.json": error("NotFoundError"),
    "error_409.json": error("ConflictError"),
    "error_412.json": error("PreconditionFailedError"),
    "error_429.json": "/components/schemas/Error",
    "error_500.json": error("UnexpectedError"),
    "error_feature_not_available.json": error("FeatureNotAvailableError"),
}


def relax_empty_document(spec: Any) -> None:
    """Work around one spec quirk before validating.

    ``RevisionPageDocument`` is an ``allOf`` that includes ``Document``, and
    the "Empty" branch of ``Document`` sets ``additionalProperties: false``.
    Read literally, that rejects every document page without inline
    ``markdown`` or ``document``, which is what ``listPages`` returns. The
    branch is relaxed here so it means "no content fields", as intended.
    """
    for branch in spec["components"]["schemas"]["Document"].get("oneOf", []):
        if branch.get("title") == "Empty" and branch.get("additionalProperties") is False:
            del branch["additionalProperties"]
            branch["not"] = {"anyOf": [{"required": ["markdown"]}, {"required": ["document"]}]}
            print("note: relaxed Document 'Empty' branch (additionalProperties: false inside allOf)")


def main(argv: List[str]) -> int:
    if len(argv) != 2:
        print(__doc__)
        return 2
    spec: Any = json.loads(Path(argv[1]).read_text(encoding="utf-8-sig"))
    relax_empty_document(spec)
    registry: Registry[Any] = Registry().with_resource(
        SPEC_URI, Resource.from_contents(spec, default_specification=DRAFT202012)
    )
    failures = 0
    names = sorted(p.name for p in FIXTURES.glob("*.json"))
    unmapped = [n for n in names if n not in TARGETS]
    for name in names:
        pointer = TARGETS.get(name)
        if pointer is None:
            continue
        data = json.loads((FIXTURES / name).read_text(encoding="utf-8"))
        validator = Draft202012Validator({"$ref": SPEC_URI + "#" + pointer}, registry=registry)
        errors = sorted(validator.iter_errors(data), key=lambda e: list(e.absolute_path))
        if errors:
            failures += 1
            print(f"FAIL {name}")
            for err in errors[:5]:
                where = "/".join(str(p) for p in err.absolute_path) or "(root)"
                print(f"     {where}: {err.message[:300]}")
        else:
            print(f"ok   {name}")
    for name in unmapped:
        failures += 1
        print(f"FAIL {name}: no schema mapping in TARGETS")
    print(f"{len(names) - failures} of {len(names)} fixtures match the spec")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
