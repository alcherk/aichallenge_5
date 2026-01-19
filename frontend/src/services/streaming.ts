// SSE Streaming service

import type { ChatRequest, SSEEvent } from '@/types';

import type { StructuredResponse } from '@/types';
import { useMetricsStore } from '@/store/metricsStore';

// Module-level AbortController for canceling ongoing requests
let abortController: AbortController | null = null;

/**
 * Cancel the current generation/streaming request
 */
export function cancelGeneration(): void {
  if (abortController) {
    abortController.abort();
    abortController = null;
  }
}

/**
 * Check if a generation is currently in progress
 */
export function isGenerating(): boolean {
  return abortController !== null;
}

export interface StreamCallbacks {
  onChunk?: (delta: string) => void;
  onDone?: (data: StructuredResponse) => void;
  onError?: (error: StructuredResponse) => void;
}

/**
 * Parse SSE event stream manually
 */
function parseSSEEvents(textChunk: string, state: { buffer: string }): SSEEvent[] {
  state.buffer += textChunk.replace(/\r/g, '');
  const events: SSEEvent[] = [];

  let splitIndex: number;
  while ((splitIndex = state.buffer.indexOf('\n\n')) !== -1) {
    const rawEvent = state.buffer.slice(0, splitIndex);
    state.buffer = state.buffer.slice(splitIndex + 2);

    const lines = rawEvent.split('\n');
    let eventName = 'message';
    const dataLines: string[] = [];

    for (const line of lines) {
      if (line.startsWith('event:')) {
        eventName = line.slice('event:'.length).trim();
      } else if (line.startsWith('data:')) {
        dataLines.push(line.slice('data:'.length).trim());
      }
    }

    const dataRaw = dataLines.join('\n');
    if (!dataRaw) continue;

    try {
      const data = JSON.parse(dataRaw);
      events.push({ event: eventName, data } as SSEEvent);
    } catch {
      // Skip malformed events
      console.warn('Failed to parse SSE data:', dataRaw);
    }
  }

  return events;
}

/**
 * Stream chat messages from the API
 */
export async function streamChat(
  request: ChatRequest,
  callbacks: StreamCallbacks
): Promise<void> {
  // Cancel any existing request before starting a new one
  cancelGeneration();

  // Create a new AbortController for this request
  abortController = new AbortController();
  const { signal } = abortController;

  // Defensive: strip MCP-related fields from the outbound payload.
  // (The backend supports MCP overrides, but the UI should not send them for chat requests.)
  const sanitizedRequest: Record<string, unknown> = { ...(request as unknown as Record<string, unknown>) };
  delete sanitizedRequest.mcp_enabled;
  delete sanitizedRequest.mcp_config_path;
  delete sanitizedRequest.workspace_root;

  const response = await fetch('/api/chat/stream', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Accept: 'text/event-stream',
    },
    body: JSON.stringify(sanitizedRequest),
    signal,
  });

  if (!response.ok || !response.body) {
    throw new Error(`Stream request failed with status ${response.status}`);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder('utf-8');
  const sseState = { buffer: '' };

  // Metrics tracking state
  const startTime = Date.now();
  let firstTokenTime: number | null = null;
  let tokensGenerated = 0;

  // Get metrics store methods (Zustand pattern for use outside React)
  const metricsStore = useMetricsStore.getState();

  try {
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;

      const text = decoder.decode(value, { stream: true });
      const events = parseSSEEvents(text, sseState);

      for (const evt of events) {
        if (evt.event === 'chunk' && evt.data && typeof evt.data.delta === 'string') {
          // Track first token latency
          if (firstTokenTime === null) {
            firstTokenTime = Date.now();
            const firstTokenLatency = firstTokenTime - startTime;
            metricsStore.updateFirstTokenLatency(firstTokenLatency);
          }

          // Increment token count (approximate: 1 chunk = 1 token for simplicity)
          tokensGenerated++;
          metricsStore.updateTokensGenerated(tokensGenerated);

          // Calculate and update tokens per second
          const elapsedSeconds = (Date.now() - startTime) / 1000;
          if (elapsedSeconds > 0) {
            const tokensPerSecond = tokensGenerated / elapsedSeconds;
            metricsStore.updateTokensPerSecond(tokensPerSecond);
          }

          callbacks.onChunk?.(evt.data.delta);
        } else if (evt.event === 'done') {
          // Update total latency when streaming completes
          const totalLatency = Date.now() - startTime;
          metricsStore.updateTotalLatency(totalLatency);

          callbacks.onDone?.(evt.data);
        } else if (evt.event === 'error') {
          callbacks.onError?.(evt.data);
        }
      }
    }

    // Process any remaining buffered data
    const finalEvents = parseSSEEvents('\n\n', sseState);
    for (const evt of finalEvents) {
      if (evt.event === 'chunk' && evt.data && typeof evt.data.delta === 'string') {
        // Track first token latency (in case first chunk is in final buffer)
        if (firstTokenTime === null) {
          firstTokenTime = Date.now();
          const firstTokenLatency = firstTokenTime - startTime;
          metricsStore.updateFirstTokenLatency(firstTokenLatency);
        }

        tokensGenerated++;
        metricsStore.updateTokensGenerated(tokensGenerated);

        const elapsedSeconds = (Date.now() - startTime) / 1000;
        if (elapsedSeconds > 0) {
          const tokensPerSecond = tokensGenerated / elapsedSeconds;
          metricsStore.updateTokensPerSecond(tokensPerSecond);
        }

        callbacks.onChunk?.(evt.data.delta);
      } else if (evt.event === 'done') {
        const totalLatency = Date.now() - startTime;
        metricsStore.updateTotalLatency(totalLatency);

        callbacks.onDone?.(evt.data);
      } else if (evt.event === 'error') {
        callbacks.onError?.(evt.data);
      }
    }
  } catch (error) {
    // Don't re-throw if the request was intentionally aborted
    if (error instanceof DOMException && error.name === 'AbortError') {
      // Request was cancelled - this is expected behavior
      return;
    }
    throw error;
  } finally {
    // Clean up the abort controller when streaming completes or fails
    abortController = null;
  }
}
