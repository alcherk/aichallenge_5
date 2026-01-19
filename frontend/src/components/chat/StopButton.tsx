import React from 'react';

interface StopButtonProps {
  onStop: () => void;
}

export const StopButton: React.FC<StopButtonProps> = ({ onStop }) => {
  return (
    <button
      className="px-4 py-2 bg-gradient-to-r from-red-600 to-red-700 text-white rounded-lg hover:from-red-700 hover:to-red-800 focus:outline-none focus:ring-2 focus:ring-red-500 transition-all duration-200 font-semibold shadow-lg flex items-center gap-2"
      onClick={onStop}
      aria-label="Stop generation"
      type="button"
    >
      <span className="text-sm">&#x25A0;</span>
      Stop
    </button>
  );
};
