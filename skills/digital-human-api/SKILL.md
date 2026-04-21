---
name: digital-human-api
description: Digital human video generation via Qingyun API — avatar-based talking head videos
---

# digital-human-api v3

基于青云API的通用数字人口播视频生成 Skill。

**v3核心改进：每shot生成专属场景图（Daniel真脸 + 个性化场景），视频自然不抽象。**

## 触发条件
- `数字人视频`、`口播视频`、`digital human`
- 基于剧本生成分镜头数字人视频

## v3 新流程（4步/shot）

```
剧本JSON → [Scene Image] → [TTS] → [Kling Video] → [Lip Sync] → FFmpeg合并
              ↑ 新增：每个shot独立生成贴合场景的图片
```

**每shot独立流程：**
1. 🖼️ **场景图生成** — Grok依据参考脸生成贴合场景的图片（保持Daniel的脸）
2. 📝 **TTS语音** — Gemini生成口播音频
3. 🎬 **Kling视频** — 场景图 + 动作提示词 → 动态视频
4. 👄 **对口型** — Kling LipSync音画同步
5. 🔗 **FFmpeg合并** — 所有shot + BGM → 最终视频

## v3 剧本格式

```json
{
  "title": "视频标题",
  "avatar_image": "/path/to/daniel-headshot.jpg",
  "shots": [
    {
      "id": 1,
      "text": "口播文案",
      "emotion": "sarcastic",
      "scene_description": "（可选）场景图详细描述",
      "duration": 5
    }
  ]
}
```

### emotion 可选值

| emotion | 动作风格 |
|---------|---------|
| `serious` | 严肃直视镜头 |
| `friendly` | 友好微笑 |
| `excited` | 兴奋手势多 |
| `sarcastic` | 讽刺挑眉 |
| `storytelling` | 讲故事手势 |
| `humorous` | 幽默轻松 |
| `intense` | 紧张/激动 |
| `confident` | 自信权威 |
| `questioning` | 疑惑歪头 |
| `casual` | 日常对话 |

### scene_description 写法

描述越具体，场景图越贴合。建议格式：
- 人物表情+动作（如：raised eyebrow, holding coffee cup）
- 场景（如：modern cafe, restaurant table）
- 光线（如：warm natural lighting）
- 风格（如：realistic photo, shot on iPhone）

## 使用方式

```bash
export QINGYUN_API_KEY=$(pass show api/qingyun)

# 完整流水线
python3 scripts/generate.py --script script.json --concurrent 1

# 分步执行
python3 scripts/generate.py --script script.json --step image    # 场景图
python3 scripts/generate.py --script script.json --step tts      # TTS语音
python3 scripts/generate.py --script script.json --step video     # Kling视频
python3 scripts/generate.py --script script.json --step lipsync  # 对口型
python3 scripts/generate.py --script script.json --step merge    # 合并
```

## 输出结构

```
output_dir/
├── shot_01_scene.jpg          # 场景原图
├── shot_01_scene_768.jpg      # 适配Kling的尺寸
├── shot_01_audio.mp3          # TTS语音
├── shot_01_video.mp4          # Kling视频
├── shot_01_lipsync.mp4        # 对口型完成
├── ...
└── final.mp4                  # 最终视频
```

## 已知限制

| 问题 | 解决 |
|------|------|
| 视频太抽象 | v3改用场景图，每个shot独立生成 |
| 429限流 | 并发=1，轮询间隔15s |
| 图片像素无效 | 自动resize到768px宽 |
| Grok场景图失败 | 自动降级到无ref生成 |

## 文件清单

```
digital-human-api/
├── SKILL.md              # 本文件
├── scripts/
│   ├── generate.py       # 主脚本 v3（~800行）
│   └── config.yaml       # 配置 v3
```
