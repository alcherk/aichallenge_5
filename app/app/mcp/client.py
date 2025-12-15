from __future__ import annotations

from typing import Any, Dict, List, Optional

from .jsonrpc import parse_response
from .transports.base import MCPTransport


class MCPClientSession:
    """
    Minimal MCP client session implementing initialize + tools/list + tools/call.

    We keep this deliberately small and tolerant because MCP servers may vary.
    """

    def __init__(self, transport: MCPTransport, *, server_name: str) -> None:
        self._transport = transport
        self._server_name = server_name
        self._initialized = False

    async def initialize(self) -> None:
        if self._initialized:
            return

        # protocolVersion value is treated as an opaque string by many servers.
        init_params: Dict[str, Any] = {
            "protocolVersion": "2024-11-05",
            "clientInfo": {"name": "week1_day1_proxy", "version": "0.1"},
            "capabilities": {},
        }
        raw = await self._transport.request("initialize", init_params)
        _ = parse_response(raw)

        # Many MCP servers expect an 'initialized' notification (similar to LSP).
        await self._transport.notify("initialized", {})
        self._initialized = True

    async def list_tools(self) -> List[Dict[str, Any]]:
        raw = await self._transport.request("tools/list", {})
        result = parse_response(raw)

        if isinstance(result, dict) and isinstance(result.get("tools"), list):
            tools = result["tools"]
        elif isinstance(result, list):
            tools = result
        else:
            tools = []

        return [t for t in tools if isinstance(t, dict)]

    async def call_tool(self, name: str, arguments: Dict[str, Any]) -> Any:
        raw = await self._transport.request("tools/call", {"name": name, "arguments": arguments})
        return parse_response(raw)

    async def aclose(self) -> None:
        await self._transport.aclose()


