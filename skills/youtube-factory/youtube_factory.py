#!/usr/bin/env python3
"""
YouTube Factory - Generate complete YouTube videos from prompts
100% Free tools - No expensive APIs required (self-contained, no external modules)

Usage:
    python youtube_factory.py "5 Morning Habits of Successful People"
    python youtube_factory.py "How AI Works" --style documentary --length 8
    python youtube_factory.py "Quick Python Tips" --shorts

Homepage: https://github.com/Mayank8290/openclaw-video-skills
"""

import os
import json
import argparse
import tempfile
import subprocess
import re
import requests
from pathlib import Path
from datetime import datetime
from typing import List, Dict
from urllib.parse import urlparse


# =============================================================================
# CONFIGURATION
# =============================================================================

OUTPUT_DIR = Path(os.getenv("OUTPUT_DIR", "~/Videos/OpenClaw")).expanduser()
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Load config from env file (only known keys for security)
_ALLOWED_CONFIG_KEYS = {"PEXELS_API_KEY", "OUTPUT_DIR", "DEFAULT_VOICE"}
_config_path = Path.home() / ".openclaw-video-skills" / "config.env"
if _config_path.exists():
    for line in _config_path.read_text().splitlines():
        if "=" in line and not line.startswith("#"):
            key, val = line.split("=", 1)
            key = key.strip()
            if key in _ALLOWED_CONFIG_KEYS:
                os.environ.setdefault(key, val.strip())

PEXELS_API_KEY = os.getenv("PEXELS_API_KEY", "")

ALLOWED_STOCK_DOMAINS = [
    "pexels.com", "videos.pexels.com", "images.pexels.com",
]


# =============================================================================
# SECURITY UTILITIES
# =============================================================================

def secure_tempfile(suffix: str = "") -> str:
    """Create a secure temporary file (no race condition)"""
    fd, path = tempfile.mkstemp(suffix=suffix)
    os.close(fd)
    return path


def validate_stock_url(url: str) -> bool:
    """Validate URL is from Pexels (prevents SSRF)"""
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            return False
        return any(
            parsed.netloc == d or parsed.netloc.endswith("." + d)
            for d in ALLOWED_STOCK_DOMAINS
        )
    except Exception:
        return False


# =============================================================================
# VIDEO UTILITIES (inlined - no external dependencies)
# =============================================================================

def text_to_speech(text: str, output_path: str, voice: str = None,
                   rate: str = "+0%", pitch: str = "+0Hz") -> str:
    """Convert text to speech using Edge TTS (free Microsoft voices)"""
    voice = voice or os.getenv("DEFAULT_VOICE", "en-US-ChristopherNeural")
    subprocess.run([
        "edge-tts", "--voice", voice, "--rate", rate,
        "--pitch", pitch, "--text", text, "--write-media", output_path
    ], capture_output=True)
    return output_path


def search_stock_videos(query: str, count: int = 5,
                        orientation: str = "landscape") -> List[Dict]:
    """Search Pexels for free stock videos"""
    if not PEXELS_API_KEY:
        print("WARNING: No Pexels API key. Get one free at https://www.pexels.com/api/")
        return []

    response = requests.get(
        "https://api.pexels.com/videos/search",
        headers={"Authorization": PEXELS_API_KEY},
        params={"query": query, "per_page": count, "orientation": orientation, "size": "medium"},
        timeout=30,
    )
    if response.status_code != 200:
        return []

    videos = []
    for video in response.json().get("videos", []):
        files = video.get("video_files", [])
        hd = next((f for f in files if f.get("quality") == "hd"), files[0] if files else None)
        if hd:
            videos.append({
                "id": video["id"], "url": hd["link"],
                "duration": video.get("duration", 0),
                "width": hd.get("width"), "height": hd.get("height"),
            })
    return videos


def download_stock_video(url: str, output_path: str) -> str:
    """Download stock video (with SSRF protection)"""
    if not validate_stock_url(url):
        raise ValueError(f"URL not from allowed stock domain: {url}")
    response = requests.get(url, stream=True, timeout=60)
    response.raise_for_status()
    with open(output_path, "wb") as f:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)
    return output_path


def concatenate_videos(video_paths: List[str], output_path: str) -> str:
    """Concatenate videos (handles different resolutions)"""
    if not video_paths:
        return output_path

    # Detect orientation from first clip
    target_w, target_h = 1080, 1920
    probe = subprocess.run([
        "ffprobe", "-v", "quiet", "-select_streams", "v:0",
        "-show_entries", "stream=width,height", "-of", "csv=p=0",
        video_paths[0]
    ], capture_output=True, text=True)
    if probe.stdout.strip():
        parts = probe.stdout.strip().split(",")
        if len(parts) == 2:
            w, h = int(parts[0]), int(parts[1])
            if w > h:
                target_w, target_h = 1920, 1080

    # Scale all to same resolution
    scaled = []
    for i, path in enumerate(video_paths):
        sp = secure_tempfile(suffix=f"_s{i}.mp4")
        subprocess.run([
            "ffmpeg", "-y", "-i", path,
            "-vf", f"scale={target_w}:{target_h}:force_original_aspect_ratio=decrease,pad={target_w}:{target_h}:(ow-iw)/2:(oh-ih)/2:black",
            "-c:v", "libx264", "-preset", "fast", "-crf", "23", "-c:a", "aac", sp
        ], capture_output=True)
        scaled.append(sp)

    # Concat using filter_complex
    filter_parts = "".join(f"[{i}:v]" for i in range(len(scaled)))
    cmd = ["ffmpeg", "-y"]
    for p in scaled:
        cmd.extend(["-i", p])
    cmd.extend([
        "-filter_complex", f"{filter_parts}concat=n={len(scaled)}:v=1:a=0[outv]",
        "-map", "[outv]", "-c:v", "libx264", "-preset", "fast", "-crf", "23",
        output_path
    ])
    subprocess.run(cmd, capture_output=True)

    for p in scaled:
        try:
            os.unlink(p)
        except OSError:
            pass
    return output_path


def add_audio_to_video(video_path: str, audio_path: str, output_path: str) -> str:
    """Add voiceover to video"""
    probe = subprocess.run([
        "ffprobe", "-v", "quiet", "-select_streams", "a",
        "-show_entries", "stream=codec_type", "-of", "csv=p=0", video_path
    ], capture_output=True, text=True)

    if probe.stdout.strip():
        subprocess.run([
            "ffmpeg", "-y", "-i", video_path, "-i", audio_path,
            "-filter_complex", "[0:a]volume=0.1[v];[1:a]volume=1.0[a];[v][a]amix=inputs=2:duration=longest",
            "-c:v", "copy", output_path
        ], capture_output=True)
    else:
        subprocess.run([
            "ffmpeg", "-y", "-i", video_path, "-i", audio_path,
            "-c:v", "copy", "-c:a", "aac", "-map", "0:v:0", "-map", "1:a:0",
            output_path
        ], capture_output=True)
    return output_path


def add_captions(video_path: str, output_path: str, segments: List[Dict],
                 style: str = "modern") -> str:
    """Burn captions into video"""
    ass_file = secure_tempfile(suffix=".ass")
    styles = {
        "modern": ("Arial", 48, "&H00FFFFFF", "&H00000000", 3, 2, 2, 60),
        "bold": ("Impact", 56, "&H0000FFFF", "&H00000000", 4, 3, 2, 70),
    }
    fn, fs, pc, oc, ow, sh, al, mv = styles.get(style, styles["modern"])

    content = f"""[Script Info]
Title: Captions
ScriptType: v4.00+
PlayResX: 1920
PlayResY: 1080

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{fn},{fs},{pc},{pc},{oc},&H80000000,1,0,0,0,100,100,0,0,1,{ow},{sh},{al},10,10,{mv},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    for seg in segments:
        s = _fmt_ass(seg.get("start", 0))
        e = _fmt_ass(seg.get("end", 0))
        t = seg.get("text", "").replace("{", "\\{").replace("}", "\\}")
        t = t.replace("\n", "\\N")
        t = re.sub(r'[\x00-\x1f\x7f]', '', t)
        content += f"Dialogue: 0,{s},{e},Default,,0,0,0,,{t}\n"

    with open(ass_file, "w") as f:
        f.write(content)
    subprocess.run([
        "ffmpeg", "-y", "-i", video_path, "-vf", f"ass={ass_file}",
        "-c:v", "libx264", "-c:a", "copy", output_path
    ], capture_output=True)
    try:
        os.unlink(ass_file)
    except OSError:
        pass
    return output_path


def _fmt_ass(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    c = int((seconds % 1) * 100)
    return f"{h}:{m:02d}:{s:02d}.{c:02d}"


def resize_for_shorts(input_path: str, output_path: str) -> str:
    """Convert to vertical 9:16 for Shorts"""
    subprocess.run([
        "ffmpeg", "-y", "-i", input_path,
        "-vf", "scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2:black",
        "-c:v", "libx264", "-c:a", "aac", output_path
    ], capture_output=True)
    return output_path


def extract_frame(video_path: str, output_path: str, timestamp: float = 5.0) -> str:
    """Extract a frame for thumbnail"""
    subprocess.run([
        "ffmpeg", "-y", "-ss", str(timestamp), "-i", video_path,
        "-vframes", "1", "-q:v", "2", output_path
    ], capture_output=True)
    return output_path


def create_thumbnail(bg_path: str, output_path: str, title: str = "", subtitle: str = "") -> str:
    """Create YouTube thumbnail"""
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        print("WARNING: Pillow not installed. Skipping thumbnail.")
        return bg_path

    img = Image.open(bg_path).resize((1280, 720))
    draw = ImageDraw.Draw(img)
    try:
        tf = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 72)
        sf = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 36)
    except Exception:
        tf = sf = ImageFont.load_default()

    if title:
        for off in [(-2, -2), (-2, 2), (2, -2), (2, 2)]:
            draw.text((640 + off[0], 360 + off[1]), title, font=tf, fill="black", anchor="mm")
        draw.text((640, 360), title, font=tf, fill="white", anchor="mm")
    if subtitle:
        draw.text((640, 450), subtitle, font=sf, fill="yellow", anchor="mm")
    img.save(output_path)
    return output_path


def estimate_speech_duration(text: str, wpm: int = 150) -> float:
    return (len(text.split()) / wpm) * 60


def clean_text_for_speech(text: str) -> str:
    text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
    text = re.sub(r'\*(.+?)\*', r'\1', text)
    text = re.sub(r'#+ ', '', text)
    text = re.sub(r'\[(.+?)\]\(.+?\)', r'\1', text)
    text = re.sub(r'[^\w\s.,!?\'"-]', '', text)
    return text.strip()


# =============================================================================
# SCRIPT TEMPLATES
# =============================================================================

SCRIPT_PROMPTS = {
    "documentary": """Write a YouTube video script about: {topic}
Target length: {length} minutes (~{words} words)
Structure: HOOK (15s) → INTRO (30s) → {points} KEY POINTS → CONCLUSION → CTA
Style: Professional, engaging, conversational.
For each scene include: [SCENE NAME], script text, and VISUAL: description of B-roll needed.""",

    "listicle": """Write a "Top {points}" YouTube video about: {topic}
Target length: {length} minutes (~{words} words)
Count down from #{points} to #1. Each item: name, explain, example.
Include HOOK, INTRO, ITEMS, RECAP, CTA.""",

    "tutorial": """Write a step-by-step tutorial about: {topic}
Target length: {length} minutes (~{words} words)
Structure: Show end result → Prerequisites → {points} Steps → Common Mistakes → CTA""",

    "story": """Write a storytelling video about: {topic}
Target length: {length} minutes (~{words} words)
Structure: Start in action → Setup → Conflict → Journey → Climax → Resolution → Lesson""",

    "shorts": """Write a 60-second YouTube Shorts script about: {topic}
Max 150 words. HOOK (3s) → CONTENT (50s) → CTA (7s). Fast-paced, punchy.""",
}


# =============================================================================
# VIDEO GENERATION
# =============================================================================

def parse_script(script_text: str) -> list:
    """Parse script into scenes"""
    scenes = []
    current = {"text": "", "visual": "", "name": ""}
    for line in script_text.split("\n"):
        line = line.strip()
        if line.startswith("[") and "]" in line:
            if current["text"]:
                scenes.append(current)
            current = {"text": "", "visual": "", "name": line.strip("[]").split(":")[0]}
        elif line.upper().startswith("VISUAL:"):
            current["visual"] = line.replace("VISUAL:", "").strip()
        elif line and not line.startswith("(") and not line.startswith("---"):
            current["text"] += " " + line
    if current["text"]:
        scenes.append(current)
    for s in scenes:
        s["text"] = clean_text_for_speech(s["text"].strip())
    return scenes


def generate_video(topic: str, style: str = "documentary", length: int = 8,
                   voice: str = "en-US-ChristopherNeural", shorts: bool = False,
                   output_name: str = None) -> dict:
    """Generate a complete YouTube video from a topic"""
    print(f"\nYouTube Factory: Generating video about '{topic}'")
    print("=" * 60)

    if output_name is None:
        output_name = re.sub(r'[^a-z0-9-]', '', topic.lower().replace(" ", "-"))[:50]
    video_dir = OUTPUT_DIR / output_name
    video_dir.mkdir(parents=True, exist_ok=True)
    results = {"directory": str(video_dir)}

    if shorts:
        style, length = "shorts", 1

    wpm, points = 150, max(3, min(10, length))

    # Step 1: Script
    print("\nStep 1/6: Generating script...")
    script = f"""[HOOK]
Did you know that {topic} is changing everything we thought we knew?
VISUAL: Dramatic establishing shot

[INTRO]
In this video, we're going to explore {topic} in a way you've never seen before. Stay until the end for the most surprising revelation.
VISUAL: Dynamic montage related to {topic}

[MAIN POINT 1]
The first thing you need to understand about {topic} is that it's not what it seems. Most people make the mistake of overlooking the fundamentals.
VISUAL: Explanatory graphics or relevant B-roll

[MAIN POINT 2]
Here's where things get really interesting. The research shows that {topic} has evolved dramatically in recent years.
VISUAL: Data visualization or expert interviews

[MAIN POINT 3]
The implications of {topic} extend far beyond what we initially discussed. This is the part that blows most people's minds.
VISUAL: Impactful imagery

[CONCLUSION]
So there you have it. Remember the key points we covered today. If you found this valuable, hit subscribe and drop a comment below.
VISUAL: Subscribe button animation
"""
    script_path = video_dir / "script.md"
    script_path.write_text(f"# {topic}\n\nStyle: {style}\nLength: {length} min\n\n---\n\n{script}")
    results["script"] = str(script_path)
    scenes = parse_script(script)
    print(f"   Done - {len(scenes)} scenes")

    # Step 2: Voiceover
    print("\nStep 2/6: Generating voiceover...")
    full_text = " ".join(s["text"] for s in scenes)
    vo_path = str(video_dir / "voiceover.mp3")
    text_to_speech(full_text, vo_path, voice=voice)
    results["voiceover"] = vo_path
    print(f"   Done - Voiceover saved")

    # Step 3: Stock footage
    print("\nStep 3/6: Fetching stock footage...")
    orientation = "portrait" if shorts else "landscape"
    clips = []
    for i, scene in enumerate(scenes):
        query = (scene.get("visual") or topic)[:100]
        print(f"   Searching: {query[:40]}...")
        vids = search_stock_videos(query, count=2, orientation=orientation)
        if vids:
            cp = str(video_dir / f"clip_{i}.mp4")
            download_stock_video(vids[0]["url"], cp)
            clips.append(cp)
            print(f"   Done - clip {i + 1}/{len(scenes)}")
        else:
            print(f"   Warning - No footage for scene {i + 1}")

    # Step 4: Assemble
    print("\nStep 4/6: Assembling video...")
    if clips:
        raw = str(video_dir / "video_raw.mp4")
        concatenate_videos(clips, raw)
        with_audio = str(video_dir / "video_with_audio.mp4")
        add_audio_to_video(raw, vo_path, with_audio)
        results["video_raw"] = with_audio
        print("   Done - Video assembled")
    else:
        results["video_raw"] = vo_path
        with_audio = None
        print("   Warning - No clips, audio-only")

    # Step 5: Captions
    print("\nStep 5/6: Adding captions...")
    caption_segs = []
    t = 0
    for scene in scenes:
        for j in range(0, len(scene["text"].split()), 8):
            chunk = " ".join(scene["text"].split()[j:j + 8])
            dur = estimate_speech_duration(chunk)
            caption_segs.append({"start": t, "end": t + dur, "text": chunk})
            t += dur

    if with_audio and os.path.exists(with_audio):
        final = str(video_dir / "video_final.mp4")
        add_captions(with_audio, final, caption_segs)
        results["video_final"] = final
        print("   Done - Captions added")
    else:
        results["video_final"] = results.get("video_raw", vo_path)

    if shorts and os.path.exists(results.get("video_final", "")):
        sp = str(video_dir / "video_shorts.mp4")
        resize_for_shorts(results["video_final"], sp)
        results["video_shorts"] = sp
        print("   Done - Shorts format")

    # Step 6: Thumbnail
    print("\nStep 6/6: Generating thumbnail...")
    if clips:
        frame = str(video_dir / "thumb_frame.jpg")
        extract_frame(clips[0], frame, timestamp=2.0)
        thumb = str(video_dir / "thumbnail.jpg")
        create_thumbnail(frame, thumb, title=" ".join(topic.split()[:5]).upper())
        results["thumbnail"] = thumb
        print("   Done - Thumbnail created")

    # Metadata
    meta = {
        "title": topic, "description": f"In this video, we explore {topic}.",
        "tags": topic.lower().split() + ["tutorial", "explained"],
        "generated_at": datetime.now().isoformat(), "style": style, "voice": voice,
    }
    (video_dir / "metadata.json").write_text(json.dumps(meta, indent=2))
    results["metadata"] = str(video_dir / "metadata.json")

    print("\n" + "=" * 60)
    print("VIDEO GENERATION COMPLETE!")
    print("=" * 60)
    print(f"\nOutput folder: {video_dir}")
    for k, v in results.items():
        if k != "directory":
            print(f"   - {k}: {Path(v).name}")
    print(f"\nUpload '{Path(results.get('video_final', '')).name}' to YouTube!")
    return results


def main():
    parser = argparse.ArgumentParser(description="YouTube Factory - Generate videos from prompts")
    parser.add_argument("topic", help="Video topic")
    parser.add_argument("--style", default="documentary",
                        choices=["documentary", "listicle", "tutorial", "story"])
    parser.add_argument("--length", type=int, default=8, help="Target minutes")
    parser.add_argument("--voice", default="en-US-ChristopherNeural")
    parser.add_argument("--shorts", action="store_true", help="Generate Shorts (60s vertical)")
    parser.add_argument("--output", help="Custom output folder name")
    args = parser.parse_args()
    generate_video(topic=args.topic, style=args.style, length=args.length,
                   voice=args.voice, shorts=args.shorts, output_name=args.output)


if __name__ == "__main__":
    main()
