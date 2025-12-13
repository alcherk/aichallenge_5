import React from 'react';

interface MetricCardProps {
  label: string;
  value: string | number;
  className?: string;
}

export const MetricCard: React.FC<MetricCardProps> = ({ label, value, className = '' }) => {
  return (
    <div className={`flex justify-between items-center py-0.5 ${className}`}>
      <span className="text-xs text-slate-400">{label}:</span>
      <span className="text-xs font-semibold text-slate-100">{value}</span>
    </div>
  );
};
