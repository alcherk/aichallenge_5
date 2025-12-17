from __future__ import annotations

import asyncio
import json
import logging
import os
import random
import time
from typing import Any, Dict, List, Optional, Tuple

import httpx

logger = logging.getLogger("app.mcp_http")


def _now_ms() -> float:
    return time.time() * 1000.0


def _join_url(base: str, path: str) -> str:
    return f"{base.rstrip('/')}/{path.lstrip('/')}"


def _json_preview(value: Any, *, limit: int = 4000) -> Tuple[str, bool]:
    """
    Best-effort JSON preview string for logs.
    Returns (preview, truncated).
    """
    try:
        s = json.dumps(value, ensure_ascii=False, sort_keys=True)
    except Exception:
        s = str(value)
    if len(s) > limit:
        return (s[:limit] + "…", True)
    return (s, False)

def _truthy_env(name: str) -> bool:
    v = (os.getenv(name, "") or "").strip().lower()
    return v in {"1", "true", "yes", "y", "on"}


class MCPHttpToolsSession:
    """
    MCP-over-HTTP tools session (non-JSON-RPC).

    Server contract (verified from the companion mcp_server project):
      - GET  /mcp/tools -> list[ {name, description, inputSchema, outputSchema} ]
      - POST /mcp/tools/call with {name, arguments, requestId?} -> {content, isError, requestId}
    """

    def __init__(
        self,
        base_url: str,
        *,
        server_name: str,
        timeout_seconds: float = 30.0,
        max_retries: int = 3,
        backoff_initial_seconds: float = 0.5,
        backoff_max_seconds: float = 5.0,
        client: Optional[httpx.AsyncClient] = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._server_name = server_name

        self._timeout_seconds = float(timeout_seconds)
        self._max_retries = int(max_retries)
        self._backoff_initial_seconds = float(backoff_initial_seconds)
        self._backoff_max_seconds = float(backoff_max_seconds)

        self._client_external = client is not None
        self._client = client or httpx.AsyncClient(timeout=httpx.Timeout(self._timeout_seconds))

    async def initialize(self) -> None:
        # No initialize handshake for this flavor; tools endpoints are ready immediately.
        return

    async def list_tools(self) -> List[Dict[str, Any]]:
        url = _join_url(self._base_url, "/mcp/tools")
        start = _now_ms()
        resp = await self._request_with_retries("GET", url, json_body=None)
        duration_ms = _now_ms() - start

        tools_raw = resp.json()
        if not isinstance(tools_raw, list):
            raise RuntimeError("MCP HTTP tools endpoint expected a JSON array")
        tools: List[Dict[str, Any]] = [t for t in tools_raw if isinstance(t, dict)]

        tool_names = []
        for t in tools:
            name = t.get("name")
            if isinstance(name, str) and name:
                tool_names.append(name)

        logger.info(
            json.dumps(
                {
                    "event": "tools_list",
                    "server": self._server_name,
                    "url": url,
                    "count": len(tools),
                    "names": tool_names,
                    "duration_ms": round(duration_ms, 2),
                },
                ensure_ascii=False,
            )
        )
        # Detailed payload (debug by default; can be promoted to info via MCP_LOG_VERBOSE=1).
        preview, truncated = _json_preview(tools_raw)
        (logger.info if _truthy_env("MCP_LOG_VERBOSE") else logger.debug)(
            json.dumps(
                {
                    "event": "tools_list_payload",
                    "server": self._server_name,
                    "url": url,
                    "duration_ms": round(duration_ms, 2),
                    "truncated": truncated,
                    "payload": preview,
                },
                ensure_ascii=False,
            )
        )
        return tools

    async def call_tool(self, name: str, arguments: Dict[str, Any]) -> Any:
        url = _join_url(self._base_url, "/mcp/tools/call")
        req_id = f"{int(time.time() * 1000)}-{random.randint(1000, 9999)}"
        # Defensive arg normalization for known weather tools.
        # Some deployments appear to mis-handle `timezone` (treating it as forecast_days),
        # so omit timezone; it is optional and default exists server-side.
        call_args: Dict[str, Any] = dict(arguments or {})
        if name in ("weather.get_current", "weather.get_forecast"):
            call_args.pop("timezone", None)
            # Some deployments expect `forecast_days` even for current weather.
            # Ensure it's present AND an int. If invalid/unparseable, force to 1.
            fd = call_args.get("forecast_days", None)
            if isinstance(fd, bool) or fd is None:
                call_args["forecast_days"] = 1
            elif isinstance(fd, int):
                # keep as-is
                pass
            else:
                try:
                    if isinstance(fd, float):
                        call_args["forecast_days"] = int(fd)
                    elif isinstance(fd, str) and fd.strip().isdigit():
                        call_args["forecast_days"] = int(fd.strip())
                    else:
                        # Anything else (e.g. timezone string) -> force to 1
                        call_args["forecast_days"] = 1
                except Exception:
                    call_args["forecast_days"] = 1
        else:
            # For other tools, if forecast_days is present but not an int, try best-effort coercion.
            if "forecast_days" in call_args and not isinstance(call_args.get("forecast_days"), int):
                v = call_args.get("forecast_days")
                try:
                    if isinstance(v, float):
                        call_args["forecast_days"] = int(v)
                    elif isinstance(v, str) and v.strip().isdigit():
                        call_args["forecast_days"] = int(v.strip())
                except Exception:
                    pass

        body = {"name": name, "arguments": call_args, "requestId": req_id}

        # Log the outbound request parameters (debug by default; promotable via MCP_LOG_VERBOSE=1).
        body_preview, body_truncated = _json_preview(body)
        (logger.info if _truthy_env("MCP_LOG_VERBOSE") else logger.debug)(
            json.dumps(
                {
                    "event": "tool_call_request",
                    "server": self._server_name,
                    "tool": name,
                    "url": url,
                    "truncated": body_truncated,
                    "body": body_preview,
                },
                ensure_ascii=False,
            )
        )

        start = _now_ms()
        resp = await self._request_with_retries("POST", url, json_body=body)
        duration_ms = _now_ms() - start

        payload = resp.json()
        if not isinstance(payload, dict):
            raise RuntimeError("MCP tools/call expected a JSON object response")

        parsed = self._parse_tool_call_response(payload)

        # Detailed MCP response (debug by default; can be promoted to info via MCP_LOG_VERBOSE=1).
        payload_preview, payload_truncated = _json_preview(payload)
        parsed_preview, parsed_truncated = _json_preview(parsed)
        args_preview, args_truncated = _json_preview(call_args or {})
        (logger.info if _truthy_env("MCP_LOG_VERBOSE") else logger.debug)(
            json.dumps(
                {
                    "event": "tool_call_response",
                    "server": self._server_name,
                    "tool": name,
                    "requestId": req_id,
                    "url": url,
                    "duration_ms": round(duration_ms, 2),
                    "args_truncated": args_truncated,
                    "args": args_preview,
                    "payload_truncated": payload_truncated,
                    "payload": payload_preview,
                    "parsed_truncated": parsed_truncated,
                    "parsed": parsed_preview,
                },
                ensure_ascii=False,
            )
        )

        logger.info(
            json.dumps(
                {
                    "event": "tool_call",
                    "server": self._server_name,
                    "tool": name,
                    "url": url,
                    "duration_ms": round(duration_ms, 2),
                    "is_error": bool(parsed.get("isError")),
                },
                ensure_ascii=False,
            )
        )
        return parsed

    async def aclose(self) -> None:
        if self._client_external:
            return
        await self._client.aclose()

    def _parse_tool_call_response(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normalize MCP response to a JSONable dict suitable for LLM tool output.
        """
        content = payload.get("content") or []
        is_error = bool(payload.get("isError") is True)
        request_id = payload.get("requestId")

        text: Optional[str] = None
        data: Optional[Dict[str, Any]] = None
        if isinstance(content, list):
            for item in content:
                if not isinstance(item, dict):
                    continue
                t = item.get("type")
                if text is None and t == "text" and isinstance(item.get("text"), str):
                    text = item["text"]
                if data is None and t == "json" and isinstance(item.get("data"), dict):
                    data = item["data"]

        return {
            "isError": is_error,
            "text": text,
            "data": data,
            "requestId": request_id,
            "raw": payload,
        }

    def _should_retry(self, exc: Optional[BaseException], response: Optional[httpx.Response]) -> bool:
        if exc is not None:
            return isinstance(exc, (httpx.TimeoutException, httpx.TransportError))
        if response is None:
            return False
        # Retry transient server-side failures; do NOT retry normal 4xx.
        if response.status_code >= 500:
            return True
        if response.status_code == 429:
            return True
        return False

    def _retry_delay(self, attempt: int) -> float:
        """
        Exponential backoff with jitter.
        attempt is 0-based (0 = first retry wait).
        """
        base = self._backoff_initial_seconds * (2**attempt)
        base = min(base, self._backoff_max_seconds)
        jitter = random.random() * min(0.25, base)  # cap jitter to keep predictable
        return base + jitter

    async def _request_with_retries(
        self, method: str, url: str, *, json_body: Optional[Dict[str, Any]]
    ) -> httpx.Response:
        attempts_total = max(1, self._max_retries + 1)
        last_exc: Optional[BaseException] = None
        last_resp: Optional[httpx.Response] = None

        for attempt in range(attempts_total):
            last_exc = None
            last_resp = None
            started = _now_ms()
            try:
                if method.upper() == "GET":
                    resp = await self._client.get(url)
                else:
                    resp = await self._client.request(method.upper(), url, json=json_body)
                last_resp = resp

                if resp.status_code >= 400 and self._should_retry(None, resp) and attempt < attempts_total - 1:
                    delay = self._retry_delay(attempt)
                    logger.warning(
                        json.dumps(
                            {
                                "event": "http_retry",
                                "server": self._server_name,
                                "url": url,
                                "method": method.upper(),
                                "attempt": attempt + 1,
                                "status_code": resp.status_code,
                                "delay_seconds": round(delay, 3),
                                "duration_ms": round(_now_ms() - started, 2),
                            },
                            ensure_ascii=False,
                        )
                    )
                    await asyncio.sleep(delay)
                    continue

                if resp.status_code >= 400 and not self._should_retry(None, resp):
                    # Helpful details for debugging non-retriable failures (truncated).
                    body_preview, body_truncated = _json_preview(
                        resp.text if hasattr(resp, "text") else "<no body>"
                    )
                    logger.error(
                        json.dumps(
                            {
                                "event": "http_error",
                                "server": self._server_name,
                                "url": url,
                                "method": method.upper(),
                                "status_code": resp.status_code,
                                "duration_ms": round(_now_ms() - started, 2),
                                "body_truncated": body_truncated,
                                "body": body_preview,
                            },
                            ensure_ascii=False,
                        )
                    )

                resp.raise_for_status()
                return resp
            except Exception as e:
                last_exc = e
                if attempt < attempts_total - 1 and self._should_retry(e, None):
                    delay = self._retry_delay(attempt)
                    logger.warning(
                        json.dumps(
                            {
                                "event": "http_retry",
                                "server": self._server_name,
                                "url": url,
                                "method": method.upper(),
                                "attempt": attempt + 1,
                                "error_type": type(e).__name__,
                                "delay_seconds": round(delay, 3),
                                "duration_ms": round(_now_ms() - started, 2),
                            },
                            ensure_ascii=False,
                        )
                    )
                    await asyncio.sleep(delay)
                    continue
                break

        if last_resp is not None:
            # Raise a useful HTTP error
            last_resp.raise_for_status()
        if last_exc is not None:
            raise last_exc
        raise RuntimeError("HTTP request failed without an exception or response")


