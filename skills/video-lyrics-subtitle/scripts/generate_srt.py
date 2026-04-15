#!/usr/bin/env python3
"""
generate_srt.py — 从歌词文本 + 时间轴生成 SRT 字幕文件

支持输入格式：
  1. LRC 格式（带 [mm:ss.xx] 时间戳）
  2. 纯文本（按行等间隔分配时间，需 --audio 或 --duration）
  3. JSON 时间轴（--json-timeline 带精确时间）

用法:
  python3 generate_srt.py <lyrics_file> [options]
"""

import argparse
import json
import os
import re
import struct
import sys
import subprocess


def format_srt_time(seconds: float) -> str:
    """将秒数转为 SRT 时间格式 HH:MM:SS,mmm"""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int(round((seconds - int(seconds)) * 1000))
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def parse_lrc(filepath: str) -> list[tuple[float, str]]:
    """解析 LRC 格式歌词，返回 [(时间秒, 歌词文本), ...]"""
    lines = []
    time_pattern = re.compile(r'\[(\d{1,2}):(\d{2})(?:\.(\d{1,3}))?\]')
    with open(filepath, 'r', encoding='utf-8') as f:
        for raw_line in f:
            raw_line = raw_line.strip()
            if not raw_line:
                continue
            # 提取所有时间标签
            timestamps = time_pattern.findall(raw_line)
            if not timestamps:
                # 没有时间标签的行，可能是元数据或纯歌词
                text = raw_line.strip()
                if text:
                    lines.append((None, text))
                continue
            # 去掉时间标签，取歌词文本
            text = time_pattern.sub('', raw_line).strip()
            for ts in timestamps:
                minutes = int(ts[0])
                seconds = int(ts[1])
                frac = ts[2] if ts[2] else '0'
                # 补齐到3位
                frac = frac.ljust(3, '0')[:3]
                total = minutes * 60 + seconds + int(frac) / 1000.0
                lines.append((total, text))
    # 按时间排序
    lines.sort(key=lambda x: x[0] if x[0] is not None else 0)
    return lines


def parse_plain_text(filepath: str, duration: float) -> list[tuple[float, str]]:
    """
    解析纯文本歌词，按行等间隔分配时间。
    空行表示纯音乐段，标注 (纯音乐)。
    """
    with open(filepath, 'r', encoding='utf-8') as f:
        raw_lines = [line.rstrip('\n').rstrip('\r') for line in f]

    # 过滤完全空白行但保留为纯音乐标记
    entries = []
    for line in raw_lines:
        stripped = line.strip()
        if not stripped:
            entries.append('')  # 空白 = 纯音乐段
        else:
            entries.append(stripped)

    if not entries:
        return []

    # 非空条目数
    non_empty = [e for e in entries if e]
    if not non_empty:
        # 全部是空行 → 整首歌都是纯音乐
        return [(0.0, '(纯音乐)', duration)]

    interval = duration / len(entries) if entries else 0
    result = []
    for i, entry in enumerate(entries):
        start = i * interval
        end = (i + 1) * interval
        text = entry if entry else '(纯音乐)'
        result.append((start, text, end))
    return result


def parse_json_timeline(filepath: str) -> dict:
    """读取 JSON 时间轴文件"""
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)


def get_audio_duration(filepath: str) -> float:
    """
    获取音频文件时长（秒）。
    不依赖 mutagen 等外部库，优先用 ffprobe，回退到 mp3 header 解析。
    """
    # 方法1: ffprobe
    ffprobe = os.path.expanduser('~/tools/ffmpeg/ffprobe')
    if not os.path.exists(ffprobe):
        # 尝试系统 ffprobe
        ffprobe = 'ffprobe'
    try:
        result = subprocess.run(
            [ffprobe, '-v', 'quiet', '-print_format', 'json',
             '-show_format', '-show_streams', filepath],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            info = json.loads(result.stdout)
            dur = info.get('format', {}).get('duration')
            if dur:
                return float(dur)
    except Exception:
        pass

    # 方法2: MP3 header 解析 (VBR 兼容)
    try:
        return _mp3_duration_by_frames(filepath)
    except Exception:
        pass

    # 方法3: 文件大小 / 码率估算（不太准确）
    return 0.0


def _mp3_duration_by_frames(filepath: str) -> float:
    """通过解析 MP3 帧头计算时长（兼容 CBR/VBR）"""
    # MPEG1 Layer3 比特率表 (kbps)
    bitrate_table = [
        0, 32, 40, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320, 0
    ]
    # 采样率表
    sample_rate_table = [44100, 48000, 32000, 0]

    with open(filepath, 'rb') as f:
        total_frames = 0
        total_samples = 0
        sample_rate = None

        data = f.read(10)  # skip possible ID3v2 header
        if data[:3] == b'ID3':
            size = (data[6] << 21) | (data[7] << 14) | (data[8] << 7) | data[9]
            f.seek(size + 10)
        else:
            f.seek(0)

        for _ in range(50000):  # max frames to parse
            header = f.read(4)
            if len(header) < 4:
                break

            h = struct.unpack('>I', header)[0]

            # Sync word
            if (h >> 21) & 0x7FF != 0x7FF:
                f.seek(-3, 1)
                continue

            # MPEG1 = bits 20-19 = 11
            version = (h >> 19) & 3
            if version != 3:  # not MPEG1
                f.seek(-3, 1)
                continue

            # Layer3 = bits 18-17 = 01
            layer = (h >> 17) & 3
            if layer != 1:  # not Layer III
                f.seek(-3, 1)
                continue

            br_idx = (h >> 12) & 0xF
            sr_idx = (h >> 10) & 3
            padding = (h >> 9) & 1

            if br_idx == 0 or br_idx == 15 or sr_idx == 3:
                f.seek(-3, 1)
                continue

            bitrate = bitrate_table[br_idx] * 1000
            sr = sample_rate_table[sr_idx]
            if sample_rate is None:
                sample_rate = sr

            # Frame size = 144 * bitrate / sample_rate + padding
            frame_size = int(144 * bitrate / sr) + padding
            samples_per_frame = 1152

            total_frames += 1
            total_samples += samples_per_frame

            # Skip frame data (already read 4 bytes of header)
            f.seek(frame_size - 4, 1)

        if sample_rate and total_samples > 0:
            return total_samples / sample_rate

    return 0.0


def build_srt_from_lrc(entries: list, duration: float = 0) -> str:
    """从 LRC 解析结果生成 SRT 内容"""
    output = []
    for i, (start, text) in enumerate(entries):
        if not text:
            text = '(纯音乐)'
        # 计算结束时间：下一条的开始时间，或总时长
        if i + 1 < len(entries) and entries[i + 1][0] is not None:
            end = entries[i + 1][0]
        else:
            end = start + 5.0 if duration == 0 else duration
        output.append(f"{i + 1}")
        output.append(f"{format_srt_time(start)} --> {format_srt_time(end)}")
        output.append(text)
        output.append("")
    return '\n'.join(output)


def build_srt_from_plain(entries: list) -> str:
    """从纯文本等间隔分配结果生成 SRT 内容"""
    output = []
    for i, (start, text, end) in enumerate(entries):
        output.append(f"{i + 1}")
        output.append(f"{format_srt_time(start)} --> {format_srt_time(end)}")
        output.append(text)
        output.append("")
    return '\n'.join(output)


def build_srt_from_json(lyrics_lines: list, json_data: dict) -> str:
    """
    从 JSON 时间轴数据生成 SRT。
    JSON 格式: {"sections": [{"lines": [{"text": ..., "time_start": ..., "time_end": ...}]}]}
    也支持 scenes 格式: {"scenes": [{"start_s": ..., "end_s": ..., "section": ...}]}
    """
    output = []
    idx = 1

    # 方式1: sections.lines 格式
    if 'sections' in json_data:
        for section in json_data['sections']:
            for line in section.get('lines', []):
                text = line.get('text', '').strip()
                if not text:
                    continue
                start = line.get('time_start', 0)
                end = line.get('time_end', start + 5)

                # 清理标签如 <verse1>, <chorus> 等
                clean = re.sub(r'<[^>]+>', '', text).strip()
                if not clean:
                    clean = text  # 保留原文

                output.append(f"{idx}")
                output.append(f"{format_srt_time(start)} --> {format_srt_time(end)}")
                output.append(clean)
                output.append("")
                idx += 1

    # 方式2: scenes 格式（用歌词行分配到场景）
    elif 'scenes' in json_data and lyrics_lines:
        scenes = json_data['scenes']
        total_duration = json_data.get('total_duration_s', 0)

        # 将歌词行分配到各场景
        non_empty_lines = [l for l in lyrics_lines if l.strip()]
        if not non_empty_lines:
            return ""

        for scene in scenes:
            start_s = scene.get('start_s', 0)
            end_s = scene.get('end_s', start_s + 5)
            duration_s = end_s - start_s
            section = scene.get('section', '')

            # 场景内按歌词行等分
            # 每个场景分配 2-4 行（根据时长）
            lines_per_scene = max(1, int(duration_s / 8))
            scene_lines = []
            while non_empty_lines and lines_per_scene > 0:
                scene_lines.append(non_empty_lines.pop(0))
                lines_per_scene -= 1

            if not scene_lines:
                scene_lines = ['(纯音乐)']

            line_interval = duration_s / len(scene_lines)
            for j, line_text in enumerate(scene_lines):
                l_start = start_s + j * line_interval
                l_end = start_s + (j + 1) * line_interval
                output.append(f"{idx}")
                output.append(f"{format_srt_time(l_start)} --> {format_srt_time(l_end)}")
                output.append(line_text.strip())
                output.append("")
                idx += 1

    return '\n'.join(output)


def add_bilingual(srt_content: str, cn_file: str) -> str:
    """
    在 SRT 中添加中文翻译行。
    原文行和翻译行在同一条目内用 \\N 分隔。
    """
    with open(cn_file, 'r', encoding='utf-8') as f:
        cn_lines = [line.strip() for line in f if line.strip()]

    # 解析 SRT
    blocks = re.split(r'\n\n+', srt_content.strip())
    output_blocks = []

    for i, block in enumerate(blocks):
        lines = block.split('\n')
        if len(lines) < 3:
            output_blocks.append(block)
            continue

        seq = lines[0]
        timecode = lines[1]
        text_lines = lines[2:]

        # 获取对应的中文翻译
        cn_text = cn_lines[i] if i < len(cn_lines) else ''

        if cn_text:
            # 用 \N 连接原文和翻译（SRT/ASS 换行标记）
            combined = '\\N'.join(text_lines) + '\\N' + cn_text
            output_blocks.append(f"{seq}\n{timecode}\n{combined}")
        else:
            output_blocks.append(block)

    return '\n\n'.join(output_blocks) + '\n'


def detect_format(filepath: str) -> str:
    """检测歌词文件格式：lrc / plain / json"""
    with open(filepath, 'r', encoding='utf-8') as f:
        first_chars = f.read(100)

    if first_chars.strip().startswith('{'):
        return 'json'

    if re.search(r'\[\d{1,2}:\d{2}', first_chars):
        return 'lrc'

    return 'plain'


def _apply_time_offset(srt_content: str, offset: float) -> str:
    """
    给 SRT 中每条字幕的时间加上偏移（秒）。
    用于 Phase 分段编译时对齐时间轴。
    offset > 0 → 时间后移，offset < 0 → 时间前移。
    """
    def shift_time(match):
        start = parse_srt_time_inline(match.group(1))
        end = parse_srt_time_inline(match.group(2))
        new_start = max(0.0, start + offset)
        new_end = max(0.0, end + offset)
        return f"{format_srt_time(new_start)} --> {format_srt_time(new_end)}"

    return re.sub(
        r'(\d{2}:\d{2}:\d{2}[,.]\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2}[,.]\d{3})',
        shift_time,
        srt_content
    )


def parse_srt_time_inline(time_str: str) -> float:
    """将 SRT 时间格式转为秒数"""
    match = re.match(r'(\d{2}):(\d{2}):(\d{2})[,.](\d{3})', time_str.strip())
    if not match:
        return 0.0
    h, m, s, ms = match.groups()
    return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000.0


def main():
    parser = argparse.ArgumentParser(
        description='从歌词文本 + 时间轴生成 SRT 字幕文件'
    )
    parser.add_argument('lyrics_file', help='歌词文件路径（LRC、纯文本或 JSON）')
    parser.add_argument('--audio', help='音频文件，用于获取总时长')
    parser.add_argument('--duration', type=float, help='总时长（秒）')
    parser.add_argument('--bilingual', help='中文翻译文件路径')
    parser.add_argument('--json-timeline', help='带时间轴的 JSON 文件路径')
    parser.add_argument('--offset', type=float, default=0.0,
                        help='时间偏移（秒），用于 Phase 分段编译时对齐时间轴')
    parser.add_argument('-o', '--output', help='输出 SRT 文件路径（默认 stdout）')

    args = parser.parse_args()

    if not os.path.exists(args.lyrics_file):
        print(f"错误：歌词文件不存在: {args.lyrics_file}", file=sys.stderr)
        sys.exit(1)

    fmt = detect_format(args.lyrics_file)
    srt_content = ''

    if fmt == 'json':
        # JSON 格式：直接从文件读取时间轴
        with open(args.lyrics_file, 'r', encoding='utf-8') as f:
            json_data = json.load(f)
        lyrics_lines = []
        srt_content = build_srt_from_json(lyrics_lines, json_data)

    elif fmt == 'lrc':
        entries = parse_lrc(args.lyrics_file)
        duration = 0
        if args.audio:
            duration = get_audio_duration(args.audio)
        elif args.duration:
            duration = args.duration
        srt_content = build_srt_from_lrc(entries, duration)

    else:
        # 纯文本
        # 读取歌词行
        with open(args.lyrics_file, 'r', encoding='utf-8') as f:
            lyrics_lines = [line.rstrip('\n\r') for line in f]

        # 如果有 JSON 时间轴，用它
        if args.json_timeline:
            json_data = parse_json_timeline(args.json_timeline)
            srt_content = build_srt_from_json(lyrics_lines, json_data)
        else:
            # 等间隔分配
            duration = 0
            if args.audio:
                duration = get_audio_duration(args.audio)
                if duration <= 0:
                    print("错误：无法获取音频时长，请用 --duration 指定", file=sys.stderr)
                    sys.exit(1)
            elif args.duration:
                duration = args.duration
            else:
                print("错误：纯文本歌词需要 --audio 或 --duration 指定总时长", file=sys.stderr)
                sys.exit(1)

            entries = parse_plain_text(args.lyrics_file, duration)
            srt_content = build_srt_from_plain(entries)

    # 应用时间偏移
    if args.offset and args.offset != 0.0:
        srt_content = _apply_time_offset(srt_content, args.offset)

    # 添加双语翻译
    if args.bilingual:
        if not os.path.exists(args.bilingual):
            print(f"警告：中文翻译文件不存在: {args.bilingual}", file=sys.stderr)
        else:
            srt_content = add_bilingual(srt_content, args.bilingual)

    # 输出
    if args.output:
        os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(srt_content)
        print(f"✅ SRT 字幕已生成: {args.output}", file=sys.stderr)
    else:
        print(srt_content)


if __name__ == '__main__':
    main()
