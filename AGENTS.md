# Agent Guide

This repo is a small Python workspace for a FastAPI/MCP server and a CocoIndex-based indexer.

## Working rules

- Make the smallest change that fixes the request.
- Prefer local, targeted edits over broad refactors.
- Check `README.md` first for setup and runtime context.
- Keep code style aligned with the existing files in `src/`, `scripts/`, and `tests/`.

## Validation

- Run `uv run pytest` for behavior changes.
- Run `uv run ruff check .` for lint-sensitive changes.
- If you touch database setup or server wiring, verify the affected path directly.

## Main entry points

- `src/` for application code.
- `tests/` for pytest coverage.
- `scripts/init_db.py` for database initialization.
