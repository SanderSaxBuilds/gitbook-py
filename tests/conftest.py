from __future__ import annotations

import json
from pathlib import Path
from typing import Any, AsyncIterator, Iterator, List

import pytest
import respx

from gitbook_api import AsyncGitBook, GitBook

FIXTURES = Path(__file__).parent / "fixtures"
BASE_URL = "https://api.gitbook.com/v1"
TOKEN = "gb_api_test_token"


def load(name: str) -> Any:
    """Read a JSON fixture from tests/fixtures."""
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


class SleepRecorder:
    """Stands in for time.sleep / asyncio.sleep and records the delays."""

    def __init__(self) -> None:
        self.calls: List[float] = []

    def __call__(self, seconds: float) -> None:
        self.calls.append(seconds)

    async def async_sleep(self, seconds: float) -> None:
        self.calls.append(seconds)


@pytest.fixture(autouse=True)
def _no_env_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GITBOOK_TOKEN", raising=False)
    monkeypatch.delenv("GITBOOK_BASE_URL", raising=False)


@pytest.fixture
def api() -> Iterator[respx.MockRouter]:
    with respx.mock(base_url=BASE_URL, assert_all_called=True, assert_all_mocked=True) as router:
        yield router


@pytest.fixture
def sleeps() -> SleepRecorder:
    return SleepRecorder()


@pytest.fixture
def client(sleeps: SleepRecorder) -> Iterator[GitBook]:
    c = GitBook(TOKEN)
    c._sleep = sleeps
    yield c
    c.close()


@pytest.fixture
async def aclient(sleeps: SleepRecorder) -> AsyncIterator[AsyncGitBook]:
    c = AsyncGitBook(TOKEN)
    c._sleep = sleeps.async_sleep
    yield c
    await c.close()
