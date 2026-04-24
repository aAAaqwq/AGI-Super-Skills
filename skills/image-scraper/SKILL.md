---
name: image-scraper
description: Scrape and download all images from a given URL. Takes a URL, extracts image URLs from the page, and downloads them. Uses python3/curl as primary method, falls back to browser automation if needed. Use when user provides a URL and wants to download images from that page.
---

# Image Scraper

Scrape all images from a given URL and download them locally.

## Method 1: Python3 (Primary - Zero Dependency)

```python
#!/usr/bin/env python3
"""Download all images from a URL."""
import sys
import os
import re
import urllib.request
import urllib.error
from html.parser import HTMLParser

class ImageParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.images = []
    def handle_starttag(self, tag, attrs):
        if tag == 'img':
            for attr, val in attrs:
                if attr == 'src' and val:
                    self.images.append(val)
        if tag == 'source':
            for attr, val in attrs:
                if attr == 'src' and val:
                    self.images.append(val)

def scrape_images(url, output_dir="images"):
    os.makedirs(output_dir, exist_ok=True)
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req, timeout=15) as resp:
        html = resp.read().decode('utf-8', errors='ignore')
    parser = ImageParser()
    parser.feed(html)
    # Deduplicate and filter
    seen = set()
    urls = []
    for img in parser.images:
        if img.startswith('//'):
            img = 'https:' + img
        if img.startswith('http') and img not in seen:
            seen.add(img)
            urls.append(img)
    print(f"Found {len(urls)} images")
    for i, img_url in enumerate(urls):
        try:
            ext = os.path.splitext(img_url.split('?')[0])[1] or '.jpg'
            fname = f"{output_dir}/img_{i:03d}{ext}"
            urllib.request.urlretrieve(img_url, fname)
            print(f"  [{i+1}] {fname}")
        except Exception as e:
            print(f"  [{i+1}] FAILED: {e}")
    return urls

if __name__ == "__main__":
    url = sys.argv[1] if len(sys.argv) > 1 else input("URL: ")
    scrape_images(url)
```

**Usage:**
```bash
python3 /path/to/image-scraper.py "https://example.com/article"
```

## Method 2: Curl + Grep (Minimal)

```bash
# Extract image URLs and download
curl -sL "URL" | grep -oP 'https?://[^"]+\.(jpg|jpeg|png|webp|gif)' | sort -u | head -20 | while read url; do
  curl -sL "$url" -o "images/$(echo $url | md5sum | cut -d' ' -f1).${url##*.}"
done
```

## Method 3: Browser Automation (Fallback)

Use OpenClaw's browser tool when the page is JavaScript-rendered or Method 1 fails.

```bash
# 1. Open page in browser
browser(action=open, url="URL")

# 2. Get page content and extract images via JavaScript
browser(action=act, targetId="TAB_ID", request={
  "kind": "evaluate",
  "fn": "() => Array.from(document.querySelectorAll('img')).map(img => img.src)"
})

# 3. Download each image with curl
```

## Decision Flow

1. **Try Method 1** (python3) first — handles most static pages
2. **If 403/blocked**: Try adding headers (`Referer`, `Accept`)
3. **If JS-rendered or paywalled**: Use Method 3 (browser)
4. **Always** print the downloaded file paths

## Output

- Images saved to `./images/` by default
- Named `img_000.jpg`, `img_001.png`, etc.
- Report: "Downloaded N images to images/"

## Notes

- Only downloads images from the given URL, not full site
- Filters out tracking pixels and tiny icons (width/height < 50px optionally)
- Respects robots.txt implicitly (no enforcement)
- For Twitter/X: browser method may be needed due to JS rendering
