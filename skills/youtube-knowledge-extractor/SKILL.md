---
name: youtube-knowledge-extractor
description: >
  Multimodal YouTube video analysis through both audio (transcript) and visual (frame extraction + image analysis) channels.
  Especially powerful for HowTo videos, tutorials, demos, and explainer videos where what is SHOWN (screenshots, UI demos,
  diagrams, code, physical actions) is just as important as what is SAID. Use this skill whenever a user wants to analyze,
  summarize, or create step-by-step guides from YouTube videos, or when they share a YouTube URL and want to understand
  what happens in the video. Triggers on requests like "Analyze this YouTube video", "Create a step-by-step guide from
  this video", "What does this video show?", "Summarize this tutorial", or any YouTube URL shared with analysis intent.
version: 1.0.0
metadata:
  openclaw:
    requires:
      bins:
        - ffmpeg
        - python3
        - curl
    emoji: "🎬"
    os:
      - linux
      - macos
    install:
      - kind: uv
        package: yt-dlp
        bins: [yt-dlp]
---

# YouTube Video Analyzer — Multimodal

This skill performs deep analysis of YouTube videos through **both information channels**:
- **Audio channel**: Transcript with timestamps (what is SAID)
- **Visual channel**: Frame extraction + image analysis (what is SHOWN)

Most YouTube skills only extract transcripts. This skill closes the gap by **synchronizing visual frames with spoken content**, enabling accurate step-by-step guides where "click the blue button" is matched with the actual screenshot showing which button.

## Workflow Overview

```
YouTube URL
    |
    +---> 1. Get metadata (title, duration, video ID)
    |
    +---> 2. Extract transcript (yt-dlp --dump-json + curl)
    |         -> Timestamped segments
    |
    +---> 3. Extract frames (yt-dlp + ffmpeg)
    |         -> Keyframes at strategic intervals
    |
    +---> 4. Synchronize frames <-> transcript
    |         -> Match frames to spoken content by timestamp
    |
    +---> 5. Multimodal analysis
              -> Read each frame image, combine with transcript
              -> Generate structured output
```

## Step 1: Setup Working Directory

```bash
VIDEO_URL="<YOUTUBE_URL>"
WORK_DIR=$(mktemp -d /tmp/yt-analysis-XXXXXX)
mkdir -p "$WORK_DIR/frames"
```

## Step 2: Get Video Metadata

```bash
yt-dlp --print title --print duration --print id "$VIDEO_URL" 2>/dev/null
```

This returns three lines: title, duration in seconds, video ID. Store these for later use.

## Step 3: Extract Transcript

**IMPORTANT: Direct subtitle download via `--write-sub` frequently hits YouTube rate limits (HTTP 429).
Use the reliable two-step method below instead.**

### Step 3a: Get subtitle URL from video JSON

```bash
yt-dlp --dump-json "$VIDEO_URL" 2>/dev/null | python3 -c "
import json, sys
data = json.load(sys.stdin)
auto = data.get('automatic_captions', {})
subs = data.get('subtitles', {})

# Priority: manual subs > auto subs. Prefer user's language, fallback chain.
for source in [subs, auto]:
    for lang in ['en', 'de', 'en-orig', 'fr', 'es']:
        if lang in source:
            for fmt in source[lang]:
                if fmt.get('ext') == 'json3':
                    print(fmt['url'])
                    sys.exit(0)

# Fallback: take first available auto-caption, get json3 URL
for lang in sorted(auto.keys()):
    for fmt in auto[lang]:
        if fmt.get('ext') == 'json3':
            url = fmt['url']
            # Remove translation param to get original language
            import re
            url = re.sub(r'&tlang=[^&]+', '', url)
            print(url)
            sys.exit(0)

print('NO_SUBS', file=sys.stderr)
sys.exit(1)
" > "$WORK_DIR/sub_url.txt"
```

### Step 3b: Download and parse transcript

```bash
curl -s "$(cat "$WORK_DIR/sub_url.txt")" -o "$WORK_DIR/transcript.json3"
```

Verify it is valid JSON (not an HTML error page):

```bash
head -c 20 "$WORK_DIR/transcript.json3"
# Should start with { — if it starts with <html, retry after 10s sleep
```

### Step 3c: Parse json3 into readable timestamped segments

```bash
python3 -c "
import json

with open('$WORK_DIR/transcript.json3') as f:
    data = json.load(f)

for event in data.get('events', []):
    segs = event.get('segs', [])
    if not segs:
        continue
    start_ms = event.get('tStartMs', 0)
    duration_ms = event.get('dDurationMs', 0)
    text = ''.join(s.get('utf8', '') for s in segs).strip()
    if not text or text == '\n':
        continue
    s = start_ms / 1000
    e = (start_ms + duration_ms) / 1000
    print(f'[{int(s//60):02d}:{int(s%60):02d} - {int(e//60):02d}:{int(e%60):02d}] {text}')
" > "$WORK_DIR/transcript.txt"
```

Read `$WORK_DIR/transcript.txt` to get the full transcript with timestamps.

### Fallback: No transcript available

If no subtitles exist at all, inform the user and proceed with visual-only analysis.

## Step 4: Download Video and Extract Frames

### Step 4a: Download video (720p is sufficient for frame analysis)

```bash
yt-dlp -f "bestvideo[height<=720]+bestaudio/best[height<=720]" \
       -o "$WORK_DIR/video.mp4" "$VIDEO_URL"
```

### Step 4b: Get exact duration

```bash
DURATION=$(ffprobe -v quiet -show_entries format=duration -of csv=p=0 "$WORK_DIR/video.mp4")
```

### Step 4c: Extract frames using adaptive interval strategy

Choose interval based on video length:

| Duration | Interval | Approx. Frames | Rationale |
|----------|----------|-----------------|-----------|
| < 5 min | 10s | 20-30 | Dense enough for detailed analysis |
| 5-20 min | 20s | 15-60 | Good balance of coverage vs. volume |
| 20-60 min | 30-45s | 30-120 | Focus on key moments |
| > 60 min | 60s | 60-120+ | Ask user if they want to focus on specific sections |

```bash
# Example for a 5-20 minute video (interval=20):
ffmpeg -i "$WORK_DIR/video.mp4" -vf "fps=1/20" -q:v 3 "$WORK_DIR/frames/frame_%04d.jpg" 2>&1
```

**For scene-change-detection (software HowTos, UI demos):**

```bash
ffmpeg -i "$WORK_DIR/video.mp4" \
       -vf "select='gt(scene,0.3)',showinfo" \
       -vsync vfr -q:v 3 "$WORK_DIR/frames/scene_%04d.jpg" 2>&1
```

### Step 4d: Calculate timestamps for each frame

For fixed-interval extraction: frame N has timestamp `(N-1) * interval` seconds.

```
frame_0001.jpg -> 0:00
frame_0002.jpg -> 0:20
frame_0003.jpg -> 0:40
...
```

## Step 5: Synchronize Frames with Transcript

For each extracted frame:
1. Calculate the frame's timestamp in seconds
2. Find the transcript segment(s) covering that timestamp
3. Create a synchronized pair: `{timestamp, transcript_text, frame_path}`

This is done mentally or via a simple lookup — no external script needed.

## Step 6: Multimodal Analysis

### Step 6a: Read and analyze each frame

Use the `Read` tool (or `view` tool) to look at each frame image. For each frame, consider:

- **UI elements**: Buttons, menus, dialogs, settings panels visible
- **Text on screen**: Code, labels, error messages, URLs, terminal output
- **Diagrams/graphics**: Charts, flow diagrams, architecture drawings
- **Physical actions**: Hand positions, tool usage (for physical HowTos)
- **Changes**: What changed compared to the previous frame?

### Step 6b: Synthesize both channels

For each key moment, combine audio and visual:

```
Segment [TIMESTAMP]:
  SAID: "Click the blue button in the top right"
  SHOWN: Settings page screenshot, blue "Save" button highlighted
         in top-right corner, cursor pointing at it
  SYNTHESIS: -> On the Settings page, click the blue "Save" button
               in the top-right corner
```

### Step 6c: Identify visual-only information

Flag moments where the visual channel provides information NOT present in audio:
- Specific button names, menu paths, exact UI locations
- Code that is shown but not read aloud
- Error messages visible on screen
- Before/after comparisons

## Output Formats

Generate the appropriate format based on the user's request:

### Format A: Step-by-Step Guide (most common)

```markdown
# [Video Title] — Guide

## Step 1: [Action] (00:15)
[Description based on transcript + frame analysis]
> Visual: [What the screen/image shows at this point]

## Step 2: [Action] (00:42)
[...]
```

### Format B: Comprehensive Summary with Visual Anchors

```markdown
# [Video Title] — Summary

## Overview
[2-3 sentence summary of the entire video]

## Key Sections

### [Section Name] (00:00 - 02:30)
[Summary of this section]
- Key visual: [Description of what's shown]
- Key quote: "[Important spoken content]"

### [Section Name] (02:30 - 05:00)
[...]

## Key Takeaways
- [Takeaway 1]
- [Takeaway 2]
```

### Format C: Technical Detail Analysis

Separate analysis of both channels plus discrepancy detection:

```markdown
# [Video Title] — Technical Analysis

## Audio Channel Analysis
[What was said, key points, structure]

## Visual Channel Analysis
[What was shown, UI flows, code, diagrams]

## Channel Synchronization
[Where audio and visual complement each other]

## Visual-Only Information
[Important details only visible in frames, not mentioned in speech]
```

## Error Handling & Edge Cases

| Problem | Solution |
|---------|----------|
| HTTP 429 on subtitle download | Use `--dump-json` method (Step 3a). If curl also gets blocked, wait 10-15 seconds and retry with different User-Agent |
| No subtitles available at all | Proceed with visual-only analysis, inform user |
| Original audio language not in auto-captions list | The original language is the source — auto-captions are translations. Remove `&tlang=XX` from any auto-caption URL to get the original |
| `transcript.json3` contains HTML instead of JSON | YouTube returned an error page. Wait 10s, retry with: `curl -s --user-agent "Mozilla/5.0 (Windows NT 10.0; Win64; x64)" "$URL"` |
| Video > 60 min | Ask user if they want to focus on specific time ranges or chapters |
| Poor video quality / blurry frames | Extract more frames at tighter intervals to compensate |
| Video is age-restricted or private | Inform user that the video cannot be accessed. Suggest using `--cookies-from-browser` if they have access |
| yt-dlp download fails | Try alternative format: `-f "best[height<=720]"` without separate audio+video streams |

## Cleanup

After analysis is complete, remove temporary files:

```bash
rm -rf "$WORK_DIR"
```

## Tips for Best Results

- **Software HowTos**: Use scene-change detection — UI transitions create clear visual breaks
- **Physical HowTos**: Use tighter frame intervals (10-15s) — movements are subtler
- **Read the transcript first**: Identify "interesting timestamps" before extracting frames. Look for phrases like "as you can see here", "let me show you", "on the screen" — these signal important visual moments
- **Context-aware frame analysis**: When analyzing a frame, always provide the transcript context. The speaker often explains what's about to be shown
- **Batch frame reading**: Read frames in batches of 8-10 to maintain context across sequential frames and detect visual changes
- **Always extract both channels in parallel**: Start the video download while processing the transcript to save time
