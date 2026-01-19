import React, { useState, useEffect, useCallback } from 'react';
import { useSettingsStore } from '@/store/settingsStore';
import { chatAPI } from '@/services/api';

interface OllamaModelOption {
  id: string;
  name: string;
  size: string;
}

// Format bytes to human readable
const formatSize = (bytes: number): string => {
  const gb = bytes / (1024 * 1024 * 1024);
  return `${gb.toFixed(1)}GB`;
};

interface SliderProps {
  label: string;
  value: number;
  min: number;
  max: number;
  step: number;
  onChange: (value: number) => void;
  formatValue?: (value: number) => string;
}

function Slider({ label, value, min, max, step, onChange, formatValue }: SliderProps) {
  const displayValue = formatValue ? formatValue(value) : value.toString();

  return (
    <div className="space-y-2">
      <div className="flex justify-between items-center">
        <label className="text-sm text-slate-300">{label}</label>
        <span className="text-sm font-mono text-slate-400">{displayValue}</span>
      </div>
      <input
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        className="w-full h-2 bg-slate-700 rounded-lg appearance-none cursor-pointer accent-blue-500"
      />
      <div className="flex justify-between text-xs text-slate-500">
        <span>{min}</span>
        <span>{max}</span>
      </div>
    </div>
  );
}

interface ToggleProps {
  label: string;
  checked: boolean;
  onChange: (checked: boolean) => void;
  description?: string;
}

function Toggle({ label, checked, onChange, description }: ToggleProps) {
  return (
    <div className="flex items-start justify-between gap-4">
      <div className="flex-1">
        <label className="text-sm font-medium text-slate-300">{label}</label>
        {description && (
          <p className="text-xs text-slate-500 mt-0.5">{description}</p>
        )}
      </div>
      <button
        role="switch"
        aria-checked={checked}
        onClick={() => onChange(!checked)}
        className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 focus:ring-offset-slate-800 ${
          checked ? 'bg-blue-600' : 'bg-slate-600'
        }`}
      >
        <span
          className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
            checked ? 'translate-x-6' : 'translate-x-1'
          }`}
        />
      </button>
    </div>
  );
}

interface CollapsibleProps {
  title: string;
  children: React.ReactNode;
  defaultOpen?: boolean;
}

function Collapsible({ title, children, defaultOpen = false }: CollapsibleProps) {
  const [isOpen, setIsOpen] = useState(defaultOpen);

  return (
    <div className="border border-slate-700 rounded-lg overflow-hidden">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="w-full px-4 py-3 flex items-center justify-between bg-slate-800 hover:bg-slate-750 transition-colors text-left"
      >
        <span className="text-sm font-medium text-slate-300">{title}</span>
        <svg
          className={`w-4 h-4 text-slate-400 transition-transform ${isOpen ? 'rotate-180' : ''}`}
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </button>
      {isOpen && (
        <div className="px-4 py-4 bg-slate-850 space-y-4">
          {children}
        </div>
      )}
    </div>
  );
}

interface ModelSelectorProps {
  value: string;
  onChange: (value: string) => void;
  models: OllamaModelOption[];
  isLoading?: boolean;
  onRefresh?: () => void;
}

function ModelSelector({ value, onChange, models, isLoading, onRefresh }: ModelSelectorProps) {
  return (
    <div className="flex gap-2">
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        disabled={isLoading || models.length === 0}
        className="flex-1 px-3 py-2 rounded-lg border border-slate-600 bg-slate-800 text-slate-100 focus:outline-none focus:ring-2 focus:ring-blue-500 cursor-pointer disabled:opacity-50"
      >
        {models.length === 0 ? (
          <option value="">
            {isLoading ? 'Loading...' : 'No models found'}
          </option>
        ) : (
          models.map((model) => (
            <option key={model.id} value={model.id}>
              {model.name} ({model.size})
            </option>
          ))
        )}
      </select>
      {onRefresh && (
        <button
          onClick={onRefresh}
          disabled={isLoading}
          title="Refresh models from Ollama"
          className="px-3 py-2 rounded-lg border border-slate-600 bg-slate-800 text-slate-300 hover:bg-slate-700 hover:text-slate-100 focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50 transition-colors"
        >
          {isLoading ? '...' : '↻'}
        </button>
      )}
    </div>
  );
}

interface ProviderToggleProps {
  provider: 'cloud' | 'local';
  onChange: (provider: 'cloud' | 'local') => void;
}

function ProviderToggle({ provider, onChange }: ProviderToggleProps) {
  return (
    <div className="flex rounded-lg border border-slate-600 overflow-hidden">
      <button
        onClick={() => onChange('cloud')}
        className={`flex-1 px-4 py-2 text-sm font-medium transition-colors ${
          provider === 'cloud'
            ? 'bg-blue-600 text-white'
            : 'bg-slate-800 text-slate-400 hover:text-slate-200 hover:bg-slate-700'
        }`}
      >
        <span className="mr-1.5">&#9729;</span>
        Cloud
      </button>
      <button
        onClick={() => onChange('local')}
        className={`flex-1 px-4 py-2 text-sm font-medium transition-colors ${
          provider === 'local'
            ? 'bg-teal-600 text-white'
            : 'bg-slate-800 text-slate-400 hover:text-slate-200 hover:bg-slate-700'
        }`}
      >
        <span className="mr-1.5">&#128421;</span>
        Local
      </button>
    </div>
  );
}

export function LocalModelSettings() {
  const { localModel, setLocalModelSetting, resetLocalModelSettings } = useSettingsStore();
  const [ollamaModels, setOllamaModels] = useState<OllamaModelOption[]>([]);
  const [isLoadingModels, setIsLoadingModels] = useState(false);

  // Fetch models from Ollama
  const fetchModels = useCallback(async () => {
    setIsLoadingModels(true);
    try {
      const models = await chatAPI.getOllamaModels();
      const modelOptions: OllamaModelOption[] = models.map((m) => ({
        id: m.name,
        name: m.name.split(':')[0], // Remove tag for display
        size: formatSize(m.size),
      }));
      setOllamaModels(modelOptions);

      // If current model is not in the list, select the first available
      if (modelOptions.length > 0 && !modelOptions.find(m => m.id === localModel.model)) {
        setLocalModelSetting('model', modelOptions[0].id);
      }
    } catch (error) {
      console.error('Failed to fetch Ollama models:', error);
      setOllamaModels([]);
    } finally {
      setIsLoadingModels(false);
    }
  }, [localModel.model, setLocalModelSetting]);

  // Fetch models on mount and when provider changes to local
  useEffect(() => {
    if (localModel.provider === 'local') {
      fetchModels();
    }
  }, [localModel.provider, fetchModels]);

  const handleProviderChange = (provider: 'cloud' | 'local') => {
    setLocalModelSetting('provider', provider);
    // When switching to local, enable local model; when switching to cloud, disable
    setLocalModelSetting('enabled', provider === 'local');
  };

  const handleReset = () => {
    if (confirm('Reset local model settings to defaults?')) {
      resetLocalModelSettings();
    }
  };

  return (
    <div className="space-y-6">
      {/* Section Header */}
      <div className="border-b border-slate-700 pb-2">
        <h3 className="text-lg font-semibold text-slate-200">Local Model</h3>
        <p className="text-xs text-slate-500 mt-1">
          Configure local LLM inference with Ollama
        </p>
      </div>

      {/* Provider Toggle */}
      <div className="space-y-2">
        <label className="block text-sm font-medium text-slate-300">
          Provider
        </label>
        <ProviderToggle
          provider={localModel.provider}
          onChange={handleProviderChange}
        />
        <p className="text-xs text-slate-500">
          {localModel.provider === 'local'
            ? 'Using local Ollama model for inference'
            : 'Using cloud API for inference'}
        </p>
      </div>

      {/* Model Selector - only show when local is selected */}
      {localModel.provider === 'local' && (
        <div className="space-y-2">
          <label className="block text-sm font-medium text-slate-300">
            Model
          </label>
          <ModelSelector
            value={localModel.model}
            onChange={(model) => setLocalModelSetting('model', model)}
            models={ollamaModels}
            isLoading={isLoadingModels}
            onRefresh={fetchModels}
          />
          <p className="text-xs text-slate-500">
            {ollamaModels.length > 0
              ? `${ollamaModels.length} model(s) installed`
              : 'Run: ollama pull llama3.2'}
          </p>
        </div>
      )}

      {/* RAG Toggle */}
      <Toggle
        label="Enable RAG"
        checked={localModel.ragEnabled}
        onChange={(checked) => setLocalModelSetting('ragEnabled', checked)}
        description="Augment responses with retrieved document context"
      />

      {/* Advanced Settings */}
      <Collapsible title="Advanced Settings">
        <Slider
          label="Temperature"
          value={localModel.temperature}
          min={0}
          max={2}
          step={0.1}
          onChange={(value) => setLocalModelSetting('temperature', value)}
          formatValue={(v) => v.toFixed(1)}
        />
        <p className="text-xs text-slate-500 -mt-2">
          Lower = more focused, Higher = more creative
        </p>

        <Slider
          label="Top P"
          value={localModel.topP}
          min={0}
          max={1}
          step={0.05}
          onChange={(value) => setLocalModelSetting('topP', value)}
          formatValue={(v) => v.toFixed(2)}
        />
        <p className="text-xs text-slate-500 -mt-2">
          Nucleus sampling threshold
        </p>

        <Slider
          label="Max Tokens"
          value={localModel.maxTokens}
          min={100}
          max={4096}
          step={100}
          onChange={(value) => setLocalModelSetting('maxTokens', value)}
          formatValue={(v) => v.toString()}
        />
        <p className="text-xs text-slate-500 -mt-2">
          Maximum tokens to generate
        </p>
      </Collapsible>

      {/* Reset Button */}
      <button
        onClick={handleReset}
        className="w-full px-4 py-2 text-sm font-medium text-slate-300 bg-slate-800 border border-slate-600 rounded-lg hover:bg-slate-700 hover:text-slate-200 transition-colors focus:outline-none focus:ring-2 focus:ring-slate-500"
      >
        Reset to Defaults
      </button>
    </div>
  );
}
