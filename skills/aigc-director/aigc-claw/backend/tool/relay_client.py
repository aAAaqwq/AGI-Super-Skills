# -*- coding: utf-8 -*-
"""
统一中转站 (Relay) 客户端
通过第三方中转站（如青云 API）统一调用各种模型
使用 OpenAI 兼容格式，一个 API Key + Base URL 调用所有模型

支持的模型类型：
  - LLM 文本生成（chat.completions）
  - VLM 视觉理解（chat.completions + 图片）
  - 图片生成（images.generate 或 chat.completions）
  - 视频生成（异步任务：创建 → 轮询 → 获取结果）
  - Embedding（embeddings）

参考：青云聚合 API (https://api.qingyuntop.top)
"""

import os
import time
import json
import base64
import logging
import requests
from typing import List, Optional, Dict, Any
from openai import OpenAI

logger = logging.getLogger(__name__)


class RelayClient:
    """
    统一中转站客户端
    所有模型通过同一个 OpenAI 兼容 API 调用
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: int = 300,
    ):
        self.api_key = api_key or os.getenv("RELAY_API_KEY", "")
        self.base_url = base_url or os.getenv("RELAY_BASE_URL", "")
        self.provider_name = os.getenv("RELAY_PROVIDER_NAME", "relay")
        self.timeout = timeout

        if not self.api_key:
            raise ValueError(
                "RELAY_API_KEY 未设置。请在 .env 中配置 RELAY_API_KEY 或传入 api_key 参数。\n"
                "示例: RELAY_API_KEY=sk-xxx RELAY_BASE_URL=https://api.qingyuntop.top/v1"
            )
        if not self.base_url:
            raise ValueError(
                "RELAY_BASE_URL 未设置。请在 .env 中配置 RELAY_BASE_URL 或传入 base_url 参数。\n"
                "示例: RELAY_BASE_URL=https://api.qingyuntop.top/v1"
            )

        # 确保 base_url 以 /v1 结尾
        if not self.base_url.endswith("/v1"):
            self.base_url = self.base_url.rstrip("/") + "/v1"

        self.client = OpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
            timeout=timeout,
        )
        self._base_url_no_v1 = self.base_url.rstrip("/v1").rstrip("/v")

        logger.info(f"RelayClient 初始化: provider={self.provider_name}, base_url={self.base_url}")

    # ==================== LLM 文本生成 ====================

    def chat(
        self,
        prompt: str,
        model: str = "qwen3.5-plus",
        image_urls: Optional[List[str]] = None,
        max_tokens: int = 8192,
        temperature: float = 0.7,
        system_prompt: str = "You are a helpful assistant.",
        web_search: bool = False,
    ) -> str:
        """
        LLM 文本生成（OpenAI chat.completions 格式）

        Args:
            prompt: 用户提示词
            model: 模型名称
            image_urls: 图片 URL 列表（多模态模型）
            max_tokens: 最大生成 token 数
            temperature: 温度参数
            system_prompt: 系统提示词
            web_search: 是否启用联网搜索

        Returns:
            生成的文本内容
        """
        messages = [{"role": "system", "content": system_prompt}]

        # 构建用户消息
        content: list = [{"type": "text", "text": prompt}]
        if image_urls:
            for url in image_urls:
                content.append({"type": "image_url", "image_url": {"url": url}})

        messages.append({"role": "user", "content": content})

        max_attempts = 5
        for attempt in range(max_attempts):
            try:
                request_params = {
                    "model": model,
                    "messages": messages,
                    "max_tokens": max_tokens,
                    "temperature": temperature,
                }
                if web_search:
                    request_params["search_tool"] = "auto"

                response = self.client.chat.completions.create(**request_params)

                if response.choices and response.choices[0].message.content:
                    return response.choices[0].message.content.strip()
                else:
                    logger.warning(f"[{self.provider_name}] 空响应，重试 {attempt + 1}/{max_attempts}")
            except Exception as e:
                logger.error(f"[{self.provider_name}] chat 错误 (model={model}): {e}")
                if attempt < max_attempts - 1:
                    time.sleep(5 * (attempt + 1))

        raise Exception(f"[{self.provider_name}] 达到最大重试次数，模型 {model} 调用失败")

    # ==================== VLM 视觉理解 ====================

    def vlm_chat(
        self,
        prompt: str,
        image_paths: Optional[List[str]] = None,
        model: str = "gemini-3-flash-preview",
        max_tokens: int = 4096,
    ) -> str:
        """
        VLM 视觉语言模型调用（图片理解）

        Args:
            prompt: 文本提示
            image_paths: 图片路径列表（支持本地路径、URL、data: URI）
            model: 视觉模型名称

        Returns:
            模型回复文本
        """
        content: list = [{"type": "text", "text": prompt}]

        if image_paths:
            for path in image_paths:
                if path.startswith("data:"):
                    content.append({"type": "image_url", "image_url": {"url": path}})
                elif path.startswith("http"):
                    content.append({"type": "image_url", "image_url": {"url": path}})
                else:
                    # 本地文件转 base64
                    with open(path, "rb") as f:
                        img_data = base64.b64encode(f.read()).decode("utf-8")
                    ext = os.path.splitext(path)[1].lower()
                    mime = "image/png" if ext == ".png" else "image/jpeg"
                    content.append({
                        "type": "image_url",
                        "image_url": {"url": f"data:{mime};base64,{img_data}"}
                    })

        messages = [{"role": "user", "content": content}]

        max_attempts = 5
        for attempt in range(max_attempts):
            try:
                response = self.client.chat.completions.create(
                    model=model,
                    messages=messages,
                    max_tokens=max_tokens,
                )
                if response.choices and response.choices[0].message.content:
                    return response.choices[0].message.content.strip()
            except Exception as e:
                logger.error(f"[{self.provider_name}] vlm_chat 错误: {e}")
                if attempt < max_attempts - 1:
                    time.sleep(5 * (attempt + 1))

        raise Exception(f"[{self.provider_name}] VLM 调用失败，模型 {model}")

    # ==================== 图片生成 ====================

    def generate_image(
        self,
        prompt: str,
        model: str = "gemini-3-pro-image-preview",
        size: str = "1024x1024",
        save_dir: Optional[str] = None,
        image_urls: Optional[List[str]] = None,
    ) -> str:
        """
        图片生成（通过中转站）

        支持两种格式：
          1. images.generate 格式（如 sora_image）
          2. chat.completions 格式（如 gemini-3-pro-image-preview，通过 chat 返回 base64 图片）

        Args:
            prompt: 图片描述
            model: 图片模型名
            size: 图片尺寸
            save_dir: 保存目录（不传则返回 URL/base64）
            image_urls: 参考图片 URL

        Returns:
            本地文件路径、URL 或 base64 字符串
        """
        # 判断是否使用 chat 格式（gemini/grok 系列图片模型）
        chat_image_models = [
            "gemini-3-pro-image-preview",
            "gemini-2.5-pro-image",
            "gemini-2.5-flash-image",
            "grok-imagine-image-pro",
        ]
        use_chat_format = any(m in model for m in chat_image_models)

        if use_chat_format:
            return self._generate_image_chat(prompt, model, size, save_dir, image_urls)
        else:
            return self._generate_image_api(prompt, model, size, save_dir)

    def _generate_image_chat(
        self,
        prompt: str,
        model: str,
        size: str = "1024x1024",
        save_dir: Optional[str] = None,
        image_urls: Optional[List[str]] = None,
    ) -> str:
        """通过 chat.completions 格式生成图片（Gemini/Grok 系列）"""
        content: list = [{"type": "text", "text": prompt}]
        if image_urls:
            for url in image_urls:
                content.append({"type": "image_url", "image_url": {"url": url}})

        messages = [{"role": "user", "content": content}]

        max_attempts = 5
        for attempt in range(max_attempts):
            try:
                response = self.client.chat.completions.create(
                    model=model,
                    messages=messages,
                )

                if not response.choices:
                    continue

                choice = response.choices[0]
                msg = choice.message

                # 检查是否有 inline_data（base64 图片）
                if hasattr(msg, 'content') and isinstance(msg.content, list):
                    for part in msg.content:
                        if isinstance(part, dict) and part.get("type") == "image_url":
                            img_url = part["image_url"]["url"]
                            return self._save_or_return_image(img_url, save_dir)

                # 文本响应中可能包含 base64
                text = msg.content if isinstance(msg.content, str) else ""
                if text and ";base64," in text:
                    # 从文本中提取 base64
                    import re
                    match = re.search(r'data:image/[^;]+;base64,([A-Za-z0-9+/=]+)', text)
                    if match:
                        b64_data = match.group(1)
                        return self._save_b64_image(b64_data, save_dir)

                # 直接返回文本（可能包含 URL）
                if text:
                    # 尝试提取 URL
                    url_match = re.search(r'https?://[^\s)]+\.(png|jpg|jpeg|webp)', text)
                    if url_match:
                        return self._download_and_save(url_match.group(0), save_dir)
                    return text

            except Exception as e:
                logger.error(f"[{self.provider_name}] 图片生成(chat) 错误: {e}")
                if attempt < max_attempts - 1:
                    time.sleep(5)

        raise Exception(f"[{self.provider_name}] 图片生成失败，模型 {model}")

    def _generate_image_api(
        self,
        prompt: str,
        model: str,
        size: str = "1024x1024",
        save_dir: Optional[str] = None,
    ) -> str:
        """通过 images.generate 格式生成图片"""
        max_attempts = 5
        for attempt in range(max_attempts):
            try:
                response = self.client.images.generate(
                    model=model,
                    prompt=prompt,
                    size=size,
                    n=1,
                )
                if response.data and response.data[0]:
                    img = response.data[0]
                    if img.url:
                        return self._download_and_save(img.url, save_dir)
                    elif hasattr(img, 'b64_json') and img.b64_json:
                        return self._save_b64_image(img.b64_json, save_dir)
            except Exception as e:
                logger.error(f"[{self.provider_name}] 图片生成(api) 错误: {e}")
                if attempt < max_attempts - 1:
                    time.sleep(5)

        raise Exception(f"[{self.provider_name}] 图片生成失败，模型 {model}")

    # ==================== 视频生成（异步任务） ====================

    def generate_video(
        self,
        prompt: str,
        model: str = "sora-2-all",
        image_url: Optional[str] = None,
        save_path: Optional[str] = None,
        poll_interval: int = 10,
        max_wait: int = 600,
        **kwargs,
    ) -> str:
        """
        视频生成（异步任务模式）
        创建任务 → 轮询状态 → 下载结果

        支持模型：
          - sora-2-all, sora-2-pro-all (Sora 格式)
          - veo_3_1-fast-4K, veo_3_1-components-4K (Veo 格式)
          - grok-video-3-10s (Grok 格式)
          - doubao-seedance-* (豆包格式)

        Args:
            prompt: 视频描述
            model: 视频模型名
            image_url: 首帧图片 URL（图生视频）
            save_path: 保存路径
            poll_interval: 轮询间隔（秒）
            max_wait: 最大等待时间（秒）
            **kwargs: 额外参数（duration, ratio 等）

        Returns:
            视频本地路径或 URL
        """
        # 1. 创建任务
        task_id = self._create_video_task(prompt, model, image_url, **kwargs)
        logger.info(f"[{self.provider_name}] 视频任务创建: task_id={task_id}, model={model}")

        # 2. 轮询等待
        result = self._poll_task(task_id, poll_interval, max_wait)

        # 3. 提取视频 URL
        video_url = self._extract_video_url(result, model)

        # 4. 下载保存
        if save_path and video_url:
            return self._download_video(video_url, save_path)

        return video_url

    def _create_video_task(
        self,
        prompt: str,
        model: str,
        image_url: Optional[str] = None,
        **kwargs,
    ) -> str:
        """创建视频生成任务"""
        body: Dict[str, Any] = {
            "model": model,
            "prompt": prompt,
        }
        if image_url:
            body["image_url"] = image_url
        body.update(kwargs)

        # 使用 raw HTTP 请求（视频 API 通常是自定义格式）
        url = f"{self._base_url_no_v1}/v1/video/generations"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

        resp = requests.post(url, json=body, headers=headers, timeout=self.timeout)
        data = resp.json()

        if resp.status_code >= 400:
            raise RuntimeError(f"视频任务创建失败: {data}")

        # 兼容多种响应格式
        task_id = (
            data.get("id")
            or data.get("task_id")
            or data.get("data", {}).get("task_id")
            or data.get("data", {}).get("id")
        )
        if not task_id:
            raise RuntimeError(f"无法提取 task_id: {data}")

        return str(task_id)

    def _poll_task(self, task_id: str, interval: int = 10, max_wait: int = 600) -> dict:
        """轮询异步任务状态"""
        url = f"{self._base_url_no_v1}/v1/video/generations/{task_id}"
        headers = {"Authorization": f"Bearer {self.api_key}"}

        elapsed = 0
        while elapsed < max_wait:
            resp = requests.get(url, headers=headers, timeout=30)
            data = resp.json()

            status = (
                data.get("status")
                or data.get("data", {}).get("status")
                or "unknown"
            ).lower()

            if status in ("completed", "succeed", "succeeded", "success"):
                return data
            elif status in ("failed", "error"):
                raise RuntimeError(f"视频任务失败: {data}")

            logger.info(f"[{self.provider_name}] 视频任务 {task_id}: {status} ({elapsed}s)")
            time.sleep(interval)
            elapsed += interval

        raise TimeoutError(f"视频任务超时 ({max_wait}s): task_id={task_id}")

    def _extract_video_url(self, result: dict, model: str) -> str:
        """从任务结果中提取视频 URL"""
        # 多种响应格式兼容
        candidates = [
            result.get("data", {}).get("video_url"),
            result.get("data", {}).get("url"),
            result.get("output", {}).get("video_url"),
            result.get("video_url"),
        ]

        # 嵌套在 results 数组中
        results_list = result.get("data", {}).get("results", [])
        if results_list and isinstance(results_list, list):
            for item in results_list:
                if isinstance(item, dict):
                    url = item.get("url") or item.get("video_url")
                    if url:
                        candidates.append(url)

        for url in candidates:
            if url and isinstance(url, str) and url.startswith("http"):
                return url

        raise RuntimeError(f"无法提取视频 URL: {json.dumps(result, ensure_ascii=False)[:500]}")

    def _download_video(self, url: str, save_path: str) -> str:
        """下载视频到本地"""
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        resp = requests.get(url, stream=True, timeout=300)
        resp.raise_for_status()
        with open(save_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
        logger.info(f"[{self.provider_name}] 视频已保存: {save_path}")
        return save_path

    # ==================== Embedding ====================

    def embed(self, text: str, model: str = "gemini-embedding-2-preview") -> List[float]:
        """
        文本 Embedding

        Args:
            text: 输入文本
            model: Embedding 模型名

        Returns:
            向量列表
        """
        response = self.client.embeddings.create(
            model=model,
            input=text,
        )
        return response.data[0].embedding

    # ==================== 工具方法 ====================

    def _save_or_return_image(self, url_or_data: str, save_dir: Optional[str]) -> str:
        if url_or_data.startswith("data:"):
            # base64 data URI
            _, b64_data = url_or_data.split(",", 1)
            return self._save_b64_image(b64_data, save_dir)
        elif url_or_data.startswith("http"):
            return self._download_and_save(url_or_data, save_dir)
        else:
            return url_or_data

    def _save_b64_image(self, b64_data: str, save_dir: Optional[str]) -> str:
        if save_dir:
            os.makedirs(save_dir, exist_ok=True)
            file_name = f"relay_{int(time.time())}_{id(b64_data) % 10000}.png"
            file_path = os.path.join(save_dir, file_name)
            with open(file_path, "wb") as f:
                f.write(base64.b64decode(b64_data))
            return file_path
        return b64_data

    def _download_and_save(self, url: str, save_dir: Optional[str]) -> str:
        if not save_dir:
            return url
        os.makedirs(save_dir, exist_ok=True)
        ext = os.path.splitext(url.split("?")[0])[1] or ".png"
        file_name = f"relay_{int(time.time())}_{hash(url) % 10000}{ext}"
        file_path = os.path.join(save_dir, file_name)
        resp = requests.get(url, timeout=120)
        resp.raise_for_status()
        with open(file_path, "wb") as f:
            f.write(resp.content)
        return file_path


if __name__ == "__main__":
    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from config import Config

    print("=== Relay Client (统一中转站) 可用性测试 ===")
    api_key = Config.RELAY_API_KEY
    base_url = Config.RELAY_BASE_URL
    provider = Config.RELAY_PROVIDER_NAME

    if not api_key or not base_url:
        print("✗ RELAY_API_KEY 或 RELAY_BASE_URL 未设置，跳过")
        print("  请在 .env 中配置:")
        print("  RELAY_API_KEY=your_relay_api_key")
        print("  RELAY_BASE_URL=https://api.qingyuntop.top")
        sys.exit(1)

    print(f"  Provider: {provider}")
    print(f"  API Key: {api_key[:6]}***{api_key[-4:]}")
    print(f"  Base URL: {base_url}")

    client = RelayClient(api_key=api_key, base_url=base_url)

    # 测试 1: LLM
    print("\n--- 测试 LLM (qwen3.5-plus) ---")
    try:
        resp = client.chat("用一句话介绍你自己。", model="qwen3.5-plus")
        print(f"✓ LLM 响应: {resp[:200]}")
    except Exception as e:
        print(f"✗ LLM 失败: {e}")

    # 测试 2: Embedding
    print("\n--- 测试 Embedding (gemini-embedding-2-preview) ---")
    try:
        vec = client.embed("测试文本", model="gemini-embedding-2-preview")
        print(f"✓ Embedding 维度: {len(vec)}, 前5: {vec[:5]}")
    except Exception as e:
        print(f"✗ Embedding 失败: {e}")
