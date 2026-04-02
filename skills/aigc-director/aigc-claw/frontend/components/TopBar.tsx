'use client';

import React, { useState, useRef, useEffect } from 'react';
import { CheckCircle, Circle, Loader, Edit3, AlertCircle, Square, Zap, Settings2, ChevronDown, Hexagon } from 'lucide-react';
import Link from 'next/link';
import clsx from 'clsx';
import { LLM_PROVIDERS, T2I_PROVIDERS, I2I_PROVIDERS, VIDEO_PROVIDERS, VLM_PROVIDERS, VIDEO_RATIOS, ProviderGroup } from '@/config/models';

export type StageStatus = 'pending' | 'running' | 'waiting' | 'completed' | 'error' | 'stopped';

export const STAGES = [
  { id: 'script_generation', name: '剧本生成', shortName: '剧本' },
  { id: 'character_design', name: '角色设计', shortName: '角色' },
  { id: 'storyboard', name: '分镜设计', shortName: '分镜' },
  { id: 'reference_generation', name: '参考图', shortName: '参考图' },
  { id: 'video_generation', name: '视频生成', shortName: '视频' },
  { id: 'post_production', name: '后期剪辑', shortName: '后期' },
] as const;

export type StageId = typeof STAGES[number]['id'];

export interface ModelConfig {
  llm_model: string;
  vlm_model: string;
  image_t2i_model: string;
  image_it2i_model: string;
  video_model: string;
  video_ratio: string;
  enable_concurrency: boolean;
}

interface TopBarProps {
  /** null = 首页 */
  activeStage: string | null;
  stageStatuses: Record<string, StageStatus>;
  onStageClick: (stageId: string) => void;
  onHomeClick: () => void;
  /** 是否处于工作流中（有 sessionId） */
  hasSession: boolean;
  /** 是否正在执行 */
  isRunning: boolean;
  /** 停止执行 */
  onStop: () => void;
  /** 代理模式（自动执行全流程） */
  autoMode: boolean;
  onAutoModeChange: (auto: boolean) => void;
  /** 当前模型配置 */
  modelConfig?: ModelConfig;
  /** 模型配置变更 */
  onModelConfigChange?: (config: ModelConfig) => void;
  /** 项目状态（如 running, waiting_in_stage, stage_completed, session_completed, idle, error 等） */
  projectStatus?: string;
}

/* ─── 带 Provider 分组的 <select> ─── */
function ProviderSelect({
  value,
  providers,
  onChange,
}: {
  value: string;
  providers: ProviderGroup[];
  onChange: (val: string) => void;
}) {
  return (
    <select
      value={value}
      onChange={e => onChange(e.target.value)}
      className="bg-gray-50 border border-gray-200 rounded-lg px-2 py-1.5 text-xs text-gray-700 outline-none w-full"
    >
      {providers.map(pg => (
        <optgroup key={pg.provider} label={pg.label}>
          {pg.models.map(m => (
            <option key={m.id} value={m.id}>{m.label}</option>
          ))}
        </optgroup>
      ))}
    </select>
  );
}

/* ─── 模型选择下拉面板 ─── */
function ModelSelector({
  config,
  onChange,
}: {
  config: ModelConfig;
  onChange: (config: ModelConfig) => void;
}) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    if (open) document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [open]);

  const update = (key: keyof ModelConfig, val: string | boolean) => {
    onChange({ ...config, [key]: val });
  };

  return (
    <div ref={ref} className="relative">
      <button
        onClick={() => setOpen(!open)}
        className={clsx(
          'flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all',
          open
            ? 'bg-blue-50 text-blue-700 ring-1 ring-blue-200'
            : 'text-gray-500 hover:bg-gray-50'
        )}
        title="生成配置"
      >
        <Settings2 className="w-3.5 h-3.5" />
        <span>生成配置</span>
        <ChevronDown className={clsx('w-3 h-3 transition-transform', open && 'rotate-180')} />
      </button>

      {open && (
        <div className="absolute right-0 top-full mt-1 w-72 bg-white rounded-xl shadow-lg border border-gray-200 p-3 z-50 space-y-2.5">
          <label className="flex flex-col gap-1">
            <span className="text-[10px] text-gray-400 font-medium">LLM 模型</span>
            <ProviderSelect value={config.llm_model} providers={LLM_PROVIDERS} onChange={v => update('llm_model', v)} />
          </label>
          <label className="flex flex-col gap-1">
            <span className="text-[10px] text-gray-400 font-medium">VLM 评估模型</span>
            <ProviderSelect value={config.vlm_model} providers={VLM_PROVIDERS} onChange={v => update('vlm_model', v)} />
          </label>
          <label className="flex flex-col gap-1">
            <span className="text-[10px] text-gray-400 font-medium">文生图</span>
            <ProviderSelect value={config.image_t2i_model} providers={T2I_PROVIDERS} onChange={v => update('image_t2i_model', v)} />
          </label>
          <label className="flex flex-col gap-1">
            <span className="text-[10px] text-gray-400 font-medium">图生图</span>
            <ProviderSelect value={config.image_it2i_model} providers={I2I_PROVIDERS} onChange={v => update('image_it2i_model', v)} />
          </label>
          <label className="flex flex-col gap-1">
            <span className="text-[10px] text-gray-400 font-medium">视频模型</span>
            <ProviderSelect value={config.video_model} providers={VIDEO_PROVIDERS} onChange={v => update('video_model', v)} />
          </label>
          <label className="flex flex-col gap-1">
            <span className="text-[10px] text-gray-400 font-medium">视频比例</span>
            <div className="flex gap-0.5">
              {VIDEO_RATIOS.map(r => (
                <button
                  key={r.id}
                  onClick={() => update('video_ratio', r.id)}
                  className={`flex flex-col items-center gap-0.5 p-1 rounded border transition-all ${
                    config.video_ratio === r.id
                      ? 'border-indigo-500 bg-indigo-50'
                      : 'border-gray-200 hover:border-gray-300'
                  }`}
                  title={r.label}
                >
                  <div
                    className="bg-gray-600 rounded-sm"
                    style={{
                      width: r.ratio === '16:9' ? '16px' :
                             r.ratio === '9:16' ? '9px' :
                             r.ratio === '1:1' ? '12px' :
                             r.ratio === '4:3' ? '14px' :
                             r.ratio === '3:4' ? '10px' :
                             '18px',
                      height: r.ratio === '16:9' ? '9px' :
                             r.ratio === '9:16' ? '16px' :
                             r.ratio === '1:1' ? '12px' :
                             r.ratio === '4:3' ? '10px' :
                             r.ratio === '3:4' ? '14px' :
                             '7px',
                    }}
                  />
                  <span className="text-[8px] text-gray-500">{r.label}</span>
                </button>
              ))}
            </div>
          </label>
          <label className="flex items-center gap-2 text-xs cursor-pointer select-none">
            <input
              type="checkbox"
              checked={!!config.enable_concurrency}
              onChange={e => update('enable_concurrency', e.target.checked)}
              className="w-3.5 h-3.5 rounded border-gray-300 text-blue-500 focus:ring-blue-500/30"
            />
            <span className="text-gray-500">并发生成</span>
          </label>
        </div>
      )}
    </div>
  );
}

export default function TopBar({
  activeStage,
  stageStatuses,
  onStageClick,
  onHomeClick,
  hasSession,
  isRunning,
  onStop,
  autoMode,
  onAutoModeChange,
  modelConfig,
  onModelConfigChange,
  projectStatus,
}: TopBarProps) {
  const getStageIcon = (status: StageStatus, isActive: boolean) => {
    switch (status) {
      case 'completed':
        return <CheckCircle className="w-4 h-4 text-green-500" />;
      case 'running':
        return <Loader className="w-4 h-4 text-blue-500 animate-spin" />;
      case 'waiting':
        return <Edit3 className="w-4 h-4 text-amber-500" />;
      case 'error':
        return <AlertCircle className="w-4 h-4 text-red-500" />;
      default:
        return (
          <Circle
            className={clsx('w-4 h-4', isActive ? 'text-blue-400' : 'text-gray-300')}
          />
        );
    }
  };

  return (
    <header className="h-14 bg-white border-b border-gray-200 flex items-center px-4 flex-shrink-0 z-10">
      {/* Logo & 名称 */}
      <button
        onClick={onHomeClick}
        className="flex items-center gap-2 mr-6 hover:opacity-80 transition-opacity flex-shrink-0"
      >
        <img
          src="/logo.jpg"
          alt="Logo"
          className="w-8 h-8 rounded-lg object-contain"
        />
        <div className="flex flex-col leading-tight">
          <span className="font-bold text-sm text-gray-800 tracking-tight">
            AIGC-Claw
          </span>
        </div>
      </button>

      {/* 分隔线 */}
      {hasSession && <div className="w-px h-6 bg-gray-200 mr-4 flex-shrink-0" />}

      {/* 阶段进度条 */}
      {hasSession && (
        <nav className="flex items-center gap-1 overflow-x-auto flex-1 min-w-0">
          {STAGES.map((stage, idx) => {
            const status = stageStatuses[stage.id] || 'pending';
            const isActive = activeStage === stage.id;

            return (
              <React.Fragment key={stage.id}>
                {idx > 0 && (
                  <div
                    className={clsx(
                      'w-6 h-px flex-shrink-0',
                      stageStatuses[STAGES[idx - 1].id] === 'completed'
                        ? 'bg-green-300'
                        : 'bg-gray-200'
                    )}
                  />
                )}
                <button
                  onClick={() => onStageClick(stage.id)}
                  className={clsx(
                    'flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all whitespace-nowrap flex-shrink-0',
                    isActive
                      ? 'bg-blue-50 text-blue-700 ring-1 ring-blue-200'
                      : status === 'completed'
                        ? 'text-green-700 hover:bg-green-50'
                        : status === 'error'
                          ? 'text-red-600 hover:bg-red-50'
                          : 'text-gray-500 hover:bg-gray-50'
                  )}
                >
                  {getStageIcon(status, isActive)}
                  <span>{stage.shortName}</span>
                </button>
              </React.Fragment>
            );
          })}
        </nav>
      )}

      {/* 右侧控制区 */}
      <div className="ml-auto flex items-center gap-2 flex-shrink-0">
        {/* 模型选择 */}
        {hasSession && modelConfig && onModelConfigChange && (
          <ModelSelector config={modelConfig} onChange={onModelConfigChange} />
        )}

        {/* 代理模式切换 */}
        {hasSession && (
          <button
            onClick={() => onAutoModeChange(!autoMode)}
            className={clsx(
              'flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all',
              autoMode
                ? 'bg-amber-50 text-amber-700 ring-1 ring-amber-200'
                : 'text-gray-500 hover:bg-gray-50'
            )}
            title={autoMode ? '代理模式：自动执行全流程' : '手动模式：每阶段需确认'}
          >
            <Zap className="w-3.5 h-3.5" />
            <span>{autoMode ? '自动' : '手动'}</span>
          </button>
        )}

        {/* 停止按钮 */}
        {isRunning && (
          <button
            onClick={onStop}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-red-50 text-red-600 hover:bg-red-100 rounded-lg text-xs font-medium transition-colors ring-1 ring-red-200"
            title="停止执行"
          >
            <Square className="w-3.5 h-3.5 fill-current" />
            <span>停止</span>
          </button>
        )}

        {/* 项目状态 */}
        {hasSession && projectStatus && (
          <div
            className={clsx(
              'px-2 py-1 rounded-lg text-xs font-medium flex items-center gap-1',
              projectStatus === 'running' && 'bg-blue-50 text-blue-700',
              projectStatus === 'waiting_in_stage' && 'bg-amber-50 text-amber-700',
              projectStatus === 'stage_completed' && 'bg-green-50 text-green-700',
              projectStatus === 'idle' && 'bg-gray-50 text-gray-600',
              projectStatus === 'error' && 'bg-red-50 text-red-700',
              projectStatus === 'stopped' && 'bg-orange-50 text-orange-700'
            )}
            title="项目状态"
          >
            {projectStatus === 'running' && <Loader className="w-3 h-3 animate-spin" />}
            {projectStatus === 'waiting_in_stage' && <Edit3 className="w-3 h-3" />}
            {projectStatus === 'error' && <AlertCircle className="w-3 h-3" />}
            <span>
              {projectStatus === 'running' ? '执行中' :
               projectStatus === 'waiting_in_stage' ? '等待确认' :
               projectStatus === 'stage_completed' ? '阶段完成' :
               projectStatus === 'session_completed' ? '已完成' :
               projectStatus === 'idle' ? '空闲' :
               projectStatus === 'stopped' ? '已停止' :
               projectStatus === 'error' ? '出错' : projectStatus}
            </span>
          </div>
        )}


        {/* 临时工作台入口 */}
        <Link
          href="/sandbox"
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-gray-400 hover:text-indigo-600 hover:bg-indigo-50 transition-colors text-xs font-medium"
          title="临时工作台"
        >
          <Hexagon className="w-3.5 h-3.5" />
          <span>工作台</span>
        </Link>
      </div>
    </header>
  );
}
