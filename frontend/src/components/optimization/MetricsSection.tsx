import React from 'react';
import { useOptimizationStore } from '@/store/optimizationStore';
import { useMetricsStore } from '@/store/metricsStore';

/**
 * MetricsSection - Shows real-time classification results and inference metrics.
 */
export const MetricsSection: React.FC = () => {
  const { lastClassification, categoryInfo, promptMode } = useOptimizationStore();
  const { currentInferenceMetrics } = useMetricsStore();

  // Determine what to show based on mode
  const isAutoMode = promptMode === 'auto';
  const hasClassification = lastClassification !== null;

  return (
    <div className="space-y-3">
      <h4 className="text-xs font-semibold text-slate-400 uppercase tracking-wide">
        Live Status
      </h4>

      {/* Classification result (only in auto mode) */}
      {isAutoMode && (
        <div className="p-3 bg-slate-800/50 rounded-lg border border-slate-700">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs text-slate-400">Detected Mode</span>
            {hasClassification && categoryInfo[lastClassification.category] ? (
              <span className="text-xs font-semibold text-teal-400">
                {categoryInfo[lastClassification.category].emoji}{' '}
                {categoryInfo[lastClassification.category].name}
              </span>
            ) : (
              <span className="text-xs text-slate-500">Waiting...</span>
            )}
          </div>

          {hasClassification && (
            <>
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs text-slate-400">Confidence</span>
                <span className={`text-xs font-semibold ${
                  lastClassification.confidence >= 0.8 ? 'text-green-400' :
                  lastClassification.confidence >= 0.5 ? 'text-yellow-400' : 'text-orange-400'
                }`}>
                  {Math.round(lastClassification.confidence * 100)}%
                </span>
              </div>

              {/* Confidence bar */}
              <div className="w-full bg-slate-700 rounded-full h-1">
                <div
                  className={`h-1 rounded-full transition-all duration-300 ${
                    lastClassification.confidence >= 0.8 ? 'bg-green-500' :
                    lastClassification.confidence >= 0.5 ? 'bg-yellow-500' : 'bg-orange-500'
                  }`}
                  style={{ width: `${Math.round(lastClassification.confidence * 100)}%` }}
                />
              </div>
            </>
          )}
        </div>
      )}

      {/* Manual mode indicator */}
      {!isAutoMode && categoryInfo[promptMode] && (
        <div className="p-3 bg-slate-800/50 rounded-lg border border-slate-700">
          <div className="flex items-center gap-2">
            <span className="text-lg">{categoryInfo[promptMode].emoji}</span>
            <div>
              <span className="text-sm font-semibold text-slate-200">
                {categoryInfo[promptMode].name} Mode
              </span>
              <p className="text-xs text-slate-500">
                {categoryInfo[promptMode].description}
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Inference metrics (if available) */}
      {currentInferenceMetrics && (
        <div className="p-3 bg-slate-800/50 rounded-lg border border-slate-700 space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-xs text-slate-400">Speed</span>
            <span className="text-xs font-semibold text-slate-200">
              {currentInferenceMetrics.tokensPerSecond?.toFixed(1) ?? '0'} tok/s
            </span>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-xs text-slate-400">First Token</span>
            <span className="text-xs font-semibold text-slate-200">
              {currentInferenceMetrics.firstTokenLatencyMs ?? 0}ms
            </span>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-xs text-slate-400">Context Used</span>
            <span className="text-xs font-semibold text-slate-200">
              {((currentInferenceMetrics.contextUtilization ?? 0) * 100).toFixed(0)}%
            </span>
          </div>
        </div>
      )}
    </div>
  );
};

export default MetricsSection;
