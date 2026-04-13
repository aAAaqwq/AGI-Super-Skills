#!/usr/bin/env python3
"""用 Gemini 转录音频歌词（走青云 chat 兼容格式，支持 inline_data）"""
import json, sys, os, base64, urllib.request, urllib.error

API_KEY = os.environ.get("QINGYUN_API_KEY", "")
if not API_KEY:
    import subprocess
    API_KEY = subprocess.check_output(["pass","show","api/qingyun"],stderr=subprocess.DEVNULL).decode().strip().split('\n')[0]

audio_path = sys.argv[1] if len(sys.argv) > 1 else sys.exit("Usage: transcribe_gemini.py <audio.mp3>")

with open(audio_path, 'rb') as f:
    b64 = base64.b64encode(f.read()).decode()

ext = os.path.splitext(audio_path)[1].lower()
mime = {'.mp3':'audio/mpeg','.wav':'audio/wav','.m4a':'audio/mp4'}.get(ext,'audio/mpeg')

# Gemini 原生格式
payload = {
    "contents": [{
        "parts": [
            {"text": "请精确转录这首歌的歌词，按时间标注每一行。格式：[MM:SS] 歌词原文 (中文翻译)。如果无法确定精确时间，按段落标注。请仔细听每一句歌词。"},
            {"inline_data": {"mime_type": mime, "data": b64}}
        ]
    }],
    "generationConfig": {"responseModalities": ["TEXT"]}
}

req = urllib.request.Request(
    f"https://api.qingyuntop.top/v1beta/models/gemini-2.5-flash-preview-05-20:generateContent?key={API_KEY}",
    data=json.dumps(payload).encode(),
    headers={"Content-Type": "application/json"},
    method="POST"
)

print("Transcribing with Gemini... (30-90s)", file=sys.stderr)
try:
    with urllib.request.urlopen(req, timeout=180) as resp:
        result = json.loads(resp.read().decode())
    
    # 提取文本
    parts = result.get("candidates",[{}])[0].get("content",{}).get("parts",[])
    text = "\n".join([p.get("text","") for p in parts if "text" in p])
    print(text)
    
    out = os.path.splitext(audio_path)[0] + "_lyrics.txt"
    with open(out, 'w') as f:
        f.write(text)
    print(f"\nSaved: {out}", file=sys.stderr)
except urllib.error.HTTPError as e:
    print(f"HTTP {e.code}: {e.read().decode()[:500]}", file=sys.stderr)
    sys.exit(1)
