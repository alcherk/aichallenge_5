from __future__ import annotations

import json
import sys
from typing import Any, Dict, Optional

import httpx


def _jsonrpc_result(req_id: Any, result: Any) -> Dict[str, Any]:
    return {"jsonrpc": "2.0", "id": req_id, "result": result}


def _jsonrpc_error(req_id: Any, code: int, message: str, data: Any = None) -> Dict[str, Any]:
    err: Dict[str, Any] = {"code": code, "message": message}
    if data is not None:
        err["data"] = data
    return {"jsonrpc": "2.0", "id": req_id, "error": err}


def _tool_list() -> Dict[str, Any]:
    return {
        "tools": [
            {
                "name": "fetch",
                "description": "HTTP fetch (GET/POST). Returns status, headers, and text/json body.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "url": {"type": "string"},
                        "method": {"type": "string", "enum": ["GET", "POST"]},
                        "headers": {
                            "type": "object",
                            "additionalProperties": {"type": "string"},
                        },
                        "body": {"type": ["string", "object", "array", "number", "boolean", "null"]},
                    },
                    "required": ["url", "method"],
                    "additionalProperties": False,
                },
            }
        ]
    }


async def _do_fetch(arguments: Dict[str, Any]) -> Any:
    url = str(arguments.get("url") or "").strip()
    method = str(arguments.get("method") or "").upper().strip()
    headers = arguments.get("headers") or {}
    body = arguments.get("body")

    if not url:
        raise RuntimeError("url is required")
    if method not in ("GET", "POST"):
        raise RuntimeError("method must be GET or POST")
    if not isinstance(headers, dict):
        headers = {}

    async with httpx.AsyncClient(timeout=30.0) as client:
        if method == "GET":
            resp = await client.get(url, headers=headers)
        else:
            # If body is a dict/list, send JSON; else send as text.
            if isinstance(body, (dict, list)):
                resp = await client.post(url, headers=headers, json=body)
            else:
                resp = await client.post(url, headers=headers, content="" if body is None else str(body))

    content_type = resp.headers.get("content-type", "")
    out: Dict[str, Any] = {
        "ok": bool(resp.is_success),
        "status": int(resp.status_code),
        "headers": dict(resp.headers),
    }

    if "application/json" in content_type.lower():
        try:
            out["json"] = resp.json()
        except Exception:
            out["text"] = resp.text
    else:
        out["text"] = resp.text
    return out


def main(argv: Optional[list[str]] = None) -> int:
    # argv reserved for future; server is stdio-only.
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

        if req_id is None:
            continue

        try:
            if method == "initialize":
                result = {
                    "serverInfo": {"name": "builtin_fetch", "version": "0.1"},
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
                if name != "fetch":
                    raise RuntimeError(f"unknown tool: {name}")
                # Run the async fetch in a small loop.
                import asyncio

                result = asyncio.run(_do_fetch(arguments))
                out = _jsonrpc_result(req_id, result)
            else:
                out = _jsonrpc_error(req_id, -32601, f"Method not found: {method}")
        except Exception as e:
            out = _jsonrpc_error(req_id, -32000, str(e))

        sys.stdout.write(json.dumps(out, ensure_ascii=False) + "\n")
        sys.stdout.flush()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())



