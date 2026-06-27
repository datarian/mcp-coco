"""Search side: embed a query and run a pgvector similarity search.

This is deliberately separate from the index pipeline. CocoIndex owns the write
path (it created and maintains ``doc_embeddings``); here we only read. The query
is embedded with the same model used at index time -- but via a plain
``SentenceTransformer`` rather than the CocoIndex embedder, since query-time
embedding happens outside any pipeline/runtime.
"""

from __future__ import annotations

import functools
from typing import Any

import asyncpg

from . import config

_pool: asyncpg.Pool | None = None
_model: Any = None  # lazily-loaded SentenceTransformer


async def get_pool() -> asyncpg.Pool:
    """Return a lazily-created connection pool for the search side."""
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(config.DATABASE_URL)
    return _pool


async def close_pool() -> None:
    """Close the search-side connection pool."""
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


def _get_model() -> Any:
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer

        _model = SentenceTransformer(config.EMBED_MODEL)
    return _model


def _embed_query(query: str) -> str:
    """Embed the query and format it as a pgvector literal (``[v1,v2,...]``)."""
    vector = _get_model().encode(
        query, normalize_embeddings=True, convert_to_numpy=True
    )
    return "[" + ",".join(f"{x:.8f}" for x in vector.tolist()) + "]"


async def search_semantic(
    query: str, limit: int = 10, source_kind: str | None = None
) -> list[dict]:
    """Return the ``limit`` chunks most similar to ``query`` (cosine similarity).

    Optionally restrict to a ``source_kind`` ("repo" or "document"). Returns an
    empty list if nothing has been indexed yet.
    """
    query_vec = _embed_query(query)
    pool = await get_pool()

    args: list[Any] = [query_vec, limit]
    where = ""
    if source_kind:
        args.append(source_kind)
        where = "WHERE source_kind = $3"

    sql = f"""
        SELECT source_kind, source_id, location, content_type, text,
               1 - (embedding <=> $1::vector) AS score
        FROM {config.TABLE_NAME}
        {where}
        ORDER BY embedding <=> $1::vector
        LIMIT $2
    """

    try:
        rows = await pool.fetch(sql, *args)
    except asyncpg.UndefinedTableError:
        return []  # nothing indexed yet

    return [
        {
            "source_kind": row["source_kind"],
            "source_id": row["source_id"],
            "location": row["location"],
            "content_type": row["content_type"],
            "score": round(float(row["score"]), 4),
            "snippet": row["text"][:1000],
        }
        for row in rows
    ]


@functools.cache
def _get_reranker() -> Any:
    from sentence_transformers import CrossEncoder

    return CrossEncoder(config.RERANK_MODEL)


def rerank_results(query: str, results: list[dict]) -> list[dict]:
    reranker = _get_reranker()
    pairs = [[query, r["snippet"]] for r in results]
    scores = reranker.predict(pairs).tolist()
    for r, s in zip(results, scores):
        r["rerank_score"] = round(float(s), 4)
    return sorted(results, key=lambda r: r["rerank_score"], reverse=True)
