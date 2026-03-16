# Expo Knowledge MCP Setup

This repo now includes a local MCP server at:

- `mcp_expo_server.py`

It exposes Expo knowledge from:

- `docs/**`
- `packages/**`
- root: `README.md`, `CHANGELOG.md`, `package.json`

## Tools

- `list_docs`: List files with pagination and optional glob pattern
- `search_docs`: Search path + content with pagination
- `read_doc`: Chunked file reads (`offset` / `length`)
- `resources/list` and `resources/read`

## 1) Add to Codex config

Add this block to `~/.codex/config.toml`:

```toml
[mcp_servers.expo]
command = "python3"
args = ["/Users/ahmed/Downloads/expo/mcp_expo_server.py"]
```

If your config uses `servers` instead of `mcp_servers`, use:

```toml
[servers.expo]
command = "python3"
args = ["/Users/ahmed/Downloads/expo/mcp_expo_server.py"]
```

## 2) Restart Codex session

Restart the session so MCP servers reload.

## 3) Query patterns to use

- "Use `expo.search_docs` for `router` and paginate until `hasMore=false`."
- "Use `expo.list_docs` with pattern `docs/pages/**/*.mdx`."
- "Use `expo.read_doc` for `docs/pages/eas/ai/mcp.mdx` and read chunks until full file is consumed."

## Notes

- Server is read-only.
- Server only serves files from this repo scope.
