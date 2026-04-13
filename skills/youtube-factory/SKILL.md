---
name: youtube-factory
description: Generate complete YouTube videos from a single prompt - script, voiceover, stock footage, captions, thumbnail. Self-contained, no external modules. 100% free tools.
version: 1.3.0
author: Mayank8290
homepage: https://github.com/Mayank8290/openclaw-video-skills
tags: video, youtube, content-creation, tts, automation, faceless
metadata: { "openclaw": { "requires": { "bins": ["ffmpeg", "edge-tts"], "env": ["PEXELS_API_KEY"] }, "primaryEnv": "PEXELS_API_KEY" } }
---

# YouTube Factory

Generate complete YouTube videos from a single prompt. Script, voiceover, stock footage, captions, thumbnail - all automated.

**100% FREE tools** - No expensive APIs required.

> **Love this skill?** Support the creator and help keep it free: **[Buy Me a Coffee](https://buymeacoffee.com/mayank8290)**

## What This Skill Does

Turn any topic into a publish-ready YouTube video:

1. **Script Generation** - Uses your LLM to write engaging scripts
2. **Voiceover** - Free Microsoft Edge TTS (natural-sounding voices)
3. **Stock Footage** - Auto-fetches relevant B-roll from Pexels (free)
4. **Video Assembly** - FFmpeg combines everything seamlessly
5. **Captions** - Styled subtitles burned into video
6. **Thumbnail** - Auto-generated clickable thumbnail

## Quick Start

```
Create a YouTube video about "5 Morning Habits of Successful People"
```

```
Make a faceless YouTube video:
- Topic: How AI is changing healthcare
- Style: Documentary
- Length: 8 minutes
- Voice: Professional male
```

## Commands

### Generate Full Video
```
/youtube-factory [topic]
```
Creates complete video with all elements.

### Script Only
```
/youtube-factory script [topic] --length [minutes]
```
Just generates the script for review/editing.

### Custom Voice
```
/youtube-factory [topic] --voice [voice-name]
```

Available free voices:
- `en-US-ChristopherNeural` - Male, professional (default)
- `en-US-JennyNeural` - Female, friendly
- `en-US-GuyNeural` - Male, casual
- `en-US-AriaNeural` - Female, news anchor
- `en-GB-SoniaNeural` - British female
- `en-AU-NatashaNeural` - Australian female

### Video Styles
```
/youtube-factory [topic] --style [style]
```

Styles:
- `documentary` - Serious, informative (default)
- `listicle` - "Top 10" format with clear sections
- `tutorial` - Step-by-step instructional
- `story` - Narrative/storytelling format

### Shorts Mode (Vertical 9:16)
```
/youtube-factory [topic] --shorts
```
Creates 60-second vertical video for YouTube Shorts, TikTok, Reels.

## Output Files

After generation, you'll find in `~/Videos/OpenClaw/`:

```
your-video-title/
├── script.md          # The full script
├── voiceover.mp3      # Audio track
├── video_raw.mp4      # Without captions
├── video_final.mp4    # With captions (upload this!)
├── thumbnail.jpg      # YouTube thumbnail
└── metadata.json      # Title, description, tags
```

## Requirements

- Free Pexels API key (get at https://pexels.com/api)
- FFmpeg installed (`brew install ffmpeg`)
- Edge TTS (`pip install edge-tts`)

## Setup

```bash
# Install dependencies
brew install ffmpeg
pip install edge-tts pillow python-dotenv requests

# Add Pexels API key
echo "PEXELS_API_KEY=your_key" >> ~/.openclaw-video-skills/config.env
```

## Monetization

| Method | Potential |
|--------|-----------|
| Fiverr/Upwork service | $200-500/video |
| Monthly retainer | $1,500-3,000/client |
| Your own channels | $2,000-10,000/mo AdSense |
| Sell this skill | $50-150 on ClawHub |

## Examples

### Faceless Finance Channel
```
Create a 10-minute YouTube video about "The Psychology of Money"
Style: Documentary
Include 5 key lessons
Professional male voice
```

### Quick Shorts
```
Make a YouTube Short about a surprising fact about sleep
```

### Tutorial Content
```
Generate a tutorial video:
Topic: How to Start Investing with $100
Length: 12 minutes
Style: Tutorial with clear steps
Voice: Friendly female
```

---

## Support This Project

If this skill saved you time or made you money, consider buying me a coffee!

**[Buy Me a Coffee](https://buymeacoffee.com/mayank8290)**

Every coffee helps me build more free tools for the community.

---

Built for OpenClaw | 100% Free Tools | [Support the Creator](https://buymeacoffee.com/mayank8290)
