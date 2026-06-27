"""Source seam: where content to index comes from.

Today only the local filesystem is implemented, exposed as two *profiles*:

- ``repo``     -- code-oriented: code + markdown + text files, with vendored
  directories (``.git``, ``node_modules``, ``.venv`` ...) excluded.
- ``document`` -- prose-oriented: markdown + text + pdf files.

Both produce a CocoIndex ``localfs`` walker whose ``items()`` feed the shared
chunk -> embed -> store tail in :mod:`mcp_coco.indexer`. A future non-filesystem
source (Slack, Google Drive, S3, ...) would add another adapter that yields
keyed items into that same tail without touching the pipeline core.
"""

from __future__ import annotations

import pathlib

from cocoindex.connectors import localfs
from cocoindex.resources.file import PatternFilePathMatcher

from . import formats

SOURCE_KINDS = ("repo", "document")

# Directories that should never be indexed when walking a repository.
_REPO_EXCLUDES = [
    "**/.git/**", "**/.hg/**", "**/.svn/**",
    "**/node_modules/**", "**/bower_components/**",
    "**/.venv/**", "**/venv/**", "**/env/**",
    "**/__pycache__/**", "**/.mypy_cache/**", "**/.pytest_cache/**",
    "**/.ruff_cache/**", "**/.tox/**",
    "**/dist/**", "**/build/**", "**/.next/**", "**/target/**",
    "**/.idea/**", "**/.vscode/**",
]

# Lighter excludes for a document collection (still skip VCS metadata).
_DOC_EXCLUDES = ["**/.git/**", "**/.hg/**", "**/.svn/**"]

_PROFILES: dict[str, dict] = {
    "repo": {
        "content_types": {"code", "markdown", "text"},
        "excludes": _REPO_EXCLUDES,
    },
    "document": {
        "content_types": {"markdown", "text", "pdf"},
        "excludes": _DOC_EXCLUDES,
    },
}


def included_extensions(source_kind: str) -> set[str]:
    """Return the file extensions a given profile selects."""
    profile = _PROFILES[source_kind]
    return formats.extensions(profile["content_types"])


def walker_for(
    source_kind: str, root: pathlib.Path, *, only_file: str | None = None
) -> localfs.DirWalker:
    """Build a localfs walker for ``root`` using the profile's filters.

    When ``only_file`` is given, the walk is non-recursive and restricted to that
    single filename (used when the caller pointed at one file rather than a dir).
    """
    if source_kind not in _PROFILES:
        raise ValueError(
            f"Unknown source kind {source_kind!r}; expected one of {SOURCE_KINDS}"
        )
    profile = _PROFILES[source_kind]
    if only_file is not None:
        matcher = PatternFilePathMatcher(included_patterns=[only_file])
        return localfs.walk_dir(root, recursive=False, path_matcher=matcher)
    matcher = PatternFilePathMatcher(
        included_patterns=[f"**/*{ext}" for ext in sorted(included_extensions(source_kind))],
        excluded_patterns=profile["excludes"],
    )
    return localfs.walk_dir(root, recursive=True, path_matcher=matcher)
