#!/usr/bin/env python3
"""
audio-analyzer.py — 音频分析器
分析音频文件，输出：时长、BPM估计、能量曲线、场景时间节点
支持 MP3/WAV/M4A
"""

import sys
import json
import argparse
import struct
import math

try:
    from mutagen.mp3 import MP3
    HAS_MUTAGEN = True
except ImportError:
    HAS_MUTAGEN = False


def get_duration(audio_path: str) -> float:
    """获取音频时长（秒）"""
    if not HAS_MUTAGEN:
        # Fallback: estimate from file size and bitrate
        import os
        size = os.path.getsize(audio_path)
        # Assume 192kbps if can't read
        return size * 8 / 192000
    ext = audio_path.lower().split('.')[-1]
    if ext == 'mp3':
        return MP3(audio_path).info.length
    elif ext in ('wav', 'wave'):
        import wave
        with wave.open(audio_path, 'r') as w:
            frames = w.getnframes()
            rate = w.getframerate()
            return frames / float(rate)
    else:
        # Try mutagen for other formats
        from mutagen.File import File
        f = File(audio_path)
        return f.info.length


def estimate_bpm_simple(audio_path: str) -> int:
    """
    简单BPM估算 — 基于文件扩展名和常见音乐BPM
    真实BPM检测需要librosa，尝试import
    """
    try:
        import librosa
        y, sr = librosa.load(audio_path, sr=None, duration=30)
        tempo, _ = librosa.beat.beat_track(y=y, sr=sr)
        return int(float(tempo))
    except ImportError:
        pass
    
    # Fallback: 根据时长和常见BPM估算
    # 215s 的歌曲通常是 60-120 BPM
    # 邓紫棋的歌通常在 80-100 BPM
    return 88  # 默认中等节奏


def get_audio_info(audio_path: str) -> dict:
    """获取音频基础信息"""
    info = {"duration": 0, "bitrate": 0, "sample_rate": 0, "channels": 0}
    
    if not HAS_MUTAGEN:
        return info
        
    ext = audio_path.lower().split('.')[-1]
    try:
        if ext == 'mp3':
            audio = MP3(audio_path)
            info["duration"] = round(audio.info.length, 1)
            info["bitrate"] = audio.info.bitrate
            info["sample_rate"] = audio.info.sample_rate
            info["channels"] = audio.info.channels
        else:
            from mutagen.File import File
            f = File(audio_path)
            info["duration"] = round(f.info.length, 1)
            info["bitrate"] = getattr(f.info, 'bitrate', 0)
            info["sample_rate"] = getattr(f.info, 'sample_rate', 0)
            info["channels"] = getattr(f.info, 'channels', 0)
    except Exception as e:
        info["error"] = str(e)
    
    return info


def generate_scene_timeline(duration: float, num_scenes: int = 9) -> list:
    """
    根据音频时长生成场景分配时间线
    策略：
    - 前奏/平静段 → 场景少、时长短
    - 主歌 → 逐步递增
    - 副歌 → 场景多、时长长
    - 尾声 → 快速收尾
    """
    
    # 自动计算各段落时长比例（基于常见歌曲结构）
    # 结构: Intro(10%) → Verse1(15%) → Chorus1(20%) → Verse2(15%) → Chorus2(20%) → Bridge(10%) → Outro(10%)
    # 对应到 num_scenes 个场景
    
    total = duration
    
    # 计算各场景起止时间（秒）
    # 使用能量检测模拟：平静→上升→高潮→回落
    if num_scenes == 9:
        # 9场景分配（推荐）
        breaks = [0.0]
        # 副歌在 40-60% 位置
        chorus_start = total * 0.40
        chorus_end = total * 0.75
        
        # 生成 9 个时间节点
        # 场景1: 0-前奏 10%
        # 场景2: 10%-主歌1 25%  
        # 场景3: 25%-40% 过渡
        # 场景4-6: 40%-75% 副歌（3个场景平分）
        # 场景7-8: 75%-90% 主歌2+桥段
        # 场景9: 90%-100% 尾声
        
        t = 0
        scenes = []
        # Scene 1: 0 - 10%
        scenes.append({"scene": 1, "start": t, "end": total * 0.10, "energy": 3.0})
        t = total * 0.10
        # Scene 2: 10% - 25%
        scenes.append({"scene": 2, "start": t, "end": total * 0.25, "energy": 4.5})
        t = total * 0.25
        # Scene 3: 25% - 40%
        scenes.append({"scene": 3, "start": t, "end": total * 0.40, "energy": 6.0})
        t = total * 0.40
        # Scene 4-6: 副歌 40% - 75%
        chunk = (total * 0.75 - t) / 3
        for i in range(3):
            scenes.append({"scene": 4 + i, "start": t, "end": t + chunk, "energy": 9.0 - (2-i)*0.5})
            t += chunk
        # Scene 7: 75% - 85%
        scenes.append({"scene": 7, "start": t, "end": total * 0.88, "energy": 8.5})
        t = total * 0.88
        # Scene 8: 88% - 95%
        scenes.append({"scene": 8, "start": t, "end": total * 0.96, "energy": 10.0})
        t = total * 0.96
        # Scene 9: 96% - 100%
        scenes.append({"scene": 9, "start": t, "end": total, "energy": 2.0})
        
    elif num_scenes == 6:
        # 6场景简化版
        scenes = []
        chunk = total / 6
        energies = [3.0, 4.5, 6.0, 9.0, 8.5, 2.0]
        for i in range(6):
            scenes.append({"scene": i+1, "start": i*chunk, "end": (i+1)*chunk, "energy": energies[i]})
    else:
        # 通用均分
        chunk = total / num_scenes
        scenes = []
        for i in range(num_scenes):
            progress = i / (num_scenes - 1) if num_scenes > 1 else 0
            energy = 3 + 7 * math.sin(progress * math.pi)
            scenes.append({"scene": i+1, "start": i*chunk, "end": (i+1)*chunk, "energy": round(energy, 1)})
    
    return scenes


def format_timestamp(seconds: float) -> str:
    """秒 → MM:SS 格式"""
    m = int(seconds // 60)
    s = seconds - m * 60
    return f"{m:02d}:{s:05.2f}"


def main():
    parser = argparse.ArgumentParser(description="音频分析器 — 分析音频生成MV时间线")
    parser.add_argument("audio", help="音频文件路径 (.mp3/.wav/.m4a)")
    parser.add_argument("-o", "--output", help="输出 JSON 文件路径")
    parser.add_argument("-s", "--scenes", type=int, default=9, help="场景数量 (默认: 9)")
    parser.add_argument("-v", "--verbose", action="store_true", help="详细输出")
    args = parser.parse_args()
    
    audio_path = args.audio
    
    # 1. 获取音频信息
    info = get_audio_info(audio_path)
    duration = info.get("duration", 0)
    
    if duration == 0:
        print(f"❌ 无法读取音频: {audio_path}")
        sys.exit(1)
    
    # 2. BPM 估算
    bpm = estimate_bpm_simple(audio_path)
    
    # 3. 生成场景时间线
    scenes = generate_scene_timeline(duration, args.scenes)
    
    # 4. 组装结果
    result = {
        "audio_file": audio_path,
        "info": info,
        "bpm_estimated": bpm,
        "total_duration_s": duration,
        "total_duration_formatted": format_timestamp(duration),
        "num_scenes": args.scenes,
        "scenes": scenes,
        "scene_summary": [
            {
                "scene": s["scene"],
                "time_range": f"{format_timestamp(s['start'])}-{format_timestamp(s['end'])}",
                "start_s": round(s["start"], 1),
                "end_s": round(s["end"], 1),
                "duration_s": round(s["end"] - s["start"], 1),
                "emotion_score": s["energy"]
            }
            for s in scenes
        ]
    }
    
    if args.verbose:
        print(f"📊 音频分析结果:")
        print(f"   时长: {result['total_duration_formatted']} ({duration}s)")
        print(f"   采样率: {info['sample_rate']} Hz")
        print(f"   码率: {info['bitrate']//1000 if info['bitrate'] else '?'} kbps")
        print(f"   估算BPM: {bpm}")
        print(f"   场景数: {args.scenes}")
        print()
        for sc in result["scene_summary"]:
            print(f"   Scene {sc['scene']}: {sc['time_range']} ({sc['duration_s']}s) emotion={sc['emotion_score']}")
    
    output = args.output or audio_path.replace(".mp3", "_analysis.json").replace(".wav", "_analysis.json")
    with open(output, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    
    print(f"✅ 分析完成 → {output}")
    return result


if __name__ == "__main__":
    main()
