#!/usr/bin/env python3
"""
场景分配器 (Scene Assigner)
基于歌词解析结果 + 歌手角色卡，分配场景类型、运镜、首尾帧。

输入: lyrics_parsed.json + 角色卡 JSON
输出: scenes_assigned.json — 一组分镜指令

用法:
  python3 scene-assigner.py --parsed lyrics_parsed.json
  python3 scene-assigner.py --parsed lyrics_parsed.json --character chloe-card.json
  python3 scene-assigner.py --parsed lyrics_parsed.json --style ethereal
"""

import argparse
import json
import os
import sys
from typing import List, Dict, Optional

# ── Chloe 角色卡（默认） ───────────────────────────────────────

DEFAULT_CHARACTER = {
    "name": "Chloe",
    "age": 22,
    "mbti": "ENTJ",
    "vibe": "外表仙气内心铁肺",
    "visual": {
        "outfit": "白色蕾丝刺绣裙",
        "accessories": ["樱花发饰", "复古蕾丝折伞"],
        "color_palette": ["晨曦白", "落樱粉", "浅草绿"],
        "hair": "长直黑发，樱花发饰点缀",
        "makeup": "清透底妆，淡粉唇色，自然眉",
    },
    "voice": {
        "type": "略带沙哑清亮音色",
        "technique": "belting爆发力",
        "characteristic": "情感穿透",
    },
    "genre": "国风电子流行",
    "debut_song": "《樱花落尽时》",
}

# ── 场景库 ─────────────────────────────────────────────────────

SCENE_LIBRARY = {
    "溪畔樱花林": {
        "id": "sakura_stream",
        "description": "溪水潺潺，两岸樱花树，花瓣随风飘落",
        "light": "golden hour 早晨柔光",
        "color_temp": "3500-4500K",
        "palette": "晨曦白+落樱粉+浅草绿",
        "best_for": ["intro", "verse", "outro"],
        "emotion_range": [2, 5],
        "camera_moves": ["slow push-in", "slow pan left", "static with falling petals"],
    },
    "月下庭院": {
        "id": "moonlit_garden",
        "description": "日式庭院，石灯笼，月光洒落，苔藓石板",
        "light": "月光 + 花灯暖光",
        "color_temp": "月白+暖黄",
        "palette": "月白+暖黄+墨蓝",
        "best_for": ["chorus", "bridge"],
        "emotion_range": [5, 8],
        "camera_moves": ["orbiting shot", "slow tilt up", "tracking follow"],
    },
    "雨巷": {
        "id": "rainy_alley",
        "description": "青石板路，两侧矮墙，雨丝如帘，水洼倒影",
        "light": "阴天散射光 + 远处暖窗光",
        "color_temp": "灰蓝+暖橙",
        "palette": "灰蓝+暖橙+白",
        "best_for": ["pre_chorus", "bridge"],
        "emotion_range": [4, 7],
        "camera_moves": ["tracking follow", "dolly backward", "slow push-in"],
    },
    "晨雾溪畔": {
        "id": "misty_stream",
        "description": "薄雾笼罩的溪水，若隐若现，梦幻朦胧",
        "light": "黎明前柔光，光线穿透雾气",
        "color_temp": "灰白+淡金+浅蓝",
        "palette": "灰白+淡金+浅蓝",
        "best_for": ["intro", "outro"],
        "emotion_range": [0, 3],
        "camera_moves": ["slow aerial forward", "static wide", "gentle drift"],
    },
    "山顶远眺": {
        "id": "mountain_peak",
        "description": "悬崖边，远景山脉，云海翻涌，壮阔天空",
        "light": "日出/日落 golden hour",
        "color_temp": "暖金+深蓝+橙红",
        "palette": "暖金+深蓝+橙红",
        "best_for": ["final_chorus"],
        "emotion_range": [8, 10],
        "camera_moves": ["crane up reveal", "slow push-in to silhouette", "360 orbit"],
    },
    "窗前光影": {
        "id": "window_light",
        "description": "和室窗户，光影投射在木质地板上，花瓣贴在玻璃",
        "light": "斜射阳光，窗花投下阴影",
        "color_temp": "暖白+木色+影灰",
        "palette": "暖白+木色+影灰",
        "best_for": ["verse"],
        "emotion_range": [3, 5],
        "camera_moves": ["static with light movement", "slow pan right", "push-in to face"],
    },
    "星空下": {
        "id": "starry_night",
        "description": "开阔地带，银河横跨夜空，萤火虫环绕",
        "light": "星光 + 萤火虫暖光",
        "color_temp": "深蓝+银白+暖黄",
        "palette": "深蓝+银白+暖黄",
        "best_for": ["final_chorus", "chorus"],
        "emotion_range": [7, 10],
        "camera_moves": ["tilt up to sky", "slow orbit", "crane up from ground"],
    },
    "碎裂空间": {
        "id": "shattered_space",
        "description": "超现实空间，镜面碎片飘浮，花瓣化作光点",
        "light": "多方向散射光，棱镜折射",
        "color_temp": "全光谱",
        "palette": "彩虹光斑+白+深空蓝",
        "best_for": ["bridge", "final_chorus"],
        "emotion_range": [8, 10],
        "camera_moves": ["fast push-pull", "handheld", "whip pan"],
    },
}

# ── 情绪→运镜映射 ─────────────────────────────────────────────

EMOTION_CAMERA_MAP = {
    (0, 2): ["static", "slow drift", "gentle aerial"],
    (2, 4): ["slow push-in", "slow pan", "static with element movement"],
    (4, 6): ["tracking follow", "slow dolly", "tilt up"],
    (6, 8): ["push-pull", "orbit", "tracking with speed variation"],
    (8, 10): ["fast push-in", "crane up", "handheld dynamic", "multi-axis move"],
}

# ── 转场映射 ───────────────────────────────────────────────────

TRANSITION_MAP = {
    (0, 3): "slow dissolve",
    (3, 5): "crossfade",
    (5, 7): "match cut with element",
    (7, 9): "hard cut on beat",
    (9, 11): "flash white + hard cut",
}


def get_camera_for_emotion(emotion: float) -> str:
    """根据情绪分数选择运镜"""
    for (lo, hi), moves in EMOTION_CAMERA_MAP.items():
        if lo <= emotion < hi:
            return moves[min(0, len(moves) - 1)]
    return "static"


def get_transition(emotion: float, next_emotion: Optional[float] = None) -> str:
    """根据情绪选择转场"""
    if next_emotion is not None and abs(next_emotion - emotion) > 3:
        return "flash white + hard cut"

    for (lo, hi), transition in TRANSITION_MAP.items():
        if lo <= emotion < hi:
            return transition
    return "dissolve"


def select_scene(section_type: str, emotion: float) -> Dict:
    """根据段落类型和情绪分数选择场景"""
    candidates = []
    for name, scene in SCENE_LIBRARY.items():
        score = 0
        # 段落匹配
        if section_type in scene["best_for"]:
            score += 5
        if section_type == "final_chorus" and section_type in scene["best_for"]:
            score += 3
        # 情绪匹配
        emo_lo, emo_hi = scene["emotion_range"]
        if emo_lo <= emotion <= emo_hi:
            score += 3
        elif abs(emotion - (emo_lo + emo_hi) / 2) < 2:
            score += 1
        candidates.append((score, name, scene))

    candidates.sort(key=lambda x: x[0], reverse=True)
    if candidates:
        _, name, scene = candidates[0]
        return {"name": name, **scene}
    return {"name": "溪畔樱花林", **SCENE_LIBRARY["溪畔樱花林"]}


def build_visual_prompt(scene: Dict, character: Dict, emotion: float,
                        shot_type: str = "medium") -> str:
    """
    构建完整的视觉 prompt
    """
    char_vis = character.get("visual", {})
    outfit = char_vis.get("outfit", "white lace dress")
    accessories = ", ".join(char_vis.get("accessories", []))
    hair = char_vis.get("hair", "long straight black hair")

    shot_descriptions = {
        "wide": "wide establishing shot",
        "full": "full body shot",
        "medium": "medium shot waist up",
        "close": "close-up portrait",
        "extreme_close": "extreme close-up",
    }

    prompt_parts = [
        shot_descriptions.get(shot_type, "cinematic shot"),
        f"ethereal 22-year-old Asian young woman in {outfit}",
        f"with {accessories}" if accessories else "",
        hair,
        f"in {scene.get('description', 'beautiful setting')}",
        scene.get("light", "natural light"),
        f"{scene.get('palette', '')} color palette",
        "cinematic composition, professional photography",
        "8k quality, highly detailed",
    ]

    if emotion >= 7:
        prompt_parts.append("dramatic intensity, powerful expression")
    elif emotion >= 5:
        prompt_parts.append("emotional depth, expressive")
    elif emotion >= 3:
        prompt_parts.append("serene, gentle atmosphere")
    else:
        prompt_parts.append("ethereal, dreamlike quality")

    return ", ".join(p for p in prompt_parts if p)


def determine_shot_type(section_type: str, emotion: float, position: str = "mid") -> str:
    """根据段落类型、情绪、位置决定景别"""
    if section_type == "intro" and position == "start":
        return "wide"
    elif section_type == "outro" and position == "end":
        return "wide"
    elif emotion >= 8:
        return "close"
    elif emotion >= 6:
        return "medium"
    elif section_type == "verse":
        return "full"
    else:
        return "medium"


def assign_scenes(parsed_data: dict, character: dict = None,
                  style: str = "ethereal") -> List[Dict]:
    """
    主分配函数：基于歌词解析结果分配场景

    Args:
        parsed_data: lyrics-parser.py 的输出
        character: 角色卡
        style: 视觉风格

    Returns:
        分镜列表
    """
    if character is None:
        character = DEFAULT_CHARACTER

    sections = parsed_data.get("sections", [])
    scenes = []
    scene_id = 1

    for i, section in enumerate(sections):
        section_type = section["section_type"]
        emotion = section["emotion_score"]
        lines = section.get("lines", [])
        duration = section.get("duration_seconds", 15)

        # 选择场景
        scene_info = select_scene(section_type, emotion)

        # 确定运镜
        camera_move = get_camera_for_emotion(emotion)
        # 如果场景有推荐运镜，优先使用
        if scene_info.get("camera_moves"):
            camera_move = scene_info["camera_moves"][0]

        # 确定景别
        shot_type = determine_shot_type(section_type, emotion, "start")
        shot_type_end = determine_shot_type(section_type, emotion, "end")

        # 合并歌词文本
        lyrics_text = " / ".join(l["text"] for l in lines) if lines else "（纯音乐）"

        # 构建视觉 prompt
        visual_prompt = build_visual_prompt(scene_info, character, emotion, shot_type)

        # 构建首帧
        first_frame = {
            "description": f"{shot_type}：{scene_info['description']}，"
                          f"{character['name']}静立其中，"
                          f"{scene_info['light']}，画面色调{scene_info['palette']}",
            "gemini_composite": True,
            "composition": "三分法构图" if emotion < 6 else "中心构图",
            "continuity_from": "承接上一分镜的视觉元素" if scene_id > 1 else "故事开场",
        }

        # 构建尾帧（为下一分镜铺路）
        next_section = sections[i + 1] if i + 1 < len(sections) else None
        transition_hint = ""
        if next_section:
            next_emotion = next_section["emotion_score"]
            if next_emotion > emotion + 2:
                transition_hint = "光线开始变化，情绪渐强，为爆发铺垫"
            elif next_emotion < emotion - 2:
                transition_hint = "动态元素减缓，画面归于宁静"
            else:
                transition_hint = "花瓣/雾气等动态元素持续流动"

        last_frame = {
            "description": f"{shot_type_end}：{scene_info['description']}，"
                          f"{character['name']}特写，"
                          f"{transition_hint}",
            "gemini_composite": True,
            "composition": "偏侧构图，留出视觉引导空间",
            "leads_to": transition_hint,
        }

        # 转场
        next_emotion = next_section["emotion_score"] if next_section else None
        transition = get_transition(emotion, next_emotion)

        # beat_sync 标注
        beat_sync_map = {
            "intro": "前奏起点，节奏舒缓",
            "verse": "主歌进入，平稳叙事",
            "pre_chorus": "情绪铺垫，节奏渐强",
            "chorus": "副歌起点，★ 卡点爆发",
            "bridge": "桥段转折，反差设计",
            "outro": "情绪收束，余韵悠长",
        }

        scene_obj = {
            "scene_id": scene_id,
            "time_range": section["time_range"],
            "section": section["section_label"],
            "lyrics": lyrics_text,
            "emotion_score": emotion,
            "emotion_label": section["emotion_label"],
            "scene_type": scene_info["name"],
            "location": scene_info["description"],
            "camera_move": camera_move,
            "camera_description": f"{'缓慢' if emotion < 5 else '快速' if emotion > 7 else '平稳'}{camera_move}",
            "visual_prompt": visual_prompt,
            "first_frame": first_frame,
            "last_frame": last_frame,
            "duration_seconds": duration,
            "beat_sync": beat_sync_map.get(section_type, ""),
            "transition": transition,
            "continuity_note": last_frame.get("leads_to", ""),
        }

        scenes.append(scene_obj)
        scene_id += 1

    return scenes


def main():
    parser = argparse.ArgumentParser(description='场景分配器 - 基于歌词情绪分配 MV 场景')
    parser.add_argument('--parsed', type=str, required=True, help='歌词解析结果 JSON 路径')
    parser.add_argument('--character', type=str, default=None, help='角色卡 JSON 路径')
    parser.add_argument('--style', type=str, default='ethereal',
                       choices=['cinematic', 'ethereal', 'anime', 'realistic'],
                       help='视觉风格')
    parser.add_argument('--output', type=str, default='scenes_assigned.json', help='输出文件路径')

    args = parser.parse_args()

    # 加载歌词解析结果
    with open(args.parsed, 'r', encoding='utf-8') as f:
        parsed_data = json.load(f)

    # 加载角色卡
    character = DEFAULT_CHARACTER
    if args.character and os.path.exists(args.character):
        with open(args.character, 'r', encoding='utf-8') as f:
            character = json.load(f)

    # 分配场景
    scenes = assign_scenes(parsed_data, character, args.style)

    # 输出
    result = {
        "metadata": {
            "character": character.get("name", "Chloe"),
            "style": args.style,
            "total_scenes": len(scenes),
            "total_duration": sum(s["duration_seconds"] for s in scenes),
            "source_file": args.parsed,
        },
        "scenes": scenes,
    }

    with open(args.output, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"✅ 场景分配完成")
    print(f"   角色: {character.get('name', 'Chloe')}")
    print(f"   风格: {args.style}")
    print(f"   分镜数: {len(scenes)}")
    print(f"   总时长: {sum(s['duration_seconds'] for s in scenes):.1f}s")
    print(f"   输出: {args.output}")

    # 打印分镜摘要
    print("\n🎬 分镜列表:")
    for s in scenes:
        print(f"  #{s['scene_id']:2d} │ {s['time_range']:13s} │ "
              f"情绪{s['emotion_score']:.1f} │ {s['scene_type']:10s} │ "
              f"{s['camera_move']:20s} │ {s['section']}")

    return result


if __name__ == '__main__':
    main()
