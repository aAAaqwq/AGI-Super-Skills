---
name: virtual-singer-mv-script
description: Virtual singer MV script generator — audio analysis to video storyboard pipeline
---

# 🎬 Virtual Singer MV Script Generator

> 为虚拟歌手生成完整的 MV 分镜剧本 — 从歌词/音频到可执行的视频制作蓝图

## 触发词
- 生成MV剧本
- MV分镜脚本
- 虚拟歌手视频剧本
- mv script
- 分镜设计
- 分析音频生成MV

## 输入（任选一种方式）

| 方式 | 参数 | 必填 | 说明 |
|------|------|------|------|
| **音频文件** | `audio` | ✅ | MP3/WAV/M4A 文件路径（**推荐**，精准同步） |
| 纯歌词 | `lyrics` | ✅ | 歌词文本 |
| 角色卡 | `character_card` | ❌ | 歌手角色卡路径（默认：Chloe） |
| 风格 | `style` | ❌ | cinematic / ethereal / anime / realistic |
| 场景数 | `scenes` | ❌ | 默认 9 |

**推荐方式**：`python3 scripts/audio-analyzer.py <audio_file> -s 9 -v`
→ 自动分析时长、BPM、能量曲线，生成精准时间线

## 输出
1. **JSON 格式完整分镜** — 可直接对接视频生成管线
2. **Markdown 可读剧本** — 人类审阅用
3. **情绪曲线图** — emotion_score 0-10 走势
4. **时间轴对齐** — 精确到毫秒，与音频同步

## 工作流程

```
音频文件 / 歌词文本
        │
        ▼
┌─────────────────────────────────┐
│  0. 音频分析 (audio-analyzer)   │  ← 新增第一步
│     - mutagen 读取真实时长      │
│     - librosa BPM 检测          │
│     - 能量曲线 → 场景时间节点    │
│     - 输出: scene_timeline.json  │
└──────────────┬──────────────────┘
               │ (无音频时跳过，用歌词估算)
               ▼
┌─────────────────────────────┐
│  1. 歌词解析 (lyrics-parser) │
│     - 结构识别 (Verse/Chorus/Bridge) │
│     - 情绪曲线计算 (0-10)    │
│     - 时间轴对齐（精确到秒）  │
└──────────┬──────────────────┘
           │
           ▼
┌─────────────────────────────┐
│  2. 场景分配 (scene-assigner) │
│     - 情绪→场景类型映射      │
│     - Chloe 专属场景库       │
│     - 运镜设计              │
│     - 首尾帧衔接设计         │
│     - 音频同步校正           │
└──────────┬──────────────────┘
           │
           ▼
┌─────────────────────────────┐
│  3. 模型选择 (model-selector) │
│     - 场景复杂度评估         │
│     - 视频生成模型推荐       │
│     - 参数配置              │
└──────────┬──────────────────┘
           │
           ▼
  完整 MV 分镜剧本 (JSON + MD)
```

## 快速开始

### Step 0：音频分析（推荐）
```bash
python3 ~/clawd/skills/virtual-singer-mv-script/scripts/audio-analyzer.py \
  /path/to/song.mp3 \
  -s 9 -v -o /tmp/song_analysis.json
```
输出：时长、BPM、9个场景的精准起止时间

### Step 1：生成完整剧本
```bash
cd ~/clawd/skills/virtual-singer-mv-script

# 有音频 → 精准模式
python3 scripts/audio-analyzer.py "/path/to/song.mp3" -s 9
python3 scripts/lyrics-parser.py --lyrics "..." --bpm 88
python3 scripts/scene-assigner.py --parsed /tmp/lyrics_parsed.json \
  --timeline /tmp/song_analysis.json
python3 scripts/merge-output.py \
  --lyrics /tmp/lyrics_parsed.json \
  --scenes /tmp/scenes_assigned.json \
  --output mv_script.json
```

## 场景时间分配规则（音频同步模式）

| 段落 | 时长占比 | 情绪策略 |
|------|---------|---------|
| 前奏 (0-10%) | 10% | 平静 3.0 |
| 主歌1 (10-25%) | 15% | 渐升 4.5 |
| 过渡 (25-40%) | 15% | 铺垫 6.0 |
| 副歌1 (40-55%) | 15% | 爆发 8.0 |
| 副歌2 (55-70%) | 15% | 维持 8.5 |
| 高潮 (70-82%) | 12% | 巅峰 9.0 |
| 桥段 (82-92%) | 10% | 承接 8.5 |
| 终极 (92-98%) | 6% | 最高 10.0 |
| 尾声 (98-100%) | 2% | 消散 2.0 |

> **关键原则**：所有场景时长基于真实音频时长计算，不可用固定值估算

## 帧文件规范

帧命名：`scene{NN}_{first|last}.png`
- `scene01_first.png` — Scene 1 首帧
- `scene01_last.png` — Scene 1 尾帧

必须元素（每帧 prompt 必须包含）：
```
A beautiful young East Asian woman, long black wavy hair,
pink cherry blossom hair clip, white lace dress,
holding cherry blossom branch near her lips singing, fair skin
```

## 视频模型选择规则

| 场景类型 | 推荐模型 | 原因 |
|----------|---------|------|
| 静态人物+自然光 | kling-1.6 | 性价比高，静态稳定 |
| 动态运镜+人物 | kling-2 | 运镜理解强 |
| 360°旋转/复杂特效 | veo-3.1 | 粒子/旋转效果最佳 |
| 长镜头+叙事 | sora-2 | 长时一致性 |
| 国风/舞蹈 | seedance-3.0 | 东方美学流畅 |

## 注意事项
1. **音频优先** — 有音频时必须用 audio-analyzer.py 分析真实时长
2. **首尾帧连续性** — 尾帧视觉元素必须在下一场景首帧中出现
3. **情绪曲线连贯** — 不允许突然跳跃（除非音乐设计需要）
4. **总时长精确** — 所有分镜时长之和 = 音频总时长
5. **BPM 同步** — 转场卡点必须落在节拍上

## 示例
- [完整示例：《雨停》MV 精准剧本](examples/yutin_mv_final.md)
- [《樱花落尽时》MV 演示剧本](examples/chloe_mv_script_final_readable.md)
