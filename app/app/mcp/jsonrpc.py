from __future__ import annotations

import itertools
from dataclasses import dataclass
from typing import Any, Dict, Optional


_id_counter = itertools.count(1)


def next_id() -> int:
    return next(_id_counter)


@dataclass(frozen=True)
class JSONRPCError(Exception):
    code: int
    message: str
    data: Optional[Any] = None

    def __str__(self) -> str:
        if self.data is None:
            return f"JSONRPCError(code={self.code}, message={self.message})"
        return f"JSONRPCError(code={self.code}, message={self.message}, data={self.data})"


def build_request(method: str, params: Optional[Dict[str, Any]] = None, *, request_id: int) -> Dict[str, Any]:
    req: Dict[str, Any] = {"jsonrpc": "2.0", "id": request_id, "method": method}
    if params is not None:
        req["params"] = params
    return req


def build_notification(method: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    notif: Dict[str, Any] = {"jsonrpc": "2.0", "method": method}
    if params is not None:
        notif["params"] = params
    return notif


def parse_response(payload: Dict[str, Any]) -> Any:
    """
    Parse a JSON-RPC response object.
    """
    if "error" in payload and payload["error"] is not None:
        err = payload["error"]
        if isinstance(err, dict):
            raise JSONRPCError(
                code=int(err.get("code", -32000)),
                message=str(err.get("message", "Unknown error")),
                data=err.get("data"),
            )
        raise JSONRPCError(code=-32000, message=str(err))
    return payload.get("result")


