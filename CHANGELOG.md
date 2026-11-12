# Changelog

## 0.1.0

First release.

- Sync `GitBook` and async `AsyncGitBook` clients on httpx, with bearer token auth from an argument or `GITBOOK_TOKEN`.
- Resources for users, organizations and members, spaces and revisions, pages and page content (Markdown and JSON document), space and organization search, change requests and reviews, and collections.
- Lazy cursor pagination with `max_items`, page access and resume tokens.
- Typed exceptions per status code, including `FeatureNotAvailableError` with the upgrade details.
- Retries with exponential backoff and jitter on 429 and 5xx, honoring `Retry-After` and `X-RateLimit-Reset`.
- `search.for_llm()`, `SEARCH_TOOL` and `format_results()` for language model tool calls.
- `TypedDict` models for every response, checked with `mypy --strict`.
