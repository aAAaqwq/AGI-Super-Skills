# Google AI Studio 多模态生成能力完整指南

> 研究日期: 2026-03-12  
> 研究目的: 为 Daniel 的多模态生成需求提供技术参考

---

## 目录

1. [模型对比总览](#1-模型对比总览)
2. [Imagen 4 图像生成](#2-imagen-4-图像生成)
3. [Nano Banana Pro 图像生成](#3-nano-banana-pro-图像生成)
4. [Veo 3.1 视频生成](#4-veo-31-视频生成)
5. [Gemini 3.1 Pro 推理模型](#5-gemini-31-pro-推理模型)
6. [价格对比表](#6-价格对比表)
7. [限制与配额](#7-限制与配额)
8. [Agent 调用代码示例](#8-agent-调用代码示例)
9. [最佳实践建议](#9-最佳实践建议)

---

## 1. 模型对比总览

### 图像生成模型

| 模型 | 模型 ID | 特点 | 最佳场景 | 价格 |
|------|---------|------|----------|------|
| **Imagen 4 Ultra** | `imagen-4.0-generate-001` (ultra) | 最高质量，精确文本渲染 | 专业设计、海报、品牌物料 | $0.06/图 |
| **Imagen 4 Standard** | `imagen-4.0-generate-001` (standard) | 平衡质量与速度 | 通用图像生成 | $0.04/图 |
| **Imagen 4 Fast** | `imagen-4.0-generate-001` (fast) | 最快生成速度 | 快速原型、批量生成 | $0.02/图 |
| **Nano Banana Pro** | `gemini-3-pro-image-preview` | 高容量优化，多语言文本 | 国际化内容、快速迭代 | Token计费 |

### 视频生成模型

| 模型 | 模型 ID | 特点 | 最佳场景 | 价格 |
|------|---------|------|----------|------|
| **Veo 3.1** | `veo-3.1-generate-001` | 最新一代，原生音频 | 专业视频、广告、短视频 | $0.50-0.75/秒 |
| **Veo 3.1 Fast** | `veo-3.1-generate-preview` | 快速生成 | 快速原型 | ~$0.30/8秒视频 |

### 推理模型

| 模型 | 模型 ID | 特点 | 最佳场景 | 价格 |
|------|---------|------|----------|------|
| **Gemini 3.1 Pro** | `gemini-3.1-pro-preview` | 1M上下文，动态推理 | 复杂推理、多模态理解 | $2-4/M input, $12-18/M output |

---

## 2. Imagen 4 图像生成

### 模型信息

| 属性 | 值 |
|------|-----|
| **模型 ID** | `imagen-4.0-generate-001` |
| **输入类型** | Text |
| **输出类型** | Images (1-4张) |
| **输入 Token 限制** | 480 tokens |
| **最大分辨率** | 2048x2048 (2K) |
| **支持语言** | 仅英语 |
| **水印** | SynthID 隐形水印 |

### 三种质量级别

| 级别 | 价格 | 速度 | 适用场景 |
|------|------|------|----------|
| **Fast** | $0.02/图 | 最快 (~10x vs 上一代) | 快速原型、批量测试、简单图形 |
| **Standard** | $0.04/图 | 平衡 | 通用用途、社交媒体图片 |
| **Ultra** | $0.06/图 | 最慢但最高质量 | 专业设计、品牌物料、印刷品 |

### 支持的参数

```python
# Imagen 4 API 参数
parameters = {
    "sampleCount": 1,        # 1-4 张图片
    "aspectRatio": "16:9",   # 宽高比: "16:9", "9:16", "1:1"
    "personGeneration": "allow_all",  # 人物生成设置
    "negativePrompt": "...", # 负面提示词
    "seed": 12345,          # 随机种子（可选）
}
```

### 提示词最佳实践

```text
# 结构化提示词公式
<Create/generate an image of> <subject> <action> <scene>

# 专业提示词元素
- Camera Proximity: close up, taken from far away
- Camera Position: aerial, from below
- Lighting: natural, dramatic, warm, cold
- Camera Settings: motion blur, soft focus, bokeh, portrait
- Lens Types: 35mm, 50mm, fisheye, wide angle, macro
- Film Types: black and white, polaroid

# 示例
"A woman, 35mm portrait, blue and grey duotones"
"A minimalist logo for a health care company on a solid color background. Include the text Journey."
```

### API 调用示例

```python
# 使用 google-genai SDK
from google import genai
from google.genai import types

client = genai.Client(api_key="YOUR_API_KEY")

response = client.models.generate_images(
    model="imagen-4.0-generate-001",
    prompt="A serene mountain landscape at sunset, photorealistic, 35mm lens",
    config=types.GenerateImagesConfig(
        number_of_images=4,
        aspect_ratio="16:9",
        # quality: "fast" | "standard" | "ultra"
    )
)

for i, image in enumerate(response.generated_images):
    image.save(f"output_{i}.png")
```

```python
# REST API 调用
import requests

url = "https://generativelanguage.googleapis.com/v1beta/models/imagen-4.0-generate-001:predict"
headers = {
    "x-goog-api-key": "YOUR_API_KEY",
    "Content-Type": "application/json"
}
data = {
    "instances": [{"prompt": "A cat reading a book"}],
    "parameters": {"sampleCount": 1}
}

response = requests.post(url, headers=headers, json=data)
image_data = response.json()["predictions"][0]["bytesBase64Encoded"]
```

---

## 3. Nano Banana Pro 图像生成

### 模型信息

| 属性 | 值 |
|------|-----|
| **模型 ID** | `gemini-3-pro-image-preview` 或 `gemini-2.5-flash-image` |
| **特点** | 高容量优化，低延迟 |
| **最大分辨率** | 最高 4K (4096x4096) |
| **多语言文本** | 支持多种语言精确文本渲染 |
| **水印** | SynthID 隐形水印 |
| **价格** | Token 计费 ($120/M image output tokens) |

### Token 消耗

| 分辨率 | Token 消耗 | 实际成本 |
|--------|-----------|----------|
| 1K (1024x1024) | 1120 tokens | ~$0.134/图 |
| 2K (2048x2048) | 1120 tokens | ~$0.134/图 |
| 4K (4096x4096) | 2000 tokens | ~$0.24/图 |

### 最佳场景

- **国际化内容**: 多语言文本渲染（海报、mockups）
- **品牌一致性**: 高保真视觉，一致的品牌元素
- **快速迭代**: 高容量低延迟优化
- **Redo with Pro**: 从简单版本升级到专业版本

### API 调用示例

```python
from google import genai
from google.genai import types

client = genai.Client(api_key="YOUR_API_KEY")

response = client.models.generate_content(
    model="gemini-3-pro-image-preview",
    contents="Generate an image of a futuristic cityscape at night with neon signs in Japanese and English",
    config=types.GenerateContentConfig(
        response_modalities=["IMAGE", "TEXT"],
    )
)

# 保存图片
if response.candidates[0].content.parts[0].inline_data:
    image_data = response.candidates[0].content.parts[0].inline_data.data
    with open("output.png", "wb") as f:
        f.write(image_data)
```

---

## 4. Veo 3.1 视频生成

### 模型信息

| 属性 | 值 |
|------|-----|
| **模型 ID** | `veo-3.1-generate-001` / `veo-3.1-generate-preview` |
| **默认时长** | 8 秒 |
| **分辨率** | 720p, 1080p |
| **宽高比** | 16:9, 9:16 |
| **原生音频** | 支持（可选） |
| **输出数量** | 1-4 个视频 |
| **生成时间** | 11秒 - 6分钟（视复杂度） |

### 定价

| 类型 | 价格 |
|------|------|
| **Video Only (无音频)** | $0.50/秒 |
| **Video + Audio (带音频)** | $0.75/秒 |
| **8秒视频估算** | $4.00 - $6.00 |

### 支持的功能

| 功能 | 描述 |
|------|------|
| **Text-to-Video** | 从文本提示生成视频 |
| **Image-to-Video** | 从首帧图像生成视频 |
| **First + Last Frame** | 从首尾帧生成中间过渡 |
| **Video Extension** | 扩展现有视频 |
| **Reference Images** | 使用1-3张参考图引导生成 |

### API 参数

```python
from google.genai.types import GenerateVideosConfig

config = GenerateVideosConfig(
    aspect_ratio="16:9",        # "16:9" 或 "9:16"
    resolution="1080p",         # "720p" 或 "1080p" (Veo 3 only)
    sample_count=1,             # 1-4
    person_generation="allow_all",
    negative_prompt="blurry, low quality",
    seed=12345,
)
```

### API 调用示例

```python
# 基本文本生成视频
import time
from google import genai
from google.genai.types import GenerateVideosConfig

client = genai.Client(api_key="YOUR_API_KEY")

# 发起异步生成请求
operation = client.models.generate_videos(
    model="veo-3.1-generate-001",
    prompt="An origami butterfly flaps its wings and flies out of the french doors into the garden.",
    config=GenerateVideosConfig(
        aspect_ratio="16:9",
        resolution="1080p",
    )
)

# 轮询等待完成
while not operation.done:
    time.sleep(10)
    operation = client.operations.get(operation.name)

# 获取生成的视频
video = operation.response.generated_videos[0]
video.save("output.mp4")
```

```python
# 从首帧图像生成视频
from google.genai.types import GenerateVideosConfig, Image

operation = client.models.generate_videos(
    model="veo-3.1-generate-001",
    prompt="A hand reaches in and places a glass of milk next to the plate of cookies",
    image=Image(
        gcs_uri="gs://your-bucket/first_frame.png",
        mime_type="image/png",
    ),
    config=GenerateVideosConfig(
        aspect_ratio="16:9",
    )
)
```

```python
# REST API 调用
import requests
import time

BASE_URL = "https://generativelanguage.googleapis.com/v1beta"
API_KEY = "YOUR_API_KEY"

# Step 1: 发起生成请求
response = requests.post(
    f"{BASE_URL}/models/veo-3.1-generate-preview:predictLongRunning",
    headers={"x-goog-api-key": API_KEY},
    json={
        "instances": [{
            "prompt": "A cinematic shot of waves crashing on a beach at sunset"
        }],
        "parameters": {
            "aspectRatio": "16:9",
            "resolution": "1080p",
            "sampleCount": 1
        }
    }
)

operation_name = response.json()["name"]

# Step 2: 轮询状态
while True:
    status = requests.get(
        f"{BASE_URL}/{operation_name}",
        headers={"x-goog-api-key": API_KEY}
    ).json()
    
    if status.get("done"):
        video_data = status["response"]["generatedVideos"][0]["video"]["bytesBase64Encoded"]
        break
    
    time.sleep(10)
```

---

## 5. Gemini 3.1 Pro 推理模型

### 模型信息

| 属性 | 值 |
|------|-----|
| **模型 ID** | `gemini-3.1-pro-preview` |
| **上下文窗口** | 1,048,576 tokens (1M) |
| **动态推理** | 默认开启 |
| **多模态** | 文本、图像、视频、音频、代码 |
| **Context Caching** | 支持 |

### 新特性 (3.1 vs 3.0)

- **新增 MEDIUM thinking_level**: 更灵活的成本/性能权衡
- **更高效的推理**: 各类用例下 token 效率提升
- **Custom Tools 变体**: `gemini-3.1-pro-preview-customtools`

### 定价

| Token 量级 | 输入价格 | 输出价格 |
|-----------|---------|---------|
| ≤ 200k tokens | $2.00/M | $12.00/M |
| > 200k tokens | $4.00/M | $18.00/M |

### 关键参数

```python
from google.genai import types

config = types.GenerateContentConfig(
    # 推理级别控制 (3.1 新增 medium)
    thinking_level="medium",  # "low" | "medium" | "high"
    
    # 媒体分辨率控制
    media_resolution="high",  # "low" | "medium" | "high"
    
    # Grounding (搜索增强)
    tools=[types.Tool(google_search=types.GoogleSearch())],
)
```

### 思考级别对比

| 级别 | 适用场景 | 延迟 | 成本 |
|------|---------|------|------|
| **low** | 简单查询、快速响应 | 最低 | 最低 |
| **medium** | 中等复杂度、平衡场景 | 中等 | 中等 |
| **high** | 复杂推理、深度分析 | 最高 | 最高 |

### API 调用示例

```python
from google import genai
from google.genai import types

client = genai.Client(api_key="YOUR_API_KEY")

response = client.models.generate_content(
    model="gemini-3.1-pro-preview",
    contents="分析这张图片中的所有元素，并提供详细描述",
    config=types.GenerateContentConfig(
        thinking_level="high",
        media_resolution="high",
    )
)

# 获取推理过程和最终答案
for part in response.candidates[0].content.parts:
    if hasattr(part, 'thought') and part.thought:
        print(f"推理: {part.thought}")
    elif hasattr(part, 'text'):
        print(f"回答: {part.text}")
```

---

## 6. 价格对比表

### 图像生成价格对比

| 模型 | 每张价格 | 8张成本 | 100张成本 |
|------|---------|---------|----------|
| Imagen 4 Fast | $0.02 | $0.16 | $2.00 |
| Imagen 4 Standard | $0.04 | $0.32 | $4.00 |
| Imagen 4 Ultra | $0.06 | $0.48 | $6.00 |
| Nano Banana Pro (1K-2K) | ~$0.13 | ~$1.04 | ~$13.00 |
| Nano Banana Pro (4K) | ~$0.24 | ~$1.92 | ~$24.00 |

### 视频生成价格对比

| 模型 | 每秒价格 | 8秒视频 | 30秒视频 |
|------|---------|---------|---------|
| Veo 3.1 (Video Only) | $0.50 | $4.00 | $15.00 |
| Veo 3.1 (Video + Audio) | $0.75 | $6.00 | $22.50 |

### 推理模型价格对比

| 模型 | Input ≤200k | Input >200k | Output ≤200k | Output >200k |
|------|------------|-------------|--------------|--------------|
| Gemini 3.1 Pro | $2/M | $4/M | $12/M | $18/M |
| Gemini 3 Pro | $2/M | $4/M | $12/M | $18/M |
| Gemini 2.5 Pro | $1.25/M | $2.50/M | $5/M | $10/M |
| Gemini 2.5 Flash | $0.075/M | - | $0.30/M | - |

---

## 7. 限制与配额

### Imagen 4 限制

| 限制项 | 值 |
|--------|-----|
| 单次请求数量 | 1-4 张图片 |
| 输入 Token | 480 tokens max |
| 支持语言 | 仅英语 |
| 最大分辨率 | 2048x2048 |

### Veo 3.1 限制

| 限制项 | 值 |
|--------|-----|
| 默认时长 | 8 秒 |
| 分辨率 | 720p, 1080p |
| 单次请求数量 | 1-4 个视频 |
| 生成时间 | 11秒 - 6分钟 |
| 参考图片 | 1-3 张 |

### Gemini 3.1 Pro 限制

| 限制项 | 值 |
|--------|-----|
| 上下文窗口 | 1M tokens |
| Rate Limit (Tier 1) | 250 RPD, 10 RPM |
| Rate Limit (Tier 2) | 1000 RPD, 30 RPM |
| Context Cache TTL | 1小时起 |

### 配额提升路径

| Tier | 累计消费要求 | RPM | RPD | TPM |
|------|------------|-----|-----|-----|
| 1 | $0 | 2 | 100 | 1M |
| 2 | $50+ | 10 | 1000 | 4M |
| 3 | $1500+ | 30 | 5000 | 10M |

---

## 8. Agent 调用代码示例

### 小content Agent - 生图脚本

```python
#!/usr/bin/env python3
"""
小content Agent - Imagen 4 图像生成工具
用于小content agent 调用的图像生成脚本
"""

import os
import sys
import json
import base64
from pathlib import Path
from google import genai
from google.genai import types

def generate_image(
    prompt: str,
    output_dir: str = "./generated_images",
    quality: str = "standard",  # fast, standard, ultra
    aspect_ratio: str = "16:9",
    count: int = 1,
) -> list[str]:
    """
    使用 Imagen 4 生成图像
    
    Args:
        prompt: 英文提示词
        output_dir: 输出目录
        quality: 质量级别 (fast/standard/ultra)
        aspect_ratio: 宽高比 (16:9, 9:16, 1:1)
        count: 生成数量 (1-4)
    
    Returns:
        生成的图片路径列表
    """
    client = genai.Client(api_key=os.environ.get("GOOGLE_API_KEY"))
    
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    
    response = client.models.generate_images(
        model="imagen-4.0-generate-001",
        prompt=prompt,
        config=types.GenerateImagesConfig(
            number_of_images=min(count, 4),
            aspect_ratio=aspect_ratio,
        )
    )
    
    saved_paths = []
    for i, image in enumerate(response.generated_images):
        output_path = f"{output_dir}/image_{i}_{quality}.png"
        image.save(output_path)
        saved_paths.append(output_path)
        print(f"✅ 已保存: {output_path}")
    
    return saved_paths

def generate_image_nano_banana(
    prompt: str,
    output_path: str = "./generated_image.png",
    model: str = "gemini-3-pro-image-preview",
) -> str:
    """
    使用 Nano Banana Pro 生成图像（支持多语言文本）
    
    Args:
        prompt: 提示词（支持中文）
        output_path: 输出路径
        model: 模型选择
    
    Returns:
        生成的图片路径
    """
    client = genai.Client(api_key=os.environ.get("GOOGLE_API_KEY"))
    
    response = client.models.generate_content(
        model=model,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_modalities=["IMAGE", "TEXT"],
        )
    )
    
    for part in response.candidates[0].content.parts:
        if hasattr(part, 'inline_data') and part.inline_data:
            image_data = base64.b64decode(part.inline_data.data)
            with open(output_path, "wb") as f:
                f.write(image_data)
            print(f"✅ 已保存: {output_path}")
            return output_path
    
    raise ValueError("未能生成图像")

# CLI 入口
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python generate_image.py <prompt> [--quality standard] [--ratio 16:9] [--count 1]")
        sys.exit(1)
    
    prompt = sys.argv[1]
    quality = "standard"
    ratio = "16:9"
    count = 1
    
    i = 2
    while i < len(sys.argv):
        if sys.argv[i] == "--quality":
            quality = sys.argv[i + 1]
            i += 2
        elif sys.argv[i] == "--ratio":
            ratio = sys.argv[i + 1]
            i += 2
        elif sys.argv[i] == "--count":
            count = int(sys.argv[i + 1])
            i += 2
        else:
            i += 1
    
    generate_image(prompt, quality=quality, aspect_ratio=ratio, count=count)
```

### 小content Agent - 生视频脚本

```python
#!/usr/bin/env python3
"""
小content Agent - Veo 3.1 视频生成工具
用于小content agent 调用的视频生成脚本
"""

import os
import sys
import time
from google import genai
from google.genai.types import GenerateVideosConfig, Image

def generate_video(
    prompt: str,
    output_path: str = "./generated_video.mp4",
    aspect_ratio: str = "16:9",
    resolution: str = "1080p",
    with_audio: bool = True,
    first_frame: str = None,
    timeout: int = 600,  # 10分钟超时
) -> str:
    """
    使用 Veo 3.1 生成视频
    
    Args:
        prompt: 英文提示词
        output_path: 输出路径
        aspect_ratio: 宽高比 (16:9, 9:16)
        resolution: 分辨率 (720p, 1080p)
        with_audio: 是否生成音频
        first_frame: 首帧图片路径（可选）
        timeout: 超时秒数
    
    Returns:
        生成的视频路径
    """
    client = genai.Client(api_key=os.environ.get("GOOGLE_API_KEY"))
    
    config = GenerateVideosConfig(
        aspect_ratio=aspect_ratio,
        resolution=resolution,
    )
    
    kwargs = {
        "model": "veo-3.1-generate-001",
        "prompt": prompt,
        "config": config,
    }
    
    # 如果有首帧图片
    if first_frame and os.path.exists(first_frame):
        # 需要先上传到 GCS
        # kwargs["image"] = Image(gcs_uri="gs://...", mime_type="image/png")
        print("⚠️ 首帧图片需要先上传到 Google Cloud Storage")
    
    # 发起异步生成请求
    print(f"🎬 开始生成视频: {prompt[:50]}...")
    operation = client.models.generate_videos(**kwargs)
    
    # 轮询等待完成
    start_time = time.time()
    while not operation.done:
        elapsed = time.time() - start_time
        if elapsed > timeout:
            raise TimeoutError(f"视频生成超时 ({timeout}秒)")
        
        print(f"⏳ 生成中... ({int(elapsed)}秒)")
        time.sleep(10)
        operation = client.operations.get(operation.name)
    
    # 保存视频
    if operation.response and operation.response.generated_videos:
        video = operation.response.generated_videos[0]
        video.save(output_path)
        print(f"✅ 视频已保存: {output_path}")
        return output_path
    else:
        raise ValueError("视频生成失败")

def extend_video(
    video_path: str,
    prompt: str,
    output_path: str = "./extended_video.mp4",
) -> str:
    """
    扩展现有视频
    
    Args:
        video_path: 原视频路径
        prompt: 扩展提示词
        output_path: 输出路径
    
    Returns:
        扩展后的视频路径
    """
    # 实现视频扩展逻辑
    # 需要先上传原视频到 GCS
    print("⚠️ 视频扩展需要先将视频上传到 Google Cloud Storage")
    pass

# CLI 入口
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python generate_video.py <prompt> [--ratio 16:9] [--resolution 1080p] [--output video.mp4]")
        sys.exit(1)
    
    prompt = sys.argv[1]
    ratio = "16:9"
    resolution = "1080p"
    output = "./generated_video.mp4"
    
    i = 2
    while i < len(sys.argv):
        if sys.argv[i] == "--ratio":
            ratio = sys.argv[i + 1]
            i += 2
        elif sys.argv[i] == "--resolution":
            resolution = sys.argv[i + 1]
            i += 2
        elif sys.argv[i] == "--output":
            output = sys.argv[i + 1]
            i += 2
        else:
            i += 1
    
    generate_video(prompt, aspect_ratio=ratio, resolution=resolution, output_path=output)
```

### Bash 快捷脚本

```bash
#!/bin/bash
# quick_gen_image.sh - 快速生成图片

PROMPT="$1"
QUALITY="${2:-standard}"
RATIO="${3:-16:9}"

if [ -z "$PROMPT" ]; then
    echo "用法: ./quick_gen_image.sh <prompt> [quality] [ratio]"
    echo "示例: ./quick_gen_image.sh 'A cat reading a book' standard 16:9"
    exit 1
fi

python3 -c "
from google import genai
from google.genai import types
import os

client = genai.Client(api_key=os.environ.get('GOOGLE_API_KEY'))

response = client.models.generate_images(
    model='imagen-4.0-generate-001',
    prompt='$PROMPT',
    config=types.GenerateImagesConfig(
        number_of_images=1,
        aspect_ratio='$RATIO',
    )
)

response.generated_images[0].save('output.png')
print('✅ 已保存: output.png')
"

echo "打开图片: open output.png"
```

---

## 9. 最佳实践建议

### 成本优化策略

1. **图像生成**
   - 原型阶段用 Imagen 4 Fast ($0.02/图)
   - 最终输出用 Imagen 4 Standard/Ultra
   - 大批量考虑 Nano Banana Pro Token 计费

2. **视频生成**
   - 测试用 720p 无音频 ($0.50/秒)
   - 最终用 1080p + 音频 ($0.75/秒)
   - 8秒够用就不要更长

3. **推理模型**
   - 简单任务用 thinking_level="low"
   - 复杂推理用 "high"
   - 利用 Context Caching 减少重复输入

### 提示词优化

1. **Imagen 4**
   - 使用结构化提示词: subject + action + scene
   - 添加专业摄影术语增强效果
   - 文本渲染用明确的 "Include the text XXX"

2. **Veo 3.1**
   - 描述动态过程而非静态场景
   - 指定镜头运动和转场
   - 音频需求明确说明

3. **Nano Banana Pro**
   - 可用中文提示词（多语言支持）
   - 适合国际化内容创作
   - 利用 "Redo with Pro" 功能迭代

### 风险与注意事项

1. **配额限制**: Tier 1 只有 100 RPD，生产环境需要升级
2. **语言限制**: Imagen 4 仅支持英文，Nano Banana Pro 支持多语言
3. **水印**: 所有生成图片都有 SynthID 隐形水印
4. **异步生成**: 视频生成需要轮询，注意超时处理
5. **GCS 依赖**: 视频的参考图片/首帧需要上传到 Google Cloud Storage

---

## 附录: 快速参考卡

### 模型选择决策树

```
需要生成什么?
├── 图像
│   ├── 需要多语言文本? → Nano Banana Pro
│   ├── 快速/批量? → Imagen 4 Fast
│   ├── 专业质量? → Imagen 4 Ultra
│   └── 平衡? → Imagen 4 Standard
│
├── 视频
│   ├── 快速原型? → Veo 3.1 Fast (第三方API)
│   └── 专业视频? → Veo 3.1 官方API
│
└── 推理/理解
    └── Gemini 3.1 Pro (thinking_level 调整)
```

### 价格速查

| 操作 | 成本 |
|------|------|
| 1张 Fast 图片 | $0.02 |
| 1张 Standard 图片 | $0.04 |
| 1张 Ultra 图片 | $0.06 |
| 1个 8秒视频 (无音频) | $4.00 |
| 1个 8秒视频 (有音频) | $6.00 |
| 1M tokens 输入 (≤200k) | $2.00 |
| 1M tokens 输出 (≤200k) | $12.00 |

---

*文档生成时间: 2026-03-12 02:30 Asia/Shanghai*  
*数据来源: Google AI 官方文档、Brave Search、第三方服务商价格对比*
