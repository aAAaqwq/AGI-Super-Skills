---
name: av-sync-workflow
description: "Audio-to-video synchronization workflow: analyze audio (beats, tempo, emotion, mood), find/match video clips to match scene and feeling, sync cuts to music beats, generate beat-marked videos. Use when user wants to: (1) turn a song into a music video, (2) sync video clips to music beats, (3) create a video that matches audio mood/scene/rhythm, (4) do beat-matching video editing. Triggers: \"制作音乐视频\", \"音频转视频\", \"beat matching\", \"卡点视频\", \"音视频同步\", \"视频踩点\", \"music video creation\", \"sync video to audio\""
---

# AV-Sync Workflow

Transform audio into a professionally edited video synchronized to beats, mood, and scene.

## Workflow Overview

```
Audio → Analysis → Clip Matching → Beat Sync → Video Assembly → Export
```

## Step 1: Analyze Audio

Use `scripts/audio_analysis.py` to extract:
- **Beats/BPM**: Timestamp of each beat, overall tempo (BPM)
- **Sections**: Verse, chorus, bridge, outro markers
- **Emotion/Mood**: Energy level, valence (happy/sad), tempo category
- **Key moments**: High-impact points (drops, climaxes, transitions)

```bash
python3 scripts/audio_analysis.py /path/to/song.mp3 --output /tmp/analysis.json
```

Output structure:
```json
{
  "bpm": 120,
  "duration": 214,
  "beats": [0.0, 0.5, 1.0, ...],
  "sections": [
    {"type": "intro", "start": 0, "end": 15},
    {"type": "verse", "start": 15, "end": 45},
    {"type": "chorus", "start": 45, "end": 75}
  ],
  "mood": {"energy": 0.7, "valence": 0.6, "danceability": 0.8},
  "key_moments": [
    {"time": 45.0, "type": "chorus_drop", "intensity": 1.0}
  ]
}
```

## Step 2: Gather Video Clips

User provides video clips OR search for stock footage:

**Stock footage sources:**
- Pexels: `https://www.pexels.com/search/videos/{query}/`
- Pixabay: `https://pixabay.com/videos/search/{query}/`
- Coverr: `https://coverr.co/search/{query}`

**Download stock video:**
```bash
# Via yt-dlp (for pexels/pixabay)
yt-dlp -f "best[height<=1080]" -o "/tmp/clip_%(id)s.%(ext)s" "https://pexels.com/video/12345"

# Via direct URL
ffmpeg -i "https://example.com/video.mp4" -c copy /tmp/clip.mp4
```

## Step 3: Analyze Each Clip

For each clip, extract:
- Scene type (indoor/outdoor, city/nature, close-up/wide)
- Mood/style (energetic/calm, happy/sad)
- Duration and cut points
- Visual elements (faces, motion, colors)

```bash
python3 scripts/video_analysis.py /tmp/clip.mp4 --output /tmp/clip_analysis.json
```

## Step 4: Match Clips to Audio Sections

Algorithm: Map clips to audio sections based on:
1. **Emotion matching**: High-energy chorus → energetic clips
2. **Scene continuity**: Smooth transitions between scenes
3. **Beat alignment**: Cut on beats for rhythm
4. **Length fit**: Clip duration matches section duration

```bash
python3 scripts/match_clips.py \
  --audio-analysis /tmp/analysis.json \
  --clips /tmp/clip1.mp4,/tmp/clip2.mp4 \
  --clip-analyses /tmp/clip1_analysis.json,/tmp/clip2_analysis.json \
  --output /tmp/edit_plan.json
```

## Step 5: Generate Beat-Synced Video

```bash
python3 scripts/assemble_video.py \
  --edit-plan /tmp/edit_plan.json \
  --audio /path/to/song.mp3 \
  --output /tmp/final_video.mp4 \
  --format mp4 \
  --codec h264 \
  --quality high
```

## Reference Scripts

### `scripts/audio_analysis.py`

Analyzes audio file using librosa. Extracts:
- Beat timestamps (per-beat and bar-level)
- BPM
- Onset strength envelope
- Spectral features for mood
- librosa-beat-grid output option

### `scripts/video_analysis.py`

Analyzes video clip:
- Dominant colors / color mood
- Scene type classification (urban, nature, indoor, etc.)
- Motion level (static, moderate, high)
- Detected faces / people
- Suggested cut points (scene changes)

### `scripts/match_clips.py`

Intelligent clip-to-audio matching:
- Emotion/mood alignment scoring
- Scene variety ensuring no repetitive cuts
- Beat-synced cut point optimization
- Output: detailed edit decision list (EDL)

### `scripts/assemble_video.py`

Final video assembly:
- Apply cut points from edit plan
- Add smooth transitions (dissolve, fade)
- Add slow-motion on climactic beats
- Mix audio track
- Export at specified quality

## Beat-Sync Cut Points

For every beat in the audio, consider:
- **Strong beat (bar 1)**: Major cut or transition
- **Weak beat (bar 2-4)**: Minor cut or no cut
- **Off-beat**: Effect triggers (zoom, flash)

Standard cut cadence:
- 4-beat bars: Cut every 4 or 8 beats
- Chorus: Cut every 2 beats for high energy
- Outro: Gradual slowdown, fade

## Quick Start (Minimal)

If user provides just audio + one video:
```bash
# 1. Detect beats
python3 scripts/audio_analysis.py song.mp3 -o beats.json

# 2. Simple beat-sync assembly
python3 scripts/simple_sync.py --audio song.mp3 --clip video.mp4 --beats beats.json -o output.mp4
```

## Quality Settings

| Quality | Resolution | Bitrate | Use Case |
|---------|------------|---------|----------|
| draft | 720p | 2Mbps | Quick preview |
| standard | 1080p | 5Mbps | Social media |
| high | 1080p | 10Mbps | YouTube |
| premium | 4K | 20Mbps | Final output |

## Key Notes

- **FFmpeg required**: Most scripts depend on ffmpeg being installed
- **Audio duration vs video clips**: If clips shorter than audio, loop or find more clips
- **BPM > 140**: Consider half-time editing for drop-songs
- **Transitions**: Default is cut-only (beat-sync), add dissolves for chorus sections
- **Mood input**: If user specifies mood (e.g., "sad, rainy, nostalgic"), prioritize that over automatic analysis

## Troubleshooting

- **No beats detected**: Audio may be recorded poorly; try --spectral mode
- **Clip too short**: Auto-loop small clips up to 3x original length
- **Aspect ratio mismatch**: Automatically crop/pad to 16:9 or 9:16 for reels
