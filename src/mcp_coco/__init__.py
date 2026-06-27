"""CocoIndex MCP: incremental semantic indexing of repositories and documents.

The package is split into focused modules:

- ``config``   -- shared constants (DB URL, embedding model, table name, state path)
- ``formats``  -- the format-extractor registry
- ``sources``  -- the source seam (localfs ``repo``/``document`` profiles today)
- ``indexer``  -- the CocoIndex pipeline + ``index_repo`` / ``index_documents``
- ``db``       -- the search side (query embedding + pgvector similarity)
- ``server``   -- the FastMCP server exposing tools
- ``cli``      -- the ``just``-friendly command line entry point
"""

__all__ = ["__version__"]

__version__ = "0.1.0"
