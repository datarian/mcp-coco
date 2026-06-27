"""Model-free tests for the format registry and source profiles.

These intentionally avoid the database, the embedding model and PDF parsing so
the suite runs fast and offline. The pipeline wiring itself is exercised via
integration runs (``just index``).
"""

from dataclasses import dataclass

import pytest

from mcp_coco import formats, sources


@dataclass
class _FakeFilePath:
    name: str


class _FakeFile:
    """Minimal duck-typed stand-in for cocoindex's FileLike (text only)."""

    def __init__(self, name: str, text: str) -> None:
        self._file_path = _FakeFilePath(name)
        self._text = text

    @property
    def file_path(self) -> _FakeFilePath:
        return self._file_path

    async def read_text(self) -> str:
        return self._text


def test_handler_routing_by_extension() -> None:
    assert formats.handler_for("main.py") is not None
    assert formats.handler_for("README.md") is not None
    assert formats.handler_for("notes.txt") is not None
    assert formats.handler_for("paper.pdf") is not None
    assert formats.handler_for("photo.png") is None
    assert formats.handler_for("Makefile") is None


def test_handler_routing_is_case_insensitive() -> None:
    assert formats.handler_for("REPORT.PDF") is not None
    assert formats.handler_for("Main.PY") is not None


async def _collect(file):
    return [e async for e in formats.extract(file)]


@pytest.mark.asyncio
async def test_extract_code() -> None:
    result = await _collect(_FakeFile("main.py", "print('hi')\n"))
    assert len(result) == 1
    extracted = result[0]
    assert extracted.content_type == "code"
    assert extracted.chunk_language == "python"
    assert "print" in extracted.text


@pytest.mark.asyncio
async def test_extract_markdown_and_text() -> None:
    md = await _collect(_FakeFile("README.md", "# Title\n"))
    assert len(md) == 1 and md[0].content_type == "markdown"
    assert md[0].chunk_language == "markdown"

    txt = await _collect(_FakeFile("notes.txt", "plain"))
    assert len(txt) == 1 and txt[0].content_type == "text"
    assert txt[0].chunk_language is None


@pytest.mark.asyncio
async def test_extract_unsupported_returns_none() -> None:
    result = await _collect(_FakeFile("photo.png", ""))
    assert result == []


def test_source_profiles_select_expected_extensions() -> None:
    repo_exts = sources.included_extensions("repo")
    doc_exts = sources.included_extensions("document")

    # Repos are code-oriented; documents are prose-oriented.
    assert ".py" in repo_exts
    assert ".py" not in doc_exts
    assert ".pdf" in doc_exts
    assert ".pdf" not in repo_exts

    # Markdown is shared by both profiles.
    assert ".md" in repo_exts
    assert ".md" in doc_exts


def test_walker_for_rejects_unknown_kind() -> None:
    import pathlib

    with pytest.raises(ValueError):
        sources.walker_for("bogus", pathlib.Path("."))
