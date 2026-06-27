# cocoindex MCP — task runner (https://github.com/casey/just)
# Run `just` with no args to list recipes.

set dotenv-load := true

export HF_HUB_OFFLINE := "1"

# Show available recipes
default:
    @just --list

# Install dependencies into the project venv
install:
    uv sync

# Preflight: check the database is reachable and pgvector is available
init:
    uv run python scripts/init_db.py

# Index a path; auto-detects repo vs document. Prints debug logs to the console.
# Usage: just index ./some/path            (auto)
#        just index ./some/path repo        (force repo profile)
#        just index ./docs document         (force document profile)
index path kind="auto":
    uv run python -m mcp_coco.cli index "{{path}}" --kind {{kind}}

# Index a path explicitly as a code repository
index-repo path:
    uv run python -m mcp_coco.cli index "{{path}}" --kind repo

# Index a path explicitly as a document collection
index-docs path:
    uv run python -m mcp_coco.cli index "{{path}}" --kind document

# Show a visual representation of the indexed data
visualize_index:
    uv run python -m mcp_coco.cli visualize

# Semantic search over the index. Usage: just search "how does auth work" 5
search query limit="10":
    uv run python -m mcp_coco.cli search "{{query}}" --limit {{limit}}

# Remove a previously indexed source (rows + CocoIndex state)
drop path kind="auto":
    uv run python -m mcp_coco.cli drop "{{path}}" --kind {{kind}}

# Run the MCP server over stdio
serve:
    uv run python -m mcp_coco.server

# Run the test suite
test:
    uv run pytest

# Lint
lint:
    uv run ruff check .
