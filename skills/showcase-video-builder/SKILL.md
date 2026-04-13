---
name: showcase-video-builder
description: Build polished showcase and demo videos from screenshots, avatars, and text overlays using ffmpeg. Use when creating demo reels, hackathon presentations, product walkthroughs, or social media video content from static assets. Requires ffmpeg.
version: 1.0.0
metadata:
  {
      "openclaw": {
            "emoji": "\ud83c\udfac",
            "requires": {
                  "bins": [
                        "ffmpeg"
                  ],
                  "env": []
            },
            "primaryEnv": null,
            "network": {
                  "outbound": false,
                  "reason": "Local ffmpeg operations only. No external network calls."
            }
      }
}
---

# Showcase Video Builder

Turn screenshots and images into polished demo videos with Ken Burns pan/zoom effects, crossfade transitions, and text overlays. Built for hackathon teams and OSS projects that need showcase content without video editing software.

## Core Patterns

### Image Slideshow with Crossfades

```bash
ffmpeg -loop 1 -t 4 -i slide1.png \
       -loop 1 -t 4 -i slide2.png \
       -loop 1 -t 4 -i slide3.png \
       -filter_complex \
       "[0:v]scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2,setsar=1,fade=t=out:st=3:d=1[v0]; \
        [1:v]scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2,setsar=1,fade=t=in:st=0:d=1,fade=t=out:st=3:d=1[v1]; \
        [2:v]scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2,setsar=1,fade=t=in:st=0:d=1[v2]; \
        [v0][v1][v2]concat=n=3:v=1:a=0[out]" \
       -map "[out]" -c:v libx264 -pix_fmt yuv420p output.mp4
```

### Ken Burns (Slow Zoom)

```bash
# Slow zoom in over 5 seconds
ffmpeg -loop 1 -t 5 -i image.png -filter_complex \
  "scale=8000:-1,zoompan=z='min(zoom+0.0015,1.5)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=150:s=1920x1080:fps=30" \
  -c:v libx264 -pix_fmt yuv420p -t 5 zoomed.mp4
```

### Text Overlay

```bash
# macOS: use /System/Library/Fonts/Helvetica.ttc
ffmpeg -i input.mp4 -vf \
  "drawtext=text='Built in 48 Hours':fontfile=/System/Library/Fonts/Helvetica.ttc:fontsize=48:fontcolor=white:x=(w-text_w)/2:y=h-80:enable='between(t,2,5)'" \
  -c:v libx264 -c:a copy output.mp4
```

### Title Card (Solid Colour + Text)

```bash
ffmpeg -f lavfi -i "color=c=0x6366F1:s=1920x1080:d=3" -vf \
  "drawtext=text='Your Project Name':fontfile=/System/Library/Fonts/Helvetica.ttc:fontsize=72:fontcolor=white:x=(w-text_w)/2:y=(h-text_h)/2" \
  -c:v libx264 -pix_fmt yuv420p title.mp4
```

### Concatenate Segments

```bash
# Create concat list
echo "file 'title.mp4'" > concat.txt
echo "file 'slides.mp4'" >> concat.txt
echo "file 'closing.mp4'" >> concat.txt

ffmpeg -f concat -safe 0 -i concat.txt -c copy final.mp4
```

## Platform Tips

- **LinkedIn:** Autoplays muted — don't rely on audio. Use text overlays for key messages.
- **Twitter/X:** 2:20 max (free tier). 280 char caption limit. Media upload needs OAuth 1.0a.
- **Resize for embedding:** Avatars 150px, screenshots 600px, composites 700px. Keeps file under 5MB.

## Lessons

- **macOS font path:** `/System/Library/Fonts/Helvetica.ttc` — if drawtext fails, check this first
- **Always use `-pix_fmt yuv420p`** — without it, some players show a green screen
- **Ken Burns on large images is slow** — pre-scale to 2x target resolution, not 8x

## Files

- `scripts/build_showcase.sh` — Complete showcase builder script with configurable sections
