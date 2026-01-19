import React from 'react';
import type { ModelProvider } from '@/types';

interface ProviderBadgeProps {
  provider: ModelProvider;
}

/**
 * Badge component that displays the current LLM provider (local or cloud).
 *
 * - Local: teal/green accent indicating local Ollama model
 * - Cloud: blue accent indicating OpenAI cloud model
 */
export const ProviderBadge: React.FC<ProviderBadgeProps> = ({ provider }) => {
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
            ? 'bg-teal-100 text-teal-800 border-teal-300 dark:bg-teal-900/30 dark:text-teal-300 dark:border-teal-700'
            : 'bg-blue-100 text-blue-800 border-blue-300 dark:bg-blue-900/30 dark:text-blue-300 dark:border-blue-700'
        }
      `}
      role="status"
      aria-label={`Using ${isLocal ? 'local' : 'cloud'} model`}
    >
      {isLocal ? (
        <>
          <span aria-hidden="true">&#128421;</span>
          <span>Local</span>
        </>
      ) : (
        <>
          <span aria-hidden="true">&#9729;</span>
          <span>Cloud</span>
        </>
      )}
    </div>
  );
};
