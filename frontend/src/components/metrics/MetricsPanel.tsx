import React from 'react';
import { useMetricsStore } from '@/store/metricsStore';
import { MetricCard } from './MetricCard';

export const MetricsPanel: React.FC = () => {
  const { currentMetrics, totalRequests, totalCost, resetMetrics } = useMetricsStore();

  const handleReset = () => {
    if (confirm('Reset all metrics? This cannot be undone.')) {
      resetMetrics();
    }
  };

  return (
    <div className="w-80 bg-slate-900 border-l border-slate-700 shadow-2xl overflow-y-auto flex-shrink-0">
      <div className="sticky top-0 bg-slate-800 border-b border-slate-700 px-4 py-2 shadow-md">
        <h3 className="text-base font-semibold text-slate-100">📊 Metrics</h3>
      </div>

      <div className="p-3 space-y-3">
        {/* Current Request Metrics */}
        <div>
          <h4 className="text-xs font-semibold text-slate-300 mb-1.5">Current Request</h4>
          <div className="space-y-1">
            <MetricCard
              label="Model"
              value={currentMetrics?.model || '-'}
            />
            <MetricCard
              label="Provider"
              value="OpenAI"
            />
            <MetricCard
              label="Input Tokens"
              value={currentMetrics?.inputTokens.toLocaleString() || '0'}
            />
            <MetricCard
              label="Output Tokens"
              value={currentMetrics?.outputTokens.toLocaleString() || '0'}
            />
            <MetricCard
              label="Total Tokens"
              value={currentMetrics?.totalTokens.toLocaleString() || '0'}
            />
            <MetricCard
              label="Cost"
              value={currentMetrics ? `$${currentMetrics.cost.toFixed(6)}` : '$0.000'}
            />
            <MetricCard
              label="Response Time"
              value={currentMetrics ? `${currentMetrics.responseTime}ms` : '-'}
            />
          </div>
        </div>

        {/* Context Window Usage */}
        <div className="border-t border-slate-700 pt-2">
          <h4 className="text-xs font-semibold text-slate-300 mb-1.5">Context Window</h4>
          <div className="space-y-1">
            <MetricCard
              label="Context Window"
              value={currentMetrics ? `${(currentMetrics.contextWindow / 1000).toFixed(0)}k` : '-'}
            />
            <MetricCard
              label="Context Usage"
              value={currentMetrics?.contextUsage.toLocaleString() || '0'}
            />
            <MetricCard
              label="Usage %"
              value={currentMetrics ? `${currentMetrics.contextUsagePercent.toFixed(2)}%` : '0%'}
            />

            {/* Progress bar */}
            {currentMetrics && (
              <div className="mt-1">
                <div className="w-full bg-slate-700 rounded-full h-1.5">
                  <div
                    className={`h-1.5 rounded-full transition-all ${
                      currentMetrics.contextUsagePercent > 80
                        ? 'bg-red-500'
                        : currentMetrics.contextUsagePercent > 60
                        ? 'bg-yellow-500'
                        : 'bg-green-500'
                    }`}
                    style={{ width: `${Math.min(currentMetrics.contextUsagePercent, 100)}%` }}
                  />
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Total Metrics */}
        <div className="border-t border-slate-700 pt-2">
          <h4 className="text-xs font-semibold text-slate-300 mb-1.5">Session Total</h4>
          <div className="space-y-1">
            <MetricCard
              label="Total Requests"
              value={totalRequests.toLocaleString()}
            />
            <MetricCard
              label="Total Cost"
              value={`$${totalCost.toFixed(6)}`}
            />
          </div>
        </div>

        {/* Reset Button */}
        <div className="border-t border-slate-700 pt-2">
          <button
            onClick={handleReset}
            className="w-full px-3 py-1.5 bg-red-600 text-white rounded-lg hover:bg-red-700 focus:outline-none focus:ring-2 focus:ring-red-500 transition-all duration-200 text-xs font-semibold shadow-lg"
          >
            🗑️ Reset Stats
          </button>
        </div>
      </div>
    </div>
  );
};
