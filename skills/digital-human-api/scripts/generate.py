#!/usr/bin/env python3
"""
digital-human-api v3 — 全流程数字人口播视频生成
新流程: Scene Image → TTS → Kling Video → Lip Sync → Merge

v3改进:
- 每shot生成专属场景图（Daniel脸 + 个性化场景）
- Grok参考脸生成保持一致性
- Kling使用场景图而非固定avatar
"""

import argparse
import base64
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
import urllib.error
import yaml
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from PIL import Image

# ─── 配置 ───────────────────────────────────────────────────────

SCRIPT_DIR = Path(__file__).parent
CONFIG_PATH = SCRIPT_DIR / "config.yaml"


def load_config():
    with open(CONFIG_PATH) as f:
        return yaml.safe_load(f)


def get_api_key():
    key = os.environ.get("QINGYUN_API_KEY", "")
    if not key:
        result = subprocess.run(["pass", "show", "api/qingyun"], capture_output=True, text=True)
        key = result.stdout.strip()
    if not key:
        print("ERROR: QINGYUN_API_KEY not set")
        sys.exit(1)
    return key


# ─── Prompt 工程 ────────────────────────────────────────────────

DEFAULT_NEGATIVE_PROMPT = (
    "animation, cartoon, illustration, painting, 3d render, unrealistic, "
    "distorted face, deformed, blurry, low quality, oversaturated, "
    "artistic filter, dramatic cinematic lighting, stiff pose, robotic, "
    "claymation, anime, comic book style"
)

BASE_ACTIONS = {
    "serious": "serious expression, direct eye contact, calm composed demeanor",
    "friendly": "friendly warm smile, relaxed posture, approachable natural look",
    "excited": "animated excited expression, energetic hand gestures, engaged",
    "sarcastic": "slight eye roll, wry half-smile, raised eyebrow, skeptical look",
    "storytelling": "relaxed open posture, hand movements while speaking, engaged storyteller",
    "explaining": "focused concentration, clear expression, hand gestures to emphasize",
    "questioning": "curious expression, slight head tilt, pondering wondering look",
    "confident": "confident stance, arms relaxed, direct calm eye contact, authoritative",
    "humorous": "playful smile, light easygoing expression, relaxed shoulders, fun vibe",
    "intense": "focused intense stare, serious determined mood, leaning forward slightly",
    "casual": "very relaxed casual pose, natural movement, conversational comfortable mood",
}

EMOTION_MAP = {
    "neutral": "casual", "serious": "serious", "dramatic": "intense",
    "funny": "humorous", "exciting": "excited", "sad": "serious",
    "curious": "questioning", "default": "friendly",
}


def build_video_prompt(shot, config):
    """构建Kling视频生成的正向+负向提示词"""
    custom_prompt = shot.get("action_prompt", "")
    emotion = shot.get("emotion", "default")
    negative = shot.get("negative_prompt", config.get("negative_prompt", ""))

    if custom_prompt:
        positive = custom_prompt
    else:
        emotion_key = EMOTION_MAP.get(emotion, "friendly")
        base_action = BASE_ACTIONS.get(emotion_key, BASE_ACTIONS["friendly"])
        text = shot.get("text", "")

        # 根据文案内容添加微动作
        micro = []
        if any(w in text for w in ["？", "?", "怎么", "为什么", "是不是"]):
            micro.append("slight confused head tilt")
        if any(w in text for w in ["！", "!", "太", "真", "厉害", "精彩"]):
            micro.append("genuinely surprised expression, eyes widening")
        if any(w in text for w in ["但是", "可是", "不过", "其实"]):
            micro.append("brief pause, thoughtful expression")
        if any(w in text for w in ["笑", "哈哈", "搞笑"]):
            micro.append("natural relaxed laughter")
        if any(w in text for w in ["告", "告状", "状", "索赔"]):
            micro.append("serious formal expression")
        if any(w in text for w in ["兄弟", "合伙", "饭馆"]):
            micro.append("casual relatable everyday expression")

        positive = f"hyper-realistic video footage of a young Asian man, {base_action}"
        if micro:
            positive += ", " + ", ".join(micro)
        positive += ", cinematic natural lighting, high quality realistic video, not animated, not stylized"

    full_negative = f"{negative}, {DEFAULT_NEGATIVE_PROMPT}".strip()
    return positive.strip(), full_negative.strip()


def build_scene_prompt(shot):
    """
    为每个shot构建场景图生成提示词。
    优先级: scene_description(剧本自带) > emotion自动生成
    """
    text = shot.get("text", "")
    emotion = shot.get("emotion", "default")

    # 优先使用剧本中明确定义的scene_description
    custom_scene = shot.get("scene_description", "").strip()
    if custom_scene:
        prompt = f"young Asian man, {custom_scene}"
        prompt += ", shot on iPhone 15 Pro, natural authentic lighting, realistic photo style, high quality"
        return prompt

    # 自动根据情绪生成场景
    emotion_scenes = {
        "sarcastic": "sitting casually, holding phone showing meme or news, slight amused knowing smile, raised eyebrow, modern casual setting, warm indoor lighting",
        "storytelling": "relaxed in cozy cafe, holding coffee cup, friendly nostalgic expression, hand gesturing while speaking, warm golden lighting",
        "humorous": "in funny relatable everyday situation, awkward amused expression, natural relaxed pose, candid street style photography, warm natural light",
        "excited": "energetic standing pose, animated hand gestures, enthusiastic bright expression, bright naturally lit room, engaged excited mood",
        "confident": "confident relaxed posture, direct calm eye contact, standing in clean modern space, soft natural side lighting, authoritative calm vibe",
        "intense": "serious focused expression, slight forward lean, dramatic window light from one side, contemplative intense mood, clean minimal background",
        "friendly": "warm approachable smile, relaxed casual pose, standing in bright welcoming space, soft even natural lighting, friendly inviting mood",
        "questioning": "curious pondering expression, slight head tilt, sitting casually with elbows on table, warm cafe lighting, thoughtful curious mood",
        "serious": "serious composed professional expression, sitting at clean desk workspace, balanced natural lighting, formal but not stiff, focused working mood",
        "casual": "very relaxed casual everyday expression, leaning casually against wall or furniture, natural window light, comfortable conversational mood",
    }

    emotion_key = EMOTION_MAP.get(emotion, "friendly")
    scene_template = emotion_scenes.get(emotion_key, emotion_scenes["friendly"])

    # 根据文案关键词二次微调
    if any(w in text for w in ["告", "告状", "索赔", "打官司"]):
        scene_template += ", looking at legal document or phone with serious expression"
    elif any(w in text for w in ["饭馆", "米其林", "菜单", "兄弟"]):
        scene_template += ", sitting at restaurant table"
    elif any(w in text for w in ["134亿", "800亿", "钱", "估值"]):
        scene_template += ", looking at phone showing money or numbers"
    elif any(w in text for w in ["开源", "闭源", "xAI"]):
        scene_template += ", looking at code or laptop screen"
    elif any(w in text for w in ["上帝", "神"]):
        scene_template += ", looking slightly upward thoughtfully"

    prompt = f"young Asian man, {scene_template}, shot on iPhone 15 Pro, authentic natural lighting, 35mm focal length, realistic candid photo style, no artificial enhancement"
    return prompt


# ─── API 工具 ───────────────────────────────────────────────────

def api_request(method, path, payload=None, timeout=60, max_retries=3):
    config = load_config()
    base_url = config["qingyun_base_url"]
    api_key = get_api_key()
    url = f"{base_url}{path}"

    for attempt in range(max_retries):
        try:
            data = json.dumps(payload).encode() if payload else None
            req = urllib.request.Request(
                url, data=data,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {api_key}",
                },
                method=method,
            )
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read())
        except urllib.error.HTTPError as e:
            body = e.read().decode()[:300]
            print(f"  HTTP {e.code} (attempt {attempt+1}/{max_retries}): {body}")
            if e.code == 429:
                print(f"  Rate limited, sleeping 30s...")
                time.sleep(30)
            if attempt == max_retries - 1:
                raise
            time.sleep(5)
        except (urllib.error.URLError, TimeoutError) as e:
            print(f"  Network error (attempt {attempt+1}/{max_retries}): {e}")
            if attempt == max_retries - 1:
                raise
            time.sleep(5)
    return None


def api_poll(path, interval=15, max_wait=360):
    elapsed = 0
    last_status = "unknown"
    while elapsed < max_wait:
        try:
            result = api_request("GET", path, max_retries=1)
        except Exception as e:
            print(f"  Poll error, retrying in {interval}s: {e}")
            time.sleep(interval)
            elapsed += interval
            continue

        status = result.get("status") or result.get("data", {}).get("task_status", "unknown")
        if status != last_status:
            print(f"  [{elapsed}s] {status}")
            last_status = status

        if status in ("succeed", "completed"):
            return result
        elif status in ("failed", "error"):
            raise RuntimeError(f"Task failed: {json.dumps(result)[:300]}")

        time.sleep(interval)
        elapsed += interval

    raise TimeoutError(f"Polling timed out after {max_wait}s")


def gemini_request(payload, timeout=120, max_retries=3):
    config = load_config()
    api_key = get_api_key()
    model = payload.get("model", config["tts_model"])
    url = f"{config['qingyun_base_url']}/v1beta/models/{model}:generateContent?key={api_key}"

    for attempt in range(max_retries):
        try:
            data = json.dumps(payload).encode()
            req = urllib.request.Request(url, data=data,
                headers={"Content-Type": "application/json"}, method="POST")
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read())
        except Exception as e:
            print(f"  Gemini error (attempt {attempt+1}/{max_retries}): {e}")
            if attempt == max_retries - 1:
                raise
            time.sleep(5)


def grok_image_request(prompt, ref_image_b64=None, size="960x960", timeout=120, max_retries=3):
    """
    调用Grok图像生成（支持参考图）。
    qingyun Grok API: POST /v1/images/generations
    返回: base64编码的图片数据（而非URL）
    """
    config = load_config()
    api_key = get_api_key()
    url = f"{config['qingyun_base_url']}/v1/images/generations"

    for attempt in range(max_retries):
        try:
            payload = {
                "model": "grok-imagine-image-pro",
                "prompt": prompt,
                "image_size": size,
            }
            if ref_image_b64:
                payload["reference_image"] = ref_image_b64

            # 用curl避免SSL问题
            import subprocess as _sub
            cmd = [
                "curl", "-sL", "-X", "POST", url,
                "-H", "Content-Type: application/json",
                "-H", f"Authorization: Bearer {api_key}",
                "-d", json.dumps(payload),
                "--max-time", str(timeout)
            ]
            proc = _sub.run(cmd, capture_output=True, timeout=timeout + 10)
            if proc.returncode != 0:
                raise RuntimeError(f"curl failed: {proc.stderr.decode()[:200]}")

            result = json.loads(proc.stdout)

            # Grok返回URL，不是base64
            img_url = result.get("data", [{}])[0].get("url", "")
            if not img_url:
                # 尝试异步任务
                task_id = result.get("data", {}).get("task_id") or result.get("task_id")
                if task_id:
                    print(f"  Grok task {task_id}, polling...")
                    poll_result = api_poll(f"/v1/images/generations/{task_id}", interval=10, max_wait=180)
                    img_url = poll_result.get("data", [{}])[0].get("url", "")

            if not img_url:
                raise RuntimeError(f"No URL in Grok response: {json.dumps(result)[:200]}")

            # 下载图片到临时文件
            import tempfile as _tmp
            tmp_fd, tmp_path = _tmp.mkstemp(suffix=".jpg")
            os.close(tmp_fd)
            dl = _sub.run(
                ["curl", "-sL", "--max-time", "60", "-o", tmp_path, img_url],
                capture_output=True, timeout=70
            )
            if dl.returncode != 0:
                raise RuntimeError(f"Download failed: {dl.stderr.decode()[:100]}")

            with open(tmp_path, "rb") as f:
                img_data = f.read()
            os.unlink(tmp_path)
            return img_data

        except Exception as e:
            print(f"  Grok error (attempt {attempt+1}/{max_retries}): {e}")
            if attempt == max_retries - 1:
                raise
            time.sleep(5)


def download_grok_image(img_url, timeout=60):
    """从Grok URL下载图片数据"""
    import tempfile, subprocess as _sub
    tmp_fd, tmp_path = tempfile.mkstemp(suffix=".jpg")
    os.close(tmp_fd)
    r = _sub.run(
        ["curl", "-sL", "--max-time", str(timeout), "-o", tmp_path, img_url],
        capture_output=True, timeout=timeout + 10
    )
    if r.returncode != 0:
        raise RuntimeError(f"curl download failed: {r.stderr.decode()[:100]}")
    with open(tmp_path, "rb") as f:
        data = f.read()
    os.unlink(tmp_path)
    return data


def download_file(url, output_path):
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    for attempt in range(3):
        try:
            subprocess.run(
                ["curl", "-sL", "--max-time", "120", "-o", output_path, url],
                check=True, capture_output=True)
            if os.path.getsize(output_path) > 0:
                return True
        except Exception as e:
            print(f"  Download error (attempt {attempt+1}): {e}")
            time.sleep(3)
    return False


# ─── 图像处理 ───────────────────────────────────────────────────

def resize_for_kling(img_path, output_path, min_width=768):
    """确保图片尺寸符合Kling要求（≥512px宽）"""
    from PIL import Image
    img = Image.open(img_path)
    w, h = img.size
    if w >= min_width:
        return img_path  # 已经够大

    # 按比例放大到min_width
    new_w = min_width
    new_h = int(h * (min_width / w))
    resized = img.resize((new_w, new_h), Image.LANCZOS)
    resized.save(output_path, "JPEG", quality=95)
    print(f"  Resized {w}x{h} → {new_w}x{new_h}")
    return output_path


# ─── Step 0: 场景图生成 ─────────────────────────────────────────

def generate_scene_image(shot, output_dir, config, ref_face_b64=None):
    """
    为单个shot生成专属场景图。
    Grok生成 → 下载 → 裁剪为9:16竖屏 → resize到Kling要求
    """
    shot_id = shot["id"]
    output_path = os.path.join(output_dir, f"shot_{shot_id:02d}_scene.jpg")
    portrait_path = os.path.join(output_dir, f"shot_{shot_id:02d}_scene_portrait.jpg")
    resized_path = os.path.join(output_dir, f"shot_{shot_id:02d}_scene_768.jpg")

    # 检查是否已有可用的最终图
    if os.path.exists(resized_path) and os.path.getsize(resized_path) > 30000:
        print(f"  Shot {shot_id}: Scene image already exists, skipping")
        return resized_path

    print(f"  Shot {shot_id}: Generating scene image...")

    # 构建场景prompt
    scene_prompt = build_scene_prompt(shot)
    print(f"  Shot {shot_id}: Scene → {scene_prompt[:80]}...")

    img_data = None

    # 尝试1: Grok with reference face (bytes直接返回)
    if ref_face_b64:
        try:
            print(f"  Shot {shot_id}: Grok + ref face...")
            img_data = grok_image_request(
                prompt=scene_prompt,
                ref_image_b64=ref_face_b64,
                size="960x960",
                timeout=180
            )
        except Exception as e:
            print(f"  Shot {shot_id}: Grok ref failed ({e}), trying without ref...")

    # 尝试2: Grok without reference
    if not img_data:
        try:
            img_data = grok_image_request(
                prompt=scene_prompt,
                size="960x960",
                timeout=180
            )
        except Exception as e:
            print(f"  Shot {shot_id}: Grok failed: {e}")
            raise RuntimeError(f"Shot {shot_id}: Scene image generation failed: {e}")

    # 保存原始图
    with open(output_path, "wb") as f:
        f.write(img_data)
    print(f"  Shot {shot_id}: Raw saved ({len(img_data)//1024}KB, {Image.open(output_path).size})")

    # 裁剪+resize为9:16竖屏（Kling要求）
    img = Image.open(output_path)
    w, h = img.size

    # 如果是横屏(宽>高)，裁剪中间部分转为竖屏
    if w > h:
        # 计算9:16裁剪（从中心裁）
        target_ratio = 9 / 16
        current_ratio = w / h
        if current_ratio > target_ratio:
            # 太宽了，裁左右
            new_w = int(h * target_ratio)
            left = (w - new_w) // 2
            img = img.crop((left, 0, left + new_w, h))

    # 缩放到宽度≥768（Kling最低要求）
    w2, h2 = img.size
    if w2 < 768:
        scale = 768 / w2
        new_w, new_h = 768, int(h2 * scale)
        img = img.resize((new_w, new_h), Image.LANCZOS)

    img = img.convert("RGB")
    img.save(portrait_path, "JPEG", quality=95)
    print(f"  Shot {shot_id}: Portrait saved ({img.size})")

    # copy as the 768 version
    import shutil
    shutil.copy(portrait_path, resized_path)
    return resized_path


# ─── Step 1: TTS ────────────────────────────────────────────────

def generate_tts(shot, output_dir, config):
    shot_id = shot["id"]
    text = shot["text"]
    tts_voice = shot.get("tts_voice", config.get("tts_voice", "Kore"))
    output_path = os.path.join(output_dir, f"shot_{shot_id:02d}_audio.mp3")

    if os.path.exists(output_path) and os.path.getsize(output_path) > 100:
        print(f"  Shot {shot_id}: TTS exists, skipping")
        return output_path

    print(f"  Shot {shot_id}: TTS ({len(text)} chars)...")

    payload = {
        "model": config["tts_model"],
        "contents": [{"parts": [{"text": text}]}],
        "generationConfig": {
            "responseModalities": ["AUDIO"],
            "speechConfig": {
                "voiceConfig": {
                    "prebuiltVoiceConfig": {"voiceName": tts_voice}
                }
            }
        }
    }

    result = gemini_request(payload)
    parts = result.get("candidates", [{}])[0].get("content", {}).get("parts", [])
    for part in parts:
        if "inlineData" in part:
            audio_data = base64.b64decode(part["inlineData"]["data"])
            with open(output_path, "wb") as f:
                f.write(audio_data)
            print(f"  Shot {shot_id}: TTS saved ({len(audio_data)//1024}KB)")
            return output_path

    raise RuntimeError(f"Shot {shot_id}: No audio in TTS response")


# ─── Step 2: Kling Video ────────────────────────────────────────

def generate_video(shot, output_dir, config, scene_img_b64):
    shot_id = shot["id"]
    output_path = os.path.join(output_dir, f"shot_{shot_id:02d}_video.mp4")

    if os.path.exists(output_path) and os.path.getsize(output_path) > 10000:
        print(f"  Shot {shot_id}: Video exists, skipping")
        return output_path

    raw_dur = shot.get("duration", 5)
    duration = "5" if raw_dur <= 5 else "10"

    positive_prompt, negative_prompt = build_video_prompt(shot, config)
    print(f"  Shot {shot_id}: Video prompt → {positive_prompt[:70]}...")

    payload = {
        "model_name": config["video_model"],
        "image": scene_img_b64,
        "prompt": positive_prompt,
        "duration": duration,
        "aspect_ratio": config["aspect_ratio"],
        "image_tail": "",
        "negative_prompt": negative_prompt,
        "mode": config.get("video_mode", "std"),
        "cfg_scale": config.get("video_cfg_scale", 0.3),
    }

    result = api_request("POST", "/kling/v1/videos/image2video", payload, timeout=60)
    task_id = result.get("data", {}).get("task_id") or result.get("task_id")
    if not task_id:
        raise RuntimeError(f"Shot {shot_id}: No task_id: {json.dumps(result)[:200]}")

    print(f"  Shot {shot_id}: Kling {task_id}, polling...")
    poll_result = api_poll(f"/kling/v1/videos/image2video/{task_id}", interval=15, max_wait=360)

    videos = poll_result.get("data", {}).get("task_result", {}).get("videos", [])
    if not videos:
        raise RuntimeError(f"Shot {shot_id}: No video in result")

    if not download_file(videos[0]["url"], output_path):
        raise RuntimeError(f"Shot {shot_id}: Download failed")

    print(f"  Shot {shot_id}: Video saved ({os.path.getsize(output_path)//1024}KB)")
    return output_path


# ─── Step 3: Lip Sync ───────────────────────────────────────────

def generate_lipsync(shot, video_path, audio_path, output_dir, config):
    shot_id = shot["id"]
    output_path = os.path.join(output_dir, f"shot_{shot_id:02d}_lipsync.mp4")

    if os.path.exists(output_path) and os.path.getsize(output_path) > 10000:
        print(f"  Shot {shot_id}: Lipsync exists, skipping")
        return output_path

    print(f"  Shot {shot_id}: Lip sync...")

    # 人脸检测
    face_result = api_request("POST", "/kling/v1/videos/lip-sync/face",
                                {"video": video_path}, timeout=60)
    session_id = face_result.get("session_id") or face_result.get("data", {}).get("session_id")
    face_id = face_result.get("face_id") or face_result.get("data", {}).get("face_id", "-1")
    if not session_id:
        raise RuntimeError(f"Shot {shot_id}: Face detection failed: {json.dumps(face_result)[:200]}")

    print(f"  Shot {shot_id}: Face OK (session={session_id[:16]})")

    # 对口型任务
    audio_dur_ms = shot.get("duration", 5) * 1000 + 2000
    lip_payload = {
        "session_id": session_id,
        "face_choose": [{
            "face_id": face_id,
            "sound_file": audio_path,
            "sound_start_time": 0,
            "sound_end_time": audio_dur_ms,
            "sound_insert_time": 0,
            "sound_volume": config.get("lip_sync_sound_volume", 1),
            "original_audio_volume": config.get("lip_sync_orig_volume", 0),
        }]
    }

    lip_result = api_request("POST", "/kling/v1/videos/advanced-lip-sync", lip_payload, timeout=60)
    task_id = lip_result.get("task_id") or lip_result.get("data", {}).get("task_id")
    if not task_id:
        raise RuntimeError(f"Shot {shot_id}: Lip task failed: {json.dumps(lip_result)[:200]}")

    print(f"  Shot {shot_id}: Lip task {task_id}, polling...")
    poll_result = api_poll(f"/kling/v1/videos/advanced-lip-sync/{task_id}", interval=15, max_wait=360)

    video_url = (poll_result.get("task_result", {}).get("video_url")
                 or poll_result.get("data", {}).get("video_url", ""))
    if not video_url:
        raise RuntimeError(f"Shot {shot_id}: No video URL in lip result")

    if not download_file(video_url, output_path):
        raise RuntimeError(f"Shot {shot_id}: Lip download failed")

    print(f"  Shot {shot_id}: Lipsync saved ({os.path.getsize(output_path)//1024}KB)")
    return output_path


# ─── Step 4: Merge ─────────────────────────────────────────────

def merge_videos(shot_paths, output_dir, config, bgm_path=None):
    final_path = os.path.join(output_dir, "final.mp4")
    concat_path = os.path.join(output_dir, "concat_list.txt")

    with open(concat_path, "w") as f:
        for p in sorted(shot_paths):
            f.write(f"file '{p}'\n")

    print(f"Merging {len(shot_paths)} clips...")
    merged = os.path.join(output_dir, "merged_no_bgm.mp4")

    cmd = ["ffmpeg", "-y", "-f", "concat", "-safe", "0",
           "-i", concat_path, "-c", "copy", merged]
    r = subprocess.run(cmd, capture_output=True)
    if r.returncode != 0:
        print(f"  Concat error: {r.stderr.decode()[:200]}")

    if bgm_path and os.path.exists(bgm_path):
        print(f"Adding BGM: {bgm_path}")
        cmd = [
            "ffmpeg", "-y", "-i", merged,
            "-stream_loop", "-1", "-i", bgm_path,
            "-filter_complex",
            f"[0:a]volume={config.get('voice_volume', 1.0)}[a1];"
            f"[1:a]volume={config.get('bgm_volume', 0.25)}[a2];"
            f"[a1][a2]amix=inputs=2:duration=first[aout]",
            "-map", "0:v", "-map", "[aout]",
            "-c:v", "copy", "-shortest", final_path
        ]
        subprocess.run(cmd, capture_output=True)
    else:
        if os.path.exists(merged):
            os.rename(merged, final_path)

    if os.path.exists(final_path):
        print(f"✅ Final: {final_path} ({os.path.getsize(final_path)//(1024*1024)}MB)")
        return final_path
    return None


# ─── 主流程 ────────────────────────────────────────────────────

def run_pipeline(script_path, output_dir=None, step="all", concurrent=1):
    config = load_config()

    with open(script_path) as f:
        script = json.load(f)

    shots = script["shots"]
    ref_face_path = script.get("avatar_image", config.get("avatar_image"))
    bgm_path = script.get("bgm_path")
    if not output_dir:
        output_dir = script.get("output_dir", config["output_dir"])

    os.makedirs(output_dir, exist_ok=True)

    print(f"\n🎬 Digital Human Pipeline v3")
    print(f"   Title: {script.get('title', 'untitled')}")
    print(f"   Shots: {len(shots)}")
    print(f"   Face Ref: {ref_face_path}")
    print(f"   Output: {output_dir}")
    print(f"   Concurrent: {concurrent}")
    print()

    # 加载参考脸
    ref_face_b64 = None
    if ref_face_path and os.path.exists(ref_face_path):
        with open(ref_face_path, "rb") as f:
            ref_face_b64 = base64.b64encode(f.read()).decode()
        print(f"📎 Loaded face reference: {os.path.getsize(ref_face_path)//1024}KB")
    else:
        print("⚠️ No face reference image found, scene images may lack face consistency")

    # ── Step 0: 场景图 ──
    if step in ("all", "image"):
        print(f"🖼️ Step 0: Generating scene images (concurrent=1 to avoid rate limit)...")
        scene_paths = {}
        for shot in shots:
            try:
                p = generate_scene_image(shot, output_dir, config, ref_face_b64)
                scene_paths[shot["id"]] = p
            except Exception as e:
                print(f"  ❌ Shot {shot['id']} scene failed: {e}")
        print()

    # 加载场景图路径
    if step not in ("image",):
        scene_paths = {}
        for shot in shots:
            p = os.path.join(output_dir, f"shot_{shot['id']:02d}_scene_768.jpg")
            alt_p = os.path.join(output_dir, f"shot_{shot['id']:02d}_scene.jpg")
            if os.path.exists(p):
                scene_paths[shot["id"]] = p
            elif os.path.exists(alt_p):
                scene_paths[shot["id"]] = alt_p

    # ── Step 1: TTS ──
    if step in ("all", "tts"):
        print("📝 Step 1: TTS audio...")
        for shot in shots:
            try:
                generate_tts(shot, output_dir, config)
            except Exception as e:
                print(f"  ❌ Shot {shot['id']} TTS failed: {e}")
        print()

    # 加载音频路径
    if step not in ("tts",):
        pass  # 从output_dir重新扫描

    audio_paths = {}
    for shot in shots:
        p = os.path.join(output_dir, f"shot_{shot['id']:02d}_audio.mp3")
        if os.path.exists(p):
            audio_paths[shot["id"]] = p

    # ── Step 2: Kling Video ──
    if step in ("all", "video"):
        print(f"🎬 Step 2: Kling videos (concurrent={concurrent})...")
        video_paths = {}

        def gen_vid(shot):
            sid = shot["id"]
            img_path = scene_paths.get(sid)
            if not img_path:
                print(f"  ⚠️ Shot {sid}: No scene image, skipping video")
                return sid, None
            try:
                with open(img_path, "rb") as f:
                    img_b64 = base64.b64encode(f.read()).decode()
                return sid, generate_video(shot, output_dir, config, img_b64)
            except Exception as e:
                print(f"  ❌ Shot {sid} video failed: {e}")
                return sid, None

        for shot in shots:
            sid, path = gen_vid(shot)
            if path:
                video_paths[sid] = path
        print()

    # 加载视频路径
    if step not in ("video",):
        video_paths = {}
        for shot in shots:
            p = os.path.join(output_dir, f"shot_{shot['id']:02d}_video.mp4")
            if os.path.exists(p):
                video_paths[shot["id"]] = p

    # ── Step 3: Lip Sync ──
    if step in ("all", "lipsync"):
        print(f"👄 Step 3: Lip sync...")
        lipsync_paths = {}
        for shot in shots:
            sid = shot["id"]
            vp = video_paths.get(sid)
            ap = audio_paths.get(sid)
            if not vp or not ap:
                print(f"  ⚠️ Shot {sid}: Missing video/audio, skipping lip")
                continue
            try:
                p = generate_lipsync(shot, vp, ap, output_dir, config)
                lipsync_paths[sid] = p
            except Exception as e:
                print(f"  ❌ Shot {sid} lip failed: {e}")
        print()

    # 加载lip路径
    if step not in ("lipsync",):
        lipsync_paths = {}
        for shot in shots:
            p = os.path.join(output_dir, f"shot_{shot['id']:02d}_lipsync.mp4")
            if os.path.exists(p):
                lipsync_paths[shot["id"]] = p

    # ── Step 4: Merge ──
    if step in ("all", "merge"):
        print("🔗 Step 4: Merging...")
        valid = [lipsync_paths[s["id"]] for s in shots if s["id"] in lipsync_paths]
        if valid:
            final = merge_videos(valid, output_dir, config, bgm_path)
            if final:
                print(f"\n🎉 Done! {final}")
        else:
            print("❌ No lipsync clips to merge!")

    print("\n✅ Pipeline v3 complete.")


# ─── CLI ────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Digital Human Video Pipeline v3")
    parser.add_argument("--script", required=True)
    parser.add_argument("--output", help="Output directory")
    parser.add_argument("--step", default="all",
                        choices=["all", "image", "tts", "video", "lipsync", "merge"])
    parser.add_argument("--concurrent", type=int, default=1,
                        help="Concurrent tasks (default 1 to avoid 429)")
    args = parser.parse_args()
    run_pipeline(args.script, args.output, args.step, args.concurrent)
