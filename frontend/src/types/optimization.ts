// Types for LLM optimization and conditional prompts

/**
 * Prompt mode for conditional system prompts.
 * - auto: Automatically classify the request and select appropriate prompt
 * - code: Technical/programming tasks
 * - creative: Creative writing tasks
 * - analysis: Data analysis and reasoning tasks
 * - general: General questions (fallback)
 */
export type PromptMode = 'auto' | 'code' | 'creative' | 'analysis' | 'general';

/**
 * Advanced Ollama generation parameters.
 */
export interface OllamaOptions {
  /** Context window size (2048-32768) */
  num_ctx?: number;
  /** Maximum tokens to generate (128-4096) */
  num_predict?: number;
  /** Repetition penalty (1.0-2.0) */
  repeat_penalty?: number;
  /** Number of GPU layers (0-99) */
  num_gpu?: number;
  /** Number of CPU threads (1-16) */
  num_thread?: number;
}

/**
 * Default parameters for a prompt category.
 */
export interface CategoryDefaults {
  num_ctx: number;
  temperature: number;
}

/**
 * Category display information for UI.
 */
export interface CategoryInfo {
  name: string;
  emoji: string;
  description: string;
}

/**
 * Result from LLM classification.
 */
export interface ClassificationResult {
  category: PromptMode;
  confidence: number;
}

/**
 * Response from /api/prompt-templates endpoint.
 */
export interface PromptTemplatesResponse {
  templates: Record<PromptMode, string>;
  defaults: Record<PromptMode, CategoryDefaults>;
  categories: Record<PromptMode, CategoryInfo>;
}

/**
 * Response from /api/ollama/model/{name} endpoint.
 */
export interface ModelInfo {
  name: string;
  context_length: number;
  default_num_ctx: number;
  size_bytes?: number;
  modified_at?: string;
  parameters?: Record<string, unknown>;
}

/**
 * Default Ollama options.
 */
export const DEFAULT_OLLAMA_OPTIONS: OllamaOptions = {
  num_ctx: 8192,
  num_predict: 2048,
  repeat_penalty: 1.1,
  num_gpu: 99,
  num_thread: 8,
};

/**
 * Category defaults from backend.
 */
export const CATEGORY_DEFAULTS: Record<PromptMode, CategoryDefaults> = {
  auto: { num_ctx: 8192, temperature: 0.7 },
  code: { num_ctx: 16384, temperature: 0.2 },
  creative: { num_ctx: 8192, temperature: 0.9 },
  analysis: { num_ctx: 16384, temperature: 0.3 },
  general: { num_ctx: 4096, temperature: 0.7 },
};

/**
 * Category info for UI display.
 */
export const CATEGORY_INFO: Record<PromptMode, CategoryInfo> = {
  auto: {
    name: 'Auto',
    emoji: '🔄',
    description: 'Automatically detect the best mode',
  },
  code: {
    name: 'Technical',
    emoji: '💻',
    description: 'Programming, debugging, API, system administration',
  },
  creative: {
    name: 'Creative',
    emoji: '✨',
    description: 'Writing, storytelling, copywriting',
  },
  analysis: {
    name: 'Analysis',
    emoji: '📊',
    description: 'Data analysis, logical tasks, mathematics',
  },
  general: {
    name: 'General',
    emoji: '💬',
    description: 'General questions and conversations',
  },
};

/**
 * Context size presets for slider.
 */
export const CONTEXT_SIZE_PRESETS = [
  { value: 2048, label: '2K', description: 'Fast, ~4GB RAM' },
  { value: 4096, label: '4K', description: 'Light, ~6GB RAM' },
  { value: 8192, label: '8K', description: 'Balanced, ~8GB RAM' },
  { value: 16384, label: '16K', description: 'Extended, ~12GB RAM' },
  { value: 32768, label: '32K', description: 'Maximum, ~16GB RAM' },
];
