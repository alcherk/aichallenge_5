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
    mcpEnabled,
    mcpConfigPath,
    workspaceRoot,
    setSystemPrompt,
    setTemperature,
    setModel,
    setCompressionThreshold,
    setMcpEnabled,
    setMcpConfigPath,
    setWorkspaceRoot,
    resetToDefaults,
  } = useSettingsStore();

  const { messages, setMessages } = useChatStore();

  // Local state for editing
  const [localSystemPrompt, setLocalSystemPrompt] = useState(systemPrompt);
  const [localTemperature, setLocalTemperature] = useState(temperature);
  const [localModel, setLocalModel] = useState(model);
  const [localCompressionThreshold, setLocalCompressionThreshold] = useState(compressionThreshold);
  const [localMcpEnabled, setLocalMcpEnabled] = useState(mcpEnabled);
  const [localMcpConfigPath, setLocalMcpConfigPath] = useState(mcpConfigPath);
  const [localWorkspaceRoot, setLocalWorkspaceRoot] = useState(workspaceRoot);

  // Sync local state when settings change
  useEffect(() => {
    setLocalSystemPrompt(systemPrompt);
    setLocalTemperature(temperature);
    setLocalModel(model);
    setLocalCompressionThreshold(compressionThreshold);
    setLocalMcpEnabled(mcpEnabled);
    setLocalMcpConfigPath(mcpConfigPath);
    setLocalWorkspaceRoot(workspaceRoot);
  }, [systemPrompt, temperature, model, compressionThreshold, mcpEnabled, mcpConfigPath, workspaceRoot]);

  const handleSave = () => {
    setSystemPrompt(localSystemPrompt);
    setTemperature(localTemperature);
    setModel(localModel);
    setCompressionThreshold(localCompressionThreshold);
    setMcpEnabled(localMcpEnabled);
    setMcpConfigPath(localMcpConfigPath);
    setWorkspaceRoot(localWorkspaceRoot);

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
      setLocalMcpEnabled(DEFAULT_SETTINGS.mcpEnabled);
      setLocalMcpConfigPath(DEFAULT_SETTINGS.mcpConfigPath);
      setLocalWorkspaceRoot(DEFAULT_SETTINGS.workspaceRoot);
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

          {/* MCP Settings */}
          <div className="border-t border-slate-700 pt-6">
            <div className="flex items-center justify-between mb-2">
              <label className="block text-sm font-semibold text-slate-300">
                MCP (Tools)
              </label>
              <label className="flex items-center gap-2 text-sm text-slate-300">
                <input
                  type="checkbox"
                  checked={localMcpEnabled}
                  onChange={(e) => {
                    const next = e.target.checked;
                    setLocalMcpEnabled(next);
                    // Apply immediately so chat requests reflect the toggle even if user closes without Save.
                    setMcpEnabled(next);
                  }}
                  className="h-4 w-4 rounded border-slate-600 bg-slate-800 text-blue-600 focus:ring-blue-500"
                />
                Enable
              </label>
            </div>

            <p className="text-xs text-slate-400 mb-3">
              When enabled, the backend will connect to configured MCP servers and expose their tools to the assistant.
            </p>

            {localMcpEnabled && (
              <div className="space-y-3">
                <div>
                  <label className="block text-xs font-semibold text-slate-400 mb-1">
                    MCP config path (server file path)
                  </label>
                  <input
                    type="text"
                    value={localMcpConfigPath}
                    onChange={(e) => setLocalMcpConfigPath(e.target.value)}
                    placeholder="/absolute/path/to/mcp_servers.json"
                    className="w-full px-3 py-2 rounded-lg border border-slate-600 bg-slate-800 text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                </div>

                <div>
                  <label className="block text-xs font-semibold text-slate-400 mb-1">
                    Workspace root (filesystem tools are restricted to this)
                  </label>
                  <input
                    type="text"
                    value={localWorkspaceRoot}
                    onChange={(e) => setLocalWorkspaceRoot(e.target.value)}
                    placeholder="/absolute/path/to/workspace"
                    className="w-full px-3 py-2 rounded-lg border border-slate-600 bg-slate-800 text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                </div>

                <p className="text-xs text-slate-500">
                  Tip: start from <span className="font-mono">mcp_servers.example.json</span>.
                </p>
              </div>
            )}
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
