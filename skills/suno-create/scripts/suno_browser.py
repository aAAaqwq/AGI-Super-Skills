#!/usr/bin/env python3
"""
Suno Browser Automation Script

Usage:
    python3 suno_browser.py --lyrics "歌词内容" --style "风格描述" [--click-create]

Requirements:
    pip install playwright
    playwright install chromium
"""

import argparse
import asyncio
import json
import sys
from playwright.async_api import async_playwright

DEFAULT_STYLE = "G.E.M.邓紫棋风格, 强大的 belting 声乐, 沙哑音色, R&B 流行, 宽广音域, 情感化中文演唱, 呼吸感副歌, 灵魂情歌, 2000s-2020s 华语天后气质, 怀旧浪漫"


async def fill_and_create(lyrics: str, style: str = DEFAULT_STYLE, click_create: bool = True, cdp_url: str = "http://127.0.0.1:18800"):
    """Fill Suno form and optionally click Create"""
    
    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp(cdp_url, timeout=10000)
        context = browser.contexts[0]
        
        # Find or create Suno page
        suno_page = None
        for page in context.pages:
            if "suno.com" in page.url:
                suno_page = page
                break
        
        if not suno_page:
            print("❌ No Suno page found. Please navigate to suno.com/create first.")
            return None
        
        await suno_page.bring_to_front()
        await suno_page.goto("https://suno.com/create")
        await asyncio.sleep(3)
        
        # Prepare lyrics with proper line breaks for Suno
        lyrics_formatted = lyrics.strip()
        
        # Fill lyrics
        fill_result = await suno_page.evaluate(f"""() => {{
            const LYRICS = `{lyrics_formatted}`;
            const STYLE = `{style}`;
            
            let filled = 0;
            const textareas = document.querySelectorAll('textarea');
            
            for (const ta of textareas) {{
                const ph = ta.placeholder || '';
                const val = ta.value || '';
                
                // Fill lyrics textarea
                if (ph.includes('lyrics') || ph.includes('Write some')) {{
                    Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, 'value').set.call(ta, LYRICS);
                    ta.dispatchEvent(new Event('input', {{bubbles: true}}));
                    ta.dispatchEvent(new Event('change', {{bubbles: true}}));
                    filled++;
                    console.log('✓ Lyrics filled');
                }}
                
                // Fill style textarea (placeholder "Meditative" or existing "moody" value)
                if (ph.includes('Meditative') || (val.includes('moody') && !val.includes('G.E.M.'))) {{
                    Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, 'value').set.call(ta, STYLE);
                    ta.dispatchEvent(new Event('input', {{bubbles: true}}));
                    ta.dispatchEvent(new Event('change', {{bubbles: true}}));
                    filled++;
                    console.log('✓ Style filled');
                }}
            }}
            
            return {{ filled, lyricsLength: LYRICS.length, styleLength: STYLE.length }};
        }}""")
        
        print(f"✅ Form filled: {fill_result}")
        
        if click_create:
            await asyncio.sleep(1)
            result = await suno_page.evaluate("""() => {
                const buttons = Array.from(document.querySelectorAll('button'));
                for (const btn of buttons) {
                    const txt = btn.textContent.trim();
                    if (txt === 'Create' || txt === 'Create song') {
                        if (!btn.disabled) {
                            btn.click();
                            console.log('✓ Create clicked');
                            return 'SUCCESS';
                        }
                        return 'DISABLED';
                    }
                }
                return 'NOT_FOUND';
            }""")
            print(f"🎵 Create button: {result}")
            return result
        
        return "READY_TO_CREATE"


async def get_songs(cdp_url: str = "http://127.0.0.1:18800") -> list:
    """Get list of songs from Suno page"""
    
    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp(cdp_url, timeout=10000)
        context = browser.contexts[0]
        
        suno_page = None
        for page in context.pages:
            if "suno.com" in page.url and "/song/" in page.url:
                suno_page = page
                break
        
        if not suno_page:
            # Try any suno page
            for page in context.pages:
                if "suno.com" in page.url:
                    suno_page = page
                    break
        
        if not suno_page:
            print("❌ No Suno page found")
            return []
        
        songs = await suno_page.evaluate("""() => {
            const links = Array.from(document.querySelectorAll('a[href*="/song/"]'));
            const seen = new Set();
            const songs = [];
            
            for (const a of links) {
                const match = a.href.match(/\\/song\\/([^\\/]+)/);
                if (match && !seen.has(match[1])) {
                    seen.add(match[1]);
                    const title = a.textContent.trim() || 'Untitled';
                    songs.push({ id: match[1], title: title, url: a.href });
                }
            }
            return songs.slice(0, 20);
        }""")
        
        return songs


async def download_song(song_id: str, output_path: str = "/tmp/song_{id}.mp3") -> str:
    """Download song from Suno CDN"""
    import urllib.request
    import os
    
    url = f"https://cdn1.suno.ai/{song_id}.mp3"
    output = output_path.replace("{id}", song_id)
    
    try:
        urllib.request.urlretrieve(url, output)
        size = os.path.getsize(output)
        print(f"✅ Downloaded: {output} ({size} bytes)")
        return output
    except Exception as e:
        print(f"❌ Download failed: {e}")
        return None


def main():
    parser = argparse.ArgumentParser(description="Suno Browser Automation")
    parser.add_argument("--lyrics", "-l", required=True, help="Song lyrics")
    parser.add_argument("--style", "-s", default=DEFAULT_STYLE, help="Style prompt")
    parser.add_argument("--click-create", "-c", action="store_true", help="Click Create button")
    parser.add_argument("--cdp-url", default="http://127.0.0.1:18800", help="CDP URL")
    parser.add_argument("--get-songs", action="store_true", help="Get songs from page")
    
    args = parser.parse_args()
    
    if args.get_songs:
        songs = asyncio.run(get_songs(args.cdp_url))
        print(json.dumps(songs, indent=2, ensure_ascii=False))
    else:
        result = asyncio.run(fill_and_create(
            lyrics=args.lyrics,
            style=args.style,
            click_create=args.click_create,
            cdp_url=args.cdp_url
        ))
        print(result)


if __name__ == "__main__":
    main()
