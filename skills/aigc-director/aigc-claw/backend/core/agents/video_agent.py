# -*- coding: utf-8 -*-
"""
阶段5: 视频生成智能体
分镜参考图 → 各分镜视频片段
- 视频提示词使用阶段3的原始分镜剧情描述(plot)，而非视觉描述或首帧图像提示词
- 参考图使用用户在阶段4选择的版本，而非第一版
- 支持逐项实时预览、重新生成、多版本管理
"""

import os
import re
import glob
import json
import asyncio
import logging
from typing import Any, Optional, Dict, List
from concurrent.futures import ThreadPoolExecutor, as_completed

from .base_agent import AgentInterface

logger = logging.getLogger(__name__)


class VideoDirectorAgent(AgentInterface):
    """视频生成：分镜参考图(阶段4用户选择) + 分镜剧情描述(阶段3 plot) → 视频片段"""

    def __init__(self):
        super().__init__(name="VideoDirector")

    # ─── 版本管理 ───

    @staticmethod
    def _video_base(sid: str) -> str:
        return os.path.join('code/result/video', str(sid))

    def _list_versions(self, sid: str, shot_id: str) -> List[str]:
        """列出某个分镜视频的所有历史版本"""
        video_dir = self._video_base(sid)
        pattern = os.path.join(video_dir, f"{shot_id}*.mp4")
        files = [f for f in sorted(glob.glob(pattern), key=os.path.getmtime)
                 if not f.endswith('_final.mp4')]
        return files

    def _next_version_path(self, sid: str, shot_id: str) -> str:
        """获取下一个版本路径"""
        video_dir = self._video_base(sid)
        os.makedirs(video_dir, exist_ok=True)

        existing = self._list_versions(sid, shot_id)
        if not existing:
            return os.path.join(video_dir, f"{shot_id}.mp4")

        max_v = 1
        for fp in existing:
            bn = os.path.splitext(os.path.basename(fp))[0]
            m = re.search(r'_v(\d+)$', bn)
            if m:
                max_v = max(max_v, int(m.group(1)))

        return os.path.join(video_dir, f"{shot_id}_v{max_v + 1}.mp4")

    # ─── 视频生成 ───

    def _generate_one(self, sid: str, shot_id: str, prompt: str,
                      img_path: str, video_model: str,
                      duration: int = 5, sound: str = "",
                      shot_type: str = "multi") -> tuple:
        """生成单个分镜视频，返回 (shot_id, path_or_None)"""
        # 取消时直接跳过，不抛异常，以保留已生成的部分结果
        if self.cancellation_check and self.cancellation_check():
            logger.info(f"VideoDirectorAgent: {shot_id} 跳过（用户取消）")
            return shot_id, None

        if not os.path.exists(img_path):
            logger.warning(f"Image missing for {shot_id}: {img_path}")
            return shot_id, None

        save_path = self._next_version_path(sid, shot_id)
        try:
            from tool.video_client import VideoClient
            client = VideoClient()
            client.generate_video(
                prompt=prompt,
                image_path=img_path,
                save_path=save_path,
                model=video_model,
                duration=duration,
                sound=sound,
                shot_type=shot_type,
            )
            return shot_id, save_path
        except Exception as e:
            logger.error(f"Video gen failed for {shot_id}: {e}")
            if os.path.exists(save_path):
                try:
                    os.remove(save_path)
                except Exception:
                    pass
        return shot_id, None

    # ─── 排序 ───

    @staticmethod
    def _sort_shot_keys(keys: list) -> list:
        """对 shot_id 排序: shot_001_01, shot_001_02, shot_002_01, ..."""
        def sort_key(k):
            nums = re.findall(r'(\d+)', k)
            return tuple(int(n) for n in nums) if nums else (0,)
        return sorted(keys, key=sort_key)

    # ─── 预览 / Payload 构建 ───

    @staticmethod
    def _shot_display_name(shot_id: str) -> str:
        """shot_001_02 → 场景1-镜头2"""
        nums = re.findall(r'(\d+)', shot_id)
        if len(nums) >= 2:
            return f"场景{int(nums[0])}-镜头{int(nums[1])}"
        elif len(nums) == 1:
            return f"场景{int(nums[0])}"
        return shot_id

    def _build_preview(self, sid: str, shot_keys: list, s2i: dict) -> list:
        """构建视频片段预览列表"""
        preview = []
        for idx, shot_id in enumerate(shot_keys, 1):
            versions = self._list_versions(sid, shot_id)
            entry = s2i.get(shot_id, {})
            desc = entry.get('plot', '') or entry.get('video_prompt', '') or entry.get('prompt', '')
            preview.append({
                "id": shot_id,
                "name": self._shot_display_name(shot_id),
                "index": idx,
                "description": desc,
                "duration": entry.get('duration', 5),
                "selected": versions[-1] if versions else "",
                "versions": versions,
                "status": "done" if versions else "pending",
            })
        return preview

    def _build_payload(self, sid: str, shot_keys: list, s2i: dict, clip_descriptions: dict = None) -> dict:
        """构建最终 payload

        Args:
            clip_descriptions: 用户修改的提示词，优先使用
        """
        clips = []
        for idx, shot_id in enumerate(shot_keys, 1):
            versions = self._list_versions(sid, shot_id)
            entry = s2i.get(shot_id, {})
            # 优先使用用户修改的描述，否则用 scene2image 中的原始描述
            if clip_descriptions and shot_id in clip_descriptions:
                desc = clip_descriptions[shot_id]
            else:
                desc = entry.get('plot', '') or entry.get('video_prompt', '') or entry.get('prompt', '')
            clips.append({
                "id": shot_id,
                "name": self._shot_display_name(shot_id),
                "index": idx,
                "description": desc,
                "duration": entry.get('duration', 5),
                "selected": versions[-1] if versions else "",
                "versions": versions,
                "status": "done" if versions else "failed",
            })
        return {
            "payload": {
                "session_id": sid,
                "clips": clips,
            },
            "stage_completed": True,
        }

    # ─── 视频提示词前缀/后缀配置 ───

    # 尝试从模板文件加载前缀/后缀，失败则使用默认值
    _VIDEO_PROMPT_PREFIX = None
    _VIDEO_PROMPT_SUFFIX = None

    @classmethod
    def _load_video_enhance_prompt(cls) -> tuple:
        """加载视频提示词优化模板"""
        if cls._VIDEO_PROMPT_PREFIX is not None:
            return cls._VIDEO_PROMPT_PREFIX, cls._VIDEO_PROMPT_SUFFIX

        try:
            from prompts.loader import PROMPTS_DIR
            import os
            enhance_file = os.path.join(PROMPTS_DIR, 'video', 'enhance.txt')
            if os.path.exists(enhance_file):
                with open(enhance_file, 'r', encoding='utf-8') as f:
                    content = f.read()

                prefix = ""
                suffix = ""
                current_section = None

                for line in content.split('\n'):
                    line = line.strip()
                    if not line or line.startswith('#'):
                        continue
                    if line == '[prefix]':
                        current_section = 'prefix'
                    elif line == '[suffix]':
                        current_section = 'suffix'
                    elif line.startswith('[') and line.endswith(']'):
                        # 遇到新的 section（如 [style_keywords]），停止解析
                        current_section = None
                    elif current_section == 'prefix':
                        prefix += line + " "
                    elif current_section == 'suffix':
                        suffix += " " + line

                cls._VIDEO_PROMPT_PREFIX = prefix.strip()
                cls._VIDEO_PROMPT_SUFFIX = suffix.strip()
                logger.info(f"Loaded video enhance prompt from file: prefix={len(cls._VIDEO_PROMPT_PREFIX)} chars, suffix={len(cls._VIDEO_PROMPT_SUFFIX)} chars")
                return cls._VIDEO_PROMPT_PREFIX, cls._VIDEO_PROMPT_SUFFIX
        except Exception as e:
            logger.warning(f"Failed to load video enhance prompt: {e}")

        # 默认值
        cls._VIDEO_PROMPT_PREFIX = (
            "high quality, detailed, cinematic footage, smooth motion, natural movement, "
        )
        cls._VIDEO_PROMPT_SUFFIX = (
            ", realistic, no blur, no distortion, professional lighting, film grain"
        )
        return cls._VIDEO_PROMPT_PREFIX, cls._VIDEO_PROMPT_SUFFIX

    # 视频API字符限制（可灵2500，万象也类似）
    MAX_PROMPT_LENGTH = 2500

    # ─── 风格关键词映射 ───
    # 根据项目风格添加对应的视觉描述词

    STYLE_VIDEO_KEYWORDS = {
        # 动漫/动画风格
        "anime": "anime style, animated, cel-shaded, vibrant colors, manga aesthetic, ",
        "cartoon": "cartoon style, animated, colorful, fun, children's book illustration, ",
        # 写实风格
        "realistic": "photorealistic, realistic, natural lighting, detailed textures, cinema photography, ",
        "photorealistic": "photorealistic, realistic, natural lighting, detailed textures, cinema photography, ",
        # 3D 迪士尼风格
        "3d-disney": "3D animation, Disney style, pixar, CGI, smooth textures, computer generated, ",
        "3d": "3D animation, CGI, computer generated, smooth textures, digital cinema, ",
        # 油画风格
        "oil-painting": "oil painting style, impasto, classical art, painterly, rich brushstrokes, ",
        "watercolor": "watercolor style, delicate, soft colors, artistic, flowing, ",
        # 漫画风格
        "comic-book": "comic book style, vibrant, bold outlines, pop art, graphic novel, ",
        # 赛博朋克
        "cyberpunk": "cyberpunk, neon lights, futuristic, dark atmosphere, sci-fi, ",
        # 中国风
        "chinese-ink": "Chinese ink painting style, traditional, minimalist, brush strokes, oriental art, ",
        "ink": "Chinese ink painting style, traditional, minimalist, brush strokes, oriental art, ",
    }

    def _get_style_keywords(self, sid: str) -> str:
        """获取项目风格对应的视频关键词"""
        try:
            from config import settings
            result_file = os.path.join(settings.RESULT_DIR, 'script', f'script_{sid}.json')
            if os.path.exists(result_file):
                with open(result_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                session_data = data.get(str(sid), {})
                style = session_data.get('overall_style', '').lower().strip()
                if style and style in self.STYLE_VIDEO_KEYWORDS:
                    logger.info(f"Using style keywords for video: {style}")
                    return self.STYLE_VIDEO_KEYWORDS[style]
        except Exception as e:
            logger.debug(f"Could not get style for video prompt: {e}")
        return ""

    # ─── 辅助：获取分镜的视频提示词和参考图路径 ───

    def _enhance_video_prompt(self, base_prompt: str, sid: str = None) -> str:
        """
        增强视频提示词：添加前缀后缀优化生成效果
        不截断，发送完整提示词给API
        """
        if not base_prompt:
            return base_prompt

        prefix, suffix = self._load_video_enhance_prompt()
        base_lower = base_prompt.lower().strip()

        # 获取风格关键词
        style_keywords = ""
        if sid:
            style_keywords = self._get_style_keywords(sid)

        # 获取对话语言要求
        dialog_language = ""
        if sid:
            from config import settings
            import os
            script_file = os.path.join(settings.RESULT_DIR, 'script', f'script_{sid}.json')
            if os.path.exists(script_file):
                import json
                with open(script_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    script_data = data.get(str(sid), {})
                    # title 可能在 script_json 子对象中
                    title = script_data.get('title') or script_data.get('script_json', {}).get('title', '')
                    # 判断语言：检查标题是否包含中文字符
                    is_zh = any('\u4e00' <= c <= '\u9fff' for c in title)
                    if is_zh:
                        dialog_language = "注意：人物对话必须使用中文，不要使用英文。"
                    else:
                        dialog_language = "Note: Character dialogues must be in English."

        # 构建增强后的提示词
        # 检查是否已包含前缀关键词
        has_prefix = any(kw in base_lower for kw in ["high quality", "cinematic", "smooth motion", "anime", "photorealistic"])
        # 检查是否已包含后缀关键词
        has_suffix = any(kw in base_lower for kw in ["film grain", "realistic", "professional lighting", "masterpiece"])

        enhanced = base_prompt.strip()

        # 添加对话语言要求
        if dialog_language:
            enhanced = enhanced + " " + dialog_language

        # 添加风格关键词（前缀之前）
        if style_keywords:
            enhanced = style_keywords + enhanced

        if prefix and not has_prefix:
            enhanced = prefix + enhanced

        if suffix and not has_suffix:
            enhanced = enhanced + suffix

        logger.info(f"Video prompt enhanced: {len(base_prompt)} -> {len(enhanced)} chars")
        # 不截断，发送完整提示词
        return enhanced

    def _get_shot_prompt(self, entry: dict, enhance: bool = True, sid: str = None, shot_id: str = None, clip_descriptions: dict = None) -> str:
        """获取视频提示词：优先用用户修改的提示词，其次用 plot（剧情描述），兼容旧数据回退到 video_prompt"""
        # 优先使用用户修改的提示词
        if not shot_id:
            shot_id = entry.get('shot_id') or entry.get('id', '')
        if clip_descriptions and shot_id and clip_descriptions.get(shot_id):
            base_prompt = clip_descriptions[shot_id]
        else:
            base_prompt = entry.get('plot', '') or entry.get('video_prompt', '') or entry.get('prompt', '')
        if enhance:
            return self._enhance_video_prompt(base_prompt, sid)
        return base_prompt

    def _get_shot_image(self, sid: str, shot_id: str, entry: dict,
                        selected_images: dict) -> str:
        """获取参考图路径：优先用前端传入的用户选择，再用 scene2image 的 local_path，
        最后回退到扫描磁盘最新版本"""
        # 1. 前端传入的用户选择（stage 4 确认时携带）
        if selected_images.get(shot_id):
            path = selected_images[shot_id]
            if os.path.exists(path):
                return path
            logger.warning(f"selected_images path missing for {shot_id}: {path}")

        # 2. scene2image 中的 local_path
        local_path = entry.get('local_path', '')
        if local_path and os.path.exists(local_path):
            return local_path

        # 3. 回退：扫描磁盘，使用最新版本
        from core.agents.reference_agent import ReferenceGeneratorAgent
        versions = ReferenceGeneratorAgent._list_versions_static(sid, shot_id)
        if versions:
            logger.info(f"Fallback to latest version for {shot_id}: {versions[-1]}")
            return versions[-1]

        # 4. 最终回退：默认路径
        return os.path.join('code/result/image', str(sid), 'Scenes', f"{shot_id}.jpg")

    # ─── 核心流程 ───

    async def process(self, input_data: Any, intervention: Optional[Dict] = None) -> Dict:
        from config import settings

        sid = input_data["session_id"]
        video_model = input_data.get("video_model", "") or settings.VIDEO_MODEL
        # 根据 enable_concurrency 决定并发数
        enable_concurrency = input_data.get("enable_concurrency", True)
        from config_model import get_max_concurrency
        concurrency = get_max_concurrency(video_model, enable_concurrency)
        selected_images = input_data.get("selected_images", {})
        # 优先使用 input_data 中已有的 clips（包含用户修改的 description）
        existing_clips = input_data.get("clips", [])
        clip_descriptions = {c['id']: c['description'] for c in existing_clips if c.get('id') and c.get('description')}
        video_sound = input_data.get("video_sound", "on")
        video_shot_type = input_data.get("video_shot_type", "multi")
        sound_param = "" if video_sound == "off" else video_sound

        logger.info(f"VideoDirectorAgent: sid={sid}, video_model={video_model}, sound={video_sound}, shot_type={video_shot_type}")

        result_file = os.path.join(settings.RESULT_DIR, 'script', f'script_{sid}.json')

        # 读取数据
        with open(result_file, 'r', encoding='utf-8') as f:
            results = json.load(f)
        story_data = results[str(sid)]

        s2i = story_data.get('scene2image', {})

        # 从 storyboard 获取时长数据（用户修改已同步到 clips 中）
        storyboard = story_data.get('storyboard', {})
        storyboard_shots_list = storyboard.get('shots', [])
        shot_duration_map = {s.get('shot_id'): s.get('duration', 10) for s in storyboard_shots_list if s.get('shot_id')}

        # 同步 scene2image 中的时长
        for shot_id in s2i:
            if shot_id in shot_duration_map:
                s2i[shot_id]['duration'] = shot_duration_map[shot_id]

        logger.info(f"VideoDirectorAgent: duration sync from storyboard: {list(shot_duration_map.keys())}")

        # 兼容 shot_xxx_xx 和旧 Scene_x 格式
        shot_keys = self._sort_shot_keys(list(s2i.keys()))
        total = len(shot_keys)

        logger.info(f"VideoDirectorAgent: total shots in scene2image = {total}, shot_keys = {shot_keys}")

        if not shot_keys:
            raise Exception("未找到场景图数据(scene2image)，请先完成阶段4")

        # ═══ 介入：重新生成指定片段 ═══
        if intervention:
            regen_clips = intervention.get("regenerate_clips", [])

            if regen_clips:
                self._report_progress("视频生成", "重新生成中...", 10)

                def regen_run():
                    regen_total = len(regen_clips)
                    done = 0
                    with ThreadPoolExecutor(max_workers=concurrency) as executor:
                        futs = {}
                        for shot_id in regen_clips:
                            entry = s2i.get(shot_id, {})
                            prompt = self._get_shot_prompt(entry, sid=sid, shot_id=shot_id, clip_descriptions=clip_descriptions)
                            img_path = self._get_shot_image(sid, shot_id, entry, selected_images)
                            shot_duration = entry.get('duration', 5)
                            fut = executor.submit(
                                self._generate_one, sid, shot_id, prompt,
                                img_path, video_model, shot_duration,
                                sound_param, video_shot_type
                            )
                            futs[fut] = shot_id
                        for fut in as_completed(futs):
                            shot_id_done = futs[fut]
                            try:
                                _, result_path = fut.result()
                            except Exception as e:
                                logger.error(f"Regen future error for {shot_id_done}: {e}")
                                result_path = None
                            done += 1
                            pct = 10 + int(85 * done / max(regen_total, 1))
                            if result_path:
                                versions = self._list_versions(sid, shot_id_done)
                                self._report_progress("视频生成", f"完成: {shot_id_done}", pct, data={
                                    "asset_complete": {
                                        "type": "clips", "id": shot_id_done,
                                        "status": "done",
                                        "selected": result_path,
                                        "versions": versions,
                                    }
                                })
                            else:
                                self._report_progress("视频生成", f"失败: {shot_id_done}", pct, data={
                                    "asset_complete": {
                                        "type": "clips", "id": shot_id_done,
                                        "status": "failed",
                                        "selected": "", "versions": [],
                                    }
                                })
                            # 检查取消：停止等待剩余任务
                            if self.cancellation_check and self.cancellation_check():
                                logger.info("VideoDirectorAgent: 用户取消重新生成，停止等待剩余任务")
                                for f in futs:
                                    if not f.done():
                                        f.cancel()
                                break

                loop = asyncio.get_running_loop()
                await loop.run_in_executor(None, regen_run)

            self._report_progress("视频生成", "完成", 100)
            return self._build_payload(sid, shot_keys, s2i, clip_descriptions)

        # ═══ 正常流程：全量生成 ═══
        self._report_progress("视频生成", "加载场景数据...", 5)

        # 发送预览列表
        preview = self._build_preview(sid, shot_keys, s2i)
        self._report_progress("视频生成", "加载视频列表", 8, data={"assets_preview": {"clips": preview}})

        def run():
            # 筛选需要生成的（跳过已有的）
            tasks = []
            for shot_id in shot_keys:
                existing = self._list_versions(sid, shot_id)
                if existing:
                    continue
                entry = s2i.get(shot_id, {})
                prompt = self._get_shot_prompt(entry, sid=sid, shot_id=shot_id, clip_descriptions=clip_descriptions)
                img_path = self._get_shot_image(sid, shot_id, entry, selected_images)
                shot_duration = entry.get('duration', 5)
                tasks.append((shot_id, prompt, img_path, shot_duration))

            if not tasks:
                self._report_progress("视频生成", "所有视频已存在", 95)
                return

            gen_total = len(tasks)
            done = 0

            cancelled = False
            with ThreadPoolExecutor(max_workers=concurrency) as executor:
                futs = {}
                for shot_id, prompt, img_path, shot_duration in tasks:
                    fut = executor.submit(
                        self._generate_one, sid, shot_id, prompt,
                        img_path, video_model, shot_duration,
                        sound_param, video_shot_type,
                    )
                    futs[fut] = shot_id
                for fut in as_completed(futs):
                    shot_id_done = futs[fut]
                    try:
                        _, result_path = fut.result()
                    except Exception as e:
                        logger.error(f"Video future error for {shot_id_done}: {e}")
                        result_path = None
                    done += 1
                    pct = 10 + int(85 * done / max(gen_total, 1))
                    if result_path:
                        versions = self._list_versions(sid, shot_id_done)
                        self._report_progress("视频生成", f"完成: {shot_id_done}", pct, data={
                            "asset_complete": {
                                "type": "clips", "id": shot_id_done,
                                "status": "done",
                                "selected": result_path,
                                "versions": versions,
                            }
                        })
                    else:
                        self._report_progress("视频生成", f"失败: {shot_id_done}", pct, data={
                            "asset_complete": {
                                "type": "clips", "id": shot_id_done,
                                "status": "failed",
                                "selected": "", "versions": [],
                            }
                        })
                    # 检查取消：停止等待剩余任务
                    if self.cancellation_check and self.cancellation_check():
                        logger.info("VideoDirectorAgent: 用户取消，停止等待剩余任务")
                        for f in futs:
                            if not f.done():
                                f.cancel()
                        cancelled = True
                        break

            if cancelled:
                self._report_progress("视频生成", "已取消（保留已完成片段）", 96)
            else:
                self._report_progress("视频生成", "保存结果...", 96)

            # 写回结果文件
            with open(result_file, 'r', encoding='utf-8') as f:
                res = json.load(f)
            i2v_data = {}
            for shot_id in shot_keys:
                versions = self._list_versions(sid, shot_id)
                entry = s2i.get(shot_id, {})
                if versions:
                    i2v_data[shot_id] = {
                        "video_prompt": self._get_shot_prompt(entry, sid=sid, shot_id=shot_id, clip_descriptions=clip_descriptions),
                        "input_path": self._get_shot_image(sid, shot_id, entry, selected_images),
                        "output_path": versions[-1],
                        "duration": entry.get('duration', 10),
                        "status": "done",
                    }
            res[str(sid)]['image2video'] = i2v_data
            with open(result_file, 'w', encoding='utf-8') as f:
                json.dump(res, f, indent=4, ensure_ascii=False)

        loop = asyncio.get_running_loop()
        try:
            await loop.run_in_executor(None, run)
        except Exception as e:
            # 即使异常也保留已完成的部分结果
            if "cancel" in str(e).lower():
                logger.info("VideoDirectorAgent: 用户取消，返回已完成的部分结果")
                self._report_progress("视频生成", "已取消（保留已完成片段）", 100)
                return self._build_payload(sid, shot_keys, s2i, clip_descriptions)
            raise

        self._report_progress("视频生成", "完成", 100)
        return self._build_payload(sid, shot_keys, s2i, clip_descriptions)