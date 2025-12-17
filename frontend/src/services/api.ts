// API service for backend communication

import type { ChatRequest, McpStatusResponse, StructuredResponse } from '@/types';

type McpStatusQuery = {
  enabled?: boolean;
  mcp_config_path?: string | null;
  workspace_root?: string | null;
};

export const chatAPI = {
  /**
   * Send a chat message (non-streaming)
   */
  async sendMessage(request: ChatRequest): Promise<StructuredResponse> {
    const response = await fetch('/api/chat', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(request),
    });

    if (!response.ok) {
      throw new Error(`API request failed with status ${response.status}`);
    }

    return response.json();
  },

  /**
   * Health check endpoint
   */
  async healthCheck(): Promise<{ status: string }> {
    const response = await fetch('/health');
    return response.json();
  },

  /**
   * MCP status (servers + discovered tools) for the UI.
   *
   * Backend endpoint: GET /api/mcp/status?enabled=&mcp_config_path=&workspace_root=
   */
  async getMcpStatus(query?: McpStatusQuery): Promise<McpStatusResponse> {
    const params = new URLSearchParams();
    if (query?.enabled !== undefined) params.set('enabled', String(query.enabled));
    if (query?.mcp_config_path) params.set('mcp_config_path', query.mcp_config_path);
    if (query?.workspace_root) params.set('workspace_root', query.workspace_root);

    const url = params.toString() ? `/api/mcp/status?${params.toString()}` : '/api/mcp/status';
    const response = await fetch(url);

    if (!response.ok) {
      throw new Error(`MCP status request failed with status ${response.status}`);
    }
    return response.json();
  },
};
