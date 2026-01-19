// Metrics state management with Zustand

import { create } from 'zustand';
import type { MetricData, StructuredResponse, InferenceMetrics } from '@/types';
import { MODEL_PRICING, CONTEXT_WINDOWS } from '@/types';
import { metricsStorage } from '@/services/storage';

interface MetricsState {
  currentMetrics: MetricData | null;
  totalRequests: number;
  totalCost: number;

  // Inference metrics for local LLM streaming
  currentInferenceMetrics: InferenceMetrics | null;

  // Actions
  updateMetrics: (response: StructuredResponse) => void;
  resetMetrics: () => void;
  resetCurrentMetrics: () => void;
  loadFromStorage: () => void;

  // Inference metrics actions
  setInferenceMetrics: (metrics: InferenceMetrics) => void;
  clearInferenceMetrics: () => void;
  updateTokensPerSecond: (tps: number) => void;
  updateFirstTokenLatency: (latencyMs: number) => void;
  updateTokensGenerated: (tokens: number) => void;
  updateTotalLatency: (latencyMs: number) => void;
  updateContextUtilization: (utilization: number) => void;
}

function calculateCost(model: string, inputTokens: number, outputTokens: number): number {
  const pricing = MODEL_PRICING[model as keyof typeof MODEL_PRICING] || MODEL_PRICING['gpt-4o-mini'];
  const inputCost = (inputTokens / 1_000_000) * pricing.input;
  const outputCost = (outputTokens / 1_000_000) * pricing.output;
  return inputCost + outputCost;
}

// Default inference metrics (all zeros)
const defaultInferenceMetrics: InferenceMetrics = {
  tokensPerSecond: 0,
  firstTokenLatencyMs: 0,
  totalLatencyMs: 0,
  tokensGenerated: 0,
  contextUtilization: 0,
};

export const useMetricsStore = create<MetricsState>((set, get) => ({
  currentMetrics: null,
  totalRequests: 0,
  totalCost: 0,
  currentInferenceMetrics: null,

  updateMetrics: (response) => {
    if (!response.success || !response.metadata) return;

    const { metadata } = response;
    const { token_usage, model, processing_time_ms } = metadata;

    if (!token_usage) return;

    const cost = calculateCost(
      model,
      token_usage.prompt_tokens,
      token_usage.completion_tokens
    );

    const contextWindow = CONTEXT_WINDOWS[model as keyof typeof CONTEXT_WINDOWS] || 128000;
    const contextUsage = token_usage.prompt_tokens;
    const contextUsagePercent = (contextUsage / contextWindow) * 100;

    const currentMetrics: MetricData = {
      model,
      inputTokens: token_usage.prompt_tokens,
      outputTokens: token_usage.completion_tokens,
      totalTokens: token_usage.total_tokens,
      cost,
      responseTime: processing_time_ms,
      contextUsage,
      contextUsagePercent,
      contextWindow,
    };

    const { totalRequests, totalCost } = get();
    const newTotalRequests = totalRequests + 1;
    const newTotalCost = totalCost + cost;

    set({
      currentMetrics,
      totalRequests: newTotalRequests,
      totalCost: newTotalCost,
    });

    // Persist total metrics
    metricsStorage.set({
      requests: newTotalRequests,
      totalCost: newTotalCost,
    });
  },

  resetMetrics: () => {
    set({
      currentMetrics: null,
      totalRequests: 0,
      totalCost: 0,
    });
    metricsStorage.reset();
  },

  resetCurrentMetrics: () => {
    set({ currentMetrics: null });
  },

  loadFromStorage: () => {
    const { requests, totalCost } = metricsStorage.get();
    set({
      totalRequests: requests,
      totalCost,
    });
  },

  // Inference metrics actions for local LLM streaming

  setInferenceMetrics: (metrics) => {
    set({ currentInferenceMetrics: metrics });
  },

  clearInferenceMetrics: () => {
    set({ currentInferenceMetrics: null });
  },

  updateTokensPerSecond: (tps) => {
    const current = get().currentInferenceMetrics || { ...defaultInferenceMetrics };
    set({
      currentInferenceMetrics: {
        ...current,
        tokensPerSecond: tps,
      },
    });
  },

  updateFirstTokenLatency: (latencyMs) => {
    const current = get().currentInferenceMetrics || { ...defaultInferenceMetrics };
    set({
      currentInferenceMetrics: {
        ...current,
        firstTokenLatencyMs: latencyMs,
      },
    });
  },

  updateTokensGenerated: (tokens) => {
    const current = get().currentInferenceMetrics || { ...defaultInferenceMetrics };
    set({
      currentInferenceMetrics: {
        ...current,
        tokensGenerated: tokens,
      },
    });
  },

  updateTotalLatency: (latencyMs) => {
    const current = get().currentInferenceMetrics || { ...defaultInferenceMetrics };
    set({
      currentInferenceMetrics: {
        ...current,
        totalLatencyMs: latencyMs,
      },
    });
  },

  updateContextUtilization: (utilization) => {
    const current = get().currentInferenceMetrics || { ...defaultInferenceMetrics };
    set({
      currentInferenceMetrics: {
        ...current,
        contextUtilization: Math.max(0, Math.min(1, utilization)), // Clamp to 0-1
      },
    });
  },
}));
