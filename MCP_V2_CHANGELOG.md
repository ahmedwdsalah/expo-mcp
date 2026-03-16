# MCP V2 Change Log

## Scope

This is a non-breaking parallel implementation.

- Existing server kept intact: `mcp_expo_server.py`
- New server: `mcp_expo_server_v2.py`

## Fixed / Improved

1. Search efficiency
- Added in-memory text index (`IndexedDoc`) to avoid full file reads on repeated queries.
- Added file metadata checks (`mtime_ns`, `size`) to refresh only changed docs.

2. Search quality
- Added relevance scoring with path/content weighting.
- Added deterministic sort by score then path position.
- Added `searchMode` (`both`, `path`, `content`).

3. Stability and safety
- Added query length guard (`MAX_QUERY_LENGTH`).
- Added validation for tool arguments object shape.
- Kept strict path scope enforcement for `read_doc` and `resources/read`.

4. Corpus control
- Added ignored directory names for non-knowledge folders.
- Added max indexed file size cap to protect memory from giant files.

5. Operational visibility
- Added `get_stats` tool for index and corpus health metrics.

## Compatibility

- Existing tools remain available: `list_docs`, `search_docs`, `read_doc`, `resources/list`, `resources/read`.
- V2 adds `get_stats` and optional `searchMode` for `search_docs`.

## Validation Performed

- Python syntax check (`py_compile`) passed.
- MCP JSON-RPC smoke flow passed for:
  - `initialize`
  - `tools/list`
  - `tools/call` with `search_docs`
  - `tools/call` with `get_stats`

## Benchmark Snapshot (local)

Same-process 3-search run (lower is better):

- `mcp_expo_server.py`: `real 0.63s`
- `mcp_expo_server_v2.py`: `real 0.55s`

Note: cold starts can vary because process startup cost dominates short runs.
