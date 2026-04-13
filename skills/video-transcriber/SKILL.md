---
name: video-transcriber
description: 视频转写工作流，支持B站和YouTube视频。自动判断有字幕/无字幕，有字幕则获取字幕，无字幕则下载音频+whisper转写。触发场景：(1) 用户要求总结视频内容 (2) 用户要求获取视频字幕 (3) 用户要求转写视频 (4) 处理B站/YouTube视频
---

# 视频转写工作流

## 决策流程

```
1. 尝试获取字幕 → bilibili-youtube-watcher
      ↓
   有字幕？ ──是──→ 检查语言 ──需翻译？──是──→ LLM翻译
      ↓否                       ↓否
2. 下载音频 → yt-dlp      直接使用
      ↓
3. 判断语言 → 中文？用--language Chinese : 用--language en
      ↓
4. 转写 → whisper.cpp tiny模型
```

## 工具

### bilibili-youtube-watcher（有字幕时）
```bash
# B站视频字幕
python3 ~/.openclaw/extensions/bilibili-youtube-watcher/scripts/get_transcript.py "URL" --lang zh-CN

# YouTube字幕（尝试en/zh-CN）
python3 ~/.openclaw/extensions/bilibili-youtube-watcher/scripts/get_transcript.py "URL" --lang en
```

### yt-dlp + whisper.cpp（无字幕时）

```bash
# 1. 获取视频时长
yt-dlp --dump-json --no-check-certificate "URL" | jq -r '.duration, .title'

# 2. 下载音频
yt-dlp -f bestaudio --no-check-certificate "URL" -o audio.m4a

# 3. 转码
ffmpeg -i audio.m4a -ar 16000 -ac 1 audio.wav

# 4. 转写
# 中文视频
whisper-cpp -m ggml-tiny.bin -f audio.wav -osrt --language Chinese
# 英文视频
whisper-cpp -m ggml-tiny.bin -f audio.wav -osrt --language English
```

## 注意事项

- exec默认timeout=1800秒（30分钟），足够处理40分钟视频
- 翻译：用LLM直接处理字幕内容
- 字幕库：my.feishu.cn/docx/I9P3dGDZioSJZlxfHwwclXcAnDe
