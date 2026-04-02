import os
import time
import uuid
import base64
import httpx
from openai import OpenAI
try:
    from tool.image_processor import ImageProcessor
except ImportError:
    from image_processor import ImageProcessor


class ImageGPT:
    """
    OpenAI 图片生成客户端
    支持模型：
        - sora_image    → Images API（通过代理/中转服务器）
        - gpt-image-1.5 → Responses API（直连官方，走本地代理）
    """
    def __init__(self, base_url="", api_key="", timeout=300,
                 official_api_key="", local_proxy=""):
        # 普通客户端（可连接代理/中转服务器，用于 sora_image 等）
        if base_url:
            self.client = OpenAI(api_key=api_key, base_url=base_url, timeout=timeout)
        else:
            self.client = OpenAI(api_key=api_key, timeout=timeout)
        self.max_attempts = 10
        self.image_processor = ImageProcessor()

        # 官方直连客户端（仅 gpt-image-1.5 等需要直连官方 API 的模型使用）
        self._official_client = None
        self._official_api_key = official_api_key
        self._local_proxy = local_proxy
        self._timeout = timeout

    def _get_official_client(self):
        """懒加载官方 OpenAI 客户端，通过本地代理访问"""
        if self._official_client is None:
            if not self._official_api_key:
                raise ValueError("使用 gpt-image-1.5 需要设置 OPENAI_OFFICIAL_API_KEY（官方 OpenAI API Key）")
            kwargs = {"timeout": self._timeout}
            if self._local_proxy:
                kwargs["http_client"] = httpx.Client(
                    proxy=self._local_proxy,
                    timeout=self._timeout,
                )
            self._official_client = OpenAI(api_key=self._official_api_key, **kwargs)
        return self._official_client

    def generate_image(self, prompt, size="1024x1024", quality="standard", model=None,
                       save_dir=None, image_urls=None):
        """Generate a single image, download it, and return the local file path.

        Args:
            prompt: 图片描述提示词
            size: 图片尺寸
            quality: 图片质量
            model: 模型名称 (sora_image / gpt-image-1.5)
            save_dir: 保存目录（不传则返回 URL 或 base64）
            image_urls: 参考图片 URL 列表（仅 gpt-image-1.5 支持）
        """
        if model is None:
            model = "sora_image"

        # gpt-image-1.5 走官方 Responses API
        if model == "gpt-image-1.5":
            return self._generate_image_official(prompt, size=size, quality=quality,
                                                  save_dir=save_dir, image_urls=image_urls)

        # 其他模型走普通 Images API
        return self._generate_image_legacy(prompt, size=size, quality=quality,
                                            model=model, save_dir=save_dir)

    def _generate_image_official(self, prompt, size="1024x1024", quality="standard",
                                  save_dir=None, image_urls=None):
        """通过官方 Responses API 生成图片 (gpt-image-1.5)，走本地代理"""
        client = self._get_official_client()

        # 构建 input content
        content = [{"type": "input_text", "text": prompt}]
        if image_urls:
            for url in image_urls:
                content.append({"type": "input_image", "image_url": url})

        attempts = 0
        last_error = None
        while attempts < self.max_attempts:
            try:
                response = client.responses.create(
                    model="gpt-image-1.5",
                    input=[{"role": "user", "content": content}],
                    tools=[{"type": "image_generation", "size": size, "quality": quality}],
                )

                # 从 output 中提取 image_generation_call 结果
                image_data = [
                    output.result for output in response.output
                    if output.type == "image_generation_call"
                ]

                if image_data:
                    b64 = image_data[0]
                    if save_dir:
                        os.makedirs(save_dir, exist_ok=True)
                        file_name = f"gptimg_{int(time.time())}_{uuid.uuid4().hex[:6]}.png"
                        file_path = os.path.join(save_dir, file_name)
                        with open(file_path, "wb") as f:
                            f.write(base64.b64decode(b64))
                        return file_path
                    else:
                        return b64  # 返回 base64 字符串
                else:
                    text_output = " ".join(
                        getattr(o, "text", "") for o in response.output if hasattr(o, "text")
                    ).strip()
                    print(f"gpt-image-1.5: 未返回图片。模型回复: {text_output[:200]}")
            except Exception as e:
                last_error = e
                print(f"gpt-image-1.5 Error: {e}. Retrying in 10s.")
            time.sleep(10)
            attempts += 1

        raise Exception(f"gpt-image-1.5: 达到最大重试次数。Last error: {last_error}")

    def _generate_image_legacy(self, prompt, size="1024x1024", quality="standard",
                                model="sora_image", save_dir=None):
        """通过 Images API 生成图片 (sora_image 等)"""
        # Fallback chain: user's choice -> sora_image
        models_to_try = [model, "sora_image"]
        models_to_try = list(dict.fromkeys(models_to_try))  # Remove duplicates

        attempts = 0
        last_error = None
        while attempts < self.max_attempts:
            for m in models_to_try:
                try:
                    response = self.client.images.generate(
                        model=m,
                        prompt=prompt,
                        size=size,
                        quality=quality,
                        n=1,
                    )
                    if response and response.data and response.data[0].url:
                        url = response.data[0].url
                        if save_dir:
                            os.makedirs(save_dir, exist_ok=True)
                            file_name = f"sora_{int(time.time())}_{uuid.uuid4().hex[:6]}.png"
                            file_path = os.path.join(save_dir, file_name)
                            if self.image_processor.download_image(url, file_path):
                                return file_path
                            else:
                                print(f"Failed to save image from {url}")
                        else:
                            return url
                except Exception as e:
                    last_error = e
                    msg = str(e)
                    # Model not found or no distributor: try next model
                    if "model_not_found" in msg or "无可用渠道" in msg or "distributor" in msg:
                        continue
                    # Other errors: wait before retry
                    print(f"Image generation error: {e}. Retrying in 10 seconds.")
                    time.sleep(10)
                    break  # Break inner loop to retry all models
            attempts += 1
        raise Exception(f"Max attempts reached, failed to generate image. Last error: {last_error}")

    def generate_images(self, prompt, count=4, size="1024x1024", quality="standard", model=None):
        """Generate multiple image URLs by calling Images API 'count' times."""
        urls = []
        for _ in range(count):
            url = self.generate_image(prompt=prompt, size=size, quality=quality, model=model)
            urls.append(url)
        return urls


if __name__ == "__main__":
    import sys
    import tempfile
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from config import Config

    print("=== GPT 图片生成可用性测试 ===")
    api_key = Config.OPENAI_API_KEY
    base_url = Config.OPENAI_BASE_URL
    official_key = Config.OPENAI_OFFICIAL_API_KEY
    local_proxy = Config.LOCAL_PROXY

    if not api_key and not official_key:
        print("✗ OPENAI_API_KEY 和 OPENAI_OFFICIAL_API_KEY 均未设置，跳过")
        sys.exit(1)

    print(f"  API Key: {api_key[:6]}***{api_key[-4:] if api_key else '(未设置)'}")
    print(f"  Base URL: {base_url}")
    print(f"  Official Key: {official_key[:6]}***{official_key[-4:] if official_key else '(未设置)'}")
    print(f"  Local Proxy: {local_proxy or '(未设置)'}")

    client = ImageGPT(api_key=api_key, base_url=base_url,
                      official_api_key=official_key, local_proxy=local_proxy)

    # 1. sora_image 图片生成（仅尝试 1 次）
    if api_key:
        img_prompt = "一只橘猫躺在阳光下的窗台上"
        print(f"\n[1/2 sora_image] Prompt: {img_prompt}")
        client.max_attempts = 1
        t0 = time.time()
        try:
            with tempfile.TemporaryDirectory() as tmp:
                path = client.generate_image(prompt=img_prompt, size="1024x1024", model="sora_image", save_dir=tmp)
                elapsed = time.time() - t0
                print(f"✓ 生成成功 ({elapsed:.1f}s): {path}")
        except Exception as e:
            elapsed = time.time() - t0
            print(f"✗ 图片生成失败 ({elapsed:.1f}s): {e}\n  (该代理可能不支持 sora_image 模型)")
    else:
        print("\n[1/2 sora_image] 跳过（OPENAI_API_KEY 未设置）")

    # 2. gpt-image-1.5 图片生成（官方 API + 本地代理）
    if official_key:
        img_prompt = "A cute orange cat lying on a sunny windowsill, watercolor style"
        print(f"\n[2/2 gpt-image-1.5] Prompt: {img_prompt}")
        client.max_attempts = 1
        t0 = time.time()
        try:
            with tempfile.TemporaryDirectory() as tmp:
                path = client.generate_image(prompt=img_prompt, size="1024x1024",
                                              model="gpt-image-1.5", save_dir=tmp)
                elapsed = time.time() - t0
                print(f"✓ 生成成功 ({elapsed:.1f}s): {path}")
        except Exception as e:
            elapsed = time.time() - t0
            print(f"✗ gpt-image-1.5 失败 ({elapsed:.1f}s): {e}")
    else:
        print("\n[2/2 gpt-image-1.5] 跳过（OPENAI_OFFICIAL_API_KEY 未设置）")
