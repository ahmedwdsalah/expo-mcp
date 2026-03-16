# MCP V2.1 Change Log

## Scope

Non-breaking parallel upgrade.

- Keeps: `mcp_expo_server.py`, `mcp_expo_server_v2.py`
- Adds: `mcp_expo_server_v2_1.py`

## What changed from V2

1. Semantic-lite ranking
- Added tokenized query/document scoring.
- Added query coverage and token frequency weighting.
- Added proximity boost between matched query tokens.
- Added filename/title token boost.

2. Better matching behavior
- Search no longer depends only on full-phrase matching.
- Multi-token queries can match by token overlap (with minimum overlap threshold).

3. Ranking controls
- Added `rankingProfile` on `search_docs`:
  - `semantic_lite` (default)
  - `balanced`

4. Relevance cleanup
- Excluded `docs/public/static/data/*.json` from indexing to reduce generated-data noise.

5. Recall mode control
- Added `recallMode` on `search_docs`:
  - `high_precision` (default, excludes generated docs data JSON from results)
  - `high_recall` (includes generated docs data JSON and looser token threshold)

6. Version bump
- Server version updated to `2.1.0`.

## Validation

- Python compile check passed.
- JSON-RPC smoke checks passed for:
  - `initialize`
  - `search_docs` (default and `balanced`)
  - `get_stats`

## Current index snapshot

- Files discovered/indexed: `3080`
- Total indexed size: `21850954` bytes
