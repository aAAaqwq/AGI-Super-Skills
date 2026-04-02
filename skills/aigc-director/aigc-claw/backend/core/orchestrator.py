# -*- coding: utf-8 -*-
"""
核心编排器 / 工作流引擎
管理六阶段状态机，协调各智能体执行，支持用户在任意阶段介入
"""

import json
import logging
import os
import threading
import time
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from core.agents import (
    ScriptWriterAgent,
    CharacterDesignerAgent,
    StoryboardAgent,
    ReferenceGeneratorAgent,
    VideoDirectorAgent,
    VideoEditorAgent,
)

logger = logging.getLogger(__name__)


class WorkflowStage(str, Enum):
    """工作流阶段"""
    INIT = "init"
    SCRIPT_GENERATION = "script_generation"
    CHARACTER_DESIGN = "character_design"
    STORYBOARD = "storyboard"
    REFERENCE_GENERATION = "reference_generation"
    VIDEO_GENERATION = "video_generation"
    POST_PRODUCTION = "post_production"
    COMPLETED = "session_completed"


STAGE_ORDER = [
    WorkflowStage.SCRIPT_GENERATION,
    WorkflowStage.CHARACTER_DESIGN,
    WorkflowStage.STORYBOARD,
    WorkflowStage.REFERENCE_GENERATION,
    WorkflowStage.VIDEO_GENERATION,
    WorkflowStage.POST_PRODUCTION,
]


class WorkflowState:
    """工作流状态"""

    # 状态说明：
    # - idle: 新建会话，还没有任何数据，也没有在运行
    # - running: 会话正在运行
    # - waiting_in_stage: 会话在某一阶段内等待用户介入（如选择角色、选择图片等）
    # - stage_completed: 会话完成了某一阶段，等待用户确定开始下一阶段
    # - session_completed: 会话全部完成
    # - stopped: 用户手动停止
    # - error: 执行中遇到错误

    def __init__(self, session_id: str):
        self.session_id = session_id
        self.current_stage: WorkflowStage = WorkflowStage.INIT
        self.status: str = "idle"
        self.stages_completed: List[str] = []  # 已完成的阶段列表
        self.artifacts: Dict[str, Any] = {}
        self.error: Optional[str] = None
        self.started_at: Optional[datetime] = None
        self.updated_at: datetime = datetime.now()
        self.meta: Dict[str, Any] = {}

    def to_dict(self) -> Dict:
        return {
            "session_id": self.session_id,
            "current_stage": self.current_stage.value,
            "status": self.status,
            "error": self.error,
            "stages_completed": self.stages_completed,
            "artifacts": self.artifacts,
            "meta": self.meta,
            "updated_at": self.updated_at,
        }


class WorkflowEngine:
    """工作流引擎 - 管理六阶段状态机"""

    def __init__(self):
        self.agents = {
            WorkflowStage.SCRIPT_GENERATION: ScriptWriterAgent(),
            WorkflowStage.CHARACTER_DESIGN: CharacterDesignerAgent(),
            WorkflowStage.STORYBOARD: StoryboardAgent(),
            WorkflowStage.REFERENCE_GENERATION: ReferenceGeneratorAgent(),
            WorkflowStage.VIDEO_GENERATION: VideoDirectorAgent(),
            WorkflowStage.POST_PRODUCTION: VideoEditorAgent(),
        }
        self.sessions: Dict[str, WorkflowState] = {}
        self._stop_events: Dict[str, threading.Event] = {}
        self._session_dir = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), '..', 'code', 'data', 'sessions'
        )
        os.makedirs(self._session_dir, exist_ok=True)
        self._load_sessions_from_disk()

    def get_or_create_state(self, session_id: str) -> WorkflowState:
        if session_id not in self.sessions:
            self.sessions[session_id] = WorkflowState(session_id=session_id)
        if session_id not in self._stop_events:
            self._stop_events[session_id] = threading.Event()
        return self.sessions[session_id]

    def get_state(self, session_id: str) -> Optional[WorkflowState]:
        # 先从内存中获取
        if session_id in self.sessions:
            return self.sessions[session_id]

        # 内存中没有，从磁盘加载
        path = os.path.join(self._session_dir, f"{session_id}.json")
        if os.path.exists(path):
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                # 从磁盘数据恢复 WorkflowState
                state = WorkflowState(session_id=session_id)
                state.status = data.get('status', 'idle')
                stage_str = data.get('current_stage')
                state.current_stage = WorkflowStage(stage_str) if stage_str else WorkflowStage.INIT
                state.stages_completed = data.get('stages_completed', [])
                state.artifacts = data.get('artifacts', {})
                state.meta = data.get('meta', {})
                state.error = data.get('error')
                state.updated_at = data.get('updated_at', 0)

                # 缓存到内存
                self.sessions[session_id] = state
                return state
            except json.JSONDecodeError as e:
                logger.warning(f"Session file {session_id} is corrupted, ignoring: {e}")
            except Exception as e:
                logger.warning(f"Failed to load session {session_id} from disk: {e}")

        return None

    def get_stop_event(self, session_id: str) -> threading.Event:
        if session_id not in self._stop_events:
            self._stop_events[session_id] = threading.Event()
        return self._stop_events[session_id]

    def stop_session(self, session_id: str):
        self.get_stop_event(session_id).set()
        state = self.get_state(session_id)
        if state and state.status == "running":
            state.status = "stopped"
            state.error = None  # 清除错误，因为是主动停止
            state.updated_at = datetime.now()
            self.save_session_to_disk(session_id)
        logger.info(f"Session {session_id} stop signal sent")

    def reset_stop_event(self, session_id: str):
        if session_id in self._stop_events:
            self._stop_events[session_id].clear()

    def _get_next_stage(self, current: WorkflowStage) -> Optional[WorkflowStage]:
        try:
            idx = STAGE_ORDER.index(current)
            if idx + 1 < len(STAGE_ORDER):
                return STAGE_ORDER[idx + 1]
        except ValueError:
            pass
        return None

    async def execute_stage(self,
                            state: WorkflowState,
                            stage: WorkflowStage,
                            input_data: Any,
                            cancellation_check: Optional[Callable] = None,
                            progress_callback: Optional[Callable] = None,
                            intervention: Optional[Dict] = None) -> Dict:
        import time

        agent = self.agents[stage]

        # 合并会话级停止信号与请求级取消检查
        session_stop = self.get_stop_event(state.session_id)
        def combined_cancel_check():
            return session_stop.is_set() or (cancellation_check and cancellation_check())

        agent.set_cancellation_check(combined_cancel_check)

        # 包装 progress_callback，定期保存状态到 sessions json
        last_save_time = {"time": 0}
        SAVE_INTERVAL = 10  # 每10秒保存一次

        def wrapped_progress_callback(phase: str, step: str, percent: float, data: dict = None):
            # 调用原始 callback
            if progress_callback:
                progress_callback(phase, step, percent, data)

            # 如果有 asset_complete 数据，说明有新生成的图片/视频，立即保存到磁盘
            if data and data.get("asset_complete"):
                self.save_session_to_disk(state.session_id)
                last_save_time["time"] = time.time()
                return

            # 如果有 progress 回调（纯文字阶段），也定期保存
            # 这样前端可以实时看到文字生成进度
            current_time = time.time()
            if current_time - last_save_time["time"] >= SAVE_INTERVAL:
                last_save_time["time"] = current_time
                self.save_session_to_disk(state.session_id)

        if progress_callback:
            agent.set_progress_callback(wrapped_progress_callback)

        state.current_stage = stage
        state.status = "running"
        state.updated_at = datetime.now()

        try:
            result = await agent.process(input_data, intervention=intervention)
            state.artifacts[stage.value] = result.get("payload")

            # 第三阶段修改分镜时：同步更新第四、第五阶段的相关内容
            if stage.value == "storyboard" and intervention and "modified_storyboard" in intervention:
                modified_shots = intervention["modified_storyboard"]
                if isinstance(modified_shots, list):
                    shot_durations = {s.get('shot_id'): s.get('duration', 10)
                                    for s in modified_shots if s.get('shot_id')}
                    shot_visual_prompts = {s.get('shot_id'): s.get('visual_prompt', '')
                                         for s in modified_shots if s.get('shot_id')}
                    shot_plots = {s.get('shot_id'): s.get('plot', '')
                                for s in modified_shots if s.get('shot_id')}

                    # 1. 同步 duration 到第五阶段 clips
                    video_art = state.artifacts.get('video_generation', {})
                    if isinstance(video_art, dict) and 'clips' in video_art:
                        for clip in video_art['clips']:
                            shot_id = clip.get('id')
                            if shot_id in shot_durations:
                                clip['duration'] = shot_durations[shot_id]
                            if shot_id in shot_plots:
                                clip['description'] = shot_plots[shot_id]

                    # 2. 同步 visual_prompt 到第四阶段 scenes (description)
                    ref_art = state.artifacts.get('reference_generation', {})
                    if isinstance(ref_art, dict) and 'scenes' in ref_art:
                        for scene in ref_art['scenes']:
                            shot_id = scene.get('id')
                            if shot_id in shot_visual_prompts:
                                scene['description'] = shot_visual_prompts[shot_id]

                    # 3. 新增分镜：同步到第四、第五阶段
                    existing_shot_ids = {clip.get('id') for clip in video_art.get('clips', [])} if isinstance(video_art, dict) else set()
                    existing_scene_ids = {scene.get('id') for scene in ref_art.get('scenes', [])} if isinstance(ref_art, dict) else set()

                    for shot in modified_shots:
                        shot_id = shot.get('shot_id')
                        if not shot_id:
                            continue
                        # 新增到第五阶段
                        if shot_id not in existing_shot_ids:
                            if isinstance(video_art, dict):
                                video_art.setdefault('clips', []).append({
                                    'id': shot_id,
                                    'name': f"镜头{shot_id.split('_')[-1]}",
                                    'description': shot.get('plot', ''),
                                    'duration': shot.get('duration', 10),
                                    'selected': '',
                                    'versions': [],
                                    'status': 'pending'
                                })
                        # 新增到第四阶段
                        if shot_id not in existing_scene_ids:
                            if isinstance(ref_art, dict):
                                ref_art.setdefault('scenes', []).append({
                                    'id': shot_id,
                                    'name': f"场景{shot_id.split('_')[-2]}",
                                    'description': shot.get('visual_prompt', ''),
                                    'selected': '',
                                    'versions': [],
                                    'status': 'pending'
                                })

                    logger.info(f"Synced stage 3 modifications: {len(shot_durations)} durations, {len(shot_visual_prompts)} prompts")

            # 调试日志
            logger.info(f"[execute_stage] stage={stage.value}, intervention={intervention is not None}, requires_intervention={result.get('requires_intervention')}, stage_completed={result.get('stage_completed')}")

            # 状态转换逻辑：
            # - stage_completed=True: 阶段已完成，等待用户确认进入下一阶段
            # - requires_intervention=True: 阶段内需要用户介入（如选择图片等）
            # - 其他（running）：阶段正在执行中
            if result.get("stage_completed"):
                # 阶段真正完成，标记到已完成的列表
                if stage.value not in state.stages_completed:
                    state.stages_completed.append(stage.value)
                # 如果是最后一个阶段，设置为 session_completed
                if stage == WorkflowStage.POST_PRODUCTION:
                    state.status = "session_completed"
                else:
                    state.status = "stage_completed"
            elif result.get("requires_intervention"):
                # 阶段内需要用户介入，等待用户选择
                state.status = "waiting_in_stage"
            else:
                # 阶段正在执行中（中间步骤），保持 running
                state.status = "running"

            state.updated_at = datetime.now()
            # 立即保存状态到磁盘，确保前端能获取到最新状态
            self.save_session_to_disk(state.session_id)
            return result

        except Exception as e:
            state.status = "error"
            state.error = str(e)
            state.updated_at = datetime.now()
            raise

    async def handle_intervention(self,
                                  session_id: str,
                                  stage: str,
                                  modifications: Dict[str, Any]) -> Dict:
        state = self.sessions[session_id]
        stage_enum = WorkflowStage(stage)
        current_artifact = state.artifacts.get(stage, {})

        input_data = current_artifact if isinstance(current_artifact, dict) else {}
        input_data.update(modifications)

        return await self.execute_stage(state, stage_enum, input_data, intervention=modifications)

    async def continue_workflow(self, session_id: str) -> Dict:
        state = self.sessions[session_id]
        logger.info(f"[continue_workflow] session={session_id}, current_stage={state.current_stage}, status={state.status}")

        # 检查当前阶段是否已完成
        current_stage_str = state.current_stage.value if hasattr(state.current_stage, 'value') else str(state.current_stage)

        # 如果当前状态是 running，说明阶段还在执行中，不能继续
        if state.status == "running":
            return {
                "status": "waiting",
                "openclaw": f"当前阶段（{current_stage_str}）还在执行中，请等待完成后再调用 /continue。",
                "message": f"当前阶段（{current_stage_str}）还在执行中，请等待完成后再调用 /continue。",
                "current_status": state.status,
            }

        # 状态转换逻辑：
        # - waiting_in_stage 或 stage_completed: 用户确认后直接进入下一阶段
        # 注意：只有当阶段真正完成（waiting_in_stage 或 stage_completed）时才允许继续

        if state.status == "waiting_in_stage" or state.status == "stage_completed":
            # 用户确认后标记阶段完成
            if current_stage_str not in state.stages_completed:
                state.stages_completed.append(current_stage_str)

            # 直接进入下一阶段
            state.status = "running"
            next_stage = self._get_next_stage(state.current_stage)

            if not next_stage:
                state.status = "session_completed"
                self.save_session_to_disk(state.session_id)
                return {"status": "session_completed"}

            self.save_session_to_disk(state.session_id)
            return {"status": "ready", "next_stage": next_stage.value}

        # 其他状态（如 idle, stopped, error, session_completed）不允许继续
        return {
            "status": "error",
            "openclaw": f"当前状态 {state.status} 不允许继续，请检查会话状态。",
            "message": f"当前状态不允许继续",
            "current_status": state.status,
        }

    # ──────────── 会话持久化 ────────────

    def save_session_to_disk(self, session_id: str, meta: Dict = None):
        """保存 / 更新会话到磁盘（原子写入）"""
        import tempfile
        import shutil

        path = os.path.join(self._session_dir, f"{session_id}.json")
        data: Dict[str, Any] = {}
        if os.path.exists(path):
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
            except (json.JSONDecodeError, Exception):
                # 文件损坏，忽略旧数据
                pass
        data["session_id"] = session_id
        if meta:
            for k, v in meta.items():
                data[k] = v
        if "created_at" not in data:
            data["created_at"] = time.time()
        data["updated_at"] = time.time()
        state = self.sessions.get(session_id)
        if state:
            data["current_stage"] = state.current_stage.value
            data["status"] = state.status
            data["stages_completed"] = state.stages_completed
            data["artifacts"] = state.artifacts
            data["error"] = state.error
            # datetime 对象需要转换为时间戳
            data["updated_at"] = state.updated_at.timestamp() if isinstance(state.updated_at, datetime) else state.updated_at
            # 保存元数据（包含模型配置）
            if state.meta:
                for k, v in state.meta.items():
                    if v is not None:
                        data[k] = v

        # 原子写入：先写临时文件，再重命名
        dir_path = os.path.dirname(path)
        fd, tmp_path = tempfile.mkstemp(dir=dir_path, suffix='.json')
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            shutil.move(tmp_path, path)
        except Exception:
            # 写入失败，删除临时文件
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
            raise

    def _load_sessions_from_disk(self):
        """启动时从磁盘加载所有已保存的会话"""
        if not os.path.exists(self._session_dir):
            return
        for filename in os.listdir(self._session_dir):
            if not filename.endswith('.json'):
                continue
            try:
                fpath = os.path.join(self._session_dir, filename)
                with open(fpath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                sid = data["session_id"]
                state = WorkflowState(sid)
                try:
                    state.current_stage = WorkflowStage(data.get("current_stage", "init"))
                except ValueError:
                    state.current_stage = WorkflowStage.INIT
                # 旧版本兼容：状态名称转换
                old_status = data.get("status", "idle")
                if old_status == "waiting_intervention":
                    state.status = "waiting_in_stage"
                elif old_status == "completed":
                    state.status = "session_completed"
                else:
                    state.status = old_status

                state.stages_completed = data.get("stages_completed", [])
                state.artifacts = data.get("artifacts", {})
                state.error = data.get("error")
                state.updated_at = data.get("updated_at", 0)
                state.meta = {k: data[k] for k in
                              ("idea", "style", "llm_model", "image_t2i_model",
                               "image_it2i_model", "video_model")
                              if k in data}
                self.sessions[sid] = state
            except json.JSONDecodeError:
                logger.warning(f"Skipping corrupted session file: {filename}")
            except Exception as e:
                logger.warning(f"Failed to load session {filename}: {e}")

    def delete_session(self, session_id: str) -> bool:
        """删除指定会话（内存 + 磁盘 + 结果文件）"""
        from config import settings

        # 从内存中移除
        self.sessions.pop(session_id, None)
        self._stop_events.pop(session_id, None)

        # 1. 删除会话元数据文件
        path = os.path.join(self._session_dir, f"{session_id}.json")
        if os.path.exists(path):
            os.remove(path)

        # 2. 删除结果文件（剧本、图片、视频）
        result_base = settings.RESULT_DIR

        # 删除剧本文件
        script_file = os.path.join(result_base, 'script', f'script_{session_id}.json')
        if os.path.exists(script_file):
            os.remove(script_file)

        # 删除图片目录
        image_dir = os.path.join(result_base, 'image', session_id)
        if os.path.exists(image_dir):
            import shutil
            shutil.rmtree(image_dir)

        # 删除视频目录
        video_dir = os.path.join(result_base, 'video', session_id)
        if os.path.exists(video_dir):
            import shutil
            shutil.rmtree(video_dir)

        logger.info(f"Session and results deleted: {session_id}")
        return True

    def list_saved_sessions(self) -> List[Dict]:
        """列出所有已保存的会话概要"""
        sessions: List[Dict] = []
        if not os.path.exists(self._session_dir):
            return sessions
        for filename in os.listdir(self._session_dir):
            if not filename.endswith('.json'):
                continue
            try:
                fpath = os.path.join(self._session_dir, filename)
                with open(fpath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                sessions.append({
                    "id": data["session_id"],
                    "idea": data.get("idea", ""),
                    "style": data.get("style", ""),
                    "date": data.get("updated_at", 0),
                    "stages": data.get("stages_completed", []),
                })
            except Exception:
                continue
        sessions.sort(key=lambda x: x.get("date", 0), reverse=True)
        return sessions
