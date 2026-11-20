# Changelog

## 0.2.0

Follows `@gitbook/api` 0.210 and 0.211 (18 and 19 November 2026).

- `spaces.list_tags()` for the new `listTags` endpoint: every tag and category of the published content, parents first, with `pageCount`.
- `pages.list(tag=...)` takes one slug or several, sent as a repeated `tag` parameter, on live content, change requests and revisions. An empty slug or list raises `ValueError` before the request.
- `Revision.mergedFrom` is now `ChangeRequest | SiteChangeRequest` and may be absent, matching the new `RevisionMergedFrom` schema. New `SiteChangeRequest`, `RevisionTag` and `RevisionTagWithPageCount` types, and `Revision.tags` is typed.
- Two new fixtures, checked against the 0.211 spec by `scripts/validate_fixtures.py`. 233 tests.

## 0.1.0

First release.

- Sync `GitBook` and async `AsyncGitBook` clients on httpx, with bearer token auth from an argument or `GITBOOK_TOKEN`.
- Resources for users, organizations and members, spaces and revisions, pages and page content (Markdown and JSON document), space and organization search, change requests and reviews, and collections.
- Lazy cursor pagination with `max_items`, page access and resume tokens.
- Typed exceptions per status code, including `FeatureNotAvailableError` with the upgrade details.
- Retries with exponential backoff and jitter on 429 and 5xx, honoring `Retry-After` and `X-RateLimit-Reset`.
- `search.for_llm()`, `SEARCH_TOOL` and `format_results()` for language model tool calls.
- `TypedDict` models for every response, checked with `mypy --strict`.
