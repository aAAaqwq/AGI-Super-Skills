---
name: video-lyrics-subtitle
description: Video lyrics subtitle generator — create synchronized subtitle files for music videos
---

# 🎵 视频歌词字幕生成 Skill

> 视频歌词字幕生成引擎：从歌词文本 + 时间轴 → SRT/ASS 字幕 → FFmpeg 烧录到视频

## 触发词

歌词字幕、lyrics subtitle、字幕烧录、字幕生成、SRT、ASS、bilingual subtitle、双语字幕、字幕文件、字幕制作

## 功能概述

从歌词文本（纯文本或 LRC 格式）+ 时间轴信息，生成 SRT/ASS 字幕文件，并可通过 FFmpeg 烧录到视频中。

### 核心 Pipeline

```
lyrics.txt + audio.mp3
  → generate_srt.py   (生成 SRT 时间轴)
  → generate_ass.py   (可选：生成 ASS 高级样式 / KTV 效果)
  → burn_subtitles.sh (FFmpeg 烧录到视频)
  → final_with_subtitles.mp4
```

## 脚本位置

所有脚本在 `scripts/` 子目录下：

| 脚本 | 功能 |
|------|------|
| `scripts/generate_srt.py` | 从歌词文本 + 时间轴生成 SRT 字幕 |
| `scripts/generate_ass.py` | SRT → ASS 转换（支持 KTV 高亮） |
| `scripts/burn_subtitles.sh` | FFmpeg 烧录字幕到视频 |

## 标准输入

| 输入 | 文件 | 说明 |
|------|------|------|
| 歌词原文 | `lyrics/lyrics.txt` | 纯文本或 LRC 格式带时间戳 |
| 中文翻译 | `lyrics/lyrics_cn.txt` | 可选，用于双语字幕 |
| 音频文件 | `audio/song_final.mp3` | 用于获取总时长（纯文本歌词时） |
| 视频文件 | `video/*.mp4` | 烧录目标 |

## generate_srt.py — SRT 字幕生成

### 用法

```bash
python3 scripts/generate_srt.py <lyrics_file> [options]
```

### 选项

| 参数 | 说明 |
|------|------|
| `lyrics_file` | 歌词文件路径（LRC 或纯文本） |
| `--audio <file>` | 音频文件，用于获取总时长（纯文本歌词时必须） |
| `--duration <seconds>` | 总时长（秒），替代 `--audio` |
| `--bilingual <cn_file>` | 中文翻译文件，生成双语 SRT |
| `--json-timeline <file>` | 带时间轴的 JSON 文件（如 `chloe_lyrics_parsed.json`） |
| `-o / --output <file>` | 输出 SRT 文件路径（默认 stdout） |

### 输入格式支持

#### 1. LRC 格式（带时间戳）
```
[00:00.00]（纯音乐前奏）
[00:15.00]樱花落尽时 花瓣纷飞如雪
[00:20.00]你的笑容 在记忆中凋谢
```

#### 2. 纯文本格式（等间隔分配）
需要 `--audio` 或 `--duration` 指定总时长，每行歌词等间隔分配时间。
空行表示纯音乐段，自动标注 `(纯音乐)`。

#### 3. JSON 时间轴格式
通过 `--json-timeline` 传入带 `sections[].lines[]` 结构的 JSON 文件，
支持精确的 start/end 时间。

### SRT 生成规则

- 每行歌词对应一条 SRT 条目
- 空行 / 纯音乐段自动标注 `(纯音乐)`
- 双语模式：原文行在上，翻译行在下，同一条目内用 `\N` 分隔
- 时间格式：`HH:MM:SS,mmm`（SRT 标准）

### 示例

```bash
# LRC 歌词 → SRT
python3 scripts/generate_srt.py lyrics/lyrics.lrc -o subtitles/lyrics.srt

# 纯文本歌词 + 音频时长 → SRT
python3 scripts/generate_srt.py lyrics/lyrics.txt --audio audio/song_final.mp3 -o subtitles/lyrics.srt

# 双语字幕
python3 scripts/generate_srt.py lyrics/lyrics.txt --audio audio/song_final.mp3 \
  --bilingual lyrics/lyrics_cn.txt -o subtitles/lyrics_bilingual.srt

# JSON 时间轴 → SRT
python3 scripts/generate_srt.py lyrics/lyrics.txt \
  --json-timeline script/chloe_lyrics_parsed.json \
  -o subtitles/lyrics.srt
```

## generate_ass.py — ASS 高级字幕生成

### 用法

```bash
python3 scripts/generate_ass.py <srt_file> [options]
```

### 选项

| 参数 | 说明 |
|------|------|
| `srt_file` | 输入 SRT 文件路径 |
| `--style <ktv\|simple>` | 样式模式（默认 `simple`） |
| `--font <name>` | 字体名称（默认 `Noto Sans CJK SC`） |
| `--fontsize <size>` | 字体大小（默认 `48`） |
| `--primary-color <hex>` | 主文字颜色（默认 `#FFFFFF`） |
| `--outline-color <hex>` | 描边颜色（默认 `#000000`） |
| `--back-color <hex>` | 背景色（默认 `#80000000` 半透明黑） |
| `-o / --output <file>` | 输出 ASS 文件路径（默认同名 `.ass`） |

### ASS 样式

#### simple 模式
- 底部居中显示
- 白色文字 + 黑色描边
- 半透明背景条

#### ktv 模式
- 逐字高亮效果（`\kt` 标签）
- 播放时文字从灰色变为亮色
- 适合 KTV / 卡拉 OK 场景

### 示例

```bash
# 简单样式
python3 scripts/generate_ass.py subtitles/lyrics.srt -o subtitles/lyrics.ass

# KTV 样式
python3 scripts/generate_ass.py subtitles/lyrics.srt --style ktv -o subtitles/lyrics.ass

# 自定义字体和颜色
python3 scripts/generate_ass.py subtitles/lyrics.srt \
  --font "Source Han Sans CN" --fontsize 52 \
  --primary-color "#FFD700" -o subtitles/lyrics.ass
```

## burn_subtitles.sh — FFmpeg 字幕烧录

### 用法

```bash
bash scripts/burn_subtitles.sh <video_file> <subtitle_file> [output_file]
```

### 功能

- 自动检测字幕格式（SRT / ASS）
- 调用 FFmpeg 硬字幕烧录
- 默认输出文件名：`<video>_with_subtitles.mp4`
- FFmpeg 路径：`~/tools/ffmpeg`

### FFmpeg 命令

```bash
# SRT 硬字幕
ffmpeg -i video.mp4 -vf "subtitles=lyrics.srt" -c:a copy output.mp4

# ASS 硬字幕
ffmpeg -i video.mp4 -vf "ass=lyrics.ass" -c:a copy output.mp4
```

### 示例

```bash
# 烧录 SRT 字幕
bash scripts/burn_subtitles.sh video/phase1_preview.mp4 subtitles/lyrics.srt video/final_with_subtitles.mp4

# 烧录 ASS 字幕
bash scripts/burn_subtitles.sh video/phase1_preview.mp4 subtitles/lyrics.ass video/final_with_subtitles.mp4
```

---

## 📁 规范 MV 项目文件结构

所有 MV 项目遵循以下文件结构：

```
~/clawd/projects/MediaClaw/output/<project-name>/
├── lyrics/                    # 🎵 歌词（必须有）
│   ├── lyrics.txt             # 歌词原文（纯文本或LRC）
│   ├── lyrics_cn.txt          # 中文翻译（可选）
│   └── lyrics.json            # 带时间轴的JSON（程序生成）
├── subtitles/                 # 📝 字幕文件（程序生成）
│   ├── lyrics.srt             # SRT格式
│   ├── lyrics_bilingual.srt   # 双语SRT
│   └── lyrics.ass             # ASS格式（KTV效果）
├── audio/                     # 🎶 音频
│   └── song_final.mp3         # 最终版音频
├── video/                     # 🎬 视频
│   ├── clips/                 # 各clip片段
│   └── final_with_subtitles.mp4  # 最终带字幕视频
├── frames/                    # 🖼️ 参考帧图片
└── script/                    # 📜 剧本/计划
    ├── mv_script.json         # MV脚本
    └── edit_plan.json         # 剪辑计划
```

### 文件命名铁律 ⚠️

| 内容 | 固定路径 | 说明 |
|------|----------|------|
| 歌词原文 | `lyrics/lyrics.txt` | 纯文本或 LRC |
| 中文翻译 | `lyrics/lyrics_cn.txt` | 可选 |
| SRT 字幕 | `subtitles/lyrics.srt` | 单语 |
| 双语 SRT | `subtitles/lyrics_bilingual.srt` | 双语 |
| ASS 字幕 | `subtitles/lyrics.ass` | KTV 效果 |
| 最终视频 | `video/final_with_subtitles.mp4` | 带字幕成品 |

**禁止随意命名**（如 `sub01.srt`、`lyrics_raw_v2.txt`、`final_v3_new.mp4`）。
所有文件必须遵循以上命名规范。

---

## 完整工作流示例

```bash
# 设置项目路径
PROJECT=~/clawd/projects/MediaClaw/output/chloe-sakura-mv
SKILL=~/clawd/skills/video-lyrics-subtitle

# 1. 生成 SRT 字幕（从 LRC 歌词）
python3 $SKILL/scripts/generate_srt.py \
  $PROJECT/lyrics/lyrics.txt \
  --json-timeline $PROJECT/script/sakura_mv_final.json \
  -o $PROJECT/subtitles/lyrics.srt

# 2. 生成 ASS 字幕（KTV 风格）
python3 $SKILL/scripts/generate_ass.py \
  $PROJECT/subtitles/lyrics.srt \
  --style ktv \
  -o $PROJECT/subtitles/lyrics.ass

# 3. 烧录字幕到视频
bash $SKILL/scripts/burn_subtitles.sh \
  $PROJECT/video/phase1_preview_sakura_mv.mp4 \
  $PROJECT/subtitles/lyrics.ass \
  $PROJECT/video/final_with_subtitles.mp4
```
