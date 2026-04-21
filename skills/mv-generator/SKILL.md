---
name: mv-generator
description: MediaClaw 内置的音乐视频端到端生成技能。
  End-to-end MV (music video) generation pipeline for virtual singers.
  Audio analysis → Scene timeline → Frame generation → Video generation → Final merge.
  Use when: creating music videos, generating MV frames, syncing video to audio.
---

# MV Generator — 音乐视频生成管线

MediaClaw 内置的音乐视频端到端生成技能。

## 触发词
- 生成MV
- MV制作
- 音乐视频
- mv generator
- 虚拟歌手MV

## 管线流程

```
音频文件 + 歌词 + 角色卡
        │
        ▼
┌────────────────────────────┐
│  Step 1: 音频分析            │
│  scripts/audio-analyzer.py  │
│  → 时长、BPM、场景时间线     │
└────────────┬───────────────┘
             │
             ▼
┌────────────────────────────┐
│  Step 2: 歌词解析            │
│  scripts/lyrics-parser.py   │
│  → 段落结构、情绪曲线        │
└────────────┬───────────────┘
             │
             ▼
┌────────────────────────────┐
│  Step 3: 场景+帧设计         │
│  scripts/scene-design.py    │
│  → 场景类型、运镜、首尾帧prompt │
└────────────┬───────────────┘
             │
             ▼
┌────────────────────────────┐
│  Step 4: 帧图像生成          │
│  qingyun gpt-image-1 API    │
│  → 每场景 first+last frame  │
└────────────┬───────────────┘
             │
             ▼
┌────────────────────────────┐
│  Step 5: 视频片段生成        │
│  kling-2 / veo-3.1 / etc    │
│  → 首帧→尾帧 5s 视频片段    │
└────────────┬───────────────┘
             │
             ▼
┌────────────────────────────┐
│  Step 6: 最终合成            │
│  FFmpeg merge               │
│  → 音轨对齐+转场+字幕       │
└────────────────────────────┘
```

## 输入

| 参数 | 必填 | 说明 |
|------|------|------|
| `audio_file` | ✅ | 音频文件路径 (.mp3/.wav/.m4a) |
| `lyrics` | ✅ | 歌词文本 |
| `character_card` | ✅ | 角色卡 JSON（外貌、声音、风格） |
| `style` | ❌ | cinematic / realistic / anime / ethereal |
| `num_scenes` | ❌ | 分镜数（默认 9） |
| `output_dir` | ❌ | 输出目录（默认: `MediaClaw/output/<project>/`） |

## 输出目录结构

```
output/<project-name>/
├── README.md              ← 项目概要 + 时间轴
├── frames/                ← 首尾帧图像
│   ├── 01_first.png
│   ├── 01_last.png
│   └── ...
├── audio/                 ← 音频文件（多版本）
│   └── song_v1.mp3
├── script/                ← MV 剧本
│   ├── mv_final.json      ← 精准时间轴 JSON
│   ├── mv_final.md        ← 人类可读剧本
│   └── character.json     ← 角色卡
├── docs/                  ← 文档和参考素材
│   └── avatar.png
└── video/                 ← 生成的视频片段（Step 5 产出）
    ├── scene_01.mp4
    └── ...
```

## 经验总结（来自 Chloe《樱花落尽时》项目）

### 图像生成最佳实践
| 项目 | 推荐 | 备注 |
|------|------|------|
| 模型 | qingyun `gpt-image-1` | 成功率最高 |
| API | `/v1/images/generations` | 比 edits 更稳定 |
| 尺寸 | `1024x1536`（竖版） | 必须用规定尺寸 |
| 并发 | 2-3 并发 | 过多会 SSL EOF |
| 重试 | 失败单独重试 | 不整批重跑 |

### 角色一致性技巧
- **统一 prompt prefix**: 包含角色核心外貌特征
- **参考图**: 用 edits API 传入角色头像（但成功率低）
- **场景限定词**: 每帧 prompt 固定前缀 + 场景变量

### 音频同步
- 用 `mutagen` 读 MP3 时长（无需 ffprobe）
- 场景时间按歌曲结构比例分配
- BPM 检测需 `librosa`（可选）

### 视频模型选择
| 情绪 | 模型 | 场景类型 |
|------|------|---------|
| ≤ 6.0 | kling-1.6 | 静态/自然/国风 |
| 6.0-8.0 | kling-1.6 或 kling-2 | 过渡 |
| ≥ 8.0 | kling-2 | 爆发/力量 |
| 360°旋转 | veo-3.1 | 特殊运镜 |

## 依赖
- Python: mutagen, requests
- 外部 API: qingyun (图像), xingjiabi (视频), Google (veo-3.1)
- 可选: librosa (BPM), ffmpeg (合成)

## 参考
- [audio-analyzer.py](scripts/audio-analyzer.py) — 音频分析
- [Chloe 项目完整输出](../../output/chloe-sakura-mv/)
- [virtual-singer-mv-script](~/clawd/skills/virtual-singer-mv-script/) — 独立 MV 剧本 skill
