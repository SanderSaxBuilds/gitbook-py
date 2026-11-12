from __future__ import annotations

import pytest

from gitbook_api import document_to_text, make_snippet, markdown_to_text

from .conftest import load


def test_document_to_text_fixture() -> None:
    text = document_to_text(load("json_document.json"))
    assert text.split("\n") == [
        "Authentication",
        "Send your token in the Authorization header. See tokens.",
        "export GITBOOK_TOKEN=gb_api_xxx",
        'curl -H "Authorization: Bearer $GITBOOK_TOKEN"',
        "Never commit tokens to git.",
    ]


def test_document_to_text_walks_fragments_and_unknown_blocks() -> None:
    doc = {
        "object": "document",
        "data": {},
        "nodes": [
            {
                "object": "block",
                "type": "tabs",
                "nodes": [
                    {
                        "object": "block",
                        "type": "tabs-item",
                        "fragments": [
                            {"object": "fragment", "nodes": [
                                {"object": "block", "type": "paragraph", "nodes": [
                                    {"object": "text", "leaves": [{"object": "leaf", "text": "Tab body", "marks": []}]}
                                ]}
                            ]}
                        ],
                        "nodes": [{"object": "text", "leaves": [{"object": "leaf", "text": "Tab title", "marks": []}]}],
                    }
                ],
            },
            {"object": "block", "type": "future-block", "nodes": [{"object": "leaf", "text": "Leaf only"}]},
            "not a node",
        ],
    }
    assert document_to_text(doc).split("\n") == ["Tab title", "Tab body", "Leaf only"]


def test_document_to_text_empty() -> None:
    assert document_to_text({"object": "document", "data": {}, "nodes": []}) == ""
    assert document_to_text({}) == ""


def test_markdown_to_text_fixture_page() -> None:
    md = load("page_markdown.json")["markdown"]
    assert markdown_to_text(md) == (
        "Authentication\n\n"
        "Send your token in the Authorization header. See tokens.\n\n"
        "export GITBOOK_TOKEN=gb_api_xxx\n\n"
        "Never commit tokens to git."
    )


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("## Title", "Title"),
        ("**bold** and __strong__", "bold and strong"),
        ("*em* and _em_ but snake_case_name", "em and em but snake_case_name"),
        ("~~old~~ new", "old new"),
        ("![diagram](https://x/d.png)", "diagram"),
        ("[docs][ref]", "docs"),
        ("> quoted", "quoted"),
        ("- one\n* two\n1. three\n- [x] done", "one\ntwo\nthree\ndone"),
        ("a\n\n---\n\nb", "a\n\nb"),
        ("<details><summary>More</summary>Hidden</details>", "MoreHidden"),
        ("<!-- note -->kept", "kept"),
        ("Fish &amp; chips&nbsp;now", "Fish & chips now"),
        ("| A | B |\n|---|---|\n| 1 | 2 |", "A B\n1 2"),
        ("line   with\ttabs", "line with tabs"),
        ("a\n\n\n\nb", "a\n\nb"),
    ],
)
def test_markdown_to_text_cases(source: str, expected: str) -> None:
    assert markdown_to_text(source) == expected


def test_make_snippet_short_text_unchanged() -> None:
    assert make_snippet("  short   text ", "x") == "short text"


def test_make_snippet_centers_on_match() -> None:
    text = " ".join(f"word{i}" for i in range(200)) + " needle " + " ".join(f"tail{i}" for i in range(200))
    snippet = make_snippet(text, "needle", 80)
    assert "needle" in snippet
    assert snippet.startswith("...") and snippet.endswith("...")
    assert len(snippet) <= 86


def test_make_snippet_prefers_phrase() -> None:
    text = "token " + "x " * 200 + "api token rotation " + "y " * 200
    assert "api token rotation" in make_snippet(text, "api token", 60)


def test_make_snippet_without_match_starts_at_beginning() -> None:
    text = "alpha " * 100
    snippet = make_snippet(text, "missing", 50)
    assert snippet.startswith("alpha")
    assert snippet.endswith("...")


def test_make_snippet_match_near_end() -> None:
    text = "a " * 300 + "the end marker"
    snippet = make_snippet(text, "marker", 40)
    assert snippet.endswith("marker")
    assert snippet.startswith("...")


def test_make_snippet_rejects_tiny_limit() -> None:
    with pytest.raises(ValueError):
        make_snippet("text", "q", 5)
