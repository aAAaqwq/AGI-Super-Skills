# -*- coding: utf-8 -*-
"""
阶段3: 分镜智能体
基于剧本JSON，逐场景拆分为带时长标签的分镜（shots），按幕分组输出。
"""

import os
import re
import json
import asyncio
import logging
from typing import Any, Optional, Dict, List
from concurrent.futures import ThreadPoolExecutor, as_completed

from .base_agent import AgentInterface
from prompts.loader import load_prompt

logger = logging.getLogger(__name__)

# ─── 幕名 ───
ACT_NAMES = {1: "激励事件", 2: "进入新世界", 3: "灵魂黑夜", 4: "高潮决战"}


def _get_shot_prompt(lang: str = 'zh') -> str:
    """获取分镜提示词"""
    return load_prompt('storyboard', 'shot', lang)


def _get_continue_prompt(lang: str = 'zh') -> str:
    """获取续写分镜提示词"""
    from prompts.loader import load_prompt_with_fallback
    return load_prompt_with_fallback('storyboard', 'continue', lang, 'zh')


def _get_prompt(name: str) -> str:
    """Helper to get prompts"""
    if name == 'SHOT_PROMPT_ZH':
        return load_prompt('storyboard', 'shot', 'zh')
    elif name == 'SHOT_PROMPT_EN':
        return load_prompt('storyboard', 'shot', 'en')
    raise AttributeError(f"module has no attribute {name!r}")


class StoryboardAgent(AgentInterface):
    """分镜智能体：逐场景拆分为带时长标签的分镜"""

    def __init__(self):
        super().__init__(name="Storyboard")

    # ─── 辅助方法 ───

    @staticmethod
    def _read_script_json(sid: str) -> dict:
        """从结果文件读取 script_json"""
        from config import settings
        result_file = os.path.join(settings.RESULT_DIR, 'script', f'script_{sid}.json')
        if not os.path.exists(result_file):
            return {}
        with open(result_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data.get(str(sid), {}).get('script_json', {})

    @staticmethod
    def _extract_json_array(text: str) -> Optional[List[dict]]:
        """从LLM输出中提取JSON数组"""
        text = text.strip()
        text = re.sub(r'^```(?:json)?\s*', '', text)
        text = re.sub(r'\s*```$', '', text)
        text = text.strip()
        try:
            result = json.loads(text)
            if isinstance(result, list):
                return result
        except json.JSONDecodeError:
            pass
        # 尝试找到 [ ... ] 部分
        m = re.search(r'\[.*\]', text, re.DOTALL)
        if m:
            try:
                result = json.loads(m.group())
                if isinstance(result, list):
                    return result
            except json.JSONDecodeError:
                pass
        return None

    @staticmethod
    def _validate_shots(shots: List[dict]) -> List[dict]:
        """校验并清洗分镜数据"""
        valid = []
        for s in shots:
            if not isinstance(s, dict):
                continue
            dur = s.get("duration", 10)
            if dur not in (5, 10, 15):
                dur = 10  # 默认10秒
            valid.append({
                "shot_number": s.get("shot_number", len(valid) + 1),
                "duration": dur,
                "characters": s.get("characters", []),
                "location": s.get("location", ""),
                "plot": s.get("plot", ""),
                "visual_prompt": s.get("visual_prompt", ""),
            })
        return valid

    async def _continue_story(self, input_data: Dict, continue_info: Dict) -> Dict:
        """智能续写：根据已有剧情续写新场景"""
        from config import settings
        from tool.llm_client import LLM

        sid = input_data["session_id"]
        style = input_data.get("style", "anime")
        llm_model = input_data.get("llm_model", "qwen3.5-plus")

        result_file = os.path.join(settings.RESULT_DIR, 'script', f'script_{sid}.json')

        # 读取已有分镜
        with open(result_file, 'r', encoding='utf-8') as f:
            results = json.load(f)
        existing_shots = results.get(str(sid), {}).get('storyboard', {}).get('shots', [])
        if not existing_shots:
            raise Exception("没有已有分镜，无法续写")

        # 读取剧本信息
        script_json = self._read_script_json(sid)
        if not script_json:
            raise Exception("未找到剧本数据")

        title = script_json.get("title", "")
        characters = script_json.get("characters", [])
        settings_list = script_json.get("settings", [])

        # 取所有分镜作为上下文
        last_shots = existing_shots

        # 构建上下文描述
        char_names = [c.get("name", "") for c in characters]
        # 只使用现有分镜中实际使用的场景位置
        used_locations = set(s.get("location", "") for s in existing_shots if s.get("location"))
        setting_names = [s.get("name", "") for s in settings_list if s.get("name", "") in used_locations]

        # 获取续写提示词
        is_zh = any('\u4e00' <= c <= '\u9fff' for c in title)
        prompt_template = _get_continue_prompt('zh' if is_zh else 'en')

        # 格式化已有分镜信息
        shots_context = ""
        for shot in last_shots:
            shots_context += f"- 场景{shot.get('scene_number')} 分镜{shot.get('shot_number')}: {shot.get('plot', '')}\n"

        prompt = prompt_template.format(
            title=title,
            style=style,
            characters=", ".join(char_names),
            settings=", ".join(setting_names),
            existing_shots=shots_context,
        )

        self._report_progress("分镜", "智能续写中...", 10)

        def run():
            llm = LLM()
            raw = self._cancellable_query(llm, prompt, model=llm_model, task_id=sid)
            new_shots = self._extract_json_array(raw)
            if not new_shots:
                raise Exception("续写失败，无法解析LLM输出")
            new_shots = self._validate_shots(new_shots)
            return new_shots

        loop = asyncio.get_running_loop()
        new_shots = await loop.run_in_executor(None, run)

        # 为新分镜添加全局标识
        last_scene = last_shots[-1] if last_shots else None
        next_scene_num = (last_scene.get("scene_number", 0) + 1) if last_scene else 1
        next_act = last_scene.get("act", 1) if last_scene else 1

        for i, shot in enumerate(new_shots):
            shot["shot_id"] = f"shot_{next_scene_num:03d}_{i + 1:02d}"
            shot["scene_number"] = next_scene_num
            shot["act"] = next_act
            shot["is_new"] = True  # 标记为新添加的分镜

        # 追加到已有分镜
        all_shots = existing_shots + new_shots

        # 保存（带有 is_new 标记，供前端识别）
        results.setdefault(str(sid), {})['storyboard'] = {
            'shots': all_shots,
            'user_modified': True,
            'new_shot_ids': [s["shot_id"] for s in new_shots],  # 记录新分镜ID
        }
        with open(result_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=4, ensure_ascii=False)

        self._report_progress("分镜", "续写完成", 100)

        return {
            "payload": {
                "session_id": sid,
                "shots": all_shots,
                "new_shots": new_shots,
                "new_shot_ids": [s["shot_id"] for s in new_shots],
                "continued": True,
            },
            "requires_intervention": True,
        }

    # ─── 核心流程 ───

    async def process(self, input_data: Any, intervention: Optional[Dict] = None) -> Dict:
        from config import settings
        from tool.llm_client import LLM

        sid = input_data["session_id"]
        style = input_data.get("style", "anime")
        llm_model = input_data.get("llm_model", "qwen3.5-plus")

        result_file = os.path.join(settings.RESULT_DIR, 'script', f'script_{sid}.json')

        # ── 用户修改了分镜 ──
        if intervention and "modified_storyboard" in intervention:
            modified_shots = intervention["modified_storyboard"]
            if isinstance(modified_shots, str):
                modified_shots = json.loads(modified_shots)

            with open(result_file, 'r', encoding='utf-8') as f:
                results = json.load(f)

            # 同步更新 script_json 中的 scenes
            # 获取修改后的 shots 中包含的场景编号
            new_scene_numbers = set(s.get("scene_number") for s in modified_shots if s.get("scene_number"))

            # 更新 script_json.scenes
            script_json = results.get(str(sid), {}).get('script_json', {})
            if script_json and 'scenes' in script_json:
                original_scenes = script_json.get('scenes', [])
                # 保留新分镜中包含的场景，按原始顺序
                filtered_scenes = [s for s in original_scenes if s.get('scene_number') in new_scene_numbers]
                # 重新编号（确保 scene_number 连续）
                for i, scene in enumerate(filtered_scenes, 1):
                    scene['scene_number'] = i
                script_json['scenes'] = filtered_scenes

            # 清除 new_shot_ids 标记，同时清除 is_new 标志
            for shot in modified_shots:
                if 'is_new' in shot:
                    shot['is_new'] = False
            storyboard_data = {
                'shots': modified_shots,
                'user_modified': True,
                'new_shot_ids': [],  # 清除新分镜标记
            }

            results.setdefault(str(sid), {})['storyboard'] = storyboard_data
            if script_json:
                results.setdefault(str(sid), {})['script_json'] = script_json
            with open(result_file, 'w', encoding='utf-8') as f:
                json.dump(results, f, indent=4, ensure_ascii=False)

            # 返回完整的 payload 包含 user_modified 和 new_shot_ids
            return {
                "payload": {
                    "session_id": sid,
                    "shots": modified_shots,
                    "user_modified": True,
                    "new_shot_ids": [],
                },
                "stage_completed": True,
            }

        # ── 用户点击"智能续写" ──
        if intervention and "continue_story" in intervention:
            return await self._continue_story(input_data, intervention["continue_story"])

        # ── 正常流程 ──
        script_json = self._read_script_json(sid)
        if not script_json:
            raise Exception("未找到剧本数据(script_json)，请先完成阶段1")

        scenes = script_json.get("scenes", [])
        characters = {c["name"]: c for c in script_json.get("characters", [])}
        settings_map = {s["name"]: s for s in script_json.get("settings", [])}

        is_zh = any('\u4e00' <= c <= '\u9fff' for c in script_json.get("title", ""))
        prompt_template = _get_prompt('SHOT_PROMPT_ZH') if is_zh else _get_prompt('SHOT_PROMPT_EN')

        self._report_progress("分镜", "读取剧本数据...", 5)

        # 获取并发数
        enable_concurrency = input_data.get("enable_concurrency", True)
        from config_model import get_max_concurrency
        # LLM 调用的并发数
        concurrency = get_max_concurrency("llm", enable_concurrency)
        logger.info(f"[StoryboardAgent] enable_concurrency={enable_concurrency}, concurrency={concurrency}")

        # 用于按场景顺序存储结果的字典
        shots_results: Dict[int, List[dict]] = {}
        done_count = 0
        total = len(scenes)

        def generate_one_scene(scene_index: int, scene: dict) -> tuple:
            """生成单个场景的分镜"""
            llm = LLM()
            sn = scene.get("scene_number", scene_index + 1)
            act = scene.get("act", 1)

            location = scene.get("location", "")
            scene_chars = scene.get("characters", [])
            plot = scene.get("plot", "")

            # 角色外貌描述
            char_descs = []
            for cn in scene_chars:
                c = characters.get(cn)
                if c:
                    char_descs.append(f"{cn}: {c.get('description', '')}")
            char_desc_text = "\n".join(char_descs) if char_descs else "无"

            # 场景环境描述
            setting_info = settings_map.get(location, {})
            setting_desc = setting_info.get("description", location)

            prompt = prompt_template.format(
                style=style,
                scene_number=sn,
                location=location,
                characters=", ".join(scene_chars),
                plot=plot,
                char_descriptions=char_desc_text,
                setting_description=setting_desc,
            )

            # 最多重试3次
            scene_shots = None
            for attempt in range(3):
                if hasattr(self, 'cancellation_check') and self.cancellation_check:
                    if self.cancellation_check():
                        break
                raw = self._cancellable_query(llm, prompt, model=llm_model, task_id=sid)
                parsed = self._extract_json_array(raw)
                if parsed:
                    scene_shots = self._validate_shots(parsed)
                    if scene_shots:
                        break
                logger.warning(f"Scene {sn} shot parse attempt {attempt+1} failed")

            if not scene_shots:
                # 降级: 整个场景作为一个分镜
                scene_shots = [{
                    "shot_number": 1,
                    "duration": 15,
                    "characters": scene_chars,
                    "location": location,
                    "plot": plot,
                    "visual_prompt": plot,
                }]

            # 为每个分镜添加全局标识
            for shot in scene_shots:
                shot["shot_id"] = f"shot_{sn:03d}_{shot['shot_number']:02d}"
                shot["scene_number"] = sn
                shot["act"] = act

            return scene_index, scene_shots, sn, act

        def run():
            nonlocal done_count
            # 检测是否有多幕结构（微电影模式只有一幕或无 act 字段）
            act_values = {s.get("act") for s in scenes}
            multi_act = len(act_values - {None}) > 1

            with ThreadPoolExecutor(max_workers=concurrency) as executor:
                futs = {}
                for i, scene in enumerate(scenes):
                    fut = executor.submit(generate_one_scene, i, scene)
                    futs[fut] = i

                # 按提交顺序收集结果（不是按完成顺序）
                for scene_index in range(len(scenes)):
                    # 找到对应的 future
                    found_future = None
                    for fut in futs:
                        if futs[fut] == scene_index:
                            found_future = fut
                            break

                    if found_future:
                        try:
                            idx, scene_shots, sn, act = found_future.result()
                            shots_results[idx] = scene_shots

                            # 报告进度
                            done_count += 1
                            pct = 5 + int(90 * done_count / max(total, 1))
                            if multi_act:
                                act_label = ACT_NAMES.get(act, f"第{act}幕")
                                self._report_progress("分镜", f"第{act}幕「{act_label}」 场景{sn}/{total}完成", pct)
                            else:
                                self._report_progress("分镜", f"场景{sn}完成 ({len(scene_shots)}个分镜)", pct)

                            # 发送逐场完成事件
                            self._report_progress(
                                "分镜",
                                f"场景{sn}完成 ({len(scene_shots)}个分镜)",
                                pct,
                                data={"scene_shots_complete": {
                                    "scene_number": sn,
                                    "act": act,
                                    "shots": scene_shots,
                                }},
                            )
                        except Exception as e:
                            logger.error(f"Scene {scene_index} generation error: {e}")
                            shots_results[scene_index] = []

            # 按场景顺序拼接所有分镜
            all_shots = []
            for i in range(len(scenes)):
                if i in shots_results:
                    all_shots.extend(shots_results[i])

            self._report_progress("分镜", "保存结果...", 96)

            # 写入结果文件
            with open(result_file, 'r', encoding='utf-8') as f:
                results = json.load(f)
            results.setdefault(str(sid), {})['storyboard'] = {
                'shots': all_shots,
            }
            with open(result_file, 'w', encoding='utf-8') as f:
                json.dump(results, f, indent=4, ensure_ascii=False)

            self._report_progress("分镜", "完成", 100)
            return {
                "payload": {
                    "session_id": sid,
                    "shots": all_shots,
                },
                "stage_completed": True,
            }

        loop = asyncio.get_running_loop()
        all_shots = await loop.run_in_executor(None, run)

        return {
            "payload": {
                "session_id": sid,
                "shots": all_shots,
            },
            "stage_completed": True,
        }
