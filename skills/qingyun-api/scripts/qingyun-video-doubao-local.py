#!/usr/bin/env python3
"""
doubao-seedance 视频生成 — 支持本地文件作为首帧/尾帧
自动将本地图片转为 base64 data URI
"""
import json
import sys
import os
import base64
import subprocess
import time
import argparse

BASE_URL = "https://api.qingyuntop.top"
API_KEY = os.environ.get("QINGYUN_API_KEY", "")

if not API_KEY:
    # 尝试从 pass 获取
    try:
        API_KEY = subprocess.check_output(["pass", "show", "api/qingyun"], 
                                          stderr=subprocess.DEVNULL).decode().strip().split('\n')[0]
    except:
        pass

def image_to_data_uri(path):
    """将本地图片文件转为 data URI"""
    ext = os.path.splitext(path)[1].lower()
    mime_map = {'.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.webp': 'image/webp'}
    mime = mime_map.get(ext, 'image/png')
    with open(path, 'rb') as f:
        b64 = base64.b64encode(f.read()).decode()
    return f"data:{mime};base64,{b64}"

def api_request(method, path, payload=None):
    """调用青云API"""
    import urllib.request
    import urllib.error
    
    url = f"{BASE_URL}{path}"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {API_KEY}"
    }
    
    data = json.dumps(payload).encode() if payload else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        print(f"ERROR: HTTP {e.code}", file=sys.stderr)
        print(body[:500], file=sys.stderr)
        sys.exit(1)

def poll_task(task_id, interval=10, max_wait=1800):
    """轮询任务状态"""
    elapsed = 0
    while elapsed < max_wait:
        result = api_request("GET", f"/volc/v1/contents/generations/tasks/{task_id}")
        status = result.get("status", "")
        print(f"Status: {status} (elapsed: {elapsed}s)", file=sys.stderr)
        
        if status in ("succeeded", "complete", "done"):
            return result
        elif status in ("failed", "error"):
            print(f"Task failed: {json.dumps(result, ensure_ascii=False)[:500]}", file=sys.stderr)
            sys.exit(1)
        
        time.sleep(interval)
        elapsed += interval
    
    print("Timeout!", file=sys.stderr)
    sys.exit(1)

def extract_video_url(result):
    """从结果中提取视频URL"""
    # 尝试多种路径
    paths = [
        ("data", "content", 0, "url"),
        ("data", "video_url",),
        ("data", "url",),
        ("output", "video_url",),
        ("result", "video_url",),
        ("result", "url",),
    ]
    obj = result
    for path in paths:
        try:
            v = result
            for key in path:
                v = v[key]
            if v and isinstance(v, str) and v.startswith("http"):
                return v
        except (KeyError, IndexError, TypeError):
            continue
    
    # 深度搜索
    def find_url(d):
        if isinstance(d, str) and d.startswith("http") and (".mp4" in d or "video" in d):
            return d
        if isinstance(d, dict):
            for v in d.values():
                r = find_url(v)
                if r: return r
        if isinstance(d, list):
            for v in d:
                r = find_url(v)
                if r: return r
        return None
    
    return find_url(result)

def main():
    parser = argparse.ArgumentParser(description='Doubao Seedance video gen with local file support')
    parser.add_argument('prompt', help='Video generation prompt')
    parser.add_argument('--model', default='doubao-seedance-1-5-pro-251215')
    parser.add_argument('--first-frame', help='First frame image (URL or local file)')
    parser.add_argument('--last-frame', help='Last frame image (URL or local file)')
    parser.add_argument('-o', '--output', help='Output mp4 path')
    args = parser.parse_args()
    
    if not API_KEY:
        print("ERROR: QINGYUN_API_KEY not set", file=sys.stderr)
        sys.exit(1)
    
    output = args.output or f"doubao-video-{time.strftime('%Y%m%d-%H%M%S')}.mp4"
    
    # 构建content数组
    content = [{"type": "text", "text": args.prompt}]
    
    if args.first_frame:
        if os.path.isfile(args.first_frame):
            url = image_to_data_uri(args.first_frame)
            print(f"📷 First frame: local file → base64 ({os.path.getsize(args.first_frame)//1024}KB)", file=sys.stderr)
        else:
            url = args.first_frame
        content.append({"type": "image_url", "role": "first_frame", "image_url": {"url": url}})
    
    if args.last_frame:
        if os.path.isfile(args.last_frame):
            url = image_to_data_uri(args.last_frame)
            print(f"📷 Last frame: local file → base64 ({os.path.getsize(args.last_frame)//1024}KB)", file=sys.stderr)
        else:
            url = args.last_frame
        content.append({"type": "image_url", "role": "last_frame", "image_url": {"url": url}})
    
    payload = {"model": args.model, "content": content}
    
    print(f"Creating task... (model: {args.model})", file=sys.stderr)
    resp = api_request("POST", "/volc/v1/contents/generations/tasks", payload)
    
    task_id = resp.get("task_id") or resp.get("id") or resp.get("data", {}).get("task_id")
    if not task_id:
        print(f"No task_id in response: {json.dumps(resp, ensure_ascii=False)[:500]}", file=sys.stderr)
        sys.exit(1)
    
    print(f"Task ID: {task_id}", file=sys.stderr)
    result = poll_task(task_id)
    
    video_url = extract_video_url(result)
    if not video_url:
        print(f"No video URL in result: {json.dumps(result, ensure_ascii=False)[:500]}", file=sys.stderr)
        sys.exit(1)
    
    print(f"Downloading: {video_url[:100]}...", file=sys.stderr)
    os.makedirs(os.path.dirname(output) or ".", exist_ok=True)
    subprocess.run(["curl", "-sL", "-o", output, video_url], check=True)
    
    size = os.path.getsize(output)
    print(f"✅ Saved: {output} ({size//1024}KB)")

if __name__ == "__main__":
    main()
