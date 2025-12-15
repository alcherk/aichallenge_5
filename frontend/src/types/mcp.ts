export interface McpServerStatus {
  name: string;
  transport: 'stdio' | 'http';
  kind: 'filesystem' | 'fetch' | 'generic';
  connected: boolean;
}

export interface McpToolStatus {
  openai_name: string;
  server: string | null;
  mcp_name: string | null;
  kind: string | null;
  description?: string;
  parameters?: unknown;
}

export interface McpStatusResponse {
  enabled: boolean;
  servers: McpServerStatus[];
  tools: McpToolStatus[];
  error?: { type: string; detail: string };
}


