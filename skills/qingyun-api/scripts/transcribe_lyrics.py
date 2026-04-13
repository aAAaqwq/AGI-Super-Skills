#!/usr/bin/env python3
"""用 gpt-4o-audio 转录音频歌词"""
import json, sys, os, base64, urllib.request, urllib.error

API_KEY = os.environ.get("QINGYUN_API_KEY", "")
if not API_KEY:
    import subprocess
    API_KEY = subprocess.check_output(["pass","show","api/qingyun"],stderr=subprocess.DEVNULL).decode().strip().split('\n')[0]

audio_path = sys.argv[1] if len(sys.argv) > 1 else sys.exit("Usage: transcribe.py <audio.mp3>")

with open(audio_path, 'rb') as f:
    b64 = base64.b64encode(f.read()).decode()

ext = os.path.splitext(audio_path)[1].lower()
mime = {'.mp3':'audio/mpeg','.wav':'audio/wav','.m4a':'audio/mp4'}.get(ext,'audio/mpeg')

payload = {
    "model": "gpt-4o-audio-preview",
    "messages": [{
        "role": "user",
        "content": [
            {"type": "text", "text": "Please transcribe this song lyrics with timestamps. Format each line as: [MM:SS] lyrics text. If the song is in Japanese, also provide Chinese translation in parentheses. Be precise with timing."},
            {"type": "input_audio", "input_audio": {"data": b64, "format": "mp3" if ext=='.mp3' else "wav"}}
        ]
    }]
}

req = urllib.request.Request(
    "https://api.qingyuntop.top/v1/chat/completions",
    data=json.dumps(payload).encode(),
    headers={"Content-Type":"application/json", "Authorization": f"Bearer {API_KEY}"},
    method="POST"
)

print("Transcribing... (this may take 30-60s)", file=sys.stderr)
with urllib.request.urlopen(req, timeout=120) as resp:
    result = json.loads(resp.read().decode())

text = result.get("choices",[{}])[0].get("message",{}).get("content","")
print(text)

# Save
out = os.path.splitext(audio_path)[0] + "_lyrics.txt"
with open(out, 'w') as f:
    f.write(text)
print(f"\nSaved to: {out}", file=sys.stderr)
