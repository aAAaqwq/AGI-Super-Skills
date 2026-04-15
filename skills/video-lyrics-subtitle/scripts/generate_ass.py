#!/usr/bin/env python3
"""
generate_ass.py — SRT 转 ASS 字幕（支持 KTV 逐字高亮效果）

用法:
  python3 generate_ass.py <srt_file> [options]
"""

import argparse
import os
import re
import sys


# ── ASS 样式定义 ─────────────────────────────────────────────

ASS_HEADER_SIMPLE = """\
[Script Info]
Title: Lyrics Subtitle
ScriptType: v4.00+
PlayResX: 1920
PlayResY: 1080
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{fontname},{fontsize},&H{primary_colour},&H{secondary_colour},&H{outline_colour},&H{back_colour},0,0,0,0,100,100,0,0,1,{outline},{shadow},2,{margin_l},{margin_r},{margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

ASS_HEADER_KTV = """\
[Script Info]
Title: KTV Lyrics Subtitle
ScriptType: v4.00+
PlayResX: 1920
PlayResY: 1080
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{fontname},{fontsize},&H{primary_colour},&H{secondary_colour},&H{outline_colour},&H{back_colour},0,0,0,0,100,100,0,0,1,{outline},{shadow},2,{margin_l},{margin_r},{margin_v},1
Style: KTV,{fontname},{fontsize},&H{secondary_colour},&H{primary_colour},&H{outline_colour},&H{back_colour},0,0,0,0,100,100,0,0,1,{outline},{shadow},2,{margin_l},{margin_r},{margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


def hex_to_ass_color(hex_color: str) -> str:
    """
    将 #RRGGBB 或 #AARRGGBB 转为 ASS 颜色格式 &HAABBGGRR
    """
    hex_color = hex_color.lstrip('#')
    if len(hex_color) == 6:
        r, g, b = hex_color[0:2], hex_color[2:4], hex_color[4:6]
        a = '00'
    elif len(hex_color) == 8:
        a, r, g, b = hex_color[0:2], hex_color[2:4], hex_color[4:6], hex_color[6:8]
    else:
        return '00FFFFFF'  # default white

    return f"{a}{b}{g}{r}"


def parse_srt_time(time_str: str) -> float:
    """将 SRT 时间 HH:MM:SS,mmm 转为秒"""
    match = re.match(r'(\d+):(\d+):(\d+)[,.](\d+)', time_str.strip())
    if not match:
        return 0.0
    h, m, s, ms = match.groups()
    ms = ms.ljust(3, '0')[:3]
    return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000.0


def format_ass_time(seconds: float) -> str:
    """将秒数转为 ASS 时间格式 H:MM:SS.cc"""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    cs = int(round((seconds - int(seconds)) * 100))
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def parse_srt(filepath: str) -> list[dict]:
    """
    解析 SRT 文件，返回 [{'index': int, 'start': float, 'end': float, 'text': str}, ...]
    """
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    blocks = re.split(r'\n\n+', content.strip())
    entries = []

    for block in blocks:
        lines = block.strip().split('\n')
        if len(lines) < 3:
            continue

        # 序号
        try:
            index = int(lines[0].strip())
        except ValueError:
            continue

        # 时间行
        time_match = re.match(
            r'(\d+:\d+:\d+[,.]\d+)\s*-->\s*(\d+:\d+:\d+[,.]\d+)',
            lines[1].strip()
        )
        if not time_match:
            continue

        start = parse_srt_time(time_match.group(1))
        end = parse_srt_time(time_match.group(2))
        text = '\n'.join(lines[2:])

        entries.append({
            'index': index,
            'start': start,
            'end': end,
            'text': text,
            'duration': end - start,
        })

    return entries


def escape_ass_text(text: str) -> str:
    """转义 ASS 特殊字符"""
    text = text.replace('{', '\\{')
    text = text.replace('}', '\\}')
    return text


def generate_ktv_override(duration: float, text: str) -> str:
    """
    生成 KTV 逐字高亮的 override 标签。
    使用 \\kf (karaoke fill) 效果。
    """
    # 清理换行标记
    clean_text = text.replace('\\N', '\n').replace('\\n', '\n')
    chars = list(clean_text)

    if not chars or duration <= 0:
        return escape_ass_text(text)

    char_duration = duration / len(chars)
    # 构建 \k 标签序列
    # \k<duration> 表示接下来一个字符持续的时间（单位：1/10秒）
    kd = round(char_duration * 10)  # 转为 1/10 秒单位
    if kd < 1:
        kd = 1

    parts = []
    for char in chars:
        if char == '\n':
            parts.append('\\N')
        else:
            parts.append(f'{{\\kf{kd}}}{escape_ass_text(char)}')

    return ''.join(parts)


def srt_to_ass_simple(entries: list[dict], config: dict) -> str:
    """生成 simple 模式 ASS 字幕"""
    header = ASS_HEADER_SIMPLE.format(
        fontname=config['fontname'],
        fontsize=config['fontsize'],
        primary_colour=hex_to_ass_color(config['primary_color']),
        secondary_colour=hex_to_ass_color(config['secondary_color']),
        outline_colour=hex_to_ass_color(config['outline_color']),
        back_colour=hex_to_ass_color(config['back_color']),
        outline=config['outline'],
        shadow=config['shadow'],
        margin_l=config['margin_l'],
        margin_r=config['margin_r'],
        margin_v=config['margin_v'],
    )

    lines = [header]
    for entry in entries:
        start = format_ass_time(entry['start'])
        end = format_ass_time(entry['end'])
        text = escape_ass_text(entry['text'])
        # 添加描边和阴影效果
        text = f"{{\\bord{config['outline']}\\shad{config['shadow']}}}{text}"
        lines.append(
            f"Dialogue: 0,{start},{end},Default,,0,0,0,,{text}"
        )

    return '\n'.join(lines) + '\n'


def srt_to_ass_ktv(entries: list[dict], config: dict) -> str:
    """生成 KTV 模式 ASS 字幕（逐字高亮）"""
    header = ASS_HEADER_KTV.format(
        fontname=config['fontname'],
        fontsize=config['fontsize'],
        primary_colour=hex_to_ass_color(config['primary_color']),
        secondary_colour=hex_to_ass_color(config['secondary_color']),
        outline_colour=hex_to_ass_color(config['outline_color']),
        back_colour=hex_to_ass_color(config['back_color']),
        outline=config['outline'],
        shadow=config['shadow'],
        margin_l=config['margin_l'],
        margin_r=config['margin_r'],
        margin_v=config['margin_v'],
    )

    lines = [header]
    for entry in entries:
        start = format_ass_time(entry['start'])
        end = format_ass_time(entry['end'])
        duration = entry['duration']

        # KTV 逐字高亮
        ktv_text = generate_ktv_override(duration, entry['text'])

        lines.append(
            f"Dialogue: 0,{start},{end},KTV,,0,0,0,,{ktv_text}"
        )

    return '\n'.join(lines) + '\n'


def main():
    parser = argparse.ArgumentParser(
        description='SRT 转 ASS 字幕（支持 KTV 逐字高亮）'
    )
    parser.add_argument('srt_file', help='输入 SRT 文件路径')
    parser.add_argument('--style', choices=['ktv', 'simple'], default='simple',
                        help='样式模式（默认 simple）')
    parser.add_argument('--font', default='Noto Sans CJK SC',
                        help='字体名称（默认 Noto Sans CJK SC）')
    parser.add_argument('--fontsize', type=int, default=48,
                        help='字体大小（默认 48）')
    parser.add_argument('--primary-color', default='#FFFFFF',
                        help='主文字颜色（默认 #FFFFFF 白色）')
    parser.add_argument('--secondary-color', default='#FFD700',
                        help='KTV 高亮颜色（默认 #FFD700 金色）')
    parser.add_argument('--outline-color', default='#000000',
                        help='描边颜色（默认 #000000 黑色）')
    parser.add_argument('--back-color', default='#80000000',
                        help='背景色（默认 #80000000 半透明黑）')
    parser.add_argument('--outline', type=int, default=3,
                        help='描边宽度（默认 3）')
    parser.add_argument('--shadow', type=int, default=1,
                        help='阴影深度（默认 1）')
    parser.add_argument('--margin-v', type=int, default=40,
                        help='底部边距（默认 40）')
    parser.add_argument('-o', '--output', help='输出 ASS 文件路径')

    args = parser.parse_args()

    if not os.path.exists(args.srt_file):
        print(f"错误：SRT 文件不存在: {args.srt_file}", file=sys.stderr)
        sys.exit(1)

    entries = parse_srt(args.srt_file)
    if not entries:
        print("错误：SRT 文件为空或格式不正确", file=sys.stderr)
        sys.exit(1)

    config = {
        'fontname': args.font,
        'fontsize': args.fontsize,
        'primary_color': args.primary_color,
        'secondary_color': args.secondary_color,
        'outline_color': args.outline_color,
        'back_color': args.back_color,
        'outline': args.outline,
        'shadow': args.shadow,
        'margin_l': 10,
        'margin_r': 10,
        'margin_v': args.margin_v,
    }

    if args.style == 'ktv':
        ass_content = srt_to_ass_ktv(entries, config)
    else:
        ass_content = srt_to_ass_simple(entries, config)

    # 输出
    output_path = args.output
    if not output_path:
        base = os.path.splitext(args.srt_file)[0]
        output_path = base + '.ass'

    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(ass_content)

    print(f"✅ ASS 字幕已生成: {output_path} (样式: {args.style}, 条目数: {len(entries)})",
          file=sys.stderr)


if __name__ == '__main__':
    main()
