#!/usr/bin/env python3
"""
歌词→场景映射 + 音频精准分段
用法: python3 lyrics_segment_sync.py --lyrics lyrics.json --scenes scenes.json --audio song.mp3 --outdir output/
"""

import json
import argparse
import subprocess
import os
from pathlib import Path

def load_json(path):
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

def map_lyrics_to_clips(lyrics_data, scenes_data):
    """
    将歌词行映射到视频clip，生成 edit_plan
    """
    lines = lyrics_data.get('lines', [])
    scenes = scenes_data.get('scenes', [])
    
    if not scenes:
        # 从 video_plan 格式解析
        scenes = scenes_data
    
    edit_plan = []
    
    for scene in scenes:
        scene_start = scene.get('start_s', scene.get('time_start', 0))
        scene_end = scene.get('end_s', scene.get('time_end', 0))
        scene_id = scene.get('scene_id', scene.get('id', 0))
        emotion = scene.get('emotion_score', scene.get('emotion', 5))
        
        # 找到时间轴上对应的歌词行
        matching_lines = []
        for line in lines:
            line_start = line.get('start_s', line.get('time_start', 0))
            line_end = line.get('end_s', line.get('time_end', 0))
            
            # 歌词行与场景时间有重叠
            if line_start < scene_end and line_end > scene_start:
                matching_lines.append(line)
        
        # 如果没有精确匹配，用最近的歌词
        if not matching_lines and lines:
            min_dist = float('inf')
            closest = None
            for line in lines:
                mid = (line.get('start_s', 0) + line.get('end_s', 0)) / 2
                scene_mid = (scene_start + scene_end) / 2
                dist = abs(mid - scene_mid)
                if dist < min_dist:
                    min_dist = dist
                    closest = line
            if closest:
                matching_lines = [closest]
        
        edit_plan.append({
            'scene_id': scene_id,
            'start_s': scene_start,
            'end_s': scene_end,
            'duration_s': scene_end - scene_start,
            'emotion': emotion,
            'lyrics': matching_lines,
            'lyrics_text': ' '.join([l.get('text', '') for l in matching_lines]),
            'lyrics_cn': ' '.join([l.get('text_cn', '') for l in matching_lines]),
            'section': scene.get('section', scene.get('section_type', '')),
        })
    
    return edit_plan

def segment_audio(audio_path, edit_plan, output_dir, fade_in=0.3, fade_out=0.5):
    """
    用 ffmpeg 精准裁剪音频段
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    segments = []
    for i, clip in enumerate(edit_plan):
        start = clip['start_s']
        end = clip['end_s']
        duration = end - start
        
        if duration <= 0:
            continue
        
        out_file = output_dir / f"segment_{i:02d}_scene{clip['scene_id']}.m4a"
        
        cmd = [
            'ffmpeg', '-y', '-hide_banner',
            '-i', audio_path,
            '-ss', str(start),
            '-to', str(end),
            '-af', f'afade=t=in:st=0:d={fade_in},afade=t=out:st={duration-fade_out}:d={fade_out}',
            '-c:a', 'aac', '-b:a', '192k',
            str(out_file)
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode == 0:
            segments.append({
                'file': str(out_file),
                'scene_id': clip['scene_id'],
                'start_s': start,
                'end_s': end,
            })
            print(f"  ✅ Segment {i:02d}: {start:.1f}s - {end:.1f}s → {out_file.name}")
        else:
            print(f"  ❌ Segment {i:02d} failed: {result.stderr[-200:]}")
    
    return segments

def generate_srt(edit_plan, output_path, style='dual'):
    """
    从 edit_plan 生成 SRT 字幕文件
    """
    def fmt_time(seconds):
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = int(seconds % 60)
        ms = int((seconds % 1) * 1000)
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"
    
    srt_entries = []
    idx = 1
    
    for clip in edit_plan:
        for line in clip.get('lyrics', []):
            start = line.get('start_s', line.get('time_start', 0))
            end = line.get('end_s', line.get('time_end', 0))
            text = line.get('text', '')
            text_cn = line.get('text_cn', '')
            
            if not text:
                continue
            
            if style == 'dual' and text_cn:
                display = f"{text}\n{text_cn}"
            elif style == 'single':
                display = text
            elif style == 'cn_only':
                display = text_cn or text
            else:
                display = text
            
            srt_entries.append(f"{idx}")
            srt_entries.append(f"{fmt_time(start)} --> {fmt_time(end)}")
            srt_entries.append(display)
            srt_entries.append("")
            idx += 1
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(srt_entries))
    
    print(f"📝 SRT saved: {output_path} ({idx-1} entries)")

def main():
    parser = argparse.ArgumentParser(description='Lyrics-Video Sync Engine')
    parser.add_argument('--lyrics', required=True, help='Lyrics JSON file')
    parser.add_argument('--scenes', required=True, help='Scenes/video-plan JSON file')
    parser.add_argument('--audio', help='Audio MP3 file (for segmentation)')
    parser.add_argument('--outdir', default='./output', help='Output directory')
    parser.add_argument('--fade-in', type=float, default=0.3, help='Audio fade-in seconds')
    parser.add_argument('--fade-out', type=float, default=0.5, help='Audio fade-out seconds')
    parser.add_argument('--srt', action='store_true', help='Generate SRT subtitles')
    parser.add_argument('--srt-style', default='dual', choices=['single', 'dual', 'cn_only'])
    
    args = parser.parse_args()
    
    lyrics_data = load_json(args.lyrics)
    scenes_data = load_json(args.scenes)
    
    # 映射歌词到场景
    print("🗺️  Mapping lyrics to scenes...")
    edit_plan = map_lyrics_to_clips(lyrics_data, scenes_data)
    
    # 保存 edit_plan
    plan_path = Path(args.outdir) / 'edit_plan.json'
    plan_path.parent.mkdir(parents=True, exist_ok=True)
    with open(plan_path, 'w', encoding='utf-8') as f:
        json.dump(edit_plan, f, ensure_ascii=False, indent=2)
    print(f"📋 Edit plan saved: {plan_path}")
    
    # 显示映射结果
    for clip in edit_plan:
        lyrics_short = clip['lyrics_text'][:40] if clip['lyrics_text'] else '(纯音乐)'
        cn_short = clip['lyrics_cn'][:40] if clip['lyrics_cn'] else ''
        print(f"  Scene {clip['scene_id']}: {clip['start_s']:.0f}-{clip['end_s']:.0f}s [{clip['section']}] → {lyrics_short}")
        if cn_short:
            print(f"    🈶 {cn_short}")
    
    # 分段音频
    if args.audio:
        print(f"\n🎵 Segmenting audio: {args.audio}")
        segments = segment_audio(args.audio, edit_plan, args.outdir, 
                                args.fade_in, args.fade_out)
        print(f"  Total segments: {len(segments)}")
    
    # 生成 SRT
    if args.srt:
        srt_path = Path(args.outdir) / 'lyrics.srt'
        generate_srt(edit_plan, str(srt_path), args.srt_style)

if __name__ == '__main__':
    main()
