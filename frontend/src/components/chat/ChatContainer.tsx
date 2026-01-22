import React, { useCallback, useRef, useState, useEffect } from 'react';
import { useChatStore } from '@/store/chatStore';
import { useSettingsStore } from '@/store/settingsStore';
import { useMetricsStore } from '@/store/metricsStore';
import { useOptimizationStore } from '@/store/optimizationStore';
import { chatAPI } from '@/services/api';
import { cancelGeneration, streamChat } from '@/services/streaming';
import type { Message, StructuredResponse, OllamaHealthResponse } from '@/types';
import { MessageList } from './MessageList';
import { ChatInput } from './ChatInput';
import { StopButton } from './StopButton';
import { ProviderBadge } from './ProviderBadge';
import { InferenceMetricsPanel } from './InferenceMetricsPanel';
import { OfflineBanner } from './OfflineBanner';

export const ChatContainer: React.FC = () => {
  const { messages, addMessage, setIsStreaming, isStreaming } = useChatStore();
  const { systemPrompt, temperature, model, mcpConfigPath, workspaceRoot, assistantMode, localModel } = useSettingsStore();
  const { updateMetrics, clearInferenceMetrics, initInferenceMetrics } = useMetricsStore();
  const { promptMode, ollamaOptions, setLastClassification } = useOptimizationStore();

  const [messageResponses] = React.useState(new Map<number, StructuredResponse>());
  const [streamingContent, setStreamingContent] = useState('');
  const streamTimerRef = useRef<number | null>(null);

  // Ollama health state
  const [ollamaHealth, setOllamaHealth] = useState<OllamaHealthResponse | null>(null);
  const [isCheckingHealth, setIsCheckingHealth] = useState(false);

  // Check Ollama health on mount and when provider changes
  useEffect(() => {
    const checkHealth = async () => {
      if (localModel.provider === 'local') {
        setIsCheckingHealth(true);
        const health = await chatAPI.checkOllamaHealth();
        setOllamaHealth(health);
        setIsCheckingHealth(false);
      }
    };
    checkHealth();
  }, [localModel.provider]);

  // Retry health check
  const handleRetryHealth = useCallback(async () => {
    setIsCheckingHealth(true);
    const health = await chatAPI.checkOllamaHealth();
    setOllamaHealth(health);
    setIsCheckingHealth(false);
  }, []);

  const handleStopGeneration = useCallback(() => {
    // Cancel any real streaming request
    cancelGeneration();

    // Stop the simulated streaming timer
    if (streamTimerRef.current) {
      window.clearInterval(streamTimerRef.current);
      streamTimerRef.current = null;
    }

    // If we have partial streaming content, save it as a partial response
    if (streamingContent) {
      addMessage({ role: 'assistant', content: streamingContent + '\n\n[Generation stopped]' });
    }

    setStreamingContent('');
    setIsStreaming(false);
  }, [streamingContent, addMessage, setIsStreaming]);

  const handleSendMessage = useCallback(
    async (content: string) => {
      // Clear inference metrics before starting a new request
      clearInferenceMetrics();

      // Initialize inference metrics for local model
      if (localModel.provider === 'local') {
        initInferenceMetrics(localModel.provider, localModel.model);
      }

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

      // Determine effective settings based on provider
      const isLocal = localModel.provider === 'local';
      const effectiveModel = isLocal ? localModel.model : model;
      const effectiveTemperature = isLocal ? localModel.temperature : temperature;

      // MCP config paths
      const fallbackConfigPath = '/Users/lex/Projects/ai/AI_Challenge_5/week1_day1/mcp_servers.json';
      const effectiveConfigPath = (mcpConfigPath && mcpConfigPath.trim()) || fallbackConfigPath;

      // Default workspace root for /review and /help commands
      const defaultWorkspaceRoot = '/Users/lex/Projects/ai/AI_Challenge_5/week1_day1';
      const isReviewOrHelpCommand = content.trim().toLowerCase().startsWith('/review') ||
                                    content.trim().toLowerCase().startsWith('/help');

      // Use default workspace root for /review and /help commands, otherwise use settings
      const effectiveWorkspaceRoot = isReviewOrHelpCommand
        ? defaultWorkspaceRoot
        : (workspaceRoot && workspaceRoot.trim()) || null;

      try {
        if (isLocal) {
          // Use real streaming for local models
          let accumulatedContent = '';

          await streamChat(
            {
              messages: conversationMessages,
              temperature: effectiveTemperature,
              model: effectiveModel,
              provider: 'local',
              rag_enabled: localModel.ragEnabled,
              top_p: localModel.topP,
              max_tokens: localModel.maxTokens,
              // Optimization parameters
              prompt_mode: promptMode,
              ollama_options: ollamaOptions,
            },
            {
              onChunk: (delta) => {
                accumulatedContent += delta;
                setStreamingContent(accumulatedContent);
              },
              onDone: (data) => {
                if (accumulatedContent) {
                  addMessage({ role: 'assistant', content: accumulatedContent });
                }
                updateMetrics(data);

                // Update classification result from response metadata
                if (data?.metadata?.prompt_mode && data?.metadata?.classification_confidence !== undefined) {
                  setLastClassification({
                    category: data.metadata.prompt_mode,
                    confidence: data.metadata.classification_confidence,
                  });
                }

                setStreamingContent('');
                setIsStreaming(false);
              },
              onError: (data) => {
                const errorMessage: Message = {
                  role: 'assistant',
                  content: `Error: ${data?.error?.detail || data?.message || 'Streaming failed'}`,
                };
                addMessage(errorMessage);
                setStreamingContent('');
                setIsStreaming(false);
              },
            }
          );
        } else {
          // Use non-streaming for cloud (supports MCP tool calls)
          const data = await chatAPI.sendMessage({
            messages: conversationMessages,
            temperature: effectiveTemperature,
            model: effectiveModel,
            provider: 'cloud',
            mcp_enabled: true,
            mcp_config_path: effectiveConfigPath || null,
            workspace_root: effectiveWorkspaceRoot,
            assistant_mode: assistantMode || null,
            rag_enabled: localModel.ragEnabled,
          });

          const assistantText = data?.data?.choices?.[0]?.message?.content || '';
          if (data.success) {
            if (assistantText) {
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
              // Success but no content - might be a valid empty response
              const errorMessage: Message = {
                role: 'assistant',
                content: `No response content received. ${data?.error?.detail || 'Please try again.'}`,
              };
              addMessage(errorMessage);
            }
          } else {
            const errorMessage: Message = {
              role: 'assistant',
              content: `Error: ${data?.error?.detail || data?.message || 'Request failed'}`,
            };
            addMessage(errorMessage);
          }
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
      localModel,
      mcpConfigPath,
      workspaceRoot,
      assistantMode,
      addMessage,
      setIsStreaming,
      updateMetrics,
      clearInferenceMetrics,
      initInferenceMetrics,
      messageResponses,
      promptMode,
      ollamaOptions,
      setLastClassification,
    ]
  );

  // Show offline banner if Ollama is unavailable when local provider selected
  const showOfflineBanner = localModel.provider === 'local' && ollamaHealth && !ollamaHealth.available;

  return (
    <div className="flex flex-col h-full bg-slate-950">
      {/* Offline banner for local model unavailability */}
      {showOfflineBanner && (
        <OfflineBanner
          onRetry={handleRetryHealth}
          isRetrying={isCheckingHealth}
        />
      )}

      {/* Provider badge in header area */}
      <div className="flex items-center justify-between px-4 py-2 border-b border-slate-800">
        <ProviderBadge
          provider={localModel.provider}
          model={localModel.provider === 'local' ? localModel.model : model}
        />
      </div>

      <MessageList
        messages={messages}
        streamingMessage={streamingContent}
        messageResponses={messageResponses}
      />

      <div className="relative">
        <ChatInput
          onSend={handleSendMessage}
          disabled={isStreaming || !!showOfflineBanner}
          placeholder={
            showOfflineBanner
              ? 'Ollama unavailable. Click retry or switch to cloud.'
              : isStreaming
                ? 'Waiting for response...'
                : 'Type your message...'
          }
        />
        {isStreaming && (
          <div className="absolute right-4 top-4">
            <StopButton onStop={handleStopGeneration} />
          </div>
        )}
      </div>

      {/* Inference metrics panel (shows during local model streaming) */}
      <InferenceMetricsPanel />
    </div>
  );
};
