import React, { useState } from 'react';
import { useMetricsStore } from '@/store/metricsStore';
import { useSettingsStore } from '@/store/settingsStore';

interface MetricItemProps {
  label: string;
  value: string;
  icon?: string;
}

/**
 * Individual metric display item
 */
const MetricItem: React.FC<MetricItemProps> = ({ label, value, icon }) => {
  return (
    <div className="flex items-center gap-2 px-3 py-1.5">
      {icon && <span className="text-sm">{icon}</span>}
      <span className="text-xs text-slate-400">{label}:</span>
      <span className="text-xs font-semibold text-slate-100">{value}</span>
    </div>
  );
};

/**
 * InferenceMetricsPanel displays real-time inference metrics during local LLM streaming.
 * Shows tokens per second, first token latency, and context utilization.
 *
 * Features:
 * - Collapsible/expandable
 * - Dismissible
 * - Only shows when metrics are available
 * - Primarily for local model inference
 */
export const InferenceMetricsPanel: React.FC = () => {
  const { currentInferenceMetrics, clearInferenceMetrics } = useMetricsStore();
  const { localModel } = useSettingsStore();

  const [isCollapsed, setIsCollapsed] = useState(false);
  const [isDismissed, setIsDismissed] = useState(false);

  // Don't render if dismissed, no metrics, or using cloud provider (optional: can be enabled for cloud too)
  if (isDismissed || !currentInferenceMetrics) {
    return null;
  }

  // Only show for local model by default (acceptance criteria says "optional for cloud")
  // Uncomment the following line to restrict to local model only:
  // if (localModel.provider !== 'local') return null;

  const handleDismiss = () => {
    setIsDismissed(true);
    clearInferenceMetrics();
  };

  const handleToggleCollapse = () => {
    setIsCollapsed(!isCollapsed);
  };

  // Format metrics values safely
  const tokensPerSecond = currentInferenceMetrics.tokensPerSecond?.toFixed(1) ?? '0.0';
  const firstTokenLatency = currentInferenceMetrics.firstTokenLatencyMs ?? 0;
  const contextUtilization = ((currentInferenceMetrics.contextUtilization ?? 0) * 100).toFixed(0);
  const tokensGenerated = currentInferenceMetrics.tokensGenerated ?? 0;
  const totalLatency = currentInferenceMetrics.totalLatencyMs ?? 0;

  return (
    <div className="fixed bottom-20 right-4 z-50">
      <div className="bg-slate-800 border border-slate-700 rounded-lg shadow-xl overflow-hidden min-w-[200px]">
        {/* Header with collapse/dismiss controls */}
        <div className="flex items-center justify-between px-3 py-2 bg-slate-700/50 border-b border-slate-600">
          <button
            onClick={handleToggleCollapse}
            className="flex items-center gap-2 text-sm font-medium text-slate-200 hover:text-white transition-colors"
            aria-label={isCollapsed ? 'Expand metrics panel' : 'Collapse metrics panel'}
          >
            <span className={`transform transition-transform ${isCollapsed ? '-rotate-90' : ''}`}>
              &#9662;
            </span>
            <span>Inference Metrics</span>
          </button>
          <button
            onClick={handleDismiss}
            className="text-slate-400 hover:text-slate-200 transition-colors p-1"
            aria-label="Dismiss metrics panel"
          >
            <svg
              xmlns="http://www.w3.org/2000/svg"
              className="h-4 w-4"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M6 18L18 6M6 6l12 12"
              />
            </svg>
          </button>
        </div>

        {/* Collapsible content */}
        {!isCollapsed && (
          <div className="p-2 space-y-1">
            {/* Speed (tokens per second) */}
            <MetricItem
              label="Speed"
              value={`${tokensPerSecond} tok/s`}
              icon="&#9889;"
            />

            {/* First token latency */}
            <MetricItem
              label="First token"
              value={`${firstTokenLatency}ms`}
              icon="&#128337;"
            />

            {/* Context utilization */}
            <MetricItem
              label="Context"
              value={`${contextUtilization}%`}
              icon="&#128202;"
            />

            {/* Additional metrics (tokens generated, total latency) */}
            <div className="border-t border-slate-700 mt-2 pt-2">
              <MetricItem
                label="Tokens"
                value={tokensGenerated.toLocaleString()}
              />
              <MetricItem
                label="Total time"
                value={`${(totalLatency / 1000).toFixed(2)}s`}
              />
            </div>

            {/* Context utilization progress bar */}
            <div className="px-3 pb-2">
              <div className="w-full bg-slate-700 rounded-full h-1.5 mt-1">
                <div
                  className={`h-1.5 rounded-full transition-all duration-300 ${
                    Number(contextUtilization) > 80
                      ? 'bg-red-500'
                      : Number(contextUtilization) > 60
                      ? 'bg-yellow-500'
                      : 'bg-teal-500'
                  }`}
                  style={{ width: `${Math.min(Number(contextUtilization), 100)}%` }}
                />
              </div>
            </div>
          </div>
        )}

        {/* Provider indicator */}
        <div className="px-3 py-1.5 bg-slate-900/50 border-t border-slate-700">
          <span className={`text-xs font-medium ${
            localModel.provider === 'local' ? 'text-teal-400' : 'text-blue-400'
          }`}>
            {localModel.provider === 'local' ? 'Local Model' : 'Cloud Model'}
          </span>
        </div>
      </div>
    </div>
  );
};

export default InferenceMetricsPanel;
