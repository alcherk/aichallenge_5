from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, Dict, List

from app.app.mcp.config import MCPConfig, MCPServerConfig
from app.app.mcp.manager import MCPManager


def test_manager_strips_timezone_for_weather_tools(monkeypatch) -> None:
    tools_payload: List[Dict[str, Any]] = [
        {
            "name": "weather.get_current",
            "description": "Get current weather for a given latitude and longitude.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "latitude": {"type": "number"},
                    "longitude": {"type": "number"},
                    "timezone": {"type": "string"},
                },
                "required": ["latitude", "longitude"],
            },
            "outputSchema": {"type": "object"},
        }
    ]

    class FakeMCPHttpToolsSession:
        def __init__(self, base_url: str, *, server_name: str, **_kwargs: Any) -> None:
            self.last_args: Dict[str, Any] | None = None

        async def initialize(self) -> None:
            return

        async def list_tools(self) -> List[Dict[str, Any]]:
            return tools_payload

        async def call_tool(self, name: str, arguments: Dict[str, Any]) -> Any:
            self.last_args = dict(arguments)
            return {"isError": False, "text": "OK", "data": {"args": arguments}}

        async def aclose(self) -> None:
            return

    import app.app.mcp.manager as manager_mod

    monkeypatch.setattr(manager_mod, "MCPHttpToolsSession", FakeMCPHttpToolsSession)

    async def run() -> None:
        cfg = MCPConfig(
            servers=[
                MCPServerConfig(
                    name="weather_mcp_tools",
                    transport="http",
                    url="http://example",
                    kind="generic",
                    http_mode="mcp_tools",
                )
            ]
        )
        mgr = MCPManager(config=cfg, workspace_root=Path("."), config_source="test")
        await mgr.connect()

        # Execute the weather tool with timezone; manager should strip timezone before calling server.
        out = await mgr.call_openai_tool(
            "mcp_weather_mcp_tools__weather_get_current",
            {"latitude": 1.0, "longitude": 2.0, "timezone": "Europe/Moscow"},
        )
        assert out["data"]["args"]["latitude"] == 1.0
        assert out["data"]["args"]["longitude"] == 2.0
        assert "timezone" not in out["data"]["args"]

    asyncio.run(run())


