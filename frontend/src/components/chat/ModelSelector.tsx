import React, { useState, useRef, useEffect } from 'react';
import { useSettingsStore } from '@/store/settingsStore';

type ModelStatus = 'loaded' | 'available' | 'unavailable';

interface ModelOption {
  name: string;
  provider: 'local' | 'cloud';
  available?: boolean;
  status?: ModelStatus;
  description?: string;
}

interface ModelSelectorProps {
  models?: ModelOption[];
  className?: string;
}

// Placeholder models - actual API integration comes in D.5
const DEFAULT_LOCAL_MODELS: ModelOption[] = [
  { name: 'qwen2.5:14b', provider: 'local', available: true, status: 'available', description: 'Qwen 2.5 14B - Balanced performance' },
  { name: 'llama3.2:3b', provider: 'local', available: true, status: 'available', description: 'Llama 3.2 3B - Fast and lightweight' },
  { name: 'mistral:7b', provider: 'local', available: false, status: 'unavailable', description: 'Mistral 7B - Not installed' },
];

const DEFAULT_CLOUD_MODELS: ModelOption[] = [
  { name: 'gpt-4o-mini', provider: 'cloud', available: true, status: 'available', description: 'Recommended - Fast and affordable' },
  { name: 'gpt-4o', provider: 'cloud', available: true, status: 'available', description: 'Most powerful, multimodal' },
  { name: 'gpt-4-turbo', provider: 'cloud', available: true, status: 'available', description: 'Fast and capable' },
];

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
  models,
  className = ''
}) => {
  const { localModel, setLocalModelSetting } = useSettingsStore();
  const [isOpen, setIsOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  // Merge provided models with defaults
  const allModels = models || [...DEFAULT_LOCAL_MODELS, ...DEFAULT_CLOUD_MODELS];

  // Group models by provider
  const localModels = allModels.filter(m => m.provider === 'local');
  const cloudModels = allModels.filter(m => m.provider === 'cloud');

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
          {localModels.length > 0 && (
            <div>
              <div className="px-3 py-2 text-xs font-semibold text-slate-400 uppercase tracking-wide bg-slate-900/50 flex items-center gap-2">
                <span>{getProviderIcon('local')}</span>
                <span>Local Models</span>
              </div>
              <div role="group" aria-label="Local models">
                {localModels.map(model => renderModelOption(model, model.name === currentModel.name))}
              </div>
            </div>
          )}

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

          {/* Empty state */}
          {localModels.length === 0 && cloudModels.length === 0 && (
            <div className="px-3 py-4 text-center text-slate-400 text-sm">
              No models available
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default ModelSelector;
