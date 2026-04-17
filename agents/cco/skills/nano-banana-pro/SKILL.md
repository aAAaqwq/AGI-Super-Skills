---
name: nano-banana-pro
description: Generate/edit images with Nano Banana Pro (Gemini 3 Pro Image). Use for image create/modify requests incl. edits. Supports text-to-image + image-to-image; 1K/2K/4K; use --input-image.
---

# Nano Banana Pro Image Generation & Editing

Generate new images or edit existing ones using Google's Nano Banana Pro API (Gemini 3 Pro Image).

## Usage

Run scripts using absolute path (do NOT cd to skill directory first).

**⚡ MANDATORY: Always optimize prompt first before generating!**

### Step 1: Optimize Prompt (required)
```bash
OPTIMIZED=$(uv run ~/.openclaw/agents/content/agent/skills/nano-banana-pro/scripts/optimize_prompt.py \
  --prompt "用户原始描述" \
  --style photo|illustration|anime|oil-painting|3d|pixel|cinematic|watercolor)
```

### Step 2: Generate with optimized prompt
```bash
uv run ~/.openclaw/agents/content/agent/skills/nano-banana-pro/scripts/generate_image_boluobao.py \
  --prompt "$OPTIMIZED" --filename "output.png" [--resolution 1k|2k|4k] [--aspect-ratio 16:9]
```

Or using xingjiabiapi (primary):
```bash
uv run ~/.openclaw/agents/content/agent/skills/nano-banana-pro/scripts/generate_image.py \
  --prompt "$OPTIMIZED" --filename "output.png" [--resolution 1K|2K|4K] [--api-key KEY]
```

**Edit existing image (skip optimizer):**
```bash
uv run ~/.openclaw/agents/content/agent/skills/nano-banana-pro/scripts/generate_image.py \
  --prompt "editing instructions" --filename "output.png" --input-image "path/to/input.png"
```

**Important:** Always run from the user's current working directory.

## Default Workflow (optimize → draft → iterate → final)

Goal: optimize prompt first, then fast iteration.

1. **Optimize**: Run `optimize_prompt.py` to enhance user's description
2. **Draft (1K)**: Generate with optimized prompt at low res
3. **Iterate**: Adjust prompt or re-optimize if needed
4. **Final (4K)**: Only when satisfied with the result

```bash
# Step 1: Optimize
OPTIMIZED=$(uv run ~/.openclaw/agents/content/agent/skills/nano-banana-pro/scripts/optimize_prompt.py -p "一只在樱花树下的猫" -s photo)

# Step 2: Draft
uv run ~/.openclaw/agents/content/agent/skills/nano-banana-pro/scripts/generate_image_boluobao.py -p "$OPTIMIZED" -f "draft.png" -r 1k

# Step 3: Final (after approval)
uv run ~/.openclaw/agents/content/agent/skills/nano-banana-pro/scripts/generate_image_boluobao.py -p "$OPTIMIZED" -f "final.png" -r 4k
```

## Resolution Options

The Gemini 3 Pro Image API supports three resolutions (uppercase K required):

- **1K** (default) - ~1024px resolution
- **2K** - ~2048px resolution
- **4K** - ~4096px resolution

Map user requests to API parameters:
- No mention of resolution → `1K`
- "low resolution", "1080", "1080p", "1K" → `1K`
- "2K", "2048", "normal", "medium resolution" → `2K`
- "high resolution", "high-res", "hi-res", "4K", "ultra" → `4K`

## API Key

**Primary (xingjiabiapi / Google Gemini):**
1. `--api-key` argument
2. `GEMINI_API_KEY` environment variable

**Fallback (Boluobao 菠萝包):**
1. `--api-key` argument
2. `BOLUOBAO_API_KEY` environment variable
3. `pass show api/boluobao`

If the primary provider fails (quota/403/timeout), automatically switch to Boluobao fallback.

## Fallback: Boluobao Provider

When xingjiabiapi is unavailable, use the Boluobao script instead:

```bash
uv run ~/.openclaw/skills/nano-banana-pro/scripts/generate_image_boluobao.py \
  --prompt "your description" \
  --filename "output.jpg" \
  --resolution 2k \
  --aspect-ratio 16:9
```

**Boluobao-specific options:**
- `--aspect-ratio`: 1:1, 2:3, 3:2, 3:4, 4:3, 4:5, 5:4, 9:16, 16:9, 21:9
- `--input-image`: Pass image URLs (not local files) for editing, up to 14 images
- `--model`: Default `gemini-3-pro-image-preview`, can be changed if more models are added

**Decision logic:**
1. Try primary (xingjiabiapi) first
2. If fails → use `generate_image_boluobao.py` with same prompt/resolution

## Preflight + Common Failures (fast fixes)

- Preflight:
  - `command -v uv` (must exist)
  - `test -n \"$GEMINI_API_KEY\"` (or pass `--api-key`)
  - If editing: `test -f \"path/to/input.png\"`

- Common failures:
  - `Error: No API key provided.` → set `GEMINI_API_KEY` or pass `--api-key`
  - `Error loading input image:` → wrong path / unreadable file; verify `--input-image` points to a real image
  - "quota/permission/403" style API errors → wrong key, no access, or quota exceeded; try a different key/account

## Filename Generation

Generate filenames with the pattern: `yyyy-mm-dd-hh-mm-ss-name.png`

**Format:** `{timestamp}-{descriptive-name}.png`
- Timestamp: Current date/time in format `yyyy-mm-dd-hh-mm-ss` (24-hour format)
- Name: Descriptive lowercase text with hyphens
- Keep the descriptive part concise (1-5 words typically)
- Use context from user's prompt or conversation
- If unclear, use random identifier (e.g., `x9k2`, `a7b3`)

Examples:
- Prompt "A serene Japanese garden" → `2025-11-23-14-23-05-japanese-garden.png`
- Prompt "sunset over mountains" → `2025-11-23-15-30-12-sunset-mountains.png`
- Prompt "create an image of a robot" → `2025-11-23-16-45-33-robot.png`
- Unclear context → `2025-11-23-17-12-48-x9k2.png`

## Image Editing

When the user wants to modify an existing image:
1. Check if they provide an image path or reference an image in the current directory
2. Use `--input-image` parameter with the path to the image
3. The prompt should contain editing instructions (e.g., "make the sky more dramatic", "remove the person", "change to cartoon style")
4. Common editing tasks: add/remove elements, change style, adjust colors, blur background, etc.

## Prompt Handling

**For generation:** Pass user's image description as-is to `--prompt`. Only rework if clearly insufficient.

**For editing:** Pass editing instructions in `--prompt` (e.g., "add a rainbow in the sky", "make it look like a watercolor painting")

Preserve user's creative intent in both cases.

## Prompt Templates (high hit-rate)

Use templates when the user is vague or when edits must be precise.

- Generation template:
  - "Create an image of: <subject>. Style: <style>. Composition: <camera/shot>. Lighting: <lighting>. Background: <background>. Color palette: <palette>. Avoid: <list>."

- Editing template (preserve everything else):
  - "Change ONLY: <single change>. Keep identical: subject, composition/crop, pose, lighting, color palette, background, text, and overall style. Do not add new objects. If text exists, keep it unchanged."

## Output

- Saves PNG to current directory (or specified path if filename includes directory)
- Script outputs the full path to the generated image
- **Do not read the image back** - just inform the user of the saved path

## Examples

**Generate new image:**
```bash
uv run ~/.codex/skills/nano-banana-pro/scripts/generate_image.py --prompt "A serene Japanese garden with cherry blossoms" --filename "2025-11-23-14-23-05-japanese-garden.png" --resolution 4K
```

**Edit existing image:**
```bash
uv run ~/.codex/skills/nano-banana-pro/scripts/generate_image.py --prompt "make the sky more dramatic with storm clouds" --filename "2025-11-23-14-25-30-dramatic-sky.png" --input-image "original-photo.jpg" --resolution 2K
```
