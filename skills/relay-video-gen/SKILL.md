---
name: relay-video-gen
description: >
  Generate short videos via relay with provider priority fallback.
  Google Gemini Veo 3.1 (primary, direct API) → Xingjiabi (kling-video fallback).
  Async task-based: submit → poll → download. 4-8 second clips.
  Use when: creating video clips, marketing videos, animated content from text.
  Extensible: add providers by editing RELAY_PRIORITY in the script.
---

# Relay Video Generation

Multi-provider video generation with async polling and automatic model fallback.

## Quick Start

```bash
uv run ~/.openclaw/skills/relay-video-gen/scripts/relay_video_gen.py \
  -p "A rotating blue globe with stars in background" \
  -f "globe.mp4"
```

## Parameters

| Flag | Description | Default |
|------|-------------|---------|
| `-p` | Video prompt (English) | Required |
| `-f` | Output filename (.mp4) | Required |
| `-d` | Duration in seconds (3-15) | `5` |
| `-a` | Aspect ratio: `16:9`, `9:16`, `1:1` | `16:9` |
| `-m` | Override model name | `kling-video` |
| `-P` | Force provider | `xingjiabi` |

## Examples

```bash
# 10-second vertical video for Reels/TikTok
uv run ~/.openclaw/skills/relay-video-gen/scripts/relay_video_gen.py \
  -p "A person typing on laptop in coffee shop, warm lighting" \
  -f "coffee.mp4" -d 10 -a 9:16

# Use veo3.1 model
uv run ~/.openclaw/skills/relay-video-gen/scripts/relay_video_gen.py \
  -p "Ocean waves crashing on beach at sunset" \
  -f "ocean.mp4" -m veo3.1-fast
```

## Workflow

1. Submit generation request → get `task_id`
2. Poll every 5s until `completed` / `failed` (max 10 min)
3. Download video to output path
4. If model fails/saturated → auto-try next model

## Model Fallback Order

Gemini (veo-3.1-generate-preview, direct Google API) → xingjiabi: kling-video → veo-3.1-fast → veo-3.1 → minimax/video-01 → grok-video-3

## Provider Details

See [references/providers.md](references/providers.md) for API formats, model status, and how to add providers.
