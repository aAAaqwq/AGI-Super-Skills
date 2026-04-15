#!/usr/bin/env python3
"""
extract_phase.py — 从完整音频 + SRT + 歌词中提取指定时间段的 Phase 素材

为 MV 分段编译提供精确同步的素材：
  1. 分段音频（从完整音频中截取）
  2. 分段字幕（SRT，时间轴从 00:00 开始）
  3. 歌词文本片段（仅该时间段内的歌词行）

用法:
  python3 extract_phase.py \
    --audio audio/song_final.mp3 \
    --srt subtitles/lyrics.srt \
    --lyrics lyrics/lyrics.txt \
    --start 208.0 \
    --end 237.0 \
    --phase 1 \
    --outdir .

输出:
  <outdir>/audio/phase<N>_audio.mp3   — 分段音频
  <outdir>/subtitles/phase<N>_lyrics.srt — 分段字幕（00:00 起始）
  <outdir>/lyrics/phase<N>_lyrics.txt — 歌词文本片段
"""

import argparse
import os
import re
import subprocess
import sys


def format_srt_time(seconds: float) -> str:
    """将秒数转为 SRT 时间格式 HH:MM:SS,mmm"""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int(round((seconds - int(seconds)) * 1000))
    # 处理进位（如 999.999ms → 1s）
    if ms >= 1000:
        s += 1
        ms -= 1000
    if s >= 60:
        m += 1
        s -= 60
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def parse_srt_time(time_str: str) -> float:
    """将 SRT 时间格式 HH:MM:SS,mmm 转为秒数"""
    match = re.match(r'(\d{2}):(\d{2}):(\d{2})[,.](\d{3})', time_str.strip())
    if not match:
        raise ValueError(f"无效 SRT 时间格式: {time_str}")
    h, m, s, ms = match.groups()
    return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000.0


def parse_srt(filepath: str) -> list[dict]:
    """
    解析 SRT 文件，返回 [{"index": int, "start": float, "end": float, "text": str}, ...]
    """
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    blocks = re.split(r'\n\n+', content.strip())
    entries = []

    for block in blocks:
        lines = block.strip().split('\n')
        if len(lines) < 3:
            continue

        # 第一行：序号
        try:
            index = int(lines[0].strip())
        except ValueError:
            continue

        # 第二行：时间码
        time_match = re.match(
            r'(\d{2}:\d{2}:\d{2}[,.]\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2}[,.]\d{3})',
            lines[1].strip()
        )
        if not time_match:
            continue

        start = parse_srt_time(time_match.group(1))
        end = parse_srt_time(time_match.group(2))

        # 第三行起：字幕文本
        text = '\n'.join(lines[2:]).strip()

        entries.append({
            'index': index,
            'start': start,
            'end': end,
            'text': text,
        })

    return entries


def extract_srt_phase(entries: list[dict], phase_start: float, phase_end: float) -> list[dict]:
    """
    从完整 SRT 条目中提取指定时间范围的条目。
    时间轴重置为从 00:00 开始。
    处理部分重叠的条目（裁剪起止时间）。
    """
    phase_entries = []

    for entry in entries:
        s, e = entry['start'], entry['end']

        # 跳过完全在范围外的条目
        if e <= phase_start or s >= phase_end:
            continue

        # 裁剪到 Phase 范围内
        clipped_start = max(s, phase_start)
        clipped_end = min(e, phase_end)

        # 时间轴偏移：减去 phase_start，使从 00:00 开始
        new_start = clipped_start - phase_start
        new_end = clipped_end - phase_start

        # 确保不为负
        new_start = max(0.0, new_start)
        new_end = max(new_start + 0.001, new_end)

        phase_entries.append({
            'start': new_start,
            'end': new_end,
            'text': entry['text'],
        })

    # 按时间排序
    phase_entries.sort(key=lambda x: x['start'])

    return phase_entries


def build_phase_srt(phase_entries: list[dict]) -> str:
    """将分段 SRT 条目组装为 SRT 格式字符串"""
    lines = []
    for i, entry in enumerate(phase_entries):
        lines.append(str(i + 1))
        lines.append(f"{format_srt_time(entry['start'])} --> {format_srt_time(entry['end'])}")
        lines.append(entry['text'])
        lines.append('')
    return '\n'.join(lines)


def extract_lyrics_phase(srt_entries: list[dict], phase_start: float, phase_end: float) -> list[str]:
    """
    从 SRT 条目中提取 Phase 范围内的歌词文本行。
    过滤掉纯音乐/标签等非歌词行。
    """
    lyrics_lines = []
    skip_patterns = [
        r'^\(纯音乐\)$',
        r'^\[.*\]$',
        r'^\.\.\.$',
        r'^（.*）$',
    ]

    for entry in srt_entries:
        s, e = entry['start'], entry['end']
        # 跳过完全在范围外的
        if e <= phase_start or s >= phase_end:
            continue

        text = entry['text'].strip()
        # 跳过纯音乐/标签行
        is_skip = False
        for pat in skip_patterns:
            if re.match(pat, text):
                is_skip = True
                break
        if not is_skip and text:
            lyrics_lines.append(text)

    return lyrics_lines


def extract_audio_phase(audio_path: str, phase_start: float, phase_end: float,
                        output_path: str) -> bool:
    """使用 FFmpeg 从完整音频中截取指定时间段"""
    duration = phase_end - phase_start

    # FFmpeg 路径
    ffmpeg = os.path.expanduser('~/tools/ffmpeg/ffmpeg')
    if not os.path.exists(ffmpeg):
        ffmpeg = 'ffmpeg'

    cmd = [
        ffmpeg,
        '-i', audio_path,
        '-ss', str(phase_start),
        '-t', str(duration),
        '-c:a', 'aac',
        '-b:a', '192k',
        '-y',
        output_path,
    ]

    print(f"🎵 截取音频: {phase_start:.1f}s → {phase_end:.1f}s ({duration:.1f}s)")
    print(f"   命令: {' '.join(cmd)}")

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"❌ FFmpeg 错误:\n{result.stderr}", file=sys.stderr)
        return False

    return True


def main():
    parser = argparse.ArgumentParser(
        description='从完整音频 + SRT + 歌词中提取 Phase 分段素材'
    )
    parser.add_argument('--audio', required=True, help='完整音频文件路径')
    parser.add_argument('--srt', required=True, help='完整 SRT 字幕文件路径')
    parser.add_argument('--lyrics', help='歌词文本文件路径（可选，用于提取歌词片段）')
    parser.add_argument('--start', type=float, required=True,
                        help='Phase 起始时间（秒）')
    parser.add_argument('--end', type=float, required=True,
                        help='Phase 结束时间（秒）')
    parser.add_argument('--phase', type=int, required=True,
                        help='Phase 编号')
    parser.add_argument('--outdir', default='.',
                        help='输出根目录（默认当前目录）')

    args = parser.parse_args()

    phase_start = args.start
    phase_end = args.end
    phase_num = args.phase
    outdir = os.path.abspath(args.outdir)

    duration = phase_end - phase_start
    print(f"🎬 Phase {phase_num}: {phase_start:.1f}s → {phase_end:.1f}s ({duration:.1f}s)")
    print()

    # === 1. 解析完整 SRT ===
    if not os.path.exists(args.srt):
        print(f"❌ SRT 文件不存在: {args.srt}", file=sys.stderr)
        sys.exit(1)

    entries = parse_srt(args.srt)
    print(f"📝 完整 SRT: {len(entries)} 条字幕")

    # === 2. 提取分段 SRT ===
    phase_entries = extract_srt_phase(entries, phase_start, phase_end)
    print(f"📝 Phase SRT: {len(phase_entries)} 条字幕")

    if not phase_entries:
        print("⚠️  该时间段内无字幕条目")
    else:
        print(f"   第一条: {format_srt_time(phase_entries[0]['start'])} → {phase_entries[0]['text'][:30]}")
        print(f"   最后条: {format_srt_time(phase_entries[-1]['end'])} → {phase_entries[-1]['text'][:30]}")

    # 写入分段 SRT
    srt_outdir = os.path.join(outdir, 'subtitles')
    os.makedirs(srt_outdir, exist_ok=True)
    srt_path = os.path.join(srt_outdir, f'phase{phase_num}_lyrics.srt')

    phase_srt_content = build_phase_srt(phase_entries)
    with open(srt_path, 'w', encoding='utf-8') as f:
        f.write(phase_srt_content)
    print(f"✅ 分段 SRT 已保存: {srt_path}")
    print()

    # === 3. 提取歌词文本片段 ===
    lyrics_lines = extract_lyrics_phase(entries, phase_start, phase_end)
    lyrics_outdir = os.path.join(outdir, 'lyrics')
    os.makedirs(lyrics_outdir, exist_ok=True)
    lyrics_path = os.path.join(lyrics_outdir, f'phase{phase_num}_lyrics.txt')

    with open(lyrics_path, 'w', encoding='utf-8') as f:
        for line in lyrics_lines:
            f.write(line + '\n')
    print(f"📝 歌词片段 ({len(lyrics_lines)} 行): {lyrics_path}")
    for line in lyrics_lines:
        print(f"   {line}")
    print()

    # === 4. 截取分段音频 ===
    if not os.path.exists(args.audio):
        print(f"⚠️  音频文件不存在，跳过音频截取: {args.audio}", file=sys.stderr)
    else:
        audio_outdir = os.path.join(outdir, 'audio')
        os.makedirs(audio_outdir, exist_ok=True)
        audio_path = os.path.join(audio_outdir, f'phase{phase_num}_audio.m4a')

        if extract_audio_phase(args.audio, phase_start, phase_end, audio_path):
            print(f"✅ 分段音频已保存: {audio_path}")
        print()

    # === 汇总 ===
    print(f"🎉 Phase {phase_num} 素材提取完成！")
    print(f"   音频: {srt_path.replace('/subtitles/', '/audio/').replace('.srt', '.m4a')}")
    print(f"   字幕: {srt_path}")
    print(f"   歌词: {lyrics_path}")


if __name__ == '__main__':
    main()
