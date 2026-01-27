// Type definitions matching backend schemas

export type Role = 'system' | 'user' | 'assistant';

export interface Message {
  role: Role;
  content: string;
}

import type { OllamaOptions, PromptMode } from './optimization';

export interface ChatRequest {
  messages: Message[];
  model?: string;
  temperature?: number;
  max_tokens?: number;
  // Optional MCP per-request overrides (backend supports these).
  mcp_enabled?: boolean | null;
  mcp_config_path?: string | null;
  workspace_root?: string | null;
  // Assistant mode: strict RAG-only mode
  assistant_mode?: boolean | null;
  // Provider selection for local/cloud routing
  provider?: 'cloud' | 'local';
  // RAG toggle for per-request control
  rag_enabled?: boolean | null;
  // Additional local model options
  top_p?: number;
  // Ollama optimization parameters
  ollama_options?: OllamaOptions;
  // Prompt mode for conditional system prompts
  prompt_mode?: PromptMode;
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

export interface RAGMetadata {
  enabled: boolean;
  initial_chunks?: number;
  filtered_chunks?: number;
  final_chunks?: number;
  threshold?: number;
  fallback_triggered?: boolean;
  reranker_enabled?: boolean;
  reranker_type?: string | null;
  scores_range?: [number, number] | null;
  initial_scores?: number[];
  filtered_scores?: number[];
  context_size?: number;
  compare_mode?: boolean;
  baseline_answer?: string;
  enhanced_answer?: string;
  error?: string;
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
    rag?: RAGMetadata;
    // Optimization metadata
    prompt_mode?: PromptMode;
    classification_confidence?: number;
  } | null;
}

export interface SttEnabledResponse {
  enabled: boolean;
}

export interface TranscribeResponse {
  text: string;
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
