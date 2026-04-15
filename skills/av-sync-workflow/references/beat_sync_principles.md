# Beat Sync Video Editing Principles

## Beat Detection

### Using librosa (Python)

```python
import librosa

y, sr = librosa.load("song.mp3")
tempo, beats = librosa.beat.beat_track(y=y, sr=sr)
beat_times = librosa.frames_to_time(beats, sr=sr)

# Save for ffmpeg
with open("beats.txt", "w") as f:
    for t in beat_times:
        f.write(f"{t:.3f}\n")
```

### Using FFmpeg (no Python)

```bash
# Beat detection via audio analysis
ffmpeg -i song.mp3 -filter_complex "aformat=channel_layouts=mono,showwavespic=s=1920x1080" -frames:v 1 output.png

# Or use beat-detect filter
ffmpeg -i song.mp3 -af "abitscope=rl=0:s=800x400,ametadata=print:key=lavfi.abitscope.peak:file=peaks.txt"
```

## Cut Point Principles

### Beat Strength Levels

| Level | Description | Cut Type |
|-------|-------------|----------|
| 1 | Downbeat (bar 1) | Hard cut, transition |
| 2 | Off-beat (bar 2-4) | Soft cut |
| 3 | In-beat subdivisions | No cut, add effect |
| 4 | Rest/silence | Always cut |

### Music Section Cut Strategy

**Intro (0-15s)**
- Slow buildup: Cut every 4-8 beats
- Establish mood: Wide shots, ambient clips

**Verse**
- Moderate energy: Cut every 4 beats
- Lyrics-focused: Medium shots

**Pre-Chorus**
- Building tension: Cut every 2-4 beats
- Start with wider, end tighter

**Chorus (High Energy)**
- Fast cuts: Every 1-2 beats
- Most dynamic clips
- Add motion effects (zoom, pan)

**Bridge**
- Contrast: Change scene type
- Slower cuts: Every 8 beats

**Outro**
- Wind down: Fade out
- Final beat: Slow-mo or hold frame

## Timing Formulas

```
beat_interval = 60 / bpm  (seconds per beat)
bar_duration = beat_interval * 4  (4/4 time)

# For N-beat cuts:
cut_every_N_beats = 4  # options: 1, 2, 4, 8
cut_interval = beat_interval * cut_every_N_beats
```

## Scene Matching Heuristics

### Energy Curve

Map video motion to audio energy:
```
high_energy (>0.7): Fast motion, cuts, zooms
medium_energy (0.4-0.7): Moderate motion, standard cuts
low_energy (<0.4): Static shots, slow pans, no cuts
```

### Emotional Matching

| Audio Mood | Video Style |
|------------|-------------|
| Sad, melancholy | Rain, night, isolated subjects |
| Happy, upbeat | Sunshine, crowd, movement |
| Romantic | Close-ups, warm colors, soft focus |
| Epic, dramatic | Wide landscapes, slow motion |
| Dark, intense | Urban night, high contrast |
| Chill, calm | Nature, minimal motion |

## Transition Timing

### On-Beat Transitions

Place transitions (cuts, dissolves) exactly on beat timestamps:

```bash
# FFmpeg concat with silence (example concept)
ffmpeg -i clip1.mp4 -i clip2.mp4 -filter_complex \
  "[0:v]trim=0:2.5,setpts=PTS-STARTPTS[v1];
   [1:v]trim=0:3.0,setpts=PTS-STARTPTS[v2];
   [v1][v2]concat=n=2:v=1:a=0[out]" \
  -map "[out]" output.mp4
```

### Cross-Dissolve on Beats

For chorus sections, use 0.3-0.5s cross-dissolves on strong beats:
```
dissolve_start = beat_time - 0.15
dissolve_end = beat_time + 0.15
```
