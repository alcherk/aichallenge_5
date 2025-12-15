// LocalStorage service for persistence

import type { Message, Settings, TotalMetrics } from '@/types';
import { DEFAULT_SETTINGS } from '@/types';

const KEYS = {
  CONVERSATION: 'chatConversationV1',
  MESSAGE_COUNT: 'chatMessageCountV1',
  SYSTEM_PROMPT: 'systemPrompt',
  TEMPERATURE: 'temperature',
  MODEL: 'model',
  COMPRESSION_THRESHOLD: 'compressionThreshold',
  MCP_ENABLED: 'mcpEnabled',
  MCP_CONFIG_PATH: 'mcpConfigPath',
  WORKSPACE_ROOT: 'workspaceRoot',
  TOTAL_METRICS: 'totalMetrics',
} as const;

// Helper functions
function safeGet<T>(key: string, defaultValue: T): T {
  try {
    const item = localStorage.getItem(key);
    return item ? JSON.parse(item) : defaultValue;
  } catch {
    return defaultValue;
  }
}

function safeSet(key: string, value: unknown): void {
  try {
    localStorage.setItem(key, JSON.stringify(value));
  } catch (error) {
    console.warn(`Failed to save to localStorage: ${error}`);
  }
}

function safeRemove(key: string): void {
  try {
    localStorage.removeItem(key);
  } catch (error) {
    console.warn(`Failed to remove from localStorage: ${error}`);
  }
}

// Conversation storage
export const conversationStorage = {
  get(): Message[] {
    return safeGet<Message[]>(KEYS.CONVERSATION, []);
  },

  set(messages: Message[]): void {
    safeSet(KEYS.CONVERSATION, messages);
  },

  clear(): void {
    safeRemove(KEYS.CONVERSATION);
    safeRemove(KEYS.MESSAGE_COUNT);
  },

  getMessageCount(): number {
    return safeGet<number>(KEYS.MESSAGE_COUNT, 0);
  },

  setMessageCount(count: number): void {
    safeSet(KEYS.MESSAGE_COUNT, count);
  },
};

// Settings storage
export const settingsStorage = {
  get(): Settings {
    return {
      systemPrompt: safeGet<string>(KEYS.SYSTEM_PROMPT, DEFAULT_SETTINGS.systemPrompt),
      temperature: safeGet<number>(KEYS.TEMPERATURE, DEFAULT_SETTINGS.temperature),
      model: safeGet<string>(KEYS.MODEL, DEFAULT_SETTINGS.model) as Settings['model'],
      compressionThreshold: safeGet<number>(
        KEYS.COMPRESSION_THRESHOLD,
        DEFAULT_SETTINGS.compressionThreshold
      ),
      mcpEnabled: safeGet<boolean>(KEYS.MCP_ENABLED, DEFAULT_SETTINGS.mcpEnabled),
      mcpConfigPath: safeGet<string>(KEYS.MCP_CONFIG_PATH, DEFAULT_SETTINGS.mcpConfigPath),
      workspaceRoot: safeGet<string>(KEYS.WORKSPACE_ROOT, DEFAULT_SETTINGS.workspaceRoot),
    };
  },

  set(settings: Settings): void {
    safeSet(KEYS.SYSTEM_PROMPT, settings.systemPrompt);
    safeSet(KEYS.TEMPERATURE, settings.temperature);
    safeSet(KEYS.MODEL, settings.model);
    safeSet(KEYS.COMPRESSION_THRESHOLD, settings.compressionThreshold);
    safeSet(KEYS.MCP_ENABLED, settings.mcpEnabled);
    safeSet(KEYS.MCP_CONFIG_PATH, settings.mcpConfigPath);
    safeSet(KEYS.WORKSPACE_ROOT, settings.workspaceRoot);
  },

  setSystemPrompt(prompt: string): void {
    safeSet(KEYS.SYSTEM_PROMPT, prompt);
  },

  setTemperature(temperature: number): void {
    safeSet(KEYS.TEMPERATURE, temperature);
  },

  setModel(model: string): void {
    safeSet(KEYS.MODEL, model);
  },

  setCompressionThreshold(threshold: number): void {
    safeSet(KEYS.COMPRESSION_THRESHOLD, threshold);
  },

  setMcpEnabled(enabled: boolean): void {
    safeSet(KEYS.MCP_ENABLED, enabled);
  },

  setMcpConfigPath(path: string): void {
    safeSet(KEYS.MCP_CONFIG_PATH, path);
  },

  setWorkspaceRoot(path: string): void {
    safeSet(KEYS.WORKSPACE_ROOT, path);
  },
};

// Metrics storage
export const metricsStorage = {
  get(): TotalMetrics {
    return safeGet<TotalMetrics>(KEYS.TOTAL_METRICS, {
      requests: 0,
      totalCost: 0,
    });
  },

  set(metrics: TotalMetrics): void {
    safeSet(KEYS.TOTAL_METRICS, metrics);
  },

  reset(): void {
    safeSet(KEYS.TOTAL_METRICS, { requests: 0, totalCost: 0 });
  },
};
