"""Command-line entry point used by the ``justfile``.

Commands:
- ``index <path> [--kind auto|repo|document]`` -- index a repo or document set
- ``visualize``                                 -- render the indexed data
- ``search <query> [--limit N] [--kind ...]``   -- semantic search
- ``drop <path> [--kind ...]``                  -- remove a source from the index

Indexing emits DEBUG logs and a live progress display to the console.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import pathlib
import sys

from . import config


def _configure_logging(level: int = logging.DEBUG) -> None:
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)-7s %(name)s | %(message)s",
        datefmt="%H:%M:%S",
        stream=sys.stderr,
    )


def _normalize_kind(kind: str, path: str) -> str:
    """Map a user-supplied kind to 'repo' or 'document', auto-detecting if asked."""
    kind = kind.lower()
    if kind in ("repo", "repository"):
        return "repo"
    if kind in ("document", "documents", "doc", "docs"):
        return "document"
    if kind == "auto":
        target = pathlib.Path(path).expanduser()
        # A directory that looks like a git checkout is a repo; otherwise treat
        # it (and any single file) as a document collection.
        if target.is_dir() and (target / ".git").exists():
            return "repo"
        return "document"
    raise SystemExit(f"Unknown --kind {kind!r} (use auto, repo, or document)")


async def _cmd_index(args: argparse.Namespace) -> None:
    from . import indexer

    kind = _normalize_kind(args.kind, args.path)
    fn = indexer.index_repo if kind == "repo" else indexer.index_documents
    summary = await fn(args.path, progress=True)
    print(json.dumps(summary, indent=2))


async def _cmd_drop(args: argparse.Namespace) -> None:
    from . import indexer

    kind = _normalize_kind(args.kind, args.path)
    result = await indexer.drop_source(kind, args.path)
    print(json.dumps(result, indent=2))


async def _cmd_search(args: argparse.Namespace) -> None:
    from .db import close_pool, search_semantic

    try:
        results = await search_semantic(
            args.query, limit=args.limit, source_kind=args.kind
        )
    finally:
        await close_pool()

    if not results:
        print("No results (is anything indexed yet?).")
        return
    for i, r in enumerate(results, 1):
        print(f"{i:>2}. [{r['score']:.3f}] {r['source_kind']}:{r['location']} ({r['content_type']})")
        snippet = " ".join(r["snippet"].split())
        print(f"    {snippet}")


async def _cmd_visualize(_args: argparse.Namespace) -> None:
    import asyncpg
    from rich.console import Console
    from rich.table import Table
    from rich.tree import Tree

    from .db import close_pool, get_pool

    console = Console()
    pool = await get_pool()
    try:
        rows = await pool.fetch(
            f"""
            SELECT source_kind, source_id, content_type,
                   count(*) AS chunks,
                   count(DISTINCT location) AS files
            FROM {config.TABLE_NAME}
            GROUP BY source_kind, source_id, content_type
            ORDER BY source_kind, source_id, content_type
            """
        )
    except asyncpg.UndefinedTableError:
        rows = []
    finally:
        await close_pool()

    if not rows:
        console.print("[yellow]Nothing indexed yet.[/] Run [bold]just index <path>[/] first.")
        return

    # Group rows by (source_kind, source_id) for the tree.
    grouped: dict[tuple[str, str], list] = {}
    for row in rows:
        grouped.setdefault((row["source_kind"], row["source_id"]), []).append(row)

    tree = Tree(f"[bold]Indexed data[/] · postgres table [cyan]{config.TABLE_NAME}[/]")
    total_chunks = 0
    total_files = 0
    for (kind, source_id), entries in grouped.items():
        files = sum(e["files"] for e in entries)
        chunks = sum(e["chunks"] for e in entries)
        total_chunks += chunks
        total_files += files
        icon = "📦" if kind == "repo" else "📄"
        branch = tree.add(
            f"{icon} [bold]{kind}[/] {source_id}  "
            f"[dim]({chunks} chunks, {files} files)[/]"
        )
        for e in entries:
            branch.add(
                f"[green]{e['content_type']}[/]: {e['chunks']} chunks "
                f"[dim]({e['files']} files)[/]"
            )

    summary = Table(show_header=True, header_style="bold")
    summary.add_column("Sources")
    summary.add_column("Files", justify="right")
    summary.add_column("Chunks", justify="right")
    summary.add_row(str(len(grouped)), str(total_files), str(total_chunks))

    console.print(tree)
    console.print(summary)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="mcp-coco")
    sub = parser.add_subparsers(dest="command", required=True)

    p_index = sub.add_parser("index", help="Index a repo or document collection")
    p_index.add_argument("path")
    p_index.add_argument("--kind", default="auto", help="auto | repo | document")
    p_index.set_defaults(func=_cmd_index)

    p_viz = sub.add_parser("visualize", help="Show a visual map of indexed data")
    p_viz.set_defaults(func=_cmd_visualize)

    p_search = sub.add_parser("search", help="Semantic search over the index")
    p_search.add_argument("query")
    p_search.add_argument("--limit", type=int, default=10)
    p_search.add_argument("--kind", default=None, help="filter: repo | document")
    p_search.set_defaults(func=_cmd_search)

    p_drop = sub.add_parser("drop", help="Remove a source from the index")
    p_drop.add_argument("path")
    p_drop.add_argument("--kind", default="auto", help="auto | repo | document")
    p_drop.set_defaults(func=_cmd_drop)

    return parser


def main() -> None:
    _configure_logging()
    args = _build_parser().parse_args()
    asyncio.run(args.func(args))


if __name__ == "__main__":
    main()
