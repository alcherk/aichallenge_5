import { useEffect, useRef, useState } from 'react';
import { useChatStore } from './store/chatStore';
import { useSettingsStore } from './store/settingsStore';
import { useMetricsStore } from './store/metricsStore';
import { AppLayout } from './components/layout/AppLayout';
import { Header } from './components/layout/Header';
import { ChatContainer } from './components/chat/ChatContainer';
import { SettingsPanel } from './components/settings/SettingsPanel';
import { MetricsPanel } from './components/metrics/MetricsPanel';
import { chatAPI } from './services/api';

type ToastKind = 'info' | 'error';
type ToastState = {
  open: boolean;
  kind: ToastKind;
  title: string;
  message: string;
};

function App() {
  const { loadFromStorage: loadChat, clearMessages } = useChatStore();
  const {
    loadFromStorage: loadSettings,
    systemPrompt,
    temperature,
    model,
    mcpEnabled,
    mcpConfigPath,
    workspaceRoot,
  } = useSettingsStore();
  const { loadFromStorage: loadMetrics, updateMetrics } = useMetricsStore();

  const [showSettings, setShowSettings] = useState(false);
  const [toast, setToast] = useState<ToastState>({
    open: false,
    kind: 'info',
    title: '',
    message: '',
  });
  const toastTimerRef = useRef<number | null>(null);

  // Load persisted data on mount
  useEffect(() => {
    loadChat();
    loadSettings();
    loadMetrics();
  }, [loadChat, loadSettings, loadMetrics]);

  const handleNewChat = () => {
    clearMessages();

    // Auto weather summary on new chat.
    // This uses the non-streaming /api/chat endpoint because the streaming endpoint
    // intentionally disables MCP overrides and does not support the server-side tool loop.
    const weatherPrompt =
      'Check the weather for Nizhniy Novgorod (Russia). ' +
      'Return EXACTLY two lines:\n' +
      '1) Weather: 4-5 words (how it feels now)\n' +
      '2) Clothing: 3-5 words (what to wear)\n' +
      'No extra text.';

    const fallbackConfigPath = '/Users/lex/Projects/ai/AI_Challenge_5/week1_day1/mcp_servers.json';
    const effectiveConfigPath = (mcpConfigPath && mcpConfigPath.trim()) || fallbackConfigPath;

    if (toastTimerRef.current) {
      window.clearTimeout(toastTimerRef.current);
      toastTimerRef.current = null;
    }

    void (async () => {
      try {
        const userMessage = { role: 'user' as const, content: weatherPrompt };
        const resp = await chatAPI.sendMessage({
          messages: [{ role: 'system', content: systemPrompt }, userMessage],
          model,
          temperature,
          // Ensure MCP is enabled for this request and point at the weather server config.
          mcp_enabled: true,
          mcp_config_path: (mcpEnabled ? effectiveConfigPath : effectiveConfigPath) || null,
          workspace_root: (workspaceRoot && workspaceRoot.trim()) || null,
        });

        const assistantText =
          resp?.data?.choices?.[0]?.message?.content ||
          (resp?.success ? '' : resp?.error?.detail) ||
          '';

        if (resp?.success && assistantText) {
          updateMetrics(resp);
          setToast({
            open: true,
            kind: 'info',
            title: 'Weather',
            message: assistantText,
          });
        } else {
          setToast({
            open: true,
            kind: 'error',
            title: 'Weather error',
            message:
              assistantText ||
              resp?.error?.detail ||
              'Failed to generate weather summary. Check MCP config path.',
          });
        }
      } catch (e) {
        setToast({
          open: true,
          kind: 'error',
          title: 'Weather error',
          message: e instanceof Error ? e.message : 'Failed to fetch weather summary',
        });
      } finally {
        // Only start auto-hide once a toast is shown (i.e., after the request completes).
        toastTimerRef.current = window.setTimeout(() => {
          setToast((t) => ({ ...t, open: false }));
          toastTimerRef.current = null;
        }, 10000);
      }
    })();
  };

  return (
    <>
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

      {/* Toast / notification */}
      {toast.open && (
        <div className="fixed right-4 top-4 z-50 w-[min(520px,calc(100vw-2rem))]">
          <div
            className={`rounded-lg border shadow-2xl backdrop-blur-sm ${
              toast.kind === 'error'
                ? 'border-red-900 bg-red-950/70'
                : 'border-slate-700 bg-slate-900/80'
            }`}
            role="status"
            aria-live="polite"
          >
            <div className="flex items-start justify-between gap-3 px-4 py-3 border-b border-slate-800">
              <div>
                <div
                  className={`text-sm font-semibold ${
                    toast.kind === 'error' ? 'text-red-200' : 'text-slate-100'
                  }`}
                >
                  {toast.title}
                </div>
              </div>
              <button
                onClick={() => {
                  if (toastTimerRef.current) {
                    window.clearTimeout(toastTimerRef.current);
                    toastTimerRef.current = null;
                  }
                  setToast((t) => ({ ...t, open: false }));
                }}
                className="text-slate-400 hover:text-slate-200 text-xl leading-none transition-colors"
                title="Close"
              >
                ×
              </button>
            </div>
            <div
              className={`px-4 py-3 text-sm whitespace-pre-wrap ${
                toast.kind === 'error' ? 'text-red-100' : 'text-slate-200'
              }`}
            >
              {toast.message}
            </div>
          </div>
        </div>
      )}
    </>
  );
}

export default App;
