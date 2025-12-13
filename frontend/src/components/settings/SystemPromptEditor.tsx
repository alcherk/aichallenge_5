import React from 'react';

interface SystemPromptEditorProps {
  value: string;
  onChange: (value: string) => void;
}

export const SystemPromptEditor: React.FC<SystemPromptEditorProps> = ({ value, onChange }) => {
  return (
    <textarea
      value={value}
      onChange={(e) => onChange(e.target.value)}
      rows={8}
      className="w-full px-4 py-2 border border-slate-600 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent resize-vertical font-mono text-sm bg-slate-800 text-slate-100 placeholder-slate-400"
      placeholder="Enter system prompt..."
    />
  );
};
