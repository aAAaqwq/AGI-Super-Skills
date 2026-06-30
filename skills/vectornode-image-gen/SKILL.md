---
name: vectornode-image-gen
description: "GPT image generation/editing via VectorNode relay; auto-routes token vs per-request billing based on prompt length."
allowed-tools: [exec, read, write]
user-invocable: true
---

# VectorNode Image Generation

GPT Image (gpt-image-2) generation and editing via VectorNode relay API.
Auto-routing: short prompts → token billing · long prompts → per-request billing.

## Trigger

Use when: "生成图片", "generate image", "create illustration", "画一张", "编辑图片", "edit image", "GPT生图", "gpt image".

## Quick Start

```bash
# Generation (auto-route billing)
python3 ~/.openclaw/skills/vectornode-image-gen/scripts/vectornode_gen.py \
  -p "你的提示词" \
  -o "/path/to/output.png"

# Edit existing image
python3 ~/.openclaw/skills/vectornode-image-gen/scripts/vectornode_gen.py \
  -p "add a sunset background" \
  -i "/path/to/input.png" \
  -o "/path/to/output.png"

# Force billing mode
python3 ~/.openclaw/skills/vectornode-image-gen/scripts/vectornode_gen.py \
  -p "long detailed prompt..." \
  -o "/path/to/output.png" \
  --billing per-request  # or token
```

## Routing Logic

| Prompt Length | Billing | Model | Best For |
|---|---|---|---|
| < 300 chars | Token | `gpt-image-2` | Simple prompts, quick iterations |
| ≥ 300 chars | Per-request | `gpt-image-2-all` | Detailed prompts, content covers |

Threshold configurable via `VECTORNODE_ROUTE_THRESHOLD` env var (default: 300).

## Parameters

| Flag | Required | Default | Description |
|---|---|---|---|
| `-p, --prompt` | ✅ | — | Image prompt (max 1000 chars for gen) |
| `-o, --output` | ✅ | — | Output file path (.png/.jpg/.webp) |
| `-i, --image` | ❌ | — | Input image for edit mode |
| `-m, --mask` | ❌ | — | Mask image for edit (transparent areas = edit zone) |
| `-s, --size` | ❌ | `1024x1024` | `1024x1024`, `1536x1024`, `1024x1536`, `2048x2048`, etc. |
| `-n, --count` | ❌ | `1` | Number of images (1-10) |
| `-q, --quality` | ❌ | `auto` | `low`, `medium`, `high`, `auto` |
| `--billing` | ❌ | `auto` | `auto`, `token`, `per-request` |
| `--background` | ❌ | `auto` | `opaque`, `transparent`, `auto` (edit mode only) |
| `--moderation` | ❌ | `auto` | `low`, `auto` |

## API Endpoints

| Mode | Endpoint | Method | Content-Type |
|---|---|---|---|
| Generate | `/v1/images/generations` | POST | `application/json` |
| Edit | `/v1/images/edits` | POST | `multipart/form-data` |

## Configuration

API credentials read from (in priority order):
1. Environment variables: `VECTORNODE_API_KEY`, `VECTORNODE_BASE_URL`
2. `~/.openclaw/workspace/.env` file

## Supported Sizes

- `1024x1024` — Square (default)
- `1536x1024` — Landscape 3:2
- `1024x1536` — Portrait 2:3
- `2048x2048` — 2K Square
- `2048x1152` — 2K Landscape
- `3840x2160` — 4K Landscape
- `2160x3840` — 4K Portrait
- `auto` — Model decides

Constraints: max dimension ≤ 3840px, aspect ratio ≤ 3:1, pixel range 655360–8294400.

## Output Formats

`png`, `jpeg`, `webp`. Transparent background requires `png` or `webp` + `--background transparent`.

## Workflow

1. Determine mode: has `-i` → edit, otherwise → generate
2. Auto-route billing if `--billing auto`:
   - Prompt < threshold chars → token billing (`gpt-image-2`)
   - Prompt ≥ threshold chars → per-request (`gpt-image-2-all`)
3. Call API, decode base64 response, save to output path
4. Return output path for downstream use

## Integration with Content Workflow

When generating content covers, combine with **content-cover-gen** skill for prompt design:

```
1. Read content-cover-gen SKILL.md for visual metaphor methodology
2. Design prompt with visual metaphor + Chinese text
3. Call vectornode-image-gen with the designed prompt
4. Use output image as article cover
```

## Error Handling

- API errors surfaced with HTTP status + response body
- Network timeout: 120s
- Retry: 1 automatic retry on 5xx
- Invalid image format: validated before upload (PNG < 50MB, mask PNG < 4MB)
