import os
import json
import logging
import time
import uuid
import dashscope
from dashscope import MultiModalConversation
from dashscope.aigc.image_generation import ImageGeneration
try:
    from tool.image_processor import ImageProcessor
except ImportError:
    from image_processor import ImageProcessor

class DashScopeClient:
    def __init__(self, api_key=None, base_url=None):
        self.api_key = api_key or os.getenv("DASHSCOPE_API_KEY")
        # 默认使用中国（北京）地域 API，如果环境变量或参数未设置则使用默认地址
        self.base_url = base_url or os.getenv("DASHSCOPE_BASE_URL")
        dashscope.api_key = self.api_key
        dashscope.base_http_api_url = self.base_url
        self.image_processor = ImageProcessor()

    def generate_image(self, prompt, model="wan2.6-t2i", size="1024*1024", n=1, session_id=None, save_dir=None):
        """
        Text to Image generation using DashScope
        """
        try:
            messages = [{"role": "user", "content": [{"text": prompt}]}]
            response = ImageGeneration.call(
                model=model,
                api_key=self.api_key,
                messages=messages,
                n=n,
                size=size,
                watermark=False,
            )

            if response.status_code == 200:
                results = []
                try:
                    # 标准 ImageGeneration 返回结果解析
                    if response.output and response.output.choices:
                        for item in response.output.choices:
                            if 'message' in item and 'content' in item['message']:
                                results.append(item['message']['content'][0]['image'])
                except Exception as e:
                    logging.error(f"Failed to parse ImageGeneration outputs: {e}")
                
                # Check if we should download
                if save_dir:
                    os.makedirs(save_dir, exist_ok=True)
                    local_files = []
                    for i, url in enumerate(results):
                        file_name = f"ds_{session_id if session_id else 'nosess'}_{int(time.time())}_{i}_{uuid.uuid4().hex[:6]}.png"
                        file_path = os.path.join(save_dir, file_name)
                        if self.image_processor.download_image(url, file_path):
                            local_files.append(file_path)
                    return local_files
                
                return results
            else:
                logging.error(f"Image generation failed: {response.code}, {response.message}, status={response.status_code}")
                return []
        except Exception as e:
            logging.error(f"Error in generate_image (DashScope): {e}")
            return []

    def edit_image(self, prompt, image_urls, model="wan2.6-image", size="1920*1080", n=1, session_id=None, save_dir=None):
        """
        Image editing/compositing using DashScope ImageGeneration
        """
        # Prepare content
        content_list = []
        for img_url in image_urls:
            content_list.append({"image": img_url})
        content_list.append({"text": prompt})

        messages = [
            {
                "role": "user",
                "content": content_list
            }
        ]

        try:
            # Use ImageGeneration.call with messages, same as generate_image
            response = ImageGeneration.call(
                model=model,
                api_key=self.api_key,
                messages=messages,
                n=n,
                size=size,
                watermark=False,
            )

            if response.status_code == 200:
                results = []
                try:
                    # 标准 ImageGeneration 返回结果解析
                    if response.output and response.output.choices:
                        for item in response.output.choices:
                            # 简化解析逻辑以处理多张图片的返回结构
                            if isinstance(item, dict):
                                if 'image' in item: # 部分新模型直接返回 {'image': 'url', 'finish_reason': ...}
                                     results.append(item['image'])
                                elif 'url' in item:
                                     results.append(item['url'])
                                elif 'message' in item and 'content' in item['message']: # 兼容 Message 结构
                                    content = item['message']['content']
                                    if isinstance(content, list):
                                        for c in content:
                                            if isinstance(c, dict) and 'image' in c:
                                                results.append(c['image'])
                except Exception as e:
                    logging.error(f"Failed to parse ImageGeneration outputs: {e}")

                # Check if we should download
                if save_dir:
                    os.makedirs(save_dir, exist_ok=True)
                    local_files = []
                    for i, url in enumerate(results):
                        file_name = f"ds_{session_id if session_id else 'nosess'}_{int(time.time())}_{i}_{uuid.uuid4().hex[:6]}.png"
                        file_path = os.path.join(save_dir, file_name)
                        if self.image_processor.download_image(url, file_path):
                            local_files.append(file_path)
                    return local_files

                return results
            else:
                logging.error(f"Image edit failed: {response.code}, {response.message}, status={response.status_code}")
                return []
        except Exception as e:
            logging.error(f"Error in edit_image: {e}")
            return []


if __name__ == "__main__":
    import sys
    import tempfile
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from config import Config

    print("=== DashScope 图片生成可用性测试 ===")
    api_key = Config.DASHSCOPE_API_KEY
    base_url = Config.DASHSCOPE_BASE_URL
    if not api_key:
        print("✗ DASHSCOPE_API_KEY 未设置，跳过")
        sys.exit(1)
    print(f"  API Key: {api_key[:6]}***{api_key[-4:]}")
    print(f"  Base URL: {base_url}")
    client = DashScopeClient(api_key=api_key, base_url=base_url)
    prompt = "一只橘猫躺在阳光下的窗台上，水彩画风格"
    print(f"Prompt: {prompt}")
    with tempfile.TemporaryDirectory() as tmp:
        t0 = time.time()
        try:
            paths = client.generate_image(
                prompt=prompt, model="wan2.6-t2i",
                size="1024*1024", save_dir=tmp,
            )
            elapsed = time.time() - t0
            if paths:
                print(f"✓ 生成 {len(paths)} 张图片 ({elapsed:.1f}s): {paths}")
            else:
                print(f"✗ 返回空列表 ({elapsed:.1f}s)")
        except Exception as e:
            print(f"✗ 失败: {e}")
            sys.exit(1)
