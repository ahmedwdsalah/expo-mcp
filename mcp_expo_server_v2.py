#!/usr/bin/env python3
import hashlib
import json
import re
import sys
from dataclasses import dataclass
from fnmatch import fnmatch
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parent
SEARCH_DIRS = [ROOT / "docs", ROOT / "packages"]
ROOT_INCLUDE_FILES = {
    ROOT / "README.md",
    ROOT / "CHANGELOG.md",
    ROOT / "package.json",
}

TEXT_EXTENSIONS = {
    ".md",
    ".mdx",
    ".txt",
    ".json",
    ".ts",
    ".tsx",
    ".js",
    ".jsx",
    ".d.ts",
    ".yml",
    ".yaml",
}

IGNORED_DIR_NAMES = {
    ".git",
    ".github",
    ".vscode",
    "node_modules",
    "build",
    "dist",
    "android",
    "ios",
    "vendor",
    "Pods",
}

MAX_SEARCH_LIMIT = 200
DEFAULT_SEARCH_LIMIT = 25
MAX_READ_CHUNK = 200_000
DEFAULT_READ_CHUNK = 50_000
MAX_INDEXED_FILE_BYTES = 2_000_000
MAX_QUERY_LENGTH = 512


@dataclass
class IndexedDoc:
    path: Path
    rel: str
    uri: str
    mime_type: str
    text: str
    text_lower: str
    size_bytes: int
    mtime_ns: int
    digest: str


_DOC_PATHS_CACHE: Optional[List[Path]] = None
_DOCS_INDEX: Dict[str, IndexedDoc] = {}


def _json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)


def _send(message: Dict[str, Any]) -> None:
    sys.stdout.write(_json_dumps(message) + "\n")
    sys.stdout.flush()


def _error_response(req_id: Any, code: int, message: str) -> Dict[str, Any]:
    return {"jsonrpc": "2.0", "id": req_id, "error": {"code": code, "message": message}}


def _ok_response(req_id: Any, result: Any) -> Dict[str, Any]:
    return {"jsonrpc": "2.0", "id": req_id, "result": result}


def _is_relative_to(path: Path, base: Path) -> bool:
    try:
        path.resolve().relative_to(base.resolve())
        return True
    except ValueError:
        return False


def _is_in_search_scope(path: Path) -> bool:
    resolved = path.resolve()
    root_files = {p.resolve() for p in ROOT_INCLUDE_FILES if p.exists()}
    if resolved in root_files:
        return True

    for base in SEARCH_DIRS:
        if base.exists() and _is_relative_to(resolved, base):
            return True
    return False


def _is_text_file(path: Path) -> bool:
    suffix = path.suffix.lower()
    if suffix in TEXT_EXTENSIONS:
        return True
    if path.name.endswith(".d.ts"):
        return True
    return False


def _should_skip_path(path: Path) -> bool:
    for part in path.parts:
        if part in IGNORED_DIR_NAMES:
            return True
    return False


def _to_doc_uri(path: Path) -> str:
    rel = path.relative_to(ROOT).as_posix()
    return f"docs://{rel}"


def _from_doc_uri(uri: str) -> Path:
    if not uri.startswith("docs://"):
        raise ValueError("URI must start with docs://")

    rel = uri[len("docs://") :]
    candidate = (ROOT / rel).resolve()
    if not _is_in_search_scope(candidate):
        raise ValueError("URI points outside searchable scope")
    return candidate


def _mime_for(path: Path) -> str:
    if path.suffix.lower() in {".md", ".mdx"}:
        return "text/markdown"
    if _is_text_file(path):
        return "text/plain"
    return "application/octet-stream"


def _all_knowledge_files() -> List[Path]:
    global _DOC_PATHS_CACHE
    if _DOC_PATHS_CACHE is not None:
        return _DOC_PATHS_CACHE

    files: List[Path] = []

    for path in sorted(ROOT_INCLUDE_FILES):
        if path.exists() and path.is_file() and _is_text_file(path):
            files.append(path)

    for base in SEARCH_DIRS:
        if not base.exists():
            continue

        for path in base.rglob("*"):
            if not path.is_file() or not _is_text_file(path):
                continue
            if _should_skip_path(path):
                continue
            files.append(path)

    dedup: Dict[str, Path] = {}
    for f in files:
        rel = f.relative_to(ROOT).as_posix()
        dedup[rel] = f

    _DOC_PATHS_CACHE = [dedup[k] for k in sorted(dedup.keys())]
    return _DOC_PATHS_CACHE


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _compute_digest(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8", errors="replace")).hexdigest()


def _index_doc(path: Path) -> Optional[IndexedDoc]:
    try:
        stat = path.stat()
    except OSError:
        return None

    size_bytes = int(stat.st_size)
    if size_bytes > MAX_INDEXED_FILE_BYTES:
        return None

    rel = path.relative_to(ROOT).as_posix()
    cached = _DOCS_INDEX.get(rel)
    if cached and cached.mtime_ns == int(stat.st_mtime_ns) and cached.size_bytes == size_bytes:
        return cached

    text = _read_text(path)
    doc = IndexedDoc(
        path=path,
        rel=rel,
        uri=_to_doc_uri(path),
        mime_type=_mime_for(path),
        text=text,
        text_lower=text.lower(),
        size_bytes=size_bytes,
        mtime_ns=int(stat.st_mtime_ns),
        digest=_compute_digest(text),
    )
    _DOCS_INDEX[rel] = doc
    return doc


def _refresh_index() -> None:
    valid_rels = set()
    for path in _all_knowledge_files():
        rel = path.relative_to(ROOT).as_posix()
        valid_rels.add(rel)
        _index_doc(path)

    stale = [rel for rel in _DOCS_INDEX.keys() if rel not in valid_rels]
    for rel in stale:
        _DOCS_INDEX.pop(rel, None)


def _safe_snippet(text: str, idx: int, qlen: int, radius: int = 120) -> str:
    if idx < 0:
        snippet = text[: min(2 * radius, len(text))]
    else:
        start = max(0, idx - radius)
        end = min(len(text), idx + qlen + radius)
        snippet = text[start:end].strip()
        if start > 0:
            snippet = "..." + snippet
        if end < len(text):
            snippet = snippet + "..."
    return re.sub(r"\s+", " ", snippet)


def _normalize_paging(arguments: Dict[str, Any]) -> Tuple[int, int]:
    raw_offset = arguments.get("offset", 0)
    raw_limit = arguments.get("limit", DEFAULT_SEARCH_LIMIT)

    try:
        offset = int(raw_offset)
    except (TypeError, ValueError):
        offset = 0

    try:
        limit = int(raw_limit)
    except (TypeError, ValueError):
        limit = DEFAULT_SEARCH_LIMIT

    offset = max(0, offset)
    limit = max(1, min(MAX_SEARCH_LIMIT, limit))
    return offset, limit


def _validate_query(query: str) -> str:
    query = query.strip()
    if not query:
        raise ValueError("query is required")
    if len(query) > MAX_QUERY_LENGTH:
        raise ValueError(f"query is too long (max {MAX_QUERY_LENGTH} characters)")
    return query


def _score_match(rel: str, text: str, text_lower: str, query: str, query_lower: str) -> Tuple[int, int, int]:
    rel_lower = rel.lower()
    score = 0

    path_index = rel_lower.find(query_lower)
    content_index = text_lower.find(query_lower)
    count = text_lower.count(query_lower)

    if path_index != -1:
        score += 120
        if rel_lower.endswith(query_lower):
            score += 20
        if path_index == 0:
            score += 10

    if content_index != -1:
        score += 80
        score += min(30, count * 3)

    tokens = [t for t in re.split(r"\s+", query_lower) if t]
    if len(tokens) > 1:
        token_hits = sum(1 for t in tokens if t in rel_lower or t in text_lower)
        score += token_hits * 8

    return score, path_index, content_index


def _list_resources() -> List[Dict[str, Any]]:
    resources: List[Dict[str, Any]] = []
    for path in _all_knowledge_files():
        rel = path.relative_to(ROOT).as_posix()
        resources.append(
            {
                "uri": _to_doc_uri(path),
                "name": rel,
                "description": f"Expo knowledge file: {rel}",
                "mimeType": _mime_for(path),
            }
        )
    return resources


def _read_resource(uri: str) -> Dict[str, Any]:
    path = _from_doc_uri(uri)
    if not path.exists() or not path.is_file():
        raise FileNotFoundError(f"Resource not found: {uri}")

    text = _read_text(path)
    return {
        "contents": [
            {
                "uri": uri,
                "mimeType": _mime_for(path),
                "text": text,
            }
        ]
    }


def _tool_definitions() -> List[Dict[str, Any]]:
    return [
        {
            "name": "list_docs",
            "description": "List Expo knowledge file paths with pagination. Supports optional glob pattern like docs/pages/**/*.mdx or packages/**/src/**/*.ts",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "pattern": {"type": "string", "description": "Optional glob pattern against repo-relative paths."},
                    "offset": {"type": "integer", "minimum": 0, "description": "Start index (default 0)."},
                    "limit": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": MAX_SEARCH_LIMIT,
                        "description": f"Page size (default {DEFAULT_SEARCH_LIMIT}, max {MAX_SEARCH_LIMIT}).",
                    },
                },
            },
        },
        {
            "name": "search_docs",
            "description": "Search Expo knowledge files by path and content with scoring and pagination.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Text to find in file paths or file contents."},
                    "offset": {"type": "integer", "minimum": 0, "description": "Start index in matches (default 0)."},
                    "limit": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": MAX_SEARCH_LIMIT,
                        "description": f"Page size (default {DEFAULT_SEARCH_LIMIT}, max {MAX_SEARCH_LIMIT}).",
                    },
                    "searchMode": {
                        "type": "string",
                        "enum": ["both", "path", "content"],
                        "description": "Search scope: both (default), path only, or content only.",
                    },
                },
                "required": ["query"],
            },
        },
        {
            "name": "read_doc",
            "description": "Read one Expo knowledge file by path with optional chunking via offset/length.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Repo-relative path, such as docs/pages/eas/ai/mcp.mdx or packages/expo/src/Expo.ts",
                    },
                    "offset": {
                        "type": "integer",
                        "minimum": 0,
                        "description": "Character offset for chunked reads (default 0).",
                    },
                    "length": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": MAX_READ_CHUNK,
                        "description": f"Characters to return (default {DEFAULT_READ_CHUNK}, max {MAX_READ_CHUNK}).",
                    },
                },
                "required": ["path"],
            },
        },
        {
            "name": "get_stats",
            "description": "Get MCP index and corpus statistics for diagnostics.",
            "inputSchema": {"type": "object", "properties": {}},
        },
    ]


def _tool_list_docs(arguments: Dict[str, Any]) -> Dict[str, Any]:
    pattern = str(arguments.get("pattern", "")).strip()
    offset, limit = _normalize_paging(arguments)

    items: List[Dict[str, Any]] = []
    for path in _all_knowledge_files():
        rel = path.relative_to(ROOT).as_posix()
        if pattern and not fnmatch(rel, pattern):
            continue
        items.append({"path": rel, "uri": _to_doc_uri(path)})

    total = len(items)
    page = items[offset : offset + limit]

    payload = {
        "total": total,
        "offset": offset,
        "limit": limit,
        "hasMore": (offset + limit) < total,
        "nextOffset": offset + limit if (offset + limit) < total else None,
        "results": page,
    }
    return {"content": [{"type": "text", "text": _json_dumps(payload)}]}


def _tool_search_docs(arguments: Dict[str, Any]) -> Dict[str, Any]:
    query = _validate_query(str(arguments.get("query", "")))
    offset, limit = _normalize_paging(arguments)
    search_mode = str(arguments.get("searchMode", "both")).strip().lower() or "both"
    if search_mode not in {"both", "path", "content"}:
        raise ValueError("searchMode must be one of: both, path, content")

    query_lower = query.lower()
    results = []

    _refresh_index()

    for rel, doc in _DOCS_INDEX.items():
        path_hit = query_lower in rel.lower()
        content_hit = query_lower in doc.text_lower

        if search_mode == "path" and not path_hit:
            continue
        if search_mode == "content" and not content_hit:
            continue
        if search_mode == "both" and not (path_hit or content_hit):
            continue

        score, path_idx, content_idx = _score_match(rel, doc.text, doc.text_lower, query, query_lower)
        snippet = _safe_snippet(doc.text, content_idx, len(query)) if content_hit else ""

        results.append(
            {
                "path": rel,
                "uri": doc.uri,
                "pathMatch": path_hit,
                "contentMatch": content_hit,
                "snippet": snippet,
                "score": score,
                "_pathIdx": path_idx,
                "_contentIdx": content_idx,
            }
        )

    results.sort(
        key=lambda item: (
            -item["score"],
            item["_pathIdx"] if item["_pathIdx"] >= 0 else 10**9,
            item["path"],
        )
    )

    total = len(results)
    page = results[offset : offset + limit]
    for item in page:
        item.pop("_pathIdx", None)
        item.pop("_contentIdx", None)

    payload = {
        "query": query,
        "searchMode": search_mode,
        "total": total,
        "offset": offset,
        "limit": limit,
        "hasMore": (offset + limit) < total,
        "nextOffset": offset + limit if (offset + limit) < total else None,
        "results": page,
    }
    return {"content": [{"type": "text", "text": _json_dumps(payload)}]}


def _tool_read_doc(arguments: Dict[str, Any]) -> Dict[str, Any]:
    rel = str(arguments.get("path", "")).strip()
    if not rel:
        raise ValueError("path is required")

    candidate = (ROOT / rel).resolve()
    if not _is_in_search_scope(candidate):
        raise ValueError("path must be inside docs/, packages/, or allowed root files")
    if not candidate.exists() or not candidate.is_file():
        raise FileNotFoundError(f"File not found: {rel}")

    raw_offset = arguments.get("offset", 0)
    raw_length = arguments.get("length", DEFAULT_READ_CHUNK)

    try:
        offset = int(raw_offset)
    except (TypeError, ValueError):
        offset = 0

    try:
        length = int(raw_length)
    except (TypeError, ValueError):
        length = DEFAULT_READ_CHUNK

    offset = max(0, offset)
    length = max(1, min(MAX_READ_CHUNK, length))

    text = _read_text(candidate)
    total_chars = len(text)
    content = text[offset : offset + length]

    payload = {
        "path": candidate.relative_to(ROOT).as_posix(),
        "uri": _to_doc_uri(candidate),
        "totalChars": total_chars,
        "offset": offset,
        "length": length,
        "hasMore": (offset + length) < total_chars,
        "nextOffset": offset + length if (offset + length) < total_chars else None,
        "content": content,
    }
    return {"content": [{"type": "text", "text": _json_dumps(payload)}]}


def _tool_get_stats(_: Dict[str, Any]) -> Dict[str, Any]:
    _refresh_index()

    files_count = len(_all_knowledge_files())
    indexed_count = len(_DOCS_INDEX)
    total_indexed_bytes = sum(doc.size_bytes for doc in _DOCS_INDEX.values())

    payload = {
        "root": str(ROOT),
        "searchDirs": [str(d) for d in SEARCH_DIRS],
        "filesDiscovered": files_count,
        "filesIndexed": indexed_count,
        "filesSkippedForSize": max(0, files_count - indexed_count),
        "maxIndexedFileBytes": MAX_INDEXED_FILE_BYTES,
        "totalIndexedBytes": total_indexed_bytes,
    }
    return {"content": [{"type": "text", "text": _json_dumps(payload)}]}


def _handle_request(req: Dict[str, Any]) -> Dict[str, Any]:
    req_id = req.get("id")
    method = req.get("method")
    params = req.get("params", {})

    if method == "initialize":
        return _ok_response(
            req_id,
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}, "resources": {}},
                "serverInfo": {"name": "expo-knowledge-mcp", "version": "2.0.0"},
            },
        )

    if method == "notifications/initialized":
        return _ok_response(req_id, {})

    if method == "resources/list":
        return _ok_response(req_id, {"resources": _list_resources()})

    if method == "resources/read":
        uri = params.get("uri")
        if not uri:
            return _error_response(req_id, -32602, "Missing required parameter: uri")
        try:
            return _ok_response(req_id, _read_resource(str(uri)))
        except Exception as exc:
            return _error_response(req_id, -32000, str(exc))

    if method == "tools/list":
        return _ok_response(req_id, {"tools": _tool_definitions()})

    if method == "tools/call":
        name = params.get("name")
        arguments = params.get("arguments", {})
        if not isinstance(arguments, dict):
            return _error_response(req_id, -32602, "arguments must be an object")

        try:
            if name == "list_docs":
                return _ok_response(req_id, _tool_list_docs(arguments))
            if name == "search_docs":
                return _ok_response(req_id, _tool_search_docs(arguments))
            if name == "read_doc":
                return _ok_response(req_id, _tool_read_doc(arguments))
            if name == "get_stats":
                return _ok_response(req_id, _tool_get_stats(arguments))
            return _error_response(req_id, -32601, f"Unknown tool: {name}")
        except Exception as exc:
            return _error_response(req_id, -32000, str(exc))

    return _error_response(req_id, -32601, f"Method not found: {method}")


def main() -> None:
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue

        try:
            req = json.loads(line)
        except json.JSONDecodeError:
            continue

        # Ignore notifications that do not require responses.
        if "id" not in req:
            continue

        _send(_handle_request(req))


if __name__ == "__main__":
    main()
