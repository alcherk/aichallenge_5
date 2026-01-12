"""Get Git context for developer assistant mode."""
import logging
from typing import Dict, Any, Optional
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
