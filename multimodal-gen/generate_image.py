#!/usr/bin/env python3
"""
图像生成工具 - 调用性价比 API 的多模态模型
"""

import sys
import json
import base64
import subprocess
import re
from datetime import datetime
from pathlib import Path
import requests

# 配置
API_BASE = "https://xingjiabiapi.com/v1"
DEFAULT_MODEL = "gemini-3-pro-image-preview"
OUTPUT_DIR = Path.home() / "clawd" / "output" / "images"

# 可用模型
MODELS = {
    "gemini": "gemini-3-pro-image-preview",
    "flux": "flux-pro-max",
    "flux-ultra": "flux-pro-1.1-ultra",
    "imagen": "google/imagen-4-ultra",
    "dalle": "gpt-image-1",
    "kling": "kling-image",
    "seedream": "doubao-seedream-4-5-251128",
}

def get_api_key():
    """从 pass 获取 API key"""
    result = subprocess.run(["pass", "api/xingjiabiapi"], capture_output=True, text=True)
    return result.stdout.strip()

def generate_image(prompt: str, model: str = None, output_path: str = None) -> dict:
    """生成图片"""
    api_key = get_api_key()
    model = model or DEFAULT_MODEL
    
    # 支持别名
    if model in MODELS:
        model = MODELS[model]
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    data = {
        "model": model,
        "messages": [{"role": "user", "content": f"Generate an image: {prompt}"}]
    }
    
    try:
        response = requests.post(f"{API_BASE}/chat/completions", headers=headers, json=data, timeout=120)
        result = response.json()
    except Exception as e:
        return {"error": str(e)}
    
    if "error" in result:
        return {"error": result["error"]}
    
    # 提取图片
    content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
    
    # 查找 base64 图片
    if "data:image" in content:
        match = re.search(r'data:image/(\w+);base64,([A-Za-z0-9+/=]+)', content)
        if match:
            img_format = match.group(1)
            img_data = match.group(2)
            
            # 保存图片
            OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            if output_path:
                filepath = Path(output_path)
            else:
                filepath = OUTPUT_DIR / f"gen_{timestamp}.{img_format}"
            
            with open(filepath, "wb") as f:
                f.write(base64.b64decode(img_data))
            
            return {
                "success": True,
                "path": str(filepath),
                "format": img_format,
                "model": model,
                "prompt": prompt
            }
    
    # 检查是否有 inline_data (Gemini 格式)
    if isinstance(content, list):
        for part in content:
            if isinstance(part, dict) and "inline_data" in part:
                img_data = part["inline_data"].get("data", "")
                mime_type = part["inline_data"].get("mime_type", "image/jpeg")
                img_format = mime_type.split("/")[-1]
                
                OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filepath = OUTPUT_DIR / f"gen_{timestamp}.{img_format}"
                
                with open(filepath, "wb") as f:
                    f.write(base64.b64decode(img_data))
                
                return {
                    "success": True,
                    "path": str(filepath),
                    "format": img_format,
                    "model": model,
                    "prompt": prompt
                }
    
    # 检查是否有 URL 链接 (Flux 等模型返回 URL)
    url_match = re.search(r'https://[^\s\)]+\.(png|jpg|jpeg|webp)', content)
    if url_match:
        img_url = url_match.group(0)
        img_format = url_match.group(1)
        
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        if output_path:
            filepath = Path(output_path)
        else:
            filepath = OUTPUT_DIR / f"gen_{timestamp}.{img_format}"
        
        # 下载图片
        img_response = requests.get(img_url, timeout=60)
        with open(filepath, "wb") as f:
            f.write(img_response.content)
        
        return {
            "success": True,
            "path": str(filepath),
            "format": img_format,
            "model": model,
            "prompt": prompt,
            "url": img_url
        }
    
    # 检查 s3.ffire.cc 链接
    ffire_match = re.search(r'https://s3\.ffire\.cc/[^\s\)\]]+', content)
    if ffire_match:
        img_url = ffire_match.group(0)
        
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        if output_path:
            filepath = Path(output_path)
        else:
            filepath = OUTPUT_DIR / f"gen_{timestamp}.png"
        
        # 下载图片
        img_response = requests.get(img_url, timeout=60)
        with open(filepath, "wb") as f:
            f.write(img_response.content)
        
        return {
            "success": True,
            "path": str(filepath),
            "format": "png",
            "model": model,
            "prompt": prompt,
            "url": img_url
        }
    
    return {"error": "No image found in response", "raw": str(content)[:500]}

def main():
    if len(sys.argv) < 2:
        print("Usage: generate_image.py <prompt> [model] [output_path]")
        print(f"Available models: {', '.join(MODELS.keys())}")
        sys.exit(1)
    
    prompt = sys.argv[1]
    model = sys.argv[2] if len(sys.argv) > 2 and not sys.argv[2].startswith("/") else None
    output_path = sys.argv[-1] if len(sys.argv) > 2 and sys.argv[-1].startswith("/") else None
    
    result = generate_image(prompt, model, output_path)
    print(json.dumps(result, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
