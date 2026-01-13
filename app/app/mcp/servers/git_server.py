"""Built-in MCP Git server (stdio)."""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, Optional


def get_max_diff_size() -> int:
    """
    Get maximum diff size from environment variable.
    Default: 50KB (50 * 1024 bytes)
    Can be set via GIT_MCP_MAX_DIFF_SIZE environment variable (in bytes or with K/M suffix).
    Examples:
        GIT_MCP_MAX_DIFF_SIZE=100000  # 100KB
        GIT_MCP_MAX_DIFF_SIZE=500K    # 500KB
        GIT_MCP_MAX_DIFF_SIZE=1M      # 1MB
    """
    default_size = 50 * 1024  # 50KB default
    
    env_value = os.getenv("GIT_MCP_MAX_DIFF_SIZE", "").strip()
    if not env_value:
        return default_size
    
    try:
        # Handle suffixes: K (KB), M (MB)
        env_value_upper = env_value.upper()
        if env_value_upper.endswith("K"):
            size = int(float(env_value_upper[:-1]) * 1024)
        elif env_value_upper.endswith("M"):
            size = int(float(env_value_upper[:-1]) * 1024 * 1024)
        else:
            size = int(env_value)
        
        # Minimum 1KB, maximum 10MB
        size = max(1024, min(size, 10 * 1024 * 1024))
        return size
    except (ValueError, TypeError):
        print(f"[git_server] Invalid GIT_MCP_MAX_DIFF_SIZE value: {env_value}, using default {default_size}", file=sys.stderr, flush=True)
        return default_size


def _jsonrpc_result(req_id: Any, result: Any) -> Dict[str, Any]:
    return {"jsonrpc": "2.0", "id": req_id, "result": result}


def _jsonrpc_error(req_id: Any, code: int, message: str, data: Any = None) -> Dict[str, Any]:
    err: Dict[str, Any] = {"code": code, "message": message}
    if data is not None:
        err["data"] = data
    return {"jsonrpc": "2.0", "id": req_id, "error": err}


def _run_git(repo_root: Path, *args: str) -> tuple[str, int]:
    """Run git command and return (stdout, returncode)."""
    import time
    start_time = time.time()
    cmd_str = " ".join(args)
    
    try:
        print(f"[git_server] Executing git command: git {cmd_str}", file=sys.stderr, flush=True)
        print(f"[git_server] Working directory: {repo_root}", file=sys.stderr, flush=True)
        
        # Set environment to disable pager and colors
        env = os.environ.copy()
        env["GIT_PAGER"] = "cat"
        env["GIT_CONFIG_NOSYSTEM"] = "1"
        env["NO_COLOR"] = "1"
        
        result = subprocess.run(
            ["git"] + list(args),
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=10,
            env=env,
        )
        
        duration_ms = int((time.time() - start_time) * 1000)
        stdout_len = len(result.stdout) if result.stdout else 0
        stderr_len = len(result.stderr) if result.stderr else 0
        
        print(f"[git_server] Git command completed: git {cmd_str}", file=sys.stderr, flush=True)
        print(f"[git_server]   Duration: {duration_ms}ms", file=sys.stderr, flush=True)
        print(f"[git_server]   Return code: {result.returncode}", file=sys.stderr, flush=True)
        print(f"[git_server]   Stdout length: {stdout_len} bytes", file=sys.stderr, flush=True)
        if stderr_len > 0:
            print(f"[git_server]   Stderr length: {stderr_len} bytes", file=sys.stderr, flush=True)
            # Log first 200 chars of stderr if present
            stderr_preview = result.stderr[:200] if result.stderr else ""
            if stderr_preview:
                print(f"[git_server]   Stderr preview: {stderr_preview}", file=sys.stderr, flush=True)
        
        # Log first 500 chars of stdout for debugging (if not too long)
        if stdout_len > 0 and stdout_len < 10000:
            stdout_preview = result.stdout[:500] if result.stdout else ""
            if stdout_preview:
                print(f"[git_server]   Stdout preview: {stdout_preview}", file=sys.stderr, flush=True)
        elif stdout_len >= 10000:
            print(f"[git_server]   Stdout is large ({stdout_len} bytes), preview skipped", file=sys.stderr, flush=True)
        
        return result.stdout.strip(), result.returncode
    except subprocess.TimeoutExpired:
        duration_ms = int((time.time() - start_time) * 1000)
        print(f"[git_server] Git command TIMEOUT after {duration_ms}ms: git {cmd_str}", file=sys.stderr, flush=True)
        print(f"[git_server]   Working directory: {repo_root}", file=sys.stderr, flush=True)
        return "Command timeout", 1
    except FileNotFoundError:
        print(f"[git_server] Git command NOT FOUND: git executable not found in PATH", file=sys.stderr, flush=True)
        return "git command not found", 1
    except Exception as e:
        duration_ms = int((time.time() - start_time) * 1000)
        print(f"[git_server] Git command ERROR after {duration_ms}ms: git {cmd_str}", file=sys.stderr, flush=True)
        print(f"[git_server]   Error type: {type(e).__name__}", file=sys.stderr, flush=True)
        print(f"[git_server]   Error message: {str(e)}", file=sys.stderr, flush=True)
        import traceback
        traceback.print_exc(file=sys.stderr)
        return f"Error: {e}", 1
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
        
        # Log to stderr (won't interfere with JSON-RPC stdout)
        print(f"[git_server] git_diff called: path={path}, commit={commit}", file=sys.stderr, flush=True)
        
        try:
            # Build git diff command
            diff_args = []
            
            if commit:
                diff_args.append(commit)
                if path:
                    diff_args.extend(["--", path])
                    print(f"[git_server] Running: git diff {commit} -- {path}", file=sys.stderr, flush=True)
                else:
                    print(f"[git_server] Running: git diff {commit}", file=sys.stderr, flush=True)
            else:
                if path:
                    diff_args.extend(["--", path])
                    print(f"[git_server] Running: git diff -- {path}", file=sys.stderr, flush=True)
                else:
                    print(f"[git_server] Running: git diff (uncommitted)", file=sys.stderr, flush=True)
            
            stdout, returncode = _run_git(repo_root, "diff", *diff_args)
            
            # Limit diff size to prevent huge responses
            # Size limit is configurable via GIT_MCP_MAX_DIFF_SIZE environment variable
            max_diff_size = get_max_diff_size()
            original_len = len(stdout)
            if original_len > max_diff_size:
                print(f"[git_server] Diff truncated from {original_len} to {max_diff_size} bytes (limit from GIT_MCP_MAX_DIFF_SIZE)", file=sys.stderr, flush=True)
                stdout = stdout[:max_diff_size] + f"\n\n[... diff truncated, {original_len - max_diff_size} more bytes ...]"
            else:
                print(f"[git_server] Diff size {original_len} bytes is within limit {max_diff_size} bytes", file=sys.stderr, flush=True)
            
            print(f"[git_server] git diff completed: returncode={returncode}, stdout_len={len(stdout)} (original={original_len})", file=sys.stderr, flush=True)
            
            if returncode != 0:
                return {"error": stdout, "diff": ""}
            
            result = {
                "diff": stdout,
                "path": path,
                "commit": commit,
            }
            
            # Log result size for debugging
            import json as json_module
            result_json = json_module.dumps(result, ensure_ascii=False)
            print(f"[git_server] Result JSON size: {len(result_json)} bytes", file=sys.stderr, flush=True)
            
            return result
        except Exception as e:
            print(f"[git_server] git_diff error: {e}", file=sys.stderr, flush=True)
            raise
    
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
    # Set stdout to unbuffered mode to ensure large responses are sent immediately
    # This prevents buffering issues with large JSON responses
    sys.stdout.reconfigure(line_buffering=True)
    
    parser = argparse.ArgumentParser(description="Built-in MCP Git server (stdio).")
    parser.add_argument("--root", required=True, help="Repository root for git operations")
    args = parser.parse_args(argv)
    
    repo_root = Path(args.root).resolve()
    
    # Check if it's a git repository
    _, returncode = _run_git(repo_root, "rev-parse", "--git-dir")
    if returncode != 0:
        # Not a git repo, but continue anyway (will return errors in tool calls)
        print(f"[git_server] WARNING: Not a git repository: {repo_root}", file=sys.stderr, flush=True)
    else:
        print(f"[git_server] Git repository detected: {repo_root}", file=sys.stderr, flush=True)
    
    print(f"[git_server] Starting main loop, reading from stdin", file=sys.stderr, flush=True)
    
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        print(f"[git_server] Received line: {line[:200]}", file=sys.stderr, flush=True)
        try:
            msg = json.loads(line)
        except Exception as e:
            print(f"[git_server] Failed to parse JSON: {e}, line={line[:100]}", file=sys.stderr, flush=True)
            continue
        if not isinstance(msg, dict):
            print(f"[git_server] Message is not a dict: {type(msg)}", file=sys.stderr, flush=True)
            continue
        
        req_id = msg.get("id")
        method = msg.get("method")
        params = msg.get("params") or {}
        
        print(f"[git_server] Parsed message: id={req_id}, method={method}", file=sys.stderr, flush=True)
        
        # Notifications have no id; ignore.
        if req_id is None:
            print(f"[git_server] Ignoring notification (no id)", file=sys.stderr, flush=True)
            continue
        
        try:
            if method == "initialize":
                print(f"[git_server] Handling initialize request", file=sys.stderr, flush=True)
                result = {
                    "serverInfo": {"name": "builtin_git", "version": "0.1"},
                    "capabilities": {"tools": {}},
                }
                out = _jsonrpc_result(req_id, result)
            elif method == "tools/list":
                print(f"[git_server] Handling tools/list request", file=sys.stderr, flush=True)
                out = _jsonrpc_result(req_id, _tool_list())
            elif method == "tools/call":
                name = str(params.get("name") or "")
                arguments = params.get("arguments") or {}
                if not isinstance(arguments, dict):
                    arguments = {}
                print(f"[git_server] tools/call received: name={name}, arguments={arguments}", file=sys.stderr, flush=True)
                try:
                    result = _call_tool(repo_root, name, arguments)
                    print(f"[git_server] tools/call completed: name={name}, result_keys={list(result.keys()) if isinstance(result, dict) else 'not_dict'}", file=sys.stderr, flush=True)
                    out = _jsonrpc_result(req_id, result)
                except Exception as e:
                    print(f"[git_server] tools/call error: {e}", file=sys.stderr, flush=True)
                    import traceback
                    traceback.print_exc(file=sys.stderr)
                    raise
            else:
                print(f"[git_server] Unknown method: {method}", file=sys.stderr, flush=True)
                out = _jsonrpc_error(req_id, -32601, f"Method not found: {method}")
        except Exception as e:
            print(f"[git_server] Exception handling request: {e}", file=sys.stderr, flush=True)
            import traceback
            traceback.print_exc(file=sys.stderr)
            out = _jsonrpc_error(req_id, -32000, str(e))
        
        response_json = json.dumps(out, ensure_ascii=False)
        response_size = len(response_json)
        print(f"[git_server] Sending response: size={response_size} bytes, id={req_id}, preview={response_json[:200]}", file=sys.stderr, flush=True)
        
        # Write response and ensure it's flushed
        # For large responses, write in chunks to avoid blocking
        try:
            response_line = response_json + "\n"
            response_bytes = response_line.encode("utf-8")
            
            # For very large responses (>100KB), write in chunks
            chunk_size = 64 * 1024  # 64KB chunks
            if len(response_bytes) > chunk_size:
                print(f"[git_server] Writing large response in chunks: {len(response_bytes)} bytes", file=sys.stderr, flush=True)
                offset = 0
                while offset < len(response_bytes):
                    chunk = response_bytes[offset:offset + chunk_size]
                    written = sys.stdout.buffer.write(chunk)
                    sys.stdout.buffer.flush()
                    offset += written
                    print(f"[git_server] Written chunk: {written} bytes, total: {offset}/{len(response_bytes)}", file=sys.stderr, flush=True)
            else:
                # Small response - write all at once
                sys.stdout.write(response_line)
                sys.stdout.flush()
            
            # Verify the write completed
            print(f"[git_server] Response sent successfully: {response_size} bytes, id={req_id}", file=sys.stderr, flush=True)
        except BrokenPipeError:
            print(f"[git_server] ERROR: Broken pipe - client disconnected while sending response", file=sys.stderr, flush=True)
            # Don't raise - client is gone, nothing we can do
        except Exception as e:
            print(f"[git_server] ERROR sending response: {e}", file=sys.stderr, flush=True)
            import traceback
            traceback.print_exc(file=sys.stderr)
            # Still try to send error response if possible
            try:
                error_response = _jsonrpc_error(req_id, -32000, f"Error sending response: {str(e)}")
                sys.stdout.write(json.dumps(error_response, ensure_ascii=False) + "\n")
                sys.stdout.flush()
            except:
                pass
            raise
    
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
