// Settings state management with Zustand

import { create } from 'zustand';
import type { Settings, ModelName, LocalModelSettings } from '@/types';
import { DEFAULT_SETTINGS, DEFAULT_LOCAL_MODEL_SETTINGS } from '@/types';
import { settingsStorage } from '@/services/storage';

interface SettingsState extends Settings {
  // Actions
  setSystemPrompt: (prompt: string) => void;
  setTemperature: (temperature: number) => void;
  setModel: (model: ModelName) => void;
  setCompressionThreshold: (threshold: number) => void;
  setMcpEnabled: (enabled: boolean) => void;
  setMcpConfigPath: (path: string) => void;
  setWorkspaceRoot: (path: string) => void;
  setAssistantMode: (enabled: boolean) => void;
  resetToDefaults: () => void;
  loadFromStorage: () => void;
  // Local model actions
  setLocalModelSetting: <K extends keyof LocalModelSettings>(
    key: K,
    value: LocalModelSettings[K]
  ) => void;
  resetLocalModelSettings: () => void;
}

export const useSettingsStore = create<SettingsState>((set) => ({
  ...DEFAULT_SETTINGS,

  setSystemPrompt: (systemPrompt) => {
    set({ systemPrompt });
    settingsStorage.setSystemPrompt(systemPrompt);
  },

  setTemperature: (temperature) => {
    set({ temperature });
    settingsStorage.setTemperature(temperature);
  },

  setModel: (model) => {
    set({ model });
    settingsStorage.setModel(model);
  },

  setCompressionThreshold: (compressionThreshold) => {
    set({ compressionThreshold });
    settingsStorage.setCompressionThreshold(compressionThreshold);
  },

  setMcpEnabled: (mcpEnabled) => {
    set({ mcpEnabled });
    settingsStorage.setMcpEnabled(mcpEnabled);
  },

  setMcpConfigPath: (mcpConfigPath) => {
    set({ mcpConfigPath });
    settingsStorage.setMcpConfigPath(mcpConfigPath);
  },

  setWorkspaceRoot: (workspaceRoot) => {
    set({ workspaceRoot });
    settingsStorage.setWorkspaceRoot(workspaceRoot);
  },

  setAssistantMode: (assistantMode) => {
    set({ assistantMode });
    settingsStorage.setAssistantMode(assistantMode);
  },

  resetToDefaults: () => {
    set(DEFAULT_SETTINGS);
    settingsStorage.set(DEFAULT_SETTINGS);
  },

  loadFromStorage: () => {
    const settings = settingsStorage.get();
    set(settings);
  },

  setLocalModelSetting: (key, value) => {
    set((state) => {
      const newLocalModel = { ...state.localModel, [key]: value };
      settingsStorage.setLocalModel(newLocalModel);
      return { localModel: newLocalModel };
    });
  },

  resetLocalModelSettings: () => {
    set({ localModel: DEFAULT_LOCAL_MODEL_SETTINGS });
    settingsStorage.setLocalModel(DEFAULT_LOCAL_MODEL_SETTINGS);
  },
}));
