from __future__ import annotations

import asyncio
import json
from typing import Any, Dict, List

import httpx

from app.app.mcp.http_tools_session import MCPHttpToolsSession


def _json_response(data: Any, status_code: int = 200) -> httpx.Response:
    return httpx.Response(status_code=status_code, json=data)


def test_list_tools_parses_descriptors() -> None:
    tools_payload: List[Dict[str, Any]] = [
        {
            "name": "weather.geocode",
            "description": "Convert a place name to latitude/longitude using Open-Meteo geocoding.",
            "inputSchema": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]},
            "outputSchema": {"type": "object", "properties": {"query": {"type": "string"}}},
        },
        {
            "name": "weather.get_current",
            "description": "Get current weather for a given latitude and longitude.",
            "inputSchema": {"type": "object", "properties": {"latitude": {"type": "number"}}},
            "outputSchema": {"type": "object", "properties": {"summary": {"type": "string"}}},
        },
    ]

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url.path == "/mcp/tools"
        return _json_response(tools_payload)

    async def run() -> None:
        client = httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="http://test")
        session = MCPHttpToolsSession("http://test", server_name="weather", client=client)

        tools = await session.list_tools()
        assert isinstance(tools, list)
        assert [t["name"] for t in tools] == ["weather.geocode", "weather.get_current"]

        await client.aclose()

    asyncio.run(run())


def test_call_tool_success_extracts_text_and_json() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == "/mcp/tools/call"
        body = json.loads((request.content or b"{}").decode("utf-8"))
        assert body["name"] == "weather.get_current"
        # Client injects forecast_days=1 and strips timezone for weather calls.
        assert body["arguments"] == {"latitude": 1.0, "longitude": 2.0, "forecast_days": 1}
        assert isinstance(body.get("requestId"), str)
        return _json_response(
            {
                "content": [
                    {"type": "text", "text": "Temperature: 10"},
                    {"type": "json", "data": {"summary": "Temperature: 10", "raw": {"ok": True}}},
                ],
                "isError": False,
                "requestId": body["requestId"],
            }
        )

    async def run() -> None:
        client = httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="http://test")
        session = MCPHttpToolsSession("http://test", server_name="weather", client=client)

        out = await session.call_tool("weather.get_current", {"latitude": 1.0, "longitude": 2.0})
        assert out["isError"] is False
        assert out["text"] == "Temperature: 10"
        assert out["data"]["summary"] == "Temperature: 10"
        assert out["raw"]["isError"] is False

        await client.aclose()

    asyncio.run(run())


def test_call_tool_isError_true_is_returned() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads((request.content or b"{}").decode("utf-8"))
        assert body["arguments"].get("forecast_days") == 1
        return _json_response(
            {
                "content": [
                    {"type": "text", "text": "Invalid tool arguments."},
                    {"type": "json", "data": {"validationErrors": [{"loc": ["latitude"], "msg": "bad"}]}},
                ],
                "isError": True,
                "requestId": body.get("requestId"),
            }
        )

    async def run() -> None:
        client = httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="http://test")
        session = MCPHttpToolsSession("http://test", server_name="weather", client=client)

        out = await session.call_tool("weather.get_current", {"latitude": 999})
        assert out["isError"] is True
        assert out["text"] == "Invalid tool arguments."
        assert "validationErrors" in (out["data"] or {})

        await client.aclose()

    asyncio.run(run())


def test_weather_forecast_days_invalid_is_forced_to_one() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads((request.content or b"{}").decode("utf-8"))
        assert body["name"] == "weather.get_current"
        # If model sends garbage forecast_days, client must force it to int=1.
        assert body["arguments"]["forecast_days"] == 1
        return _json_response(
            {
                "content": [
                    {"type": "text", "text": "OK"},
                    {"type": "json", "data": {"summary": "OK", "raw": {}}},
                ],
                "isError": False,
                "requestId": body.get("requestId"),
            }
        )

    async def run() -> None:
        client = httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="http://test")
        session = MCPHttpToolsSession("http://test", server_name="weather", client=client)
        out = await session.call_tool(
            "weather.get_current",
            {"latitude": 1.0, "longitude": 2.0, "forecast_days": "Europe/Moscow"},
        )
        assert out["isError"] is False
        await client.aclose()

    asyncio.run(run())


