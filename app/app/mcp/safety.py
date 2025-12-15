from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, Iterable, Tuple


PATH_LIKE_KEYS = {
    "path",
    "file_path",
    "filepath",
    "filename",
    "directory",
    "dir",
    "target",
}


def _is_within_root(root: Path, candidate: Path) -> bool:
    try:
        candidate.relative_to(root)
        return True
    except Exception:
        return False


def resolve_and_validate_path(workspace_root: Path, raw: str) -> Path:
    """
    Resolve a user-provided path and ensure it stays within `workspace_root`.

    - Relative paths are resolved against workspace_root.
    - Absolute paths are allowed only if they are inside workspace_root.
    - Any '..' escaping is rejected by the `relative_to` check after resolve().
    """
    root = workspace_root.resolve()
    p = Path(raw)
    if not p.is_absolute():
        candidate = (root / p).resolve()
    else:
        candidate = p.resolve()
    if not _is_within_root(root, candidate):
        raise RuntimeError(f"Path escapes WORKSPACE_ROOT: {raw}")
    return candidate


def iter_path_args(arguments: Any) -> Iterable[Tuple[str, str]]:
    """
    Yield (key, value) for any dict entries that look like path parameters.
    """
    if isinstance(arguments, dict):
        for k, v in arguments.items():
            key = str(k)
            if isinstance(v, str) and key.lower() in PATH_LIKE_KEYS:
                yield (key, v)
            else:
                yield from iter_path_args(v)
    elif isinstance(arguments, list):
        for item in arguments:
            yield from iter_path_args(item)


def guard_filesystem_tool_args(workspace_root: Path, tool_name: str, arguments: Dict[str, Any]) -> None:
    """
    Enforce workspace-root restriction for filesystem-like tools.

    We don't assume a specific tool schema; we scan for path-ish keys.
    """
    if not arguments:
        return
    for key, raw in iter_path_args(arguments):
        _ = resolve_and_validate_path(workspace_root, raw)


def guard_fetch_tool_result(tool_name: str, result: Any) -> None:
    """
    Validate fetch-like tool outputs (best-effort).

    External MCP fetch servers differ, so this is intentionally tolerant:
    - If a status/statusCode field is present, require 2xx.
    - If ok is present, require truthy.
    """
    def walk(obj: Any) -> None:
        if isinstance(obj, dict):
            status = obj.get("status", obj.get("statusCode"))
            if isinstance(status, int) and not (200 <= status <= 299):
                raise RuntimeError(f"Fetch tool returned non-2xx status: {status}")
            ok = obj.get("ok")
            if ok is False:
                raise RuntimeError("Fetch tool returned ok=false")
            for v in obj.values():
                walk(v)
        elif isinstance(obj, list):
            for v in obj:
                walk(v)

    walk(result)


