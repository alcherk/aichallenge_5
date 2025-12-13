import React from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import rehypeHighlight from 'rehype-highlight';
import type { Message, StructuredResponse } from '@/types';
import { extractJSON, syntaxHighlightJSON } from '@/utils/json';

interface ChatMessageProps {
  message: Message;
  fullResponse?: StructuredResponse;
}

export const ChatMessage: React.FC<ChatMessageProps> = ({ message, fullResponse }) => {
  const [showFullResponse, setShowFullResponse] = React.useState(false);
  const { role, content } = message;

  const isUser = role === 'user';
  const isAssistant = role === 'assistant';

  // Extract JSON if present in assistant messages
  const jsonContent = isAssistant ? extractJSON(content) : null;

  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'} mb-4`}>
      <div
        className={`max-w-[80%] rounded-lg px-4 py-3 shadow-lg ${
          isUser
            ? 'bg-gradient-to-r from-blue-600 to-blue-700 text-white'
            : 'bg-slate-800 border border-slate-700 text-slate-100'
        }`}
      >
        {/* Message Header */}
        <div className="flex items-center justify-between mb-2 text-sm">
          <span className="font-semibold">{isUser ? '👤 You' : '🤖 Assistant'}</span>

          {/* Stats for assistant messages */}
          {isAssistant && fullResponse?.metadata && (
            <div className="text-xs text-slate-400 ml-4 flex gap-2">
              {fullResponse.metadata.model && (
                <span>Model: {fullResponse.metadata.model}</span>
              )}
              {fullResponse.metadata.processing_time_ms && (
                <span>Time: {fullResponse.metadata.processing_time_ms}ms</span>
              )}
              {fullResponse.metadata.token_usage && (
                <span>
                  Tokens: {fullResponse.metadata.token_usage.total_tokens}
                </span>
              )}
            </div>
          )}
        </div>

        {/* Message Content */}
        <div className={`prose prose-sm max-w-none ${isAssistant ? 'prose-invert' : ''}`}>
          {jsonContent ? (
            // Display JSON content
            <div className="bg-slate-900 rounded p-3 border border-slate-600">
              <div className="text-xs font-semibold text-slate-300 mb-2">
                📋 JSON Response
              </div>
              <pre className="text-xs overflow-x-auto">
                <code
                  dangerouslySetInnerHTML={{
                    __html: syntaxHighlightJSON(jsonContent),
                  }}
                />
              </pre>
            </div>
          ) : isAssistant ? (
            // Display markdown for assistant messages with syntax highlighting
            <ReactMarkdown
              remarkPlugins={[remarkGfm]}
              rehypePlugins={[rehypeHighlight]}
            >
              {content}
            </ReactMarkdown>
          ) : (
            // Plain text for user messages
            <p className="whitespace-pre-wrap">{content}</p>
          )}
        </div>

        {/* Show full response button for assistant messages */}
        {isAssistant && fullResponse && (
          <div className="mt-2">
            <button
              onClick={() => setShowFullResponse(!showFullResponse)}
              className="text-xs text-blue-400 hover:text-blue-300 underline"
            >
              {showFullResponse ? 'Hide' : 'Show'} Full Response
            </button>

            {showFullResponse && (
              <div className="mt-2 bg-slate-900 rounded p-3 border border-slate-600">
                <pre className="text-xs overflow-x-auto">
                  <code
                    dangerouslySetInnerHTML={{
                      __html: syntaxHighlightJSON(
                        JSON.stringify(fullResponse, null, 2)
                      ),
                    }}
                  />
                </pre>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};
