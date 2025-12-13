import React, { useState, useEffect } from 'react';
import { useSettingsStore } from '@/store/settingsStore';
import { useChatStore } from '@/store/chatStore';
import { ModelSelector } from './ModelSelector';
import { TemperatureSlider } from './TemperatureSlider';
import { SystemPromptEditor } from './SystemPromptEditor';
import { DEFAULT_SETTINGS } from '@/types';

interface SettingsPanelProps {
  isOpen: boolean;
  onClose: () => void;
}

export const SettingsPanel: React.FC<SettingsPanelProps> = ({ isOpen, onClose }) => {
  const {
    systemPrompt,
    temperature,
    model,
    compressionThreshold,
    setSystemPrompt,
    setTemperature,
    setModel,
    setCompressionThreshold,
    resetToDefaults,
  } = useSettingsStore();

  const { messages, setMessages } = useChatStore();

  // Local state for editing
  const [localSystemPrompt, setLocalSystemPrompt] = useState(systemPrompt);
  const [localTemperature, setLocalTemperature] = useState(temperature);
  const [localModel, setLocalModel] = useState(model);
  const [localCompressionThreshold, setLocalCompressionThreshold] = useState(compressionThreshold);

  // Sync local state when settings change
  useEffect(() => {
    setLocalSystemPrompt(systemPrompt);
    setLocalTemperature(temperature);
    setLocalModel(model);
    setLocalCompressionThreshold(compressionThreshold);
  }, [systemPrompt, temperature, model, compressionThreshold]);

  const handleSave = () => {
    setSystemPrompt(localSystemPrompt);
    setTemperature(localTemperature);
    setModel(localModel);
    setCompressionThreshold(localCompressionThreshold);

    // Update system message in current conversation
    const updatedMessages = [...messages];
    const systemIndex = updatedMessages.findIndex(m => m.role === 'system');
    if (systemIndex >= 0) {
      updatedMessages[systemIndex] = { role: 'system', content: localSystemPrompt };
    } else {
      updatedMessages.unshift({ role: 'system', content: localSystemPrompt });
    }
    setMessages(updatedMessages);

    onClose();
  };

  const handleReset = () => {
    if (confirm('Reset all settings to defaults?')) {
      setLocalSystemPrompt(DEFAULT_SETTINGS.systemPrompt);
      setLocalTemperature(DEFAULT_SETTINGS.temperature);
      setLocalModel(DEFAULT_SETTINGS.model);
      setLocalCompressionThreshold(DEFAULT_SETTINGS.compressionThreshold);
      resetToDefaults();
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black bg-opacity-75 backdrop-blur-sm flex items-center justify-center z-50 p-4">
      <div className="bg-slate-900 rounded-lg shadow-2xl border border-slate-700 max-w-2xl w-full max-h-[90vh] overflow-y-auto">
        {/* Header */}
        <div className="sticky top-0 bg-slate-800 border-b border-slate-700 px-6 py-4 flex items-center justify-between rounded-t-lg">
          <h2 className="text-xl font-bold text-slate-100">⚙️ Settings</h2>
          <button
            onClick={onClose}
            className="text-slate-400 hover:text-slate-200 text-2xl leading-none transition-colors"
            title="Close settings"
          >
            ×
          </button>
        </div>

        {/* Content */}
        <div className="p-6 space-y-6">
          {/* Model Selection */}
          <div>
            <label className="block text-sm font-semibold text-slate-300 mb-2">
              Model
            </label>
            <ModelSelector
              value={localModel}
              onChange={setLocalModel}
            />
          </div>

          {/* Temperature Slider */}
          <div>
            <label className="block text-sm font-semibold text-slate-300 mb-2">
              Temperature: {localTemperature.toFixed(1)}
            </label>
            <TemperatureSlider
              value={localTemperature}
              onChange={setLocalTemperature}
            />
            <p className="text-xs text-slate-400 mt-1">
              Lower values make output more focused and deterministic. Higher values make it more creative.
            </p>
          </div>

          {/* System Prompt */}
          <div>
            <label className="block text-sm font-semibold text-slate-300 mb-2">
              System Prompt
            </label>
            <SystemPromptEditor
              value={localSystemPrompt}
              onChange={setLocalSystemPrompt}
            />
          </div>

          {/* Compression Threshold */}
          <div>
            <label className="block text-sm font-semibold text-slate-300 mb-2">
              Compression Threshold: {localCompressionThreshold} messages
            </label>
            <input
              type="range"
              min={5}
              max={50}
              step={5}
              value={localCompressionThreshold}
              onChange={(e) => setLocalCompressionThreshold(Number(e.target.value))}
              className="w-full h-2 bg-slate-700 rounded-lg appearance-none cursor-pointer accent-blue-500"
            />
            <div className="flex justify-between text-xs text-slate-400 mt-1">
              <span>5</span>
              <span>27</span>
              <span>50</span>
            </div>
            <p className="text-xs text-slate-400 mt-1">
              Automatically compress conversation history after this many messages
            </p>
          </div>
        </div>

        {/* Footer Actions */}
        <div className="sticky bottom-0 bg-slate-800 border-t border-slate-700 px-6 py-4 flex gap-3 rounded-b-lg">
          <button
            onClick={handleSave}
            className="flex-1 px-4 py-2 bg-gradient-to-r from-blue-600 to-blue-700 text-white rounded-lg hover:from-blue-700 hover:to-blue-800 focus:outline-none focus:ring-2 focus:ring-blue-500 transition-all duration-200 font-semibold shadow-lg"
          >
            💾 Save
          </button>
          <button
            onClick={handleReset}
            className="px-4 py-2 bg-slate-700 text-slate-200 border border-slate-600 rounded-lg hover:bg-slate-600 focus:outline-none focus:ring-2 focus:ring-slate-500 transition-all duration-200"
          >
            🔄 Reset
          </button>
          <button
            onClick={onClose}
            className="px-4 py-2 bg-slate-800 border border-slate-600 text-slate-300 rounded-lg hover:bg-slate-700 focus:outline-none focus:ring-2 focus:ring-slate-500 transition-all duration-200"
          >
            ✕ Cancel
          </button>
        </div>
      </div>
    </div>
  );
};
