'use client';

import React, { useState, useRef, useEffect, useCallback } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import {
  startProject,
  executeStage,
  parseStreamEvents,
  getProjectStatus,
  getProjectStatusFromDisk,
  continueWorkflow,
  stopProject,
  intervene,
  getArtifact,
  fetchSessions,
  updateModels,
  deleteSession,
  saveSelections,
} from '@/lib/workflowApi';
import TopBar, { STAGES, type ModelConfig } from './TopBar';
import HomePage, { type ProjectParams } from './HomePage';
import {
  ScriptStage,
  CharacterStage,
  StoryboardStage,
  ReferenceStage,
  VideoStage,
  PostProductionStage,
  type StageState,
  type StageStatus,
} from './stages';

const STAGE_ORDER: string[] = STAGES.map(s => s.id);

const STAGE_COMPONENTS: Record<string, React.ComponentType<any>> = {
  script_generation: ScriptStage,
  character_design: CharacterStage,
  storyboard: StoryboardStage,
  reference_generation: ReferenceStage,
  video_generation: VideoStage,
  post_production: PostProductionStage,
};

interface HistoryItem {
  id: string;
  idea: string;
  style?: string;
  date: string;
  status: string;
  stages?: string[];  // stages_completed 列表
}

function initStageStates(): Record<string, StageState> {
  const states: Record<string, StageState> = {};
  for (const s of STAGE_ORDER) {
    states[s] = {
      status: 'pending',
      progress: 0,
      progressMessage: '',
      artifact: null,
      error: null,
    };
  }
  return states;
}

export default function WorkflowPanel() {
  const router = useRouter();
  const searchParams = useSearchParams();

  const [sessionId, setSessionId] = useState<string | null>(null);
  const [activeStage, setActiveStage] = useState<string | null>(null);
  const [stageStates, setStageStates] = useState<Record<string, StageState>>(initStageStates());
  const [isRunning, setIsRunning] = useState(false);
  const [history, setHistory] = useState<HistoryItem[]>([]);
  const [projectParams, setProjectParams] = useState<ProjectParams | null>(null);
  const [autoMode, setAutoMode] = useState(false);
  const [videoSound, setVideoSound] = useState('on');
  const [videoShotType, setVideoShotType] = useState('multi');
  // 用于顶栏流程图状态判断
  const [currentStageFromSession, setCurrentStageFromSession] = useState<string | null>(null);
  const [completedStagesFromSession, setCompletedStagesFromSession] = useState<string[]>([]);

  const abortRef = useRef<AbortController | null>(null);
  const stoppedRef = useRef(false);
  const pollRef = useRef<string | null>(null);

  // 清理轮询
  useEffect(() => {
    return () => { pollRef.current = null; };
  }, []);

  // 轮询等待后端阶段完成（从 sessions json 读取，支持后端重启后恢复）
  const pollForCompletion = useCallback(async (sid: string, stageId: string) => {
    const key = `${sid}:${stageId}`;
    pollRef.current = key;
    for (let i = 0; i < 300; i++) {  // 增加轮询次数（最多10分钟）
      await new Promise(r => setTimeout(r, 2000));
      if (pollRef.current !== key) return;
      try {
        // 优先从 sessions json 读取（支持后端重启后恢复）
        let status: any;
        try {
          status = await getProjectStatusFromDisk(sid);
        } catch {
          // 如果从磁盘读取失败，回退到内存状态
          status = await getProjectStatus(sid);
        }
        if (pollRef.current !== key) return;
        const done = status.stages_completed || [];
        if (done.includes(stageId)) {
          const isWait = status.status === 'waiting_in_stage' && status.current_stage === stageId;
          let artifact = null;
          try { artifact = (await getArtifact(sid, stageId)).artifact; } catch {}
          updateStageState(stageId, {
            status: isWait ? 'waiting' : 'completed',
            progress: 100,
            progressMessage: isWait ? '等待确认' : '已完成',
            artifact,
          });
          pollRef.current = null;
          return;
        }
        if (status.status === 'error') {
          updateStageState(stageId, {
            status: 'error',
            error: status.error || '执行出错',
            progressMessage: '执行失败',
          });
          pollRef.current = null;
          return;
        }
        // 如果后端状态不再是 running，提前停止轮询（比如变成了 waiting_intervention 或已完成）
        if (status.status !== 'running') {
          pollRef.current = null;
          return;
        }
        // 更新进度信息（从 artifacts 中读取）
        const artifacts = status.artifacts || {};
        const currentArtifact = artifacts[stageId];
        const update: Partial<StageState> = {};

        // 始终设置状态为 running（如果尚未设置）
        const currentState = stageStates[stageId];
        if (!currentState || currentState.status === 'pending') {
          update.status = 'running';
          update.progress = 0;
        }

        if (currentArtifact) {
          // 检查是否有已生成的参考图/视频
          const hasProgress = currentArtifact.scenes?.some((s: any) => s.versions?.length > 0) ||
                             currentArtifact.clips?.some((c: any) => c.versions?.length > 0) ||
                             currentArtifact.characters?.length > 0 ||
                             currentArtifact.shots?.length > 0;
          if (hasProgress) {
            update.progressMessage = '执行中...（已生成部分资源）';
          } else {
            update.progressMessage = '执行中...';
          }
        } else {
          update.progressMessage = '执行中...';
        }

        if (Object.keys(update).length > 0) {
          updateStageState(stageId, update);
        }
      } catch { /* retry */ }
    }
  }, []);

  // 检查 URL 参数，加载指定的 session 和阶段
  useEffect(() => {
    const sessionParam = searchParams.get('session');
    const stageParam = searchParams.get('stage');
    if (sessionParam) {
      // 保存目标阶段，等会话加载完成后再设置
      const targetStage = stageParam && STAGE_ORDER.includes(stageParam) ? stageParam : null;
      handleResumeProject(sessionParam, targetStage);
    }
  }, [searchParams]);

  // 页面加载时从后端获取历史记录
  useEffect(() => {
    fetchSessions()
      .then(sessions => {
        setHistory(
          sessions.map((s: any) => ({
            id: s.id,
            idea: (s.idea || 'Untitled').slice(0, 60),
            style: s.style || '',
            date: s.date
              ? new Date(s.date * 1000).toLocaleDateString('zh-CN')
              : '',
            status: (s.stages?.length || 0) > 0 ? 'partial' : 'new',
            stages: s.stages || [],
          }))
        );
      })
      .catch(() => {});
  }, []);

  const updateStageState = (stageId: string, update: Partial<StageState>) => {
    setStageStates(prev => ({
      ...prev,
      [stageId]: { ...prev[stageId], ...update },
    }));
  };

  // ── 停止执行 ──
  const handleStop = async () => {
    stoppedRef.current = true;
    // 1. 断开前端 SSE 流
    if (abortRef.current) {
      abortRef.current.abort();
      abortRef.current = null;
    }
    // 2. 通知后端停止
    if (sessionId) {
      try { await stopProject(sessionId); } catch { /* ignore */ }
    }
    setIsRunning(false);
    // 3. 将所有 running 阶段标记为 stopped，保留已有的 artifact
    setStageStates(prev => {
      const next = { ...prev };
      for (const s of STAGE_ORDER) {
        if (next[s]?.status === 'running') {
          // 如果已有 artifact 数据（如部分已生成的视频片段），保留为 waiting 状态以便用户操作
          const hasArtifact = next[s]?.artifact &&
            (Array.isArray(next[s].artifact?.clips) ? next[s].artifact.clips.some((c: any) => c.status === 'done') :
             Array.isArray(next[s].artifact?.images) ? next[s].artifact.images.some((c: any) => c.status === 'done') :
             false);
          if (hasArtifact) {
            next[s] = { ...next[s], status: 'waiting', error: null, progressMessage: '已停止（保留已完成内容）' };
          } else {
            next[s] = { ...next[s], status: 'error', error: '已手动停止', progressMessage: '已停止' };
          }
        }
      }
      return next;
    });
    // 4. 尝试从后端获取最新 artifact（后端可能已保存部分结果）
    if (sessionId) {
      setTimeout(async () => {
        for (const s of STAGE_ORDER) {
          try {
            const artResult = await getArtifact(sessionId, s);
            if (artResult?.artifact) {
              setStageStates(prev => {
                const cur = prev[s];
                if (!cur || cur.status === 'completed') return prev;
                // 检查 artifact 是否含有效内容
                const clips = artResult.artifact?.clips;
                const images = artResult.artifact?.images;
                const hasDone = (Array.isArray(clips) && clips.some((c: any) => c.status === 'done'))
                    || (Array.isArray(images) && images.some((c: any) => c.status === 'done'));
                if (hasDone) {
                  return { ...prev, [s]: { ...cur, status: 'waiting', artifact: artResult.artifact, error: null, progressMessage: '已停止（保留已完成内容）' } };
                }
                return prev;
              });
            }
          } catch { /* 该阶段无 artifact，跳过 */ }
        }
      }, 500);
    }
  };

  // ── 执行单个阶段 ──
  const runStage = async (sid: string, stageId: string, inputData: Record<string, any>) => {
    if (stoppedRef.current) throw new Error('Stopped');
    updateStageState(stageId, { status: 'running', progress: 0, progressMessage: '启动中...', error: null });
    setActiveStage(stageId);

    const controller = new AbortController();
    abortRef.current = controller;

    try {
      const response = await executeStage(sid, stageId, inputData, controller.signal);

      for await (const event of parseStreamEvents(response)) {
        if (event.type === 'progress') {
          updateStageState(stageId, {
            progress: event.percent || 0,
            progressMessage: event.message || '',
          });
          // 处理素材预览和逐个完成事件
          if (event.data?.assets_preview) {
            updateStageState(stageId, { artifact: event.data.assets_preview });
          }
          if (event.data?.asset_complete) {
            const assetUpdate = event.data.asset_complete;
            setStageStates(prev => {
              const prevArt = prev[stageId]?.artifact;
              if (!prevArt) return prev;
              const key = assetUpdate.type as string;
              const items = [...(prevArt[key] || [])];
              const idx = items.findIndex((item: any) => item.id === assetUpdate.id);
              if (idx >= 0) {
                items[idx] = {
                  ...items[idx],
                  status: assetUpdate.status,
                  selected: assetUpdate.selected || items[idx].selected,
                  versions: assetUpdate.versions || items[idx].versions,
                };
              }
              return {
                ...prev,
                [stageId]: { ...prev[stageId], artifact: { ...prevArt, [key]: items } },
              };
            });
          }
          // 处理剧本逐幕增量事件
          if (event.data?.beat_sheet) {
            setStageStates(prev => {
              const prevArt = prev[stageId]?.artifact || {};
              return {
                ...prev,
                [stageId]: {
                  ...prev[stageId],
                  artifact: { ...prevArt, phase: 'generating', beat_sheet: event.data.beat_sheet },
                },
              };
            });
          }
          if (event.data?.act_complete) {
            const actData = event.data.act_complete;
            setStageStates(prev => {
              const prevArt = prev[stageId]?.artifact || {};
              const prevActs = prevArt.completed_acts || [];
              return {
                ...prev,
                [stageId]: {
                  ...prev[stageId],
                  artifact: {
                    ...prevArt,
                    phase: 'generating',
                    completed_acts: [...prevActs, actData],
                  },
                },
              };
            });
          }
          // 处理分镜逐场完成事件
          if (event.data?.scene_shots_complete) {
            const sceneData = event.data.scene_shots_complete;
            setStageStates(prev => {
              const prevArt = prev[stageId]?.artifact || {};
              const prevShots = prevArt.shots || [];
              return {
                ...prev,
                [stageId]: {
                  ...prev[stageId],
                  artifact: {
                    ...prevArt,
                    phase: 'generating',
                    shots: [...prevShots, ...sceneData.shots],
                  },
                },
              };
            });
          }
        } else if (event.type === 'stage_complete') {
          const newStatus: StageStatus = event.requires_intervention ? 'waiting' : 'completed';

          let artifact = null;
          try {
            const artResult = await getArtifact(sid, stageId);
            artifact = artResult.artifact;
          } catch { /* ignore */ }

          updateStageState(stageId, {
            status: newStatus,
            progress: 100,
            progressMessage: newStatus === 'waiting' ? '等待确认' : '已完成',
            artifact,
          });
        } else if (event.type === 'error') {
          // 取消/停止类错误：尝试获取部分结果而不是直接报错
          const isCancelError = /cancel|取消|停止/i.test(event.content || '');
          if (isCancelError) {
            let artifact = null;
            try {
              const artResult = await getArtifact(sid, stageId);
              artifact = artResult?.artifact;
            } catch { /* ignore */ }
            // 如果有已完成的内容，显示为 waiting 状态
            const clips = artifact?.clips;
            const images = artifact?.images;
            const hasDone = (Array.isArray(clips) && clips.some((c: any) => c.status === 'done'))
                || (Array.isArray(images) && images.some((c: any) => c.status === 'done'));
            if (hasDone) {
              updateStageState(stageId, {
                status: 'waiting',
                progress: 100,
                progressMessage: '已停止（保留已完成内容）',
                artifact,
                error: null,
              });
              return; // 不抛异常，让工作流正常停下
            }
          }
          updateStageState(stageId, {
            status: 'error',
            error: event.content || 'Unknown error',
            progressMessage: '执行失败',
          });
          throw new Error(event.content);
        }
      }
    } catch (error: any) {
      if (error.name !== 'AbortError') {
        updateStageState(stageId, {
          status: 'error',
          error: error.message,
          progressMessage: '执行失败',
        });
      }
      throw error;
    }
  };

  // ── 启动新项目 ──
  const handleStartProject = async (params: ProjectParams, autoOverride?: boolean) => {
    if (isRunning) return;
    stoppedRef.current = false;
    const useAutoMode = autoOverride !== undefined ? autoOverride : autoMode;
    if (autoOverride !== undefined) setAutoMode(autoOverride);
    setIsRunning(true);
    setStageStates(initStageStates());
    setProjectParams(params);

    try {
      const result = await startProject({
        idea: params.idea,
        style: params.style,
        llm_model: params.llm_model,
        vlm_model: params.vlm_model,
        image_t2i_model: params.image_t2i_model,
        image_it2i_model: params.image_it2i_model,
        video_model: params.video_model,
        enable_concurrency: params.enable_concurrency,
      });
      setSessionId(result.session_id);

      // 添加到历史
      setHistory(prev => [
        {
          id: result.session_id,
          idea: params.idea.slice(0, 60),
          style: params.style,
          date: new Date().toLocaleDateString('zh-CN'),
          status: 'running',
          stages: [],
        },
        ...prev,
      ]);

      const inputData: Record<string, any> = {
        idea: params.idea,
        session_id: result.session_id,
        style: params.style,
        llm_model: params.llm_model,
        vlm_model: params.vlm_model,
        image_t2i_model: params.image_t2i_model,
        image_it2i_model: params.image_it2i_model,
        video_model: params.video_model,
        scene_number: result.params?.scene_number,
        expand_idea: params.expand_idea,
        auto_mode: useAutoMode,
      };

      for (const stageId of STAGE_ORDER) {
        if (stoppedRef.current) break;
        await runStage(result.session_id, stageId, inputData);

        // 剧本生成完成后，用实际场景数更新 scene_number
        if (stageId === 'script_generation') {
          try {
            const artResult = await getArtifact(result.session_id, 'script_generation');
            if (artResult?.artifact?.scenes?.length) {
              inputData.scene_number = artResult.artifact.scenes.length;
            }
          } catch { /* ignore */ }
        }

        const status = await getProjectStatus(result.session_id);
        // waiting_in_stage: 等待用户介入（如选择角色/图片），不能自动 continue
        // stage_completed: 阶段完成，等待确认进入下一阶段
        if (status.status === 'stage_completed') {
          if (useAutoMode) {
            // 代理模式：自动确认并继续
            await continueWorkflow(result.session_id);
            updateStageState(stageId, { status: 'completed', progressMessage: '已自动确认' });
          } else {
            updateStageState(stageId, { status: 'completed' });
            setActiveStage(stageId);
            setIsRunning(false);
            return;
          }
        } else if (status.status === 'waiting_in_stage') {
          // 用户需要介入，停止自动执行
          updateStageState(stageId, { status: 'waiting' });
          setActiveStage(stageId);
          setIsRunning(false);
          return;
        }
      }
    } catch (error: any) {
      if (!stoppedRef.current) console.error('Workflow error:', error);
    } finally {
      setIsRunning(false);
    }
  };

  // ── 确认阶段并继续 ──
  const handleConfirmStage = async (stageId: string) => {
    if (!sessionId || isRunning) return;
    setIsRunning(true);

    try {
      const result = await continueWorkflow(sessionId);
      updateStageState(stageId, { status: 'completed', progressMessage: '已确认' });

      // 更新顶栏状态
      setCompletedStagesFromSession(prev => [...prev, stageId]);
      if (result.next_stage) {
        setCurrentStageFromSession(result.next_stage);
      }

      if (result.next_stage) {
        const idx = STAGE_ORDER.indexOf(stageId);

        // 构建完整的 inputData
        const inputData: Record<string, any> = {
          session_id: sessionId,
          style: projectParams?.style,
          llm_model: projectParams?.llm_model,
          vlm_model: projectParams?.vlm_model,
          image_t2i_model: projectParams?.image_t2i_model,
          image_it2i_model: projectParams?.image_it2i_model,
          video_model: projectParams?.video_model,
          video_sound: videoSound,
          video_shot_type: videoShotType,
        };
        // 从剧本产物获取实际场景数
        try {
          const scriptArt = await getArtifact(sessionId, 'script_generation');
          if (scriptArt?.artifact?.scenes?.length) {
            inputData.scene_number = scriptArt.artifact.scenes.length;
          }
        } catch { /* ignore */ }

        // 从参考图产物获取用户选择的图片版本，传递给视频生成阶段
        if (stageId === 'reference_generation') {
          const refArt = stageStates['reference_generation']?.artifact;
          if (refArt?.scenes) {
            const selectedImages: Record<string, string> = {};
            refArt.scenes.forEach((s: any) => {
              if (s.id && s.selected) {
                selectedImages[s.id] = s.selected;
              }
            });
            inputData.selected_images = selectedImages;
          }
        }

        // 从视频产物获取用户选择的视频版本，传递给后期制作阶段
        if (stageId === 'video_generation') {
          const vidArt = stageStates['video_generation']?.artifact;
          if (vidArt?.clips) {
            const selectedClips: Record<string, string> = {};
            vidArt.clips.forEach((c: any) => {
              if (c.id && c.selected) {
                selectedClips[c.id] = c.selected;
              }
            });
            inputData.selected_clips = selectedClips;
          }
        }

        for (let i = idx + 1; i < STAGE_ORDER.length; i++) {
          if (stoppedRef.current) break;
          const nextStage = STAGE_ORDER[i];
          await runStage(sessionId, nextStage, inputData);

          const status = await getProjectStatus(sessionId);
          // waiting_in_stage: 等待用户介入（如选择角色/图片），不能自动 continue
          // stage_completed: 阶段完成，等待确认进入下一阶段，可以自动 continue
          if (status.status === 'stage_completed') {
            if (autoMode) {
              await continueWorkflow(sessionId);
              updateStageState(nextStage, { status: 'completed', progressMessage: '已自动确认' });
              setCompletedStagesFromSession(prev => [...prev, nextStage]);
              setCurrentStageFromSession(nextStage);
            } else {
              updateStageState(nextStage, { status: 'completed' });
              setCompletedStagesFromSession(prev => [...prev, nextStage]);
              setCurrentStageFromSession(nextStage);
              setActiveStage(nextStage);
              break;
            }
          } else if (status.status === 'waiting_in_stage') {
            // 用户需要介入，停止自动执行
            updateStageState(nextStage, { status: 'waiting' });
            setCurrentStageFromSession(nextStage);
            setActiveStage(nextStage);
            break;
          }
        }
      }
    } catch (error: any) {
      console.error('Continue error:', error);
    } finally {
      setIsRunning(false);
    }
  };

  // ── 用户介入修改 ──
  const handleIntervene = async (stageId: string, modifications: Record<string, any>) => {
    if (!sessionId) return;
    // 设置 running 状态以便显示进度条（如 Logline 选择后生成剧本）
    // 若选择了 Logline，将其保存到 artifact 以便 ScriptStage 在生成期间展示
    // 若选择了模式，保留已选 Logline 并设置 generating 状态
    const artifactPatch = modifications.selected_logline
      ? { phase: 'generating', selected_logline: modifications.selected_logline }
      : modifications.selected_mode
        ? { phase: 'generating', selected_logline: stageStates[stageId]?.artifact?.selected_logline }
        : undefined;
    setIsRunning(true);
    updateStageState(stageId, { status: 'running', progress: 0, progressMessage: '处理中...', ...(artifactPatch ? { artifact: artifactPatch } : {}) });
    try {
      const response = await intervene(sessionId, stageId, modifications);
      for await (const event of parseStreamEvents(response)) {
        if (event.type === 'progress') {
          updateStageState(stageId, {
            progress: event.percent || 0,
            progressMessage: event.message || '',
          });
          // 处理 asset_complete 实时事件
          if (event.data?.asset_complete) {
            const assetUpdate = event.data.asset_complete;
            setStageStates(prev => {
              const prevArt = prev[stageId]?.artifact;
              if (!prevArt) return prev;
              const key = assetUpdate.type as string;
              const items = [...(prevArt[key] || [])];
              const idx = items.findIndex((item: any) => item.id === assetUpdate.id);
              if (idx >= 0) {
                items[idx] = {
                  ...items[idx],
                  status: assetUpdate.status,
                  selected: assetUpdate.selected || items[idx].selected,
                  versions: assetUpdate.versions || items[idx].versions,
                };
              }
              return {
                ...prev,
                [stageId]: { ...prev[stageId], artifact: { ...prevArt, [key]: items } },
              };
            });
          }
          // 处理剧本逐幕增量事件 (介入模式)
          if (event.data?.beat_sheet) {
            setStageStates(prev => {
              const prevArt = prev[stageId]?.artifact || {};
              return {
                ...prev,
                [stageId]: {
                  ...prev[stageId],
                  artifact: { ...prevArt, phase: 'generating', beat_sheet: event.data.beat_sheet },
                },
              };
            });
          }
          if (event.data?.act_complete) {
            const actData = event.data.act_complete;
            setStageStates(prev => {
              const prevArt = prev[stageId]?.artifact || {};
              const prevActs = prevArt.completed_acts || [];
              return {
                ...prev,
                [stageId]: {
                  ...prev[stageId],
                  artifact: {
                    ...prevArt,
                    phase: 'generating',
                    completed_acts: [...prevActs, actData],
                  },
                },
              };
            });
          }
          // 处理分镜逐场完成事件 (介入模式)
          if (event.data?.scene_shots_complete) {
            const sceneData = event.data.scene_shots_complete;
            setStageStates(prev => {
              const prevArt = prev[stageId]?.artifact || {};
              const prevShots = prevArt.shots || [];
              return {
                ...prev,
                [stageId]: {
                  ...prev[stageId],
                  artifact: {
                    ...prevArt,
                    phase: 'generating',
                    shots: [...prevShots, ...sceneData.shots],
                  },
                },
              };
            });
          }
        } else if (event.type === 'stage_complete') {
          const artResult = await getArtifact(sessionId, stageId);
          updateStageState(stageId, { artifact: artResult.artifact, status: 'waiting' });
        } else if (event.type === 'error') {
          console.error('Intervention error:', event.content);
        }
      }
    } catch (error: any) {
      console.error('Intervention error:', error);
    } finally {
      setIsRunning(false);
    }
  };

  // ── 本地更新产物（不触发服务端调用） ──
  const handleUpdateArtifact = (stageId: string, patch: Record<string, any>) => {
    setStageStates(prev => ({
      ...prev,
      [stageId]: {
        ...prev[stageId],
        artifact: { ...(prev[stageId]?.artifact || {}), ...patch },
      },
    }));
  };

  // ── 保存用户选择到服务端 ──
  const handleSaveSelections = async (stageId: string, selections: Record<string, any>): Promise<void> => {
    if (!sessionId) return;
    try {
      // 构建更新: 把用户选择写回 artifact 中每个 item 的 selected 字段
      const art = stageStates[stageId]?.artifact;
      if (!art) return;

      let patch: Record<string, any> = {};
      if (stageId === 'script_generation') {
        // 剧本阶段：直接保存整个 data 覆盖 artifact
        patch = selections;
      } else if (stageId === 'character_design') {
        const chars = (art.characters || []).map((c: any) => ({ ...c, selected: selections[c.id] || c.selected }));
        const sets = (art.settings || []).map((s: any) => ({ ...s, selected: selections[s.id] || s.selected }));
        patch = { characters: chars, settings: sets };
      } else if (stageId === 'storyboard') {
        // 分镜阶段：保存 shots 数据（排除 original_shots，只保留 artifact 需要的字段）
        const { original_shots, ...rest } = selections;
        patch = { ...rest, user_modified: true };
      } else if (stageId === 'reference_generation') {
        const { _editDescs, ...restSelections } = selections;
        const scenes = (art.scenes || []).map((s: any) => ({
          ...s,
          selected: restSelections[s.id] || s.selected,
          description: _editDescs?.[s.id] ?? s.description,
        }));
        patch = { scenes };
      } else if (stageId === 'video_generation') {
        const { _editDescs, ...restSelections } = selections;
        const clips = (art.clips || []).map((c: any) => ({
          ...c,
          selected: restSelections[c.id] || c.selected,
          description: _editDescs?.[c.id] ?? c.description,
        }));
        patch = { clips };
      }

      // 本地更新
      handleUpdateArtifact(stageId, patch);

      // 服务端持久化
      await saveSelections(sessionId, stageId, patch);
      // 保存成功后标记为已完成，顶栏显示对勾
      updateStageState(stageId, { status: 'completed' });

      // 如果是分镜阶段保存，刷���第3和第4阶段的 artifact
      console.log('[handleSaveSelections] stageId:', stageId, 'patch:', patch);
      if (stageId === 'storyboard') {
        // 更新本地 artifact 以清除 is_new 标记
        handleUpdateArtifact(stageId, patch);

        // 获取第4阶段当前已有 artifact
        const oldRefArtifact = stageStates['reference_generation']?.artifact;
        const oldScenes = (oldRefArtifact?.scenes || []) as any[];
        const oldScenesMap = new Map(oldScenes.map((s: any) => [s.id, s]));

        // 使用 original_shots（保留 is_new 标记）构建第4阶段 scenes
        const sourceShots = patch.original_shots || patch.shots || [];
        console.log('[handleSaveSelections] sourceShots:', sourceShots);
        const newScenes = sourceShots.map((shot: any, idx: number) => {
          const oldScene = oldScenesMap.get(shot.shot_id) as any;
          const isNew = shot.is_new;
          // 如果是新分镜，使用空值；否则保留原有的 selected/versions
          return {
            id: shot.shot_id,
            name: `场景${shot.scene_number}-镜头${shot.shot_number}`,
            index: idx + 1,
            description: shot.visual_prompt || '',
            duration: shot.duration || 10,
            selected: isNew ? '' : (oldScene?.selected || ''),
            versions: isNew ? [] : (oldScene?.versions || []),
            status: isNew ? 'pending' : 'done',
          };
        });
        console.log('[handleSaveSelections] newScenes:', newScenes);

        // 更新第4阶段的 artifact
        updateStageState('reference_generation', {
          artifact: { session_id: sessionId, scenes: newScenes },
          status: 'completed'
        });
        console.log('[handleSaveSelections] 第4阶段已更新');

        // 同步更新第5阶段（video_generation）
        const oldVidArtifact = stageStates['video_generation']?.artifact;
        const oldClips = (oldVidArtifact?.clips || []) as any[];
        const oldClipsMap = new Map(oldClips.map((c: any) => [c.id, c]));

        const newClips = sourceShots.map((shot: any, idx: number) => {
          const oldClip = oldClipsMap.get(shot.shot_id) as any;
          return {
            id: shot.shot_id,
            name: `场景${shot.scene_number}-镜头${shot.shot_number}`,
            index: idx + 1,
            description: shot.visual_prompt || '',
            duration: shot.duration || 10,
            selected: oldClip?.selected || '',
            versions: oldClip?.versions || [],
            status: 'pending',
          };
        });

        // 更新第5阶段的 artifact
        updateStageState('video_generation', {
          artifact: { session_id: sessionId, clips: newClips },
          status: 'completed'
        });
        console.log('[handleSaveSelections] 第5阶段已更新');
      }
    } catch (error) {
      console.error('Save selections error:', error);
      throw error; // 抛出让 StageActions 捕获以恢复按钮状态
    }
  };

  // ── 重新生成当前阶段 ──
  const handleRegenerate = async (stageId: string) => {
    if (!sessionId || isRunning) return;
    stoppedRef.current = false;
    setIsRunning(true);

    // 清空当前阶段状态
    updateStageState(stageId, {
      status: 'running',
      progress: 0,
      progressMessage: '重新生成中...',
      artifact: null,
      error: null,
    });

    // 将该阶段之后的所有阶段重置为 pending
    const idx = STAGE_ORDER.indexOf(stageId);
    for (let i = idx + 1; i < STAGE_ORDER.length; i++) {
      updateStageState(STAGE_ORDER[i], {
        status: 'pending',
        progress: 0,
        progressMessage: '',
        artifact: null,
        error: null,
      });
    }

    try {
      const inputData: Record<string, any> = {
        session_id: sessionId,
        style: projectParams?.style,
        llm_model: projectParams?.llm_model,
        vlm_model: projectParams?.vlm_model,
        image_t2i_model: projectParams?.image_t2i_model,
        image_it2i_model: projectParams?.image_it2i_model,
        video_model: projectParams?.video_model,
        video_sound: videoSound,
        video_shot_type: videoShotType,
      };

      // 尝试获取场景数
      try {
        const scriptArt = await getArtifact(sessionId, 'script_generation');
        if (scriptArt?.artifact?.scenes?.length) {
          inputData.scene_number = scriptArt.artifact.scenes.length;
        }
      } catch { /* ignore */ }

      await runStage(sessionId, stageId, inputData);

      const status = await getProjectStatus(sessionId);
      if (status.status === 'waiting_in_stage') {
        updateStageState(stageId, { status: 'waiting' });
        setActiveStage(stageId);
      }
    } catch (error: any) {
      if (!stoppedRef.current) console.error('Regenerate error:', error);
    } finally {
      setIsRunning(false);
    }
  };

  // ── 恢复历史项目 ──
  const handleResumeProject = async (sid: string, targetStage: string | null = null) => {
    // 如果正在执行的就是同一个项目，直接恢复视图，不重置状态
    if (sid === sessionId) {
      const runningStage = STAGE_ORDER.find(s => stageStates[s]?.status === 'running');
      const waitingStage = STAGE_ORDER.find(s => stageStates[s]?.status === 'waiting');
      const lastCompleted = [...STAGE_ORDER].reverse().find(s => stageStates[s]?.status === 'completed');
      setActiveStage(targetStage || runningStage || waitingStage || lastCompleted || STAGE_ORDER[0]);
      return;
    }

    setSessionId(sid);
    // 更新 URL 参数（包含阶段）
    const stageParam = targetStage ? `&stage=${targetStage}` : '';
    router.push(`/?session=${sid}${stageParam}`);
    try {
      // 优先从 sessions json 读取（支持后端重启后恢复）
      let status: any;
      try {
        status = await getProjectStatusFromDisk(sid);
      } catch {
        status = await getProjectStatus(sid);
      }
      const newStates = initStageStates();
      const completedStages = status.stages_completed || [];
      const currentStage = status.current_stage;
      const isWaiting = status.status === 'waiting_in_stage';
      // 保存到 state 供顶栏流程图使用
      setCurrentStageFromSession(currentStage || null);
      setCompletedStagesFromSession(completedStages);

      for (const cs of completedStages) {
        const isCurrentWaiting = cs === currentStage && isWaiting;
        newStates[cs] = {
          status: isCurrentWaiting ? 'waiting' : 'completed',
          progress: 100,
          progressMessage: isCurrentWaiting ? '等待确认' : '已完成',
          artifact: null,
          error: null,
        };
        try {
          const artResult = await getArtifact(sid, cs);
          newStates[cs].artifact = artResult.artifact;
        } catch { /* ignore */ }
      }

      // 如果 current_stage 不在 completedStages 中，也需要显示（可能是 stage_completed 或 running 状态）
      if (currentStage && !completedStages.includes(currentStage)) {
        newStates[currentStage] = {
          status: status.status === 'waiting_in_stage' ? 'waiting' : (status.status === 'stage_completed' ? 'completed' : 'running'),
          progress: 100,
          progressMessage: status.status === 'waiting_in_stage' ? '等待确认' : (status.status === 'stage_completed' ? '已完成' : '进行中'),
          artifact: null,
          error: null,
        };
        try {
          const artResult = await getArtifact(sid, currentStage);
          newStates[currentStage].artifact = artResult.artifact;
        } catch { /* ignore */ }
      }

      // 恢复项目参数（从顶层字段读取，sessions json 中模型参数是顶层字段）
      if ((status as any).idea) {
        const s = status as any;
        setProjectParams({
          idea: s.idea || '',
          style: s.style || '',
          video_ratio: s.video_ratio || '16:9',
          llm_model: s.llm_model || '',
          vlm_model: s.vlm_model || '',
          image_t2i_model: s.image_t2i_model || '',
          image_it2i_model: s.image_it2i_model || '',
          video_model: s.video_model || '',
          expand_idea: s.expand_idea || false,
          enable_concurrency: s.enable_concurrency || false,
        });
      }

      // 确定要显示的阶段（优先使用 URL 中的目标阶段）
      let finalStage = targetStage;
      if (!finalStage) {
        finalStage = currentStage || (completedStages.length > 0 ? completedStages[completedStages.length - 1] : STAGE_ORDER[0]);
      }
      setActiveStage(finalStage);
      setStageStates(newStates);

      // 轮询当前正在执行的阶段（仅当该阶段有 artifact 数据时）
      if (status.status === 'running' && currentStage && !completedStages.includes(currentStage)) {
        pollForCompletion(sid, currentStage);
      }
    } catch {
      setActiveStage(STAGE_ORDER[0]);
    }
  };

  // ── 返回首页 ──
  // 处理阶段点击，更新 URL
  const handleStageClick = (stage: string) => {
    setActiveStage(stage);
    if (sessionId) {
      router.push(`/?session=${sessionId}&stage=${stage}`);
    }
  };

  const handleGoHome = () => {
    setActiveStage(null);
    router.push('/');
  };

  // ── 删除历史记录 ──
  const handleDeleteSession = async (sid: string, password: string) => {
    await deleteSession(sid, password);
    setHistory(prev => prev.filter(h => h.id !== sid));
  };

  // ── 模型配置变更处理 ──
  const handleModelConfigChange = (config: ModelConfig) => {
    setProjectParams(prev => prev ? { ...prev, ...config } : null);
    // 同步到后端会话元数据（需要将 boolean 转为 string）
    if (sessionId) {
      const stringConfig: Record<string, string> = {};
      for (const [key, value] of Object.entries(config)) {
        stringConfig[key] = String(value);
      }
      updateModels(sessionId, stringConfig).catch(console.error);
    }
  };

  // 构建 modelConfig for TopBar
  const modelConfig: ModelConfig | undefined = projectParams
    ? {
        llm_model: projectParams.llm_model,
        vlm_model: projectParams.vlm_model,
        image_t2i_model: projectParams.image_t2i_model,
        image_it2i_model: projectParams.image_it2i_model,
        video_model: projectParams.video_model,
        video_ratio: projectParams.video_ratio,
        enable_concurrency: projectParams.enable_concurrency || false,
      }
    : undefined;

  // ── 计算 stageStatuses for TopBar ──
  // 根据 session 的 current_stage 和 stages_completed 判断图标状态
  const stageStatuses: Record<string, StageStatus> = {};
  const currentIdx = STAGE_ORDER.indexOf(currentStageFromSession || '');

  for (let i = 0; i < STAGE_ORDER.length; i++) {
    const s = STAGE_ORDER[i];

    if (i < currentIdx) {
      // current_stage 之前的阶段：已完成（绿色对勾）
      stageStatuses[s] = 'completed';
    } else if (i > currentIdx) {
      // current_stage 之后的阶段
      if (completedStagesFromSession.includes(s)) {
        // 在 stages_completed 中（黄色图案）
        stageStatuses[s] = 'waiting';
      } else {
        // 不在 stages_completed 中：pending
        stageStatuses[s] = 'pending';
      }
    } else {
      // current_stage 本身：根据 stageStates 判断
      stageStatuses[s] = stageStates[s]?.status || 'pending';
    }
  }

  // ── 计算项目状态 ──
  // 后端状态: idle, running, waiting_in_stage, stage_completed, session_completed, error
  // 前端 StageStatus: pending, running, waiting, completed, error
  const hasRunning = Object.values(stageStates).some(s => s.status === 'running');
  const hasWaiting = Object.values(stageStates).some(s => s.status === 'waiting');
  const hasError = Object.values(stageStates).some(s => s.status === 'error');
  const allCompleted = Object.values(stageStates).every(s => s.status === 'completed' || s.status === 'pending');

  let computedStatus: string;
  if (hasRunning) computedStatus = 'running';
  else if (hasWaiting) computedStatus = 'waiting_in_stage';
  else if (hasError) computedStatus = 'error';
  else if (allCompleted && stageStates[STAGE_ORDER[STAGE_ORDER.length - 1]]?.status === 'completed') {
    computedStatus = 'session_completed';
  } else if (allCompleted) {
    computedStatus = 'stage_completed';
  } else {
    computedStatus = 'idle';
  }

  const projectStatus = sessionId ? computedStatus : undefined;

  // ── 渲染阶段内容 ──
  const renderStageContent = () => {
    if (!activeStage) return null;
    const Component = STAGE_COMPONENTS[activeStage];
    if (!Component) return null;

    const state = stageStates[activeStage];

    // 判断后续阶段是否已执行过：如有，则隐藏"确认并继续"
    const idx = STAGE_ORDER.indexOf(activeStage);
    const hasSubsequentExecution = STAGE_ORDER.slice(idx + 1).some(
      s => stageStates[s]?.status && stageStates[s].status !== 'pending'
    );
    const showConfirm = !hasSubsequentExecution;

    // 计算是否有待生成的项（阶段2、4、5）
    let hasPendingItems = false;
    if (activeStage === 'character_design') {
      const chars = state?.artifact?.characters || [];
      const sets = state?.artifact?.settings || [];
      hasPendingItems = chars.some((c: any) => !c.selected) || sets.some((s: any) => !s.selected);
    } else if (activeStage === 'reference_generation') {
      const scenes = state?.artifact?.scenes || [];
      hasPendingItems = scenes.some((s: any) => !s.selected);
    } else if (activeStage === 'video_generation') {
      const clips = state?.artifact?.clips || [];
      // 检查是否有未选中的 clips
      const hasUnselected = clips.some((c: any) => !c.selected);
      // 检查参考图阶段的 scenes 数量是否大于 video clips 数量
      // 如果是，说明有新分镜需要生成
      const refScenes = stageStates['reference_generation']?.artifact?.scenes || [];
      const hasNewShots = refScenes.length > clips.length;
      hasPendingItems = hasUnselected || hasNewShots;
    }

    // 计算后续阶段是否已开始（阶段1、3）
    const hasNextStageStarted = hasSubsequentExecution;

    // 传递第4阶段的 artifact 到第5阶段用于依赖检查
    const referenceArtifact = activeStage === 'video_generation'
      ? stageStates['reference_generation']?.artifact
      : undefined;

    return (
      <Component
        state={state}
        sessionId={sessionId || ''}
        onConfirm={() => handleConfirmStage(activeStage)}
        onIntervene={(mods: Record<string, any>) => handleIntervene(activeStage, mods)}
        onRegenerate={() => handleRegenerate(activeStage)}
        onUpdateArtifact={(patch: Record<string, any>) => handleUpdateArtifact(activeStage, patch)}
        onSaveSelections={(selections: Record<string, any>) => handleSaveSelections(activeStage, selections)}
        showConfirm={showConfirm}
        isRunning={isRunning}
        hasPendingItems={hasPendingItems}
        hasNextStageStarted={hasNextStageStarted}
        videoSound={videoSound}
        videoShotType={videoShotType}
        onVideoParamsChange={(params: { videoSound?: string; videoShotType?: string }) => {
          if (params.videoSound !== undefined) setVideoSound(params.videoSound);
          if (params.videoShotType !== undefined) setVideoShotType(params.videoShotType);
        }}
        referenceArtifact={referenceArtifact}
      />
    );
  };

  const showHome = activeStage === null;

  return (
    <div className="flex flex-col h-screen w-screen bg-gray-50/50">
      <TopBar
        activeStage={activeStage}
        stageStatuses={stageStatuses}
        onStageClick={handleStageClick}
        onHomeClick={handleGoHome}
        hasSession={sessionId !== null}
        isRunning={isRunning}
        onStop={handleStop}
        autoMode={autoMode}
        onAutoModeChange={setAutoMode}
        modelConfig={modelConfig}
        onModelConfigChange={handleModelConfigChange}
        projectStatus={projectStatus}
      />

      <main className="flex-1 overflow-hidden">
        {showHome ? (
          <HomePage
            onStartProject={handleStartProject}
            onResumeProject={handleResumeProject}
            onDeleteSession={handleDeleteSession}
            history={history}
          />
        ) : (
          renderStageContent()
        )}
      </main>
    </div>
  );
}
