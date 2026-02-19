#!/usr/bin/env python3
"""
多模态生成工具 - 图像和视频生成
使用 xingjiabiapi 的各种生成模型
"""

import os
import sys
import json
import time
import requests
import subprocess
from pathlib import Path

# 获取 API Key
def get_api_key():
    try:
        result = subprocess.run(['pass', 'show', 'api/xingjiabiapi'], 
                              capture_output=True, text=True)
        return result.stdout.strip()
    except:
        return os.environ.get('XINGJIABIAPI_KEY', '')

API_KEY = get_api_key()
BASE_URL = "https://xingjiabiapi.com/v1"

# 模型别名映射
IMAGE_MODELS = {
    'flux': 'flux-pro-max',
    'fluxk': 'flux-kontext-max',
    'imagen': 'google/imagen-4-ultra',
    'dalle': 'gpt-image-1',
    'doubao': 'doubao-seedream-4-5-251128',
    'klingimg': 'kling-image',
    'g3pi': 'gemini-3-pro-image-preview',
}

VIDEO_MODELS = {
    'veo': 'veo3.1',
    'veopro': 'veo3.1-pro',
    'veo4k': 'veo3.1-pro-4k',
    'sora': 'sora-2-pro-all',
    'kling': 'kling-video',
    'hailuo': 'MiniMax-Hailuo-2.3',
}

def resolve_model(model_name, model_type='image'):
    """解析模型别名"""
    models = IMAGE_MODELS if model_type == 'image' else VIDEO_MODELS
    return models.get(model_name, model_name)

def generate_image(prompt, model='flux-pro-max', size='1024x1024', n=1):
    """生成图像"""
    model = resolve_model(model, 'image')
    
    response = requests.post(
        f"{BASE_URL}/images/generations",
        headers={
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json"
        },
        json={
            "model": model,
            "prompt": prompt,
            "n": n,
            "size": size
        },
        timeout=120
    )
    
    if response.status_code == 200:
        data = response.json()
        return {
            "success": True,
            "model": model,
            "images": data.get("data", [])
        }
    else:
        return {
            "success": False,
            "error": response.text
        }

def generate_video(prompt, model='veo3.1-pro', duration=5):
    """生成视频"""
    model = resolve_model(model, 'video')
    
    response = requests.post(
        f"{BASE_URL}/videos/generations",
        headers={
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json"
        },
        json={
            "model": model,
            "prompt": prompt,
            "duration": duration
        },
        timeout=300
    )
    
    if response.status_code == 200:
        data = response.json()
        return {
            "success": True,
            "model": model,
            "video": data
        }
    else:
        return {
            "success": False,
            "error": response.text
        }

def save_media(url, output_dir="~/clawd/output", prefix="gen"):
    """下载并保存媒体文件"""
    output_dir = Path(output_dir).expanduser()
    output_dir.mkdir(parents=True, exist_ok=True)
    
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    
    # 根据 URL 判断文件类型
    if any(ext in url.lower() for ext in ['.mp4', '.webm', '.mov']):
        ext = '.mp4'
        subdir = 'videos'
    else:
        ext = '.png'
        subdir = 'images'
    
    (output_dir / subdir).mkdir(exist_ok=True)
    filename = f"{prefix}_{timestamp}{ext}"
    filepath = output_dir / subdir / filename
    
    response = requests.get(url, timeout=60)
    if response.status_code == 200:
        with open(filepath, 'wb') as f:
            f.write(response.content)
        return str(filepath)
    return None

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="多模态生成工具")
    parser.add_argument("type", choices=["image", "video"], help="生成类型")
    parser.add_argument("prompt", help="生成提示词")
    parser.add_argument("--model", "-m", default=None, help="模型名称或别名")
    parser.add_argument("--size", "-s", default="1024x1024", help="图像尺寸")
    parser.add_argument("--duration", "-d", type=int, default=5, help="视频时长(秒)")
    parser.add_argument("--save", action="store_true", help="保存到本地")
    
    args = parser.parse_args()
    
    if args.type == "image":
        model = args.model or "flux-pro-max"
        result = generate_image(args.prompt, model, args.size)
    else:
        model = args.model or "veo3.1-pro"
        result = generate_video(args.prompt, model, args.duration)
    
    print(json.dumps(result, indent=2, ensure_ascii=False))
    
    if result["success"] and args.save:
        if args.type == "image":
            for img in result.get("images", []):
                url = img.get("url")
                if url:
                    path = save_media(url)
                    print(f"已保存: {path}")
        else:
            url = result.get("video", {}).get("url")
            if url:
                path = save_media(url)
                print(f"已保存: {path}")
