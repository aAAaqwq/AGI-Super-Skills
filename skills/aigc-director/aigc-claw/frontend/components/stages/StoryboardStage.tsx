'use client';

import React, { useState, useMemo, useCallback, useEffect } from 'react';
import { Save, X, Code, LayoutList, Camera, Clock, MapPin, Users, Plus, Trash2, Sparkles, Check, AlertTriangle } from 'lucide-react';
import type { StageViewProps } from './types';
import StageActions from './StageActions';
import StageProgress from './StageProgress';
import { checkSceneAssets } from '@/lib/workflowApi';

// ─── 类型 ───

interface Shot {
  shot_id: string;
  scene_number: number;
  act: number;
  shot_number: number;
  duration: number; // 5 | 10 | 15
  location: string;
  characters: string[];
  plot: string;
  visual_prompt: string;
  is_new?: boolean; // 新添加的分镜标记
}

const ACT_NAMES: Record<number, string> = {
  1: '激励事件', 2: '进入新世界', 3: '灵魂黑夜', 4: '高潮决战',
};

const DURATION_COLORS: Record<number, string> = {
  5:  'bg-green-100 text-green-700',
  10: 'bg-amber-100 text-amber-700',
  15: 'bg-red-100 text-red-700',
};

// ─── 分镜视图 ───

export default function StoryboardStage({ state, sessionId, onConfirm, onIntervene, onRegenerate, onSaveSelections, showConfirm, isRunning, hasPendingItems, hasNextStageStarted }: StageViewProps) {
  // 处理嵌套的 shots 结构：可能是数组，也可能是 {payload: {shots: []}, requires_intervention: true}
  const artifactShots = state.artifact?.shots;
  let shots: Shot[] = [];
  if (Array.isArray(artifactShots)) {
    shots = artifactShots;
  } else if (artifactShots?.payload?.shots) {
    shots = artifactShots.payload.shots;
  }
  const newShotIds = new Set(state.artifact?.new_shot_ids || state.artifact?.payload?.new_shot_ids || []);

  // 跟踪新添加但未确认的分镜
  const [pendingNewShots, setPendingNewShots] = useState<string[]>([]);

  const [isEditing, setIsEditing] = useState(false);
  const [editMode, setEditMode] = useState<'structured' | 'raw'>('structured');
  const [editShots, setEditShots] = useState<Shot[]>([]);
  const [rawJson, setRawJson] = useState('');
  const [isContinuing, setIsContinuing] = useState(false);

  // 删除场景时的确认对话框
  const [deleteConfirm, setDeleteConfirm] = useState<{
    show: boolean;
    sceneNumber: number;
    assetInfo: { reference_images: number; videos: number } | null;
  }>({ show: false, sceneNumber: 0, assetInfo: null });

  // 检测新添加的分镜 - 使用shots的JSON字符串作为依赖避免无限循环
  const shotsJson = JSON.stringify(shots || []);
  useEffect(() => {
    try {
      const parsed = JSON.parse(shotsJson);
      if (Array.isArray(parsed)) {
        const newIds = parsed.filter((s: Shot) => s.is_new).map((s: Shot) => s.shot_id);
        setPendingNewShots(newIds);
      }
    } catch { /* ignore parse errors */ }
  }, [shotsJson]);

  // 确认新分镜（清除 is_new 标记）
  const handleConfirmNewShots = useCallback(async () => {
    // 保留原始 shots 用于第4阶段（带有 is_new 标记）
    const originalShots = [...shots];

    // 使用 shots 中已有的 is_new 字段来确认（因为 new_shot_ids 保存后会被清除）
    const confirmedShots = shots.map(s => {
      if (s.is_new) {
        return { ...s, is_new: false };
      }
      return s;
    });
    // 保存时清除 new_shot_ids 标记，同时传递原始 shots 用于刷新第4阶段
    await onSaveSelections?.({ shots: confirmedShots, new_shot_ids: [], original_shots: originalShots });
    setPendingNewShots([]);
  }, [shots, onSaveSelections]);

  // 取消新分镜（删除）
  const handleCancelNewShots = useCallback(async () => {
    // 使用 shots 中已有的 is_new 字段来过滤
    const filteredShots = shots.filter(s => !s.is_new);
    await onSaveSelections?.({ shots: filteredShots });
    setPendingNewShots([]);
  }, [shots, onSaveSelections]);

  // 生成新的 shot_id
  const generateShotId = (sceneNum: number, shotNum: number) => {
    return `shot_${sceneNum.toString().padStart(3, '0')}_${shotNum.toString().padStart(2, '0')}`;
  };

  // 添加新场景
  const addScene = useCallback(() => {
    if (editShots.length === 0) return;
    const lastShot = editShots[editShots.length - 1];
    const newSceneNum = (lastShot?.scene_number || 0) + 1;
    const newAct = lastShot?.act || 1;

    // 添加一个空分镜
    const newShot: Shot = {
      shot_id: generateShotId(newSceneNum, 1),
      scene_number: newSceneNum,
      act: newAct,
      shot_number: 1,
      duration: 10,
      location: '',
      characters: [],
      plot: '',
      visual_prompt: '',
    };
    setEditShots(prev => [...prev, newShot]);
  }, [editShots]);

  // 删除场景（先检查是否有生成的资产）
  const deleteScene = useCallback(async (sceneNum: number) => {
    // 检查该场景是否有生成的参考图或视频
    try {
      const assets = await checkSceneAssets(sessionId, sceneNum);
      if (assets.reference_images > 0 || assets.videos > 0) {
        // 有资产，显示确认对话框
        setDeleteConfirm({
          show: true,
          sceneNumber: sceneNum,
          assetInfo: { reference_images: assets.reference_images, videos: assets.videos },
        });
        return;
      }
    } catch (e) {
      // API 调用失败，直接删除
      console.error('Failed to check scene assets:', e);
    }
    // 没有资产，直接删除
    setEditShots(prev => prev.filter(s => s.scene_number !== sceneNum));
  }, [sessionId]);

  // 确认删除场景
  const confirmDeleteScene = useCallback(() => {
    setEditShots(prev => prev.filter(s => s.scene_number !== deleteConfirm.sceneNumber));
    setDeleteConfirm({ show: false, sceneNumber: 0, assetInfo: null });
  }, [deleteConfirm.sceneNumber]);

  // 取消删除
  const cancelDeleteScene = useCallback(() => {
    setDeleteConfirm({ show: false, sceneNumber: 0, assetInfo: null });
  }, []);

  // 添加分镜
  const addShot = useCallback((sceneNum: number) => {
    setEditShots(prev => {
      const sceneShots = prev.filter(s => s.scene_number === sceneNum);
      const lastShot = sceneShots[sceneShots.length - 1];
      const newShotNum = (lastShot?.shot_number || 0) + 1;
      const act = lastShot?.act || 1;

      const newShot: Shot = {
        shot_id: generateShotId(sceneNum, newShotNum),
        scene_number: sceneNum,
        act: act,
        shot_number: newShotNum,
        duration: 10,
        location: lastShot?.location || '',
        characters: lastShot?.characters || [],
        plot: '',
        visual_prompt: '',
      };

      // 插入到该场景的最后
      const otherShots = prev.filter(s => s.scene_number !== sceneNum);
      return [...otherShots, ...sceneShots, newShot];
    });
  }, []);

  // 删除分镜
  const deleteShot = useCallback((shotId: string) => {
    setEditShots(prev => prev.filter(s => s.shot_id !== shotId));
  }, []);

  // 智能续写
  const handleContinueStory = useCallback(async () => {
    setIsContinuing(true);
    try {
      await onIntervene({ continue_story: true });
    } finally {
      setIsContinuing(false);
    }
  }, [onIntervene]);

  // 按幕 → 场景分组
  const grouped = useMemo(() => {
    const map = new Map<number, Map<number, Shot[]>>();
    if (!shots || !Array.isArray(shots)) return map;
    for (const shot of shots) {
      const act = shot.act ?? 1;
      const sceneNum = shot.scene_number ?? 1;
      if (!map.has(act)) map.set(act, new Map());
      const actMap = map.get(act)!;
      if (!actMap.has(sceneNum)) actMap.set(sceneNum, []);
      actMap.get(sceneNum)!.push(shot);
    }
    return map;
  }, [shots]);

  const hasContent = shots && Array.isArray(shots) && shots.length > 0;

  // 统计
  const totalDuration = useMemo(() => {
    if (!shots || !Array.isArray(shots)) return 0;
    return shots.reduce((s, sh) => s + (sh.duration || 0), 0);
  }, [shots]);

  const startEdit = useCallback(() => {
    const safeShots = Array.isArray(shots) ? shots : [];
    setEditShots(JSON.parse(JSON.stringify(safeShots)));
    setRawJson(JSON.stringify(safeShots, null, 2));
    setIsEditing(true);
    setEditMode('structured');
  }, [shots]);

  const switchEditMode = useCallback((mode: 'structured' | 'raw') => {
    if (mode === 'raw') {
      setRawJson(JSON.stringify(editShots, null, 2));
    } else {
      try { setEditShots(JSON.parse(rawJson)); } catch { /* keep current */ }
    }
    setEditMode(mode);
  }, [editShots, rawJson]);

  const handleSave = useCallback(() => {
    let finalShots: Shot[];
    if (editMode === 'raw') {
      try { finalShots = JSON.parse(rawJson); } catch { finalShots = editShots; }
    } else {
      finalShots = editShots;
    }
    onIntervene({ modified_storyboard: finalShots });
    setIsEditing(false);
  }, [editMode, rawJson, editShots, onIntervene]);

  const cancelEdit = useCallback(() => setIsEditing(false), []);

  const updateShotField = (idx: number, field: keyof Shot, value: any) => {
    setEditShots(prev => prev.map((s, i) => i === idx ? { ...s, [field]: value } : s));
  };

  // 按幕→场景分组(编辑数据)
  const editGrouped = useMemo(() => {
    const map = new Map<number, Map<number, { shot: Shot; globalIdx: number }[]>>();
    editShots.forEach((shot, globalIdx) => {
      const act = shot.act ?? 1;
      const sceneNum = shot.scene_number ?? 1;
      if (!map.has(act)) map.set(act, new Map());
      const actMap = map.get(act)!;
      if (!actMap.has(sceneNum)) actMap.set(sceneNum, []);
      actMap.get(sceneNum)!.push({ shot, globalIdx });
    });
    return map;
  }, [editShots]);

  return (
    <div className="flex flex-col h-full">
      <div className="flex-1 overflow-y-auto p-6">
        {/* 标题 + 编辑模式切换 */}
        <div className="flex items-center justify-between mb-1">
          <h2 className="text-lg font-semibold text-gray-800">分镜设计</h2>
          {isEditing && (
            <div className="flex gap-1 bg-gray-100 rounded-lg p-1 text-xs">
              <button
                onClick={() => switchEditMode('structured')}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md transition-colors ${editMode === 'structured' ? 'bg-white text-blue-600 shadow-sm' : 'text-gray-500 hover:text-gray-700'}`}
              >
                <LayoutList className="w-3.5 h-3.5" />
                结构编辑
              </button>
              <button
                onClick={() => switchEditMode('raw')}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md transition-colors ${editMode === 'raw' ? 'bg-white text-blue-600 shadow-sm' : 'text-gray-500 hover:text-gray-700'}`}
              >
                <Code className="w-3.5 h-3.5" />
                JSON编辑
              </button>
            </div>
          )}
        </div>
        <p className="text-sm text-gray-500 mb-6">
          按场景拆分分镜，每个分镜带时长标签
          {hasContent && (
            <span className="ml-2 text-gray-400">
              共 {shots.length} 个分镜 · 总时长 {totalDuration}s
            </span>
          )}
        </p>

        {/* 运行中 */}
        {state.status === 'running' && (
          <>
            <StageProgress message={state.progressMessage} fallback="正在拆分分镜..." progress={state.progress} color="amber" />
            {/* 增量显示已完成的分镜 */}
            {hasContent && (
              <div className="mt-4 space-y-4">
                {renderShotGroups(grouped)}
              </div>
            )}
          </>
        )}

        {state.error && (
          <div className="text-sm text-red-600 bg-red-50 border border-red-200 p-4 rounded-xl mb-4">{state.error}</div>
        )}

        {/* ===== 查看模式 ===== */}
        {hasContent && !isEditing && state.status !== 'running' && (
          <div className="space-y-4">
            {renderShotGroups(grouped)}
          </div>
        )}

        {/* ===== 结构编辑模式 ===== */}
        {isEditing && editMode === 'structured' && (
          <div className="space-y-4">
            {Array.from(editGrouped.entries()).sort(([a], [b]) => a - b).map(([act, sceneMap]) => (
              <React.Fragment key={act}>
                {/* 幕分隔线：仅多幕时显示 */}
                {editGrouped.size > 1 && (
                  <div className="flex items-center gap-3 pt-2">
                    <div className="flex-1 h-px bg-gradient-to-r from-amber-200 to-transparent" />
                    <span className="px-3 py-1 bg-amber-50 text-amber-600 text-xs font-semibold rounded-full whitespace-nowrap">
                      第{act}幕 — {ACT_NAMES[act] || ''}
                    </span>
                    <div className="flex-1 h-px bg-gradient-to-l from-amber-200 to-transparent" />
                  </div>
                )}

                {Array.from(sceneMap.entries()).sort(([a], [b]) => a - b).map(([sceneNum, items]) => (
                  <div key={sceneNum} className="bg-white border border-gray-200 rounded-xl overflow-hidden">
                    <div className="bg-gray-50 px-4 py-2 border-b border-gray-100 flex items-center gap-2">
                      <Camera className="w-3.5 h-3.5 text-amber-500" />
                      <span className="text-sm font-medium text-gray-700">场景 {sceneNum}</span>
                      <span className="text-xs text-gray-400">{items.length} 个分镜</span>
                      <div className="ml-auto flex items-center gap-1">
                        <button
                          onClick={() => addShot(sceneNum)}
                          className="p-1 text-blue-500 hover:bg-blue-50 rounded"
                          title="添加分镜"
                        >
                          <Plus className="w-4 h-4" />
                        </button>
                        <button
                          onClick={() => deleteScene(sceneNum)}
                          className="p-1 text-red-500 hover:bg-red-50 rounded"
                          title="删除场景"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </div>
                    </div>
                    <div className="divide-y divide-gray-100">
                      {items.map(({ shot, globalIdx }) => (
                        <div key={shot.shot_id} className="p-4 space-y-2">
                          <div className="flex items-center gap-2">
                            <span className="flex items-center justify-center w-6 h-6 rounded-full bg-amber-100 text-amber-700 text-xs font-bold flex-shrink-0">
                              {shot.shot_number}
                            </span>
                            <select
                              value={shot.duration}
                              onChange={e => updateShotField(globalIdx, 'duration', Number(e.target.value))}
                              className="text-xs border border-gray-200 rounded px-2 py-1 text-gray-700"
                            >
                              <option value={5}>5s</option>
                              <option value={10}>10s</option>
                              <option value={15}>15s</option>
                            </select>
                            <div className="flex flex-wrap gap-1 ml-2">
                              {shot.characters.map((c, ci) => (
                                <span key={ci} className="px-2 py-0.5 bg-blue-50 text-blue-600 text-xs rounded-full">{c}</span>
                              ))}
                              <span className="px-2 py-0.5 bg-green-50 text-green-600 text-xs rounded-full">{shot.location}</span>
                            </div>
                          </div>
                          <div>
                            <label className="block text-xs text-gray-500 mb-1">剧情</label>
                            <textarea
                              value={shot.plot}
                              onChange={e => updateShotField(globalIdx, 'plot', e.target.value)}
                              rows={2}
                              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm text-gray-700 focus:ring-2 focus:ring-blue-500/30 outline-none resize-none"
                            />
                          </div>
                          <div>
                            <label className="block text-xs text-gray-500 mb-1">视觉提示词</label>
                            <div className="flex gap-2">
                              <textarea
                                value={shot.visual_prompt}
                                onChange={e => updateShotField(globalIdx, 'visual_prompt', e.target.value)}
                                rows={2}
                                className="flex-1 border border-gray-200 rounded-lg px-3 py-2 text-sm text-gray-700 focus:ring-2 focus:ring-blue-500/30 outline-none resize-none"
                              />
                              <button
                                onClick={() => deleteShot(shot.shot_id)}
                                className="p-2 text-red-400 hover:bg-red-50 rounded self-start"
                                title="删除分镜"
                              >
                                <Trash2 className="w-4 h-4" />
                              </button>
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                    {/* 场景底部添加分镜按钮 */}
                    <div className="px-4 py-2 bg-gray-50 border-t border-gray-100">
                      <button
                        onClick={() => addShot(sceneNum)}
                        className="flex items-center gap-1 text-xs text-blue-500 hover:text-blue-600"
                      >
                        <Plus className="w-3.5 h-3.5" />
                        添加分镜
                      </button>
                    </div>
                  </div>
                ))}
              </React.Fragment>
            ))}

            {/* 添加场景按钮 */}
            <button
              onClick={addScene}
              className="w-full flex items-center justify-center gap-2 py-3 border-2 border-dashed border-gray-300 rounded-xl text-gray-500 hover:border-blue-400 hover:text-blue-500 transition-colors"
            >
              <Plus className="w-5 h-5" />
              添加场景
            </button>

            <div className="flex gap-2 pt-2">
              <button onClick={handleSave} className="flex items-center gap-2 px-4 py-2 bg-blue-500 text-white rounded-lg text-sm font-medium hover:bg-blue-600 transition-colors">
                <Save className="w-4 h-4" />
                保存修改
              </button>
              <button onClick={cancelEdit} className="flex items-center gap-2 px-4 py-2 bg-gray-100 text-gray-600 rounded-lg text-sm hover:bg-gray-200 transition-colors">
                <X className="w-4 h-4" />
                取消
              </button>
            </div>
          </div>
        )}

        {/* ===== JSON编辑模式 ===== */}
        {isEditing && editMode === 'raw' && (
          <div className="space-y-3">
            <textarea
              value={rawJson}
              onChange={e => setRawJson(e.target.value)}
              className="w-full bg-white border border-gray-200 rounded-xl p-4 text-sm text-gray-700 font-mono leading-relaxed resize-none outline-none min-h-[400px] focus:ring-2 focus:ring-blue-500/30"
            />
            <div className="flex gap-2">
              <button onClick={handleSave} className="flex items-center gap-2 px-4 py-2 bg-blue-500 text-white rounded-lg text-sm font-medium hover:bg-blue-600 transition-colors">
                <Save className="w-4 h-4" />
                保存修改
              </button>
              <button onClick={cancelEdit} className="flex items-center gap-2 px-4 py-2 bg-gray-100 text-gray-600 rounded-lg text-sm hover:bg-gray-200 transition-colors">
                <X className="w-4 h-4" />
                取消
              </button>
            </div>
          </div>
        )}

        {state.status === 'pending' && (
          <div className="text-center text-gray-400 text-sm py-20">等待上一阶段完成...</div>
        )}

        {/* 智能续写按钮 - 仅在分镜完成后显示（pending/running 时不显示） */}
        {hasContent && !isEditing && !['pending', 'running'].includes(state.status) && (
          <div className="mt-6 pt-6 border-t border-gray-200">
            <button
              onClick={handleContinueStory}
              disabled={isContinuing}
              className="w-full flex items-center justify-center gap-2 px-4 py-3 bg-gradient-to-r from-purple-500 to-indigo-500 text-white rounded-xl text-sm font-medium hover:from-purple-600 hover:to-indigo-600 transition-colors disabled:opacity-50"
            >
              {isContinuing ? (
                <>
                  <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                  智能续写中...
                </>
              ) : (
                <>
                  <Sparkles className="w-4 h-4" />
                  智能续写
                </>
              )}
            </button>
            <p className="text-xs text-gray-400 text-center mt-2">根据已有剧情，自动续写新的分镜</p>
          </div>
        )}

        {/* 新分镜确认/取消按钮 */}
        {pendingNewShots.length > 0 && !isEditing && (
          <div className="mt-4 p-4 bg-purple-50 border border-purple-200 rounded-xl">
            <div className="flex items-center gap-2 mb-3">
              <Sparkles className="w-4 h-4 text-purple-500" />
              <span className="text-sm font-medium text-purple-700">检测到 {pendingNewShots.length} 个新分镜</span>
            </div>
            <div className="flex gap-3">
              <button
                onClick={handleConfirmNewShots}
                disabled={isContinuing}
                className="flex-1 flex items-center justify-center gap-2 px-4 py-2 bg-purple-500 text-white rounded-lg text-sm font-medium hover:bg-purple-600 transition-colors disabled:opacity-50"
              >
                <Check className="w-4 h-4" />
                保存
              </button>
              <button
                onClick={handleCancelNewShots}
                disabled={isContinuing}
                className="flex-1 flex items-center justify-center gap-2 px-4 py-2 bg-white border border-gray-300 text-gray-700 rounded-lg text-sm font-medium hover:bg-gray-50 transition-colors disabled:opacity-50"
              >
                <X className="w-4 h-4" />
                取消
              </button>
            </div>
          </div>
        )}
      </div>

      {/* 删除场景确认对话框 */}
      {deleteConfirm.show && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-white rounded-xl p-6 max-w-sm w-full mx-4 shadow-xl">
            <div className="flex items-center gap-3 mb-4">
              <div className="w-10 h-10 rounded-full bg-red-100 flex items-center justify-center">
                <AlertTriangle className="w-5 h-5 text-red-500" />
              </div>
              <h3 className="text-lg font-semibold text-gray-800">确认删除场景</h3>
            </div>
            <p className="text-gray-600 mb-4">
              场景 {deleteConfirm.sceneNumber} 中包含已生成的资产：
            </p>
            <div className="bg-gray-50 rounded-lg p-3 mb-4 space-y-1 text-sm">
              <div className="flex justify-between">
                <span className="text-gray-500">参考图：</span>
                <span className="font-medium text-gray-800">{deleteConfirm.assetInfo?.reference_images || 0} 张</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-500">视频片段：</span>
                <span className="font-medium text-gray-800">{deleteConfirm.assetInfo?.videos || 0} 个</span>
              </div>
            </div>
            <p className="text-amber-600 text-sm mb-4">
              删除后这些资产将无法恢复！
            </p>
            <div className="flex gap-3">
              <button
                onClick={cancelDeleteScene}
                className="flex-1 px-4 py-2 border border-gray-200 rounded-lg text-gray-700 hover:bg-gray-50 transition-colors"
              >
                取消
              </button>
              <button
                onClick={confirmDeleteScene}
                className="flex-1 px-4 py-2 bg-red-500 text-white rounded-lg hover:bg-red-600 transition-colors"
              >
                确认删除
              </button>
            </div>
          </div>
        </div>
      )}

      {!isEditing && (
        <StageActions
          status={state.status}
          onConfirm={onConfirm}
          showConfirm={showConfirm}
          onEdit={startEdit}
          onRegenerate={onRegenerate}
          stageId="storyboard"
          hasPendingItems={hasPendingItems}
          hasNextStageStarted={hasNextStageStarted}
          isRunning={isRunning}
        />
      )}
      {isEditing && (
        <StageActions
          status={state.status}
          onConfirm={onConfirm}
          showConfirm={showConfirm}
          onSave={handleSave}
          onRegenerate={onRegenerate}
          stageId="storyboard"
          hasPendingItems={hasPendingItems}
          hasNextStageStarted={hasNextStageStarted}
          isRunning={isRunning}
        />
      )}
    </div>
  );
}

// ─── 分镜分组渲染 ───

function renderShotGroups(grouped: Map<number, Map<number, Shot[]>>) {
  const multiAct = grouped.size > 1;
  return Array.from(grouped.entries()).sort(([a], [b]) => a - b).map(([act, sceneMap]) => (
    <React.Fragment key={act}>
      {/* 幕分隔线：仅多幕时显示 */}
      {multiAct && (
        <div className="flex items-center gap-3 pt-2">
          <div className="flex-1 h-px bg-gradient-to-r from-amber-200 to-transparent" />
          <span className="px-3 py-1 bg-amber-50 text-amber-600 text-xs font-semibold rounded-full whitespace-nowrap">
            第{act}幕 — {ACT_NAMES[act] || ''}
          </span>
          <div className="flex-1 h-px bg-gradient-to-l from-amber-200 to-transparent" />
        </div>
      )}

      {Array.from(sceneMap.entries()).sort(([a], [b]) => a - b).map(([sceneNum, sceneShots]) => (
        <React.Fragment key={sceneNum}>
        <div className="bg-white border border-gray-200 rounded-xl overflow-hidden">
          {/* 场景标题栏 */}
          <div className="bg-gray-50 px-4 py-2 border-b border-gray-100 flex items-center gap-2">
            <Camera className="w-3.5 h-3.5 text-amber-500" />
            <span className="text-sm font-medium text-gray-700">场景 {sceneNum}</span>
            <span className="text-xs text-gray-400">
              {sceneShots.length} 个分镜 · {sceneShots.reduce((s, sh) => s + sh.duration, 0)}s
            </span>
            {sceneShots[0]?.location && (
              <span className="ml-auto px-2 py-0.5 bg-green-50 text-green-600 text-xs rounded-full flex items-center gap-1">
                <MapPin className="w-3 h-3" />
                {sceneShots[0].location}
              </span>
            )}
          </div>
          {/* 分镜列表 */}
          <div className="divide-y divide-gray-100">
            {sceneShots.map(shot => (
              <div key={shot.shot_id} className={`px-4 py-3 hover:bg-gray-50/50 transition-colors ${shot.is_new ? 'bg-purple-50 border-l-4 border-l-purple-400' : ''}`}>
                <div className="flex items-start gap-3">
                  {/* 编号 */}
                  <span className="flex items-center justify-center w-6 h-6 rounded-full bg-amber-100 text-amber-700 text-xs font-bold flex-shrink-0 mt-0.5">
                    {shot.shot_number}
                  </span>
                  <div className="flex-1 min-w-0">
                    {/* 标签行 */}
                    <div className="flex items-center gap-2 mb-1.5">
                      <span className={`inline-flex items-center gap-1 px-2 py-0.5 text-xs font-medium rounded-full ${DURATION_COLORS[shot.duration] || 'bg-gray-100 text-gray-600'}`}>
                        <Clock className="w-3 h-3" />
                        {shot.duration}s
                      </span>
                      {(shot.characters || []).map((c, ci) => (
                        <span key={ci} className="px-2 py-0.5 bg-blue-50 text-blue-600 text-xs rounded-full">{c}</span>
                      ))}
                    </div>
                    {/* 剧情 */}
                    <p className="text-sm text-gray-700 leading-relaxed">{shot.plot}</p>
                    {/* 视觉提示词 */}
                    {shot.visual_prompt && (
                      <p className="text-xs text-gray-400 leading-relaxed mt-1 italic">{shot.visual_prompt}</p>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
        </React.Fragment>
      ))}
    </React.Fragment>
  ));
}
