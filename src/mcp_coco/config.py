"""Shared configuration constants, sourced from the environment.

Centralising these keeps the index side (``indexer``) and the search side
(``db``) in agreement about the database, embedding model, target table and
the CocoIndex state-store location.
"""

from __future__ import annotations

import os

try:  # Load a local .env when present; harmless if python-dotenv is absent.
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # pragma: no cover - dotenv is an optional convenience
    pass


# Postgres target (also read by the search side for similarity queries).
DATABASE_URL: str = os.environ.get(
    "DATABASE_URL", "postgresql://cocoindex:cocoindex@db:5432/cocoindex"
)

# Sentence-transformers model used for both indexing and query embedding.
# Both sides must use the same model so vectors share one space.
EMBED_MODEL: str = os.environ.get(
    "EMBED_MODEL", "sentence-transformers/all-MiniLM-L6-v2"
)
# Output dimension of EMBED_MODEL. Must match the model above.
EMBED_DIMS: int = int(os.environ.get("EMBED_DIMS", "384"))

# Single target table for both repos and documents.
TABLE_NAME: str = os.environ.get("COCO_TABLE_NAME", "doc_embeddings")

# CocoIndex's incremental state store (LMDB). MUST be a stable, persisted path:
# if it is ephemeral, every index run re-embeds everything from scratch.
STATE_DB_PATH: str = os.environ.get("COCOINDEX_DB", "/data/cocoindex/state.db")

# Cross-encoder model used to re-rank search results.
RERANK_MODEL: str = os.environ.get(
    "RERANK_MODEL", "cross-encoder/ms-marco-MiniLM-L-6-v2"
)

# Logical app-name prefix. The concrete app name also encodes the source so each
# indexed repo/document-set gets an isolated component tree + state namespace.
APP_NAME: str = "mcp_coco"
