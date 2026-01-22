import React, { useEffect } from 'react';
import { useOptimizationStore } from '@/store/optimizationStore';
import { useSettingsStore } from '@/store/settingsStore';
import { ModeSelector } from './ModeSelector';
import { ContextSlider } from './ContextSlider';
import { ParametersSection } from './ParametersSection';
import { MetricsSection } from './MetricsSection';

/**
 * SettingsSidebar - Right collapsible sidebar for optimization settings.
 * Contains prompt mode selector, context slider, parameters, and metrics.
 */
export const SettingsSidebar: React.FC = () => {
  const {
    sidebarCollapsed,
    toggleSidebar,
    fetchTemplates,
    fetchModelInfo,
    resetToDefaults,
  } = useOptimizationStore();

  const { localModel } = useSettingsStore();

  // Fetch templates on mount (loadFromStorage is called in App.tsx)
  useEffect(() => {
    fetchTemplates();
  }, [fetchTemplates]);

  // Fetch model info when local model changes
  useEffect(() => {
    if (localModel.provider === 'local' && localModel.model) {
      fetchModelInfo(localModel.model);
    }
  }, [localModel.provider, localModel.model, fetchModelInfo]);

  // Only show for local provider
  if (localModel.provider !== 'local') {
    return null;
  }

  return (
    <>
      {/* Collapsed toggle button */}
      {sidebarCollapsed && (
        <button
          onClick={toggleSidebar}
          className="fixed right-0 top-1/2 -translate-y-1/2 z-40 bg-slate-800 border border-slate-700 border-r-0 rounded-l-lg p-2 shadow-lg hover:bg-slate-700 transition-colors group"
          title="Open optimization settings"
        >
          <svg
            xmlns="http://www.w3.org/2000/svg"
            className="h-5 w-5 text-slate-400 group-hover:text-teal-400 transition-colors"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M12 6V4m0 2a2 2 0 100 4m0-4a2 2 0 110 4m-6 8a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4m6 6v10m6-2a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4"
            />
          </svg>
        </button>
      )}

      {/* Sidebar panel */}
      <div
        className={`fixed right-0 top-0 h-full z-50 bg-slate-900 border-l border-slate-700 shadow-2xl transition-transform duration-300 ease-in-out ${
          sidebarCollapsed ? 'translate-x-full' : 'translate-x-0'
        }`}
        style={{ width: '320px' }}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3 bg-slate-800 border-b border-slate-700">
          <h3 className="text-sm font-semibold text-slate-100 flex items-center gap-2">
            <span>Optimization</span>
          </h3>
          <div className="flex items-center gap-2">
            <button
              onClick={resetToDefaults}
              className="text-xs text-slate-500 hover:text-slate-300 transition-colors"
              title="Reset to defaults"
            >
              Reset
            </button>
            <button
              onClick={toggleSidebar}
              className="text-slate-400 hover:text-slate-200 transition-colors p-1"
              title="Close sidebar"
            >
              <svg
                xmlns="http://www.w3.org/2000/svg"
                className="h-5 w-5"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M6 18L18 6M6 6l12 12"
                />
              </svg>
            </button>
          </div>
        </div>

        {/* Content */}
        <div className="overflow-y-auto h-[calc(100%-56px)] p-4 space-y-6">
          {/* Mode Selector */}
          <ModeSelector />

          {/* Divider */}
          <div className="border-t border-slate-700" />

          {/* Context Slider */}
          <ContextSlider />

          {/* Divider */}
          <div className="border-t border-slate-700" />

          {/* Parameters */}
          <ParametersSection />

          {/* Divider */}
          <div className="border-t border-slate-700" />

          {/* Metrics */}
          <MetricsSection />
        </div>
      </div>

      {/* Backdrop when open - lower z-index than main content area */}
      {!sidebarCollapsed && (
        <div
          className="fixed inset-0 bg-black/30 z-30"
          onClick={toggleSidebar}
        />
      )}
    </>
  );
};

export default SettingsSidebar;
