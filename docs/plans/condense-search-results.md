# Plan: Condense search tool results via temp file + selective retrieval

## Context

The `search` MCP tool currently returns all results inline in the tool response. With the default limit of 10 results, each carrying a 280-char snippet plus metadata, this can be 7-12 KB dumped into the calling agent's context. Most of that content may not be relevant. The fix: return a condensed summary inline and let the caller selectively retrieve only the results it actually needs via a companion tool.

## Design

**Two-tool flow:**

1. `search` — runs the query, writes full results to a JSON temp file, returns a condensed summary (location + score + ~80-char excerpt per result) plus the temp file path.
2. `read_search_results` (new) — takes the temp file path + a list of result indices, reads the JSON file, returns only those entries with full ~1000-char snippets.

The caller triages from the condensed list, then fetches the 2-3 results it cares about — context stays lean.

**Temp file format:** JSON (not markdown) so `read_search_results` can reliably parse and extract by index. The tool formats its output nicely for the caller.

## Changes

### 1. `src/mcp_coco/db.py` — increase snippet to 1000 chars

Line 93: change `row["text"][:280]` → `row["text"][:1000]`. These longer snippets only appear in the temp file, not inline.

### 2. `src/mcp_coco/server.py` — modify `search`, add `read_search_results`

**Modify `tool_search`:**
- Call `search_semantic()` as before
- Write the full results list to a JSON temp file using `tempfile.NamedTemporaryFile(mode="w", suffix=".json", prefix="mcp_search_", delete=False)`
- Build a condensed results list: each entry has `index`, `source_id`, `location`, `content_type`, `score`, and `excerpt` (first ~80 chars of snippet)
- Return `{"query": ..., "count": ..., "results_file": <path>, "results": <condensed list>}`

**Add `read_search_results` tool:**
- Validates the file path exists and looks like one we created (prefix check)
- Returns `{"results": [<full entries at requested indices>]}`
- Raises a clear error if the file is missing or an index is out of range

### 3. Also fix: duplicate `index_repo` tool registration

Lines 25-49 in `server.py` register `index_repo` twice (exact duplicate). Remove the second registration (lines 43-49) while we're editing this file.

### 4. No new dependencies

Uses only `tempfile` and `json` from stdlib.

## Files modified

- **`src/mcp_coco/db.py`** — one-line change (snippet length 280 → 1000)
- **`src/mcp_coco/server.py`** — modify `tool_search`, add `tool_read_search_results`, remove duplicate `index_repo`
