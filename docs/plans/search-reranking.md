# Plan: Add cross-encoder re-ranking to `read_search_results`

## Context

We just implemented a two-tool search flow: `search` returns condensed summaries and writes full results to a temp JSON file; `read_search_results` retrieves specific results by index. Currently `read_search_results` returns results in their original vector-similarity order. Adding a cross-encoder re-ranker would score each selected result against the original query with a more accurate (but slower) model, improving result quality when the caller retrieves multiple results.

Cross-encoders are the standard second stage in a retrieve-then-rerank pipeline. The bi-encoder (vector search) is fast but approximate; the cross-encoder jointly attends to query + passage and produces a more accurate relevance score.

## Design

- Add a `rerank` boolean parameter (default `True`) to `read_search_results`
- When enabled, use `sentence_transformers.CrossEncoder` to score each selected result's snippet against the original query
- Re-sort by cross-encoder score descending, and include the new score in the output
- Lazy-load the cross-encoder model using `@functools.cache` (avoids module-level `global` state)
- Make the model name configurable via `config.py` (env var `RERANK_MODEL`)

## Changes

### 1. `src/mcp_coco/config.py` — add rerank model config

Add one new constant:
```python
RERANK_MODEL: str = os.environ.get(
    "RERANK_MODEL", "cross-encoder/ms-marco-MiniLM-L-6-v2"
)
```

This is a small (~80 MB), fast cross-encoder widely used for re-ranking. Same `sentence-transformers` package — no new dependency.

### 2. `src/mcp_coco/db.py` — add `rerank_results` function

Add a `@functools.cache`-based lazy loader for the `CrossEncoder` and a `rerank_results` function:

```python
@functools.cache
def _get_reranker():
    from sentence_transformers import CrossEncoder
    return CrossEncoder(config.RERANK_MODEL)

def rerank_results(query: str, results: list[dict]) -> list[dict]:
    reranker = _get_reranker()
    pairs = [[query, r["snippet"]] for r in results]
    scores = reranker.predict(pairs).tolist()
    for r, s in zip(results, scores):
        r["rerank_score"] = round(float(s), 4)
    return sorted(results, key=lambda r: r["rerank_score"], reverse=True)
```

### 3. `src/mcp_coco/server.py` — wire reranking into `read_search_results`

- Import `rerank_results` from `.db`
- Add `rerank: bool = True` parameter to `tool_read_search_results`
- After selecting results by index, call `rerank_results(query, selected)` when `rerank` is True and more than one result is selected
- Update the tool description to mention re-ranking behavior

## Files modified

- **`src/mcp_coco/config.py`** — add `RERANK_MODEL` constant
- **`src/mcp_coco/db.py`** — add `_get_reranker()` and `rerank_results()`
- **`src/mcp_coco/server.py`** — add `rerank` param to `read_search_results`, call `rerank_results`
