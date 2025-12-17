from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, Dict, List

from app.app.mcp.config import MCPConfig, MCPServerConfig
from app.app.mcp.manager import MCPManager


def test_manager_uses_mcp_tools_session_and_registers_openai_tools(monkeypatch) -> None:
    tools_payload: List[Dict[str, Any]] = [
        {
            "name": "weather.geocode",
            "description": "Convert a place name to latitude/longitude using Open-Meteo geocoding.",
            "inputSchema": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]},
            "outputSchema": {"type": "object"},
        }
    ]

    class FakeMCPHttpToolsSession:
        def __init__(self, base_url: str, *, server_name: str, **_kwargs: Any) -> None:
            self.base_url = base_url
            self.server_name = server_name
            self.last_call: Dict[str, Any] | None = None

        async def initialize(self) -> None:
            return

        async def list_tools(self) -> List[Dict[str, Any]]:
            return tools_payload

        async def call_tool(self, name: str, arguments: Dict[str, Any]) -> Any:
            self.last_call = {"name": name, "arguments": arguments}
            return {"isError": False, "text": "OK", "data": {"name": name, "args": arguments}}

        async def aclose(self) -> None:
            return

    # Patch manager module to ensure it selects our MCP tools session for http_mode=mcp_tools
    import app.app.mcp.manager as manager_mod

    monkeypatch.setattr(manager_mod, "MCPHttpToolsSession", FakeMCPHttpToolsSession)

    async def run() -> None:
        cfg = MCPConfig(
            servers=[
                MCPServerConfig(
                    name="weather",
                    transport="http",
                    url="http://example",
                    kind="generic",
                    http_mode="mcp_tools",
                )
            ]
        )
        mgr = MCPManager(config=cfg, workspace_root=Path("."), config_source="test")
        await mgr.connect()

        tools = mgr.openai_tools()
        assert len(tools) == 1
        fn = tools[0]["function"]
        assert fn["name"] == "mcp_weather__weather_geocode"
        assert "Geocode" in (fn.get("description") or "") or "geocoding" in (fn.get("description") or "")

        # Verify manager can execute a tool and that any weather timezone workaround doesn't affect other tools.
        out = await mgr.call_openai_tool("mcp_weather__weather_geocode", {"query": "Berlin"})
        assert out["data"]["args"]["query"] == "Berlin"

    asyncio.run(run())


