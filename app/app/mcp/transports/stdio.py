from __future__ import annotations

import asyncio
import json
from typing import Any, Dict, Optional

from ..jsonrpc import build_notification, build_request, next_id
from .base import MCPTransport


class StdioTransport(MCPTransport):
    """
    JSON-RPC over stdio (newline-delimited JSON).

    This is the common transport for local MCP servers started as subprocesses.
    """

    def __init__(self, command: list[str]) -> None:
        self._command = command
        self._proc: Optional[asyncio.subprocess.Process] = None
        self._pending: dict[int, asyncio.Future[Dict[str, Any]]] = {}
        self._reader_task: Optional[asyncio.Task] = None
        self._write_lock = asyncio.Lock()

    async def start(self) -> None:
        if self._proc is not None:
            return
        self._proc = await asyncio.create_subprocess_exec(
            *self._command,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        assert self._proc.stdout is not None
        self._reader_task = asyncio.create_task(self._reader_loop(self._proc.stdout))

    async def _reader_loop(self, stdout: asyncio.StreamReader) -> None:
        while True:
            line = await stdout.readline()
            if not line:
                break
            try:
                msg = json.loads(line.decode("utf-8", errors="replace").strip())
            except Exception:
                continue
            if not isinstance(msg, dict):
                continue
            msg_id = msg.get("id")
            if isinstance(msg_id, int) and msg_id in self._pending:
                fut = self._pending.pop(msg_id)
                if not fut.done():
                    fut.set_result(msg)
                continue
            # Notifications or unknown responses are ignored.

        # If we exit the loop, fail all pending requests.
        for fut in list(self._pending.values()):
            if not fut.done():
                fut.set_exception(RuntimeError("MCP stdio server closed"))
        self._pending.clear()

    async def _write_json_line(self, obj: Dict[str, Any]) -> None:
        if self._proc is None:
            await self.start()
        assert self._proc is not None
        assert self._proc.stdin is not None
        data = (json.dumps(obj, ensure_ascii=False) + "\n").encode("utf-8")
        async with self._write_lock:
            self._proc.stdin.write(data)
            await self._proc.stdin.drain()

    async def request(self, method: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        if self._proc is None:
            await self.start()

        rid = next_id()
        loop = asyncio.get_running_loop()
        fut: asyncio.Future[Dict[str, Any]] = loop.create_future()
        self._pending[rid] = fut
        await self._write_json_line(build_request(method, params, request_id=rid))
        return await fut

    async def notify(self, method: str, params: Optional[Dict[str, Any]] = None) -> None:
        if self._proc is None:
            await self.start()
        await self._write_json_line(build_notification(method, params))

    async def aclose(self) -> None:
        if self._reader_task is not None:
            self._reader_task.cancel()
        if self._proc is not None:
            try:
                self._proc.terminate()
            except Exception:
                pass
            self._proc = None
        for fut in list(self._pending.values()):
            if not fut.done():
                fut.cancel()
        self._pending.clear()


