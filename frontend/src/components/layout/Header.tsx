import React from 'react';

interface HeaderProps {
  onNewChat: () => void;
  onSettingsClick: () => void;
}

export const Header: React.FC<HeaderProps> = ({ onNewChat, onSettingsClick }) => {
  const handleNewChat = () => {
    if (confirm('Start a new chat? This will clear the current conversation.')) {
      onNewChat();
    }
  };

  return (
    <div className="flex items-center justify-between">
      <div>
        <h1 className="text-2xl font-bold bg-gradient-to-r from-blue-400 to-purple-500 bg-clip-text text-transparent">
          ChatGPT Proxy
        </h1>
        <p className="text-sm text-slate-400">FastAPI + React + TypeScript</p>
      </div>

      <div className="flex gap-2">
        <button
          onClick={handleNewChat}
          className="px-4 py-2 bg-slate-800 border border-slate-600 text-slate-200 rounded-lg hover:bg-slate-700 hover:border-slate-500 focus:outline-none focus:ring-2 focus:ring-blue-500 transition-all duration-200"
        >
          🔄 New Chat
        </button>
        <button
          onClick={onSettingsClick}
          className="px-4 py-2 bg-slate-800 border border-slate-600 text-slate-200 rounded-lg hover:bg-slate-700 hover:border-slate-500 focus:outline-none focus:ring-2 focus:ring-blue-500 transition-all duration-200"
          title="Settings"
        >
          ⚙️ Settings
        </button>
      </div>
    </div>
  );
};
