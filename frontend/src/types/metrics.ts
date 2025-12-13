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

export interface TotalMetrics {
  requests: number;
  totalCost: number;
}

export interface MetricsState extends TotalMetrics {
  currentMetrics: MetricData | null;
}
