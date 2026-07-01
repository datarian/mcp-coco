"""The CocoIndex pipeline: source -> extract -> chunk -> embed -> store.

Two entry points, :func:`index_repo` and :func:`index_documents`, configure one
shared pipeline. Both walk a localfs source (see :mod:`mcp_coco.sources`), extract
text via the format registry (:mod:`mcp_coco.formats`), chunk it, embed each
chunk, and declare rows into a single ``doc_embeddings`` table. CocoIndex handles
incremental updates and automatic cleanup of rows whose source has changed.

Each indexed source is its own CocoIndex app (the app name encodes the source),
so their component trees and target ownership stay isolated even though they share
one table. Row primary keys are content-addressed UUIDs derived from
``(source_id, location, chunk position)``, keeping them globally unique and stable
across incremental runs.
"""

from __future__ import annotations

import logging
import pathlib
import uuid
import warnings

# cocoindex's SentenceTransformerEmbedder calls the deprecated
# get_sentence_embedding_dimension(); suppress until upstream fixes it.
warnings.filterwarnings(
    "ignore",
    message=r".*get_sentence_embedding_dimension",
    category=FutureWarning,
)
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Annotated

import asyncpg
import cocoindex as coco
from cocoindex.connectorkits.target import ManagedBy
from cocoindex.connectors import postgres
from cocoindex.ops.sentence_transformers import SentenceTransformerEmbedder
from cocoindex.ops.text import RecursiveSplitter
from cocoindex.resources.chunk import Chunk
from cocoindex.resources.file import FileLike
from cocoindex.resources.id import generate_uuid
from numpy.typing import NDArray

from . import config, formats, sources

log = logging.getLogger(__name__)

PG_DB = coco.ContextKey[asyncpg.Pool]("pg_db")
EMBEDDER = coco.ContextKey[SentenceTransformerEmbedder]("embedder")

_splitter = RecursiveSplitter()

# One chunking profile for now; prose and code both behave reasonably here.
CHUNK_SIZE = 1500
CHUNK_OVERLAP = 200


@dataclass
class DocEmbedding:
    """One embedded chunk -- a single row in the ``doc_embeddings`` table."""

    id: uuid.UUID
    source_kind: str  # "repo" | "document"
    source_id: str  # repo root / document-collection path (or "slack:#chan" later)
    location: str  # path within the source (or message permalink later)
    content_type: str  # "code" | "markdown" | "text" | "pdf" | ...
    chunk_start: int
    chunk_end: int
    text: str
    embedding: Annotated[NDArray, EMBEDDER]  # dimensions inferred from EMBEDDER


@coco.lifespan
async def coco_lifespan(builder: coco.EnvironmentBuilder) -> AsyncIterator[None]:
    """Provide the Postgres pool + embedder and pin the state-store location."""
    state_path = pathlib.Path(config.STATE_DB_PATH).expanduser()
    state_path.parent.mkdir(parents=True, exist_ok=True)
    builder.settings.db_path = state_path
    async with await asyncpg.create_pool(config.DATABASE_URL) as pool:
        async with pool.acquire() as conn:
            await conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
            await _ensure_table(conn)
        builder.provide(PG_DB, pool)
        builder.provide(EMBEDDER, SentenceTransformerEmbedder(config.EMBED_MODEL))
        yield


async def _ensure_table(conn: asyncpg.Connection) -> None:
    """Create the shared target table and its vector index if they don't exist yet.

    CocoIndex is told not to manage the table DDL (ManagedBy.USER), so this is
    the single place responsible for schema setup. Multiple apps sharing one table
    can safely run concurrently without 'relation already exists' errors.
    """
    await conn.execute(f"""
        CREATE TABLE IF NOT EXISTS {config.TABLE_NAME} (
            id          UUID    PRIMARY KEY,
            source_kind TEXT    NOT NULL,
            source_id   TEXT    NOT NULL,
            location    TEXT    NOT NULL,
            content_type TEXT   NOT NULL,
            chunk_start BIGINT  NOT NULL,
            chunk_end   BIGINT  NOT NULL,
            text        TEXT    NOT NULL,
            embedding   vector({config.EMBED_DIMS}) NOT NULL
        )
    """)
    await conn.execute(f"""
        CREATE INDEX IF NOT EXISTS {config.TABLE_NAME}__vector__embedding
        ON {config.TABLE_NAME} USING hnsw (embedding vector_cosine_ops)
    """)


@coco.fn
async def process_chunk(
    chunk: Chunk,
    *,
    source_kind: str,
    source_id: str,
    location: str,
    content_type: str,
    base_char_offset: int,
    table: postgres.TableTarget[DocEmbedding],
) -> None:
    """Embed one chunk and declare its row."""
    start = chunk.start.char_offset + base_char_offset
    end = chunk.end.char_offset + base_char_offset
    key = f"{source_id}\x00{location}\x00{start}\x00{end}"
    embedding = await coco.use_context(EMBEDDER).embed(chunk.text)
    table.declare_row(
        row=DocEmbedding(
            id=generate_uuid(key),
            source_kind=source_kind,
            source_id=source_id,
            location=location,
            content_type=content_type,
            chunk_start=start,
            chunk_end=end,
            text=chunk.text,
            embedding=embedding,
        )
    )


@coco.fn(memo=True)
async def process_file(
    file: FileLike,
    *,
    source_kind: str,
    source_id: str,
    table: postgres.TableTarget[DocEmbedding],
) -> None:
    """Extract, chunk and fan out one source file. Memoized on file content."""
    full_path = file.file_path.path
    try:
        location = full_path.relative_to(pathlib.Path(source_id)).as_posix()
    except ValueError:  # file outside the declared root (e.g. single-file index)
        location = file.file_path.name

    total_chunks = 0
    content_type = None
    async for extracted in formats.extract(file):
        if not extracted.text.strip():
            continue
        content_type = extracted.content_type
        chunks = _splitter.split(
            extracted.text,
            CHUNK_SIZE,
            chunk_overlap=CHUNK_OVERLAP,
            language=extracted.chunk_language,
        )
        total_chunks += len(chunks)
        await coco.map(
            process_chunk,
            chunks,
            source_kind=source_kind,
            source_id=source_id,
            location=location,
            content_type=extracted.content_type,
            base_char_offset=extracted.base_char_offset,
            table=table,
        )
    if total_chunks:
        log.debug("indexing %s (%s): %d chunk(s)", location, content_type, total_chunks)


@coco.fn
async def _app_main(
    source_kind: str, source_id: str, only_file: str | None = None
) -> None:
    """App body: declare the target table and mount one component per file."""
    table = await postgres.mount_table_target(
        PG_DB,
        config.TABLE_NAME,
        await postgres.TableSchema.from_class(DocEmbedding, primary_key=["id"]),
        managed_by=ManagedBy.USER,
    )

    walker = sources.walker_for(
        source_kind, pathlib.Path(source_id), only_file=only_file
    )
    await coco.mount_each(
        process_file,
        walker.items(),
        source_kind=source_kind,
        source_id=source_id,
        table=table,
    )


def _build_app(source_kind: str, root: str, only_file: str | None = None) -> coco.App:
    """Construct the per-source app (stable name = isolated state namespace)."""
    name = f"{config.APP_NAME}:{source_kind}:{root}"
    if only_file is not None:
        name = f"{name}:{only_file}"
    return coco.App(
        coco.AppConfig(name=name),
        _app_main,
        source_kind=source_kind,
        source_id=root,
        only_file=only_file,
    )


def _resolve(path: str) -> tuple[pathlib.Path, str | None]:
    """Resolve a path to a (walk_root, only_file) pair.

    A directory is walked recursively; a single file walks its parent restricted
    to that one filename.
    """
    target = pathlib.Path(path).expanduser().resolve()
    if target.is_dir():
        return target, None
    if target.is_file():
        return target.parent, target.name
    raise FileNotFoundError(f"Path does not exist: {target}")


def _summarize(source_kind: str, source_id: str, stats) -> dict:
    total = stats.total if stats is not None else None
    return {
        "source_kind": source_kind,
        "source_id": source_id,
        "chunks_added": total.num_adds if total else 0,
        "chunks_removed": total.num_deletes if total else 0,
        "chunks_reprocessed": total.num_reprocesses if total else 0,
        "chunks_unchanged": total.num_unchanged if total else 0,
        "errors": total.num_errors if total else 0,
    }


async def _index(source_kind: str, path: str, *, progress: bool = False) -> dict:
    root, only_file = _resolve(path)
    app = _build_app(source_kind, str(root), only_file=only_file)
    log.info("Indexing %s as %s", path, source_kind)
    async with coco.runtime():
        handle = app.update()
        if progress:
            await coco.show_progress(handle)
        else:
            await handle
        stats = handle.stats()
    summary = _summarize(source_kind, str(root), stats)
    log.info("Indexed %s: %s", path, summary)
    return summary


async def index_repo(path: str, *, progress: bool = False) -> dict:
    """Index a code repository (code-aware chunking, vendored dirs excluded)."""
    return await _index("repo", path, progress=progress)


async def index_documents(path: str, *, progress: bool = False) -> dict:
    """Index a document collection (markdown/text/pdf/..., prose chunking)."""
    return await _index("document", path, progress=progress)


async def drop_source(source_kind: str, path: str) -> dict:
    """Remove a previously indexed source: its rows and its CocoIndex state."""
    root, only_file = _resolve(path)
    app = _build_app(source_kind, str(root), only_file=only_file)
    async with coco.runtime():
        await app.drop()
    return {"dropped": f"{source_kind}:{root}"}
