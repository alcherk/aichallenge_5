import React from 'react';
import { useOptimizationStore } from '@/store/optimizationStore';
import { useSettingsStore } from '@/store/settingsStore';

/**
 * ParametersSection - Advanced Ollama generation parameters.
 * Includes temperature, max_tokens (num_predict), repeat_penalty, GPU layers, threads.
 */
export const ParametersSection: React.FC = () => {
  const { ollamaOptions, setOllamaOption, categoryDefaults, promptMode } = useOptimizationStore();
  const { temperature, setTemperature } = useSettingsStore();

  // Get category defaults for display
  const defaults = categoryDefaults[promptMode === 'auto' ? 'general' : promptMode];

  return (
    <div className="space-y-4">
      <h4 className="text-xs font-semibold text-slate-400 uppercase tracking-wide">
        Generation Parameters
      </h4>

      {/* Temperature */}
      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <label className="text-xs text-slate-400">Temperature</label>
          <span className="text-xs font-semibold text-slate-200">
            {temperature.toFixed(2)}
          </span>
        </div>
        <input
          type="range"
          min={0}
          max={2}
          step={0.05}
          value={temperature}
          onChange={(e) => setTemperature(Number(e.target.value))}
          className="w-full h-1.5 bg-slate-700 rounded-lg appearance-none cursor-pointer accent-teal-500"
        />
        <div className="flex justify-between text-[10px] text-slate-600">
          <span>Precise</span>
          <span className="text-slate-500">Default: {defaults.temperature}</span>
          <span>Creative</span>
        </div>
      </div>

      {/* Max Tokens (num_predict) */}
      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <label className="text-xs text-slate-400">Max Tokens</label>
          <span className="text-xs font-semibold text-slate-200">
            {ollamaOptions.num_predict ?? 2048}
          </span>
        </div>
        <input
          type="range"
          min={128}
          max={4096}
          step={128}
          value={ollamaOptions.num_predict ?? 2048}
          onChange={(e) => setOllamaOption('num_predict', Number(e.target.value))}
          className="w-full h-1.5 bg-slate-700 rounded-lg appearance-none cursor-pointer accent-teal-500"
        />
        <div className="flex justify-between text-[10px] text-slate-600">
          <span>128</span>
          <span>2048</span>
          <span>4096</span>
        </div>
      </div>

      {/* Repeat Penalty */}
      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <label className="text-xs text-slate-400">Repeat Penalty</label>
          <span className="text-xs font-semibold text-slate-200">
            {(ollamaOptions.repeat_penalty ?? 1.1).toFixed(2)}
          </span>
        </div>
        <input
          type="range"
          min={1.0}
          max={2.0}
          step={0.05}
          value={ollamaOptions.repeat_penalty ?? 1.1}
          onChange={(e) => setOllamaOption('repeat_penalty', Number(e.target.value))}
          className="w-full h-1.5 bg-slate-700 rounded-lg appearance-none cursor-pointer accent-teal-500"
        />
        <div className="flex justify-between text-[10px] text-slate-600">
          <span>1.0 (none)</span>
          <span>1.5</span>
          <span>2.0 (high)</span>
        </div>
      </div>

      {/* Collapsible advanced section */}
      <details className="group">
        <summary className="text-xs text-slate-500 cursor-pointer hover:text-slate-300 transition-colors">
          Hardware Settings
        </summary>
        <div className="mt-3 space-y-3 pl-2 border-l-2 border-slate-700">
          {/* GPU Layers */}
          <div className="space-y-1">
            <div className="flex items-center justify-between">
              <label className="text-xs text-slate-400">GPU Layers</label>
              <span className="text-xs font-semibold text-slate-200">
                {ollamaOptions.num_gpu ?? 99}
              </span>
            </div>
            <input
              type="range"
              min={0}
              max={99}
              step={1}
              value={ollamaOptions.num_gpu ?? 99}
              onChange={(e) => setOllamaOption('num_gpu', Number(e.target.value))}
              className="w-full h-1 bg-slate-700 rounded-lg appearance-none cursor-pointer accent-teal-500"
            />
            <p className="text-[10px] text-slate-600">
              99 = all layers on GPU
            </p>
          </div>

          {/* CPU Threads */}
          <div className="space-y-1">
            <div className="flex items-center justify-between">
              <label className="text-xs text-slate-400">CPU Threads</label>
              <span className="text-xs font-semibold text-slate-200">
                {ollamaOptions.num_thread ?? 8}
              </span>
            </div>
            <input
              type="range"
              min={1}
              max={16}
              step={1}
              value={ollamaOptions.num_thread ?? 8}
              onChange={(e) => setOllamaOption('num_thread', Number(e.target.value))}
              className="w-full h-1 bg-slate-700 rounded-lg appearance-none cursor-pointer accent-teal-500"
            />
          </div>
        </div>
      </details>
    </div>
  );
};

export default ParametersSection;
