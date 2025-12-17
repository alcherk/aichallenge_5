from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional


def _jsonrpc_result(req_id: Any, result: Any) -> Dict[str, Any]:
    return {"jsonrpc": "2.0", "id": req_id, "result": result}


def _jsonrpc_error(req_id: Any, code: int, message: str, data: Any = None) -> Dict[str, Any]:
    err: Dict[str, Any] = {"code": code, "message": message}
    if data is not None:
        err["data"] = data
    return {"jsonrpc": "2.0", "id": req_id, "error": err}


def _resolve_within_root(root: Path, raw_path: str) -> Path:
    root = root.resolve()
    p = Path(raw_path)
    candidate = (root / p).resolve() if not p.is_absolute() else p.resolve()
    try:
        candidate.relative_to(root)
    except Exception:
        raise RuntimeError(f"path escapes root: {raw_path}")
    return candidate


def _tool_list() -> Dict[str, Any]:
    return {
        "tools": [
            {
                "name": "read_file",
                "description": "Read a UTF-8 text file from the workspace root.",
                "inputSchema": {
                    "type": "object",
                    "properties": {"path": {"type": "string"}},
                    "required": ["path"],
                    "additionalProperties": False,
                },
            },
            {
                "name": "write_file",
                "description": "Write a UTF-8 text file within the workspace root.",
                "inputSchema": {
                    "type": "object",
                    "properties": {"path": {"type": "string"}, "content": {"type": "string"}},
                    "required": ["path", "content"],
                    "additionalProperties": False,
                },
            },
            {
                "name": "list_dir",
                "description": "List entries in a directory within the workspace root.",
                "inputSchema": {
                    "type": "object",
                    "properties": {"path": {"type": "string"}},
                    "required": ["path"],
                    "additionalProperties": False,
                },
            },
        ]
    }


def _call_tool(root: Path, name: str, arguments: Dict[str, Any]) -> Any:
    if name == "read_file":
        p = _resolve_within_root(root, str(arguments.get("path", "")))
        return {"path": str(p), "content": p.read_text(encoding="utf-8")}

    if name == "write_file":
        p = _resolve_within_root(root, str(arguments.get("path", "")))
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(str(arguments.get("content", "")), encoding="utf-8")
        return {"path": str(p), "written": True}

    if name == "list_dir":
        p = _resolve_within_root(root, str(arguments.get("path", "")))
        if not p.exists():
            raise RuntimeError("directory does not exist")
        if not p.is_dir():
            raise RuntimeError("path is not a directory")
        entries = []
        for child in sorted(p.iterdir(), key=lambda x: x.name):
            entries.append(
                {"name": child.name, "type": "dir" if child.is_dir() else "file"}
            )
        return {"path": str(p), "entries": entries}

    raise RuntimeError(f"unknown tool: {name}")


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Built-in MCP filesystem server (stdio).")
    parser.add_argument("--root", required=True, help="Workspace root for file operations")
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except Exception:
            continue
        if not isinstance(msg, dict):
            continue

        req_id = msg.get("id")
        method = msg.get("method")
        params = msg.get("params") or {}

        # Notifications have no id; ignore.
        if req_id is None:
            continue

        try:
            if method == "initialize":
                result = {
                    "serverInfo": {"name": "builtin_filesystem", "version": "0.1"},
                    "capabilities": {"tools": {}},
                }
                out = _jsonrpc_result(req_id, result)
            elif method == "tools/list":
                out = _jsonrpc_result(req_id, _tool_list())
            elif method == "tools/call":
                name = str(params.get("name") or "")
                arguments = params.get("arguments") or {}
                if not isinstance(arguments, dict):
                    arguments = {}
                out = _jsonrpc_result(req_id, _call_tool(root, name, arguments))
            else:
                out = _jsonrpc_error(req_id, -32601, f"Method not found: {method}")
        except Exception as e:
            out = _jsonrpc_error(req_id, -32000, str(e))

        sys.stdout.write(json.dumps(out, ensure_ascii=False) + "\n")
        sys.stdout.flush()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())



