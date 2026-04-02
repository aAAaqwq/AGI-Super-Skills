# -*- coding: utf-8 -*-
"""
阶段4: 参考图生成智能体
- 基于阶段3分镜(shots)，为每个分镜生成「首帧图像提示词」，再据此生成参考图
- 首帧提示词由 LLM 根据 shot 的 plot、visual_prompt、duration 生成
- 阶段5生视频时使用阶段3的原始分镜描述，而非首帧提示词
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
from prompts.loader import load_prompt

logger = logging.getLogger(__name__)


def ratio_to_size(ratio: str) -> str:
    """将视频比例转换为图像尺寸"""
    size_map = {
        "16:9": "1920*1080",
        "9:16": "1080*1920",
        "1:1": "1024*1024",
        "4:3": "1024*768",
        "3:4": "768*1024",
        "21:9": "2560*1080",
    }
    return size_map.get(ratio, "1920*1080")


class ReferenceGeneratorAgent(AgentInterface):
    """参考图生成：分镜(阶段3) → 首帧提示词(LLM) → 参考图(图像模型)"""

    def __init__(self):
        super().__init__(name="ReferenceGenerator")

    # ─── 版本管理 ───

    @staticmethod
    def _scenes_base(sid: str) -> str:
        return os.path.join('code/result/image', str(sid), 'Scenes')

    def _list_versions(self, sid: str, shot_id: str) -> List[str]:
        """列出某个分镜的所有历史版本
        命名: shot_001_01.jpg, shot_001_01_v2.jpg, ...
        """
        return self._list_versions_static(sid, shot_id)

    @staticmethod
    def _list_versions_static(sid: str, shot_id: str) -> List[str]:
        """列出某个分镜的所有历史版本（静态方法，供外部调用）"""
        scenes_dir = os.path.join('code/result/image', str(sid), 'Scenes')
        pattern = os.path.join(scenes_dir, f"{shot_id}*.jpg")
        files = sorted(glob.glob(pattern), key=os.path.getmtime)
        return files

    def _next_version_path(self, sid: str, shot_id: str) -> str:
        """获取下一个版本路径"""
        scenes_dir = self._scenes_base(sid)
        os.makedirs(scenes_dir, exist_ok=True)

        existing = self._list_versions(sid, shot_id)
        if not existing:
            return os.path.join(scenes_dir, f"{shot_id}.jpg")

        max_v = 1
        for fp in existing:
            bn = os.path.splitext(os.path.basename(fp))[0]
            m = re.search(r'_v(\d+)$', bn)
            if m:
                max_v = max(max_v, int(m.group(1)))

        return os.path.join(scenes_dir, f"{shot_id}_v{max_v + 1}.jpg")

    # ─── 素材匹配 ───

    @staticmethod
    def _build_asset_map(sid: str) -> Dict[str, Dict[str, str]]:
        """扫描阶段2生成的素材文件"""
        base = os.path.join('code/result/image', str(sid), 'Assets')
        am: Dict[str, Dict[str, str]] = {'characters': {}, 'settings': {}}
        for sub, key in [('characters', 'characters'), ('settings', 'settings')]:
            d = os.path.join(base, sub)
            if os.path.isdir(d):
                files = sorted(
                    [f for f in os.listdir(d) if f.endswith('.png')],
                    key=lambda f: os.path.getmtime(os.path.join(d, f))
                )
                for fn in files:
                    name = os.path.splitext(fn)[0]
                    base_id = re.sub(r'_v\d+$', '', name)
                    am[key][base_id] = os.path.join(d, fn)
        return am

    def _collect_refs(self, shot: dict, asset_map: dict,
                      char_id_map: dict, setting_id_map: dict) -> List[str]:
        """为一个分镜收集参考原图路径（角色 + 场景素材）"""
        refs = []
        for cn in shot.get('characters', []):
            cid = char_id_map.get(cn)
            if cid and cid in asset_map['characters']:
                refs.append(os.path.abspath(asset_map['characters'][cid]))
                logger.info(f"[{shot.get('shot_id', '')}] 添加角色参考图: {cn} -> {cid}")
        loc = shot.get('location', '')
        set_id = setting_id_map.get(loc)
        if set_id and set_id in asset_map['settings']:
            refs.append(os.path.abspath(asset_map['settings'][set_id]))
            logger.info(f"[{shot.get('shot_id', '')}] 添加场景参考图: {loc} -> {set_id}")
        else:
            logger.warning(f"[{shot.get('shot_id', '')}] 未找到场景参考图: location={loc}, set_id={set_id}, available_settings={list(asset_map['settings'].keys())}")
        logger.info(f"[{shot.get('shot_id', '')}] 共收集 {len(refs)} 张参考图")
        return refs[:10]

    def _get_descriptions(self, shot: dict, char_id_map: dict, setting_id_map: dict,
                          script_json: dict) -> tuple:
        """获取分镜中涉及的角色和场景描述

        Returns:
            (character_description, setting_description)
        """
        # 角色描述
        char_descs = []
        for cn in shot.get('characters', []):
            cid = char_id_map.get(cn, '')
            if cid:
                for c in script_json.get('characters', []):
                    if c.get('character_id') == cid:
                        desc = c.get('description', '')
                        visual = c.get('visual_description', '')
                        if visual:
                            char_descs.append(f"{cn}: {visual}")
                        elif desc:
                            char_descs.append(f"{cn}: {desc}")
                        break

        # 场景描述
        loc = shot.get('location', '')
        set_id = setting_id_map.get(loc)
        setting_desc = ""
        if set_id:
            for s in script_json.get('settings', []):
                if s.get('setting_id') == set_id:
                    setting_desc = s.get('description', '') or s.get('visual_description', '')
                    break

        return "； ".join(char_descs), setting_desc

    # ─── 首帧提示词生成 ───

    # ─── 预览构建 ───

    def _build_preview(self, sid: str, shots: list) -> list:
        """构建分镜预览列表（含当前状态）"""
        preview = []
        for idx, shot in enumerate(shots, 1):
            shot_id = shot['shot_id']
            versions = self._list_versions(sid, shot_id)
            preview.append({
                "id": shot_id,
                "name": f"场景{shot['scene_number']}-镜头{shot['shot_number']}",
                "index": idx,
                "description": shot.get('visual_prompt', ''),
                "selected": versions[-1] if versions else "",
                "versions": versions,
                "status": "done" if versions else "pending",
            })
        return preview

    # ─── 单张生成 ───

    def _generate_one(self, img_client, sid: str, shot: dict,
                      first_frame_prompt: str, refs: List[str],
                      style: str, it2i_model: str, t2i_model: str,
                      ref_size: str = "1920*1080", vlm_model: str = "qwen3.5-plus",
                      character_description: str = "", setting_description: str = "",
                      max_versions: int = 3) -> tuple:
        """生成单个分镜参考图，返回 (shot_id, path_or_None, eval_result)

        最多生成 max_versions 个版本，如果所有版本都没有达到8分，
        使用 VLM 选择最好的一张作为最终参考图。
        """
        shot_id = shot.get('shot_id', '')
        plot = shot.get('plot', '')
        visual_prompt = shot.get('visual_prompt', '')

        # 取消时直接跳过，不抛异常，以保留已生成的部分结果
        if self.cancellation_check and self.cancellation_check():
            logger.info(f"ReferenceGeneratorAgent: {shot_id} 跳过（用户取消）")
            return shot_id, None, None

        model = it2i_model if refs else t2i_model
        logger.info(f"[{shot_id}] 使用模型: {model}, 参考图数量: {len(refs) if refs else 0}")
        if refs:
            for i, r in enumerate(refs):
                logger.info(f"[{shot_id}] 参考图[{i}]: {r}")

        # 收集所有生成的版本
        all_versions = []
        all_eval_results = []

        for version in range(max_versions):
            self._check_cancel()

            full_prompt = (
                f"{style} style, masterpiece, cinematic composition, "
                f"best quality, high resolution, "
                f"{first_frame_prompt}"
            )

            save_path = self._next_version_path(sid, shot_id)
            save_dir = os.path.dirname(save_path)

            try:
                paths = img_client.generate_image(
                    prompt=full_prompt,
                    image_paths=refs if refs else None,
                    model=model,
                    session_id=str(sid),
                    save_dir=save_dir,
                    size=ref_size,
                )
                if not paths:
                    continue

                gen = paths[0]
                if gen != save_path:
                    if os.path.exists(save_path):
                        os.remove(save_path)
                    os.rename(gen, save_path)

                # VLM 评估
                eval_result = self._evaluate_with_vlm(save_path, shot,
                                                      character_description=character_description,
                                                      setting_description=setting_description,
                                                      vlm_model=vlm_model)

                score = eval_result.get('score', 0)
                is_acceptable = score >= 8

                logger.info(f"[{shot_id}] 版本{version + 1}: 评分 {score}/10, {'✓通过' if is_acceptable else '✗不通过'}")

                # 记录版本信息
                all_versions.append(save_path)
                all_eval_results.append(eval_result)

                # 如果达到8分，立即返回
                if is_acceptable:
                    return shot_id, save_path, eval_result

                # 报告进度
                if version < max_versions - 1:
                    self._report_progress("参考图", f"重新生成中 ({version + 2}/{max_versions}): {shot_id}", 0)

            except Exception as e:
                logger.error(f"Shot {shot_id} image generation failed: {e}")

        # 所有版本都没有达到8分，使用 VLM 选择最好的
        if all_versions:
            logger.warning(f"[{shot_id}] 所有版本都未达到8分，使用VLM选择最佳...")
            best_path, best_eval = self._select_best_with_vlm(
                all_versions, shot,
                character_description=character_description,
                setting_description=setting_description,
                vlm_model=vlm_model
            )
            if best_path:
                return shot_id, best_path, best_eval

        # 如果没有任何生成成功
        logger.warning(f"[{shot_id}] 没有成功生成任何图片")
        return shot_id, None, None

    def _select_best_with_vlm(self, image_paths: List[str], shot: dict,
                              character_description: str = "", setting_description: str = "",
                              vlm_model: str = "qwen3.5-plus") -> tuple:
        """使用 VLM 从多个版本中选择最好的一张"""
        from tool.vlm_client import VLM

        if not image_paths:
            return None, None

        shot_id = shot.get('shot_id', '')
        plot = shot.get('plot', '')
        visual_prompt = shot.get('visual_prompt', '')

        # 加载评估提示词
        select_prompt = load_prompt('reference', 'eval_select_best', 'zh').format(
            num_images=len(image_paths),
            num_images_minus_1=len(image_paths) - 1,
            plot=plot,
            visual_prompt=visual_prompt,
            character_description=character_description,
            setting_description=setting_description,
            images_list="\n".join([f"图片{i}: {p}" for i, p in enumerate(image_paths)])
        )

        try:
            vlm = VLM()
            result = vlm.query(select_prompt, image_paths=image_paths, model=vlm_model)
            logger.info(f"[{shot_id}] VLM选择结果: {result}")

            # 解析 JSON 结果
            import re
            json_match = re.search(r'\{[^{}]*\}', result, re.DOTALL)
            if json_match:
                selected = json.loads(json_match.group())
                selected_idx = selected.get('selected_index', 0)
                if 0 <= selected_idx < len(image_paths):
                    best_path = image_paths[selected_idx]
                    logger.info(f"[{shot_id}] VLM选择第{selected_idx + 1}张作为最佳图片")
                    # 构建评估结果
                    best_eval = {
                        "score": selected.get('score', 5),
                        "issues": selected.get('issues', []),
                        "is_acceptable": True,
                        "selected_by_vlm": True,
                        "reason": selected.get('reason', '')
                    }
                    return best_path, best_eval

        except Exception as e:
            logger.error(f"[{shot_id}] VLM选择最佳图片失败: {e}")

        # 如果失败，返回第一个版本
        return image_paths[0], {"score": 5, "issues": [], "selected_by_vlm": False}

    def _evaluate_with_vlm(self, image_path: str, shot: dict,
                          character_description: str = "", setting_description: str = "",
                          vlm_model: str = "qwen3.5-plus") -> dict:
        """使用 VLM 评估首帧参考图"""
        try:
            from tool.vlm_client import VLM
            vlm = VLM()

            eval_prompt = load_prompt('reference', 'eval_first_frame', 'zh').format(
                plot=shot.get('plot', ''),
                visual_prompt=shot.get('visual_prompt', ''),
                character_description=character_description,
                setting_description=setting_description
            )

            result = vlm.query(
                prompt=eval_prompt,
                image_paths=[image_path],
                model=vlm_model
            )

            if result and isinstance(result, list):
                result_text = result[0] if result else ""
            elif isinstance(result, str):
                result_text = result
            else:
                result_text = str(result)

            import json
            try:
                import re
                json_match = re.search(r'\{[^{}]*\}', result_text, re.DOTALL)
                if json_match:
                    eval_result = json.loads(json_match.group())
                    return eval_result
            except:
                pass

            return {"score": 5, "issues": ["评估解析失败"], "is_acceptable": True}

        except Exception as e:
            logger.warning(f"VLM evaluation failed: {e}")
            return {"score": 5, "issues": [str(e)], "is_acceptable": True}

    # ─── 构建最终 payload ───

    def _build_payload(self, sid: str, shots: list) -> dict:
        """构建最终 payload"""
        scenes = []
        for idx, shot in enumerate(shots, 1):
            shot_id = shot['shot_id']
            versions = self._list_versions(sid, shot_id)
            # status: 有图片=done, 无图片=pending(待生成)
            status = "done" if versions else "pending"
            scenes.append({
                "id": shot_id,
                "name": f"场景{shot['scene_number']}-镜头{shot['shot_number']}",
                "index": idx,
                "description": shot.get('visual_prompt', ''),
                "selected": versions[-1] if versions else "",
                "versions": versions,
                "status": status,
            })
        return {
            "payload": {
                "session_id": sid,
                "scenes": scenes,
            },
            "stage_completed": True,
        }

    def _update_scene2image(self, sid: str, shots: list, result_file: str,
                            first_frame_prompts: dict) -> None:
        """写回 scene2image 到结果文件
        scene2image[shot_id] = {
            local_path: 当前最新版本图片路径,
            prompt: 首帧图像提示词(阶段4生成),
            plot: 原始分镜剧情描述(阶段3，供阶段5视频使用),
            video_prompt: 原始分镜视觉描述(阶段3),
            duration: 分镜时长,
        }
        """
        with open(result_file, 'r', encoding='utf-8') as f:
            res = json.load(f)
        scene_images = {}
        for shot in shots:
            shot_id = shot['shot_id']
            versions = self._list_versions(sid, shot_id)
            if versions:
                scene_images[shot_id] = {
                    "local_path": versions[-1],
                    "prompt": first_frame_prompts.get(shot_id, shot.get('visual_prompt', '')),
                    "plot": shot.get('plot', ''),
                    "video_prompt": shot.get('visual_prompt', ''),
                    "duration": shot.get('duration', 10),
                }
        res[str(sid)]['scene2image'] = scene_images
        with open(result_file, 'w', encoding='utf-8') as f:
            json.dump(res, f, indent=4, ensure_ascii=False)

    # ─── 核心流程 ───

    async def process(self, input_data: Any, intervention: Optional[Dict] = None) -> Dict:
        from config import settings
        from tool.image_client import ImageClient
        from tool.llm_client import LLM

        sid = input_data["session_id"]
        style = input_data.get("style", "anime")
        video_ratio = input_data.get("video_ratio", "16:9")
        ref_size = ratio_to_size(video_ratio)
        llm_model = input_data.get("llm_model", "") or settings.LLM_MODEL
        t2i = input_data.get("image_t2i_model", "") or settings.IMAGE_T2I_MODEL
        it2i = input_data.get("image_it2i_model", "") or settings.IMAGE_IT2I_MODEL
        vlm_model = input_data.get("vlm_model", "") or settings.VLM_MODEL
        # 根据 enable_concurrency 决定并发数
        enable_concurrency = input_data.get("enable_concurrency", True)
        logger.info(f"[ReferenceAgent] enable_concurrency={enable_concurrency}")
        # 取 t2i 和 it2i 中的最大并发数
        from config_model import get_max_concurrency
        max_t2i = get_max_concurrency(t2i, enable_concurrency)
        max_it2i = get_max_concurrency(it2i, enable_concurrency)
        concurrency = max(max_t2i, max_it2i)
        logger.info(f"[ReferenceAgent] 使用并发数={concurrency}")

        result_file = os.path.join(settings.RESULT_DIR, 'script', f'script_{sid}.json')

        img_client = ImageClient(
            dashscope_api_key=settings.DASHSCOPE_API_KEY,
            dashscope_base_url=settings.DASHSCOPE_BASE_URL,
            gpt_api_key=os.getenv("OPENAI_API_KEY"),
            gpt_base_url=os.getenv("OPENAI_BASE_URL"),
            gpt_official_api_key=settings.OPENAI_OFFICIAL_API_KEY,
            local_proxy=settings.LOCAL_PROXY,
            ark_api_key=settings.ARK_API_KEY,
            ark_base_url=settings.ARK_BASE_URL,
        )

        # 读取数据
        with open(result_file, 'r', encoding='utf-8') as f:
            results = json.load(f)
        story_data = results[str(sid)]

        storyboard = story_data.get('storyboard', {})
        shots = storyboard.get('shots', [])
        if not shots:
            raise Exception("未找到分镜数据(storyboard.shots)，请先完成阶段3")

        script_json = story_data.get('script_json', {})

        # 判断中英文
        is_zh = any('\u4e00' <= c <= '\u9fff' for c in script_json.get("title", ""))

        # 构建 name → id 映射（用于素材匹配）
        char_id_map = {}
        for c in script_json.get('characters', []):
            char_id_map[c['name']] = c.get('character_id', '')

        setting_id_map = {}
        for s in script_json.get('settings', []):
            setting_id_map[s['name']] = s.get('setting_id', '')

        asset_map = self._build_asset_map(sid)

        # ═══ 介入：重新生成指定分镜 ═══
        if intervention:
            regen_scenes = intervention.get("regenerate_scenes", [])

            if regen_scenes:
                self._report_progress("参考图", "重新生成中...", 2)

                # 重新从 session JSON 文件读取最新的 storyboard 数据
                with open(result_file, 'r', encoding='utf-8') as f:
                    fresh_data = json.load(f)
                fresh_storyboard = fresh_data.get(str(sid), {}).get('storyboard', {})
                fresh_shots = fresh_storyboard.get('shots', [])
                fresh_shot_map = {s['shot_id']: s for s in fresh_shots}

                llm = LLM()

                def regen_run():
                    total = len(regen_scenes)
                    done = 0
                    # 每分镜5个步骤：准备(1)、生成(3)、完成(1)
                    steps_per_shot = 5
                    total_steps = total * steps_per_shot

                    def calc_pct_regen(step: int) -> int:
                        return min(2 + int(98 * step / total_steps), 100)

                    # 从最新读取的 storyboard JSON 中获取 visual_prompt
                    prompt_map = {}  # shot_id → first_frame_prompt
                    for i, shot_id in enumerate(regen_scenes):
                        shot = fresh_shot_map.get(shot_id, {})
                        ff_prompt = shot.get('visual_prompt', '')
                        prompt_map[shot_id] = ff_prompt
                        logger.info(f"[{shot_id}] first-frame prompt (from JSON): {ff_prompt[:80]}...")
                        self._report_progress("参考图", f"准备提示词: {shot_id}", calc_pct_regen(i * steps_per_shot + 1))

                    # 并发生成图像
                    self._report_progress("参考图", "生成参考图...", calc_pct_regen(total * 2))
                    with ThreadPoolExecutor(max_workers=concurrency) as executor:
                        futs = {}
                        for shot_id in regen_scenes:
                            shot = fresh_shot_map.get(shot_id, {})
                            refs = self._collect_refs(shot, asset_map, char_id_map, setting_id_map)
                            char_desc, set_desc = self._get_descriptions(
                                shot, char_id_map, setting_id_map, script_json
                            )
                            fut = executor.submit(
                                self._generate_one, img_client, sid,
                                shot, prompt_map[shot_id], refs,
                                style, it2i, t2i, ref_size, vlm_model,
                                character_description=char_desc, setting_description=set_desc
                            )
                            futs[fut] = shot_id
                        for fut in as_completed(futs):
                            shot_id_done = futs[fut]
                            try:
                                _, result_path, eval_result = fut.result()
                            except Exception as e:
                                logger.error(f"Regen future error for {shot_id_done}: {e}")
                                result_path = None
                            done += 1
                            step = done * steps_per_shot
                            pct = calc_pct_regen(step)
                            if result_path:
                                versions = self._list_versions(sid, shot_id_done)
                                self._report_progress("参考图", f"完成: {shot_id_done}", pct, data={
                                    "asset_complete": {
                                        "type": "scenes", "id": shot_id_done,
                                        "status": "done",
                                        "selected": result_path,
                                        "versions": versions,
                                    }
                                })
                            else:
                                self._report_progress("参考图", f"失败: {shot_id_done}", pct, data={
                                    "asset_complete": {
                                        "type": "scenes", "id": shot_id_done,
                                        "status": "failed",
                                        "selected": "", "versions": [],
                                    }
                                })
                            # 检查取消
                            if self.cancellation_check and self.cancellation_check():
                                logger.info("ReferenceGeneratorAgent: 用户取消重新生成，停止等待剩余任务")
                                for f in futs:
                                    if not f.done():
                                        f.cancel()
                                break

                loop = asyncio.get_running_loop()
                await loop.run_in_executor(None, regen_run)

            # 重新生成后更新 scene2image（同步最新版本信息）
            self._update_scene2image(sid, shots, result_file, {})

            self._report_progress("参考图", "完成", 100)
            return self._build_payload(sid, shots)

        # ═══ 正常流程：全量生成 ═══
        self._report_progress("参考图", "加载分镜数据...", 5)

        # 发送预览列表
        preview = self._build_preview(sid, shots)
        self._report_progress("参考图", "加载分镜列表", 8, data={"assets_preview": {"scenes": preview}})

        llm = LLM()

        def run():
            # 筛选需要生成的（跳过已有图的）
            pending_shots = []
            for shot in shots:
                shot_id = shot['shot_id']
                existing = self._list_versions(sid, shot_id)
                if existing:
                    continue
                pending_shots.append(shot)

            if not pending_shots:
                self._report_progress("参考图", "所有分镜图已存在", 95)
                return

            total = len(pending_shots)
            # 每分镜5个步骤：准备(1)、生成(3)、完成(1)
            steps_per_shot = 5
            total_steps = total * steps_per_shot + 1  # +1 是加载数据步骤

            def calc_pct(step: int) -> int:
                """根据步骤计算进度百分比"""
                return min(2 + int(98 * step / total_steps), 100)

            done = 0

            # 步骤1：加载数据
            self._report_progress("参考图", "准备生成...", calc_pct(0))

            # 步骤2-6(每分镜)：准备提示词
            first_frame_prompts = {}  # shot_id → prompt
            for i, shot in enumerate(pending_shots):
                shot_id = shot['shot_id']
                ff_prompt = shot.get('visual_prompt', '')
                first_frame_prompts[shot_id] = ff_prompt
                logger.info(f"[{shot_id}] first-frame prompt: {ff_prompt[:80]}...")
                step = i * steps_per_shot + 1
                self._report_progress("参考图", f"准备提示词: {shot_id}", calc_pct(step))

            # 步骤7+(每分镜3步)：并发生成图像
            self._report_progress("参考图", "生成参考图...", calc_pct(total * 2))
            tasks = []
            for shot in pending_shots:
                shot_id = shot['shot_id']
                refs = self._collect_refs(shot, asset_map, char_id_map, setting_id_map)
                char_desc, set_desc = self._get_descriptions(
                    shot, char_id_map, setting_id_map, script_json
                )
                tasks.append((shot, first_frame_prompts[shot_id], refs, char_desc, set_desc))

            with ThreadPoolExecutor(max_workers=concurrency) as executor:
                futs = {}
                for shot, ff_prompt, refs, char_desc, set_desc in tasks:
                    shot_id = shot['shot_id']
                    fut = executor.submit(
                        self._generate_one, img_client, sid,
                        shot, ff_prompt, refs,
                        style, it2i, t2i, ref_size, vlm_model,
                        character_description=char_desc, setting_description=set_desc
                    )
                    futs[fut] = shot_id
                cancelled = False
                for fut in as_completed(futs):
                    shot_id_done = futs[fut]
                    try:
                        _, result_path, eval_result = fut.result()
                    except Exception as e:
                        logger.error(f"Image future error for {shot_id_done}: {e}")
                        result_path = None
                    done += 1
                    # 每个分镜完成时更新进度
                    step = done * steps_per_shot
                    pct = calc_pct(step)
                    if result_path:
                        versions = self._list_versions(sid, shot_id_done)
                        self._report_progress("参考图", f"完成: {shot_id_done}", pct, data={
                            "asset_complete": {
                                "type": "scenes", "id": shot_id_done,
                                "status": "done",
                                "selected": result_path,
                                "versions": versions,
                            }
                        })
                    else:
                        self._report_progress("参考图", f"失败: {shot_id_done}", pct, data={
                            "asset_complete": {
                                "type": "scenes", "id": shot_id_done,
                                "status": "failed",
                                "selected": "", "versions": [],
                            }
                        })
                    # 检查取消
                    if self.cancellation_check and self.cancellation_check():
                        logger.info("ReferenceGeneratorAgent: 用户取消，停止等待剩余任务")
                        for f in futs:
                            if not f.done():
                                f.cancel()
                        cancelled = True
                        break

            if cancelled:
                self._report_progress("参考图", "已取消（保留已完成图片）", 96)
            else:
                self._report_progress("参考图", "保存结果...", 96)

            # 写回结果文件
            self._update_scene2image(sid, shots, result_file, first_frame_prompts)

        loop = asyncio.get_running_loop()
        try:
            await loop.run_in_executor(None, run)
        except Exception as e:
            if "cancel" in str(e).lower():
                logger.info("ReferenceGeneratorAgent: 用户取消，返回已完成���部分结果")
                self._report_progress("参考图", "已取消（保留已完成图片）", 100)
                return self._build_payload(sid, shots)
            raise

        self._report_progress("参考图", "完成", 100)
        return self._build_payload(sid, shots)
