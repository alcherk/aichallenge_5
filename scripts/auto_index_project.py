#!/usr/bin/env python3
"""Automatic project indexing script for RAG via Chunkenizer."""
import argparse
import asyncio
import fnmatch
import hashlib
import json
import logging
import signal
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple, Any

import httpx

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("auto_index")

# File patterns for indexing
INCLUDE_PATTERNS = [
    "*.py", "*.ts", "*.tsx", "*.js", "*.jsx",
    "*.md", "*.txt", "*.rst",
    "*.json", "*.yaml", "*.yml",
]

EXCLUDE_PATTERNS = [
    "*/node_modules/*", "*/__pycache__/*", "*/dist/*", "*/build/*",
    "*.pyc", "*.pyo", "*.log", "*.lock",
    "*/.venv/*", "*/venv/*", "*/ENV/*",
    "*/.git/*", "*/.vscode/*", "*/.idea/*",
    "*/.pytest_cache/*", "*/.mypy_cache/*", "*/.coverage",
    "*/.claude/*", "*/htmlcov/*",
]

# Directories to always exclude
EXCLUDE_DIRS = {
    ".venv", "venv", "ENV", ".git", ".vscode", ".idea",
    "__pycache__", "node_modules", "dist", "build",
    ".pytest_cache", ".mypy_cache", "htmlcov", ".claude",
    ".eggs", "*.egg-info", ".tox", ".coverage",
}

MAX_FILE_SIZE = 1024 * 1024  # 1MB


def get_file_hash(file_path: Path) -> str:
    """Calculate SHA256 hash of file content."""
    sha256 = hashlib.sha256()
    try:
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                sha256.update(chunk)
        return sha256.hexdigest()
    except Exception as e:
        logger.warning(f"Failed to hash {file_path}: {e}")
        return ""


def should_index_file(file_path: Path, repo_path: Path) -> bool:
    """Check if file should be indexed."""
    if not file_path.is_file():
        return False
    
    # Check file size
    try:
        if file_path.stat().st_size > MAX_FILE_SIZE:
            return False
    except Exception:
        return False
    
    # Check if file is empty
    try:
        if file_path.stat().st_size == 0:
            return False
    except Exception:
        return False
    
    # Check if matches include patterns
    matches_include = False
    try:
        rel_path = str(file_path.relative_to(repo_path))
    except ValueError:
        # File is outside repo path
        return False
    
    # Check if any parent directory is in exclude list
    for part in file_path.parts:
        if part in EXCLUDE_DIRS or part.startswith(".") and part != ".":
            # Additional check: allow .env.example, .gitignore, etc. but not .venv, .git
            if part in {".venv", ".git", ".pytest_cache", ".mypy_cache", ".claude"}:
                return False
    
    for pattern in INCLUDE_PATTERNS:
        # Use fnmatch for pattern matching
        if fnmatch.fnmatch(file_path.name, pattern) or fnmatch.fnmatch(rel_path, pattern):
            matches_include = True
            break
    
    if not matches_include:
        return False
    
    # Check if matches exclude patterns
    for pattern in EXCLUDE_PATTERNS:
        if fnmatch.fnmatch(rel_path, pattern) or fnmatch.fnmatch(file_path.name, pattern):
            return False
    
    return True


def get_files_to_index(repo_path: Path, git_tracked_only: bool = True) -> List[Path]:
    """Get list of files to index."""
    files = []
    
    if git_tracked_only:
        # Get only git-tracked files
        try:
            result = subprocess.run(
                ["git", "ls-files"],
                cwd=repo_path,
                capture_output=True,
                text=True,
                check=True,
            )
            git_files = result.stdout.strip().split("\n")
            for git_file in git_files:
                if not git_file.strip():
                    continue
                file_path = repo_path / git_file
                if file_path.exists() and should_index_file(file_path, repo_path):
                    files.append(file_path)
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to get git files: {e}")
            return []
        except FileNotFoundError:
            logger.warning("Git not found, falling back to directory scan")
            git_tracked_only = False
    
    if not git_tracked_only:
        # Scan directory recursively
        for file_path in repo_path.rglob("*"):
            if should_index_file(file_path, repo_path):
                files.append(file_path)
    
    # Remove duplicates and sort
    files = sorted(set(files))
    return files


def get_changed_files(repo_path: Path, since_commit: Optional[str] = None) -> Dict[str, List[str]]:
    """Get changed files since last commit."""
    changed = {"added": [], "modified": [], "deleted": []}
    
    try:
        if since_commit:
            # Get files changed since commit
            result = subprocess.run(
                ["git", "diff", "--name-status", since_commit, "HEAD"],
                cwd=repo_path,
                capture_output=True,
                text=True,
                check=True,
            )
        else:
            # Get files changed in working directory
            result = subprocess.run(
                ["git", "diff", "--name-status", "HEAD"],
                cwd=repo_path,
                capture_output=True,
                text=True,
                check=True,
            )
        
        for line in result.stdout.strip().split("\n"):
            if not line.strip():
                continue
            # git diff --name-status format: STATUS\tFILE_PATH
            parts = line.split("\t", 1)
            if len(parts) < 2:
                # Fallback: try space-separated
                parts = line.split(None, 1)
                if len(parts) < 2:
                    continue
            status = parts[0]
            file_path_str = parts[1].strip()
            file_path = repo_path / file_path_str
            
            if status.startswith("A"):  # Added
                if file_path.exists() and should_index_file(file_path, repo_path):
                    changed["added"].append(file_path_str)
            elif status.startswith("M"):  # Modified
                if file_path.exists() and should_index_file(file_path, repo_path):
                    changed["modified"].append(file_path_str)
            elif status.startswith("D"):  # Deleted
                changed["deleted"].append(file_path_str)
        
        # Also check for untracked files (only if not checking since commit)
        if not since_commit:
            try:
                untracked_result = subprocess.run(
                    ["git", "ls-files", "--others", "--exclude-standard"],
                    cwd=repo_path,
                    capture_output=True,
                    text=True,
                    check=True,
                )
                for untracked_file in untracked_result.stdout.strip().split("\n"):
                    if untracked_file.strip():
                        file_path = repo_path / untracked_file.strip()
                        if file_path.exists() and should_index_file(file_path, repo_path):
                            if untracked_file.strip() not in changed["added"]:
                                changed["added"].append(untracked_file.strip())
            except subprocess.CalledProcessError:
                pass
        
        # Also check for new commits
        if since_commit:
            try:
                result = subprocess.run(
                    ["git", "log", "--name-status", "--pretty=format:", f"{since_commit}..HEAD"],
                    cwd=repo_path,
                    capture_output=True,
                    text=True,
                    check=True,
                )
                for line in result.stdout.strip().split("\n"):
                    if not line.strip():
                        continue
                    # git log --name-status format: STATUS\tFILE_PATH
                    parts = line.split("\t", 1)
                    if len(parts) < 2:
                        # Fallback: try space-separated
                        parts = line.split(None, 1)
                        if len(parts) < 2:
                            continue
                    status = parts[0]
                    file_path_str = parts[1].strip()
                    
                    if status.startswith("A") and file_path_str not in changed["added"]:
                        file_path = repo_path / file_path_str
                        if file_path.exists() and should_index_file(file_path, repo_path):
                            changed["added"].append(file_path_str)
                    elif status.startswith("M") and file_path_str not in changed["modified"]:
                        file_path = repo_path / file_path_str
                        if file_path.exists() and should_index_file(file_path, repo_path):
                            changed["modified"].append(file_path_str)
                    elif status.startswith("D") and file_path_str not in changed["deleted"]:
                        changed["deleted"].append(file_path_str)
            except subprocess.CalledProcessError:
                pass
    
    except subprocess.CalledProcessError as e:
        logger.warning(f"Failed to get changed files: {e}")
    except FileNotFoundError:
        logger.warning("Git not found, cannot track changes")
    
    return changed


def get_current_commit(repo_path: Path) -> Optional[str]:
    """Get current HEAD commit hash."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()
    except Exception:
        return None


def get_file_type(file_path: Path) -> str:
    """Determine file type from extension."""
    ext = file_path.suffix.lower()
    type_map = {
        ".py": "python",
        ".ts": "typescript",
        ".tsx": "typescript",
        ".js": "javascript",
        ".jsx": "javascript",
        ".md": "markdown",
        ".txt": "text",
        ".rst": "restructuredtext",
        ".json": "json",
        ".yaml": "yaml",
        ".yml": "yaml",
    }
    return type_map.get(ext, "text")


async def ingest_file(
    file_path: Path,
    repo_path: Path,
    chunkenizer_url: str,
    force_reindex: bool = False,
) -> Dict[str, Any]:
    """Ingest a single file into Chunkenizer."""
    if not file_path.exists():
        return {"success": False, "error": f"File not found: {file_path}"}
    
    try:
        content = file_path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return {"success": False, "error": f"File is not UTF-8: {file_path}"}
    except Exception as e:
        return {"success": False, "error": f"Failed to read file: {e}"}
    
    file_hash = get_file_hash(file_path)
    file_type = get_file_type(file_path)
    rel_path = str(file_path.relative_to(repo_path))
    
    metadata = {
        "source": "project_code",
        "file_type": file_type,
        "file_path": rel_path,
        "file_hash": file_hash,
        "last_modified": datetime.now().isoformat(),
    }
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.post(
                f"{chunkenizer_url.rstrip('/')}/documents",
                files={"file": (file_path.name, content.encode("utf-8"), "text/plain")},
                data={
                    "metadata_json": json.dumps(metadata),
                    "force_reindex": str(force_reindex).lower(),
                },
            )
            response.raise_for_status()
            result = response.json()
            return {
                "success": True,
                "file": rel_path,
                "document_id": result.get("document_id"),
                "chunk_count": result.get("chunk_count", 0),
                "file_hash": file_hash,
            }
        except httpx.HTTPStatusError as e:
            return {
                "success": False,
                "file": rel_path,
                "error": f"HTTP {e.response.status_code}: {e.response.text[:200]}",
            }
        except Exception as e:
            return {
                "success": False,
                "file": rel_path,
                "error": str(e),
            }


def load_index_state(repo_path: Path) -> Dict[str, Any]:
    """Load index state from file."""
    state_file = repo_path / ".rag_index_state.json"
    if state_file.exists():
        try:
            with open(state_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load state: {e}")
    return {
        "last_commit_hash": None,
        "last_index_time": None,
        "indexed_files": {},
        "chunkenizer_url": None,
    }


def save_index_state(repo_path: Path, state: Dict[str, Any]) -> None:
    """Save index state to file."""
    state_file = repo_path / ".rag_index_state.json"
    try:
        with open(state_file, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error(f"Failed to save state: {e}")


async def full_scan(repo_path: Path, chunkenizer_url: str) -> None:
    """Perform full scan of all project files."""
    logger.info("Starting full scan of project files...")
    files = get_files_to_index(repo_path, git_tracked_only=False)
    logger.info(f"Found {len(files)} files to index")
    
    state = load_index_state(repo_path)
    state["chunkenizer_url"] = chunkenizer_url
    
    successful = 0
    failed = 0
    
    for i, file_path in enumerate(files, 1):
        rel_path = str(file_path.relative_to(repo_path))
        logger.info(f"[{i}/{len(files)}] Indexing: {rel_path}...")
        
        result = await ingest_file(file_path, repo_path, chunkenizer_url, force_reindex=True)
        
        if result["success"]:
            successful += 1
            state["indexed_files"][rel_path] = {
                "document_id": result.get("document_id"),
                "last_hash": result.get("file_hash"),
                "indexed_at": datetime.now().isoformat(),
            }
            logger.info(f"  ✓ ({result['chunk_count']} chunks)")
        else:
            failed += 1
            logger.error(f"  ✗ {result.get('error', 'Unknown error')}")
    
    state["last_index_time"] = datetime.now().isoformat()
    state["last_commit_hash"] = get_current_commit(repo_path)
    save_index_state(repo_path, state)
    
    logger.info(f"\nFull scan complete: {successful} successful, {failed} failed")


async def incremental_scan(repo_path: Path, chunkenizer_url: str) -> None:
    """Perform incremental scan of changed files."""
    logger.info("Starting incremental scan...")
    
    state = load_index_state(repo_path)
    if not state.get("last_commit_hash"):
        logger.info("No previous state found, performing full scan...")
        await full_scan(repo_path, chunkenizer_url)
        return
    
    current_commit = get_current_commit(repo_path)
    if current_commit == state.get("last_commit_hash"):
        logger.info("No new commits, checking working directory changes...")
        changed = get_changed_files(repo_path, since_commit=None)
    else:
        logger.info(f"New commits detected ({state['last_commit_hash'][:8]} -> {current_commit[:8]})")
        changed = get_changed_files(repo_path, since_commit=state["last_commit_hash"])
    
    if not any(changed.values()):
        logger.info("No changes detected")
        return
    
    state["chunkenizer_url"] = chunkenizer_url
    indexed_files = state.get("indexed_files", {})
    
    # Process added and modified files
    for file_path_str in changed["added"] + changed["modified"]:
        file_path = repo_path / file_path_str
        if not file_path.exists():
            continue
        
        file_hash = get_file_hash(file_path)
        existing = indexed_files.get(file_path_str)
        
        # Skip if file hasn't changed
        if existing and existing.get("last_hash") == file_hash:
            logger.debug(f"Skipping unchanged file: {file_path_str}")
            continue
        
        logger.info(f"Indexing: {file_path_str}...")
        result = await ingest_file(file_path, repo_path, chunkenizer_url, force_reindex=True)
        
        if result["success"]:
            indexed_files[file_path_str] = {
                "document_id": result.get("document_id"),
                "last_hash": result.get("file_hash"),
                "indexed_at": datetime.now().isoformat(),
            }
            logger.info(f"  ✓ ({result['chunk_count']} chunks)")
        else:
            logger.error(f"  ✗ {result.get('error', 'Unknown error')}")
    
    # Process deleted files (remove from state, note: Chunkenizer deletion not implemented)
    for file_path_str in changed["deleted"]:
        if file_path_str in indexed_files:
            logger.info(f"File deleted: {file_path_str} (removed from index state)")
            del indexed_files[file_path_str]
    
    state["indexed_files"] = indexed_files
    state["last_index_time"] = datetime.now().isoformat()
    state["last_commit_hash"] = current_commit
    save_index_state(repo_path, state)
    
    total_changed = len(changed["added"]) + len(changed["modified"]) + len(changed["deleted"])
    logger.info(f"Incremental scan complete: {total_changed} files processed")


async def run_daemon(repo_path: Path, chunkenizer_url: str, interval: int) -> None:
    """Run in daemon mode with periodic checks."""
    logger.info(f"Starting daemon mode (interval: {interval}s)")
    
    shutdown = False
    
    def signal_handler(sig, frame):
        nonlocal shutdown
        logger.info("Shutdown signal received, stopping...")
        shutdown = True
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    while not shutdown:
        try:
            await incremental_scan(repo_path, chunkenizer_url)
        except Exception as e:
            logger.error(f"Error during scan: {e}", exc_info=True)
        
        if shutdown:
            break
        
        logger.info(f"Sleeping for {interval} seconds...")
        for _ in range(interval):
            if shutdown:
                break
            await asyncio.sleep(1)
    
    logger.info("Daemon stopped")


async def main():
    parser = argparse.ArgumentParser(description="Auto-index project files for RAG")
    parser.add_argument(
        "--repo-path",
        type=Path,
        default=Path.cwd(),
        help="Path to repository (default: current directory)",
    )
    parser.add_argument(
        "--chunkenizer-url",
        default="http://localhost:8000",
        help="Chunkenizer API URL (default: http://localhost:8000)",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=300,
        help="Interval in seconds for daemon mode (default: 300)",
    )
    parser.add_argument(
        "--daemon",
        action="store_true",
        help="Run in daemon mode",
    )
    parser.add_argument(
        "--full-scan",
        action="store_true",
        help="Force full scan (first run)",
    )
    args = parser.parse_args()
    
    repo_path = args.repo_path.resolve()
    if not repo_path.exists():
        logger.error(f"Repository path does not exist: {repo_path}")
        sys.exit(1)
    
    if args.daemon:
        await run_daemon(repo_path, args.chunkenizer_url, args.interval)
    elif args.full_scan:
        await full_scan(repo_path, args.chunkenizer_url)
    else:
        await incremental_scan(repo_path, args.chunkenizer_url)


if __name__ == "__main__":
    asyncio.run(main())
