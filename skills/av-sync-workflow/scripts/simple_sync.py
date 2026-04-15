#!/usr/bin/env python3
"""
Simple Beat-Sync Video Assembly

Takes an audio file, video clip, and beat timestamps.
Syncs cuts to beats for a quick music video.

Usage:
    python3 simple_sync.py --audio song.mp3 --clip video.mp4 --beats beats.json -o output.mp4
"""

import argparse
import json
import subprocess
import os
import sys


def load_beats(beats_path: str) -> list:
    """Load beat timestamps from JSON or text file."""
    with open(beats_path, 'r') as f:
        if beats_path.endswith('.json'):
            data = json.load(f)
            return data.get('beats', [])
        else:
            return [float(line.strip()) for line in f if line.strip()]


def generate_edit_list(beats: list, clip_duration: float, video_duration: float) -> list:
    """Generate cut points from beats, mapping to clip."""
    cuts = []
    beat_idx = 0
    current_time = 0
    clip_pos = 0
    
    while current_time < video_duration and beat_idx < len(beats):
        cut_time = beats[beat_idx]
        if cut_time > video_duration:
            break
        
        cuts.append({
            "cut_time": cut_time,
            "clip_time": clip_pos,
            "duration": 60 / 120 / 4  # Default: 8th note
        })
        
        # Advance: 2 beats at a time (2-beat cuts)
        beat_idx += 2
        clip_pos += 60 / 120 * 2  # 2 beats worth
        if clip_pos > clip_duration:
            clip_pos = 0  # Loop clip
    
    return cuts


def assemble_with_ffmpeg(cuts: list, audio_path: str, clip_path: str, output_path: str, video_duration: float):
    """Assemble video using FFmpeg with segment concat."""
    
    # Create temp directory
    tmp_dir = "/tmp/av_sync_cuts"
    os.makedirs(tmp_dir, exist_ok=True)
    
    # Extract segments
    for i, cut in enumerate(cuts):
        start = cut["clip_time"]
        duration = cut["duration"]
        output = f"{tmp_dir}/seg_{i:04d}.mp4"
        
        cmd = [
            "ffmpeg", "-y", "-ss", str(start), "-i", clip_path,
            "-t", str(duration), "-c:v", "libx264", "-preset", "ultrafast",
            "-an", output
        ]
        subprocess.run(cmd, capture_output=True)
    
    # Create concat list
    list_file = f"{tmp_dir}/concat.txt"
    with open(list_file, "w") as f:
        for i in range(len(cuts)):
            f.write(f"file 'seg_{i:04d}.mp4'\n")
    
    # Concat segments
    cmd = [
        "ffmpeg", "-y", "-f", "concat", "-safe", "0",
        "-i", list_file, "-i", audio_path,
        "-c:v", "libx264", "-preset", "medium", "-crf", "23",
        "-c:a", "aac", "-b:a", "192k",
        "-shortest", output_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if result.returncode != 0:
        print(f"FFmpeg error: {result.stderr[-500:]}")
    
    # Cleanup
    for i in range(len(cuts)):
        seg_file = f"{tmp_dir}/seg_{i:04d}.mp4"
        if os.path.exists(seg_file):
            os.remove(seg_file)
    
    return result.returncode == 0


def main():
    parser = argparse.ArgumentParser(description="Simple beat-sync video")
    parser.add_argument("--audio", "-a", required=True, help="Audio file")
    parser.add_argument("--clip", "-c", required=True, help="Video clip")
    parser.add_argument("--beats", "-b", help="Beats JSON/TXT file (or auto-detect)")
    parser.add_argument("--output", "-o", required=True, help="Output MP4")
    parser.add_argument("--bpm", type=float, help="BPM if no beats file")
    parser.add_argument("--cuts-per-bar", type=int, default=2, help="Cuts per bar (1,2,4)")
    
    args = parser.parse_args()
    
    # Get video duration
    cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", args.clip]
    result = subprocess.run(cmd, capture_output=True, text=True)
    clip_duration = float(json.loads(result.stdout)["format"]["duration"])
    
    # Get audio duration
    cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", args.audio]
    result = subprocess.run(cmd, capture_output=True, text=True)
    audio_duration = float(json.loads(result.stdout)["format"]["duration"])
    
    print(f"Audio: {audio_duration:.1f}s, Clip: {clip_duration:.1f}s")
    
    # Generate beats
    if args.beats and os.path.exists(args.beats):
        beats = load_beats(args.beats)
        print(f"Loaded {len(beats)} beats")
    else:
        bpm = args.bpm or 120
        beat_interval = 60.0 / bpm
        beats = [round(i * beat_interval, 3) for i in range(int(audio_duration / beat_interval))]
        print(f"Generated {len(beats)} beats at {bpm} BPM")
    
    # Generate cuts
    cuts = generate_edit_list(beats, clip_duration, audio_duration)
    print(f"Generated {len(cuts)} cuts")
    
    # Assemble
    print(f"🎬 Assembling video...")
    success = assemble_with_ffmpeg(cuts, args.audio, args.clip, args.output, audio_duration)
    
    if success:
        size = os.path.getsize(args.output)
        print(f"✅ Output: {args.output} ({size / 1024 / 1024:.1f} MB)")
    else:
        print("❌ Assembly failed")
        sys.exit(1)


if __name__ == "__main__":
    main()
