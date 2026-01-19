import React from 'react';
import type { ModelProvider } from '@/types';

export interface ProviderBadgeProps {
  provider: ModelProvider;
  model?: string;
}

/**
 * Badge component that displays the current LLM provider and model.
 *
 * - Local: teal/green accent indicating local Ollama model
 * - Cloud: blue accent indicating OpenAI cloud model
 */
export const ProviderBadge: React.FC<ProviderBadgeProps> = ({ provider, model }) => {
  const isLocal = provider === 'local';

  return (
    <div
      className={`
        inline-flex items-center gap-1.5
        px-3 py-1.5
        text-sm font-medium
        rounded-full
        border
        transition-all duration-300 ease-in-out
        ${
          isLocal
            ? 'bg-teal-900/30 text-teal-300 border-teal-700'
            : 'bg-blue-900/30 text-blue-300 border-blue-700'
        }
      `}
      role="status"
      aria-label={`Using ${isLocal ? 'local' : 'cloud'} model${model ? `: ${model}` : ''}`}
    >
      {isLocal ? (
        <>
          <span aria-hidden="true">🖥️</span>
          <span>Local</span>
        </>
      ) : (
        <>
          <span aria-hidden="true">☁️</span>
          <span>Cloud</span>
        </>
      )}
      {model && (
        <span className="text-slate-400 ml-1">• {model}</span>
      )}
    </div>
  );
};
