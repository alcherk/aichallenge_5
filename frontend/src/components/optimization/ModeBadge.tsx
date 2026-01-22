import React from 'react';
import { useOptimizationStore } from '@/store/optimizationStore';

interface ModeBadgeProps {
  onClick?: () => void;
  className?: string;
}

/**
 * ModeBadge - Shows the current prompt mode with emoji.
 * Clicking opens the optimization sidebar.
 */
export const ModeBadge: React.FC<ModeBadgeProps> = ({ onClick, className = '' }) => {
  const { promptMode, lastClassification, categoryInfo, toggleSidebar } = useOptimizationStore();

  // Determine which mode to display
  const displayMode = promptMode === 'auto' && lastClassification
    ? lastClassification.category
    : promptMode;

  const info = categoryInfo[displayMode] ?? categoryInfo['general'];
  const isAutoDetected = promptMode === 'auto' && lastClassification !== null;

  // Safety check - if no info available, don't render
  if (!info) {
    return null;
  }

  const handleClick = () => {
    if (onClick) {
      onClick();
    } else {
      toggleSidebar();
    }
  };

  return (
    <button
      onClick={handleClick}
      className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium transition-all duration-200 hover:scale-105 ${
        isAutoDetected
          ? 'bg-teal-500/20 text-teal-400 border border-teal-500/30'
          : 'bg-slate-700/50 text-slate-300 border border-slate-600/50'
      } ${className}`}
      title={`${info.description}${isAutoDetected ? ' (auto-detected)' : ''}`}
    >
      <span>{info.emoji}</span>
      <span>{info.name}</span>
      {isAutoDetected && (
        <span className="text-[10px] text-teal-500 ml-0.5">auto</span>
      )}
    </button>
  );
};

export default ModeBadge;
