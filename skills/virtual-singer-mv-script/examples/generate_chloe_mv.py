#!/usr/bin/env python3
"""
generate_chloe_mv.py — 为 Chloe 出道曲《樱花落尽时》生成完整 MV 剧本
"""
import json
import sys
sys.path.insert(0, "scripts")

from lyrics_parser import LyricsParser
from scene_assigner import SceneAssigner
from model_selector import recommend_model

# ── Chloe 出道曲《樱花落尽时》完整歌词 ────────────────────────
LYRICS = """[00:00.00]<intro>
（纯音乐前奏，钢琴+弦乐，渐强）

[00:15.00]<verse1>
晨曦洒落在溪畔
樱花瓣随风轻轻飘散
她在花雨中轻声吟唱
歌声穿透晨雾的边缘

[00:45.00]<pre_chorus>
风吹过古老的樱树林
记忆像落叶般飘零
她在等待一个回音
在时间尽头不肯清醒

[01:00.00]<chorus>
樱花落尽时 歌声未曾休
哪怕春去秋来 哪怕星辰不再
她用温柔的力量
撼动这世间所有的阴霾

[01:30.00]<verse2>
月光倒映在水面
她的影子拉得很远
那不是告别 是重逢
在另一个春天再见

[02:00.00]<chorus2>
樱花落尽时 思念未曾断
哪怕万水千山 哪怕岁月变迁
她用铁肺的声音
唱出生命最炽热的火焰

[02:30.00]<bridge>
（情绪转折）
她不是脆弱的花瓣
她是烈火中重生的凤
让所有的悲伤
都化作绽放的力量

[03:00.00]<final_chorus>
樱花落尽时 光芒照亮黑暗
哪怕跌倒千次 哪怕泪水风干
她是温柔的力量
是落樱之后 最耀眼的光

[03:30.00]<outro>
（渐弱）
晨曦... 落樱...
她的歌声...
未曾休...
"""


def main():
    # Step 1: 解析歌词
    print("🎤 Step 1: 解析歌词...")
    parser = LyricsParser(bpm=82)
    parsed = parser.parse(LYRICS)
    with open("chloe_lyrics_parsed.json", "w", encoding="utf-8") as f:
        json.dump(parsed, f, ensure_ascii=False, indent=2)
    print(f"   ✅ 解析完成: {len(parsed['lines'])} 行歌词")

    # Step 2: 场景分配
    print("🎬 Step 2: 分配场景...")
    assigner = SceneAssigner()
    scenes = assigner.assign(parsed)

    # 增强 Chloe 专属视觉描述
    for scene in scenes:
        scene["visual_prompt"] = build_chloe_visual(scene)
        scene["first_frame"] = build_first_frame(scene)
        scene["last_frame"] = build_last_frame(scene)

    with open("chloe_scenes_assigned.json", "w", encoding="utf-8") as f:
        json.dump({"scenes": scenes}, f, ensure_ascii=False, indent=2)
    print(f"   ✅ 场景分配完成: {len(scenes)} 个分镜")

    # Step 3: 模型选择
    print("🤖 Step 3: 选择视频模型...")
    recommendations = []
    for scene in scenes:
        rec = recommend_model(scene)
        recommendations.append({**rec, "scene_id": scene["scene_id"]})
    with open("chloe_models_selected.json", "w", encoding="utf-8") as f:
        json.dump({"recommendations": recommendations}, f, ensure_ascii=False, indent=2)
    print(f"   ✅ 模型选择完成")

    # Step 4: 合并输出
    print("📄 Step 4: 生成完整剧本...")
    from merge_output import merge
    merge("chloe_lyrics_parsed.json", "chloe_scenes_assigned.json",
          "chloe_models_selected.json", "chloe_mv_script_final.json")

    print("\n🎉 Chloe 出道曲 MV 剧本生成完成！")
    print("   📄 完整剧本: chloe_mv_script_final.json")
    print("   📖 可读版本: chloe_mv_script_final_readable.md")

    return scenes, recommendations


def build_chloe_visual(scene):
    """为 Chloe 构建专属视觉描述"""
    scene_type = scene.get("scene_type", "")
    emotion = scene.get("emotion_score", 5)
    time_pos = scene.get("time_range", "00:00")

    base = "ethereal young East Asian woman with long wavy black hair, wearing flowing white lace embroidered dress with cherry blossom patterns, delicate flower hair accessories, vintage white lace parasol, "

    # 场景映射
    if "樱" in scene_type or "花雨" in scene_type:
        bg = "standing in a rain of cherry blossom petals, ancient cherry blossom forest, soft golden sunrise light filtering through branches, morning mist, stream nearby with crystal clear water, dreamy spring atmosphere"
    elif "溪" in scene_type or "水" in scene_type:
        bg = "by a crystal clear mountain stream, stepping stones, soft morning light, cherry trees on both banks, petals floating on water surface, ethereal reflections, serene atmosphere"
    elif "月" in scene_type or "夜" in scene_type:
        bg = "under soft moonlight by a peaceful pond, silver-blue lighting, cherry trees in gentle breeze, reflections on still water, romantic night atmosphere, mystical ambiance"
    elif "林" in scene_type or "暮" in scene_type:
        bg = "in a misty ancient forest path, cherry trees arching overhead forming a tunnel, soft diffused light, morning fog, magical fairytale atmosphere"
    elif "绽" in scene_type or "火" in scene_type or "爆发" in scene_type:
        bg = "in a dramatic burst of light, cherry blossoms swirling in powerful wind, golden rays shining through petals, dramatic cinematic lighting, emotional power, firefly particles"
    else:
        bg = "in a dreamlike spring garden, cherry blossoms and lush greenery, soft natural lighting, ethereal atmosphere, fairytale aesthetic"

    # 情绪增强
    if emotion >= 8:
        lighting = "dramatic golden hour, lens flare, emotional lighting, volumetric light rays, cinematic"
    elif emotion >= 6:
        lighting = "warm soft lighting, golden highlights, romantic atmosphere"
    else:
        lighting = "soft diffused light, gentle shadows, serene mood"

    return base + bg + ", " + lighting + ", 8K, ultra detailed, professional cinematography"


def build_first_frame(scene):
    """首帧设计"""
    scene_type = scene.get("scene_type", "")
    time_pos = scene.get("time_range", "00:00")
    start_time = time_pos.split("-")[0] if "-" in time_pos else time_pos

    if "00:00" in start_time or "intro" in str(scene.get("section", "")):
        return {
            "description": "模糊的樱花林全景，晨雾弥漫，镜头缓缓推进",
            "gemini_composite": True,
            "elements": ["樱花林全景", "晨雾", "柔和光线"]
        }
    elif "01:00" in start_time or "chorus" in str(scene.get("section", "")):
        return {
            "description": "Chloe全身出现在樱花雨中，白裙飘动，镜头对准她的眼睛",
            "gemini_composite": True,
            "elements": ["Chloe全身", "樱花雨", "白裙飘动", "眼神凝视"]
        }
    else:
        return {
            "description": "场景淡入，Chloe从模糊到清晰，镜头慢慢稳定",
            "gemini_composite": True,
            "elements": ["虚化背景", "Chloe逐渐清晰", "柔焦"]
        }


def build_last_frame(scene):
    """尾帧设计（必须与下一帧首帧衔接）"""
    scene_type = scene.get("scene_type", "")
    emotion = scene.get("emotion_score", 5)
    time_pos = scene.get("time_range", "00:00")
    end_time = time_pos.split("-")[-1] if "-" in time_pos else "00:00"

    if emotion >= 8:
        return {
            "description": "Chloe抬头，樱花瓣在身后形成光环，镜头慢慢拉远",
            "gemini_composite": True,
            "elements": ["Chloe抬头", "樱花光环", "拉远镜头"]
        }
    else:
        return {
            "description": "Chloe转身，白裙飘起，镜头跟随旋转渐隐",
            "gemini_composite": True,
            "elements": ["Chloe转身", "白裙飘起", "镜头跟随", "渐隐过渡"]
        }


if __name__ == "__main__":
    main()
