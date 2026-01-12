"""Built-in MCP Git server (stdio)."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, Optional


def _jsonrpc_result(req_id: Any, result: Any) -> Dict[str, Any]:
    return {"jsonrpc": "2.0", "id": req_id, "result": result}


def _jsonrpc_error(req_id: Any, code: int, message: str, data: Any = None) -> Dict[str, Any]:
    err: Dict[str, Any] = {"code": code, "message": message}
    if data is not None:
        err["data"] = data
    return {"jsonrpc": "2.0", "id": req_id, "error": err}


def _run_git(repo_root: Path, *args: str) -> tuple[str, int]:
    """Run git command and return (stdout, returncode)."""
    try:
        result = subprocess.run(
            ["git"] + list(args),
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=10,
        )
        return result.stdout.strip(), result.returncode
    except subprocess.TimeoutExpired:
        return "Command timeout", 1
    except FileNotFoundError:
        return "git command not found", 1
    except Exception as e:
        return f"Error: {str(e)}", 1


def _tool_list() -> Dict[str, Any]:
    return {
        "tools": [
            {
                "name": "git_status",
                "description": "Get current git repository status (branch, modified files, staged/unstaged changes).",
                "inputSchema": {
                    "type": "object",
                    "properties": {},
                    "required": [],
                    "additionalProperties": False,
                },
            },
            {
                "name": "git_branch",
                "description": "Get current git branch and list of all branches.",
                "inputSchema": {
                    "type": "object",
                    "properties": {},
                    "required": [],
                    "additionalProperties": False,
                },
            },
            {
                "name": "git_diff",
                "description": "Get git diff for a specific file or commit.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "File path (optional, if not provided shows all changes)"},
                        "commit": {"type": "string", "description": "Commit hash (optional, if not provided shows working tree diff)"},
                    },
                    "required": [],
                    "additionalProperties": False,
                },
            },
            {
                "name": "git_log",
                "description": "Get git commit history (last N commits).",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "limit": {"type": "integer", "description": "Number of commits to return (default: 10)"},
                    },
                    "required": [],
                    "additionalProperties": False,
                },
            },
            {
                "name": "git_file_status",
                "description": "Get git status for a specific file (staged, modified, untracked, etc.).",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "File path relative to repository root"},
                    },
                    "required": ["path"],
                    "additionalProperties": False,
                },
            },
        ]
    }


def _call_tool(repo_root: Path, name: str, arguments: Dict[str, Any]) -> Any:
    if name == "git_status":
        stdout, returncode = _run_git(repo_root, "status", "--porcelain", "-b")
        if returncode != 0:
            return {"error": stdout, "is_git_repo": False}
        
        # Parse status output
        lines = stdout.split("\n") if stdout else []
        branch_line = lines[0] if lines else ""
        branch = branch_line.replace("## ", "").split("...")[0] if branch_line.startswith("##") else "unknown"
        
        modified = []
        staged = []
        untracked = []
        
        for line in lines[1:]:
            if not line.strip():
                continue
            status = line[:2]
            filepath = line[3:]
            if status[0] == "?":
                untracked.append(filepath)
            elif status[0] != " ":
                staged.append(filepath)
            else:
                modified.append(filepath)
        
        return {
            "branch": branch,
            "modified_files": modified,
            "staged_files": staged,
            "untracked_files": untracked,
            "is_git_repo": True,
        }
    
    if name == "git_branch":
        stdout, returncode = _run_git(repo_root, "branch", "-a")
        if returncode != 0:
            return {"error": stdout, "is_git_repo": False}
        
        current_stdout, _ = _run_git(repo_root, "branch", "--show-current")
        current_branch = current_stdout.strip() if current_stdout else "unknown"
        
        branches = [b.strip().replace("* ", "") for b in stdout.split("\n") if b.strip()]
        
        return {
            "current_branch": current_branch,
            "all_branches": branches,
            "is_git_repo": True,
        }
    
    if name == "git_diff":
        path = arguments.get("path")
        commit = arguments.get("commit")
        
        if commit:
            if path:
                stdout, returncode = _run_git(repo_root, "diff", commit, "--", path)
            else:
                stdout, returncode = _run_git(repo_root, "diff", commit)
        else:
            if path:
                stdout, returncode = _run_git(repo_root, "diff", "--", path)
            else:
                stdout, returncode = _run_git(repo_root, "diff")
        
        if returncode != 0:
            return {"error": stdout, "diff": ""}
        
        return {
            "diff": stdout,
            "path": path,
            "commit": commit,
        }
    
    if name == "git_log":
        limit = arguments.get("limit", 10)
        stdout, returncode = _run_git(
            repo_root,
            "log",
            f"-{limit}",
            "--pretty=format:%H|%an|%ae|%ad|%s",
            "--date=iso",
        )
        if returncode != 0:
            return {"error": stdout, "commits": []}
        
        commits = []
        for line in stdout.split("\n"):
            if not line.strip():
                continue
            parts = line.split("|", 4)
            if len(parts) == 5:
                commits.append({
                    "hash": parts[0],
                    "author": parts[1],
                    "email": parts[2],
                    "date": parts[3],
                    "message": parts[4],
                })
        
        return {"commits": commits, "limit": limit}
    
    if name == "git_file_status":
        path = str(arguments.get("path", ""))
        if not path:
            raise RuntimeError("path is required")
        
        # Check if file exists
        file_path = repo_root / path
        if not file_path.exists():
            return {"path": path, "status": "not_found", "is_git_repo": True}
        
        # Get status
        stdout, returncode = _run_git(repo_root, "status", "--porcelain", "--", path)
        if returncode != 0:
            return {"path": path, "status": "error", "error": stdout}
        
        if not stdout.strip():
            # File is tracked and clean
            return {"path": path, "status": "clean", "is_git_repo": True}
        
        status_code = stdout[:2]
        if status_code[0] == "?":
            return {"path": path, "status": "untracked", "is_git_repo": True}
        elif status_code[0] != " ":
            return {"path": path, "status": "staged", "is_git_repo": True}
        else:
            return {"path": path, "status": "modified", "is_git_repo": True}
    
    raise RuntimeError(f"unknown tool: {name}")


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Built-in MCP Git server (stdio).")
    parser.add_argument("--root", required=True, help="Repository root for git operations")
    args = parser.parse_args(argv)
    
    repo_root = Path(args.root).resolve()
    
    # Check if it's a git repository
    _, returncode = _run_git(repo_root, "rev-parse", "--git-dir")
    if returncode != 0:
        # Not a git repo, but continue anyway (will return errors in tool calls)
        pass
    
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except Exception:
            continue
        if not isinstance(msg, dict):
            continue
        
        req_id = msg.get("id")
        method = msg.get("method")
        params = msg.get("params") or {}
        
        # Notifications have no id; ignore.
        if req_id is None:
            continue
        
        try:
            if method == "initialize":
                result = {
                    "serverInfo": {"name": "builtin_git", "version": "0.1"},
                    "capabilities": {"tools": {}},
                }
                out = _jsonrpc_result(req_id, result)
            elif method == "tools/list":
                out = _jsonrpc_result(req_id, _tool_list())
            elif method == "tools/call":
                name = str(params.get("name") or "")
                arguments = params.get("arguments") or {}
                if not isinstance(arguments, dict):
                    arguments = {}
                out = _jsonrpc_result(req_id, _call_tool(repo_root, name, arguments))
            else:
                out = _jsonrpc_error(req_id, -32601, f"Method not found: {method}")
        except Exception as e:
            out = _jsonrpc_error(req_id, -32000, str(e))
        
        sys.stdout.write(json.dumps(out, ensure_ascii=False) + "\n")
        sys.stdout.flush()
    
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
