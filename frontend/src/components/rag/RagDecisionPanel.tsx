import React, { useState } from 'react';
import type { RAGMetadata } from '@/types';

interface RagDecisionPanelProps {
  ragMetadata: RAGMetadata;
}

export const RagDecisionPanel: React.FC<RagDecisionPanelProps> = ({ ragMetadata }) => {
  const [isExpanded, setIsExpanded] = useState(false);

  if (!ragMetadata || !ragMetadata.enabled) {
    return null;
  }

  const {
    initial_chunks = 0,
    filtered_chunks = 0,
    final_chunks = 0,
    threshold = 0,
    fallback_triggered = false,
    reranker_enabled = false,
    reranker_type,
    scores_range,
    initial_scores = [],
    filtered_scores = [],
    context_size = 0,
    compare_mode = false,
    error,
  } = ragMetadata;

  const chunksFiltered = initial_chunks - filtered_chunks;
  const filterPercentage = initial_chunks > 0 ? ((chunksFiltered / initial_chunks) * 100).toFixed(1) : '0';

  return (
    <div className="mt-3 border-t border-slate-600 pt-3">
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="flex items-center justify-between w-full text-left text-xs text-slate-400 hover:text-slate-300 transition-colors"
      >
        <div className="flex items-center gap-2">
          <span className="font-semibold">🔍 RAG Decision Making</span>
          {error && <span className="text-red-400">⚠️ Error</span>}
          {fallback_triggered && <span className="text-yellow-400">⚠️ Fallback</span>}
        </div>
        <span className="text-slate-500">
          {isExpanded ? '▼' : '▶'} {initial_chunks} → {final_chunks} chunks
        </span>
      </button>

      {isExpanded && (
        <div className="mt-2 space-y-2 text-xs">
          {error ? (
            <div className="bg-red-900/20 border border-red-700 rounded p-2 text-red-300">
              <strong>Error:</strong> {error}
            </div>
          ) : (
            <>
              {/* Pipeline Overview */}
              <div className="bg-slate-900/50 rounded p-2 border border-slate-700">
                <div className="font-semibold text-slate-300 mb-2">Pipeline Overview</div>
                <div className="space-y-1 text-slate-400">
                  <div className="flex justify-between">
                    <span>Initial Retrieval:</span>
                    <span className="text-slate-200 font-mono">{initial_chunks} chunks</span>
                  </div>
                  {chunksFiltered > 0 && (
                    <div className="flex justify-between">
                      <span>After Filtering:</span>
                      <span className="text-slate-200 font-mono">
                        {filtered_chunks} chunks ({filterPercentage}% filtered)
                      </span>
                    </div>
                  )}
                  <div className="flex justify-between">
                    <span>Final Context:</span>
                    <span className="text-slate-200 font-mono">{final_chunks} chunks</span>
                  </div>
                  {context_size > 0 && (
                    <div className="flex justify-between">
                      <span>Context Size:</span>
                      <span className="text-slate-200 font-mono">{context_size.toLocaleString()} chars</span>
                    </div>
                  )}
                </div>
              </div>

              {/* Filtering Details */}
              {threshold > 0 && (
                <div className="bg-slate-900/50 rounded p-2 border border-slate-700">
                  <div className="font-semibold text-slate-300 mb-2">Filtering</div>
                  <div className="space-y-1 text-slate-400">
                    <div className="flex justify-between">
                      <span>Threshold:</span>
                      <span className="text-slate-200 font-mono">{threshold.toFixed(3)}</span>
                    </div>
                    {scores_range && (
                      <div className="flex justify-between">
                        <span>Score Range:</span>
                        <span className="text-slate-200 font-mono">
                          {scores_range[0].toFixed(3)} - {scores_range[1].toFixed(3)}
                        </span>
                      </div>
                    )}
                    {fallback_triggered && (
                      <div className="text-yellow-400 mt-1">
                        ⚠️ Fallback triggered: kept top chunks due to low threshold
                      </div>
                    )}
                  </div>
                </div>
              )}

              {/* Reranking Details */}
              {reranker_enabled && (
                <div className="bg-slate-900/50 rounded p-2 border border-slate-700">
                  <div className="font-semibold text-slate-300 mb-2">Reranking</div>
                  <div className="text-slate-400">
                    <div className="flex justify-between">
                      <span>Type:</span>
                      <span className="text-slate-200 font-mono">{reranker_type || 'noop'}</span>
                    </div>
                  </div>
                </div>
              )}

              {/* Similarity Scores */}
              {initial_scores.length > 0 && (
                <div className="bg-slate-900/50 rounded p-2 border border-slate-700">
                  <div className="font-semibold text-slate-300 mb-2">Similarity Scores</div>
                  <div className="space-y-1 text-slate-400">
                    <div className="text-xs">
                      <div className="mb-1">Initial ({initial_scores.length}):</div>
                      <div className="flex flex-wrap gap-1">
                        {initial_scores.slice(0, 10).map((score, idx) => (
                          <span
                            key={idx}
                            className="px-1.5 py-0.5 bg-slate-800 rounded font-mono text-xs"
                            style={{
                              backgroundColor: `rgba(59, 130, 246, ${score})`,
                            }}
                            title={`Score: ${score.toFixed(3)}`}
                          >
                            {score.toFixed(2)}
                          </span>
                        ))}
                        {initial_scores.length > 10 && (
                          <span className="text-slate-500">+{initial_scores.length - 10} more</span>
                        )}
                      </div>
                    </div>
                    {filtered_scores.length > 0 && filtered_scores.length !== initial_scores.length && (
                      <div className="text-xs mt-2">
                        <div className="mb-1">After Filter ({filtered_scores.length}):</div>
                        <div className="flex flex-wrap gap-1">
                          {filtered_scores.slice(0, 10).map((score, idx) => (
                            <span
                              key={idx}
                              className="px-1.5 py-0.5 bg-slate-800 rounded font-mono text-xs"
                              style={{
                                backgroundColor: `rgba(34, 197, 94, ${score})`,
                              }}
                              title={`Score: ${score.toFixed(3)}`}
                            >
                              {score.toFixed(2)}
                            </span>
                          ))}
                          {filtered_scores.length > 10 && (
                            <span className="text-slate-500">+{filtered_scores.length - 10} more</span>
                          )}
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              )}

              {/* Comparison Mode */}
              {compare_mode && (
                <div className="bg-blue-900/20 border border-blue-700 rounded p-2">
                  <div className="font-semibold text-blue-300 mb-2">🔬 Comparison Mode</div>
                  <div className="text-xs text-blue-200">
                    Two answers generated: baseline (no filter) vs enhanced (with filter/rerank)
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      )}
    </div>
  );
};

