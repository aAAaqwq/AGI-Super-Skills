'use client';

import React, { useState, useRef, useCallback, useEffect } from 'react';
import { Film, RefreshCw, ChevronLeft, ChevronRight, Loader, AlertCircle, AlertTriangle, Play, Volume2, VolumeX, Clapperboard, Edit2, Save } from 'lucide-react';
import type { StageViewProps } from './types';
import { assetUrl } from './utils';
import StageActions from './StageActions';
import StageProgress from './StageProgress';

/* ─── 类型 ─── */
interface ClipItem {
  id: string;             // shot_001_01, shot_001_02, ...
  name: string;           // 场景1-镜头1
  index?: number;         // 全局编号
  description: string;    // 提示词
  duration?: number;      // 视频时长（秒）
  selected: string;       // 当前选中的视频路径
  versions: string[];     // 所有历史版本路径
  status?: 'pending' | 'done' | 'failed';
}

/* ─── 水平滚动视频画廊 ─── */
function VideoGallery({
  versions,
  selected,
  onSelect,
  showPlaceholder,
}: {
  versions: string[];
  selected: string;
  onSelect: (path: string) => void;
  showPlaceholder?: boolean;
}) {
  const scrollRef = useRef<HTMLDivElement>(null);

  const scroll = (dir: 'left' | 'right') => {
    if (!scrollRef.current) return;
    scrollRef.current.scrollBy({ left: dir === 'left' ? -300 : 300, behavior: 'smooth' });
  };

  if (!versions.length && !showPlaceholder) {
    return (
      <div className="flex items-center justify-center h-full text-gray-400 text-xs">
        暂无视频
      </div>
    );
  }

  return (
    <div className="relative group">
      {(versions.length > 1 || (versions.length >= 1 && showPlaceholder)) && (
        <>
          <button
            onClick={() => scroll('left')}
            className="absolute left-0 top-1/2 -translate-y-1/2 z-10 w-7 h-7 rounded-full bg-white/90 shadow border border-gray-200 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity"
          >
            <ChevronLeft className="w-4 h-4 text-gray-600" />
          </button>
          <button
            onClick={() => scroll('right')}
            className="absolute right-0 top-1/2 -translate-y-1/2 z-10 w-7 h-7 rounded-full bg-white/90 shadow border border-gray-200 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity"
          >
            <ChevronRight className="w-4 h-4 text-gray-600" />
          </button>
        </>
      )}
      <div
        ref={scrollRef}
        className="flex gap-3 overflow-x-auto scrollbar-hide py-1 px-1"
        style={{ scrollbarWidth: 'none' }}
      >
        {versions.map((path, i) => {
          const isSelected = path === selected;
          return (
            <div
              key={path}
              onClick={() => onSelect(path)}
              className={`flex-shrink-0 cursor-pointer rounded-lg overflow-hidden transition-all ${
                isSelected
                  ? 'ring-3 ring-rose-500 shadow-lg shadow-rose-200'
                  : 'ring-1 ring-gray-200 hover:ring-gray-300 hover:shadow-md'
              }`}
            >
              <div className="relative bg-black">
                <video
                  src={assetUrl(path)}
                  controls={isSelected}
                  preload="metadata"
                  className="h-32 aspect-video object-cover"
                />
                {!isSelected && (
                  <div className="absolute inset-0 flex items-center justify-center bg-black/10">
                    <Play className="w-6 h-6 text-white/70" />
                  </div>
                )}
              </div>
              <div className={`text-center text-[10px] py-0.5 ${
                isSelected ? 'bg-rose-500 text-white font-medium' : 'bg-gray-50 text-gray-400'
              }`}>
                v{i + 1}
              </div>
            </div>
          );
        })}
        {showPlaceholder && (
          <div className="flex-shrink-0 flex items-center justify-center h-32 aspect-video bg-gray-50 rounded-lg border border-dashed border-gray-200">
            <div className="flex items-center gap-2 text-gray-400 text-xs">
              <Loader className="w-4 h-4 animate-spin" />
              <span>生成中...</span>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

/* ─── 视频行 ─── */
function ClipRow({
  clip,
  editDesc,
  onDescChange,
  onSavePrompt,
  onRegenerate,
  onSelectVersion,
  onToggleEdit,
  isStageRunning,
  isRegenerating,
  isEditing,
  canEdit,
  disabled,
  isSaving,
}: {
  clip: ClipItem;
  editDesc?: string;
  onDescChange?: (val: string) => void;
  onSavePrompt?: () => void;
  onRegenerate: () => void;
  onSelectVersion: (path: string) => void;
  onToggleEdit?: () => void;
  isStageRunning?: boolean;
  isRegenerating?: boolean;
  isEditing?: boolean;
  canEdit?: boolean;
  disabled?: boolean;
  isSaving?: boolean;
}) {
  const isPending = clip.status === 'pending' || isRegenerating;
  const isFailed = clip.status === 'failed' && !isRegenerating;
  const hasChanges = editDesc !== clip.description;

  return (
    <div className={`flex border rounded-xl overflow-hidden bg-white ${disabled ? 'opacity-50' : ''} ${
      isFailed ? 'border-red-200' : 'border-gray-200'
    }`}>
      {/* 左侧: 描述信息 */}
      <div className="w-[280px] flex-shrink-0 p-4 border-r border-gray-100 flex flex-col">
        <div className="flex items-center gap-2 mb-2">
          <span className="flex items-center justify-center w-6 h-6 rounded-full bg-rose-100 text-rose-700 text-xs font-bold flex-shrink-0">
            {clip.index ?? clip.id.replace('Scene_', '')}
          </span>
          <span className="text-sm font-semibold text-gray-800 truncate">{clip.name}</span>
          {clip.duration && (
            <span className="text-[10px] bg-gray-100 text-gray-500 px-1.5 py-0.5 rounded">{clip.duration}s</span>
          )}
          {isPending && (
            <span className="inline-flex items-center gap-1 text-[10px] bg-amber-50 text-amber-600 px-1.5 py-0.5 rounded">
              <Loader className="w-2.5 h-2.5 animate-spin" />生成中
            </span>
          )}
          {isFailed && (
            <span className="text-[10px] bg-red-50 text-red-500 px-1.5 py-0.5 rounded">失败</span>
          )}
          {/* 编辑/保存按钮 */}
          {canEdit && !isStageRunning && (
            isEditing ? (
              <button
                onClick={onSavePrompt}
                disabled={!hasChanges || isSaving}
                className={`ml-auto flex items-center gap-1 px-2 py-1 rounded-lg text-xs font-medium transition-colors ${
                  hasChanges && !isSaving
                    ? 'text-white bg-emerald-500 hover:bg-emerald-600'
                    : 'text-gray-400 bg-gray-100 cursor-not-allowed'
                }`}
              >
                <Save className="w-3 h-3" />
                {isSaving ? '保存中' : '保存'}
              </button>
            ) : (
              <button
                onClick={onToggleEdit}
                className="ml-auto flex items-center gap-1 px-2 py-1 rounded-lg text-xs font-medium text-blue-600 bg-blue-50 hover:bg-blue-100 transition-colors"
              >
                <Edit2 className="w-3 h-3" />
                编辑
              </button>
            )
          )}
        </div>
        {isEditing ? (
          <textarea
            value={editDesc ?? clip.description}
            onChange={e => onDescChange?.(e.target.value)}
            rows={4}
            className="flex-1 text-xs text-gray-600 bg-gray-50 border border-gray-200 rounded-lg p-2 resize-none focus:outline-none focus:ring-1 focus:ring-rose-300"
          />
        ) : clip.description ? (
          <p className="flex-1 text-xs text-gray-600 leading-relaxed line-clamp-4">{clip.description}</p>
        ) : (
          <p className="flex-1 text-xs text-gray-400 italic">无提示词</p>
        )}
        {/* 重新生成按钮 */}
        {!isStageRunning && (
          <button
            onClick={onRegenerate}
            disabled={disabled}
            className={`mt-3 flex items-center gap-1.5 self-start px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
              disabled
                ? 'text-gray-400 bg-gray-100 cursor-not-allowed'
                : isFailed
                  ? 'text-red-600 bg-red-50 hover:bg-red-100'
                  : 'text-rose-600 bg-rose-50 hover:bg-rose-100'
            }`}
          >
            <RefreshCw className="w-3 h-3" />
            {isFailed ? '点击重试' : '重新生成'}
          </button>
        )}
      </div>

      {/* 右侧: 视频画廊 / 占位 */}
      <div className="flex-1 min-w-0 p-3 flex items-center">
        {isPending && !clip.versions.length ? (
          <div className="flex items-center justify-center h-32 aspect-video bg-gray-50 rounded-lg border border-dashed border-gray-200">
            <div className="flex items-center gap-2 text-gray-400 text-xs">
              <Loader className="w-4 h-4 animate-spin" />
              <span>正在生成视频...</span>
            </div>
          </div>
        ) : isFailed && !clip.versions.length ? (
          <div
            className="flex items-center justify-center h-32 aspect-video bg-red-50/50 rounded-lg border border-dashed border-red-200 cursor-pointer hover:bg-red-100/50 transition-colors"
            onClick={onRegenerate}
          >
            <div className="flex flex-col items-center gap-1 text-red-400 text-xs">
              <AlertCircle className="w-4 h-4" />
              <span>生成失败，点击重试</span>
            </div>
          </div>
        ) : (
          <div className="relative w-full">
            <VideoGallery
              versions={clip.versions}
              selected={clip.selected}
              onSelect={onSelectVersion}
              showPlaceholder={isRegenerating}
            />
            {isFailed && (
              <button
                onClick={onRegenerate}
                className="absolute top-1 right-1 z-10 flex items-center gap-1 px-2 py-1 rounded-lg text-[10px] font-medium text-white bg-red-500/80 hover:bg-red-600 shadow transition-colors"
              >
                <RefreshCw className="w-2.5 h-2.5" />
                重试
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

/* ─── 主组件 ─── */
export default function VideoStage({ state, sessionId, onConfirm, onIntervene, onRegenerate, onUpdateArtifact, onSaveSelections, showConfirm, isRunning, videoSound = 'on', videoShotType = 'multi', onVideoParamsChange, referenceArtifact, hasPendingItems, hasNextStageStarted }: StageViewProps) {
  // 检查每个 clip 是否有对应的参考图
  const hasReferenceImage = useCallback((clipId: string): boolean => {
    if (!referenceArtifact?.scenes) return false;
    const refScene = referenceArtifact.scenes.find((s: any) => s.id === clipId);
    return !!(refScene?.selected || refScene?.versions?.length);
  }, [referenceArtifact]);

  // 兼容旧格式: video_clips: {Scene_1: "path"} → clips: [{id, ...}]
  const clips: ClipItem[] = (() => {
    if (state.artifact?.clips?.length) return state.artifact.clips;
    if (state.artifact?.video_clips) {
      const vc = state.artifact.video_clips as Record<string, string>;
      return Object.entries(vc)
        .sort(([a], [b]) => {
          const na = parseInt(a.replace(/\D/g, '')) || 0;
          const nb = parseInt(b.replace(/\D/g, '')) || 0;
          return na - nb;
        })
        .map(([id, path]) => ({
          id,
          name: `片段 ${id.replace('Scene_', '')}`,
          description: '',
          selected: path,
          versions: [path],
          status: 'done' as const,
        }));
    }
    return [];
  })();

  const [selectedVersions, setSelectedVersions] = useState<Record<string, string>>({});
  const [editDescs, setEditDescs] = useState<Record<string, string>>({});
  const [regeneratingIds, setRegeneratingIds] = useState<Set<string>>(new Set());
  const [editingIds, setEditingIds] = useState<Set<string>>(new Set());
  const [savingIds, setSavingIds] = useState<Set<string>>(new Set());

  // 当分镜数据变化时，初始化编辑描述
  useEffect(() => {
    if (clips.length > 0) {
      setEditDescs(prev => {
        const next: Record<string, string> = {};
        clips.forEach(c => { next[c.id] = prev[c.id] ?? c.description; });
        return next;
      });
    }
  }, [clips]);

  // 当 artifact 更新时清除重新生成状态
  useEffect(() => {
    if (regeneratingIds.size > 0) setRegeneratingIds(new Set());
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [state.artifact]);

  const hasClips = clips.length > 0;
  const canEdit = state.status === 'waiting' || state.status === 'completed';

  // 保存单个提示词到后端 JSON
  const handleSavePrompt = async (clipId: string) => {
    const newPrompt = editDescs[clipId];
    if (!newPrompt) return;

    setSavingIds(prev => new Set(prev).add(clipId));
    try {
      const response = await fetch(`/api/project/${sessionId}/artifact/video_generation`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          [clipId]: { description: newPrompt }
        })
      });
      if (response.ok) {
        // 更新前端缓存的 clips.description
        if (onUpdateArtifact && state.artifact?.clips) {
          const updatedClips = state.artifact.clips.map((c: ClipItem) =>
            c.id === clipId ? { ...c, description: newPrompt } : c
          );
          onUpdateArtifact({ clips: updatedClips });
        }
        setEditingIds(prev => {
          const next = new Set(prev);
          next.delete(clipId);
          return next;
        });
        setEditDescs(prev => ({ ...prev, [clipId]: newPrompt }));
      }
    } catch (error) {
      console.error('保存提示词失败:', error);
    } finally {
      setSavingIds(prev => {
        const next = new Set(prev);
        next.delete(clipId);
        return next;
      });
    }
  };

  // 切换编辑模式
  const handleToggleEdit = (clipId: string) => {
    setEditingIds(prev => {
      const next = new Set(prev);
      if (next.has(clipId)) {
        next.delete(clipId);
      } else {
        next.add(clipId);
      }
      return next;
    });
  };

  const handleRegenerate = (clipId: string) => {
    setRegeneratingIds(prev => new Set(prev).add(clipId));
    onIntervene({ regenerate_clips: [clipId] });
  };

  const handleSelectVersion = async (clipId: string, path: string) => {
    setSelectedVersions(prev => ({ ...prev, [clipId]: path }));
    // 同步更新 artifact 以便确认时能传递正确的选中片段给阶段6
    if (onUpdateArtifact && state.artifact?.clips) {
      const updatedClips = state.artifact.clips.map((c: ClipItem) =>
        c.id === clipId ? { ...c, selected: path } : c
      );
      onUpdateArtifact({ clips: updatedClips });
    }
    // 自动保存选择
    const selections: Record<string, string> = {};
    clips.forEach(c => { selections[c.id] = selectedVersions[c.id] || c.selected; });
    selections[clipId] = path;
    if (onSaveSelections) {
      await onSaveSelections(selections);
    }
  };

  const getSelected = (clip: ClipItem) => selectedVersions[clip.id] || clip.selected;

  return (
    <div className="flex flex-col h-full">
      <div className="flex-1 overflow-y-auto p-6">
        {/* 标题栏 */}
        <div className="flex items-center justify-between mb-1">
          <h2 className="text-lg font-semibold text-gray-800">视频生成</h2>
        </div>
        <p className="text-sm text-gray-500 mb-4">
          将场景参考图转化为视频片段，支持逐项重新生成
        </p>

        {/* ── 视频生成参数 ── */}
        <div className="flex items-center gap-6 mb-6 px-4 py-3 bg-white border border-gray-200 rounded-xl">
          {/* 音效开关 */}
          <div className="flex items-center gap-2">
            <span className="text-xs text-gray-500 font-medium">音效</span>
            <button
              onClick={() => onVideoParamsChange?.({ videoSound: videoSound === 'on' ? 'off' : 'on' })}
              className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                videoSound === 'on' ? 'bg-rose-500' : 'bg-gray-300'
              }`}
            >
              <span
                className={`inline-block h-4 w-4 transform rounded-full bg-white shadow transition-transform ${
                  videoSound === 'on' ? 'translate-x-6' : 'translate-x-1'
                }`}
              />
            </button>
            {videoSound === 'on' ? (
              <Volume2 className="w-3.5 h-3.5 text-rose-500" />
            ) : (
              <VolumeX className="w-3.5 h-3.5 text-gray-400" />
            )}
          </div>

          <div className="w-px h-5 bg-gray-200" />

          {/* 镜头模式 */}
          <div className="flex items-center gap-2">
            <Clapperboard className="w-3.5 h-3.5 text-gray-400" />
            <span className="text-xs text-gray-500 font-medium">镜头</span>
            <div className="flex gap-1 bg-gray-100 rounded-lg p-0.5">
              <button
                onClick={() => onVideoParamsChange?.({ videoShotType: 'single' })}
                className={`px-3 py-1 rounded-md text-xs font-medium transition-colors ${
                  videoShotType === 'single'
                    ? 'bg-white text-rose-600 shadow-sm'
                    : 'text-gray-500 hover:text-gray-700'
                }`}
              >
                单镜头
              </button>
              <button
                onClick={() => onVideoParamsChange?.({ videoShotType: 'multi' })}
                className={`px-3 py-1 rounded-md text-xs font-medium transition-colors ${
                  videoShotType === 'multi'
                    ? 'bg-white text-rose-600 shadow-sm'
                    : 'text-gray-500 hover:text-gray-700'
                }`}
              >
                多镜头
              </button>
            </div>
          </div>
        </div>

        {/* 运行中 */}
        {state.status === 'running' && (
          <StageProgress message={state.progressMessage} fallback="正在生成视频..." progress={state.progress} color="rose" />
        )}

        {state.error && (
          <div className="text-sm text-red-600 bg-red-50 border border-red-200 p-4 rounded-xl mb-4">{state.error}</div>
        )}

        {/* ═══ 视频列表 ═══ */}
        {hasClips && (
          <section>
            <div className="flex items-center gap-2 mb-3">
              <Film className="w-4 h-4 text-rose-500" />
              <h3 className="text-sm font-semibold text-gray-700">视频片段 ({clips.length})</h3>
            </div>
            <div className="space-y-3">
              {clips.map(clip => {
                // 检查是否有参考图
                const hasRef = hasReferenceImage(clip.id);
                return (
                  <div key={clip.id} className="relative">
                    {!hasRef && (
                      <div className="mb-2 px-3 py-2 bg-amber-50 border border-amber-200 rounded-lg text-xs text-amber-700 flex items-center gap-2">
                        <AlertTriangle className="w-3.5 h-3.5" />
                        未检测到首帧参考图，请先完成参考图生成
                      </div>
                    )}
                    <ClipRow
                      clip={{ ...clip, selected: getSelected(clip) }}
                      editDesc={editDescs[clip.id]}
                      onDescChange={canEdit ? (val => setEditDescs(prev => ({ ...prev, [clip.id]: val }))) : undefined}
                      onSavePrompt={() => handleSavePrompt(clip.id)}
                      onRegenerate={() => handleRegenerate(clip.id)}
                      onSelectVersion={path => handleSelectVersion(clip.id, path)}
                      onToggleEdit={() => handleToggleEdit(clip.id)}
                      isStageRunning={state.status === 'running'}
                      isRegenerating={regeneratingIds.has(clip.id)}
                      isEditing={editingIds.has(clip.id)}
                      canEdit={canEdit}
                      disabled={!hasRef}
                      isSaving={savingIds.has(clip.id)}
                    />
                  </div>
                );
              })}
            </div>
          </section>
        )}

        {/* 如果有 artifact 数据（即使 status 是 pending），也显示内容 */}
        {state.status === 'pending' && !hasClips && (
          <div className="text-center text-gray-400 text-sm py-20">等待上一阶段完成...</div>
        )}
      </div>

      {/* 底部操作栏 */}
      <StageActions
        status={state.status}
        onConfirm={onConfirm}
        showConfirm={showConfirm}
        onRegenerate={onRegenerate}
        stageId="video_generation"
        hasPendingItems={hasPendingItems}
        hasNextStageStarted={hasNextStageStarted}
        isRunning={isRunning}
      />
    </div>
  );
}
