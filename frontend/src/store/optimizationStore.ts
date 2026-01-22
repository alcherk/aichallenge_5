// Optimization state management with Zustand
// Manages prompt modes, Ollama options, and sidebar state

import { create } from 'zustand';
import type {
  PromptMode,
  OllamaOptions,
  CategoryDefaults,
  CategoryInfo,
  ModelInfo,
  ClassificationResult,
} from '@/types';
import {
  DEFAULT_OLLAMA_OPTIONS,
  CATEGORY_DEFAULTS,
  CATEGORY_INFO,
} from '@/types';
import { optimizationStorage } from '@/services/storage';

/**
 * Model limits from Ollama API
 */
interface ModelLimits {
  contextLength: number;
  defaultNumCtx: number;
}

/**
 * Optimization store state
 */
interface OptimizationState {
  // Current prompt mode (auto = LLM classification)
  promptMode: PromptMode;

  // Ollama generation parameters
  ollamaOptions: OllamaOptions;

  // Custom templates per category (overrides backend defaults)
  customTemplates: Partial<Record<PromptMode, string>>;

  // Backend default templates (loaded from API)
  defaultTemplates: Record<PromptMode, string>;

  // Category defaults from backend
  categoryDefaults: Record<PromptMode, CategoryDefaults>;

  // Category display info
  categoryInfo: Record<PromptMode, CategoryInfo>;

  // Model limits from Ollama
  modelLimits: ModelLimits | null;

  // Last classification result (from backend response)
  lastClassification: ClassificationResult | null;

  // Sidebar visibility
  sidebarCollapsed: boolean;

  // Loading states
  isLoadingTemplates: boolean;
  isLoadingModelInfo: boolean;

  // Actions
  setPromptMode: (mode: PromptMode) => void;
  setOllamaOption: <K extends keyof OllamaOptions>(key: K, value: OllamaOptions[K]) => void;
  setOllamaOptions: (options: Partial<OllamaOptions>) => void;
  setCustomTemplate: (mode: PromptMode, template: string) => void;
  clearCustomTemplate: (mode: PromptMode) => void;
  setLastClassification: (result: ClassificationResult | null) => void;
  setSidebarCollapsed: (collapsed: boolean) => void;
  toggleSidebar: () => void;

  // Apply category defaults (num_ctx, temperature)
  applyCategoryDefaults: (mode: PromptMode) => void;

  // Get effective template (custom or default)
  getEffectiveTemplate: (mode: PromptMode) => string;

  // Persistence
  loadFromStorage: () => void;
  resetToDefaults: () => void;

  // API calls
  fetchTemplates: () => Promise<void>;
  fetchModelInfo: (modelName: string) => Promise<void>;
}

export const useOptimizationStore = create<OptimizationState>((set, get) => ({
  // Initial state
  promptMode: 'auto',
  ollamaOptions: { ...DEFAULT_OLLAMA_OPTIONS },
  customTemplates: {},
  defaultTemplates: {} as Record<PromptMode, string>,
  categoryDefaults: CATEGORY_DEFAULTS,
  categoryInfo: CATEGORY_INFO,
  modelLimits: null,
  lastClassification: null,
  sidebarCollapsed: true,
  isLoadingTemplates: false,
  isLoadingModelInfo: false,

  // Actions
  setPromptMode: (promptMode) => {
    set({ promptMode });
    optimizationStorage.setPromptMode(promptMode);

    // Apply category defaults when manually selecting a mode
    if (promptMode !== 'auto') {
      get().applyCategoryDefaults(promptMode);
    }
  },

  setOllamaOption: (key, value) => {
    set((state) => {
      const newOptions = { ...state.ollamaOptions, [key]: value };
      optimizationStorage.setOllamaOptions(newOptions);
      return { ollamaOptions: newOptions };
    });
  },

  setOllamaOptions: (options) => {
    set((state) => {
      const newOptions = { ...state.ollamaOptions, ...options };
      optimizationStorage.setOllamaOptions(newOptions);
      return { ollamaOptions: newOptions };
    });
  },

  setCustomTemplate: (mode, template) => {
    set((state) => {
      const newTemplates = { ...state.customTemplates, [mode]: template };
      optimizationStorage.setCustomTemplates(newTemplates);
      return { customTemplates: newTemplates };
    });
  },

  clearCustomTemplate: (mode) => {
    set((state) => {
      const newTemplates = { ...state.customTemplates };
      delete newTemplates[mode];
      optimizationStorage.setCustomTemplates(newTemplates);
      return { customTemplates: newTemplates };
    });
  },

  setLastClassification: (lastClassification) => {
    set({ lastClassification });
  },

  setSidebarCollapsed: (sidebarCollapsed) => {
    set({ sidebarCollapsed });
    optimizationStorage.setSidebarCollapsed(sidebarCollapsed);
  },

  toggleSidebar: () => {
    const { sidebarCollapsed } = get();
    get().setSidebarCollapsed(!sidebarCollapsed);
  },

  applyCategoryDefaults: (mode) => {
    const { categoryDefaults } = get();
    const defaults = categoryDefaults[mode];
    if (defaults) {
      set((state) => ({
        ollamaOptions: {
          ...state.ollamaOptions,
          num_ctx: defaults.num_ctx,
        },
      }));
    }
  },

  getEffectiveTemplate: (mode) => {
    const { customTemplates, defaultTemplates } = get();
    return customTemplates[mode] ?? defaultTemplates[mode] ?? '';
  },

  loadFromStorage: () => {
    try {
      const stored = optimizationStorage.get();
      set({
        promptMode: stored.promptMode || 'auto',
        ollamaOptions: { ...DEFAULT_OLLAMA_OPTIONS, ...stored.ollamaOptions },
        customTemplates: stored.customTemplates || {},
        sidebarCollapsed: stored.sidebarCollapsed ?? true, // Default to collapsed
      });
    } catch (error) {
      console.warn('Failed to load optimization settings:', error);
      // Keep defaults
    }
  },

  resetToDefaults: () => {
    set({
      promptMode: 'auto',
      ollamaOptions: { ...DEFAULT_OLLAMA_OPTIONS },
      customTemplates: {},
      lastClassification: null,
    });
    optimizationStorage.reset();
  },

  fetchTemplates: async () => {
    set({ isLoadingTemplates: true });
    try {
      const response = await fetch('/api/prompt-templates');
      if (response.ok) {
        const data = await response.json();
        set({
          defaultTemplates: data.templates,
          categoryDefaults: data.defaults,
          categoryInfo: data.categories,
        });
      }
    } catch (error) {
      console.warn('Failed to fetch prompt templates:', error);
    } finally {
      set({ isLoadingTemplates: false });
    }
  },

  fetchModelInfo: async (modelName: string) => {
    set({ isLoadingModelInfo: true });
    try {
      const response = await fetch(`/api/ollama/model/${encodeURIComponent(modelName)}`);
      if (response.ok) {
        const data: ModelInfo = await response.json();
        set({
          modelLimits: {
            contextLength: data.context_length,
            defaultNumCtx: data.default_num_ctx,
          },
        });
      }
    } catch (error) {
      console.warn('Failed to fetch model info:', error);
    } finally {
      set({ isLoadingModelInfo: false });
    }
  },
}));
