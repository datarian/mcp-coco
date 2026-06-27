"""Format-extractor registry: turn a source file into normalized text.

This is the seam that makes "PDF is just a special case" structurally true. A
*handler* maps a :class:`~cocoindex.resources.file.FileLike` to a stream of
:class:`Extracted` pieces (normalized text + a chunking-language hint + a
content type). Most formats yield a single piece; PDFs yield one per page
batch to cap peak memory. New formats are added by registering a handler for
one or more extensions -- nothing else in the pipeline changes.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Iterable
from dataclasses import dataclass
from typing import Callable

from cocoindex.ops.text import detect_code_language
from cocoindex.resources.file import FileLike


@dataclass(frozen=True)
class Extracted:
    """Normalized text extracted from a file, ready to chunk and embed."""

    text: str
    content_type: str  # "code" | "markdown" | "text" | "pdf" | ...
    chunk_language: str | None  # language hint for RecursiveSplitter (or None)
    base_char_offset: int = 0  # offset of this piece within the full document


Handler = Callable[[FileLike], AsyncIterator["Extracted"]]

_HANDLERS: dict[str, Handler] = {}
_CONTENT_TYPES: dict[str, str] = {}


def register(extensions: Iterable[str], handler: Handler, content_type: str) -> None:
    """Register ``handler`` for each extension (e.g. ``".py"``, case-insensitive)."""
    for ext in extensions:
        key = ext.lower()
        _HANDLERS[key] = handler
        _CONTENT_TYPES[key] = content_type


def extensions(content_types: set[str] | None = None) -> set[str]:
    """Return the registered extensions, optionally filtered by content type."""
    if content_types is None:
        return set(_HANDLERS)
    return {ext for ext, ct in _CONTENT_TYPES.items() if ct in content_types}


def handler_for(filename: str) -> Handler | None:
    """Return the handler for a filename based on its extension, or ``None``."""
    dot = filename.rfind(".")
    ext = filename[dot:].lower() if dot != -1 else ""
    return _HANDLERS.get(ext)


async def extract(file: FileLike) -> AsyncIterator[Extracted]:
    """Yield extracted text pieces from ``file``. Empty if unsupported."""
    handler = handler_for(file.file_path.name)
    if handler is None:
        return
    async for item in handler(file):
        yield item


# --- Built-in handlers ------------------------------------------------------

# Common source-code extensions. detect_code_language picks the syntax-aware
# splitter language; unrecognised ones fall back to generic splitting (None).
_CODE_EXTENSIONS = (
    ".py", ".pyi", ".js", ".jsx", ".ts", ".tsx", ".go", ".rs", ".java", ".kt",
    ".scala", ".c", ".h", ".cc", ".cpp", ".hpp", ".cs", ".rb", ".php", ".swift",
    ".sh", ".bash", ".zsh", ".sql", ".html", ".css", ".scss", ".vue", ".lua",
    ".r", ".jl", ".dart", ".ex", ".exs", ".clj", ".hs", ".ml", ".proto",
    ".yaml", ".yml", ".toml", ".json", ".xml", ".ini", ".cfg",
)


async def _extract_code(file: FileLike) -> AsyncIterator[Extracted]:
    text = await file.read_text()
    language = detect_code_language(filename=file.file_path.name)
    yield Extracted(text=text, content_type="code", chunk_language=language)


async def _extract_markdown(file: FileLike) -> AsyncIterator[Extracted]:
    text = await file.read_text()
    yield Extracted(text=text, content_type="markdown", chunk_language="markdown")


async def _extract_text(file: FileLike) -> AsyncIterator[Extracted]:
    text = await file.read_text()
    yield Extracted(text=text, content_type="text", chunk_language=None)


def _pdf_extract_page(path: str, page_num: int) -> str:
    """Extract text from a single PDF page using pymupdf directly.

    Avoids the pymupdf4llm layout engine which consumes significantly more
    memory per page.
    """
    import gc

    import pymupdf

    doc = pymupdf.open(path)
    try:
        page = doc[page_num]
        return page.get_text("text")
    finally:
        doc.close()
        gc.collect()


async def _extract_pdf(file: FileLike) -> AsyncIterator[Extracted]:
    import pymupdf

    path = str(file.file_path.path)
    doc = pymupdf.open(path)
    page_count = doc.page_count
    doc.close()

    char_offset = 0
    for page_num in range(page_count):
        text = await asyncio.to_thread(_pdf_extract_page, path, page_num)
        if not text.strip():
            continue
        yield Extracted(
            text=text,
            content_type="pdf",
            chunk_language=None,
            base_char_offset=char_offset,
        )
        char_offset += len(text)


register(_CODE_EXTENSIONS, _extract_code, content_type="code")
register((".md", ".mdx", ".markdown"), _extract_markdown, content_type="markdown")
register((".txt", ".text", ".rst", ".log"), _extract_text, content_type="text")
register((".pdf",), _extract_pdf, content_type="pdf")
