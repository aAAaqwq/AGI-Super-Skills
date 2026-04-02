'use client';

import React from 'react';
import { Loader } from 'lucide-react';

interface StageProgressProps {
  /** progressMessage from StageState */
  message: string;
  /** fallback text when message is empty */
  fallback?: string;
  /** 0-100 */
  progress: number;
  /** accent color class, default blue */
  color?: 'blue' | 'amber' | 'emerald' | 'violet' | 'rose' | 'cyan';
}

const BAR_COLORS: Record<string, { bg: string; bar: string; text: string; ring: string }> = {
  blue:    { bg: 'bg-blue-100',    bar: 'bg-gradient-to-r from-blue-400 to-blue-600',    text: 'text-blue-600',    ring: 'ring-blue-200' },
  amber:   { bg: 'bg-amber-100',   bar: 'bg-gradient-to-r from-amber-400 to-amber-600',   text: 'text-amber-600',   ring: 'ring-amber-200' },
  emerald: { bg: 'bg-emerald-100', bar: 'bg-gradient-to-r from-emerald-400 to-emerald-600', text: 'text-emerald-600', ring: 'ring-emerald-200' },
  violet:  { bg: 'bg-violet-100',  bar: 'bg-gradient-to-r from-violet-400 to-violet-600',  text: 'text-violet-600',  ring: 'ring-violet-200' },
  rose:    { bg: 'bg-rose-100',    bar: 'bg-gradient-to-r from-rose-400 to-rose-600',    text: 'text-rose-600',    ring: 'ring-rose-200' },
  cyan:    { bg: 'bg-cyan-100',    bar: 'bg-gradient-to-r from-cyan-400 to-cyan-600',    text: 'text-cyan-600',    ring: 'ring-cyan-200' },
};

export default function StageProgress({
  message,
  fallback = '处理中...',
  progress,
  color = 'blue',
}: StageProgressProps) {
  const p = Math.min(100, Math.max(0, Math.round(progress)));
  const c = BAR_COLORS[color] || BAR_COLORS.blue;

  // Extract step description: progressMessage format is "阶段名: 步骤描述"
  const stepDesc = message?.includes(': ') ? message.split(': ').slice(1).join(': ') : (message || fallback);

  return (
    <div className="mb-6">
      <div className="flex items-center justify-between mb-2">
        <div className={`flex items-center gap-2 text-sm font-medium ${c.text}`}>
          <Loader className="w-4 h-4 animate-spin" />
          <span className="truncate">{stepDesc}</span>
        </div>
        <span className={`text-xs font-mono tabular-nums ${c.text} opacity-70`}>{p}%</span>
      </div>
      <div className={`w-full ${c.bg} rounded-full h-2.5 overflow-hidden ring-1 ${c.ring}`}>
        <div
          className={`${c.bar} h-2.5 rounded-full transition-all duration-700 ease-out`}
          style={{ width: `${p}%` }}
        />
      </div>
    </div>
  );
}
