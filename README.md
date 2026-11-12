# gitbook-py

A typed Python client for the [GitBook API](https://gitbook.com/docs/developers/gitbook-api/overview). It covers organizations, spaces, pages and page content, search, change requests, collections and users, with a sync client and an async client built on httpx.

- Every response is a `TypedDict` that follows the GitBook OpenAPI spec, and the package passes `mypy --strict`.
- List endpoints return iterators that follow GitBook's page cursors for you.
- HTTP errors become typed exceptions such as `NotFoundError` and `RateLimitError`.
- Rate limits and server errors are retried with backoff, and `Retry-After` is honored.
- `search.for_llm()` returns title, path and a plain-text snippet per page, ready to hand to a language model as a tool result.

Python 3.10 or newer. The only dependencies are `httpx` and `typing_extensions`.

## Install

From a checkout of this repository:

```bash
pip install .
```

For development, with the test and type-check tools:

```bash
pip install -e ".[dev]"
```

## Quick start

Create a personal access token in GitBook under Settings, Developer settings. Pass it to the client, or set `GITBOOK_TOKEN` in the environment.

```python
from gitbook_api import GitBook

with GitBook() as gb:  # reads GITBOOK_TOKEN
    me = gb.users.me()
    print(me["displayName"])

    for org in gb.organizations.list():
        print(org["id"], org["title"])
        for space in gb.spaces.list(org["id"]):
            print("  ", space["title"], space["urls"]["app"])
```

The client takes these options:

```python
gb = GitBook(
    "gb_api_...",                    # or GITBOOK_TOKEN
    base_url="https://api.gitbook.com/v1",  # or GITBOOK_BASE_URL
    timeout=30.0,                    # seconds, or an httpx.Timeout
    max_retries=3,
    user_agent="my-app/1.0",
    default_headers={"X-Team": "docs"},
    http_client=None,                # bring your own httpx.Client
)
```

If you pass your own `http_client`, the client uses it as is and does not close it.

## Resources

### Users

```python
gb.users.me()             # the owner of the token
gb.users.get("user_id")
```

### Organizations

```python
gb.organizations.list()
gb.organizations.get("org_id")
gb.organizations.list_members("org_id", role="admin", search="ada", sort="joinedAt", order="desc")
```

### Spaces

```python
gb.spaces.list("org_id")
gb.spaces.get("space_id")
gb.spaces.create("org_id", title="API reference", emoji="1f4d8", parent="collection_id")
gb.spaces.update("space_id", title="API docs", default_level="read")
gb.spaces.move("space_id", parent="collection_id")
gb.spaces.duplicate("space_id")
gb.spaces.delete("space_id")
gb.spaces.restore("space_id")

gb.spaces.get_current_revision("space_id")
gb.spaces.get_revision("space_id", "revision_id")
```

`update()` only sends the fields you pass, so leaving a field out keeps its current value. Passing `None` sends `null`: `emoji=None` removes the emoji, and `default_level=None` sets the guest level, which gives members no default access. `default_level="inherit"` takes the level from the parent collection.

### Pages and page content

```python
from gitbook_api import iter_pages

tree = gb.pages.list("space_id")           # the page tree of the live content
for page in iter_pages(tree):              # depth first, nested pages included
    print(page["type"], page["title"], page.get("path"))

page = gb.pages.get("space_id", "page_id")
page = gb.pages.get_by_path("space_id", "guides/authentication")

markdown = gb.pages.get_markdown("space_id", "page_id")
document = gb.pages.get_document("space_id", "page_id")   # JSON block tree
```

Every page method reads the live content by default. Pass `change_request_id=` to read a change request's content, or `revision_id=` to read a past revision. `get()` also takes `format="markdown"` or `format="document"`, `evaluated=True` and `dereferenced=True`.

### Search

```python
for hit in gb.search.space("space_id", "rate limits"):
    print(hit["title"], hit["path"], [s["title"] for s in hit["sections"]])

for space in gb.search.organization("org_id", "rate limits"):
    print(space["title"], len(space["pages"]))
```

### Change requests

```python
cr = gb.change_requests.create("space_id", subject="Document the search endpoint")

gb.change_requests.list("space_id", status="open", order_by="updatedAt")
gb.change_requests.list_for_organization("org_id", status=["open", "draft"])
gb.change_requests.get("space_id", cr["id"])
gb.change_requests.update("space_id", cr["id"], subject="Search endpoint docs", status="open")

gb.change_requests.submit_review("space_id", cr["id"], status="approved", comment="Looks good")
gb.change_requests.list_reviews("space_id", cr["id"])

gb.change_requests.sync("space_id", cr["id"])    # bring in changes from the main content
gb.change_requests.merge("space_id", cr["id"])
```

A string `comment` is sent as Markdown. To send a JSON document instead, pass `comment={"document": {...}}`.

### Collections

```python
gb.collections.list("org_id", nested=True)
gb.collections.get("collection_id")
gb.collections.create("org_id", title="Developer docs")
gb.collections.update("collection_id", description="Everything for integrators")
gb.collections.move("collection_id", parent=None)        # move to the top level
gb.collections.list_spaces("collection_id")
gb.collections.delete("collection_id")
```

### Anything else

The API has more endpoints than this package wraps. `request()` and `paginate()` give you the same auth, retries and errors for any of them:

```python
integrations = gb.request("GET", "/integrations", params={"limit": 50})

for site in gb.paginate("/orgs/org_id/sites"):
    print(site["title"])
```

## Pagination

List methods return a paginator. Nothing is fetched until you start reading it.

```python
spaces = gb.spaces.list("org_id", limit=100)    # 100 items per request

for space in spaces:                            # follows next.page until the end
    ...

first = spaces.first_page()                     # one request
print(first.items, first.next_page, first.count)

for page in spaces.pages():                     # page by page
    print(len(page.items))

everything = spaces.to_list()
first_fifty = gb.spaces.list("org_id", max_items=50).to_list()
```

`limit` must be between 1 and 1000. A paginator can be iterated more than once, and each pass starts again from the first page. To resume later, keep `page.next_page` and call `get_page(token)`.

## Async

`AsyncGitBook` has the same resources and the same method names. Methods that make one request are coroutines. List methods return async paginators.

```python
import asyncio
from gitbook_api import AsyncGitBook

async def main() -> None:
    async with AsyncGitBook() as gb:
        me = await gb.users.me()
        async for space in gb.spaces.list("org_id"):
            print(space["title"])
        open_crs = await gb.change_requests.list("space_id", status="open").to_list()

asyncio.run(main())
```

## Errors

Every exception derives from `GitBookError`.

| Exception | When |
| --- | --- |
| `BadRequestError` | 400 |
| `AuthenticationError` | 401, the token is missing, wrong or revoked |
| `PermissionDeniedError` | 403 |
| `FeatureNotAvailableError` | 403 because the plan lacks the feature, see `.upgrade` |
| `NotFoundError` | 404 |
| `ConflictError` | 409 |
| `PreconditionFailedError` | 412 |
| `UnprocessableEntityError` | 422 |
| `RateLimitError` | 429, after retries ran out, see `.retry_after` |
| `InternalServerError` | 5xx |
| `APIStatusError` | any other status, and the base class of all of the above |
| `APITimeoutError` | the request timed out |
| `APIConnectionError` | the server could not be reached |

Status errors carry `status_code`, `message`, `body` (the parsed JSON), `response` and `request_id` (from the `x-request-id` header).

```python
from gitbook_api import FeatureNotAvailableError, NotFoundError

try:
    gb.change_requests.merge("space_id", "cr_id")
except FeatureNotAvailableError as exc:
    print("Needs", exc.upgrade["requiredPlanName"], exc.upgrade["url"])
except NotFoundError:
    print("No such change request")
```

## Retries

By default a failed request is tried up to 3 more times.

- 429 and 503 are retried for every method.
- 500, 502, 504, timeouts and connection errors are retried only for GET, HEAD, OPTIONS, PUT and DELETE, so a POST or PATCH is never sent twice by accident.
- The wait comes from `Retry-After` when the server sends it (seconds or an HTTP date). For a 429 without it, the client waits until `X-RateLimit-Reset`. Otherwise it backs off exponentially with jitter: about 0.5, 1 and 2 seconds.
- If the server asks for a wait longer than `max_retry_after` (120 seconds by default), the error is raised at once instead of blocking.

To change this, pass a `RetryPolicy`:

```python
from gitbook_api import GitBook, RetryPolicy

gb = GitBook(retry=RetryPolicy(max_retries=5, backoff_factor=1.0, max_backoff=60.0))
gb = GitBook(max_retries=0)                                  # no retries
gb = GitBook(retry=RetryPolicy(retry_non_idempotent=True))   # retry POST and PATCH on 5xx too
```

## Search for LLM tools

`search.for_llm()` runs a space search and returns one flat result per page, with the Markdown, HTML and GitBook block tags stripped from the snippet:

```python
hits = gb.search.for_llm("space_id", "how do I rotate a token", limit=5)
# [{"title": "Authentication",
#   "path": "guides/authentication",
#   "snippet": "Send your token in the Authorization header. ... Revoke an old token ...",
#   "url": "https://app.gitbook.com/s/S9pQrT2uVwXyZ0aB1cDe/guides/authentication",
#   "page_id": "P3aUtHaBcDeFgHiJkL01",
#   "score": 12.5}, ...]
```

The snippet is built from the best matching sections and cut to about `snippet_chars` characters (320 by default) around the query. With `fetch_content=True` the client reads each page's Markdown and cuts the snippet from the full text. The async client reads those pages in parallel.

`SEARCH_TOOL` is a ready tool definition (name, description and JSON Schema parameters), and `format_results()` turns the hits into a compact text block for the tool result:

```python
from gitbook_api import SEARCH_TOOL, GitBook, format_results

gb = GitBook()

def run_tool(name: str, args: dict) -> str:
    if name == SEARCH_TOOL["name"]:
        hits = gb.search.for_llm("space_id", args["query"], limit=args.get("limit", 5))
        return format_results(hits)
    raise KeyError(name)
```

Most model APIs take the same fields under slightly different keys. For Anthropic's Messages API, for example, pass `{"name": ..., "description": ..., "input_schema": SEARCH_TOOL["parameters"]}`.

## Text helpers

The functions behind the snippets are public:

```python
from gitbook_api import document_to_text, make_snippet, markdown_to_text

markdown_to_text(gb.pages.get_markdown("space_id", "page_id"))
document_to_text(gb.pages.get_document("space_id", "page_id"))
make_snippet(long_text, "token rotation", max_chars=200)
```

## Types

All models live in `gitbook_api.types`, for example `Space`, `RevisionPage`, `ChangeRequest` and `SearchPageResult`. They are `TypedDict` classes, so responses are plain dicts at run time and fully typed for your editor and mypy. Fields the spec marks as required are typed as always present, everything else is optional.

## Development

```bash
pip install -e ".[dev]"
pytest --cov=gitbook_api
mypy --strict
```

The tests use [respx](https://lundberg.github.io/respx/) to mock httpx and make no network calls. The JSON fixtures in `tests/fixtures` are shaped like real API responses, and `scripts/validate_fixtures.py` checks every one of them against the response schemas in the OpenAPI spec:

```bash
pip install jsonschema
curl -o openapi.json https://api.gitbook.com/openapi.json
python scripts/validate_fixtures.py openapi.json
```

## License

MIT, see [LICENSE](LICENSE).
