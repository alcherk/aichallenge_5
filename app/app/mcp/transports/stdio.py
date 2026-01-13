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
        import logging
        logger = logging.getLogger("app.mcp.transport")
        logger.info(f"Starting MCP stdio server: {' '.join(self._command)}")
        
        self._proc = await asyncio.create_subprocess_exec(
            *self._command,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        assert self._proc.stdout is not None
        assert self._proc.stderr is not None
        logger.info(f"MCP stdio server started: PID={self._proc.pid}")
        
        self._reader_task = asyncio.create_task(self._reader_loop(self._proc.stdout))

    async def _reader_loop(self, stdout: asyncio.StreamReader) -> None:
        import logging
        logger = logging.getLogger("app.mcp.transport")
        
        # Also read stderr for debugging - this is critical for git_server logs
        if self._proc and self._proc.stderr:
            async def stderr_reader():
                try:
                    while True:
                        line = await self._proc.stderr.readline()
                        if not line:
                            logger.debug("MCP server stderr closed")
                            break
                        stderr_text = line.decode('utf-8', errors='replace').strip()
                        if stderr_text:
                            # Log stderr as INFO so it's always visible
                            logger.info(f"MCP server stderr: {stderr_text}")
                except Exception as e:
                    logger.warning(f"Error reading MCP stderr: {e}")
            
            # Start stderr reader in background
            asyncio.create_task(stderr_reader())
        
        buffer = b""
        max_buffer_size = 50 * 1024 * 1024  # 50MB max buffer to prevent memory issues
        while True:
            # Read in chunks to handle large responses
            # Use larger chunks for better performance with large responses
            chunk = await stdout.read(64 * 1024)  # 64KB chunks
            if not chunk:
                if buffer:
                    # Try to process remaining buffer as final message
                    if buffer.strip():
                        try:
                            line_text = buffer.decode("utf-8", errors="replace").strip()
                            msg = json.loads(line_text)
                            if isinstance(msg, dict):
                                msg_id = msg.get("id")
                                if isinstance(msg_id, int) and msg_id in self._pending:
                                    fut = self._pending.pop(msg_id)
                                    if not fut.done():
                                        fut.set_result(msg)
                                        logger.info(f"MCP response received (final buffer) for request id {msg_id}, response_size={len(line_text)} bytes")
                        except Exception as e:
                            logger.warning(f"MCP stdio stdout closed with unprocessed buffer: {e}")
                    else:
                        logger.warning("MCP stdio stdout closed with unprocessed buffer")
                else:
                    logger.warning("MCP stdio stdout closed unexpectedly")
                break
            
            buffer += chunk
            
            # Safety check: prevent buffer from growing too large
            if len(buffer) > max_buffer_size:
                logger.error(f"MCP buffer exceeded max size ({max_buffer_size} bytes), clearing")
                buffer = b""
                continue
            
            # Process complete lines (newline-delimited JSON)
            while b"\n" in buffer:
                line, buffer = buffer.split(b"\n", 1)
                if not line.strip():
                    continue
                    
                try:
                    line_text = line.decode("utf-8", errors="replace").strip()
                    msg = json.loads(line_text)
                except json.JSONDecodeError as e:
                    # For large responses, log more details
                    if len(line) > 10000:
                        logger.warning(f"Failed to parse large MCP message: {e}, line_len={len(line)}, error_pos={e.pos if hasattr(e, 'pos') else 'unknown'}")
                    else:
                        logger.debug(f"Failed to parse MCP message: {e}, line_len={len(line)}, preview={line[:100]}")
                    continue
                except Exception as e:
                    logger.debug(f"Failed to decode MCP message: {e}, line_len={len(line)}, preview={line[:100]}")
                    continue
                    
                if not isinstance(msg, dict):
                    logger.debug(f"MCP message is not a dict: {type(msg)}")
                    continue
                    
                msg_id = msg.get("id")
                if isinstance(msg_id, int) and msg_id in self._pending:
                    fut = self._pending.pop(msg_id)
                    if not fut.done():
                        fut.set_result(msg)
                        logger.info(f"MCP response received for request id {msg_id}, response_size={len(line_text)} bytes")
                    continue
                # Notifications or unknown responses are ignored.
                logger.debug(f"MCP message with id {msg_id} not in pending requests (pending: {list(self._pending.keys())})")

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
        import logging
        logger = logging.getLogger("app.mcp.transport")
        
        if self._proc is None:
            await self.start()

        rid = next_id()
        loop = asyncio.get_running_loop()
        fut: asyncio.Future[Dict[str, Any]] = loop.create_future()
        self._pending[rid] = fut
        
        request_data = build_request(method, params, request_id=rid)
        logger.debug(f"Sending MCP request id={rid}, method={method}, params={params}")
        await self._write_json_line(request_data)
        
        # Add timeout to prevent hanging (30 seconds default)
        try:
            result = await asyncio.wait_for(fut, timeout=30.0)
            logger.debug(f"MCP request id={rid} completed successfully")
            return result
        except asyncio.TimeoutError:
            # Remove from pending to avoid memory leak
            self._pending.pop(rid, None)
            logger.error(f"MCP stdio request timeout: method={method}, id={rid}, pending={list(self._pending.keys())}")
            # Check if process is still alive
            if self._proc:
                returncode = self._proc.returncode
                logger.error(f"MCP process status: returncode={returncode}, PID={self._proc.pid}")
            raise RuntimeError(f"MCP stdio request timeout: {method} after 30s")

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


