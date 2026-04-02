'use client';

import React, { useState, useCallback } from 'react';
import { Save, X, Code, LayoutList, Users, MapPin, Film, Sparkles, BookOpen, Lightbulb, Target, User, Crosshair, RefreshCw, Palette } from 'lucide-react';
import type { StageViewProps } from './types';
import StageActions from './StageActions';
import StageProgress from './StageProgress';

/* ─── 类型 ─── */

interface LoglineData {
  logline: string;
  who: string;
  goal: string;
  conflict: string;
  twist: string;
  theme: string;
}

interface ScriptCharacter {
  name: string;
  character_id?: string;
  description: string;
  personality: string[];
  motivation?: string;
  arc_description?: string;
  role: string;
  age?: string;
  species?: string;
  occupation?: string;
}

interface ScriptSetting {
  name: string;
  description: string;
}

interface ScriptScene {
  scene_number: number;
  act?: number;
  location: string;
  characters: string[];
  plot: string;
}

interface ActCompleteData {
  act: number;
  act_name: string;
  characters: ScriptCharacter[];
  settings: ScriptSetting[];
  scenes: ScriptScene[];
}

interface ScriptData {
  title?: string;
  logline?: string;
  genre?: string[];
  synopsis?: string;
  characters?: ScriptCharacter[];
  settings?: ScriptSetting[];
  scenes?: ScriptScene[];
  overall_style?: string;
  mood?: string;
  session_id?: string;
  [key: string]: any;
}

/* ─── 角色色彩 ─── */
const ROLE_COLORS: Record<string, string> = {
  '主角': 'bg-amber-100 text-amber-700',
  'protagonist': 'bg-amber-100 text-amber-700',
  '配角': 'bg-sky-100 text-sky-700',
  'supporting': 'bg-sky-100 text-sky-700',
  '背景': 'bg-gray-100 text-gray-500',
  'background': 'bg-gray-100 text-gray-500',
};

/* ─── Logline 六要素展示卡 ─── */
function LoglineSummaryBar({ logline }: { logline: LoglineData }) {
  const items = [
    { icon: Lightbulb, label: 'Logline', value: logline.logline, color: 'text-amber-600' },
    { icon: User, label: '主角', value: logline.who, color: 'text-blue-600' },
    { icon: Target, label: '目标', value: logline.goal, color: 'text-green-600' },
    { icon: Crosshair, label: '障碍', value: logline.conflict, color: 'text-red-500' },
    { icon: RefreshCw, label: '反转', value: logline.twist, color: 'text-purple-600' },
    { icon: Palette, label: '主题', value: logline.theme, color: 'text-cyan-600' },
  ];
  return (
    <div className="bg-gradient-to-r from-amber-50 to-orange-50 border border-amber-200 rounded-xl p-4">
      <div className="flex items-center gap-2 mb-3">
        <Lightbulb className="w-4 h-4 text-amber-500" />
        <span className="text-xs font-semibold text-amber-700">Logline 核心</span>
      </div>
      <div className="grid grid-cols-6 gap-3">
        {items.map(({ icon: Icon, label, value, color }) => (
          <div key={label} className="min-w-0">
            <div className={`flex items-center gap-1 mb-1 ${color}`}>
              <Icon className="w-3 h-3 flex-shrink-0" />
              <span className="text-[10px] font-semibold">{label}</span>
            </div>
            <p className="text-xs text-gray-600 leading-relaxed break-words">{value}</p>
          </div>
        ))}
      </div>
    </div>
  );
}

export default function ScriptStage({ state, onConfirm, onIntervene, onRegenerate, onSaveSelections, showConfirm, isRunning, hasPendingItems, hasNextStageStarted }: StageViewProps) {
  const data: ScriptData = state.artifact || {};

  const isLoglinePhase = data.phase === 'logline_selection' || data.phase === 'logline_confirm' || data.phase === 'mode_selection';

  const [isEditing, setIsEditing] = useState(false);
  const [editMode, setEditMode] = useState<'structured' | 'raw'>('structured');
  const [editData, setEditData] = useState<ScriptData>({});
  const [rawText, setRawText] = useState('');

  const hasContent = Boolean(data.title || data.characters?.length || data.scenes?.length);

  const startEdit = useCallback(() => {
    setEditData(JSON.parse(JSON.stringify(data)));
    setRawText(JSON.stringify(data, null, 2));
    setIsEditing(true);
    setEditMode('structured');
  }, [data]);

  const switchEditMode = useCallback((mode: 'structured' | 'raw') => {
    if (mode === 'raw') {
      setRawText(JSON.stringify(editData, null, 2));
    } else {
      try { setEditData(JSON.parse(rawText)); } catch { /* keep current */ }
    }
    setEditMode(mode);
  }, [editData, rawText]);

  const handleSave = useCallback(() => {
    let finalData: ScriptData;
    if (editMode === 'raw') {
      try { finalData = JSON.parse(rawText); } catch { return; }
    } else {
      finalData = editData;
    }
    onIntervene({ modified_script: finalData });
    setIsEditing(false);
  }, [editMode, rawText, editData, onIntervene]);

  const cancelEdit = useCallback(() => setIsEditing(false), []);

  /* ─── 编辑辅助 ─── */
  const updateField = (field: string, value: any) => setEditData(prev => ({ ...prev, [field]: value }));

  const updateCharacter = (idx: number, patch: Partial<ScriptCharacter>) => {
    setEditData(prev => ({
      ...prev,
      characters: prev.characters?.map((c, i) => i === idx ? { ...c, ...patch } : c),
    }));
  };

  const updateSetting = (idx: number, patch: Partial<ScriptSetting>) => {
    setEditData(prev => ({
      ...prev,
      settings: prev.settings?.map((s, i) => i === idx ? { ...s, ...patch } : s),
    }));
  };

  const updateScene = (idx: number, patch: Partial<ScriptScene>) => {
    setEditData(prev => ({
      ...prev,
      scenes: prev.scenes?.map((s, i) => i === idx ? { ...s, ...patch } : s),
    }));
  };

  return (
    <div className="flex flex-col h-full">
      <div className="flex-1 overflow-y-auto p-6">

        {/* 标题栏 */}
        <div className="flex items-center justify-between mb-1">
          <h2 className="text-lg font-semibold text-gray-800">剧本生成</h2>
          {isEditing && (
            <div className="flex gap-1 bg-gray-100 rounded-lg p-1 text-xs">
              <button onClick={() => switchEditMode('structured')}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md transition-colors ${editMode === 'structured' ? 'bg-white text-blue-600 shadow-sm' : 'text-gray-500 hover:text-gray-700'}`}>
                <LayoutList className="w-3.5 h-3.5" />结构编辑
              </button>
              <button onClick={() => switchEditMode('raw')}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md transition-colors ${editMode === 'raw' ? 'bg-white text-blue-600 shadow-sm' : 'text-gray-500 hover:text-gray-700'}`}>
                <Code className="w-3.5 h-3.5" />JSON编辑
              </button>
            </div>
          )}
        </div>
        <p className="text-sm text-gray-500 mb-6">多轮 LLM 交互，生成结构化剧本数据</p>

        {/* 运行中 - 进度条 & 已选 Logline & 增量生成结果 */}
        {state.status === 'running' && (
          <>
            {data.selected_logline && (
              <div className="mb-4">
                <LoglineSummaryBar logline={data.selected_logline as LoglineData} />
              </div>
            )}

            {/* 节拍表展示 */}
            {data.beat_sheet && (
              <div className="mb-4">
                <div className="flex items-center gap-2 mb-2">
                  <BookOpen className="w-4 h-4 text-orange-500" />
                  <h3 className="text-sm font-semibold text-gray-700">节拍表 (Beat Sheet)</h3>
                </div>
                <div className="bg-white border border-gray-200 rounded-xl p-4">
                  <pre className="text-sm text-gray-600 leading-relaxed whitespace-pre-wrap font-sans">{data.beat_sheet as string}</pre>
                </div>
              </div>
            )}

            {/* 逐幕完成的分场结果 */}
            {data.completed_acts && (data.completed_acts as ActCompleteData[]).length > 0 && (
              <div className="mb-4 space-y-4">
                {(data.completed_acts as ActCompleteData[]).map((actData) => (
                  <div key={actData.act}>
                    {/* 幕分隔线 */}
                    <div className="flex items-center gap-3 mb-3">
                      <div className="flex-1 h-px bg-gradient-to-r from-purple-200 to-transparent" />
                      <span className="px-3 py-1 bg-purple-50 text-purple-600 text-xs font-semibold rounded-full whitespace-nowrap">
                        第{actData.act}幕 — {actData.act_name}
                      </span>
                      <div className="flex-1 h-px bg-gradient-to-l from-purple-200 to-transparent" />
                    </div>

                    {/* 本幕场景 */}
                    <div className="space-y-2">
                      {actData.scenes.map((sc, i) => (
                        <div key={i} className="bg-white border border-gray-200 rounded-xl p-4 hover:shadow-sm transition-shadow">
                          <div className="flex items-center gap-3 mb-2">
                            <span className="flex items-center justify-center w-7 h-7 rounded-full bg-purple-100 text-purple-700 text-xs font-bold flex-shrink-0">{sc.scene_number}</span>
                            <span className="px-2 py-0.5 bg-green-50 text-green-600 text-xs rounded-full">{sc.location}</span>
                            <div className="flex flex-wrap gap-1">
                              {(sc.characters || []).map((c: any, ci: number) => (
                                <span key={ci} className="px-2 py-0.5 bg-blue-50 text-blue-600 text-xs rounded-full">{c}</span>
                              ))}
                            </div>
                          </div>
                          <p className="text-sm text-gray-600 leading-relaxed pl-10">{sc.plot}</p>
                        </div>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            )}

            <StageProgress message={state.progressMessage} fallback="正在生成剧本..." progress={state.progress} color="blue" />
          </>
        )}

        {/* 错误 */}
        {state.error && (
          <div className="text-sm text-red-600 bg-red-50 border border-red-200 p-4 rounded-xl mb-4">{state.error}</div>
        )}

        {/* ===== Logline 选择/确认阶段 ===== */}
        {isLoglinePhase && state.status === 'waiting' && (
          <div className="space-y-4">
            {/* 3 个 Logline 选项卡 */}
            {data.phase === 'logline_selection' && data.logline_options && (
              <>
                <div className="flex items-center gap-2 mb-2">
                  <Lightbulb className="w-4 h-4 text-amber-500" />
                  <h3 className="text-sm font-semibold text-gray-700">选择一个 Logline 方案</h3>
                  <span className="text-xs text-gray-400">点击卡片以选择</span>
                </div>
                <div className="grid grid-cols-3 gap-3">
                  {(data.logline_options as LoglineData[]).map((opt, i) => (
                    <button
                      key={i}
                      onClick={() => onIntervene({ selected_logline: opt })}
                      className="text-left p-4 bg-white border border-gray-200 rounded-xl hover:border-blue-400 hover:shadow-md transition-all group cursor-pointer"
                    >
                      <p className="text-sm font-medium text-gray-800 group-hover:text-blue-600 mb-3 leading-relaxed">
                        {opt.logline}
                      </p>
                      <div className="space-y-1.5 text-xs text-gray-500">
                        <p><span className="text-gray-600 font-medium">主角:</span> {opt.who}</p>
                        <p><span className="text-gray-600 font-medium">目标:</span> {opt.goal}</p>
                        <p><span className="text-gray-600 font-medium">障碍:</span> {opt.conflict}</p>
                        <p><span className="text-gray-600 font-medium">反转:</span> {opt.twist}</p>
                        <p><span className="text-gray-600 font-medium">主题:</span> {opt.theme}</p>
                      </div>
                    </button>
                  ))}
                </div>
              </>
            )}

            {/* 单个 Logline 确认 */}
            {data.phase === 'logline_confirm' && data.logline_summary && (
              <>
                <div className="flex items-center gap-2 mb-2">
                  <Lightbulb className="w-4 h-4 text-amber-500" />
                  <h3 className="text-sm font-semibold text-gray-700">Logline 提取结果</h3>
                </div>
                <LoglineSummaryBar logline={data.logline_summary as LoglineData} />
                <div className="flex justify-center pt-2">
                  <button
                    onClick={() => onIntervene({ selected_logline: data.logline_summary })}
                    className="flex items-center gap-2 px-5 py-2.5 bg-blue-500 text-white rounded-lg text-sm font-medium hover:bg-blue-600 transition-colors"
                  >
                    <Sparkles className="w-4 h-4" />
                    确认 Logline 并生成剧本
                  </button>
                </div>
              </>
            )}

            {/* 创作模式选择 */}
            {data.phase === 'mode_selection' && (
              <>
                {data.selected_logline && (
                  <div className="mb-4">
                    <LoglineSummaryBar logline={data.selected_logline as LoglineData} />
                  </div>
                )}
                <div className="flex items-center gap-2 mb-3">
                  <Film className="w-4 h-4 text-purple-500" />
                  <h3 className="text-sm font-semibold text-gray-700">选择创作模式</h3>
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <button
                    onClick={() => onIntervene({ selected_mode: 'movie' })}
                    className="text-left p-5 bg-white border-2 border-gray-200 rounded-xl hover:border-purple-400 hover:shadow-lg transition-all group cursor-pointer"
                  >
                    <div className="flex items-center gap-2 mb-3">
                      <span className="flex items-center justify-center w-10 h-10 rounded-xl bg-purple-100 text-purple-600 text-lg">🎬</span>
                      <span className="text-base font-semibold text-gray-800 group-hover:text-purple-600">电影模式</span>
                    </div>
                    <p className="text-sm text-gray-600 leading-relaxed mb-3">
                      按照四幕结构生成完整情节，叙事连贯丰富，有完整的起承转合。
                    </p>
                    <div className="flex flex-wrap gap-1.5">
                      <span className="px-2 py-0.5 bg-purple-50 text-purple-500 text-xs rounded-full">四幕结构</span>
                      <span className="px-2 py-0.5 bg-purple-50 text-purple-500 text-xs rounded-full">叙事完整</span>
                      <span className="px-2 py-0.5 bg-purple-50 text-purple-500 text-xs rounded-full">情节丰富</span>
                    </div>
                  </button>
                  <button
                    onClick={() => onIntervene({ selected_mode: 'micro' })}
                    className="text-left p-5 bg-white border-2 border-gray-200 rounded-xl hover:border-cyan-400 hover:shadow-lg transition-all group cursor-pointer"
                  >
                    <div className="flex items-center gap-2 mb-3">
                      <span className="flex items-center justify-center w-10 h-10 rounded-xl bg-cyan-100 text-cyan-600 text-lg">🎞️</span>
                      <span className="text-base font-semibold text-gray-800 group-hover:text-cyan-600">微电影模式</span>
                    </div>
                    <p className="text-sm text-gray-600 leading-relaxed mb-3">
                      所有内容生成在一幕内，叙事节奏快，情节紧凑，适合短片创作。
                    </p>
                    <div className="flex flex-wrap gap-1.5">
                      <span className="px-2 py-0.5 bg-cyan-50 text-cyan-500 text-xs rounded-full">单幕结构</span>
                      <span className="px-2 py-0.5 bg-cyan-50 text-cyan-500 text-xs rounded-full">节奏紧凑</span>
                      <span className="px-2 py-0.5 bg-cyan-50 text-cyan-500 text-xs rounded-full">3-6场景</span>
                    </div>
                  </button>
                </div>
              </>
            )}
          </div>
        )}

        {/* ===== 查看模式 ===== */}
        {hasContent && !isEditing && (
          <div className="space-y-8">

            {/* Logline 六要素摘要 */}
            {data.logline_data && (
              <LoglineSummaryBar logline={data.logline_data as LoglineData} />
            )}

            {/* 标题 / Logline / 标签 */}
            {data.title && (
              <section className="bg-white border border-gray-200 rounded-xl p-5">
                <h3 className="text-xl font-bold text-gray-800 mb-2">{data.title}</h3>
                {data.logline && <p className="text-sm text-gray-500 mb-3">{data.logline}</p>}
                <div className="flex flex-wrap gap-1.5">
                  {data.genre?.map((g, i) => (
                    <span key={i} className="px-2.5 py-0.5 bg-violet-50 text-violet-600 text-xs rounded-full font-medium">{g}</span>
                  ))}
                  {data.mood && <span className="px-2.5 py-0.5 bg-pink-50 text-pink-600 text-xs rounded-full font-medium">{data.mood}</span>}
                  {data.overall_style && <span className="px-2.5 py-0.5 bg-cyan-50 text-cyan-600 text-xs rounded-full font-medium">{data.overall_style}</span>}
                </div>
              </section>
            )}

            {/* 故事梗概 */}
            {data.synopsis && (
              <section>
                <div className="flex items-center gap-2 mb-3">
                  <BookOpen className="w-4 h-4 text-orange-500" />
                  <h3 className="text-sm font-semibold text-gray-700">故事梗概</h3>
                </div>
                <div className="bg-white border border-gray-200 rounded-xl p-5">
                  <p className="text-sm text-gray-600 leading-relaxed">{data.synopsis}</p>
                </div>
              </section>
            )}

            {/* 角色 */}
            {data.characters && data.characters.length > 0 && (
              <section>
                <div className="flex items-center gap-2 mb-3">
                  <Users className="w-4 h-4 text-blue-500" />
                  <h3 className="text-sm font-semibold text-gray-700">角色 ({data.characters.length})</h3>
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                  {data.characters.map((c, i) => (
                    <div key={i} className="bg-white border border-gray-200 rounded-xl p-4 hover:shadow-sm transition-shadow">
                      <div className="flex items-center gap-2 mb-2">
                        <span className="font-medium text-gray-800">{c.name}</span>
                        <span className={`px-1.5 py-0.5 text-[10px] rounded ${ROLE_COLORS[c.role] || 'bg-gray-100 text-gray-500'}`}>{c.role}</span>
                        {c.species && c.species !== '人类' && c.species !== 'human' && (
                          <span className="px-1.5 py-0.5 bg-emerald-50 text-emerald-600 text-[10px] rounded">{c.species}</span>
                        )}
                      </div>
                      <p className="text-sm text-gray-500 leading-relaxed mb-2">{c.description}</p>
                      {c.personality && (
                        <div className="flex flex-wrap gap-1 mb-2">
                          {(Array.isArray(c.personality) ? c.personality : String(c.personality).split(/[,，]/)).map((p: string, pi: number) => (
                            <span key={pi} className="px-1.5 py-0.5 bg-blue-50 text-blue-500 text-[10px] rounded">{p.trim()}</span>
                          ))}
                        </div>
                      )}
                      {c.motivation && <p className="text-xs text-gray-400"><span className="text-gray-500 font-medium">动机:</span> {c.motivation}</p>}
                      {c.arc_description && <p className="text-xs text-gray-400"><span className="text-gray-500 font-medium">成长:</span> {c.arc_description}</p>}
                    </div>
                  ))}
                </div>
              </section>
            )}

            {/* 场景设置 */}
            {data.settings && data.settings.length > 0 && (
              <section>
                <div className="flex items-center gap-2 mb-3">
                  <MapPin className="w-4 h-4 text-green-500" />
                  <h3 className="text-sm font-semibold text-gray-700">场景 ({data.settings.length})</h3>
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                  {data.settings.map((s, i) => (
                    <div key={i} className="bg-white border border-gray-200 rounded-xl p-4 hover:shadow-sm transition-shadow">
                      <div className="font-medium text-gray-800 mb-1">{s.name}</div>
                      <p className="text-sm text-gray-500 leading-relaxed">{s.description}</p>
                    </div>
                  ))}
                </div>
              </section>
            )}

            {/* 故事线 */}
            {data.scenes && data.scenes.length > 0 && (
              <section>
                <div className="flex items-center gap-2 mb-3">
                  <Film className="w-4 h-4 text-purple-500" />
                  <h3 className="text-sm font-semibold text-gray-700">故事线 ({data.scenes.length} 场)</h3>
                </div>
                <div className="space-y-3">
                  {data.scenes.map((sc, i) => {
                    // 幕分隔线：当场景有 act 字段，且是第一场或与上一场不同幕时显示
                    const showActSep = sc.act != null && (i === 0 || data.scenes![i - 1].act !== sc.act);
                    const actNames: Record<number, string> = { 1: '激励事件', 2: '进入新世界', 3: '灵魂黑夜', 4: '高潮决战' };
                    return (
                      <React.Fragment key={i}>
                        {showActSep && (
                          <div className="flex items-center gap-3 pt-2">
                            <div className="flex-1 h-px bg-gradient-to-r from-purple-200 to-transparent" />
                            <span className="px-3 py-1 bg-purple-50 text-purple-600 text-xs font-semibold rounded-full whitespace-nowrap">
                              第{sc.act}幕 — {actNames[sc.act!] || ''}
                            </span>
                            <div className="flex-1 h-px bg-gradient-to-l from-purple-200 to-transparent" />
                          </div>
                        )}
                        <div className="bg-white border border-gray-200 rounded-xl p-4 hover:shadow-sm transition-shadow">
                          <div className="flex items-center gap-3 mb-2">
                            <span className="flex items-center justify-center w-7 h-7 rounded-full bg-purple-100 text-purple-700 text-xs font-bold flex-shrink-0">{sc.scene_number}</span>
                            <span className="px-2 py-0.5 bg-green-50 text-green-600 text-xs rounded-full">{sc.location}</span>
                            <div className="flex flex-wrap gap-1">
                              {(sc.characters || []).map((c: any, ci: number) => (
                                <span key={ci} className="px-2 py-0.5 bg-blue-50 text-blue-600 text-xs rounded-full">{c}</span>
                              ))}
                            </div>
                          </div>
                          <p className="text-sm text-gray-600 leading-relaxed pl-10">{sc.plot}</p>
                        </div>
                      </React.Fragment>
                    );
                  })}
                </div>
              </section>
            )}
          </div>
        )}

        {/* ===== 结构编辑模式 ===== */}
        {isEditing && editMode === 'structured' && (
          <div className="space-y-6">

            {/* 基础信息 */}
            <section className="bg-white border border-gray-200 rounded-xl p-4 space-y-3">
              <h4 className="text-sm font-semibold text-gray-700 flex items-center gap-2"><Sparkles className="w-3.5 h-3.5 text-violet-500" />基本信息</h4>
              <div className="grid grid-cols-2 gap-3">
                <label className="flex flex-col gap-1 text-xs">
                  <span className="text-gray-500 font-medium">标题</span>
                  <input type="text" value={editData.title || ''} onChange={e => updateField('title', e.target.value)}
                    className="border border-gray-200 rounded-lg px-3 py-2 text-sm text-gray-700 focus:ring-2 focus:ring-blue-500/30 outline-none" />
                </label>
                <label className="flex flex-col gap-1 text-xs">
                  <span className="text-gray-500 font-medium">情绪基调</span>
                  <input type="text" value={editData.mood || ''} onChange={e => updateField('mood', e.target.value)}
                    className="border border-gray-200 rounded-lg px-3 py-2 text-sm text-gray-700 focus:ring-2 focus:ring-blue-500/30 outline-none" />
                </label>
              </div>
              <label className="flex flex-col gap-1 text-xs">
                <span className="text-gray-500 font-medium">Logline</span>
                <input type="text" value={editData.logline || ''} onChange={e => updateField('logline', e.target.value)}
                  className="border border-gray-200 rounded-lg px-3 py-2 text-sm text-gray-700 focus:ring-2 focus:ring-blue-500/30 outline-none" />
              </label>
              <label className="flex flex-col gap-1 text-xs">
                <span className="text-gray-500 font-medium">故事梗概</span>
                <textarea value={editData.synopsis || ''} onChange={e => updateField('synopsis', e.target.value)} rows={3}
                  className="border border-gray-200 rounded-lg px-3 py-2 text-sm text-gray-700 focus:ring-2 focus:ring-blue-500/30 outline-none resize-none" />
              </label>
            </section>

            {/* 角色编辑 */}
            {editData.characters && editData.characters.length > 0 && (
              <section>
                <div className="flex items-center gap-2 mb-3"><Users className="w-4 h-4 text-blue-500" /><h4 className="text-sm font-semibold text-gray-700">角色</h4></div>
                <div className="space-y-3">
                  {editData.characters.map((c, i) => (
                    <div key={i} className="bg-white border border-gray-200 rounded-xl p-4 space-y-2">
                      <div className="flex gap-3">
                        <label className="flex flex-col gap-1 text-xs flex-1"><span className="text-gray-500 font-medium">名字</span>
                          <input type="text" value={c.name} onChange={e => updateCharacter(i, { name: e.target.value })}
                            className="border border-gray-200 rounded-lg px-3 py-2 text-sm text-gray-700 focus:ring-2 focus:ring-blue-500/30 outline-none" /></label>
                        <label className="flex flex-col gap-1 text-xs w-24"><span className="text-gray-500 font-medium">角色</span>
                          <select value={c.role} onChange={e => updateCharacter(i, { role: e.target.value })}
                            className="border border-gray-200 rounded-lg px-2 py-2 text-sm text-gray-700 outline-none">
                            <option value="主角">主角</option><option value="配角">配角</option><option value="背景">背景</option>
                          </select></label>
                      </div>
                      <label className="flex flex-col gap-1 text-xs"><span className="text-gray-500 font-medium">外貌描述</span>
                        <textarea value={c.description} onChange={e => updateCharacter(i, { description: e.target.value })} rows={2}
                          className="border border-gray-200 rounded-lg px-3 py-2 text-sm text-gray-700 focus:ring-2 focus:ring-blue-500/30 outline-none resize-none" /></label>
                      <label className="flex flex-col gap-1 text-xs"><span className="text-gray-500 font-medium">动机</span>
                        <input type="text" value={c.motivation || ''} onChange={e => updateCharacter(i, { motivation: e.target.value })}
                          className="border border-gray-200 rounded-lg px-3 py-2 text-sm text-gray-700 focus:ring-2 focus:ring-blue-500/30 outline-none" /></label>
                    </div>
                  ))}
                </div>
              </section>
            )}

            {/* 场景编辑 */}
            {editData.settings && editData.settings.length > 0 && (
              <section>
                <div className="flex items-center gap-2 mb-3"><MapPin className="w-4 h-4 text-green-500" /><h4 className="text-sm font-semibold text-gray-700">场景</h4></div>
                <div className="space-y-3">
                  {editData.settings.map((s, i) => (
                    <div key={i} className="bg-white border border-gray-200 rounded-xl p-4">
                      <label className="block text-xs text-gray-500 font-medium mb-1.5">{s.name}</label>
                      <textarea value={s.description} onChange={e => updateSetting(i, { description: e.target.value })} rows={2}
                        className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm text-gray-700 focus:ring-2 focus:ring-blue-500/30 outline-none resize-none" />
                    </div>
                  ))}
                </div>
              </section>
            )}

            {/* 故事线编辑 */}
            {editData.scenes && editData.scenes.length > 0 && (
              <section>
                <div className="flex items-center gap-2 mb-3"><Film className="w-4 h-4 text-purple-500" /><h4 className="text-sm font-semibold text-gray-700">故事线</h4></div>
                <div className="space-y-3">
                  {editData.scenes.map((sc, i) => (
                    <div key={i} className="bg-white border border-gray-200 rounded-xl p-4">
                      <div className="flex items-center gap-3 mb-2">
                        <span className="flex items-center justify-center w-7 h-7 rounded-full bg-purple-100 text-purple-700 text-xs font-bold flex-shrink-0">{sc.scene_number}</span>
                        <span className="text-xs text-green-600">{sc.location}</span>
                        <div className="flex flex-wrap gap-1">
                          {sc.characters.map((c, ci) => <span key={ci} className="px-2 py-0.5 bg-blue-50 text-blue-600 text-[10px] rounded-full">{c}</span>)}
                        </div>
                      </div>
                      <textarea value={sc.plot} onChange={e => updateScene(i, { plot: e.target.value })} rows={3}
                        className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm text-gray-700 focus:ring-2 focus:ring-blue-500/30 outline-none resize-none" />
                    </div>
                  ))}
                </div>
              </section>
            )}

            <div className="flex gap-2 pt-2">
              <button onClick={handleSave} className="flex items-center gap-2 px-4 py-2 bg-blue-500 text-white rounded-lg text-sm font-medium hover:bg-blue-600 transition-colors">
                <Save className="w-4 h-4" />保存修改</button>
              <button onClick={cancelEdit} className="flex items-center gap-2 px-4 py-2 bg-gray-100 text-gray-600 rounded-lg text-sm hover:bg-gray-200 transition-colors">
                <X className="w-4 h-4" />取消</button>
            </div>
          </div>
        )}

        {/* ===== JSON编辑模式 ===== */}
        {isEditing && editMode === 'raw' && (
          <div className="space-y-3">
            <textarea value={rawText} onChange={e => setRawText(e.target.value)}
              className="w-full bg-white border border-gray-200 rounded-xl p-4 text-sm text-gray-700 font-mono leading-relaxed resize-none outline-none min-h-[400px] focus:ring-2 focus:ring-blue-500/30" />
            <div className="flex gap-2">
              <button onClick={handleSave} className="flex items-center gap-2 px-4 py-2 bg-blue-500 text-white rounded-lg text-sm font-medium hover:bg-blue-600 transition-colors">
                <Save className="w-4 h-4" />保存修改</button>
              <button onClick={cancelEdit} className="flex items-center gap-2 px-4 py-2 bg-gray-100 text-gray-600 rounded-lg text-sm hover:bg-gray-200 transition-colors">
                <X className="w-4 h-4" />取消</button>
            </div>
          </div>
        )}

        {/* 等待状态 */}
        {state.status === 'pending' && (
          <div className="text-center text-gray-400 text-sm py-20">等待生成...</div>
        )}
      </div>

      {!isEditing && !isLoglinePhase && (
        <StageActions
          status={state.status}
          onConfirm={onConfirm}
          showConfirm={showConfirm}
          onEdit={startEdit}
          onRegenerate={onRegenerate}
          stageId="script_generation"
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
          stageId="script_generation"
          hasPendingItems={hasPendingItems}
          hasNextStageStarted={hasNextStageStarted}
          isRunning={isRunning}
        />
      )}
    </div>
  );
}
