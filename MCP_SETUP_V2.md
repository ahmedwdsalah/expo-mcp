# Expo Knowledge MCP Setup (V2)

This repo includes a new MCP server implementation at:

- `mcp_expo_server_v2.py`

The original server `mcp_expo_server.py` is unchanged.

## What is improved in V2

- Faster repeated searches via in-memory indexing and file-change aware refresh.
- Better result ordering using relevance scoring.
- Search modes: `both` (default), `path`, `content`.
- Safer scanning scope with common heavy/generated folders excluded.
- Stronger request validation and clearer errors.
- New diagnostics tool: `get_stats`.

## Exposed scope

- `docs/**`
- `packages/**`
- root: `README.md`, `CHANGELOG.md`, `package.json`

## Tools

- `list_docs`: List files with pagination and optional glob pattern
- `search_docs`: Search path/content with scoring and pagination
- `read_doc`: Chunked file reads (`offset` / `length`)
- `get_stats`: Index and corpus diagnostics
- `resources/list` and `resources/read`

## 1) Add to Codex config

Add this block to `~/.codex/config.toml`:

```toml
[mcp_servers.expo_v2]
command = "python3"
args = ["/Users/ahmed/Downloads/expo/mcp_expo_server_v2.py"]
```

If your config uses `servers` instead of `mcp_servers`, use:

```toml
[servers.expo_v2]
command = "python3"
args = ["/Users/ahmed/Downloads/expo/mcp_expo_server_v2.py"]
```

## 2) Restart your Codex session

Restart so MCP servers reload.

## 3) Recommended query patterns

- "Use `expo_v2.search_docs` for `router` with `searchMode=both` and paginate until `hasMore=false`."
- "Use `expo_v2.list_docs` with pattern `docs/pages/**/*.mdx`."
- "Use `expo_v2.read_doc` for `docs/pages/eas/ai/mcp.mdx` and chunk through the whole file."
- "Run `expo_v2.get_stats` to verify indexed corpus health."

## Notes

- Server is read-only.
- No write or shell execution capabilities are exposed.
- For large files over internal size cap, `read_doc` can still read directly by path.
