from __future__ import annotations

from typing import Any, Dict, Optional

import httpx

from ..jsonrpc import build_notification, build_request, next_id
from .base import MCPTransport


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
            resp = await self._client.post(self._url, json=payload)
            # If the server returns an error here, don't fail startup/tooling.
            _ = resp.status_code
        except Exception:
            return

    async def aclose(self) -> None:
        await self._client.aclose()


