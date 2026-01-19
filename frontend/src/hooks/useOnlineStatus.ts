import { useState, useEffect } from 'react';

/**
 * Custom hook that tracks the browser's online/offline status.
 *
 * Uses the Navigator.onLine API and listens to 'online' and 'offline' events
 * to detect network connectivity changes in real-time.
 *
 * @returns {boolean} True if the browser is online, false if offline
 */
export function useOnlineStatus(): boolean {
  const [isOnline, setIsOnline] = useState<boolean>(navigator.onLine);

  useEffect(() => {
    const handleOnline = () => setIsOnline(true);
    const handleOffline = () => setIsOnline(false);

    window.addEventListener('online', handleOnline);
    window.addEventListener('offline', handleOffline);

    return () => {
      window.removeEventListener('online', handleOnline);
      window.removeEventListener('offline', handleOffline);
    };
  }, []);

  return isOnline;
}
