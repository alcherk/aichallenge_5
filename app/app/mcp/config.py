from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, Optional


TransportType = Literal["stdio", "http"]
ServerKind = Literal["filesystem", "fetch", "generic"]
HTTPMode = Literal["jsonrpc", "mcp_tools"]


@dataclass(frozen=True)
class MCPServerConfig:
    name: str
    transport: TransportType
    command: Optional[list[str]] = None
    url: Optional[str] = None
    kind: ServerKind = "generic"
    # Only used when transport == "http"
    http_mode: HTTPMode = "jsonrpc"
    timeout_seconds: float = 30.0
    max_retries: int = 3
    backoff_initial_seconds: float = 0.5
    backoff_max_seconds: float = 5.0


@dataclass(frozen=True)
class MCPConfig:
    servers: list[MCPServerConfig]


def load_mcp_config(path: Optional[str]) -> Optional[MCPConfig]:
    """
    Load MCP server configuration from a JSON file.

    This config is optional; when absent/empty, MCP is considered disabled.
    """
    if not path:
        return None

    p = Path(path)
    if not p.exists():
        raise RuntimeError(f"MCP config file not found: {p}")

    raw = json.loads(p.read_text(encoding="utf-8"))
    servers_raw = raw.get("servers") if isinstance(raw, dict) else None
    if not isinstance(servers_raw, list):
        raise RuntimeError("MCP config must be an object with a 'servers' array")

    servers: list[MCPServerConfig] = []
    for idx, s in enumerate(servers_raw):
        if not isinstance(s, dict):
            raise RuntimeError(f"MCP servers[{idx}] must be an object")

        name = str(s.get("name") or "").strip()
        if not name:
            raise RuntimeError(f"MCP servers[{idx}] missing 'name'")

        transport = s.get("transport")
        if transport not in ("stdio", "http"):
            raise RuntimeError(
                f"MCP servers[{idx}] invalid 'transport' (expected 'stdio' or 'http')"
            )

        kind = s.get("kind", "generic")
        if kind not in ("filesystem", "fetch", "generic"):
            raise RuntimeError(
                f"MCP servers[{idx}] invalid 'kind' (expected filesystem|fetch|generic)"
            )

        command = s.get("command")
        url = s.get("url")

        if transport == "stdio":
            if not isinstance(command, list) or not all(isinstance(x, str) for x in command):
                raise RuntimeError(
                    f"MCP servers[{idx}] transport=stdio requires 'command': [str, ...]"
                )
        else:
            if not isinstance(url, str) or not url.strip():
                raise RuntimeError(f"MCP servers[{idx}] transport=http requires 'url'")

        http_mode = s.get("http_mode", "jsonrpc")
        if http_mode not in ("jsonrpc", "mcp_tools"):
            raise RuntimeError(
                f"MCP servers[{idx}] invalid 'http_mode' (expected 'jsonrpc' or 'mcp_tools')"
            )

        def _num(name: str, default: float) -> float:
            v = s.get(name, default)
            if isinstance(v, bool):
                raise RuntimeError(f"MCP servers[{idx}] invalid '{name}' (number expected)")
            if isinstance(v, (int, float)):
                return float(v)
            raise RuntimeError(f"MCP servers[{idx}] invalid '{name}' (number expected)")

        def _int(name: str, default: int) -> int:
            v = s.get(name, default)
            if isinstance(v, bool):
                raise RuntimeError(f"MCP servers[{idx}] invalid '{name}' (int expected)")
            if isinstance(v, int):
                return int(v)
            raise RuntimeError(f"MCP servers[{idx}] invalid '{name}' (int expected)")

        timeout_seconds = _num("timeout_seconds", 30.0)
        if timeout_seconds <= 0:
            raise RuntimeError(f"MCP servers[{idx}] invalid 'timeout_seconds' (must be > 0)")
        max_retries = _int("max_retries", 3)
        if max_retries < 0:
            raise RuntimeError(f"MCP servers[{idx}] invalid 'max_retries' (must be >= 0)")
        backoff_initial_seconds = _num("backoff_initial_seconds", 0.5)
        if backoff_initial_seconds < 0:
            raise RuntimeError(
                f"MCP servers[{idx}] invalid 'backoff_initial_seconds' (must be >= 0)"
            )
        backoff_max_seconds = _num("backoff_max_seconds", 5.0)
        if backoff_max_seconds < 0:
            raise RuntimeError(f"MCP servers[{idx}] invalid 'backoff_max_seconds' (must be >= 0)")

        servers.append(
            MCPServerConfig(
                name=name,
                transport=transport,  # type: ignore[arg-type]
                command=command,
                url=url,
                kind=kind,  # type: ignore[arg-type]
                http_mode=http_mode,  # type: ignore[arg-type]
                timeout_seconds=timeout_seconds,
                max_retries=max_retries,
                backoff_initial_seconds=backoff_initial_seconds,
                backoff_max_seconds=backoff_max_seconds,
            )
        )

    return MCPConfig(servers=servers)


def to_jsonable(obj: Any) -> Any:
    """
    Best-effort conversion of tool results into JSON-serializable primitives.
    """
    if obj is None or isinstance(obj, (bool, int, float, str)):
        return obj
    if isinstance(obj, dict):
        return {str(k): to_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [to_jsonable(v) for v in obj]
    return str(obj)


