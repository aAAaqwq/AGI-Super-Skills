---
name: suno-create
description: "Create songs on Suno.com with custom lyrics and style. Use when user wants to (1) generate AI music on Suno with specific lyrics or theme, (2) create a song in a specific artist's style (e.g., G.E.M.邓紫棋), (3) download generated songs and send to Telegram. Triggers: create a song on Suno, generate a song, 用Suno创作歌曲, Suno创作, 下载Suno歌曲"
---

# Suno Create Skill

## Overview

Create songs on Suno.com by filling the form with lyrics + style and triggering generation. Download songs and send to Telegram.

## Workflow

### Step 1: Ensure Suno Login

Browser must be logged into Suno. If not logged in:
1. Navigate to suno.com
2. Click "Sign in" → Google OAuth login
3. Verify logged in (account name + credits visible in sidebar)

### Step 2: Navigate to Create Page

```bash
browser(action=navigate, url="https://suno.com/create")
sleep 5
```

### Step 3: Search for Correct Lyrics

If user provides lyrics → use provided lyrics.

If user provides song name → search online for correct lyrics:
- Try: `duckduckgo.com` search → find lyrics from mojigeci.com, kkbox.com, lyrics.com.tw
- Use browser to navigate to lyrics page, extract text content

Search URLs:
```
https://html.duckduckgo.com/html/?q={song_name}+歌词+{artist}
https://html.duckduckgo.com/html/?q={song_name}+lyrics+{artist}
```

### Step 4: Prepare Lyrics + Style

**Lyrics format for Suno** - Use clean text without formatting tags:
```
[Verse]
歌词内容...

[Chorus]
副歌内容...
```

**G.E.M. 邓紫棋 style prompt** (reference: `references/gem_style.md`):
```
G.E.M.邓紫棋风格, 强大的 belting 声乐, 沙哑音色, R&B 流行, 宽广音域, 情感化中文演唱, 呼吸感副歌, 灵魂情歌, 2000s-2020s 华语天后气质, 怀旧浪漫
```

### Step 5: Fill Form via Browser Evaluate

Use React-compatible input method (Suno uses React - plain fill/type won't work):

```javascript
// Fill lyrics
const LYRICS = `...`; // multi-line lyrics string

// Fill style
const STYLE = `G.E.M.邓紫棋风格, 强大的 belting 声乐...`;

browser(action=act, targetId="<current_targetId>", kind=evaluate, fn=r'''() => {
  const LYRICS = `...`;
  const STYLE = `...`;

  // Fill lyrics textarea
  const textareas = document.querySelectorAll('textarea');
  for (const ta of textareas) {
    const ph = ta.placeholder || '';
    if (ph.includes('lyrics') || ph.includes('Write some')) {
      Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, 'value').set.call(ta, LYRICS);
      ta.dispatchEvent(new Event('input', {bubbles: true}));
      ta.dispatchEvent(new Event('change', {bubbles: true}));
    }
  }

  // Fill style textarea (find by placeholder "Meditative" or existing "moody" value)
  for (const ta of textareas) {
    const ph = ta.placeholder || '';
    const val = ta.value || '';
    if (ph.includes('Meditative') || (val.includes('moody') && !val.includes('G.E.M.'))) {
      Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, 'value').set.call(ta, STYLE);
      ta.dispatchEvent(new Event('input', {bubbles: true}));
      ta.dispatchEvent(new Event('change', {bubbles: true}));
    }
  }

  // Click Create
  setTimeout(() => {
    const buttons = Array.from(document.querySelectorAll('button'));
    for (const btn of buttons) {
      const txt = btn.textContent.trim();
      if (txt === 'Create' || txt === 'Create song') {
        if (!btn.disabled) { btn.click(); }
        break;
      }
    }
  }, 500);

  return 'Done';
}''')
```

### Step 6: Wait for Generation

Wait 30-40 seconds, then take screenshot to verify:
```bash
sleep 35
browser(action=screenshot, targetId="<targetId>", fullPage=true)
```

New songs appear in right sidebar workspace.

### Step 7: Extract Song IDs

```javascript
// Get song IDs and titles from page
browser(action=act, kind=evaluate, fn=r'''() => {
  const songs = Array.from(document.querySelectorAll('a[href*="/song/"]')).map(a => {
    const match = a.href.match(/\/song\/([^\/]+)/);
    return match ? { title: a.textContent.trim(), id: match[1] } : null;
  }).filter(s => s);
  return JSON.stringify(songs.slice(0, 10));
}''')
```

### Step 8: Download Songs

Song audio URL pattern: `https://cdn1.suno.ai/{song_id}.mp3`

```bash
# Download song
curl -sL -o "/tmp/song_{id}.mp3" "https://cdn1.suno.ai/{song_id}.mp3"

# Copy to workspace for Telegram
cp "/tmp/song_{id}.mp3" "/home/aa/.openclaw/workspace-content/song_{id}.mp3"
```

### Step 9: Send to Telegram

```python
# Via message tool
message(action=send, channel="telegram", target="<chat_id>", 
        filePath="/home/aa/.openclaw/workspace-content/song_{id}.mp3",
        caption="🎵 {song_title}")
```

Or send links:
```python
message(action=send, channel="telegram", target="<chat_id>",
        message=f"🎵 {song_title}\n🎧 https://suno.com/song/{song_id}\n📥 https://cdn1.suno.ai/{song_id}.mp3")
```

## Key Notes

- **React synthetic events**: Suno's form inputs require `nativeInputValueSetter` + `input` event with `bubbles: true` to update React state
- **Credit cost**: Each Create = 10 credits (generates 2 versions)
- **Song IDs**: Each generated song has unique UUID, extract after page update
- **Download URL**: Always `https://cdn1.suno.ai/{id}.mp3` (verified working)
- **Browser stability**: If browser times out, restart with `browser(action=start)` then retry

## Troubleshooting

- **Form not filling**: Suno uses React - must use `evaluate` with `nativeInputValueSetter`
- **Create button disabled**: Check if lyrics textarea has content (may need proper line breaks)
- **Browser timeout**: Restart browser, re-navigate to suno.com/create
- **Wrong lyrics**: Always search for official lyrics first (song may have multiple versions)
