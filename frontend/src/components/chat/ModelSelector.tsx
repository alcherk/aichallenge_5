import React, { useState, useRef, useEffect, useCallback } from 'react';
import { useSettingsStore } from '@/store/settingsStore';
import { chatAPI } from '@/services/api';

type ModelStatus = 'loaded' | 'available' | 'unavailable';

interface ModelOption {
  name: string;
  provider: 'local' | 'cloud';
  available?: boolean;
  status?: ModelStatus;
  description?: string;
}

interface ModelSelectorProps {
  className?: string;
}

// Cloud models are always available
const CLOUD_MODELS: ModelOption[] = [
  { name: 'gpt-4o-mini', provider: 'cloud', available: true, status: 'available', description: 'Recommended - Fast and affordable' },
  { name: 'gpt-4o', provider: 'cloud', available: true, status: 'available', description: 'Most powerful, multimodal' },
  { name: 'gpt-4-turbo', provider: 'cloud', available: true, status: 'available', description: 'Fast and capable' },
];

// Format model size for display
const formatSize = (bytes: number): string => {
  const gb = bytes / (1024 * 1024 * 1024);
  return `${gb.toFixed(1)}GB`;
};

const getStatusIndicator = (status: ModelStatus | undefined): { color: string; label: string } => {
  switch (status) {
    case 'loaded':
      return { color: 'bg-green-500', label: 'Loaded' };
    case 'available':
      return { color: 'bg-blue-500', label: 'Available' };
    case 'unavailable':
      return { color: 'bg-slate-500', label: 'Unavailable' };
    default:
      return { color: 'bg-slate-500', label: 'Unknown' };
  }
};

const getProviderIcon = (provider: 'local' | 'cloud'): string => {
  return provider === 'local' ? '\u{1F5A5}' : '\u2601'; // Desktop computer / Cloud emoji
};

export const ModelSelector: React.FC<ModelSelectorProps> = ({
  className = ''
}) => {
  const { localModel, setLocalModelSetting } = useSettingsStore();
  const [isOpen, setIsOpen] = useState(false);
  const [localModels, setLocalModels] = useState<ModelOption[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  // Fetch models from Ollama
  const fetchLocalModels = useCallback(async () => {
    setIsLoading(true);
    try {
      const models = await chatAPI.getOllamaModels();
      const modelOptions: ModelOption[] = models.map((m) => ({
        name: m.name,
        provider: 'local' as const,
        available: true,
        status: 'available' as ModelStatus,
        description: `${formatSize(m.size)} - Installed`,
      }));
      setLocalModels(modelOptions);
    } catch (error) {
      console.error('Failed to fetch Ollama models:', error);
      setLocalModels([]);
    } finally {
      setIsLoading(false);
    }
  }, []);

  // Fetch models on mount
  useEffect(() => {
    fetchLocalModels();
  }, [fetchLocalModels]);

  // Cloud models are always available
  const cloudModels = CLOUD_MODELS;

  // All models combined
  const allModels = [...localModels, ...cloudModels];

  // Find currently selected model
  const currentModel = allModels.find(m => m.name === localModel.model) || {
    name: localModel.model,
    provider: localModel.provider,
    available: true,
    status: 'available' as ModelStatus,
  };

  // Close dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  // Close dropdown on Escape key
  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setIsOpen(false);
      }
    };

    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, []);

  const handleSelectModel = (model: ModelOption) => {
    if (model.available === false) return;

    setLocalModelSetting('model', model.name);
    setLocalModelSetting('provider', model.provider);
    setIsOpen(false);
  };

  const renderModelOption = (model: ModelOption, isSelected: boolean) => {
    const status = getStatusIndicator(model.status);
    const isDisabled = model.available === false;

    return (
      <button
        key={model.name}
        onClick={() => handleSelectModel(model)}
        disabled={isDisabled}
        className={`
          w-full px-3 py-2 text-left flex items-center gap-3 transition-colors
          ${isSelected ? 'bg-blue-600/20 border-l-2 border-blue-500' : 'border-l-2 border-transparent'}
          ${isDisabled
            ? 'opacity-50 cursor-not-allowed text-slate-500'
            : 'hover:bg-slate-700/50 cursor-pointer text-slate-100'
          }
        `}
        aria-selected={isSelected}
        role="option"
      >
        {/* Status indicator dot */}
        <span
          className={`w-2 h-2 rounded-full flex-shrink-0 ${status.color}`}
          title={status.label}
        />

        {/* Model info */}
        <div className="flex-1 min-w-0">
          <div className="font-medium truncate">{model.name}</div>
          {model.description && (
            <div className="text-xs text-slate-400 truncate">{model.description}</div>
          )}
        </div>

        {/* Selection checkmark */}
        {isSelected && (
          <svg className="w-4 h-4 text-blue-400 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
          </svg>
        )}
      </button>
    );
  };

  return (
    <div className={`relative ${className}`} ref={dropdownRef}>
      {/* Dropdown trigger button */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="
          flex items-center gap-2 px-3 py-2
          bg-slate-800 border border-slate-600 rounded-lg
          hover:bg-slate-700 hover:border-slate-500
          focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent
          transition-colors text-sm
        "
        aria-haspopup="listbox"
        aria-expanded={isOpen}
      >
        {/* Provider icon */}
        <span className="text-sm" aria-hidden="true">
          {getProviderIcon(currentModel.provider)}
        </span>

        {/* Model name */}
        <span className="text-slate-100 font-medium max-w-[150px] truncate">
          {currentModel.name}
        </span>

        {/* Dropdown arrow */}
        <svg
          className={`w-4 h-4 text-slate-400 transition-transform ${isOpen ? 'rotate-180' : ''}`}
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      {/* Dropdown menu */}
      {isOpen && (
        <div
          className="
            absolute z-50 mt-1 w-72
            bg-slate-800 border border-slate-600 rounded-lg shadow-xl
            overflow-hidden
          "
          role="listbox"
          aria-label="Select a model"
        >
          {/* Local Models Section */}
          <div>
            <div className="px-3 py-2 text-xs font-semibold text-slate-400 uppercase tracking-wide bg-slate-900/50 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span>{getProviderIcon('local')}</span>
                <span>Local Models (Ollama)</span>
              </div>
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  fetchLocalModels();
                }}
                disabled={isLoading}
                className="text-xs px-2 py-0.5 bg-slate-700 hover:bg-slate-600 rounded disabled:opacity-50"
                title="Refresh models from Ollama"
              >
                {isLoading ? '...' : '↻'}
              </button>
            </div>
            <div role="group" aria-label="Local models">
              {localModels.length > 0 ? (
                localModels.map(model => renderModelOption(model, model.name === currentModel.name))
              ) : (
                <div className="px-3 py-2 text-sm text-slate-500 italic">
                  {isLoading ? 'Loading...' : 'No models installed. Run: ollama pull llama3.2'}
                </div>
              )}
            </div>
          </div>

          {/* Cloud Models Section */}
          {cloudModels.length > 0 && (
            <div>
              <div className="px-3 py-2 text-xs font-semibold text-slate-400 uppercase tracking-wide bg-slate-900/50 flex items-center gap-2 border-t border-slate-700">
                <span>{getProviderIcon('cloud')}</span>
                <span>Cloud Models</span>
              </div>
              <div role="group" aria-label="Cloud models">
                {cloudModels.map(model => renderModelOption(model, model.name === currentModel.name))}
              </div>
            </div>
          )}

        </div>
      )}
    </div>
  );
};

export default ModelSelector;
