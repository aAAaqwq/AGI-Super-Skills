# -*- coding: utf-8 -*-
"""
阶段6: 后期制作智能体
拼接用户在阶段5选定的视频片段 → 最终成片
"""

import os
import re
import subprocess
import asyncio
import logging
from typing import Any, Optional, Dict

from .base_agent import AgentInterface

logger = logging.getLogger(__name__)


class VideoEditorAgent(AgentInterface):
    """后期制作：拼接用户选择的视频片段 → 最终成片"""

    def __init__(self):
        super().__init__(name="VideoEditor")

    async def process(self, input_data: Any, intervention: Optional[Dict] = None) -> Dict:
        sid = input_data["session_id"]
        selected_clips: dict = input_data.get("selected_clips", {})

        if not selected_clips:
            raise Exception("未收到用户选择的视频片段(selected_clips)，请先完成阶段5")

        self._report_progress("后期制作", "准备视频片段...", 5)

        def run():
            video_dir = os.path.join('code/result/video', str(sid))

            # 按 shot_id 中的数字排序
            def sort_key(k: str) -> tuple:
                return tuple(int(n) for n in re.findall(r'\d+', k)) or (999,)

            clip_paths = []
            for shot_id in sorted(selected_clips.keys(), key=sort_key):
                path = selected_clips[shot_id]
                if os.path.exists(path):
                    clip_paths.append(path)
                else:
                    logger.warning(f"[{sid}] Clip missing: {shot_id} → {path}")

            if not clip_paths:
                raise Exception("所有选定的视频片段文件均不存在")

            logger.info(f"[{sid}] Concat {len(clip_paths)} clips")
            self._report_progress("后期制作", f"拼接 {len(clip_paths)} 个片段...", 15)

            list_path = os.path.join(video_dir, 'file_list.txt')
            with open(list_path, 'w', encoding='utf-8') as f:
                for p in clip_paths:
                    f.write(f"file '{os.path.abspath(p)}'\n")

            self._report_progress("后期制作", "ffmpeg 拼接中...", 30)

            output = os.path.join(video_dir, f'{sid}_final.mp4')
            cmd = ['ffmpeg', '-f', 'concat', '-safe', '0',
                   '-i', list_path, '-c', 'copy', '-y', output]
            subprocess.run(cmd, check=True, capture_output=True)
            logger.info(f"[{sid}] Concat success: {output}")
            return output

        loop = asyncio.get_running_loop()
        final_path = await loop.run_in_executor(None, run)

        self._report_progress("后期制作", "成片完成", 100)

        return {
            "payload": {"session_id": sid, "final_video": final_path},
            "stage_completed": True,
        }