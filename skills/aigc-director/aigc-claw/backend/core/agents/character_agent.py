# -*- coding: utf-8 -*-
"""
阶段2: 角色/场景设计智能体
基于阶段1的剧本JSON生成角色4视图和场景全景图
支持单项重新生成、历史版本切换
图片以 character_id / setting_id 命名
"""

import os
import re
import json
import glob
import asyncio
import logging
from typing import Any, Optional, Dict, List
from concurrent.futures import ThreadPoolExecutor, as_completed

from .base_agent import AgentInterface
from prompts.loader import load_prompt, load_style_prompt

logger = logging.getLogger(__name__)


class CharacterDesignerAgent(AgentInterface):
    """角色/场景设计：从剧本JSON读取描述 → 生成角色4视图 + 场景全景图"""

    def __init__(self):
        super().__init__(name="CharacterDesigner")

    # ─── 提示词模板 ───

    @staticmethod
    def _char_prompt(name: str, desc: str, style: str, species: str = "") -> str:
        """角色4视图提示词 - 从风格提示词文件加载"""
        # 加载风格提示词模板
        template = load_style_prompt('character', style)
        # 替换角色信息
        return template.format(name=name, desc=desc)

    @staticmethod
    def _setting_prompt(name: str, desc: str, style: str) -> str:
        """场景全景图提示词 - 从风格提示词文件加载"""
        # 加载风格提示词模板
        template = load_style_prompt('setting', style)
        # 替换场景信息
        return template.format(name=name, desc=desc)

    # ─── 文件管理（基于唯一ID） ───

    @staticmethod
    def _asset_base(sid: str) -> str:
        return os.path.join('code/result/image', str(sid), 'Assets')

    def _list_versions(self, sid: str, asset_type: str, asset_id: str) -> List[str]:
        """列出某个素材的所有历史版本文件路径，按时间排序
        文件命名: {asset_id}.png, {asset_id}_v2.png, {asset_id}_v3.png, ...
        """
        adir = os.path.join(self._asset_base(sid), asset_type)
        pattern = os.path.join(adir, f"{asset_id}*.png")
        files = sorted(glob.glob(pattern), key=os.path.getmtime)
        return files

    def _next_version_path(self, sid: str, asset_type: str, asset_id: str) -> str:
        """获取下一个版本的文件路径"""
        adir = os.path.join(self._asset_base(sid), asset_type)
        os.makedirs(adir, exist_ok=True)

        existing = self._list_versions(sid, asset_type, asset_id)
        if not existing:
            return os.path.join(adir, f"{asset_id}.png")

        max_v = 1
        for fp in existing:
            bn = os.path.splitext(os.path.basename(fp))[0]
            m = re.search(r'_v(\d+)$', bn)
            if m:
                max_v = max(max_v, int(m.group(1)))

        return os.path.join(adir, f"{asset_id}_v{max_v + 1}.png")

    def _build_asset_info(self, sid: str, asset_type: str,
                          asset_id: str, name: str, desc: str,
                          selected_path: str = "") -> dict:
        """构建单个素材的信息（含所有历史版本）"""
        versions = self._list_versions(sid, asset_type, asset_id)
        if not selected_path and versions:
            selected_path = versions[-1]
        return {
            "id": asset_id,
            "name": name,
            "description": desc,
            "selected": selected_path,
            "versions": versions,
        }

    # ─── 图片生成 ───

    def _build_preview(self, sid: str, chars_desc: dict, sets_desc: dict) -> dict:
        """构建素材预览列表（含当前状态）用于前端实时显示"""
        preview = {"characters": [], "settings": []}
        for asset_id, info in chars_desc.items():
            existing = self._list_versions(sid, 'characters', asset_id)
            preview["characters"].append({
                "id": asset_id,
                "name": info.get("name", ""),
                "description": info.get("description", ""),
                "selected": existing[-1] if existing else "",
                "versions": existing,
                "status": "done" if existing else "pending",
            })
        for asset_id, info in sets_desc.items():
            existing = self._list_versions(sid, 'settings', asset_id)
            name = info.get("name", "") if isinstance(info, dict) else ""
            desc = info.get("description", "") if isinstance(info, dict) else str(info)
            preview["settings"].append({
                "id": asset_id,
                "name": name,
                "description": desc,
                "selected": existing[-1] if existing else "",
                "versions": existing,
                "status": "done" if existing else "pending",
            })
        return preview

    def _generate_one(self, img_client, asset_id: str, name: str, desc: str,
                      asset_type: str, style: str, species: str,
                      t2i_model: str, vlm_model: str, sid: str, max_iterations: int = 3) -> tuple:
        """生成单个素材图并返回 (asset_id, path_or_None, eval_result)

        评估-生成循环：如果 VLM 评估发现问题，最多重新生成 max_iterations 次
        """
        self._check_cancel()

        # 初始提示词
        if asset_type == 'characters':
            base_prompt = self._char_prompt(name, desc, style, species)
        else:
            base_prompt = self._setting_prompt(name, desc, style)

        size = "1920*1080"
        current_prompt = base_prompt

        for iteration in range(max_iterations):
            self._check_cancel()

            save_path = self._next_version_path(sid, asset_type, asset_id)
            save_dir = os.path.dirname(save_path)

            try:
                paths = img_client.generate_image(
                    prompt=current_prompt, model=t2i_model,
                    session_id=str(sid), save_dir=save_dir, size=size,
                )
                if not paths:
                    continue

                gen = paths[0]
                if gen != save_path:
                    if os.path.exists(save_path):
                        os.remove(save_path)
                    os.rename(gen, save_path)

                # VLM 评估
                eval_result = self._evaluate_with_vlm(save_path, desc, asset_type, vlm_model)

                # 使用固定阈值判断是否接受（8分及以上通过）
                score = eval_result.get('score', 0)
                issues = eval_result.get('issues', [])
                suggestion = eval_result.get('suggestion', '')
                is_acceptable = score >= 8

                if is_acceptable:
                    logger.info(f"[{asset_type}] {name} ✓ VLM评估通过 - 评分: {score}/10")
                else:
                    logger.warning(f"[{asset_type}] {name} ✗ VLM评估不通过 - 评分: {score}/10")
                    logger.warning(f"[{asset_type}] 问题: {issues}")
                    if suggestion:
                        logger.warning(f"[{asset_type}] 建议: {suggestion}")

                # 检查是否需要重新生成
                if is_acceptable:
                    # 评估通过，返回结果
                    return asset_id, save_path, eval_result
                else:
                    # 评估不通过，记录问题并继续循环
                    # 报告进度
                    self._report_progress("角色设计", f"重新生成中 ({iteration + 2}/{max_iterations}): {name}", 0)

            except Exception as e:
                logger.error(f"Asset gen failed for {asset_type} {name}({asset_id}): {e}")

        # 达到最大迭代次数，尝试使用 VLM 选择最佳图片
        logger.warning(f"[{asset_type}] {name} reached max iterations ({max_iterations}), trying VLM selection")

        # 收集所有生成过的版本
        all_versions = self._list_versions(sid, asset_type, asset_id)
        if len(all_versions) > 1:
            # 有多个版本，调用 VLM 选择最好的
            best_path, best_eval = self._select_best_with_vlm(
                all_versions, name, desc, asset_type, species, vlm_model
            )
            if best_path:
                logger.info(f"[{asset_type}] {name} VLM selected best version: {best_path}")
                return asset_id, best_path, best_eval

        # 没有多个版本或 VLM 选择失败，返回最后一次结果
        return asset_id, save_path if os.path.exists(save_path) else None, eval_result if 'eval_result' in locals() else None

    def _evaluate_with_vlm(self, image_path: str, description: str, asset_type: str, vlm_model: str = "qwen3.5-plus") -> dict:
        """使用 VLM 评估生成的图片"""
        try:
            from tool.vlm_client import VLM
            vlm = VLM()

            # 选择评估提示词
            if asset_type == 'characters':
                eval_prompt = load_prompt('character', 'eval_character', 'zh').format(
                    character_description=description
                )
            else:
                eval_prompt = load_prompt('setting', 'eval_setting', 'zh').format(
                    setting_description=description
                )

            result = vlm.query(
                prompt=eval_prompt,
                image_paths=[image_path],
                model=vlm_model
            )

            # 解析结果
            if result and isinstance(result, list):
                result_text = result[0] if result else ""
            elif isinstance(result, str):
                result_text = result
            else:
                result_text = str(result)

            # 尝试提取 JSON
            import json
            try:
                # 找到 JSON 部分
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

    def _select_best_with_vlm(self, image_paths: List[str], name: str, description: str,
                               asset_type: str, species: str = "", vlm_model: str = "qwen3.5-plus") -> tuple:
        """使用 VLM 从多个版本中选择最好的一张"""
        from tool.vlm_client import VLM
        import re

        if not image_paths:
            return None, None

        try:
            vlm = VLM()

            # 选择评估提示词
            if asset_type == 'characters':
                select_prompt = load_prompt('character', 'eval_select_best', 'zh').format(
                    num_images=len(image_paths),
                    num_images_minus_1=len(image_paths) - 1,
                    character_name=name,
                    character_description=description,
                    species=species,
                    images_list="\n".join([f"图片{i}: {p}" for i, p in enumerate(image_paths)])
                )
            else:
                select_prompt = load_prompt('setting', 'eval_select_best', 'zh').format(
                    num_images=len(image_paths),
                    num_images_minus_1=len(image_paths) - 1,
                    setting_name=name,
                    setting_description=description,
                    images_list="\n".join([f"图片{i}: {p}" for i, p in enumerate(image_paths)])
                )

            result = vlm.query(select_prompt, image_paths=image_paths, model=vlm_model)
            logger.info(f"[{asset_type}] {name} VLM selection result: {result}")

            # 解析 JSON 结果
            if result and isinstance(result, list):
                result_text = result[0] if result else ""
            elif isinstance(result, str):
                result_text = result
            else:
                result_text = str(result)

            logger.info(f"[{asset_type}] {name} VLM selection raw response: {result_text[:500]}")

            # 解析 JSON，提取 best_index
            best_index = 0
            try:
                # 找到 JSON 开始和结束
                json_start = result_text.find('{')
                json_end = result_text.rfind('}') + 1
                if json_start >= 0 and json_end > json_start:
                    json_str = result_text[json_start:json_end]
                    selection_result = json.loads(json_str)
                    best_index = selection_result.get('best_index', 0)
                    logger.info(f"[{asset_type}] {name} Parsed best_index: {best_index}")
            except Exception as e:
                logger.warning(f"[{asset_type}] {name} JSON parse failed: {e}, using last image")
                best_index = len(image_paths) - 1

            # 如果找到了 best_index，选择对应的图片
            if best_index is not None and 0 <= best_index < len(image_paths):
                best_path = image_paths[best_index]
                best_eval = {"score": 8, "issues": [], "is_acceptable": True, "reason": f"VLM selected image {best_index + 1} of {len(image_paths)}"}
                logger.info(f"[{asset_type}] {name} Selected image: {best_path}")
                return best_path, best_eval
            else:
                logger.warning(f"[{asset_type}] {name} Invalid best_index: {best_index}, available images: {len(image_paths)}")

        except Exception as e:
            logger.warning(f"VLM selection failed: {e}")

        return None, None

    # ─── 从剧本JSON读取角色/场景数据 ───

    @staticmethod
    def _read_script_data(sid: str) -> dict:
        """从结果文件的 script_json 字段读取角色和场景数据（含唯一ID）

        Returns:
            {
                "characters": { character_id: { "name", "description", "species" } },
                "settings":   { setting_id:   { "name", "description" } },
            }
        """
        from config import settings

        script_json_path = os.path.join(settings.RESULT_DIR, 'script', f'script_{sid}.json')
        if not os.path.exists(script_json_path):
            return {"characters": {}, "settings": {}}

        with open(script_json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        sid_data = data.get(str(sid), {})

        # 优先从 script_json 读取（包含完整ID信息）
        sj = sid_data.get('script_json')
        if sj:
            chars = {}
            for c in sj.get("characters", []):
                cid = c.get("character_id", "")
                if cid:
                    chars[cid] = {
                        "name": c.get("name", ""),
                        "description": c.get("description", ""),
                        "species": c.get("species", ""),
                    }
            sets = {}
            for s in sj.get("settings", []):
                sid_val = s.get("setting_id", "")
                if sid_val:
                    sets[sid_val] = {
                        "name": s.get("name", ""),
                        "description": s.get("description", ""),
                    }
            return {"characters": chars, "settings": sets}

        return {"characters": {}, "settings": {}}

    # ─── 核心流程 ───

    async def process(self, input_data: Any, intervention: Optional[Dict] = None) -> Dict:
        from config import settings
        from tool.image_client import ImageClient

        sid = input_data["session_id"]
        style = input_data.get("style", "anime")
        t2i_model = input_data.get("image_t2i_model", "") or settings.IMAGE_T2I_MODEL
        vlm_model = input_data.get("vlm_model", "qwen3.5-plus")
        # 根据 enable_concurrency 决定并发数
        enable_concurrency = input_data.get("enable_concurrency", True)
        logger.info(f"[CharacterAgent] enable_concurrency={enable_concurrency}")
        from config_model import get_max_concurrency
        max_concurrency = get_max_concurrency(t2i_model, enable_concurrency)
        logger.info(f"[CharacterAgent] 使用并发数={max_concurrency}")
        concurrency = max_concurrency

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

        # ═══════════ 介入: 重新生成指定素材 ═══════════
        if intervention:
            regen_chars = intervention.get("regenerate_characters", [])   # list of asset_id
            regen_sets = intervention.get("regenerate_settings", [])      # list of asset_id
            select_chars = intervention.get("select_characters", {})      # {asset_id: path}
            select_sets = intervention.get("select_settings", {})         # {asset_id: path}
            update_descriptions = intervention.get("update_descriptions", {})  # {characters: {}, settings: {}}

            script_data = self._read_script_data(sid)
            chars_desc = script_data["characters"]
            sets_desc = script_data["settings"]

            # 处理描述更新
            if update_descriptions:
                updated_chars = update_descriptions.get("characters", {})
                updated_sets = update_descriptions.get("settings", {})

                # 更新角色描述 (支持两种格式：字符串或字典)
                for asset_id, info in updated_chars.items():
                    if asset_id in chars_desc:
                        if isinstance(info, dict):
                            if "name" in info:
                                chars_desc[asset_id]["name"] = info["name"]
                            if "description" in info:
                                chars_desc[asset_id]["description"] = info["description"]
                            if "species" in info:
                                chars_desc[asset_id]["species"] = info["species"]
                        else:
                            # 简单字符串格式：直接更新 description
                            chars_desc[asset_id]["description"] = str(info)

                # 更新场景描述 (支持两种格式：字符串或字典)
                for asset_id, info in updated_sets.items():
                    if asset_id in sets_desc:
                        if isinstance(info, dict):
                            if "name" in info:
                                sets_desc[asset_id]["name"] = info["name"]
                            if "description" in info:
                                sets_desc[asset_id]["description"] = info["description"]
                        else:
                            # 简单字符串格式：直接更新 description
                            sets_desc[asset_id]["description"] = str(info)

                # 写回剧本数据文件
                script_file = os.path.join(settings.RESULT_DIR, 'script', f'script_{sid}.json')
                with open(script_file, 'r', encoding='utf-8') as f:
                    full_data = json.load(f)

                if str(sid) in full_data:
                    full_data[str(sid)]["characters"] = chars_desc
                    full_data[str(sid)]["settings"] = sets_desc

                with open(script_file, 'w', encoding='utf-8') as f:
                    json.dump(full_data, f, ensure_ascii=False, indent=2)

                logger.info(f"[CharacterAgent] Updated descriptions for session {sid}")

            if regen_chars or regen_sets:
                self._report_progress("角色设计", "重新生成中...", 10)
                tasks = []
                for asset_id in regen_chars:
                    info = chars_desc.get(asset_id, {})
                    tasks.append(("characters", asset_id, info.get("name", ""), info.get("description", ""), info.get("species", "")))
                for asset_id in regen_sets:
                    info = sets_desc.get(asset_id, {})
                    tasks.append(("settings", asset_id, info.get("name", ""), info.get("description", ""), ""))

                def regen_run():
                    total = len(tasks)
                    done = 0
                    with ThreadPoolExecutor(max_workers=concurrency) as executor:
                        futs = {}
                        for atype, aid, name, desc, species in tasks:
                            fut = executor.submit(
                                self._generate_one, img_client,
                                aid, name, desc, atype, style, species, t2i_model, vlm_model, sid
                            )
                            futs[fut] = (atype, aid, name)
                        for fut in as_completed(futs):
                            atype, aid, fname = futs[fut]
                            _, result_path, eval_result = fut.result()
                            done += 1
                            pct = 10 + int(85 * done / max(total, 1))
                            if result_path:
                                versions = self._list_versions(sid, atype, aid)
                                self._report_progress("角色设计", f"完成: {fname}", pct, data={
                                    "asset_complete": {
                                        "type": atype, "id": aid, "status": "done",
                                        "selected": result_path, "versions": versions,
                                        "evaluation": eval_result,
                                    }
                                })
                            else:
                                self._report_progress("角色设计", f"失败: {fname}", pct, data={
                                    "asset_complete": {
                                        "type": atype, "id": aid, "status": "failed",
                                        "selected": "", "versions": [],
                                    }
                                })

                loop = asyncio.get_running_loop()
                await loop.run_in_executor(None, regen_run)

            self._report_progress("角色设计", "完成", 100)
            return self._build_payload(sid, chars_desc, sets_desc, select_chars, select_sets)

        # ═══════════ 正常流程: 全量首次生成 ═══════════
        self._report_progress("角色设计", "读取剧本数据...", 5)

        script_data = self._read_script_data(sid)
        chars_desc = script_data["characters"]
        sets_desc = script_data["settings"]

        if not chars_desc and not sets_desc:
            raise Exception("未能从剧本中读取到角色或场景描述数据")

        # 发送素材预览（含所有素材和当前状态）
        preview = self._build_preview(sid, chars_desc, sets_desc)
        self._report_progress("角色设计", "加载素材列表", 8, data={"assets_preview": preview})

        def run():
            all_tasks = []
            for asset_id, info in chars_desc.items():
                existing = self._list_versions(sid, 'characters', asset_id)
                if existing:
                    continue
                all_tasks.append(("characters", asset_id, info.get("name", ""), info.get("description", ""), info.get("species", "")))

            for asset_id, info in sets_desc.items():
                desc = info.get("description", "") if isinstance(info, dict) else info
                existing = self._list_versions(sid, 'settings', asset_id)
                if existing:
                    continue
                all_tasks.append(("settings", asset_id, info.get("name", "") if isinstance(info, dict) else "", desc, ""))

            if not all_tasks:
                self._report_progress("角色设计", "所有素材已存在", 95)
                return

            total = len(all_tasks)
            done = 0

            with ThreadPoolExecutor(max_workers=concurrency) as executor:
                futs = {}
                for atype, aid, name, desc, species in all_tasks:
                    fut = executor.submit(
                        self._generate_one, img_client,
                        aid, name, desc, atype, style, species, t2i_model, vlm_model, sid,
                    )
                    futs[fut] = (atype, aid, name)

                for fut in as_completed(futs):
                    atype, aid, fname = futs[fut]
                    _, result_path, _ = fut.result()
                    done += 1
                    pct = 10 + int(85 * done / max(total, 1))
                    if result_path:
                        versions = self._list_versions(sid, atype, aid)
                        self._report_progress("角色设计", f"完成: {fname}", pct, data={
                            "asset_complete": {
                                "type": atype, "id": aid, "status": "done",
                                "selected": result_path, "versions": versions,
                            }
                        })
                    else:
                        self._report_progress("角色设计", f"失败: {fname}", pct, data={
                            "asset_complete": {
                                "type": atype, "id": aid, "status": "failed",
                                "selected": "", "versions": self._list_versions(sid, atype, aid),
                            }
                        })

            self._report_progress("角色设计", "完成", 100)

        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, run)

        return self._build_payload(sid, chars_desc, sets_desc)

    def _build_payload(self, sid: str, chars_desc: dict, sets_desc: dict,
                       selected_chars: dict = None, selected_sets: dict = None) -> dict:
        """构建返回给前端的 payload"""
        selected_chars = selected_chars or {}
        selected_sets = selected_sets or {}

        characters = []
        for asset_id, info in chars_desc.items():
            desc = info.get("description", "") if isinstance(info, dict) else info
            name = info.get("name", "") if isinstance(info, dict) else ""
            sel = selected_chars.get(asset_id, "")
            characters.append(self._build_asset_info(sid, 'characters', asset_id, name, desc, sel))

        settings_list = []
        for asset_id, info in sets_desc.items():
            desc = info.get("description", "") if isinstance(info, dict) else info
            name = info.get("name", "") if isinstance(info, dict) else ""
            sel = selected_sets.get(asset_id, "")
            settings_list.append(self._build_asset_info(sid, 'settings', asset_id, name, desc, sel))

        # 图片生成完成即为阶段完成，用户选择图片只是更新数据
        return {
            "payload": {
                "session_id": sid,
                "characters": characters,
                "settings": settings_list,
            },
            "stage_completed": True,
        }
