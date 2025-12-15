import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { chatAPI } from '@/services/api';
import { useSettingsStore } from '@/store/settingsStore';
import type { McpStatusResponse } from '@/types';
import { McpStatusModal } from '@/components/mcp/McpStatusModal';

interface HeaderProps {
  onNewChat: () => void;
  onSettingsClick: () => void;
}

export const Header: React.FC<HeaderProps> = ({ onNewChat, onSettingsClick }) => {
  const { mcpEnabled, mcpConfigPath, workspaceRoot } = useSettingsStore();
  const [showMcp, setShowMcp] = useState(false);
  const [mcpStatus, setMcpStatus] = useState<McpStatusResponse | null>(null);
  const [mcpLoading, setMcpLoading] = useState(false);

  const handleNewChat = () => {
    if (confirm('Start a new chat? This will clear the current conversation.')) {
      onNewChat();
    }
  };

  const fetchStatus = useCallback(async () => {
    setMcpLoading(true);
    try {
      const status = await chatAPI.getMcpStatus(
        mcpEnabled
          ? { enabled: true, mcp_config_path: mcpConfigPath || null, workspace_root: workspaceRoot || null }
          : undefined
      );
      setMcpStatus(status);
    } catch (e) {
      setMcpStatus({
        enabled: false,
        servers: [],
        tools: [],
        error: { type: 'Error', detail: e instanceof Error ? e.message : 'Unknown error' },
      });
    } finally {
      setMcpLoading(false);
    }
  }, [mcpEnabled, mcpConfigPath, workspaceRoot]);

  useEffect(() => {
    // Keep it lightweight: only auto-refresh status when settings change and MCP is enabled.
    if (mcpEnabled) {
      fetchStatus();
    } else {
      setMcpStatus(null);
      setShowMcp(false);
    }
  }, [mcpEnabled, mcpConfigPath, workspaceRoot, fetchStatus]);

  const mcpBadge = useMemo(() => {
    if (!mcpEnabled) return { text: 'MCP: Off', cls: 'text-slate-400 border-slate-600' };
    if (mcpLoading) return { text: 'MCP: …', cls: 'text-slate-300 border-slate-600' };
    if (mcpStatus?.enabled) return { text: `MCP: ${mcpStatus.tools.length}`, cls: 'text-green-300 border-green-700' };
    if (mcpStatus?.error) return { text: 'MCP: Error', cls: 'text-red-300 border-red-800' };
    return { text: 'MCP: On', cls: 'text-slate-300 border-slate-600' };
  }, [mcpEnabled, mcpLoading, mcpStatus]);

  return (
    <div className="flex items-center justify-between">
      <div>
        <h1 className="text-2xl font-bold bg-gradient-to-r from-blue-400 to-purple-500 bg-clip-text text-transparent">
          ChatGPT Proxy
        </h1>
        <p className="text-sm text-slate-400">FastAPI + React + TypeScript</p>
      </div>

      <div className="flex gap-2">
        {mcpEnabled && (
          <button
            onClick={() => {
              setShowMcp(true);
              fetchStatus();
            }}
            className={`px-4 py-2 bg-slate-800 border rounded-lg hover:bg-slate-700 hover:border-slate-500 focus:outline-none focus:ring-2 focus:ring-blue-500 transition-all duration-200 ${mcpBadge.cls}`}
            title="MCP status"
          >
            {mcpBadge.text}
          </button>
        )}
        <button
          onClick={handleNewChat}
          className="px-4 py-2 bg-slate-800 border border-slate-600 text-slate-200 rounded-lg hover:bg-slate-700 hover:border-slate-500 focus:outline-none focus:ring-2 focus:ring-blue-500 transition-all duration-200"
        >
          🔄 New Chat
        </button>
        <button
          onClick={onSettingsClick}
          className="px-4 py-2 bg-slate-800 border border-slate-600 text-slate-200 rounded-lg hover:bg-slate-700 hover:border-slate-500 focus:outline-none focus:ring-2 focus:ring-blue-500 transition-all duration-200"
          title="Settings"
        >
          ⚙️ Settings
        </button>
      </div>

      {mcpEnabled && (
        <McpStatusModal
          isOpen={showMcp}
          status={mcpStatus}
          isLoading={mcpLoading}
          onRefresh={fetchStatus}
          onClose={() => setShowMcp(false)}
        />
      )}
    </div>
  );
};
