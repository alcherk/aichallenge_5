from __future__ import annotations

import asyncio
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .client import MCPClientSession
from .config import MCPConfig, MCPServerConfig, load_mcp_config, to_jsonable
from .safety import guard_fetch_tool_result, guard_filesystem_tool_args
from .transports.http import HTTPTransport
from .transports.stdio import StdioTransport


_SAFE_NAME_RE = re.compile(r"[^a-zA-Z0-9_]+")


def _sanitize_name(s: str) -> str:
    s2 = _SAFE_NAME_RE.sub("_", s.strip())
    s2 = re.sub(r"_+", "_", s2)
    return s2.strip("_") or "tool"


def _sanitize_json_schema_for_openai(schema: Any) -> Any:
    """
    OpenAI tool parameter schemas must be valid JSON Schema objects.
    In practice, the API is strict about arrays: any array schema must include `items`.
    Some MCP tools (notably fetch) emit unions that include "array" without specifying items.

    This function recursively normalizes schemas to reduce upstream 400s.
    """
    if not isinstance(schema, dict):
        return schema

    out: Dict[str, Any] = dict(schema)

    t = out.get("type")
    # If type is "array" or includes "array", ensure items exists.
    is_array = t == "array" or (isinstance(t, list) and "array" in t)
    if is_array and "items" not in out:
        out["items"] = {}

    # Recurse into common schema composition keys
    for key in ("anyOf", "oneOf", "allOf"):
        if isinstance(out.get(key), list):
            out[key] = [_sanitize_json_schema_for_openai(s) for s in out[key]]

    # Recurse into object properties
    if isinstance(out.get("properties"), dict):
        out["properties"] = {
            k: _sanitize_json_schema_for_openai(v) for k, v in out["properties"].items()
        }

    # Recurse into items
    if "items" in out:
        out["items"] = _sanitize_json_schema_for_openai(out["items"])

    # Recurse into additionalProperties if it's a schema object
    ap = out.get("additionalProperties")
    if isinstance(ap, dict):
        out["additionalProperties"] = _sanitize_json_schema_for_openai(ap)

    return out


@dataclass
class _ToolBinding:
    server_name: str
    mcp_tool_name: str
    kind: str


class MCPManager:
    def __init__(
        self,
        *,
        config: MCPConfig,
        workspace_root: Path,
        config_source: str,
    ) -> None:
        self._config = config
        self._workspace_root = workspace_root
        self._config_source = config_source

        self._sessions: dict[str, MCPClientSession] = {}
        self._tools_openai: list[dict] = []
        self._tool_bindings: dict[str, _ToolBinding] = {}

    @property
    def enabled(self) -> bool:
        return bool(self._config.servers)

    async def connect(self) -> None:
        """
        Connect to configured MCP servers and discover tools.

        This should be called once at app startup.
        """
        self._tools_openai = []
        self._tool_bindings = {}

        for server in self._config.servers:
            session = await self._connect_server(server)
            self._sessions[server.name] = session
            await session.initialize()
            tools = await session.list_tools()
            self._register_tools(server, tools)

    async def aclose(self) -> None:
        for s in list(self._sessions.values()):
            try:
                await s.aclose()
            except Exception:
                pass
        self._sessions.clear()

    def matches(self, *, config_source: str, workspace_root: Path) -> bool:
        return self._config_source == config_source and self._workspace_root.resolve() == workspace_root.resolve()

    async def _connect_server(self, server: MCPServerConfig) -> MCPClientSession:
        if server.transport == "stdio":
            assert server.command is not None
            t = StdioTransport(server.command)
            await t.start()
            return MCPClientSession(t, server_name=server.name)
        else:
            assert server.url is not None
            t = HTTPTransport(server.url)
            return MCPClientSession(t, server_name=server.name)

    def openai_tools(self) -> list[dict]:
        """
        OpenAI tool definitions in chat.completions format.
        """
        return list(self._tools_openai)

    def status(self) -> dict:
        """
        Return a JSON-serializable MCP status snapshot for UI/debugging.
        """
        servers = []
        for s in self._config.servers:
            servers.append(
                {
                    "name": s.name,
                    "transport": s.transport,
                    "kind": s.kind,
                    "connected": s.name in self._sessions,
                }
            )

        tools = []
        for t in self._tools_openai:
            fn = (t or {}).get("function") or {}
            openai_name = fn.get("name")
            binding = self._tool_bindings.get(openai_name)
            tools.append(
                {
                    "openai_name": openai_name,
                    "server": binding.server_name if binding else None,
                    "mcp_name": binding.mcp_tool_name if binding else None,
                    "kind": binding.kind if binding else None,
                    "description": fn.get("description"),
                    "parameters": fn.get("parameters"),
                }
            )

        return {"enabled": True, "servers": servers, "tools": tools}

    def _register_tools(self, server: MCPServerConfig, tools: List[Dict[str, Any]]) -> None:
        server_safe = _sanitize_name(server.name)
        for t in tools:
            tool_name = str(t.get("name") or "").strip()
            if not tool_name:
                continue
            tool_safe = _sanitize_name(tool_name)
            openai_name = f"mcp_{server_safe}__{tool_safe}"

            # MCP tool schema: { name, description?, inputSchema? }
            description = str(t.get("description") or f"MCP tool {tool_name} from {server.name}")
            params = t.get("inputSchema")
            if not isinstance(params, dict):
                # OpenAI requires a JSON schema object; default to accepting anything.
                params = {"type": "object", "properties": {}, "additionalProperties": True}
            params = _sanitize_json_schema_for_openai(params)

            self._tools_openai.append(
                {
                    "type": "function",
                    "function": {
                        "name": openai_name,
                        "description": description,
                        "parameters": params,
                    },
                }
            )
            self._tool_bindings[openai_name] = _ToolBinding(
                server_name=server.name, mcp_tool_name=tool_name, kind=server.kind
            )

    async def call_openai_tool(self, openai_tool_name: str, arguments: Dict[str, Any]) -> Any:
        """
        Execute a tool by its OpenAI-facing tool name.
        """
        binding = self._tool_bindings.get(openai_tool_name)
        if binding is None:
            raise RuntimeError(f"Unknown MCP tool: {openai_tool_name}")

        session = self._sessions.get(binding.server_name)
        if session is None:
            raise RuntimeError(f"MCP server not connected: {binding.server_name}")

        if binding.kind == "filesystem":
            guard_filesystem_tool_args(self._workspace_root, binding.mcp_tool_name, arguments)

        result = await session.call_tool(binding.mcp_tool_name, arguments)

        if binding.kind == "fetch":
            guard_fetch_tool_result(binding.mcp_tool_name, result)

        return to_jsonable(result)


_MANAGER: Optional[MCPManager] = None
_MANAGER_LOCK = asyncio.Lock()


def init_mcp_manager(*, mcp_config_path: Optional[str], workspace_root: Path) -> Optional[MCPManager]:
    """
    Initialize the global MCP manager (if config is present).
    """
    cfg = load_mcp_config(mcp_config_path)
    if cfg is None or not cfg.servers:
        return None
    global _MANAGER
    _MANAGER = MCPManager(config=cfg, workspace_root=workspace_root, config_source=mcp_config_path)
    return _MANAGER


def get_mcp_manager() -> Optional[MCPManager]:
    return _MANAGER


async def ensure_mcp_manager(*, mcp_config_path: Optional[str], workspace_root: Path) -> Optional[MCPManager]:
    """
    Ensure an MCP manager is initialized and connected.

    This supports enabling MCP dynamically (e.g. from UI-provided per-request settings)
    while keeping MCP disabled by default when no config is provided.
    """
    global _MANAGER
    config_source = mcp_config_path or "__builtin_default__"

    async with _MANAGER_LOCK:
        if _MANAGER is not None and _MANAGER.matches(config_source=config_source, workspace_root=workspace_root):
            return _MANAGER

        # Reinitialize if config changed.
        if _MANAGER is not None:
            try:
                await _MANAGER.aclose()
            except Exception:
                pass
            _MANAGER = None

        if mcp_config_path:
            cfg = load_mcp_config(mcp_config_path)
            if cfg is None or not cfg.servers:
                return None
        else:
            # Built-in default: filesystem + fetch stdio servers.
            py = sys.executable
            cfg = MCPConfig(
                servers=[
                    MCPServerConfig(
                        name="builtin_filesystem",
                        transport="stdio",
                        kind="filesystem",
                        command=[
                            py,
                            "-m",
                            "app.app.mcp.servers.filesystem_server",
                            "--root",
                            str(workspace_root),
                        ],
                    ),
                    MCPServerConfig(
                        name="builtin_fetch",
                        transport="stdio",
                        kind="fetch",
                        command=[py, "-m", "app.app.mcp.servers.fetch_server"],
                    ),
                ]
            )

        _MANAGER = MCPManager(config=cfg, workspace_root=workspace_root, config_source=config_source)
        await _MANAGER.connect()
        return _MANAGER


