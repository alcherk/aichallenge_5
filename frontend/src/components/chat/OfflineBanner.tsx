import React from 'react';

interface OfflineBannerProps {
  onRetry?: () => void;
  isRetrying?: boolean;
}

/**
 * Banner component that displays when Ollama is unavailable.
 *
 * Shows a prominent amber/yellow warning banner at the top of the chat area
 * to inform users the local model is unavailable.
 */
export const OfflineBanner: React.FC<OfflineBannerProps> = ({ onRetry, isRetrying }) => {
  return (
    <div
      className="
        sticky top-0 z-50
        flex items-center justify-center gap-2
        px-4 py-2
        bg-amber-900/60 text-amber-200
        border-b border-amber-700
        text-sm font-medium
        shadow-sm
      "
      role="alert"
      aria-live="polite"
    >
      <span aria-hidden="true">⚠️</span>
      <span>Ollama Unavailable — Local model cannot be used</span>
      {onRetry && (
        <button
          onClick={onRetry}
          disabled={isRetrying}
          className="ml-2 px-2 py-1 bg-amber-700 hover:bg-amber-600 rounded text-xs disabled:opacity-50"
        >
          {isRetrying ? 'Checking...' : 'Retry'}
        </button>
      )}
    </div>
  );
};
