import React from 'react';
import { useOptimizationStore } from '@/store/optimizationStore';
import { CONTEXT_SIZE_PRESETS } from '@/types';

/**
 * ContextSlider - Slider for selecting context window size (num_ctx).
 * Shows presets with memory hints and respects model limits.
 */
export const ContextSlider: React.FC = () => {
  const { ollamaOptions, setOllamaOption, modelLimits } = useOptimizationStore();

  const currentValue = ollamaOptions.num_ctx ?? 8192;
  const maxContext = modelLimits?.contextLength ?? 32768;

  // Filter presets to those within model limits
  const availablePresets = CONTEXT_SIZE_PRESETS.filter(
    (preset) => preset.value <= maxContext
  );

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const index = Number(e.target.value);
    const preset = availablePresets[index];
    if (preset) {
      setOllamaOption('num_ctx', preset.value);
    }
  };

  // Find current preset for display
  const currentPreset = CONTEXT_SIZE_PRESETS.find(
    (p) => p.value === currentValue
  ) ?? CONTEXT_SIZE_PRESETS[2]; // Default to 8K

  // Calculate utilization percentage if we have model limits
  const utilizationPercent = modelLimits
    ? Math.round((currentValue / modelLimits.contextLength) * 100)
    : null;

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <label className="text-xs font-semibold text-slate-400 uppercase tracking-wide">
          Context Window
        </label>
        <span className="text-sm font-semibold text-teal-400">
          {currentPreset.label}
        </span>
      </div>

      {/* Slider */}
      <input
        type="range"
        min={0}
        max={availablePresets.length - 1}
        step={1}
        value={availablePresets.findIndex((p) => p.value === currentValue) ?? 2}
        onChange={handleChange}
        className="w-full h-2 bg-slate-700 rounded-lg appearance-none cursor-pointer accent-teal-500"
      />

      {/* Preset labels */}
      <div className="flex justify-between text-xs text-slate-500">
        {availablePresets.map((preset) => (
          <span
            key={preset.value}
            className={preset.value === currentValue ? 'text-teal-400 font-semibold' : ''}
          >
            {preset.label}
          </span>
        ))}
      </div>

      {/* Description and memory hint */}
      <div className="flex items-center justify-between text-xs">
        <span className="text-slate-500">{currentPreset.description}</span>
        {utilizationPercent !== null && (
          <span className={`font-medium ${
            utilizationPercent > 80 ? 'text-red-400' :
            utilizationPercent > 60 ? 'text-yellow-400' : 'text-slate-400'
          }`}>
            {utilizationPercent}% of limit
          </span>
        )}
      </div>

      {/* Progress bar showing context utilization */}
      {modelLimits && (
        <div className="w-full bg-slate-700 rounded-full h-1">
          <div
            className={`h-1 rounded-full transition-all duration-300 ${
              utilizationPercent! > 80 ? 'bg-red-500' :
              utilizationPercent! > 60 ? 'bg-yellow-500' : 'bg-teal-500'
            }`}
            style={{ width: `${Math.min(utilizationPercent!, 100)}%` }}
          />
        </div>
      )}
    </div>
  );
};

export default ContextSlider;
