import React from 'react';

interface TemperatureSliderProps {
  value: number;
  onChange: (value: number) => void;
}

export const TemperatureSlider: React.FC<TemperatureSliderProps> = ({ value, onChange }) => {
  return (
    <div>
      <input
        type="range"
        min={0}
        max={2}
        step={0.1}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        className="w-full h-2 bg-slate-700 rounded-lg appearance-none cursor-pointer accent-blue-500"
      />
      <div className="flex justify-between text-xs text-slate-400 mt-1">
        <span>0.0 (Deterministic)</span>
        <span>1.0 (Balanced)</span>
        <span>2.0 (Creative)</span>
      </div>
    </div>
  );
};
