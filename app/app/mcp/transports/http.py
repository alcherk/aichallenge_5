from __future__ import annotations

from typing import Any, Dict, Optional

import httpx
import json
import os
import logging

from ..jsonrpc import build_notification, build_request, next_id
from .base import MCPTransport


logger = logging.getLogger("app.mcp_http_jsonrpc")


def _truthy_env(name: str) -> bool:
    v = (os.getenv(name, "") or "").strip().lower()
    return v in {"1", "true", "yes", "y", "on"}


def _json_preview(value: Any, *, limit: int = 8000) -> tuple[str, bool]:
    try:
        s = json.dumps(value, ensure_ascii=False, sort_keys=True)
    except Exception:
        s = str(value)
    if len(s) > limit:
        return (s[:limit] + "…", True)
    return (s, False)


class HTTPTransport(MCPTransport):
    """
    JSON-RPC over HTTP POST.

    We assume the MCP server accepts a JSON-RPC request body and returns a JSON-RPC response.
    """

    def __init__(self, url: str, *, timeout_seconds: float = 30.0) -> None:
        self._url = url
        self._client = httpx.AsyncClient(timeout=timeout_seconds)

    async def request(self, method: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        rid = next_id()
        payload = build_request(method, params, request_id=rid)
        if _truthy_env("HTTP_LOG_POST_PAYLOADS"):
            preview, truncated = _json_preview(payload)
            logger.info(
                json.dumps(
                    {
                        "event": "http_post_payload",
                        "target": "mcp_jsonrpc",
                        "url": self._url,
                        "truncated": truncated,
                        "payload": preview,
                    },
                    ensure_ascii=False,
                )
            )
        resp = await self._client.post(self._url, json=payload)
        resp.raise_for_status()
        data = resp.json()
        if not isinstance(data, dict):
            raise RuntimeError("MCP HTTP transport expected a JSON object response")
        return data

    async def notify(self, method: str, params: Optional[Dict[str, Any]] = None) -> None:
        # Best-effort: some HTTP MCP servers may not support notifications.
        payload = build_notification(method, params)
        try:
            if _truthy_env("HTTP_LOG_POST_PAYLOADS"):
                preview, truncated = _json_preview(payload)
                logger.info(
                    json.dumps(
                        {
                            "event": "http_post_payload",
                            "target": "mcp_jsonrpc_notify",
                            "url": self._url,
                            "truncated": truncated,
                            "payload": preview,
                        },
                        ensure_ascii=False,
                    )
                )
            resp = await self._client.post(self._url, json=payload)
            # If the server returns an error here, don't fail startup/tooling.
            _ = resp.status_code
        except Exception:
            return

    async def aclose(self) -> None:
        await self._client.aclose()


