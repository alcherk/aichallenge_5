"""Get Git context for developer assistant mode."""
import logging
import re
from typing import Dict, Any, Optional, List
from pathlib import Path

logger = logging.getLogger("app.rag.git")


async def get_git_context(mcp_manager: Any, workspace_root: Path) -> Optional[Dict[str, Any]]:
    """
    Get Git context using MCP tools.
    
    Args:
        mcp_manager: MCPManager instance
        workspace_root: Repository root path
    
    Returns:
        Dict with git context (branch, modified_files, etc.) or None if error
    """
    if not mcp_manager:
        logger.debug("MCP manager not available for git context")
        return None
    
    try:
        # Find git MCP tools (they are prefixed with mcp_builtin_git__)
        git_tool_names = []
        for tool_name, binding in mcp_manager._tool_bindings.items():
            if binding.server_name == "builtin_git":
                git_tool_names.append((tool_name, binding.mcp_tool_name))
        
        if not git_tool_names:
            logger.debug("Git MCP tools not found")
            return None
        
        context = {}
        
        # Get git status (find the tool name)
        git_status_tool = None
        for openai_name, mcp_name in git_tool_names:
            if mcp_name == "git_status":
                git_status_tool = openai_name
                break
        
        if git_status_tool:
            try:
                status_result = await mcp_manager.call_openai_tool(git_status_tool, {})
                if isinstance(status_result, dict) and status_result.get("is_git_repo"):
                    context["branch"] = status_result.get("branch", "unknown")
                    context["modified_files"] = status_result.get("modified_files", [])
                    context["staged_files"] = status_result.get("staged_files", [])
                    context["untracked_files"] = status_result.get("untracked_files", [])
            except Exception as e:
                logger.warning(f"Failed to get git status: {e}")
        
        # Get branch info (if not already from status)
        if "branch" not in context:
            git_branch_tool = None
            for openai_name, mcp_name in git_tool_names:
                if mcp_name == "git_branch":
                    git_branch_tool = openai_name
                    break
            
            if git_branch_tool:
                try:
                    branch_result = await mcp_manager.call_openai_tool(git_branch_tool, {})
                    if isinstance(branch_result, dict) and branch_result.get("is_git_repo"):
                        context["branch"] = branch_result.get("current_branch", "unknown")
                except Exception as e:
                    logger.warning(f"Failed to get git branch: {e}")
        
        if not context:
            return None
        
        return context
        
    except Exception as e:
        logger.exception(f"Error getting git context: {e}")
        return None


def format_git_context(git_context: Optional[Dict[str, Any]]) -> str:
    """
    Format Git context as a string for inclusion in prompt.
    
    Args:
        git_context: Git context dict from get_git_context()
    
    Returns:
        Formatted string with git information
    """
    if not git_context:
        return ""
    
    lines = ["GIT CONTEXT:"]
    
    branch = git_context.get("branch")
    if branch:
        lines.append(f"Current branch: {branch}")
    
    modified = git_context.get("modified_files", [])
    staged = git_context.get("staged_files", [])
    untracked = git_context.get("untracked_files", [])
    
    if modified or staged or untracked:
        lines.append("Changed files:")
        if staged:
            lines.append(f"  Staged: {', '.join(staged[:5])}{'...' if len(staged) > 5 else ''}")
        if modified:
            lines.append(f"  Modified: {', '.join(modified[:5])}{'...' if len(modified) > 5 else ''}")
        if untracked:
            lines.append(f"  Untracked: {', '.join(untracked[:5])}{'...' if len(untracked) > 5 else ''}")
    
    return "\n".join(lines) if len(lines) > 1 else ""


def _extract_changed_files_from_diff(diff: str) -> List[str]:
    """
    Extract list of changed files from git diff output.
    
    Args:
        diff: Git diff output
    
    Returns:
        List of file paths that were changed
    """
    if not diff:
        return []
    
    changed_files = []
    # Pattern: "diff --git a/path/to/file b/path/to/file"
    pattern = r'^diff --git a/(.+?) b/(.+?)$'
    
    for line in diff.split('\n'):
        match = re.match(pattern, line)
        if match:
            # Use the 'b' path (new file path)
            file_path = match.group(2)
            if file_path not in changed_files:
                changed_files.append(file_path)
    
    return changed_files


async def get_review_diff(
    mcp_manager: Any,
    workspace_root: Path,
    commit_hash: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """
    Get git diff for code review.
    
    Args:
        mcp_manager: MCPManager instance
        workspace_root: Repository root path
        commit_hash: Optional commit hash (None = uncommitted changes)
    
    Returns:
        Dict with diff, changed_files, commit, or None if error
    """
    if not mcp_manager:
        logger.warning("MCP manager not available for review diff")
        return None
    
    try:
        # Find git MCP tools
        git_tool_names = []
        for tool_name, binding in mcp_manager._tool_bindings.items():
            if binding.server_name == "builtin_git":
                git_tool_names.append((tool_name, binding.mcp_tool_name))
        
        if not git_tool_names:
            logger.warning("Git MCP tools not found for review diff. Available tools: %s", 
                         list(mcp_manager._tool_bindings.keys())[:10])
            return None
        
        logger.info(f"Found {len(git_tool_names)} Git MCP tools: {[name for _, name in git_tool_names]}")
        
        # Find git_diff tool
        git_diff_tool = None
        for openai_name, mcp_name in git_tool_names:
            if mcp_name == "git_diff":
                git_diff_tool = openai_name
                break
        
        if not git_diff_tool:
            logger.warning("git_diff MCP tool not found. Available git tools: %s", 
                         [name for _, name in git_tool_names])
            return None
        
        logger.info(f"Using git_diff tool: {git_diff_tool} (MCP name: git_diff)")
        
        # Prepare arguments for git_diff
        # git_server expects: {"commit": "HEAD"} or {"commit": "HEAD~1"} or {} for uncommitted
        arguments = {}
        if commit_hash:
            # Review specific commit: diff between commit and its parent
            # git_server expects "commit" parameter
            arguments["commit"] = commit_hash
            logger.info(f"Requesting git diff for commit: {commit_hash}")
        else:
            # Empty arguments = uncommitted changes (working tree diff)
            logger.info("Requesting git diff for uncommitted changes (working tree), arguments={}")
        
        try:
            logger.info(f"Calling git_diff MCP tool: {git_diff_tool} with arguments: {arguments}")
            import asyncio
            try:
                # Add timeout to prevent hanging
                diff_result = await asyncio.wait_for(
                    mcp_manager.call_openai_tool(git_diff_tool, arguments),
                    timeout=15.0
                )
                logger.info(f"Git diff MCP tool call completed successfully")
            except asyncio.TimeoutError:
                logger.error(f"Git diff MCP tool call timed out after 15 seconds")
                return None
            except Exception as e:
                logger.error(f"Git diff MCP tool call failed: {e}", exc_info=True)
                return None
            
            if not isinstance(diff_result, dict):
                logger.warning(f"Unexpected diff result type: {type(diff_result)}, value: {str(diff_result)[:200]}")
                return None
            
            diff_text = diff_result.get("diff", "")
            diff_length = len(diff_text) if diff_text else 0
            
            logger.info(f"Git diff retrieved: length={diff_length} chars, commit={commit_hash or 'uncommitted'}")
            
            if not diff_text or diff_text.strip() == "":
                logger.info(f"No changes found for review (commit={commit_hash or 'uncommitted'})")
                return {
                    "diff": "",
                    "changed_files": [],
                    "commit": commit_hash,
                    "has_changes": False,
                }
            
            # Extract changed files from diff
            changed_files = _extract_changed_files_from_diff(diff_text)
            logger.info(f"Extracted {len(changed_files)} changed files from diff: {changed_files[:5]}{'...' if len(changed_files) > 5 else ''}")
            
            return {
                "diff": diff_text,
                "changed_files": changed_files,
                "commit": commit_hash,
                "has_changes": True,
            }
            
        except Exception as e:
            logger.error(f"Failed to call git_diff MCP tool: {e}", exc_info=True)
            return None
        
    except Exception as e:
        logger.exception(f"Error getting review diff: {e}")
        return None
