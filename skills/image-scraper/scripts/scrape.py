#!/usr/bin/env python3
"""Download all images from a URL."""
import sys
import os
import re
import urllib.request
import urllib.error
from html.parser import HTMLParser
from urllib.parse import urljoin

class ImageParser(HTMLParser):
    def __init__(self, base_url):
        super().__init__()
        self.base_url = base_url
        self.images = []
    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)
        if tag == 'img':
            src = attrs_dict.get('src') or attrs_dict.get('data-src')
            if src:
                self.images.append(urljoin(self.base_url, src))
        if tag == 'source':
            src = attrs_dict.get('src')
            if src:
                self.images.append(urljoin(self.base_url, src))

def scrape_images(url, output_dir="images"):
    os.makedirs(output_dir, exist_ok=True)
    headers = {
        'User-Agent': 'Mozilla/5.0 (compatible; ImageScraper/1.0)',
        'Accept': 'text/html,application/xhtml+xml,image/webp,*/*',
    }
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            html = resp.read().decode('utf-8', errors='ignore')
            content_type = resp.headers.get('Content-Type', '')
    except (urllib.error.HTTPError, urllib.error.URLError) as e:
        print(f"Error fetching {url}: {e}")
        return []

    parser = ImageParser(url)
    try:
        parser.feed(html)
    except Exception:
        pass

    # Deduplicate
    seen = set()
    urls = []
    for img in parser.images:
        if img.startswith('//'):
            img = 'https:' + img
        if img.startswith('http') and img not in seen and not any(x in img.lower() for x in ['favicon', 'pixel', 'tracking', 'icon']):
            seen.add(img)
            urls.append(img)

    print(f"Found {len(urls)} images from {url}")
    downloaded = []
    for i, img_url in enumerate(urls):
        try:
            path = img_url.split('?')[0]
            ext = os.path.splitext(path)[1][:5] or '.jpg'
            if ext not in ['.jpg', '.jpeg', '.png', '.webp', '.gif', '.svg']:
                ext = '.jpg'
            fname = f"{output_dir}/img_{i:03d}{ext}"
            req = urllib.request.Request(img_url, headers=headers)
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = resp.read()
            with open(fname, 'wb') as f:
                f.write(data)
            size = len(data) / 1024
            print(f"  [{i+1}] {fname} ({size:.1f}KB)")
            downloaded.append(fname)
        except Exception as e:
            print(f"  [{i+1}] FAILED: {e}")
    return downloaded

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 scrape.py <URL> [output_dir]")
        sys.exit(1)
    url = sys.argv[1]
    output_dir = sys.argv[2] if len(sys.argv) > 2 else "images"
    results = scrape_images(url, output_dir)
    print(f"\nDone. Downloaded {len(results)} images to {output_dir}/")
