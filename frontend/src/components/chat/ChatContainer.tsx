import React, { useState, useCallback } from 'react';
import { useChatStore } from '@/store/chatStore';
import { useSettingsStore } from '@/store/settingsStore';
import { useMetricsStore } from '@/store/metricsStore';
import { streamChat } from '@/services/streaming';
import type { Message, StructuredResponse } from '@/types';
import { MessageList } from './MessageList';
import { ChatInput } from './ChatInput';

export const ChatContainer: React.FC = () => {
  const { messages, addMessage, setIsStreaming, isStreaming } = useChatStore();
  const { systemPrompt, temperature, model } = useSettingsStore();
  const { updateMetrics } = useMetricsStore();

  const [streamingContent, setStreamingContent] = useState('');
  const [messageResponses] = useState(new Map<number, StructuredResponse>());

  const handleSendMessage = useCallback(
    async (content: string) => {
      // Add user message
      const userMessage: Message = { role: 'user', content };
      addMessage(userMessage);

      // Prepare request with full conversation context
      const conversationMessages: Message[] = [
        { role: 'system', content: systemPrompt },
        ...messages.filter((m) => m.role !== 'system'),
        userMessage,
      ];

      setIsStreaming(true);
      setStreamingContent('');

      try {
        let fullContent = '';

        await streamChat(
          {
            messages: conversationMessages,
            temperature,
            model,
          },
          {
            onChunk: (delta) => {
              fullContent += delta;
              setStreamingContent(fullContent);
            },
            onDone: (data) => {
              if (data.success && fullContent) {
                // Add assistant message to conversation
                const assistantMessage: Message = {
                  role: 'assistant',
                  content: fullContent,
                };
                addMessage(assistantMessage);

                // Update metrics
                updateMetrics(data);

                // Store response for "Show Full Response" button
                const messageIndex = messages.length + 1; // +1 for the new assistant message
                messageResponses.set(messageIndex, data);
              }
            },
            onError: (error) => {
              console.error('Streaming error:', error);
              // You could add an error message to the chat here
              const errorMessage: Message = {
                role: 'assistant',
                content: `Error: ${error.message || 'An error occurred during streaming'}`,
              };
              addMessage(errorMessage);
            },
          }
        );
      } catch (error) {
        console.error('Failed to send message:', error);
        const errorMessage: Message = {
          role: 'assistant',
          content: `Error: ${error instanceof Error ? error.message : 'Network or server error'}`,
        };
        addMessage(errorMessage);
      } finally {
        setIsStreaming(false);
        setStreamingContent('');
      }
    },
    [
      messages,
      systemPrompt,
      temperature,
      model,
      addMessage,
      setIsStreaming,
      updateMetrics,
      messageResponses,
    ]
  );

  return (
    <div className="flex flex-col h-full bg-slate-950">
      <MessageList
        messages={messages}
        streamingMessage={streamingContent}
        messageResponses={messageResponses}
      />
      <ChatInput
        onSend={handleSendMessage}
        disabled={isStreaming}
        placeholder={isStreaming ? 'Waiting for response...' : 'Type your message...'}
      />
    </div>
  );
};
