"""
统一视频生成客户端
根据 model 名称自动路由到对应后端：
  - wan*      → WanVideoClient (DashScope VideoSynthesis)
  - jimeng*   → JiMengClient (火山引擎即梦)
  - kling*    → KlingVideoClient (可灵 AI)
"""

import os
import logging
from typing import Optional
from config import Config

try:
    from tool.video_wan import WanVideoClient
    from tool.image_jimeng import JiMengClient
    from tool.video_kling import KlingVideoClient
except ImportError:
    from video_wan import WanVideoClient
    from image_jimeng import JiMengClient
    from video_kling import KlingVideoClient

logger = logging.getLogger(__name__)


class VideoClient:
    """
    统一视频生成客户端
    参照 ImageClient 模式，按模型名路由到不同后端
    """

    def __init__(
        self,
        dashscope_api_key: Optional[str] = None,
        dashscope_base_url: Optional[str] = None,
        jimeng_base_url: Optional[str] = None,
        jimeng_access_key: Optional[str] = None,
        jimeng_secret_key: Optional[str] = None,
        kling_access_key: Optional[str] = None,
        kling_secret_key: Optional[str] = None,
        kling_base_url: Optional[str] = None,
    ):
        # 万象客户端
        self.wan_client = WanVideoClient(
            api_key=dashscope_api_key,
            base_url=dashscope_base_url,
        )

        # 即梦客户端（图片+视频共用 HMAC 鉴权）
        self.jimeng_client = JiMengClient(
            base_url=jimeng_base_url,
            access_key=jimeng_access_key,
            secret_key=jimeng_secret_key,
        )

        # 可灵客户端
        self.kling_client = KlingVideoClient(
            access_key=kling_access_key,
            secret_key=kling_secret_key,
            base_url=kling_base_url,
        )

    def generate_video(
        self,
        prompt: str,
        image_path: str,
        save_path: str,
        model: str = "wan2.6-i2v-flash",
        duration: int = 5,
        shot_type: str = "multi",
        sound: str = "",
    ) -> str:
        """
        生成视频

        Args:
            prompt: 视频描述提示词
            image_path: 输入图片本地路径
            save_path: 输出视频保存路径
            model: 模型名，决定使用哪个后端
            duration: 视频时长（秒）
            shot_type: 镜头类型 "single" / "multi"

        Returns:
            video_url: 远端视频 URL（万象）或 task_id（即梦）

        Raises:
            FileNotFoundError: 输入图片不存在
            RuntimeError: 生成或下载失败
        """
        if not model:
            model = "wan2.6-i2v-flash"

        if Config.PRINT_MODEL_INPUT:
            print("---- VIDEO GENERATION REQUEST ----")
            print(f"Prompt: {prompt}")
            if image_path and str(image_path).startswith("data:"):
                print(f"Image: [Base64图片]")
            else:
                print(f"Image: {image_path}")
            print(f"Model: {model}")
            print(f"Duration: {duration}s")
            print(f"Shot Type: {shot_type}")
            print(f"Save: {save_path}")
            print("-" * 30)

        model_lower = model.lower()

        if "jimeng" in model_lower:
            return self._generate_jimeng(prompt, image_path, save_path, model)
        elif "kling" in model_lower:
            return self._generate_kling(prompt, image_path, save_path, model, duration, sound)
        else:
            return self._generate_wan(prompt, image_path, save_path, model, duration, shot_type)

    def _generate_wan(
        self,
        prompt: str,
        image_path: str,
        save_path: str,
        model: str,
        duration: int,
        shot_type: str,
    ) -> str:
        """通过万象模型生成视频"""
        logger.info(f"VideoClient: 路由至万象 model={model}")
        return self.wan_client.generate_video(
            prompt=prompt,
            image_path=image_path,
            save_path=save_path,
            model=model,
            duration=duration,
            shot_type=shot_type,
        )

    def _generate_jimeng(
        self,
        prompt: str,
        image_path: str,
        save_path: str,
        model: str,
    ) -> str:
        """通过即梦模型生成视频"""
        logger.info(f"VideoClient: 路由至即梦 model={model}")
        task_id = self.jimeng_client.generate_video(
            prompt=prompt,
            image_path=image_path,
        )

        # 轮询获取结果
        result = self.jimeng_client.poll_task(model=model, task_id=task_id)

        # 即梦返回的视频数据可能是 URL 或 base64
        video_url = result.get("video_url", "")
        if video_url:
            import requests
            os.makedirs(os.path.dirname(save_path), exist_ok=True)
            resp = requests.get(video_url, stream=True, timeout=120)
            resp.raise_for_status()
            with open(save_path, 'wb') as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            return video_url

        raise RuntimeError(f"即梦视频生成未返回有效结果: {result}")

    def _generate_kling(
        self,
        prompt: str,
        image_path: str,
        save_path: str,
        model: str,
        duration: int = 5,
        sound: str = "",
    ) -> str:
        """通过可灵模型生成视频"""
        logger.info(f"VideoClient: 路由至可灵 model={model}")
        return self.kling_client.generate_video(
            prompt=prompt,
            image_path=image_path,
            save_path=save_path,
            model=model,
            duration=duration,
            sound=sound,
        )
