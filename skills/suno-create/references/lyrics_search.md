# Lyrics Search Guide

## Search Strategy

When user provides a song name but not lyrics, search online:

### Step 1: DuckDuckGo Search

URL pattern:
```
https://html.duckduckgo.com/html/?q={song_name}+歌词+{artist}
https://html.duckduckgo.com/html/?q={song_name}+lyrics
```

### Step 2: Extract Lyrics from Results

Look for these Chinese lyrics sites:
- mojigeci.com (魔镜歌词网)
- kkbox.com
- lyrics.com.tw
- geciyi.com
- lyrics.net.cn

### Step 3: Get Lyrics via Browser

Navigate to found URL, extract text:
```javascript
// In browser evaluate
const content = document.body.innerText;
// Extract between "歌词内容" and sharing buttons
```

## Chinese Lyrics Sites (Direct URL patterns)

- 魔镜歌词网: `https://mojigeci.com/zh-Hans/lyrics/{song_name}`
- KKBOX: `https://www.kkbox.com/tw/tc/song/{song_id}`
- 歌词网: `https://www.lyrics.com.tw/search.php?word={song_name}`

## Notes

- Some sites block web_fetch but work in browser
- Extract clean text without HTML tags
- For Suno: use clean verse/chorus format without markdown
