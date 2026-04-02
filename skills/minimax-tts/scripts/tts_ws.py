#!/usr/bin/env python3
"""MiniMax TTS via WebSocket - speech-2.8-hd"""
import asyncio
import json
import ssl
import sys
import os

# Voice ID mapping per Daniel's request
VOICES = {
    "female-yujie": "御姐",
    "qiaopi_mengmei": "俏皮萌妹",
    "female-shaonv-jingpin": "少女音色-beta",
    "Cantonese_CuteGirl": "可爱女孩(粤语)",
}

async def synthesize(model, voice_id, text, api_key, output_path):
    url = "wss://api.minimaxi.com/ws/v1/t2a_v2"
    headers = {"Authorization": f"Bearer {api_key}"}
    
    ssl_ctx = ssl.create_default_context()
    ssl_ctx.check_hostname = False
    ssl_ctx.verify_mode = ssl.CERT_NONE
    
    try:
        import websockets
    except ImportError:
        print("Installing websockets...")
        os.system("pip3 install websockets -q")
        import websockets
    
    print(f"  Connecting to {url}...")
    async with websockets.connect(url, additional_headers=headers, ssl=ssl_ctx) as ws:
        # Wait for connected_success
        resp = json.loads(await ws.recv())
        if resp.get("event") != "connected_success":
            print(f"  ❌ Connection failed: {resp}")
            return False
        print(f"  ✅ Connected")
        
        # Send task_start
        start_msg = {
            "event": "task_start",
            "model": model,
            "voice_setting": {
                "voice_id": voice_id,
                "speed": 1,
                "vol": 1,
                "pitch": 0,
                "english_normalization": False
            },
            "audio_setting": {
                "sample_rate": 32000,
                "bitrate": 128000,
                "format": "mp3",
                "channel": 1
            }
        }
        await ws.send(json.dumps(start_msg))
        resp = json.loads(await ws.recv())
        if resp.get("event") != "task_started":
            print(f"  ❌ Task start failed: {resp}")
            return False
        print(f"  ✅ Task started")
        
        # Send text
        await ws.send(json.dumps({"event": "task_continue", "text": text}))
        
        # Collect audio
        audio_data = b""
        chunk_count = 0
        
        while True:
            resp = json.loads(await ws.recv())
            if "data" in resp and "audio" in resp["data"]:
                audio_hex = resp["data"]["audio"]
                if audio_hex:
                    audio_data += bytes.fromhex(audio_hex)
                    chunk_count += 1
            
            if resp.get("is_final"):
                break
        
        if audio_data:
            with open(output_path, "wb") as f:
                f.write(audio_data)
            print(f"  ✅ Saved {len(audio_data)} bytes ({chunk_count} chunks) → {output_path}")
            return True
        else:
            print(f"  ❌ No audio data received")
            return False

async def main():
    api_key = os.environ.get("MINIMAX_API_KEY", "")
    if not api_key:
        # Try reading from config
        try:
            with open("/home/aa/.openclaw/openclaw.json") as f:
                cfg = json.load(f)
            api_key = cfg.get("env", {}).get("vars", {}).get("MINIMAX_API_KEY", "")
        except:
            pass
    
    if not api_key:
        print("❌ No API key found")
        return
    
    model = "speech-2.8-hd"
    text = "你好Daniel，我是小a，MiniMax语音合成测试成功！"
    
    results = {}
    for voice_id, voice_name in VOICES.items():
        output_path = f"/tmp/tts_{voice_id}.mp3"
        print(f"\n🔊 {voice_name} ({voice_id}):")
        try:
            ok = await synthesize(model, voice_id, text, api_key, output_path)
            results[voice_id] = (voice_name, ok, output_path)
        except Exception as e:
            print(f"  ❌ Error: {e}")
            results[voice_id] = (voice_name, False, None)
    
    print(f"\n{'='*50}")
    print("Results:")
    for vid, (name, ok, path) in results.items():
        status = "✅" if ok else "❌"
        print(f"  {status} {name} ({vid}): {path if ok else 'failed'}")

if __name__ == "__main__":
    asyncio.run(main())
