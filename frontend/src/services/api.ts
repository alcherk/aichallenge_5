// API service for backend communication

import type { ChatRequest, StructuredResponse } from '@/types';

export const chatAPI = {
  /**
   * Send a chat message (non-streaming)
   */
  async sendMessage(request: ChatRequest): Promise<StructuredResponse> {
    const response = await fetch('/api/chat', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(request),
    });

    if (!response.ok) {
      throw new Error(`API request failed with status ${response.status}`);
    }

    return response.json();
  },

  /**
   * Health check endpoint
   */
  async healthCheck(): Promise<{ status: string }> {
    const response = await fetch('/health');
    return response.json();
  },
};
