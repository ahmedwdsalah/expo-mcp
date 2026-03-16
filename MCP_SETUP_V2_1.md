# Expo Knowledge MCP Setup (V2.1)

This repo includes a semantic-ranking MCP server at:

- `mcp_expo_server_v2_1.py`

`v1` and `v2` remain unchanged.

## Highlights in V2.1

- Semantic-lite relevance ranking for natural language queries.
- Token-aware matching (not only exact phrase matching).
- Proximity/coverage boosts for better query intent alignment.
- Optional ranking profiles:
  - `semantic_lite` (default)
  - `balanced`
- Query-time recall control via `recallMode`:
  - `high_precision` (default, cleaner)
  - `high_recall` (wider)

## Tools

- `list_docs`
- `search_docs` (`searchMode`, `rankingProfile`, `recallMode`)
- `read_doc`
- `get_stats`
- `resources/list`, `resources/read`

## Codex config

Add to `~/.codex/config.toml`:

```toml
[mcp_servers.expo_v2_1]
command = "python3"
args = ["/Users/ahmed/Downloads/expo/mcp_expo_server_v2_1.py"]
```

If your config uses `servers`:

```toml
[servers.expo_v2_1]
command = "python3"
args = ["/Users/ahmed/Downloads/expo/mcp_expo_server_v2_1.py"]
```

Restart your Codex session after updating config.

## Recommended usage

- `expo_v2_1.search_docs` with `rankingProfile="semantic_lite", recallMode="high_precision"` for cleaner intent-heavy queries.
- `expo_v2_1.search_docs` with `rankingProfile="balanced", recallMode="high_recall"` for wider discovery.
- Use `searchMode="path"` when you want file discovery only.
