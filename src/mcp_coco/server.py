"""FastMCP server exposing the indexer and search as MCP tools."""

from __future__ import annotations

from contextlib import asynccontextmanager

from mcp.server.fastmcp import FastMCP

from .db import close_pool, search_semantic
from .indexer import index_documents, index_repo


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


@mcp.tool(
    "index_repo",
    title="Index Repository",
    description="Index a code repository (code-aware chunking, vendored dirs skipped).",
)
async def tool_index_repo(path: str) -> dict:
    return await index_repo(path)


@mcp.tool(
    "search",
    title="Search Index",
    description="Semantic search over indexed repos/documents. "
    "Optionally filter by source_kind ('repo' or 'document').",
)
async def tool_search(query: str, limit: int = 10, source_kind: str | None = None) -> dict:
    results = await search_semantic(query, limit=limit, source_kind=source_kind)
    return {"query": query, "count": len(results), "results": results}


def main() -> None:
    """Run the MCP server over stdio."""
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
