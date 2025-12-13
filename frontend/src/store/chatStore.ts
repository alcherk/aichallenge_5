// Chat state management with Zustand

import { create } from 'zustand';
import type { Message } from '@/types';
import { conversationStorage } from '@/services/storage';

interface ChatState {
  messages: Message[];
  isStreaming: boolean;
  messageCount: number;

  // Actions
  setMessages: (messages: Message[]) => void;
  addMessage: (message: Message) => void;
  clearMessages: () => void;
  setIsStreaming: (isStreaming: boolean) => void;
  loadFromStorage: () => void;
  saveToStorage: () => void;
}

export const useChatStore = create<ChatState>((set, get) => ({
  messages: [],
  isStreaming: false,
  messageCount: 0,

  setMessages: (messages) => {
    set({ messages });
    conversationStorage.set(messages);

    // Update message count (exclude system messages)
    const count = messages.filter(m => m.role !== 'system').length;
    set({ messageCount: count });
    conversationStorage.setMessageCount(count);
  },

  addMessage: (message) => {
    const { messages } = get();
    const newMessages = [...messages, message];
    get().setMessages(newMessages);
  },

  clearMessages: () => {
    set({ messages: [], messageCount: 0 });
    conversationStorage.clear();
  },

  setIsStreaming: (isStreaming) => set({ isStreaming }),

  loadFromStorage: () => {
    const messages = conversationStorage.get();
    const messageCount = conversationStorage.getMessageCount();
    set({ messages, messageCount });
  },

  saveToStorage: () => {
    const { messages, messageCount } = get();
    conversationStorage.set(messages);
    conversationStorage.setMessageCount(messageCount);
  },
}));
