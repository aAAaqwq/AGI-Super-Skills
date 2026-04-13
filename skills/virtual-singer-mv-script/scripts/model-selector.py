#!/usr/bin/env python3
"""
model-selector.py — 视频生成模型选择器
根据场景复杂度、运镜需求、时长，推荐最佳视频生成模型
"""

import json
import sys
import argparse
from pathlib import Path

# ============================================================
# 视频模型池
# ============================================================
VIDEO_MODELS = {
    "kling-2": {
        "provider": "kling",
        "strengths": ["高度动态", "人物动作自然", "长镜头能力强"],
        "max_duration": 20,
        "aspect_ratios": ["16:9", "9:16", "1:1"],
        "cost_tier": "premium",
        "best_for": ["舞蹈/运动", "复杂运镜", "长镜头叙事"],
        "min_duration": 5,
    },
    "kling-1.6": {
        "provider": "kling",
        "strengths": ["性价比高", "人物稳定", "日常场景优秀"],
        "max_duration": 15,
        "aspect_ratios": ["16:9", "9:16", "1:1"],
        "cost_tier": "standard",
        "best_for": ["日常场景", "对话", "慢镜头"],
        "min_duration": 5,
    },
    "veo-3": {
        "provider": "google",
        "strengths": ["物理真实感强", "光影优秀", "场景融合自然"],
        "max_duration": 10,
        "aspect_ratios": ["16:9", "1:1"],
        "cost_tier": "premium",
        "best_for": ["自然场景", "真实感人像", "复杂光影"],
        "min_duration": 4,
    },
    "veo-3.1": {
        "provider": "google",
        "strengths": ["veo-3增强版", "更高一致性", "更长生成"],
        "max_duration": 15,
        "aspect_ratios": ["16:9", "9:16", "1:1"],
        "cost_tier": "premium",
        "best_for": ["MV级别制作", "高一致性要求", "复杂转场"],
        "min_duration": 5,
    },
    "sora-2": {
        "provider": "openai",
        "strengths": ["想象力丰富", "风格多样", "概念理解强"],
        "max_duration": 20,
        "aspect_ratios": ["16:9", "9:16", "1:1"],
        "cost_tier": "premium",
        "best_for": ["梦幻场景", "抽象概念", "创意转场"],
        "min_duration": 5,
    },
    "seedance-3.0": {
        "provider": "bytedance",
        "strengths": ["国风/古风优化", "亚洲面孔优秀", "色彩鲜艳"],
        "max_duration": 10,
        "aspect_ratios": ["16:9", "9:16"],
        "cost_tier": "standard",
        "best_for": ["国风场景", "亚洲人物", "色彩丰富画面"],
        "min_duration": 4,
    },
}

# ============================================================
# 场景复杂度评分
# ============================================================
def calc_complexity(scene_data):
    """计算场景复杂度 (1-10)"""
    score = 1
    reasons = []

    # 静态场景
    if scene_data.get("camera_move") in ["static", "none", ""]:
        score += 0
        reasons.append("静态镜头")
    elif scene_data.get("camera_move") in ["slow push-in", "slow pull-out"]:
        score += 1
        reasons.append("简单运镜")
    elif scene_data.get("camera_move") in ["pan left", "pan right", "tilt up", "tilt down"]:
        score += 2
        reasons.append("平移/倾斜运镜")
    elif scene_data.get("camera_move") in ["dolly in", "dolly out", "tracking shot"]:
        score += 3
        reasons.append("移动摄影")
    elif scene_data.get("camera_move") in ["crane shot", "aerial", "drone shot"]:
        score += 4
        reasons.append("航拍/起重机镜头")
    else:
        score += 2

    # 情绪强度
    emotion = float(scene_data.get("emotion_score", 5))
    if emotion >= 8:
        score += 2
        reasons.append("高情绪强度")
    elif emotion >= 6:
        score += 1
        reasons.append("中高情绪")

    # 特效需求
    if scene_data.get("needs_effects"):
        score += 2
        reasons.append("需要特效")

    # 人物数量
    characters = scene_data.get("character_count", 1)
    if characters >= 3:
        score += 2
        reasons.append("多人物")
    elif characters >= 2:
        score += 1
        reasons.append("双人场景")

    return min(score, 10), reasons


# ============================================================
# 模型推荐核心
# ============================================================
def recommend_model(scene_data, available_budget="standard"):
    """
    根据场景数据和预算推荐最佳模型
    """
    complexity, reasons = calc_complexity(scene_data)
    duration = int(scene_data.get("duration_seconds", 10))
    scene_type = scene_data.get("scene_type", "")
    camera = scene_data.get("camera_move", "")

    candidates = []

    for model_id, model_info in VIDEO_MODELS.items():
        # 检查时长限制
        if duration < model_info["min_duration"]:
            continue
        if duration > model_info["max_duration"]:
            continue

        # 检查预算限制
        if available_budget == "economy" and model_info["cost_tier"] == "premium":
            continue

        # 计算匹配度
        score = 0

        # 复杂度匹配
        if complexity >= 7 and model_info["cost_tier"] == "premium":
            score += 3
        elif complexity <= 3:
            score += 2

        # 场景类型匹配
        scene_lower = scene_type.lower()
        if "樱花" in scene_type or "自然" in scene_type or "花园" in scene_type:
            if "自然场景" in model_info["best_for"]:
                score += 2
            if "国风" in model_info["best_for"] or "亚洲面孔" in str(model_info["best_for"]):
                score += 1

        if "舞蹈" in scene_type or "运动" in scene_type or "爆发" in scene_type:
            if "舞蹈/运动" in model_info["best_for"]:
                score += 3

        if "夜景" in scene_type or "月光" in scene_type:
            if "复杂光影" in model_info["best_for"]:
                score += 2

        # Chloe 虚拟歌手专项加成
        if "仙气" in scene_type or "唯美" in scene_type:
            if "想象力丰富" in model_info["strengths"]:
                score += 2
            if "国风/古风优化" in model_info["strengths"]:
                score += 1

        candidates.append((model_id, score, model_info))

    if not candidates:
        # fallback 到 kling-1.6
        return {
            "model": "kling-1.6",
            "reason": "默认选择（无合适模型时兜底）",
            "complexity": complexity,
            "complexity_reasons": reasons,
            "parameters": {
                "duration": duration,
                "aspect_ratio": "16:9",
                "fps": 30,
                "prompt": build_video_prompt(scene_data),
            }
        }

    # 排序返回最佳
    candidates.sort(key=lambda x: x[1], reverse=True)
    best_id, best_score, best_info = candidates[0]

    # 构建推荐结果
    result = {
        "model": best_id,
        "provider": best_info["provider"],
        "match_score": best_score,
        "reason": f"场景复杂度 {complexity}/10，{' + '.join(reasons)} → {best_info['strengths'][0]}",
        "complexity": complexity,
        "complexity_reasons": reasons,
        "parameters": {
            "duration": duration,
            "aspect_ratio": recommend_aspect_ratio(scene_type),
            "fps": 30,
            "motion_level": recommend_motion_level(camera),
            "prompt": build_video_prompt(scene_data),
        }
    }

    return result


def recommend_aspect_ratio(scene_type):
    """根据场景类型推荐画面比例"""
    if "抖音" in scene_type or "短视频" in scene_type:
        return "9:16"
    elif "横版" in scene_type or "MV" in scene_type:
        return "16:9"
    else:
        return "16:9"  # 默认横版


def recommend_motion_level(camera_move):
    """根据运镜推荐动态水平"""
    if not camera_move or camera_move in ["static", "none"]:
        return "low"
    elif camera_move in ["slow push-in", "slow pull-out"]:
        return "medium"
    elif camera_move in ["pan", "tilt"]:
        return "medium-high"
    else:
        return "high"


def build_video_prompt(scene_data):
    """构建视频生成 prompt"""
    parts = []

    if scene_data.get("visual_prompt"):
        parts.append(scene_data["visual_prompt"])

    if scene_data.get("camera_move"):
        parts.append(f"Camera: {scene_data['camera_move']}")

    if scene_data.get("transition"):
        parts.append(f"Transition: {scene_data['transition']}")

    # Chloe 元素
    if scene_data.get("emotion_score", 0) >= 7:
        parts.append("cinematic lighting, emotional, powerful")

    return "; ".join(parts) if parts else "a beautiful woman singing in a dreamlike scene"


# ============================================================
# 批量处理场景列表
# ============================================================
def process_scenes(scenes_data, budget="standard"):
    """批量处理多个场景，返回每个场景的模型推荐"""
    results = []

    for scene in scenes_data:
        scene_id = scene.get("scene_id", len(results) + 1)
        recommendation = recommend_model(scene, budget)
        results.append({
            "scene_id": scene_id,
            "time_range": scene.get("time_range", ""),
            **recommendation
        })

    return results


# ============================================================
# CLI 入口
# ============================================================
def main():
    parser = argparse.ArgumentParser(description="视频模型选择器")
    parser.add_argument("--scenes", type=str, help="场景JSON文件路径")
    parser.add_argument("--scene", type=str, help="单个场景JSON（直接传入）")
    parser.add_argument("--budget", default="standard", choices=["economy", "standard", "premium"], help="预算等级")
    parser.add_argument("--output", type=str, help="输出JSON路径")
    args = parser.parse_args()

    if args.scenes:
        with open(args.scenes, "r", encoding="utf-8") as f:
            scenes_data = json.load(f)
        if isinstance(scenes_data, dict):
            scenes_data = scenes_data.get("scenes", [scenes_data])
        results = process_scenes(scenes_data, args.budget)
    elif args.scene:
        scenes_data = json.loads(args.scene)
        results = recommend_model(scenes_data, args.budget)
        print(json.dumps(results, ensure_ascii=False, indent=2))
        return
    else:
        print("请提供 --scenes 或 --scene 参数")
        sys.exit(1)

    output_data = {"recommendations": results, "budget": args.budget}

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(output_data, f, ensure_ascii=False, indent=2)
        print(f"✅ 已保存到 {args.output}")
    else:
        print(json.dumps(output_data, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
