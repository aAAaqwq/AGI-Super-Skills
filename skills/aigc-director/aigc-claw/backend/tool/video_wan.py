"""
通义万象（Wan）视频生成客户端
基于 DashScope SDK (dashscope.VideoSynthesis)
支持 wan2.6-i2v-flash 等模型的图生视频功能
"""

import os
import logging
from typing import Optional
from http import HTTPStatus

import dashscope
from dashscope import VideoSynthesis
import requests

logger = logging.getLogger(__name__)


class WanVideoClient:
    """
    阿里云通义万象视频生成客户端
    使用 dashscope SDK 的 VideoSynthesis 接口
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
    ) -> None:
        self.api_key = api_key or os.getenv("DASHSCOPE_API_KEY")
        self.base_url = base_url or os.getenv("DASHSCOPE_BASE_URL")

        if self.api_key:
            dashscope.api_key = self.api_key
        if self.base_url:
            dashscope.base_http_api_url = self.base_url

    def generate_video(
        self,
        prompt: str,
        image_path: str,
        save_path: str,
        model: str = "wan2.6-i2v-flash",
        duration: int = 10,
        shot_type: str = "multi",
    ) -> str:
        """
        图生视频：提交任务 → 等待完成 → 下载到本地

        Args:
            prompt: 视频描述提示词
            image_path: 输入图片本地路径
            save_path: 输出视频保存路径
            model: 万象视频模型名
            duration: 视频时长（秒），5-10
            shot_type: 镜头类型，"single" 或 "multi"

        Returns:
            video_url: 远端视频 URL

        Raises:
            FileNotFoundError: 输入图片不存在
            RuntimeError: API 调用或下载失败
        """
        if not os.path.exists(image_path):
            raise FileNotFoundError(f"输入图片不存在: {image_path}")

        abs_img = os.path.abspath(image_path)
        img_url = f"file://{abs_img}"

        logger.info(f"WanVideoClient: model={model}, prompt={prompt[:60]}...")

        rsp = VideoSynthesis.call(
            api_key=self.api_key,
            model=model,
            prompt=prompt,
            img_url=img_url,
            duration=duration,
            shot_type=shot_type,
        )

        if rsp.status_code != HTTPStatus.OK:
            raise RuntimeError(
                f"万象视频 API 错误: status={rsp.status_code}, "
                f"code={rsp.code}, message={rsp.message}"
            )

        video_url = rsp.output.video_url
        # 检查是否返回了有效的视频URL
        if not video_url:
            raise RuntimeError(f"万象视频 API 返回空URL，可能生成失败: code={rsp.code}, message={rsp.message}")

        logger.info(f"WanVideoClient: 视频生成成功: {video_url}")

        # 确保输出目录存在
        os.makedirs(os.path.dirname(save_path), exist_ok=True)

        # 下载视频
        resp = requests.get(video_url, stream=True, timeout=120)
        if resp.status_code != 200:
            raise RuntimeError(f"视频下载失败: HTTP {resp.status_code}")

        with open(save_path, 'wb') as f:
            for chunk in resp.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)

        logger.info(f"WanVideoClient: 视频已保存: {save_path}")
        return video_url


if __name__ == "__main__":
    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from config import Config

    print("=== 万象 (Wan) 视频客户端可用性测试 ===")
    api_key = Config.DASHSCOPE_API_KEY
    base_url = Config.DASHSCOPE_BASE_URL
    if not api_key:
        print("✗ DASHSCOPE_API_KEY 未设置，跳过")
        sys.exit(1)
    print(f"  API Key: {api_key[:6]}***{api_key[-4:]}")
    print(f"  Base URL: {base_url}")
    try:
        client = WanVideoClient(api_key=api_key, base_url=base_url)
        print("✓ 客户端初始化成功")
        print("  (视频生成需要图片输入且耗时数分钟，仅验证初始化)")
    except Exception as e:
        print(f"✗ 初始化失败: {e}")
        sys.exit(1)
