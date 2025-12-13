import React, { useEffect, useRef } from 'react';
import type { Message } from '@/types';
import { ChatMessage } from './ChatMessage';

interface MessageListProps {
  messages: Message[];
  streamingMessage?: string;
  messageResponses?: Map<number, any>;
}

export const MessageList: React.FC<MessageListProps> = ({
  messages,
  streamingMessage,
  messageResponses = new Map(),
}) => {
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, streamingMessage]);

  // Filter out system messages for display
  const displayMessages = messages.filter((m) => m.role !== 'system');

  return (
    <div className="flex-1 overflow-y-auto p-4 space-y-4">
      {displayMessages.length === 0 && !streamingMessage && (
        <div className="flex items-center justify-center h-full text-slate-500">
          <div className="text-center">
            <div className="text-6xl mb-4">💬</div>
            <div className="text-xl text-slate-300 font-semibold">Start a conversation</div>
            <div className="text-sm mt-2 text-slate-400">Messages are saved in your browser</div>
          </div>
        </div>
      )}

      {displayMessages.map((message, index) => (
        <ChatMessage
          key={index}
          message={message}
          fullResponse={messageResponses.get(index)}
        />
      ))}

      {/* Streaming message */}
      {streamingMessage && (
        <div className="flex justify-start mb-4">
          <div className="max-w-[80%] rounded-lg px-4 py-3 bg-slate-800 border border-slate-700 shadow-lg">
            <div className="flex items-center mb-2 text-sm">
              <span className="font-semibold text-slate-200">Assistant</span>
              <span className="ml-2 text-xs text-slate-400">typing...</span>
            </div>
            <div className="prose prose-sm prose-invert max-w-none whitespace-pre-wrap text-slate-200">
              {streamingMessage}
              <span className="inline-block w-2 h-4 bg-blue-500 ml-1 animate-pulse" />
            </div>
          </div>
        </div>
      )}

      <div ref={messagesEndRef} />
    </div>
  );
};
