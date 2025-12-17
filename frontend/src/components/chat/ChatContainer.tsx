import React, { useCallback, useRef, useState } from 'react';
import { useChatStore } from '@/store/chatStore';
import { useSettingsStore } from '@/store/settingsStore';
import { useMetricsStore } from '@/store/metricsStore';
import { chatAPI } from '@/services/api';
import type { Message, StructuredResponse } from '@/types';
import { MessageList } from './MessageList';
import { ChatInput } from './ChatInput';

export const ChatContainer: React.FC = () => {
  const { messages, addMessage, setIsStreaming, isStreaming } = useChatStore();
  const { systemPrompt, temperature, model, mcpConfigPath, workspaceRoot } = useSettingsStore();
  const { updateMetrics } = useMetricsStore();

  const [messageResponses] = React.useState(new Map<number, StructuredResponse>());
  const [streamingContent, setStreamingContent] = useState('');
  const streamTimerRef = useRef<number | null>(null);

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
      if (streamTimerRef.current) {
        window.clearInterval(streamTimerRef.current);
        streamTimerRef.current = null;
      }

      try {
        // Always include MCP tools for chat requests.
        // Use non-streaming /api/chat because streaming mode does not support server-side tool calls.
        const fallbackConfigPath = '/Users/lex/Projects/ai/AI_Challenge_5/week1_day1/mcp_servers.json';
        const effectiveConfigPath = (mcpConfigPath && mcpConfigPath.trim()) || fallbackConfigPath;

        const data = await chatAPI.sendMessage({
          messages: conversationMessages,
          temperature,
          model,
          mcp_enabled: true,
          mcp_config_path: effectiveConfigPath || null,
          workspace_root: (workspaceRoot && workspaceRoot.trim()) || null,
        });

        const assistantText = data?.data?.choices?.[0]?.message?.content || '';
        if (data.success && assistantText) {
          updateMetrics(data);

          const messageIndex = messages.length + 1; // +1 for the new assistant message
          messageResponses.set(messageIndex, data);

          // Simulated streaming: progressively reveal the final text so it doesn't pop in one-shot.
          let i = 0;
          const chunkSize = 24; // chars per tick
          const intervalMs = 25;
          streamTimerRef.current = window.setInterval(() => {
            i = Math.min(assistantText.length, i + chunkSize);
            setStreamingContent(assistantText.slice(0, i));
            if (i >= assistantText.length) {
              if (streamTimerRef.current) {
                window.clearInterval(streamTimerRef.current);
                streamTimerRef.current = null;
              }
              addMessage({ role: 'assistant', content: assistantText });
              setStreamingContent('');
              setIsStreaming(false);
            }
          }, intervalMs);
          return;
        } else {
          const errorMessage: Message = {
            role: 'assistant',
            content: `Error: ${data?.error?.detail || 'Request failed'}`,
          };
          addMessage(errorMessage);
        }
      } catch (error) {
        console.error('Failed to send message:', error);
        const errorMessage: Message = {
          role: 'assistant',
          content: `Error: ${error instanceof Error ? error.message : 'Network or server error'}`,
        };
        addMessage(errorMessage);
      } finally {
        // If we started simulated streaming, we return early above and will stop streaming there.
        if (!streamTimerRef.current) {
          setIsStreaming(false);
          setStreamingContent('');
        }
      }
    },
    [
      messages,
      systemPrompt,
      temperature,
      model,
      mcpConfigPath,
      workspaceRoot,
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
