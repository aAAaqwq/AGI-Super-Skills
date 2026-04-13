#!/usr/bin/env python3
"""
输出合并器 (Merge Output)
将歌词解析、场景分配、模型选择三个步骤的输出合并为最终 MV 分镜剧本。

输入: lyrics_parsed.json + scenes_assigned.json + models_selected.json
输出: mv_script.json + mv_script.md

用法:
  python3 merge-output.py --lyrics lyrics_parsed.json --scenes scenes_assigned.json --models models_selected.json
  python3 merge-output.py --all  # 使用默认文件名
"""

import argparse
import json
import os
from datetime import datetime
from typing import Dict, List


def merge_scripts(lyrics_path: str, scenes_path: str, models_path: str,
                  output_json: str = "mv_script.json",
                  output_md: str = "mv_script.md") -> dict:
    """
    合并三个步骤的输出为最终剧本
    """
    with open(lyrics_path, 'r', encoding='utf-8') as f:
        lyrics = json.load(f)
    with open(scenes_path, 'r', encoding='utf-8') as f:
        scenes = json.load(f)
    with open(models_path, 'r', encoding='utf-8') as f:
        models = json.load(f)

    # 合并
    merged_scenes = []
    model_map = {m["scene_id"]: m for m in models["models"]}

    for scene in scenes["scenes"]:
        sid = scene["scene_id"]
        model_info = model_map.get(sid, {})

        merged = {
            "scene_id": sid,
            "time_range": scene["time_range"],
            "section": scene.get("section", ""),
            "lyrics": scene["lyrics"],
            "emotion_score": scene["emotion_score"],
            "emotion_label": scene["emotion_label"],
            "scene_type": scene["scene_type"],
            "location": scene["location"],
            "camera_move": scene["camera_move"],
            "camera_description": scene.get("camera_description", ""),
            "visual_prompt": scene["visual_prompt"],
            "first_frame": scene["first_frame"],
            "last_frame": scene["last_frame"],
            "video_model": model_info.get("video_model", "kling-2"),
            "model_params": model_info.get("model_params", {}),
            "duration_seconds": scene["duration_seconds"],
            "beat_sync": scene["beat_sync"],
            "transition": scene["transition"],
            "continuity_note": scene.get("continuity_note", ""),
            "complexity": model_info.get("complexity", ""),
            "estimated_cost": model_info.get("estimated_cost", 0),
        }
        merged_scenes.append(merged)

    result = {
        "metadata": {
            "title": "MV 分镜剧本",
            "generated_at": datetime.now().isoformat(),
            "character": scenes["metadata"].get("character", "Chloe"),
            "style": scenes["metadata"].get("style", "ethereal"),
            "total_scenes": len(merged_scenes),
            "total_duration": sum(s["duration_seconds"] for s in merged_scenes),
            "total_estimated_cost": models["metadata"].get("total_estimated_cost", 0),
            "bpm": lyrics["metadata"]["bpm"],
            "budget_mode": models["metadata"].get("budget_mode", "balanced"),
        },
        "emotion_curve": lyrics.get("emotion_curve", []),
        "scenes": merged_scenes,
    }

    # 写 JSON
    with open(output_json, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    # 写 Markdown
    md_content = generate_markdown(result)
    with open(output_md, 'w', encoding='utf-8') as f:
        f.write(md_content)

    return result


def generate_markdown(data: dict) -> str:
    """生成可读的 Markdown 剧本"""
    lines = []
    meta = data["metadata"]

    lines.append(f"# 🎬 {meta['title']}")
    lines.append(f"")
    lines.append(f"| 属性 | 值 |")
    lines.append(f"|------|-----|")
    lines.append(f"| 歌手 | {meta['character']} |")
    lines.append(f"| 风格 | {meta['style']} |")
    lines.append(f"| BPM | {meta['bpm']} |")
    lines.append(f"| 总分镜数 | {meta['total_scenes']} |")
    lines.append(f"| 总时长 | {meta['total_duration']:.1f}s ({meta['total_duration']/60:.1f}min) |")
    lines.append(f"| 预估成本 | {meta['total_estimated_cost']:.1f} |")
    lines.append(f"| 生成时间 | {meta['generated_at'][:19]} |")
    lines.append(f"")
    lines.append(f"---")
    lines.append(f"")

    # 情绪曲线
    lines.append(f"## 📊 情绪曲线")
    lines.append(f"")
    lines.append(f"```")
    for scene in data["scenes"]:
        bar_len = int(scene["emotion_score"])
        bar = "█" * bar_len + "░" * (10 - bar_len)
        lines.append(f"  {scene['section']:15s} [{bar}] {scene['emotion_score']:.1f}")
    lines.append(f"```")
    lines.append(f"")
    lines.append(f"---")
    lines.append(f"")

    # 分镜详情
    lines.append(f"## 🎬 分镜详情")
    lines.append(f"")

    for scene in data["scenes"]:
        lines.append(f"### 🎬 Scene #{scene['scene_id']} — {scene['section']}")
        lines.append(f"")
        lines.append(f"| 项目 | 内容 |")
        lines.append(f"|------|------|")
        lines.append(f"| 时间 | `{scene['time_range']}` ({scene['duration_seconds']}s) |")
        lines.append(f"| 歌词 | {scene['lyrics']} |")
        lines.append(f"| 情绪 | **{scene['emotion_score']:.1f}** / 10 ({scene['emotion_label']}) |")
        lines.append(f"| 场景 | {scene['scene_type']} |")
        lines.append(f"| 运镜 | {scene['camera_move']} |")
        lines.append(f"| 模型 | `{scene['video_model']}` |")
        lines.append(f"| 复杂度 | {scene.get('complexity', 'N/A')} |")
        lines.append(f"| 转场 | {scene['transition']} |")
        lines.append(f"")

        lines.append(f"**🎬 首帧:**")
        lines.append(f"> {scene['first_frame']['description']}")
        lines.append(f"")

        lines.append(f"**🎬 尾帧:**")
        lines.append(f"> {scene['last_frame']['description']}")
        lines.append(f"")

        lines.append(f"**📝 Visual Prompt:**")
        lines.append(f"> {scene['visual_prompt']}")
        lines.append(f"")

        lines.append(f"**🎵 Beat Sync:** {scene['beat_sync']}")
        lines.append(f"")

        if scene.get('continuity_note'):
            lines.append(f"**🔗 连续性:** {scene['continuity_note']}")
            lines.append(f"")

        lines.append(f"---")
        lines.append(f"")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description='MV 剧本合并输出')
    parser.add_argument('--lyrics', default='lyrics_parsed.json', help='歌词解析 JSON')
    parser.add_argument('--scenes', default='scenes_assigned.json', help='场景分配 JSON')
    parser.add_argument('--models', default='models_selected.json', help='模型选择 JSON')
    parser.add_argument('--output-json', default='mv_script.json', help='输出 JSON')
    parser.add_argument('--output-md', default='mv_script.md', help='输出 Markdown')
    parser.add_argument('--all', action='store_true', help='使用默认文件名合并')

    args = parser.parse_args()

    result = merge_scripts(
        args.lyrics, args.scenes, args.models,
        args.output_json, args.output_md
    )

    print(f"✅ MV 剧本合并完成!")
    print(f"   JSON: {args.output_json}")
    print(f"   Markdown: {args.output_md}")
    print(f"   总分镜: {result['metadata']['total_scenes']}")
    print(f"   总时长: {result['metadata']['total_duration']:.1f}s")


if __name__ == '__main__':
    main()
