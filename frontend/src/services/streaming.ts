// SSE Streaming service

import type { ChatRequest, SSEEvent } from '@/types';

import type { StructuredResponse } from '@/types';

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
  const response = await fetch('/api/chat/stream', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Accept: 'text/event-stream',
    },
    body: JSON.stringify(request),
  });

  if (!response.ok || !response.body) {
    throw new Error(`Stream request failed with status ${response.status}`);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder('utf-8');
  const sseState = { buffer: '' };

  try {
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;

      const text = decoder.decode(value, { stream: true });
      const events = parseSSEEvents(text, sseState);

      for (const evt of events) {
        if (evt.event === 'chunk' && evt.data && typeof evt.data.delta === 'string') {
          callbacks.onChunk?.(evt.data.delta);
        } else if (evt.event === 'done') {
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
        callbacks.onChunk?.(evt.data.delta);
      } else if (evt.event === 'done') {
        callbacks.onDone?.(evt.data);
      } else if (evt.event === 'error') {
        callbacks.onError?.(evt.data);
      }
    }
  } catch (error) {
    throw error;
  }
}
