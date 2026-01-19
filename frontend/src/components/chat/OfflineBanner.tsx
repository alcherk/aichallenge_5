import React from 'react';
import { useOnlineStatus } from '@/hooks/useOnlineStatus';

/**
 * Banner component that displays when the browser is offline.
 *
 * Shows a prominent amber/yellow warning banner at the top of the chat area
 * to inform users they are in offline mode and will use the local model only.
 *
 * The banner automatically hides when the connection is restored.
 */
export const OfflineBanner: React.FC = () => {
  const isOnline = useOnlineStatus();

  if (isOnline) return null;

  return (
    <div
      className="
        sticky top-0 z-50
        flex items-center justify-center gap-2
        px-4 py-2
        bg-amber-100 text-amber-800
        border-b border-amber-300
        dark:bg-amber-900/40 dark:text-amber-200 dark:border-amber-700
        text-sm font-medium
        shadow-sm
      "
      role="alert"
      aria-live="polite"
    >
      <span aria-hidden="true">&#9889;</span>
      <span>Offline Mode — Using local model only</span>
    </div>
  );
};
