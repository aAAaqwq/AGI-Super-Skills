# arch-video-cut

Automatic Architecture Video Editing Workflow with Self-Learning Preferences

---

## Description

Automatically complete the full architecture video editing workflow: multi-video merging, speech-to-text subtitles, background music mixing, and dual output (landscape + portrait). Built-in self-learning system remembers your editing preferences.

**Core Features:**
- 🎬 Auto merge multiple videos + duration compression
- 🎙️ Speech transcription or custom subtitles
- 🎵 Smart background music generation + mixing
- 📱 Dual output: landscape (16:9) + portrait (3:4)
- 🧠 Self-evolving preference system

---

## Usage

### Quick Start

```bash
cd ~/.openclaw/workspace/skills/arch-video-cut
python3 scripts/full_workflow.py
```

### Prerequisites

1. **Install dependencies:**
```bash
brew install ffmpeg-full  # Required for libass subtitle support
pip3 install faster-whisper  # Optional: for speech transcription
```

2. **Prepare materials:**
- Audio file: `~/Desktop/新录音 XX.m4a` (narration voiceover)
- Video folder: `data/m1/` (architecture video clips to merge)

3. **Configure preferences (optional):**
```bash
python3 scripts/manage_preferences.py set
```

---

## Commands

| Command | Description |
|------|------|
| `python3 scripts/full_workflow.py` | Execute full editing workflow |
| `python3 scripts/manage_preferences.py show` | View current preferences |
| `python3 scripts/manage_preferences.py set` | Interactive preference editor |
| `python3 scripts/manage_preferences.py reset` | Reset to defaults |

---

## Configuration

### Preferences

Edit `config/user_preferences.json` or run `manage_preferences.py set`:

```json
{
  "video": {
    "target_duration": 20.0,      // Target duration in seconds
    "vertical_format": "3:4",     // Portrait aspect ratio
    "vertical_resolution": "1080x1440"
  },
  "subtitles": {
    "horizontal_font_size": 14,   // Landscape font size (px)
    "vertical_font_size": 10,     // Portrait font size (px)
    "font_name": "STHeiti",       // Font family
    "auto_wrap": true,            // Auto word wrap
    "margin_v": 30                // Bottom margin (px)
  },
  "audio": {
    "background_music_volume": 0.15,  // BGM volume (0-1)
    "fade_in_duration": 2,            // Fade-in duration (sec)
    "fade_out_duration": 2            // Fade-out duration (sec)
  }
}
```

### Custom Subtitles

Edit the `subtitles_text` array in `transcribe_audio()` function:

```python
subtitles_text = [
    "These six renovation projects were transformed from abandoned schools",
    "Historic buildings, red brick houses, tile-roof homes, single-story factories, and rural self-built houses",
    "Through minimalist design approaches and low-cost renovation strategies",
    "Giving old buildings new life",
    "While balancing contemporary aesthetics and market demands",
]
```

---

## Output

**Output location:** `data/` folder

| File | Description |
|------|------|
| `edited_video_final_with_subtitles.mp4` | Landscape version (16:9) |
| `edited_video_final_with_subtitles_3x4.mp4` | Portrait version (3:4) |

**Example output:**
```
✅ All done!
📁 Output: data/edited_video_final_with_subtitles.mp4
📊 Size: 16.0MB
🎬 Duration: 20.04 seconds
```

---

## Workflow

```
1. Merge videos → Compress to target duration
2. Generate subtitles → Allocate timeline based on audio duration
3. Generate BGM → Piano chords + fade in/out
4. Mix audio → Voiceover + background music
5. Burn subtitles → Landscape + Portrait versions
```

**Total processing time:** ~2-3 minutes (depends on video count and duration)

---

## Self-Learning

Built-in preference learning system automatically records your editing habits:

- 📝 Saves configuration after each edit
- 📊 Keeps last 20 adjustment records
- 🔄 Auto-applies preferences on next run
- 🎛️ Modify anytime via `manage_preferences.py`

**View learning history:**
```bash
python3 scripts/manage_preferences.py show
```

---

## Examples

### Example 1: Quick Edit
```bash
# Place 5 video clips in data/m1/
# Place voiceover audio at ~/Desktop/新录音 74.m4a
cd ~/.openclaw/workspace/skills/arch-video-cut
python3 scripts/full_workflow.py
```

### Example 2: Adjust Font Size
```bash
# Interactive modification
python3 scripts/manage_preferences.py set
# Input: horizontal font size 18px

# Re-edit with new font automatically applied
python3 scripts/full_workflow.py
```

### Example 3: Create 30-Second Version
```bash
# Modify preference
python3 scripts/manage_preferences.py set
# Input: target duration 30 seconds

# Edit
python3 scripts/full_workflow.py
```

---

## Troubleshooting

### ❌ ffmpeg-full not found
```bash
brew install ffmpeg-full  # Required for libass subtitle support
```

### ❌ Subtitles not showing
Check if `ffmpeg-full` is installed (system ffmpeg doesn't support libass)

### ❌ Transcription failed
```bash
pip3 install faster-whisper
# Or skip transcription and edit subtitle text directly in script
```

### ❌ Wrong video aspect ratio
Modify `vertical_format` in `config/user_preferences.json`

---

## Files

```
arch-video-cut/
├── SKILL.md                    # This file
├── SELF_LEARNING_GUIDE.md      # Self-learning detailed guide
├── README.md                   # Quick start guide
├── config/
│   └── user_preferences.json   # User preferences
├── scripts/
│   ├── full_workflow.py        # Main editing script
│   ├── preference_learner.py   # Preference learner
│   └── manage_preferences.py   # Preference manager
└── data/
    ├── m1/                     # Input video folder
    ├── temp_edit/              # Temporary files
    └── *.mp4                   # Output videos
```

---

## Version

**v1.0.0** - 2026-03-18

- ✅ Multi-video merge + duration compression
- ✅ Custom subtitle text
- ✅ Background music generation + mixing
- ✅ Landscape + Portrait dual output
- ✅ Self-evolving preference system

---

## Author

**WildUrban Architect - Linwangming**

**Website:** http://www.ual-studio.com/

---

_Make tools adapt to you, not you to tools._ 🧠
