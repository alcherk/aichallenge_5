import { useEffect, useState } from 'react';
import { useChatStore } from './store/chatStore';
import { useSettingsStore } from './store/settingsStore';
import { useMetricsStore } from './store/metricsStore';
import { AppLayout } from './components/layout/AppLayout';
import { Header } from './components/layout/Header';
import { ChatContainer } from './components/chat/ChatContainer';
import { SettingsPanel } from './components/settings/SettingsPanel';
import { MetricsPanel } from './components/metrics/MetricsPanel';

function App() {
  const { loadFromStorage: loadChat, clearMessages } = useChatStore();
  const { loadFromStorage: loadSettings } = useSettingsStore();
  const { loadFromStorage: loadMetrics } = useMetricsStore();

  const [showSettings, setShowSettings] = useState(false);

  // Load persisted data on mount
  useEffect(() => {
    loadChat();
    loadSettings();
    loadMetrics();
  }, [loadChat, loadSettings, loadMetrics]);

  const handleNewChat = () => {
    clearMessages();
  };

  return (
    <AppLayout
      header={
        <Header
          onNewChat={handleNewChat}
          onSettingsClick={() => setShowSettings(true)}
        />
      }
    >
      <div className="flex h-full">
        {/* Chat Container - takes remaining space */}
        <div className="flex-1 overflow-hidden">
          <ChatContainer />
        </div>

        {/* Persistent Metrics Panel - always visible on the right */}
        <MetricsPanel />

        {/* Settings Panel Modal */}
        <SettingsPanel
          isOpen={showSettings}
          onClose={() => setShowSettings(false)}
        />
      </div>
    </AppLayout>
  );
}

export default App;
