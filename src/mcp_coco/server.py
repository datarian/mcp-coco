"""FastMCP server exposing the indexer and search as MCP tools."""

from __future__ import annotations

import json
import tempfile
from contextlib import asynccontextmanager
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from .db import close_pool, search_semantic
from .indexer import index_documents, index_repo

_EXCERPT_LEN = 80
_TEMP_PREFIX = "mcp_search_"


@asynccontextmanager
async def lifespan(_server):
    # CocoIndex creates and manages the target schema; nothing to set up here.
    try:
        yield
    finally:
        await close_pool()


mcp = FastMCP("cocoindex", lifespan=lifespan)


@mcp.tool(
    "index_repo",
    title="Index Repository",
    description="Index a code repository (code-aware chunking, vendored dirs skipped).",
)
async def tool_index_repo(path: str) -> dict:
    return await index_repo(path)


@mcp.tool(
    "index_documents",
    title="Index Documents",
    description="Index a document collection (markdown, text, PDF, ...).",
)
async def tool_index_documents(path: str) -> dict:
    return await index_documents(path)


def _write_results_file(query: str, results: list[dict]) -> str:
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", prefix=_TEMP_PREFIX, delete=False
    ) as f:
        json.dump({"query": query, "results": results}, f)
        return f.name


def _condense(results: list[dict]) -> list[dict]:
    return [
        {
            "index": i,
            "source_id": r["source_id"],
            "location": r["location"],
            "content_type": r["content_type"],
            "score": r["score"],
            "excerpt": r["snippet"][:_EXCERPT_LEN],
        }
        for i, r in enumerate(results)
    ]


@mcp.tool(
    "search",
    title="Search Index",
    description="Semantic search over indexed repos/documents. "
    "Returns a condensed summary per result; use read_search_results "
    "with the returned results_file to retrieve full details for "
    "specific results. "
    "Optionally filter by source_kind ('repo' or 'document').",
)
async def tool_search(query: str, limit: int = 10, source_kind: str | None = None) -> dict:
    results = await search_semantic(query, limit=limit, source_kind=source_kind)
    results_file = _write_results_file(query, results) if results else None
    return {
        "query": query,
        "count": len(results),
        "results_file": results_file,
        "results": _condense(results),
    }


@mcp.tool(
    "read_search_results",
    title="Read Search Results",
    description="Retrieve full details for specific results from a previous search. "
    "Pass the results_file path from a search response and a list of "
    "result indices (0-based) to fetch.",
)
async def tool_read_search_results(results_file: str, indices: list[int]) -> dict:
    path = Path(results_file)
    if not path.name.startswith(_TEMP_PREFIX) or not path.is_file():
        return {"error": f"Invalid or missing results file: {results_file}"}

    data = json.loads(path.read_text())
    all_results = data["results"]

    selected = []
    for idx in indices:
        if 0 <= idx < len(all_results):
            selected.append(all_results[idx])
        else:
            return {"error": f"Index {idx} out of range (0-{len(all_results) - 1})"}

    return {"query": data["query"], "results": selected}


def main() -> None:
    """Run the MCP server over stdio."""
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
