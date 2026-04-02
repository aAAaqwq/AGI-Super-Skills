'use client';

import React, { useState, useRef, useEffect } from 'react';
import { Image as ImageIcon, RefreshCw, ChevronLeft, ChevronRight, Loader, AlertCircle, ZoomIn, ImagePlus, Edit2, Save } from 'lucide-react';
import type { StageViewProps } from './types';
import { assetUrl } from './utils';
import StageActions from './StageActions';
import StageProgress from './StageProgress';
import ImageLightbox from './ImageLightbox';

/* ─── 类型 ─── */
interface SceneItem {
  id: string;             // shot_001_01, shot_001_02, ...
  name: string;           // 场景1-镜头1
  index?: number;         // 全局编号
  description: string;    // 视觉提示词
  selected: string;       // 当前选中的文件路径
  versions: string[];     // 所有历史版本路径
  status?: 'pending' | 'done' | 'failed';
}

/* ─── 水平滚动图片画廊 ─── */
function ImageGallery({
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
  const [lightboxIndex, setLightboxIndex] = useState<number | null>(null);

  const scroll = (dir: 'left' | 'right') => {
    if (!scrollRef.current) return;
    scrollRef.current.scrollBy({ left: dir === 'left' ? -260 : 260, behavior: 'smooth' });
  };

  if (!versions.length) {
    return (
      <div className="flex items-center justify-center h-full text-gray-400 text-xs">
        暂无图片
      </div>
    );
  }

  return (
    <div className="relative group">
      {versions.length > 1 && (
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
                  ? 'ring-3 ring-emerald-500 shadow-lg shadow-emerald-200'
                  : 'ring-1 ring-gray-200 hover:ring-gray-300 hover:shadow-md'
              }`}
            >
              <div className="relative group/img">
                <img
                  src={assetUrl(path)}
                  alt={`v${i + 1}`}
                  className="h-28 w-auto object-cover"
                  onError={(e) => { (e.target as HTMLImageElement).style.display = 'none'; }}
                />
                <button
                  onClick={(e) => { e.stopPropagation(); setLightboxIndex(i); }}
                  className="absolute top-1 right-1 w-6 h-6 rounded-full bg-black/40 flex items-center justify-center opacity-0 group-hover/img:opacity-100 transition-opacity hover:bg-black/60"
                  title="放大查看"
                >
                  <ZoomIn className="w-3 h-3 text-white" />
                </button>
              </div>
              <div className={`text-center text-[10px] py-0.5 ${
                isSelected ? 'bg-emerald-500 text-white font-medium' : 'bg-gray-50 text-gray-400'
              }`}>
                v{i + 1}
              </div>
            </div>
          );
        })}
        {showPlaceholder && (
          <div className="flex-shrink-0 flex items-center justify-center h-28 aspect-video bg-gray-50 rounded-lg border border-dashed border-gray-200">
            <div className="flex items-center gap-2 text-gray-400 text-xs">
              <Loader className="w-4 h-4 animate-spin" />
              <span>生成中...</span>
            </div>
          </div>
        )}
      </div>
      {lightboxIndex !== null && (
        <ImageLightbox
          images={versions}
          initialIndex={lightboxIndex}
          onClose={() => setLightboxIndex(null)}
        />
      )}
    </div>
  );
}

/* ─── 场景行 ─── */
function SceneRow({
  scene,
  canEdit,
  editDesc,
  onDescChange,
  onRegenerate,
  onSelectVersion,
  onSavePrompt,
  isStageRunning,
  isRegenerating,
  isEditing,
  onToggleEdit,
}: {
  scene: SceneItem;
  canEdit: boolean;
  editDesc: string;
  onDescChange: (val: string) => void;
  onRegenerate: () => void;
  onSelectVersion: (path: string) => void;
  onSavePrompt: () => void;
  isStageRunning?: boolean;
  isRegenerating?: boolean;
  isEditing?: boolean;
  onToggleEdit?: () => void;
}) {
  const isPending = scene.status === 'pending' || isRegenerating;
  const isFailed = scene.status === 'failed' && !isRegenerating;
  const isPendingEmpty = scene.status === 'pending' && !scene.versions.length && !isRegenerating;
  const hasChanges = editDesc !== scene.description;

  return (
    <div className={`flex border rounded-xl overflow-hidden bg-white ${
      isFailed ? 'border-red-200' : 'border-gray-200'
    }`}>
      {/* 左侧: 提示词 */}
      <div className="w-[360px] flex-shrink-0 p-4 border-r border-gray-100 flex flex-col">
        <div className="flex items-center gap-2 mb-2">
          <span className="flex items-center justify-center w-6 h-6 rounded-full bg-emerald-100 text-emerald-700 text-xs font-bold flex-shrink-0">
            {scene.index ?? scene.id.replace('Scene_', '')}
          </span>
          <span className="text-sm font-semibold text-gray-800 truncate">{scene.name}</span>
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
                disabled={!hasChanges}
                className={`ml-auto flex items-center gap-1 px-2 py-1 rounded-lg text-xs font-medium transition-colors ${
                  hasChanges
                    ? 'text-white bg-emerald-500 hover:bg-emerald-600'
                    : 'text-gray-400 bg-gray-100 cursor-not-allowed'
                }`}
              >
                <Save className="w-3 h-3" />
                保存
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
            value={editDesc}
            onChange={e => onDescChange(e.target.value)}
            rows={6}
            className="flex-1 text-xs text-gray-600 bg-gray-50 border border-gray-200 rounded-lg p-2 resize-none focus:outline-none focus:ring-1 focus:ring-emerald-300"
          />
        ) : (
          <p className="flex-1 text-xs text-gray-600 leading-relaxed line-clamp-6">{scene.description}</p>
        )}
        {/* 重新生成按钮 */}
        {!isStageRunning && (
          <button
            onClick={onRegenerate}
            disabled={isRegenerating}
            className={`mt-3 flex items-center gap-1.5 self-start px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
              isRegenerating
                ? 'text-gray-400 bg-gray-100 cursor-not-allowed'
                : isFailed
                  ? 'text-red-600 bg-red-50 hover:bg-red-100'
                  : 'text-emerald-600 bg-emerald-50 hover:bg-emerald-100'
            }`}
          >
            <RefreshCw className={`w-3 h-3 ${isRegenerating ? 'animate-spin' : ''}`} />
            {isRegenerating ? '生成中...' : isFailed ? '点击重试' : '重新生成'}
          </button>
        )}
      </div>

      {/* 右侧: 图片画廊 / 占位 */}
      <div className="flex-1 min-w-0 p-3 flex items-center">
        {isPendingEmpty ? (
          <div
            className="flex items-center justify-center h-28 aspect-video bg-emerald-50/50 rounded-lg border border-dashed border-emerald-200 cursor-pointer hover:bg-emerald-100/50 transition-colors"
            onClick={onRegenerate}
          >
            <div className="flex flex-col items-center gap-1 text-emerald-500 text-xs">
              <ImagePlus className="w-4 h-4" />
              <span>生成首帧参考图</span>
            </div>
          </div>
        ) : isPending && !scene.versions.length ? (
          <div className="flex items-center justify-center h-28 aspect-video bg-gray-50 rounded-lg border border-dashed border-gray-200">
            <div className="flex items-center gap-2 text-gray-400 text-xs">
              <Loader className="w-4 h-4 animate-spin" />
              <span>正在生成...</span>
            </div>
          </div>
        ) : isFailed && !scene.versions.length ? (
          <div
            className="flex items-center justify-center h-28 aspect-video bg-red-50/50 rounded-lg border border-dashed border-red-200 cursor-pointer hover:bg-red-100/50 transition-colors"
            onClick={onRegenerate}
          >
            <div className="flex flex-col items-center gap-1 text-red-400 text-xs">
              <AlertCircle className="w-4 h-4" />
              <span>生成失败，点击重试</span>
            </div>
          </div>
        ) : (
          <div className="relative w-full">
            <ImageGallery
              versions={scene.versions}
              selected={scene.selected}
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
export default function ReferenceStage({ state, sessionId, onConfirm, onIntervene, onRegenerate, onUpdateArtifact, onSaveSelections, showConfirm, isRunning, hasPendingItems, hasNextStageStarted }: StageViewProps) {
  // 兼容旧格式: scene_images: {Scene_1: "path"} → scenes: [{id, ...}]
  const scenes: SceneItem[] = (() => {
    if (state.artifact?.scenes?.length) return state.artifact.scenes;
    if (state.artifact?.scene_images) {
      const si = state.artifact.scene_images as Record<string, string>;
      return Object.entries(si)
        .sort(([a], [b]) => {
          const na = parseInt(a.replace(/\D/g, '')) || 0;
          const nb = parseInt(b.replace(/\D/g, '')) || 0;
          return na - nb;
        })
        .map(([id, path]) => ({
          id,
          name: `场景 ${id.replace('Scene_', '')}`,
          description: '',
          selected: path,
          versions: [path],
          status: 'done' as const,
        }));
    }
    return [];
  })();

  const [editDescs, setEditDescs] = useState<Record<string, string>>({});
  const [selectedVersions, setSelectedVersions] = useState<Record<string, string>>({});
  const [regeneratingIds, setRegeneratingIds] = useState<Set<string>>(new Set());
  const [editingIds, setEditingIds] = useState<Set<string>>(new Set());
  const [savingIds, setSavingIds] = useState<Set<string>>(new Set());

  const canEdit = state.status === 'waiting' || state.status === 'completed';

  // 当场景数据变化时，初始化编辑描述
  useEffect(() => {
    if (scenes.length > 0) {
      setEditDescs(prev => {
        const next: Record<string, string> = {};
        scenes.forEach(s => { next[s.id] = prev[s.id] ?? s.description; });
        return next;
      });
    }
  }, [scenes]);

  // 当 artifact 更新时清除重新生成状态
  useEffect(() => {
    if (regeneratingIds.size > 0) setRegeneratingIds(new Set());
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [state.artifact]);

  const hasScenes = scenes.length > 0;

  // 保存单个提示词到后端 JSON
  const handleSavePrompt = async (sceneId: string) => {
    const newPrompt = editDescs[sceneId];
    if (!newPrompt) return;

    setSavingIds(prev => new Set(prev).add(sceneId));
    try {
      // 调用后端 API 保存提示词
      const response = await fetch(`/api/project/${sessionId}/artifact/reference_generation`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          shots: scenes.map(s => ({
            shot_id: s.id,
            visual_prompt: s.id === sceneId ? newPrompt : s.description
          }))
        })
      });
      if (response.ok) {
        // 保存成功后关闭编辑模式
        setEditingIds(prev => {
          const next = new Set(prev);
          next.delete(sceneId);
          return next;
        });
        // 更新本地状态，使用保存后的值
        setEditDescs(prev => ({ ...prev, [sceneId]: newPrompt }));
        // 同步更新 artifact 以便后续阶段能获取最新的提示词
        if (onUpdateArtifact && state.artifact?.scenes) {
          const updatedScenes = state.artifact.scenes.map((s: SceneItem) =>
            s.id === sceneId ? { ...s, description: newPrompt } : s
          );
          onUpdateArtifact({ scenes: updatedScenes });
        }
      }
    } catch (error) {
      console.error('保存提示词失败:', error);
    } finally {
      setSavingIds(prev => {
        const next = new Set(prev);
        next.delete(sceneId);
        return next;
      });
    }
  };

  // 切换编辑模式
  const handleToggleEdit = (sceneId: string) => {
    setEditingIds(prev => {
      const next = new Set(prev);
      if (next.has(sceneId)) {
        next.delete(sceneId);
      } else {
        next.add(sceneId);
      }
      return next;
    });
  };

  const handleRegenerate = (sceneId: string) => {
    setRegeneratingIds(prev => new Set(prev).add(sceneId));
    onIntervene({ regenerate_scenes: [sceneId] });
  };

  const handleSelectVersion = async (sceneId: string, path: string) => {
    setSelectedVersions(prev => ({ ...prev, [sceneId]: path }));
    // 同步更新 artifact 以便确认时能传递正确的选中图片给阶段5
    if (onUpdateArtifact && state.artifact?.scenes) {
      const updatedScenes = state.artifact.scenes.map((s: SceneItem) =>
        s.id === sceneId ? { ...s, selected: path } : s
      );
      onUpdateArtifact({ scenes: updatedScenes });
    }
    // 自动保存选择
    const selections: Record<string, string> = {};
    scenes.forEach(s => { selections[s.id] = selectedVersions[s.id] || s.selected; });
    selections[sceneId] = path;
    if (onSaveSelections) {
      await onSaveSelections(selections);
    }
  };

  const getSelected = (scene: SceneItem) => selectedVersions[scene.id] || scene.selected;

  return (
    <div className="flex flex-col h-full">
      <div className="flex-1 overflow-y-auto p-6">
        {/* 标题栏 */}
        <div className="flex items-center justify-between mb-1">
          <h2 className="text-lg font-semibold text-gray-800">参考图生成</h2>
        </div>
        <p className="text-sm text-gray-500 mb-6">
          基于角色/场景素材 + 分镜视觉描述，使用图生图生成场景参考图
        </p>

        {/* 运行中 */}
        {state.status === 'running' && (
          <StageProgress message={state.progressMessage} fallback="正在生成参考图..." progress={state.progress} color="emerald" />
        )}

        {state.error && (
          <div className="text-sm text-red-600 bg-red-50 border border-red-200 p-4 rounded-xl mb-4">{state.error}</div>
        )}

        {/* ═══ 场景列表 ═══ */}
        {hasScenes && (
          <section>
            <div className="flex items-center gap-2 mb-3">
              <ImageIcon className="w-4 h-4 text-emerald-500" />
              <h3 className="text-sm font-semibold text-gray-700">场景参考图 ({scenes.length})</h3>
            </div>
            <div className="space-y-3">
              {scenes.map(scene => (
                <SceneRow
                  key={scene.id}
                  scene={{ ...scene, selected: getSelected(scene) }}
                  canEdit={canEdit}
                  editDesc={editDescs[scene.id] || scene.description}
                  onDescChange={val => setEditDescs(prev => ({ ...prev, [scene.id]: val }))}
                  onRegenerate={() => handleRegenerate(scene.id)}
                  onSelectVersion={path => handleSelectVersion(scene.id, path)}
                  onSavePrompt={() => handleSavePrompt(scene.id)}
                  isStageRunning={state.status === 'running'}
                  isRegenerating={regeneratingIds.has(scene.id) || savingIds.has(scene.id)}
                  isEditing={editingIds.has(scene.id)}
                  onToggleEdit={() => handleToggleEdit(scene.id)}
                />
              ))}
            </div>
          </section>
        )}

        {/* 如果有 artifact 数据（即使 status 是 pending），也显示内容 */}
        {state.status === 'pending' && !hasScenes && (
          <div className="text-center text-gray-400 text-sm py-20">等待上一阶段完成...</div>
        )}
      </div>

      {/* 底部操作栏 */}
      <StageActions
        status={state.status}
        onConfirm={onConfirm}
        showConfirm={showConfirm}
        onSave={undefined}
        onRegenerate={onRegenerate}
        stageId="reference_generation"
        hasPendingItems={hasPendingItems}
        hasNextStageStarted={hasNextStageStarted}
        isRunning={isRunning}
      />
    </div>
  );
}
