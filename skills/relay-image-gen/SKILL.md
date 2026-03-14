---
name: relay-image-gen
description: >
  Generate images via relay with provider priority fallback.
  Boluobao → Google Gemini direct → Xingjiabi (dall-e-3/gpt-image-1/imagen-4).
  Supports 1K/2K/4K, multiple aspect ratios, auto model fallback.
  Use when: creating images, generating pictures/illustrations from text, poster art.
  Extensible: add providers by editing RELAY_PRIORITY in the script.
---

# Relay Image Generation

Multi-provider image generation with automatic fallback.

## Quick Start

```bash
uv run ~/.openclaw/skills/relay-image-gen/scripts/relay_image_gen.py \
  -p "A serene Japanese garden with cherry blossoms" \
  -f "garden.jpg"
```

## Parameters

| Flag | Description | Default |
|------|-------------|---------|
| `-p` | Image prompt (English recommended) | Required |
| `-f` | Output filename | Required |
| `-r` | Resolution: `1k`, `2k`, `4k` | `1k` |
| `-a` | Aspect ratio (boluobao): `1:1 16:9 9:16` etc. | `1:1` |
| `-m` | Override model name | Provider default |
| `-P` | Force provider: `boluobao` or `xingjiabi` | Auto |

## Examples

```bash
# 4K landscape
uv run ~/.openclaw/skills/relay-image-gen/scripts/relay_image_gen.py \
  -p "Wide mountain sunset, cinematic" -f "sunset-4k.jpg" -r 4k -a 16:9

# Force xingjiabi with specific model
uv run ~/.openclaw/skills/relay-image-gen/scripts/relay_image_gen.py \
  -p "A robot waving hello" -f "robot.jpg" -P xingjiabi -m gpt-image-1
```

## Relay Priority

Default: boluobao → gemini → xingjiabi. Edit `RELAY_PRIORITY` in the script to reorder.
Gemini uses direct Google API (needs `api/google-ai-studio` in pass).
Xingjiabi auto-tries fallback models (dall-e-3 → gpt-image-1 → imagen-4).

## Provider Details

See [references/providers.md](references/providers.md) for API formats, model lists, and how to add providers.
