---
name: video-content-analyzer
description: 下载视频并用AI分析内容 - 支持B站/抖音/YouTube等平台，提取语音内容并分析视频结构
version: "1.0.0"
author: laipishe
license: MIT
category: marketing
tags:
  - 视频分析
  - 内容理解
  - 语音转文字
  - B站
  - 抖音
  - YouTube
department: Marketing

allowed-tools: Exec

models:
  recommended:
    - minimax/MiniMax-M2.5
    - claude-sonnet-4
  compatible:
    - gpt-4o

languages:
  - zh

capabilities:
  - video_download
  - audio_extraction
  - speech_to_text
  - content_analysis

related_skills:
  - viral-video-analysis
  - openai-whisper-api

dependencies:
  - yt-dlp (视频下载)
  - ffmpeg (音频提取)
  - openai-whisper-api (语音转文字)
---

# 视频内容分析器

自动下载视频并用AI分析内容，提取完整的语音文案，分析视频结构和节奏。

## 功能

1. **视频下载** - 支持B站、抖音、YouTube等主流平台
2. **音频提取** - 用ffmpeg提取视频中的音频
3. **语音转写** - 用OpenAI Whisper API转写为文字
4. **内容分析** - AI分析视频结构、节奏、钩子等

## 前置要求

### 必须安装的工具

```bash
# 安装 yt-dlp (视频下载)
pip3 install --break-system-packages yt-dlp

# 安装 ffmpeg (音频处理)
# Mac: brew install ffmpeg
# Ubuntu: sudo apt install ffmpeg
```

### API Key

需要设置 OpenAI API Key（用于Whisper转写）：
```bash
export OPENAI_API_KEY="your-api-key"
```

或在 `~/.openclaw/openclaw.json` 中配置：
```json
{
  "skills": {
    "openai-whisper-api": {
      "apiKey": "your-api-key"
    }
  }
}
```

## 使用方法

### 输入

用户提供视频链接，例如：
- B站: `https://www.bilibili.com/video/BV1xuPYzcEdo`
- 抖音: `https://www.douyin.com/video/xxx`
- YouTube: `https://www.youtube.com/watch?v=xxx`

### 输出

完整的分析报告，包括：
1. 📝 完整文案（语音转写）
2. 🎬 视频结构分析（章节/时间节点）
3. 🪝 钩子分析
4. ⏱️ 节奏分析
5. 💡 内容总结

---

## 工作流程

```
1. 输入视频链接
        ↓
2. yt-dlp 下载视频
        ↓
3. 获取视频时长，计算关键帧数量
        ↓
4. ffmpeg 提取关键帧（每30秒1帧）
        ↓
5. 获取弹幕数据（若有）
        ↓
6. Whisper API 转写（若有API）
        ↓
7. AI 分析画面+弹幕+文案
        ↓
8. 输出完整报告
```

---

## 关键帧提取（优化版）

### 自动提取策略

```bash
# 视频时长 / 30 = 关键帧数量
# 例如：8分钟视频 → 16-17张关键帧

# 提取关键帧（每30秒1帧）
ffmpeg -ss 00:00:00 -i video.mp4 -vframes 1 -q:v 2 frame_001.jpg -y
ffmpeg -ss 00:00:30 -i video.mp4 -vframes 1 -q:v 2 frame_002.jpg -y
ffmpeg -ss 00:01:00 -i video.mp4 -vframes 1 -q:v 2 frame_003.jpg -y
# ... 以此类推
```

### 帧数建议

| 视频时长 | 建议帧数 | 间隔 |
|---------|---------|------|
| < 3 分钟 | 6-8 帧 | 每20-30秒 |
| 3-10 分钟 | 12-20 帧 | 每30秒 |
| 10-30 分钟 | 30-60 帧 | 每30秒 |

### 批量提取脚本

```python
import subprocess
import os

def extract_frames(video_path, output_dir, interval=30):
    """提取视频关键帧
    
    Args:
        video_path: 视频文件路径
        output_dir: 输出目录
        interval: 帧间隔（秒），默认30秒
    """
    # 获取视频时长
    cmd = ['ffprobe', '-v', 'error', '-show_entries', 
           'format=duration', '-of', 'default=noprint_wrappers=1:nokey=1', 
           video_path]
    result = subprocess.run(cmd, capture_output=True, text=True)
    duration = float(result.stdout.strip())
    
    # 计算帧数
    num_frames = int(duration // interval) + 1
    
    os.makedirs(output_dir, exist_ok=True)
    
    for i in range(num_frames):
        seconds = i * interval
        mins = seconds // 60
        secs = seconds % 60
        ts = f'{mins:02d}:{secs:02d}'
        out = f'{output_dir}/frame_{i+1:03d}.jpg'
        
        cmd = ['ffmpeg', '-ss', ts, '-i', video_path, 
               '-vframes', '1', '-q:v', '2', out, '-y']
        subprocess.run(cmd, capture_output=True)
        print(f'✓ Extracted {out}')
    
    return num_frames

# 使用示例
extract_frames('/tmp/video.mp4', '/tmp/frames', interval=30)
```

---

## 命令行示例

### 手动下载B站视频

```bash
# 下载B站视频（仅音频）
yt-dlp -x --audio-format mp3 -o "%(title)s.%(ext)s" "https://www.bilibili.com/video/BV1xuPYzcEdo"

# 下载视频（最佳画质）
yt-dlp -f "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best" -o "%(title)s.%(ext)s" "https://www.bilibili.com/video/BV1xuPYzcEdo"

# 仅下载字幕
yt-dlp --write-subs --skip-download -o "%(title)s" "https://www.bilibili.com/video/BV1xuPYzcEdo"
```

### 提取音频

```bash
# 从视频提取音频
ffmpeg -i input.mp4 -vn -acodec libmp3lame -q:a 2 output.mp3

# 或直接用yt-dlp
yt-dlp -x --audio-format mp3 "https://www.bilibili.com/video/BV1xuPYzcEdo"
```

---

## 输出模板

```markdown
# 📹 视频内容分析报告

**视频**: [标题]
**链接**: [URL]
**时长**: [时长]
**平台**: [B站/抖音/YouTube]
**关键帧数**: [数量]

---

## 📝 完整文案

[Whisper转写的完整语音文案]

---

## 🎬 视频结构（基于关键帧）

| 时间 | 画面内容 | 阶段 |
|------|---------|------|
| 0:00 | [第1帧描述] | 钩子 |
| 0:30 | [第2帧描述] | 铺垫 |
| 1:00 | [第3帧描述] | 主题展开 |
| ... | ... | ... |

---

## 🪝 钩子分析

[开头画面的钩子设计分析]

---

## 🎯 内容分层

- **开头 (0-1分钟)**:
- **中段 (1-5分钟)**:
- **高潮 (5-7分钟)**:
- **结尾 (7-分钟)**:

---

## 💡 爆款元素

| 元素 | 分析 |
|------|------|
| 情感点 | [弹幕高频情感词] |
| 互动点 | [弹幕互动热点] |
| 记忆点 | [金句/名场面] |

---

## 📊 弹幕热点词

```
[从danmaku.xml提取的高频弹幕]
```

---

## 🔥 成功原因总结

1. [核心爆款因素]
2. [情感共鸣点]
3. [创新/独特之处]

---

## 总结

[视频的核心内容和亮点]
```

---

## 注意事项

1. 📡 **网络** - 下载视频需要稳定的网络
2. 💰 **费用** - Whisper API按分钟计费（~$0.006/分钟）
3. ⏱️ **时间** - 完整分析需要3-5分钟
4. 📏 **长度** - 建议视频时长 < 30分钟
5. 🔐 **版权** - 仅供学习分析使用，勿用于商业目的

---

## 故障排除

### 下载失败
- 检查网络连接
- 尝试使用代理
- B站可能需要Cookie认证

### Whisper转写失败
- 确认OPENAI_API_KEY正确设置
- 检查API余额
- 音频文件是否损坏

### ffmpeg问题
- 确认ffmpeg已安装: `ffmpeg -version`
- Mac用户: `brew install ffmpeg`
```
