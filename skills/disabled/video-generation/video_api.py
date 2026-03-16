#!/usr/bin/env python3
"""
视频生成 API 脚本 - 支持 Veo3.1, Sora, Kling 等
使用 xingjiabiapi 的视频统一格式接口

正确的 API 端点（来自官方文档）：
- 创建视频: POST /v1/video/create
- 查询状态: GET /v1/video/query?id={task_id}

请求参数:
{
    "model": "veo3.1",
    "prompt": "视频描述",
    "aspect_ratio": "16:9",  // 可选，仅 veo3 支持
    "enhance_prompt": true,   // 可选，中文自动转英文
    "enable_upsample": true,  // 可选
    "images": ["url1", "url2"] // 可选，参考图
}
"""

import os
import sys
import json
import time
import requests
import subprocess
from pathlib import Path
from typing import Optional, Dict, Any, List

# API 配置
API_BASE = "https://xingjiabiapi.com/v1"
API_KEY = None

# 可用模型（来自官方文档）
AVAILABLE_MODELS = {
    # Veo2 系列
    "veo2": {"name": "Veo2", "desc": "Google veo2 fast 模式，质量好速度快"},
    "veo2-fast": {"name": "Veo2 Fast", "desc": "Google veo2 fast 模式"},
    "veo2-fast-frames": {"name": "Veo2 Fast Frames", "desc": "支持首尾帧"},
    "veo2-fast-components": {"name": "Veo2 Fast Components", "desc": "支持图片素材"},
    "veo2-pro": {"name": "Veo2 Pro", "desc": "高质量模式，价格较贵"},
    "veo2-pro-components": {"name": "Veo2 Pro Components", "desc": "Pro + 图片素材"},
    
    # Veo3 系列
    "veo3": {"name": "Veo3", "desc": "Veo3 标准"},
    "veo3-fast": {"name": "Veo3 Fast", "desc": "Veo3 快速模式"},
    "veo3-fast-frames": {"name": "Veo3 Fast Frames", "desc": "支持首尾帧"},
    "veo3-frames": {"name": "Veo3 Frames", "desc": "支持帧"},
    "veo3-pro": {"name": "Veo3 Pro", "desc": "Veo3 专业版"},
    "veo3-pro-frames": {"name": "Veo3 Pro Frames", "desc": "Pro + 首帧"},
    
    # Veo3.1 系列
    "veo3.1": {"name": "Veo3.1", "desc": "最新版本"},
    "veo3.1-fast": {"name": "Veo3.1 Fast", "desc": "快速模式"},
    "veo3.1-pro": {"name": "Veo3.1 Pro", "desc": "专业版"},
}

def get_api_key() -> str:
    """获取 API Key"""
    global API_KEY
    if API_KEY:
        return API_KEY
    
    try:
        result = subprocess.run(
            ["pass", "show", "api/xingjiabiapi"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            API_KEY = result.stdout.strip()
            return API_KEY
    except:
        pass
    
    API_KEY = os.environ.get("XINGJIABIAPI_KEY")
    if not API_KEY:
        raise ValueError(
            "API Key 未设置！请使用以下方式之一：\n"
            "1. pass: pass show api/xingjiabiapi\n"
            "2. 环境变量: export XINGJIABIAPI_KEY=sk-xxx"
        )
    return API_KEY

def create_video(
    prompt: str,
    model: str = "veo3.1",
    aspect_ratio: str = "16:9",
    enhance_prompt: bool = True,
    enable_upsample: bool = False,
    images: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    创建视频任务
    
    Args:
        prompt: 视频描述（veo 只支持英文，开启 enhance_prompt 可自动翻译）
        model: 模型名称
        aspect_ratio: 宽高比 (16:9 或 9:16)，仅 veo3 支持
        enhance_prompt: 是否自动将中文转英文
        enable_upsample: 是否启用上采样
        images: 参考图片 URL 列表
    
    Returns:
        dict: 包含 id, status 等信息
    """
    api_key = get_api_key()
    
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Authorization": f"Bearer {api_key}"
    }
    
    payload = {
        "model": model,
        "prompt": prompt,
        "enhance_prompt": enhance_prompt,
        "enable_upsample": enable_upsample
    }
    
    # 仅 veo3 支持 aspect_ratio
    if "veo3" in model:
        payload["aspect_ratio"] = aspect_ratio
    
    if images:
        payload["images"] = images
    
    print(f"🎬 创建视频任务...")
    print(f"   模型: {model}")
    print(f"   描述: {prompt[:80]}{'...' if len(prompt) > 80 else ''}")
    
    try:
        response = requests.post(
            f"{API_BASE}/video/create",
            headers=headers,
            json=payload,
            timeout=60
        )
        result = response.json()
        
        if "error" in result:
            print(f"❌ 错误: {result['error']}")
            return {"status": "error", "error": result["error"]}
        
        task_id = result.get("id")
        status = result.get("status")
        
        print(f"✅ 任务已创建!")
        print(f"📋 任务ID: {task_id}")
        print(f"📊 状态: {status}")
        
        return {
            "status": "submitted",
            "task_id": task_id,
            "initial_status": status,
            "response": result
        }
        
    except Exception as e:
        print(f"❌ 请求失败: {e}")
        return {"status": "error", "message": str(e)}

def query_video(task_id: str) -> Dict[str, Any]:
    """
    查询视频任务状态
    
    Args:
        task_id: 任务ID
    
    Returns:
        dict: 任务状态和结果
    """
    api_key = get_api_key()
    
    headers = {
        "Accept": "application/json",
        "Authorization": f"Bearer {api_key}"
    }
    
    try:
        response = requests.get(
            f"{API_BASE}/video/query",
            params={"id": task_id},
            headers=headers,
            timeout=30
        )
        return response.json()
    except Exception as e:
        return {"status": "error", "message": str(e)}

def generate_video(
    prompt: str,
    model: str = "veo3.1",
    aspect_ratio: str = "16:9",
    enhance_prompt: bool = True,
    output_dir: Optional[str] = None,
    wait: bool = True,
    max_wait: int = 600
) -> Dict[str, Any]:
    """
    生成视频（创建 + 等待完成）
    """
    # 创建任务
    result = create_video(
        prompt=prompt,
        model=model,
        aspect_ratio=aspect_ratio,
        enhance_prompt=enhance_prompt
    )
    
    if result.get("status") == "error":
        return result
    
    task_id = result.get("task_id")
    if not task_id:
        return {"status": "error", "message": "No task_id returned"}
    
    if not wait:
        return result
    
    # 轮询等待
    return poll_task(task_id, output_dir, max_wait)

def poll_task(
    task_id: str,
    output_dir: Optional[str] = None,
    max_wait: int = 600
) -> Dict[str, Any]:
    """轮询任务状态直到完成"""
    start_time = time.time()
    poll_interval = 10
    
    print(f"⏳ 等待视频生成...")
    
    while time.time() - start_time < max_wait:
        result = query_video(task_id)
        
        status = result.get("status")
        detail = result.get("detail", {})
        
        if status in ["completed", "succeed", "success"]:
            video_url = detail.get("video_url") or result.get("video_url")
            print(f"\n✅ 视频生成完成!")
            
            if video_url:
                print(f"🔗 URL: {video_url}")
                
                local_path = None
                if output_dir:
                    local_path = download_video(video_url, output_dir)
                
                return {
                    "status": "completed",
                    "task_id": task_id,
                    "video_url": video_url,
                    "local_path": local_path,
                    "detail": detail
                }
            else:
                return {
                    "status": "completed",
                    "task_id": task_id,
                    "detail": detail,
                    "response": result
                }
        
        elif status in ["failed", "error"]:
            error_msg = detail.get("error") or result.get("error", "Unknown error")
            print(f"\n❌ 生成失败: {error_msg}")
            return {"status": "failed", "task_id": task_id, "error": error_msg}
        
        else:
            elapsed = int(time.time() - start_time)
            print(f"\r⏳ 生成中... ({elapsed}s) 状态: {status}    ", end="", flush=True)
            time.sleep(poll_interval)
    
    return {"status": "timeout", "task_id": task_id, "message": f"Timeout after {max_wait}s"}

def download_video(url: str, output_dir: str) -> Optional[str]:
    """下载视频到本地"""
    try:
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        filename = f"video_{int(time.time())}.mp4"
        filepath = output_path / filename
        
        print(f"📥 下载视频...")
        response = requests.get(url, stream=True, timeout=120)
        response.raise_for_status()
        
        with open(filepath, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        
        print(f"✅ 下载完成: {filepath}")
        return str(filepath)
    except Exception as e:
        print(f"⚠️ 下载失败: {e}")
        return None

def list_models():
    """列出可用模型"""
    print("🎬 可用视频生成模型 (Veo 系列):")
    print("-" * 70)
    print(f"{'模型ID':<25} | {'名称':<20} | {'说明'}")
    print("-" * 70)
    for model_id, info in AVAILABLE_MODELS.items():
        print(f"{model_id:<25} | {info['name']:<20} | {info['desc']}")
    print("-" * 70)
    print("\n📝 API 端点:")
    print("   创建: POST /v1/video/create")
    print("   查询: GET /v1/video/query?id={task_id}")
    return AVAILABLE_MODELS

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="视频生成 API (xingjiabiapi)")
    subparsers = parser.add_subparsers(dest="command", help="命令")
    
    # generate 命令
    gen_parser = subparsers.add_parser("generate", help="生成视频")
    gen_parser.add_argument("prompt", help="视频描述")
    gen_parser.add_argument("-m", "--model", default="veo3.1", help="模型名称")
    gen_parser.add_argument("-r", "--ratio", default="16:9", help="宽高比")
    gen_parser.add_argument("-o", "--output", default="/tmp/videos", help="输出目录")
    gen_parser.add_argument("--no-wait", action="store_true", help="不等待完成")
    gen_parser.add_argument("--no-enhance", action="store_true", help="不自动翻译提示词")
    
    # create 命令
    create_parser = subparsers.add_parser("create", help="仅创建任务")
    create_parser.add_argument("prompt", help="视频描述")
    create_parser.add_argument("-m", "--model", default="veo3.1", help="模型名称")
    create_parser.add_argument("-r", "--ratio", default="16:9", help="宽高比")
    
    # query 命令
    query_parser = subparsers.add_parser("query", help="查询任务状态")
    query_parser.add_argument("task_id", help="任务ID")
    
    # poll 命令
    poll_parser = subparsers.add_parser("poll", help="轮询等待完成")
    poll_parser.add_argument("task_id", help="任务ID")
    poll_parser.add_argument("-o", "--output", default="/tmp/videos", help="输出目录")
    
    # models 命令
    subparsers.add_parser("models", help="列出可用模型")
    
    args = parser.parse_args()
    
    if args.command == "generate":
        result = generate_video(
            prompt=args.prompt,
            model=args.model,
            aspect_ratio=args.ratio,
            enhance_prompt=not args.no_enhance,
            output_dir=args.output,
            wait=not args.no_wait
        )
        print("\n" + "=" * 50)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        
    elif args.command == "create":
        result = create_video(
            prompt=args.prompt,
            model=args.model,
            aspect_ratio=args.ratio
        )
        print(json.dumps(result, indent=2, ensure_ascii=False))
        
    elif args.command == "query":
        result = query_video(args.task_id)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        
    elif args.command == "poll":
        result = poll_task(args.task_id, args.output)
        print("\n" + "=" * 50)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        
    elif args.command == "models":
        list_models()
        
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
