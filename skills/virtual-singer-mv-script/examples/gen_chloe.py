#!/usr/bin/env python3
"""Generate Chloe MV script demo"""
import json
from datetime import datetime

SCENES = [
    {"scene_id": 1, "section": "intro", "time_range": "00:00-00:15", "lyrics_lines": [{"text": "（纯音乐前奏，钢琴+弦乐，渐强）"}], "emotion_score": 3.0, "scene_type": "黎明樱花林", "camera_move": "slow push-in", "shot_type": "wide", "first_frame": {"description": "黎明薄雾中的樱花林全景，镜头缓缓推进", "gemini_composite": True}, "last_frame": {"description": "镜头穿过樱花枝条，Chloe身影若隐若现", "gemini_composite": True}, "transition": "dissolve", "beat_sync": "前奏渐强，镜头加速推进"},
    {"scene_id": 2, "section": "verse1", "time_range": "00:15-00:45", "lyrics_lines": [{"text": "晨曦洒落在溪畔"}, {"text": "樱花瓣随风轻轻飘散"}, {"text": "她在花雨中轻声吟唱"}, {"text": "歌声穿透晨雾的边缘"}], "emotion_score": 4.5, "scene_type": "晨雾溪畔樱花林", "camera_move": "slow push-in", "shot_type": "medium", "first_frame": {"description": "Chloe站在小溪边，晨雾轻绕，樱花纷飞", "gemini_composite": True}, "last_frame": {"description": "Chloe抬头望向树梢，樱花瓣落在发间", "gemini_composite": True}, "transition": "cross dissolve", "beat_sync": "歌词'飘散'时樱花飞起"},
    {"scene_id": 3, "section": "pre_chorus", "time_range": "00:45-01:00", "lyrics_lines": [{"text": "风吹过古老的樱树林"}, {"text": "记忆像落叶般飘零"}, {"text": "她在等待一个回音"}, {"text": "在时间尽头不肯清醒"}], "emotion_score": 6.0, "scene_type": "古老樱花隧道", "camera_move": "tracking shot", "shot_type": "medium", "first_frame": {"description": "Chloe走在樱花隧道中，花瓣在风中旋转", "gemini_composite": True}, "last_frame": {"description": "Chloe停下脚步，镜头缓缓推向她的侧脸", "gemini_composite": True}, "transition": "whip pan", "beat_sync": "'飘零'时快速转场"},
    {"scene_id": 4, "section": "chorus", "time_range": "01:00-01:30", "lyrics_lines": [{"text": "樱花落尽时 歌声未曾休"}, {"text": "哪怕春去秋来 哪怕星辰不再"}, {"text": "她用温柔的力量"}, {"text": "撼动这世间所有的阴霾"}], "emotion_score": 9.0, "scene_type": "光芒穿透樱花林", "camera_move": "crane shot rise", "shot_type": "wide", "first_frame": {"description": "Chloe张开双臂，金色光芒穿透樱花枝叶", "gemini_composite": True}, "last_frame": {"description": "镜头拉远，Chloe站在光柱中央，樱花环绕", "gemini_composite": True}, "transition": "speed ramp", "beat_sync": "'撼动'时镜头急速上升"},
    {"scene_id": 5, "section": "verse2", "time_range": "01:30-02:00", "lyrics_lines": [{"text": "月光倒映在水面"}, {"text": "她的影子拉得很远"}, {"text": "那不是告别 是重逢"}, {"text": "在另一个春天再见"}], "emotion_score": 5.5, "scene_type": "月下池塘倒影", "camera_move": "slow pull-out", "shot_type": "medium", "first_frame": {"description": "月光下池塘，Chloe倒影随波纹荡漾", "gemini_composite": True}, "last_frame": {"description": "镜头拉远，池塘全貌，月光洒满水面", "gemini_composite": True}, "transition": "dissolve", "beat_sync": "'重逢'时倒影泛起涟漪"},
    {"scene_id": 6, "section": "chorus2", "time_range": "02:00-02:30", "lyrics_lines": [{"text": "樱花落尽时 思念未曾断"}, {"text": "哪怕万水千山 哪怕岁月变迁"}, {"text": "她用铁肺的声音"}, {"text": "唱出生命最炽热的火焰"}], "emotion_score": 9.5, "scene_type": "烈火樱花爆发", "camera_move": "dolly in fast", "shot_type": "close-up", "first_frame": {"description": "Chloe闭眼深呼气，下一秒将爆发", "gemini_composite": True}, "last_frame": {"description": "Chloe张嘴歌唱，光芒从口中喷涌而出", "gemini_composite": True}, "transition": "explosion cut", "beat_sync": "'火焰'时硬切到爆发镜头"},
    {"scene_id": 7, "section": "bridge", "time_range": "02:30-02:45", "lyrics_lines": [{"text": "她不是脆弱的花瓣"}, {"text": "她是烈火中重生的凤"}, {"text": "让所有的悲伤"}, {"text": "都化作绽放的力量"}], "emotion_score": 8.5, "scene_type": "凤凰涅槃火焰", "camera_move": "360 degree orbit", "shot_type": "full", "first_frame": {"description": "Chloe在火焰旋涡中心，凤凰展翅光影", "gemini_composite": True}, "last_frame": {"description": "镜头绕Chloe旋转360度，火焰化作樱花飘散", "gemini_composite": True}, "transition": "fire to petals morph", "beat_sync": "'力量'时完成360度旋转"},
    {"scene_id": 8, "section": "final_chorus", "time_range": "02:45-03:15", "lyrics_lines": [{"text": "樱花落尽时 光芒照亮黑暗"}, {"text": "哪怕跌倒千次 哪怕泪水风干"}, {"text": "她是温柔的力量"}, {"text": "是落樱之后 最耀眼的光"}], "emotion_score": 10.0, "scene_type": "黎明光芒", "camera_move": "aerial rising", "shot_type": "extreme wide", "first_frame": {"description": "从黑暗中缓缓升起，Chloe被金色光芒包围", "gemini_composite": True}, "last_frame": {"description": "镜头不断上升拉远，Chloe站在光芒中心，黎明到来", "gemini_composite": True}, "transition": "light burst", "beat_sync": "高潮音轨峰值，卡点在'光'字"},
    {"scene_id": 9, "section": "outro", "time_range": "03:15-03:30", "lyrics_lines": [{"text": "晨曦... 落樱..."}, {"text": "她的歌声..."}, {"text": "未曾休..."}], "emotion_score": 2.0, "scene_type": "晨曦樱花", "camera_move": "slow fade out", "shot_type": "wide", "first_frame": {"description": "晨曦中Chloe身影渐渐透明化为樱花", "gemini_composite": True}, "last_frame": {"description": "只剩樱花在晨光中飘落，画面渐白", "gemini_composite": True}, "transition": "fade to white", "beat_sync": "'未曾休'尾音渐弱时缓缓淡出"},
]

VISUALS = {
    "黎明樱花林": "misty cherry blossom forest at dawn, soft golden light through mist, wide establishing shot, ethereal atmosphere",
    "晨雾溪畔樱花林": "standing by crystal stream in morning mist, cherry petals floating on water, soft sunrise light, medium shot, ethereal reflections",
    "古老樱花隧道": "walking through ancient cherry tree tunnel, petals forming canopy overhead, warm golden light rays, romantic tracking shot",
    "光芒穿透樱花林": "bathed in golden divine light rays breaking through cherry branches, volumetric lighting, crane rising shot, cinematic",
    "月下池塘倒影": "under soft moonlight by still pond, silver-blue tones, cherry petals floating on water, mirror reflections, slow pull-out",
    "烈火樱花爆发": "surrounded by swirling cherry blossoms with golden fire particles, dramatic backlight halo, dolly in fast, lens flare, powerful",
    "凤凰涅槃火焰": "surrounded by phoenix-like golden fire vortex, 360 degree orbit camera, cherry blossoms morphing into flames, epic",
    "黎明光芒": "bathed in golden divine light, aerial rising shot, cherry petals glowing, epic scale, cinematic atmosphere",
    "晨曦樱花": "fading into morning light, cherry petals drifting in soft dawn, ethereal dissolve, serene ending",
}

def chloe_visual(scene):
    st = scene["scene_type"]
    emo = scene["emotion_score"]
    base = "ethereal young East Asian woman, long wavy black hair with cherry blossom accessories, white lace embroidered dress, vintage lace parasol, "
    bg = VISUALS.get(st, "dreamlike spring garden, cherry blossoms, soft lighting")
    lighting = "dramatic golden hour, volumetric light" if emo >= 8 else "warm soft lighting" if emo >= 5 else "gentle diffused light"
    return base + bg + f", {lighting}, 8K, ultra detailed, professional cinematography"

def select_model(scene):
    emo = scene["emotion_score"]
    st = scene.get("scene_type", "")
    if emo >= 9: return {"model": "kling-2", "provider": "kling", "reason": f"高情绪{emo}+复杂运镜 → kling-2动态最强"}
    elif emo >= 7: return {"model": "veo-3.1", "provider": "google", "reason": f"高情绪{emo}+情感场景 → veo-3.1一致性最佳"}
    elif "火焰" in st or "凤" in st: return {"model": "sora-2", "provider": "openai", "reason": "火焰特效 → sora-2想象力最丰富"}
    elif "樱花" in st or "黎明" in st: return {"model": "seedance-3.0", "provider": "bytedance", "reason": "国风场景 → seedance-3.0亚洲面孔优化"}
    else: return {"model": "kling-1.6", "provider": "kling", "reason": "日常场景 → kling-1.6性价比最优"}

for s in SCENES:
    s["duration_seconds"] = 15
    s["visual_prompt"] = chloe_visual(s)
    r = select_model(s)
    s["video_model"] = r["model"]
    s["provider"] = r["provider"]
    s["model_reason"] = r["reason"]
    s["model_parameters"] = {"duration": 15, "aspect_ratio": "16:9", "fps": 30, "motion_level": "high" if s["emotion_score"] >= 8 else "medium"}

mv_script = {
    "metadata": {"generated_at": datetime.now().isoformat(), "total_scenes": len(SCENES), "total_duration_seconds": sum(s["duration_seconds"] for s in SCENES), "character": "Chloe", "song": "《樱花落尽时》"},
    "scenes": SCENES
}

with open("examples/chloe_mv_script_final.json", "w", encoding="utf-8") as f:
    json.dump(mv_script, f, ensure_ascii=False, indent=2)

# Markdown
md = [f"# 🎬 MV 剧本 — 《樱花落尽时》\n\n> 虚拟歌手: **Chloe** | 总时长: {mv_script['metadata']['total_duration_seconds']}s | 分镜: {len(SCENES)}个\n> 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n---\n\n## 📈 情绪曲线\n\n"]
for s in SCENES:
    e = s["emotion_score"]
    bar = "🔥" * int(e//2) + "░" * (5 - int(e//2))
    md.append(f"`{s['time_range']}` {bar} {e}/10\n")
md.append("\n---\n\n## 🎬 分镜详情\n\n")
for s in SCENES:
    e = s["emotion_score"]
    emo_emoji = "🔥" if e >= 8 else "💫" if e >= 5 else "🌙"
    lyrics = " / ".join(l["text"] for l in s["lyrics_lines"])
    md.append(f"### Scene {s['scene_id']} — {s['time_range']} {emo_emoji}\n\n")
    md.append(f"**情绪**: {e}/10 | **场景**: {s['scene_type']} | **运镜**: {s['camera_move']}\n")
    md.append(f"**模型**: `{s['video_model']}` | **转场**: {s['transition']} | **卡点**: {s['beat_sync']}\n\n")
    md.append(f"**歌词**: {lyrics}\n\n")
    md.append(f"**首帧**: {s['first_frame']['description']}\n")
    md.append(f"**尾帧**: {s['last_frame']['description']}\n\n---\n\n")

with open("examples/chloe_mv_script_final_readable.md", "w", encoding="utf-8") as f:
    f.write("".join(md))

print("✅ Chloe MV剧本生成完成!")
print(f"📊 总时长: {mv_script['metadata']['total_duration_seconds']}s | 分镜: {len(SCENES)}")
for s in SCENES:
    print(f"  [{s['time_range']}] {s['scene_type']:20s} → {s['video_model']:12s} (emo:{s['emotion_score']})")
