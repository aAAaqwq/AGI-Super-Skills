#!/usr/bin/env python3
"""
视频生成工具 - 调用性价比 API 的视频生成模型（异步）
"""

import sys
import json
import subprocess
import time
from datetime import datetime
from pathlib import Path
import requests

API_BASE = "https://xingjiabiapi.com/v1"
DEFAULT_MODEL = "veo3.1"
OUTPUT_DIR = Path.home() / "clawd" / "output" / "videos"

# 可用模型
MODELS = {
    "veo3.1": "veo3.1",
    "veo3.1-4k": "veo3.1-4k",
    "veo3.1-pro": "veo3.1-pro",
    "veo3.1-pro-4k": "veo3.1-pro-4k",
    "veo3": "veo3",
    "sora2": "sora-2-all",
    "sora": "sora-2-all",
    "kling": "kling-video",
    "hailuo": "MiniMax-Hailuo-2.3",
    "runway": "runwayml-gen4_turbo-10",
    "grok": "grok-video-3",
}

def get_api_key():
    result = subprocess.run(["pass", "api/xingjiabiapi"], capture_output=True, text=True)
    return result.stdout.strip()

def submit_video_task(prompt: str, model: str = None) -> dict:
    """提交视频生成任务（异步）"""
    api_key = get_api_key()
    model_id = model or DEFAULT_MODEL
    
    if model_id in MODELS:
        model_id = MODELS[model_id]
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    data = {
        "model": model_id,
        "prompt": prompt
    }
    
    try:
        response = requests.post(f"{API_BASE}/video/generations", headers=headers, json=data, timeout=60)
        result = response.json()
        
        if result.get("code") == 500:
            return {"error": result.get("message", "服务器繁忙"), "status": "error"}
        
        task_id = result.get("data", {}).get("task_id") or result.get("task_id")
        if task_id:
            return {
                "status": "submitted",
                "task_id": task_id,
                "model": model_id,
                "prompt": prompt,
                "message": "视频生成任务已提交，请稍后查询结果"
            }
        
        return {"error": "未获取到任务ID", "raw": result}
    except Exception as e:
        return {"error": str(e)}

def query_video_task(task_id: str) -> dict:
    """查询视频生成任务状态"""
    api_key = get_api_key()
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    try:
        response = requests.get(f"{API_BASE}/video/generations/{task_id}", headers=headers, timeout=30)
        result = response.json()
        
        status = result.get("data", {}).get("task_status") or result.get("task_status")
        
        if status == "completed" or status == "succeed":
            video_url = result.get("data", {}).get("video_url") or result.get("video_url")
            if video_url:
                # 下载视频
                OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filepath = OUTPUT_DIR / f"gen_{timestamp}.mp4"
                
                video_response = requests.get(video_url, timeout=120)
                with open(filepath, "wb") as f:
                    f.write(video_response.content)
                
                return {
                    "status": "completed",
                    "task_id": task_id,
                    "path": str(filepath),
                    "url": video_url
                }
        
        return {
            "status": status or "unknown",
            "task_id": task_id,
            "raw": result
        }
    except Exception as e:
        return {"error": str(e), "task_id": task_id}

def generate_video(prompt: str, model: str = None, wait: bool = False, max_wait: int = 300) -> dict:
    """生成视频（可选等待完成）"""
    # 提交任务
    submit_result = submit_video_task(prompt, model)
    
    if submit_result.get("error"):
        return submit_result
    
    task_id = submit_result.get("task_id")
    if not task_id:
        return submit_result
    
    if not wait:
        return submit_result
    
    # 等待完成
    start_time = time.time()
    while time.time() - start_time < max_wait:
        time.sleep(10)  # 每10秒查询一次
        query_result = query_video_task(task_id)
        
        status = query_result.get("status")
        if status == "completed":
            return query_result
        elif status in ["failed", "error"]:
            return query_result
        
        print(f"状态: {status}, 已等待 {int(time.time() - start_time)}s...", file=sys.stderr)
    
    return {"status": "timeout", "task_id": task_id, "message": f"等待超时 ({max_wait}s)"}

def main():
    if len(sys.argv) < 2:
        print("Usage:")
        print("  generate_video.py submit <prompt> [model]  - 提交任务")
        print("  generate_video.py query <task_id>          - 查询任务")
        print("  generate_video.py <prompt> [model]         - 提交并等待")
        print(f"\nAvailable models: {', '.join(MODELS.keys())}")
        sys.exit(1)
    
    action = sys.argv[1]
    
    if action == "submit":
        prompt = sys.argv[2]
        model = sys.argv[3] if len(sys.argv) > 3 else None
        result = submit_video_task(prompt, model)
    elif action == "query":
        task_id = sys.argv[2]
        result = query_video_task(task_id)
    else:
        # 默认：提交并等待
        prompt = sys.argv[1]
        model = sys.argv[2] if len(sys.argv) > 2 else None
        result = generate_video(prompt, model, wait=True)
    
    print(json.dumps(result, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
