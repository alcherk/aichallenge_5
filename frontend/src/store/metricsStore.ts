// Metrics state management with Zustand

import { create } from 'zustand';
import type { MetricData, StructuredResponse } from '@/types';
import { MODEL_PRICING, CONTEXT_WINDOWS } from '@/types';
import { metricsStorage } from '@/services/storage';

interface MetricsState {
  currentMetrics: MetricData | null;
  totalRequests: number;
  totalCost: number;

  // Actions
  updateMetrics: (response: StructuredResponse) => void;
  resetMetrics: () => void;
  resetCurrentMetrics: () => void;
  loadFromStorage: () => void;
}

function calculateCost(model: string, inputTokens: number, outputTokens: number): number {
  const pricing = MODEL_PRICING[model as keyof typeof MODEL_PRICING] || MODEL_PRICING['gpt-4o-mini'];
  const inputCost = (inputTokens / 1_000_000) * pricing.input;
  const outputCost = (outputTokens / 1_000_000) * pricing.output;
  return inputCost + outputCost;
}

export const useMetricsStore = create<MetricsState>((set, get) => ({
  currentMetrics: null,
  totalRequests: 0,
  totalCost: 0,

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
}));
