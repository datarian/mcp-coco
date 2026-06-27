# cocoindex MCP

An MCP server that incrementally indexes **repositories** and **documents** into a
Postgres + pgvector store using [CocoIndex](https://cocoindex.io), and exposes
semantic search over them.

The pipeline is `source → extract (format registry) → chunk → embed → store`:

- **Sources** (`src/mcp_coco/sources.py`) — local filesystem today, as two profiles:
  `repo` (code-aware, vendored dirs excluded) and `document` (markdown/text/pdf,
  prose chunking).
- **Formats** (`src/mcp_coco/formats.py`) — a registry mapping a file to normalized
  text. PDF (via `pymupdf`) is just one handler; add a format by registering one.
- **Indexer** (`src/mcp_coco/indexer.py`) — the CocoIndex app: chunk + embed
  (`sentence-transformers`) and declare rows into one `doc_embeddings` table.
- **Search** (`src/mcp_coco/db.py`) — embeds the query and runs a pgvector
  similarity search.

CocoIndex tracks its incremental state in a local LMDB file (`COCOINDEX_DB`), so
re-indexing only reprocesses what changed and removes rows for deleted files.

## Prerequisites

- [uv](https://docs.astral.sh/uv/) (Python package manager)
- [just](https://github.com/casey/just) (task runner, optional but convenient)
- A Postgres instance with [pgvector](https://github.com/pgvector/pgvector)
- [Docker](https://www.docker.com/) (if you want to run pgvector via the included compose file)

## Quick start (local)

### 1. Start a pgvector database

If you already have a Postgres instance with pgvector, skip this step and set
`DATABASE_URL` accordingly.

Otherwise, use the included compose file:

```bash
docker compose up -d
```

This starts pgvector on `localhost:5432` with user/password/db all set to `cocoindex`.

### 2. Install dependencies

```bash
uv sync
```

### 3. Configure

```bash
cp .env.example .env
```

Edit `.env` and set `DATABASE_URL` to point at your Postgres instance. For the
Docker-based database:

```
DATABASE_URL=postgresql://cocoindex:cocoindex@localhost:5432/cocoindex
```

Optional settings:

| Variable | Default | Description |
|---|---|---|
| `EMBED_MODEL` | `sentence-transformers/all-MiniLM-L6-v2` | Embedding model for indexing and search |
| `RERANK_MODEL` | `cross-encoder/ms-marco-MiniLM-L-6-v2` | Cross-encoder model for result re-ranking |
| `COCO_TABLE_NAME` | `doc_embeddings` | Postgres table name |
| `COCOINDEX_DB` | `/data/cocoindex/state.db` | Path to CocoIndex incremental state store |

### 4. Verify the database connection

```bash
just init
```

### 5. Index something

```bash
just index ./path/to/repo repo
just index ./path/to/docs document
```

The first run downloads the embedding model (~80 MB) from Hugging Face.

### 6. Search

```bash
just search "how does authentication work"
```

## Using with Coding Agents

Add the MCP server to your Claude Code settings
(`~/.claude/settings.json` for global, or `.claude/settings.json` in a project):

```json
{
  "mcpServers": {
    "cocoindex": {
      "command": "uv",
      "args": ["run", "--directory", "/absolute/path/to/cocoindex-mcp", "mcp-coco-server"],
      "env": {
        "DATABASE_URL": "postgresql://cocoindex:cocoindex@localhost:5432/cocoindex",
        "COCOINDEX_DB": "/absolute/path/to/cocoindex-mcp/.cocoindex/state.db"
      }
    }
  }
}
```

Replace `/absolute/path/to/cocoindex-mcp` with the actual path to this repository.

If your Postgres instance is elsewhere (e.g. a cloud-hosted database), adjust
`DATABASE_URL` accordingly. It is highly encouraged to pass your authentication information through env vars, do NOT hardcode into the connection string!

Once configured, Claude Code can use these tools:

| Tool | Description |
|---|---|
| `index_repo(path)` | Index a code repository |
| `index_documents(path)` | Index a document collection |
| `search(query, limit, source_kind)` | Semantic search — returns condensed summaries and a `results_file` path |
| `read_search_results(results_file, indices, rerank)` | Retrieve full details for specific results from a previous search |

### Two-stage search

To keep context lean, `search` writes full results to a temporary JSON file
and returns only condensed summaries (~80-char excerpts) inline. The caller
triages from the summary, then uses `read_search_results` to fetch full
details for the results it actually needs.

By default, `read_search_results` re-ranks the selected results using a
cross-encoder model (`cross-encoder/ms-marco-MiniLM-L-6-v2`) for more
accurate relevance ordering. Disable with `rerank=false`. The model is
configurable via the `RERANK_MODEL` environment variable.

## Development (devcontainer)

1. Open this folder in VS Code and **Reopen in Container** (Dev Containers).
   The `db` service starts automatically alongside the app container.
2. Run the preflight check:

   ```bash
   just install
   just init
   ```

   Copy `.env.example` to `.env` to customize settings. Inside the devcontainer
   the database hostname is `db` (the default).

## `just` recipes

```
just index <path> [repo|document|auto]   # index a path
just index-repo <path>                   # index as code repository
just index-docs <path>                   # index as document collection
just search "query" [limit]              # semantic search
just drop <path> [repo|document|auto]    # remove a source from the index
just visualize_index                     # show a map of what's indexed
just serve                               # run the MCP server over stdio
just test                                # run tests
just lint                                # run ruff
```
