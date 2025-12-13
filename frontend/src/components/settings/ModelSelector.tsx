import React from 'react';
import type { ModelName } from '@/types';

interface ModelSelectorProps {
  value: ModelName;
  onChange: (model: ModelName) => void;
}

const models: { value: ModelName; label: string; description: string }[] = [
  { value: 'gpt-4o', label: 'GPT-4o', description: 'Most powerful, multimodal' },
  { value: 'gpt-4-turbo', label: 'GPT-4 Turbo', description: 'Fast and capable' },
  { value: 'gpt-4', label: 'GPT-4', description: 'Classic GPT-4' },
  { value: 'gpt-4o-mini', label: 'GPT-4o Mini', description: 'Recommended - Fast and affordable' },
  { value: 'gpt-3.5-turbo', label: 'GPT-3.5 Turbo', description: 'Lightest and fastest' },
];

export const ModelSelector: React.FC<ModelSelectorProps> = ({ value, onChange }) => {
  return (
    <select
      value={value}
      onChange={(e) => onChange(e.target.value as ModelName)}
      className="w-full px-4 py-2 border border-slate-600 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent bg-slate-800 text-slate-100"
    >
      {models.map((model) => (
        <option key={model.value} value={model.value} className="bg-slate-800 text-slate-100">
          {model.label} - {model.description}
        </option>
      ))}
    </select>
  );
};
