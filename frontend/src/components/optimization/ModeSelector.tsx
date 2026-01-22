import React from 'react';
import { useOptimizationStore } from '@/store/optimizationStore';
import type { PromptMode } from '@/types';

/**
 * ModeSelector - Dropdown for selecting prompt classification mode.
 * Options: Auto (LLM classification), Code, Creative, Analysis, General
 */
export const ModeSelector: React.FC = () => {
  const { promptMode, setPromptMode, categoryInfo } = useOptimizationStore();

  const modes: PromptMode[] = ['auto', 'code', 'creative', 'analysis', 'general'];

  return (
    <div className="space-y-2">
      <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wide">
        Prompt Mode
      </label>
      <select
        value={promptMode}
        onChange={(e) => setPromptMode(e.target.value as PromptMode)}
        className="w-full px-3 py-2 rounded-lg border border-slate-600 bg-slate-800 text-slate-100 text-sm focus:outline-none focus:ring-2 focus:ring-teal-500 cursor-pointer"
      >
        {modes.map((mode) => {
          const info = categoryInfo[mode];
          if (!info) return null;
          return (
            <option key={mode} value={mode}>
              {info.emoji} {info.name}
            </option>
          );
        })}
      </select>
      <p className="text-xs text-slate-500">
        {categoryInfo[promptMode]?.description ?? ''}
      </p>
    </div>
  );
};

export default ModeSelector;
