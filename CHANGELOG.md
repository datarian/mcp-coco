# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Initial release: FastAPI/MCP server for semantic document and code retrieval using CocoIndex.
- `index_repo` and `index_documents` MCP tools.
- `search` and `read_search_results` MCP tools with two-stage search and cross-encoder re-ranking.
- HTTP API surface via `mcp-coco-api` entry point.
- CLI via `mcp-coco`.
- Docker-based pgvector development environment.
- Incremental indexing via CocoIndex LMDB state store.
- Support for code-aware chunking, vendored directory exclusion, PDF parsing (PyMuPDF).
- `sentence-transformers` based embedding with configurable model via `EMBED_MODEL`.
- `just` recipes for common workflows.
- Devcontainer configuration for reproducible development environments.
