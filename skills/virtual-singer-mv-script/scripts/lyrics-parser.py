#!/usr/bin/env python3
"""
歌词解析器 (Lyrics Parser)
将歌词文本解析为结构化时间轴，包含情绪曲线、段落识别、BPM 建议。

输入: 歌词文本（纯文本或 LRC 格式）
输出: JSON 格式的解析结果

用法:
  python3 lyrics-parser.py --lyrics "歌词文本"
  python3 lyrics-parser.py --file lyrics.txt
  python3 lyrics-parser.py --file lyrics.txt --bpm 95
"""

import argparse
import json
import re
import sys
from dataclasses import dataclass, field, asdict
from typing import List, Optional


# ── 情绪关键词词典 ──────────────────────────────────────────────

EMOTION_KEYWORDS = {
    # 高情绪（爆发/力量） 7-10
    "high": {
        "燃烧": 9, "怒放": 9, "咆哮": 10, "撕裂": 9, "爆发": 9,
        "铁了心": 8, "站在这里": 8, "等你回头": 8, "不认输": 9,
        "冲破": 9, "绽放": 8, "烈": 8, "火": 7, "雷": 8,
        "哭": 7, "痛": 8, "碎": 8, "断": 7, "裂": 8,
        "永远": 7, "绝不": 9, "最后": 7,
    },
    # 中情绪（铺垫/期待） 5-7
    "mid": {
        "渐": 6, "远": 6, "独": 6, "忆": 6, "空": 5,
        "等": 6, "望": 5, "叹": 6, "念": 6, "思": 6,
        "别": 6, "离": 6, "走": 5, "去": 5, "散": 6,
        "暗": 5, "落": 6, "凋": 6, "零": 5, "暮": 6,
        "雨": 5, "雾": 5, "影": 5, "回": 6, "逝": 6,
    },
    "low": {
        "晨曦": 3, "柔": 3, "静": 2, "梦": 3, "花": 4,
        "飘": 3, "风": 3, "光": 4, "暖": 4, "笑": 4,
        "美": 4, "轻": 2, "淡": 3, "白": 3, "溪": 3,
        "新": 4, "生": 4, "晴": 4, "阳": 4, "月": 3,
        "瓣": 3, "泉": 3, "露": 3, "芽": 4, "初": 3,
    },
}


@dataclass
class LyricLine:
    """单行歌词"""
    text: str
    time_start: float = 0.0  # 秒
    time_end: float = 0.0
    emotion_score: float = 0.0
    emotion_label: str = ""


@dataclass
class Section:
    """歌曲段落"""
    section_type: str  # intro, verse, pre_chorus, chorus, bridge, outro
    section_label: str  # 如 "Verse 1", "Chorus 2"
    time_start: float = 0.0
    time_end: float = 0.0
    emotion_score: float = 0.0
    emotion_label: str = ""
    lines: List[LyricLine] = field(default_factory=list)
    bpm_suggestion: float = 0.0


def calculate_line_emotion(text: str) -> float:
    """计算单行歌词的情绪分数 (0-10)"""
    score = 3.0  # 基线
    count = 0

    for category, keywords in EMOTION_KEYWORDS.items():
        for keyword, weight in keywords.items():
            if keyword in text:
                score += weight
                count += 1

    if count > 0:
        score = score / (count + 1) * 2  # 加权平均

    return max(0.0, min(10.0, score))


def get_emotion_label(score: float) -> str:
    """将情绪分数转为标签"""
    if score <= 2:
        return "极静/空灵"
    elif score <= 4:
        return "平静/温柔"
    elif score <= 5.5:
        return "微伤/怀念"
    elif score <= 7:
        return "铺垫/渐强"
    elif score <= 8.5:
        return "爆发/力量"
    else:
        return "极致/巅峰"


def parse_lrc_timestamps(text: str) -> List[tuple]:
    """解析 LRC 格式时间轴"""
    pattern = r'\[(\d{2}):(\d{2})\.?(\d{0,3})\](.*)'
    lines = []
    for match in re.finditer(pattern, text):
        minutes = int(match.group(1))
        seconds = int(match.group(2))
        ms = match.group(3)
        ms_val = int(ms.ljust(3, '0')[:3]) if ms else 0
        timestamp = minutes * 60 + seconds + ms_val / 1000
        lyric = match.group(4).strip()
        if lyric:
            lines.append((timestamp, lyric))
    return lines


def identify_sections(lines: List[str]) -> List[tuple]:
    """
    识别歌曲段落结构
    返回: [(段落类型, 段落标签, 行索引范围), ...]
    """
    section_markers = {
        'intro': ['intro', '前奏', '间奏前'],
        'verse': ['verse', '主歌', 'v1', 'v2'],
        'pre_chorus': ['pre-chorus', 'prechorus', '预副歌', 'pre-ch'],
        'chorus': ['chorus', '副歌', 'c1', 'c2', 'refrain'],
        'bridge': ['bridge', '桥段', '过渡'],
        'outro': ['outro', '尾奏', '结束'],
    }

    sections = []
    current_type = "intro"
    current_label = "Intro"
    section_start = 0
    section_counters = {}

    for i, line in enumerate(lines):
        line_lower = line.lower().strip()
        if not line_lower:
            continue

        detected = False
        for stype, markers in section_markers.items():
            for marker in markers:
                if line_lower.startswith(marker) or line_lower.startswith(f'[{marker}'):
                    # Save previous section
                    if i > section_start:
                        sections.append((current_type, current_label, section_start, i))

                    section_counters[stype] = section_counters.get(stype, 0) + 1
                    current_type = stype
                    label_map = {
                        'intro': 'Intro',
                        'verse': f'Verse {section_counters.get("verse", 1)}',
                        'pre_chorus': 'Pre-Chorus',
                        'chorus': f'Chorus {section_counters.get("chorus", 1)}',
                        'bridge': 'Bridge',
                        'outro': 'Outro',
                    }
                    current_label = label_map.get(stype, stype)
                    section_start = i + 1
                    detected = True
                    break
            if detected:
                break

    # Don't forget the last section
    if section_start < len(lines):
        sections.append((current_type, current_label, section_start, len(lines)))

    return sections


def auto_assign_timeline(lyrics_lines: List[str], bpm: float = 95.0,
                         total_duration: float = 210.0) -> List[LyricLine]:
    """
    为没有时间轴的歌词自动分配时间线
    
    Args:
        lyrics_lines: 歌词行列表（不含段落标记）
        bpm: BPM
        total_duration: 总时长（秒）
    """
    beat_duration = 60.0 / bpm  # 每拍时长
    bar_duration = beat_duration * 4  # 每小节时长

    # 过滤空行和段落标记
    clean_lines = []
    for line in lyrics_lines:
        stripped = line.strip()
        if stripped and not stripped.startswith('[') and not any(
            stripped.lower().startswith(m) for m in
            ['intro', 'verse', 'pre', 'chorus', 'bridge', 'outro', '前奏', '主歌', '预副歌', '副歌', '桥段', '尾奏']
        ):
            clean_lines.append(stripped)

    if not clean_lines:
        return []

    # 按段落分配时长
    # Intro: ~15s, Verse: ~30s, Pre-Chorus: ~15s, Chorus: ~30s
    # Bridge: ~15s, Outro: ~15s
    section_durations = {
        'intro': 15,
        'verse': 30,
        'pre_chorus': 15,
        'chorus': 30,
        'bridge': 15,
        'outro': 15,
    }

    # 简单策略：每行歌词分配 2-4 拍（根据行长）
    result = []
    current_time = 0.0

    for line_text in clean_lines:
        # 根据行长决定时长
        char_count = len(line_text)
        if char_count <= 5:
            line_duration = bar_duration * 0.5  # 短句
        elif char_count <= 10:
            line_duration = bar_duration * 0.75
        elif char_count <= 15:
            line_duration = bar_duration * 1.0
        else:
            line_duration = bar_duration * 1.25

        emotion = calculate_line_emotion(line_text)

        ll = LyricLine(
            text=line_text,
            time_start=round(current_time, 2),
            time_end=round(current_time + line_duration, 2),
            emotion_score=round(emotion, 1),
            emotion_label=get_emotion_label(emotion),
        )
        result.append(ll)
        current_time += line_duration

    return result


def parse_lyrics(text: str, bpm: float = 95.0, total_duration: float = 210.0) -> dict:
    """
    主解析函数

    Args:
        text: 歌词文本
        bpm: BPM（默认 95）
        total_duration: 总时长（秒）

    Returns:
        解析结果 dict
    """
    lines = text.strip().split('\n')

    # 尝试解析 LRC 时间轴
    lrc_lines = parse_lrc_timestamps(text)

    if lrc_lines:
        # 有 LRC 时间轴
        parsed_lines = []
        for i, (ts, lyric) in enumerate(lrc_lines):
            next_ts = lrc_lines[i + 1][0] if i + 1 < len(lrc_lines) else total_duration
            emotion = calculate_line_emotion(lyric)
            parsed_lines.append(LyricLine(
                text=lyric,
                time_start=round(ts, 2),
                time_end=round(next_ts, 2),
                emotion_score=round(emotion, 1),
                emotion_label=get_emotion_label(emotion),
            ))
    else:
        # 无时间轴，自动分配
        parsed_lines = auto_assign_timeline(lines, bpm, total_duration)

    # 识别段落结构
    sections_raw = identify_sections(lines)

    if not sections_raw:
        # 无法识别段落标记，按行数均匀分割
        total_lines = len(parsed_lines)
        if total_lines == 0:
            sections_raw = [
                ('intro', 'Intro', 0, 0),
                ('verse', 'Verse 1', 0, max(1, total_lines // 3)),
                ('chorus', 'Chorus 1', total_lines // 3, 2 * total_lines // 3),
                ('outro', 'Outro', 2 * total_lines // 3, total_lines),
            ]
        else:
            sections_raw = [
                ('intro', 'Intro', 0, max(1, total_lines // 6)),
                ('verse', 'Verse 1', total_lines // 6, total_lines // 3),
                ('pre_chorus', 'Pre-Chorus', total_lines // 3, total_lines // 2),
                ('chorus', 'Chorus 1', total_lines // 2, 2 * total_lines // 3),
                ('verse', 'Verse 2', 2 * total_lines // 3, 5 * total_lines // 6),
                ('chorus', 'Chorus 2', 5 * total_lines // 6, total_lines),
            ]

    # 构建段落
    sections = []
    for stype, slabel, start_idx, end_idx in sections_raw:
        section_lines = parsed_lines[start_idx:end_idx] if start_idx < len(parsed_lines) else []

        if section_lines:
            avg_emotion = sum(l.emotion_score for l in section_lines) / len(section_lines) if section_lines else 3.0
            time_start = section_lines[0].time_start
            time_end = section_lines[-1].time_end
        else:
            avg_emotion = 3.0
            time_start = 0.0
            time_end = 0.0

        # 段落情绪修正
        emotion_modifiers = {
            'intro': -1,
            'verse': 0,
            'pre_chorus': +1.5,
            'chorus': +3,
            'bridge': -1,
            'outro': -2,
        }
        modified_emotion = avg_emotion + emotion_modifiers.get(stype, 0)
        modified_emotion = max(0.0, min(10.0, modified_emotion))

        sections.append(Section(
            section_type=stype,
            section_label=slabel,
            time_start=round(time_start, 2),
            time_end=round(time_end, 2),
            emotion_score=round(modified_emotion, 1),
            emotion_label=get_emotion_label(modified_emotion),
            lines=section_lines,
            bpm_suggestion=bpm,
        ))

    # 计算全局情绪曲线
    emotion_curve = []
    for s in sections:
        for l in s.lines:
            emotion_curve.append({
                "time": l.time_start,
                "emotion_score": l.emotion_score,
                "section": s.section_label,
                "lyrics": l.text,
            })

    # BPM 建议
    bpm_suggestions = {
        "ballad": {"range": "60-80", "reason": "抒情慢板，适合温柔叙事"},
        "mid_tempo": {"range": "80-110", "reason": "中板流行，适合叙事+爆发的平衡"},
        "electronic": {"range": "110-130", "reason": "电子节拍，适合节奏感强的段落"},
    }

    result = {
        "metadata": {
            "total_duration": round(total_duration, 1),
            "bpm": bpm,
            "bpm_suggestion": "mid_tempo" if 80 <= bpm <= 110 else "ballad" if bpm < 80 else "electronic",
            "total_sections": len(sections),
            "total_lines": len(parsed_lines),
        },
        "sections": [
            {
                "section_type": s.section_type,
                "section_label": s.section_label,
                "time_range": f"{format_time(s.time_start)}-{format_time(s.time_end)}",
                "time_start": s.time_start,
                "time_end": s.time_end,
                "duration_seconds": round(s.time_end - s.time_start, 1),
                "emotion_score": s.emotion_score,
                "emotion_label": s.emotion_label,
                "bpm_suggestion": s.bpm_suggestion,
                "lines": [
                    {
                        "text": l.text,
                        "time_start": l.time_start,
                        "time_end": l.time_end,
                        "emotion_score": l.emotion_score,
                        "emotion_label": l.emotion_label,
                    }
                    for l in s.lines
                ],
            }
            for s in sections
        ],
        "emotion_curve": emotion_curve,
    }

    return result


def format_time(seconds: float) -> str:
    """格式化秒数为 MM:SS"""
    m = int(seconds) // 60
    s = int(seconds) % 60
    return f"{m:02d}:{s:02d}"


def main():
    parser = argparse.ArgumentParser(description='歌词解析器 - 将歌词文本解析为结构化时间轴')
    parser.add_argument('--lyrics', type=str, help='歌词文本（直接传入）')
    parser.add_argument('--file', type=str, help='歌词文件路径')
    parser.add_argument('--bpm', type=float, default=95.0, help='BPM（默认 95）')
    parser.add_argument('--duration', type=float, default=210.0, help='总时长秒数（默认 210）')
    parser.add_argument('--output', type=str, default='lyrics_parsed.json', help='输出文件路径')

    args = parser.parse_args()

    if args.file:
        with open(args.file, 'r', encoding='utf-8') as f:
            text = f.read()
    elif args.lyrics:
        text = args.lyrics
    else:
        # 默认示例：《樱花落尽时》
        text = """
Intro (0:00-0:15)
（纯音乐前奏，古筝与电子合成器交织）

Verse 1 (0:15-0:45)
晨曦洒落在溪畔
樱花瓣随风飘散
你说的永远太短暂
像花开一瞬就凋零

Pre-Chorus (0:45-1:00)
我不哭不代表不痛
只是笑着看你远走
风中的承诺太轻
我用手心握紧

Chorus 1 (1:00-1:30)
樱花落尽时我在等你
哪怕世界都凋零
铁了心要站在这里
等你回头看我一眼
就算花瓣化成泥
我也不会忘记

Verse 2 (1:30-2:00)
月色洒满了庭院
石灯笼映着你侧脸
那些说好的永远
碎在风里看不见

Pre-Chorus 2 (2:00-2:15)
我不哭不代表不痛
只是笑着看你远走
雨中的背影太远
我用心跳去追

Chorus 2 (2:15-2:30)
樱花落尽时我在等你
哪怕世界都凋零
铁了心要站在这里
等你回头看我一眼
就算花瓣化成泥
我也不会忘记

Bridge (2:30-2:45)
当最后一片花瓣落下
我会用双手接住它
那些碎掉的梦啊
我来一片片拼回去

Final Chorus (2:45-3:15)
樱花落尽时我在等你
哪怕世界都凋零
铁了心要站在这里
燃烧自己也要照亮你
就算花瓣化成泥
来年春天我还在这里

Outro (3:15-3:30)
（音乐渐弱，樱花瓣缓缓飘落）
"""

    result = parse_lyrics(text, args.bpm, args.duration)

    # 输出
    output_path = args.output
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"✅ 歌词解析完成")
    print(f"   总时长: {result['metadata']['total_duration']}s")
    print(f"   BPM: {result['metadata']['bpm']}")
    print(f"   段落数: {result['metadata']['total_sections']}")
    print(f"   歌词行: {result['metadata']['total_lines']}")
    print(f"   输出: {output_path}")

    # 打印情绪曲线摘要
    print("\n📊 情绪曲线:")
    for section in result['sections']:
        bar_len = int(section['emotion_score'])
        bar = "█" * bar_len + "░" * (10 - bar_len)
        print(f"  {section['section_label']:15s} [{bar}] {section['emotion_score']:.1f}  {section['emotion_label']}")

    return result


if __name__ == '__main__':
    main()
