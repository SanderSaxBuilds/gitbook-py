"""Turn GitBook content into plain text.

GitBook returns page content either as Markdown (``format="markdown"``) or
as a JSON block tree (``format="document"``). Both helpers here produce
plain text with no markup, which is what a search index or a language model
prompt usually wants.
"""

from __future__ import annotations

import re
from typing import Any, Iterable, List, Mapping

__all__ = ["document_to_text", "make_snippet", "markdown_to_text"]

# Block types whose children read as separate lines.
_LINE_BLOCKS = frozenset(
    {
        "paragraph",
        "heading-1",
        "heading-2",
        "heading-3",
        "list-item",
        "code-line",
        "blockquote",
        "hint",
        "table-row",
        "math",
    }
)


def document_to_text(document: Mapping[str, Any]) -> str:
    """Extract the readable text of a GitBook JSON document.

    Walks ``nodes`` and ``fragments`` recursively and joins text leaves,
    putting each paragraph, heading, list item and code line on its own
    line. Unknown block types are walked the same way, so new block kinds
    still give their text.
    """
    lines: List[str] = []
    current: List[str] = []

    def flush() -> None:
        text = "".join(current).strip()
        if text:
            lines.append(text)
        current.clear()

    def walk(node: Any) -> None:
        if isinstance(node, list):
            for child in node:
                walk(child)
            return
        if not isinstance(node, Mapping):
            return
        kind = node.get("object")
        if kind == "text":
            for leaf in node.get("leaves") or []:
                if isinstance(leaf, Mapping) and isinstance(leaf.get("text"), str):
                    current.append(leaf["text"])
            return
        if kind == "leaf" and isinstance(node.get("text"), str):
            current.append(node["text"])
            return
        if kind == "inline":
            walk(node.get("nodes"))
            return
        block = kind == "block"
        if block:
            flush()
        walk(node.get("nodes"))
        walk(node.get("fragments"))
        if block and (node.get("type") in _LINE_BLOCKS or current):
            flush()

    walk(document.get("nodes"))
    flush()
    return "\n".join(lines)


_FENCE = re.compile(r"^[ \t]*(```|~~~).*$", re.MULTILINE)
_LIQUID = re.compile(r"\{%.*?%\}", re.DOTALL)
_HTML_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)
_HTML_TAG = re.compile(r"</?[A-Za-z][^>]*>")
_IMAGE = re.compile(r"!\[([^\]]*)\]\([^)]*\)")
_LINK = re.compile(r"\[([^\]]+)\]\([^)]*\)")
_REF_LINK = re.compile(r"\[([^\]]+)\]\[[^\]]*\]")
_HEADING = re.compile(r"^[ \t]{0,3}#{1,6}[ \t]+", re.MULTILINE)
_QUOTE = re.compile(r"^[ \t]{0,3}>[ \t]?", re.MULTILINE)
_BULLET = re.compile(r"^[ \t]*(?:[-*+]|\d+[.)])[ \t]+(?:\[[ xX]\][ \t]+)?", re.MULTILINE)
_RULE = re.compile(r"^[ \t]*(?:-{3,}|\*{3,}|_{3,})[ \t]*$", re.MULTILINE)
_TABLE_SEP = re.compile(
    r"^[ \t]*\|?[ \t]*:?-{2,}:?[ \t]*(?:\|[ \t]*:?-{2,}:?[ \t]*)*\|?[ \t]*(?:\n|$)", re.MULTILINE
)
_BOLD = re.compile(r"(\*\*|__)(?=\S)(.+?)(?<=\S)\1")
_ITALIC = re.compile(r"(?<![\w*])([*_])(?=\S)(.+?)(?<=\S)\1(?![\w*])")
_STRIKE = re.compile(r"~~(.+?)~~")
_CODE = re.compile(r"`([^`]*)`")
_ENTITIES = {"&nbsp;": " ", "&amp;": "&", "&lt;": "<", "&gt;": ">", "&quot;": '"', "&#39;": "'"}


def markdown_to_text(markdown: str) -> str:
    """Strip Markdown, HTML and GitBook ``{% %}`` tags, keeping the words.

    Link and image text is kept, URLs are dropped, code keeps its content,
    and blank lines collapse to one.
    """
    text = markdown.replace("\r\n", "\n")
    text = _HTML_COMMENT.sub("", text)
    text = _LIQUID.sub("", text)
    text = _FENCE.sub("", text)
    text = _IMAGE.sub(r"\1", text)
    text = _LINK.sub(r"\1", text)
    text = _REF_LINK.sub(r"\1", text)
    text = _HTML_TAG.sub("", text)
    text = _TABLE_SEP.sub("", text)
    text = _RULE.sub("", text)
    text = _HEADING.sub("", text)
    text = _QUOTE.sub("", text)
    text = _BULLET.sub("", text)
    text = _BOLD.sub(r"\2", text)
    text = _STRIKE.sub(r"\1", text)
    text = _ITALIC.sub(r"\2", text)
    text = _CODE.sub(r"\1", text)
    for entity, char in _ENTITIES.items():
        text = text.replace(entity, char)
    out_lines: List[str] = []
    for line in text.split("\n"):
        line = line.strip()
        if line.startswith("|") or line.endswith("|"):
            line = " ".join(cell.strip() for cell in line.strip("|").split("|") if cell.strip())
        line = re.sub(r"[ \t]+", " ", line)
        if line or (out_lines and out_lines[-1]):
            out_lines.append(line)
    return "\n".join(out_lines).strip()


def _terms(query: str) -> List[str]:
    words = [w for w in re.split(r"\W+", query.lower()) if len(w) > 1]
    phrase = query.strip().lower()
    ordered: Iterable[str] = ([phrase] if phrase and " " in phrase else []) + sorted(
        set(words), key=len, reverse=True
    )
    return [t for t in ordered if t]


def make_snippet(text: str, query: str = "", max_chars: int = 320) -> str:
    """Cut ``text`` to about ``max_chars`` around the first match of ``query``.

    Whitespace is collapsed to single spaces. The cut lands on word
    boundaries and ``...`` marks text left out at either end. Without a
    match the snippet starts at the beginning.
    """
    if max_chars < 20:
        raise ValueError("max_chars must be at least 20")
    flat = re.sub(r"\s+", " ", text).strip()
    if len(flat) <= max_chars:
        return flat
    lower = flat.lower()
    hit = -1
    for term in _terms(query):
        hit = lower.find(term)
        if hit >= 0:
            break
    start = 0 if hit < 0 else max(0, hit - max_chars // 3)
    end = min(len(flat), start + max_chars)
    start = max(0, end - max_chars)
    if start > 0:
        space = flat.find(" ", start)
        if 0 <= space < start + 30:
            start = space + 1
    if end < len(flat):
        space = flat.rfind(" ", start, end)
        if space > start + max_chars // 2:
            end = space
    snippet = flat[start:end].strip()
    if start > 0:
        snippet = "..." + snippet
    if end < len(flat):
        snippet = snippet.rstrip(",.;:") + "..."
    return snippet
