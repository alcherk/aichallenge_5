// Type definitions matching backend schemas

export type Role = 'system' | 'user' | 'assistant';

export interface Message {
  role: Role;
  content: string;
}

export interface ChatRequest {
  messages: Message[];
  model?: string;
  temperature?: number;
  max_tokens?: number;
  // Optional MCP per-request overrides (backend supports these).
  mcp_enabled?: boolean | null;
  mcp_config_path?: string | null;
  workspace_root?: string | null;
}

export interface TokenUsage {
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
}

export interface ChatChoice {
  index: number;
  message: Message;
  finish_reason: string | null;
}

export interface ChatResponse {
  id: string;
  model: string;
  choices: ChatChoice[];
  usage?: TokenUsage;
}

export interface StructuredResponse {
  success: boolean;
  status_code: number;
  message: string;
  data: ChatResponse | null;
  error: {
    type: string;
    detail: string;
    status_code?: number;
  } | null;
  metadata: {
    timestamp: number;
    request_id?: string;
    model: string;
    processing_time_ms: number;
    token_usage?: TokenUsage;
  } | null;
}

// SSE Event types
export interface SSEChunkEvent {
  event: 'chunk';
  data: {
    delta: string;
  };
}

export interface SSEDoneEvent {
  event: 'done';
  data: StructuredResponse;
}

export interface SSEErrorEvent {
  event: 'error';
  data: StructuredResponse;
}

export type SSEEvent = SSEChunkEvent | SSEDoneEvent | SSEErrorEvent;
