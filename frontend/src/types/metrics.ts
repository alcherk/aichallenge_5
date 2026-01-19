// Metrics and analytics types

export interface MetricData {
  model: string;
  inputTokens: number;
  outputTokens: number;
  totalTokens: number;
  cost: number;
  responseTime: number;
  contextUsage: number;
  contextUsagePercent: number;
  contextWindow: number;
}

/**
 * Real-time inference metrics for local LLM streaming
 * Used to display performance stats during generation
 */
export interface InferenceMetrics {
  /** Tokens generated per second */
  tokensPerSecond: number;
  /** Time to first token in milliseconds */
  firstTokenLatencyMs: number;
  /** Total generation time in milliseconds */
  totalLatencyMs: number;
  /** Number of tokens generated so far */
  tokensGenerated: number;
  /** Context window utilization (0-1) */
  contextUtilization: number;
}

export interface TotalMetrics {
  requests: number;
  totalCost: number;
}

export interface MetricsState extends TotalMetrics {
  currentMetrics: MetricData | null;
}
