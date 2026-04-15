---
name: lyrics-video-sync
description: "歌词-视频精准匹配引擎。将MP3中的歌词片段按时间轴精准匹配到对应视频clip，支持歌词提取、时间轴对齐、情绪映射、字幕烧录、音频分段混合。触发词：歌词匹配、lyrics sync、歌词卡点、音频对齐、字幕视频、lyrics video、歌词视频、音乐视频字幕"
---

# Lyrics-Video Sync — 歌词精准匹配引擎

## 解决的问题

AI MV 制作中，音频和视频经常脱节：
- ❌ 画面和歌词内容不匹配
- ❌ 关键歌词没有对应的视觉呈现
- ❌ 音频高潮段和视频高潮段错位
- ❌ 歌词没有字幕展示

## 工作流

```
音频文件(MP3) → 歌词提取/对齐 → 场景时间轴匹配 → 音频分段 → 视频混合 → 字幕烧录
```

## Step 1: 歌词提取与时间轴对齐

### 方案A: 已有歌词文件
支持格式：
- **LRC**: `[00:15.00]樱花飘落的季节`
- **SRT**: 字幕格式，带精确时间码
- **JSON**: `{lines: [{text, start_s, end_s}]}`

### 方案B: 从音频自动识别歌词
```bash
# 使用 Whisper 识别歌词（带时间戳）
python3 scripts/extract_lyrics_whisper.py \
  --audio input.mp3 \
  --output lyrics.json \
  --language ja \
  --model large
```

### 方案C: 手动标注歌词
```bash
python3 scripts/manual_lyrics_editor.py \
  --audio input.mp3 \
  --output lyrics.json
```

输出统一格式 (`lyrics.json`):
```json
{
  "bpm": 90,
  "duration": 236.8,
  "lines": [
    {
      "index": 0,
      "text": "桜が散る季節に",
      "text_cn": "樱花飘落的季节",
      "start_s": 24.0,
      "end_s": 28.5,
      "section": "verse1",
      "emotion": "gentle",
      "energy": 0.4
    }
  ],
  "sections": [
    {
      "type": "intro",
      "start_s": 0,
      "end_s": 24,
      "energy": 0.3,
      "emotion": "peaceful"
    },
    {
      "type": "chorus",
      "start_s": 94.7,
      "end_s": 122.3,
      "energy": 0.8,
      "emotion": "passionate"
    }
  ]
}
```

## Step 2: 歌词→场景映射

### 映射规则

| 歌词特征 | 推荐画面 |
|---------|---------|
| 自然意象（花/雨/风/月） | 对应自然景观 |
| 情感词（想/哭/笑） | 角色表情特写 |
| 动作词（走/跑/飞） | 对应角色动作 |
| 抽象词（梦/希望/自由） | 抽象/梦幻画面 |
| 重复/叠句 | 重复构图但不同角度 |

### 自动映射
```bash
python3 scripts/map_lyrics_to_scenes.py \
  --lyrics lyrics.json \
  --scenes scenes.json \
  --output edit_plan.json \
  --strategy emotion_energy
```

映射策略：
- **emotion_energy** (默认): 歌词情绪+能量→场景情绪对齐
- **keyword**: 歌词关键词→场景标签匹配
- **sequential**: 按时间顺序直接对应

## Step 3: 音频精准分段

每个视频 clip 对应一段音频，精确裁剪：

```bash
python3 scripts/segment_audio.py \
  --audio input.mp3 \
  --edit-plan edit_plan.json \
  --output-dir segments/ \
  --fade-in 0.3 \
  --fade-out 0.5
```

### 分段规则
- 每段音频 = 对应 clip 的精确时间范围
- 段首段尾各加 0.3s fade（避免爆音）
- 相邻段之间保留 0.1s 重叠（交叉淡化用）
- 总时长必须等于原始音频时长（不增不减）

## Step 4: 视频+音频混合

### FFmpeg 混合命令模板

```bash
# 单个 clip + 对应音频段
ffmpeg -y -hide_banner \
  -i clip.mp4 \
  -i segment_01.m4a \
  -c:v libx264 -crf 18 \
  -c:a aac -b:a 192k \
  -shortest \
  clip_with_audio.mp4

# 多 clip 合并 + 全曲音频
ffmpeg -y -hide_banner \
  -f concat -safe 0 -i clips.txt \
  -i full_audio.mp3 \
  -c:v libx264 -crf 18 \
  -c:a aac -b:a 192k \
  -shortest \
  final_mv.mp4
```

### 音量平衡
```bash
# 对话/人声场景降低音乐音量
ffmpeg -i video.mp4 -i audio.mp3 \
  -filter_complex "[1:a]volume=0.3[a]" \
  -map 0:v -map "[a]" output.mp4
```

## Step 5: 歌词字幕烧录

### 生成 SRT 字幕
```bash
python3 scripts/lyrics_to_srt.py \
  --lyrics lyrics.json \
  --output subtitles.srt \
  --style dual \
  --font "Noto Sans CJK JP"
```

字幕样式选项：
- **single**: 原文（日语/英语）
- **dual**: 原文+中文双语
- **karaoke**: 逐字高亮（KTV效果）
- **minimal**: 底部一行小字

### 烧录到视频
```bash
ffmpeg -y -hide_banner \
  -i final_mv.mp4 \
  -vf "subtitles=subtitles.srt:force_style='FontSize=18,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,Outline=2,Alignment=2'" \
  -c:a copy \
  final_mv_subtitled.mp4
```

### ASS 高级字幕（可选）
支持更丰富的样式：
- 渐变色歌词
- 描边+阴影
- 动画效果（淡入淡出/缩放）

```bash
python3 scripts/lyrics_to_ass.py \
  --lyrics lyrics.json \
  --output subtitles.ass \
  --template karaoke_glow
```

## 完整 Pipeline 示例

```bash
# 从音频到带字幕的MV
export PATH="$HOME/tools:$PATH"

# 1. 提取歌词
python3 scripts/extract_lyrics_whisper.py \
  --audio sakura_mv.mp3 -o lyrics.json

# 2. 映射到场景
python3 scripts/map_lyrics_to_scenes.py \
  --lyrics lyrics.json \
  --scenes video_plan.json \
  -o edit_plan.json

# 3. 分段音频
python3 scripts/segment_audio.py \
  --audio sakura_mv.mp3 \
  --edit-plan edit_plan.json \
  -o segments/

# 4. 逐clip混合音频
for clip in clips/*.mp4; do
  name=$(basename "$clip" .mp4)
  seg="segments/${name}.m4a"
  [ -f "$seg" ] && ffmpeg -y -i "$clip" -i "$seg" \
    -c:v copy -c:a aac -shortest "mixed/${name}.mp4"
done

# 5. 合并全部 + 烧录字幕
ffmpeg -f concat -safe 0 -i mixed.txt -i sakura_mv.mp3 \
  -vf "subtitles=subs.srt" -c:a aac -shortest final.mp4
```

## 与其他 Skill 协作

```
lyrics-video-sync (歌词匹配)
  ← cinematic-video-gen (prompt增强，确保画面匹配歌词意境)
  ← qingyun-api (实际视频生成)
  ← av-sync-workflow (节拍级精度的音视频同步)
  → ffmpeg-video-editor (最终合成)
```

## 特殊场景

### 纯音乐段（无歌词）
- 用节拍分析代替歌词映射
- 能量高→快切/大动作，能量低→慢切/静景
- 参考 `av-sync-workflow` 的 beat sync

### 多语言歌词
- 主歌词+翻译并行显示
- SRT/ASS 支持双行布局
- 时间轴对齐到主语言

### Live Action + AI混合
- 真人片段的歌词卡点用节拍分析
- AI生成片段用歌词情绪映射
- 两者通过 edit_plan.json 统一调度

## 脚本目录

```
scripts/
├── extract_lyrics_whisper.py   # Whisper歌词提取
├── map_lyrics_to_scenes.py     # 歌词→场景映射
├── segment_audio.py            # 音频精准分段
├── lyrics_to_srt.py            # 歌词→SRT字幕
├── lyrics_to_ass.py            # 歌词→ASS高级字幕
├── manual_lyrics_editor.py     # 手动标注工具
└── verify_sync.py              # 同步验证
```

---

*创建日期: 2026-04-10*
*创建人: 小a (CEO) — 基于《樱花落尽时》MV制作需求*
