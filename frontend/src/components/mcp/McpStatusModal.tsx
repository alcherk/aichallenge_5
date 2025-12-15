import React, { useMemo } from 'react';
import type { McpStatusResponse } from '@/types';

interface McpStatusModalProps {
  isOpen: boolean;
  status: McpStatusResponse | null;
  isLoading: boolean;
  onRefresh: () => void;
  onClose: () => void;
}

export const McpStatusModal: React.FC<McpStatusModalProps> = ({
  isOpen,
  status,
  isLoading,
  onRefresh,
  onClose,
}) => {
  const toolsByServer = useMemo(() => {
    const map = new Map<string, McpStatusResponse['tools']>();
    for (const t of status?.tools ?? []) {
      const key = t.server ?? 'unknown';
      const arr = map.get(key) ?? [];
      arr.push(t);
      map.set(key, arr);
    }
    return Array.from(map.entries()).sort((a, b) => a[0].localeCompare(b[0]));
  }, [status]);

  if (!isOpen) return null;

  const enabled = Boolean(status?.enabled);

  return (
    <div className="fixed inset-0 bg-black bg-opacity-75 backdrop-blur-sm flex items-center justify-center z-50 p-4">
      <div className="bg-slate-900 rounded-lg shadow-2xl border border-slate-700 max-w-3xl w-full max-h-[90vh] overflow-y-auto">
        <div className="sticky top-0 bg-slate-800 border-b border-slate-700 px-6 py-4 flex items-center justify-between rounded-t-lg">
          <div>
            <h2 className="text-xl font-bold text-slate-100">MCP Status</h2>
            <p className="text-xs text-slate-400">
              Servers, instruments and commands exposed to the assistant
            </p>
          </div>
          <button
            onClick={onClose}
            className="text-slate-400 hover:text-slate-200 text-2xl leading-none transition-colors"
            title="Close"
          >
            ×
          </button>
        </div>

        <div className="p-6 space-y-6">
          {status?.error && (
            <div className="border border-red-900 bg-red-950/40 text-red-200 rounded-lg p-3 text-sm">
              <div className="font-semibold">Error</div>
              <div className="font-mono text-xs mt-1">
                {status.error.type}: {status.error.detail}
              </div>
            </div>
          )}

          <div className="flex items-center justify-between">
            <div className="text-sm text-slate-300">
              <span className="font-semibold">Enabled:</span>{' '}
              {enabled ? 'Yes' : 'No'}
              {enabled && (
                <>
                  {' '}
                  · <span className="font-semibold">Tools:</span> {status?.tools?.length ?? 0}
                </>
              )}
            </div>
            <button
              onClick={onRefresh}
              disabled={isLoading}
              className="px-3 py-2 bg-slate-800 border border-slate-600 text-slate-200 rounded-lg hover:bg-slate-700 hover:border-slate-500 focus:outline-none focus:ring-2 focus:ring-blue-500 transition-all duration-200 disabled:opacity-50"
            >
              {isLoading ? 'Refreshing…' : 'Refresh'}
            </button>
          </div>

          {!enabled ? (
            <div className="text-sm text-slate-400">
              MCP is currently disabled. Enable MCP in Settings to see servers and tools exposed to the assistant.
            </div>
          ) : (
            <>
              <div>
                <h3 className="text-sm font-semibold text-slate-200 mb-2">Servers</h3>
                <div className="space-y-2">
                  {(status?.servers ?? []).map((s) => (
                    <div
                      key={s.name}
                      className="flex items-center justify-between px-3 py-2 rounded-lg border border-slate-700 bg-slate-950/40"
                    >
                      <div className="text-sm text-slate-200">
                        <span className="font-mono">{s.name}</span>
                        <span className="text-slate-400"> · {s.transport} · {s.kind}</span>
                      </div>
                      <div className={`text-xs font-semibold ${s.connected ? 'text-green-300' : 'text-slate-400'}`}>
                        {s.connected ? 'CONNECTED' : 'DISCONNECTED'}
                      </div>
                    </div>
                  ))}

                  {!status?.servers?.length && (
                    <div className="text-sm text-slate-400">No MCP servers configured.</div>
                  )}
                </div>
              </div>

              <div>
                <h3 className="text-sm font-semibold text-slate-200 mb-2">Tools (Commands)</h3>
                {!status?.tools?.length ? (
                  <div className="text-sm text-slate-400">
                    No tools discovered. Provide a valid MCP config path.
                  </div>
                ) : (
                  <div className="space-y-4">
                    {toolsByServer.map(([server, tools]) => (
                      <div key={server} className="border border-slate-700 rounded-lg overflow-hidden">
                        <div className="bg-slate-800 px-4 py-2 text-sm font-semibold text-slate-200">
                          {server}
                        </div>
                        <div className="divide-y divide-slate-800">
                          {tools.map((t) => (
                            <div key={t.openai_name} className="px-4 py-3">
                              <div className="flex items-center justify-between gap-3">
                                <div className="text-sm text-slate-100 font-mono">
                                  {t.openai_name}
                                </div>
                                <div className="text-xs text-slate-400">
                                  {t.kind ?? 'tool'}
                                </div>
                              </div>
                              {t.description && (
                                <div className="text-xs text-slate-300 mt-1">
                                  {t.description}
                                </div>
                              )}
                              <div className="text-xs text-slate-500 mt-1">
                                MCP name: <span className="font-mono">{t.mcp_name ?? 'unknown'}</span>
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </>
          )}
        </div>

        <div className="sticky bottom-0 bg-slate-800 border-t border-slate-700 px-6 py-4 flex justify-end gap-3 rounded-b-lg">
          <button
            onClick={onClose}
            className="px-4 py-2 bg-slate-800 border border-slate-600 text-slate-300 rounded-lg hover:bg-slate-700 focus:outline-none focus:ring-2 focus:ring-slate-500 transition-all duration-200"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
};


