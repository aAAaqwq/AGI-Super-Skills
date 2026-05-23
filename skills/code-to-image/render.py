#!/usr/bin/env python3
"""
Code-to-Image Renderer
将 HTML/CSS/JS 设计渲染为高清 PNG，零API成本。

Usage:
  python3 render.py <html_file> [options]
  python3 render.py index.html -o output.png -w 1080 -h 1440 --scale 2

Options:
  -o, --output     输出路径 (默认: {input}_render.png)
  -w, --width      视口宽度 (默认: 1080)
  -h, --height     视口高度 (默认: 1440)
  --scale          device_scale_factor, 1=1x 2=2x 4=4x (默认: 2)
  --format         输出格式 png|jpeg|webp (默认: png)
  --quality        JPEG/WebP 质量 0-100 (默认: 95)
  --selector       只截取特定元素 (CSS selector)
  --delay          渲染等待秒数 (默认: 1)
  --fullpage       截取完整页面而非viewport
"""

import argparse
import sys
import time
import os
from pathlib import Path

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print("❌ 请安装 playwright: pip install playwright && playwright install chromium")
    sys.exit(1)


def render(html_path, output_path, width, height, scale, fmt, quality,
           selector, delay, fullpage):
    """渲染 HTML 文件为图片"""

    abs_path = os.path.abspath(html_path)
    if not os.path.exists(abs_path):
        print(f"❌ 文件不存在: {abs_path}")
        sys.exit(1)

    file_url = f"file://{abs_path}"

    print(f"🎨 渲染: {html_path}")
    print(f"📐 尺寸: {width}×{height} @ {scale}x → {width*scale}×{height*scale}px")

    start = time.time()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(
            viewport={'width': width, 'height': height},
            device_scale_factor=scale
        )
        page.goto(file_url, wait_until='networkidle')
        time.sleep(delay)  # 等待动画/字体加载

        screenshot_opts = {
            'path': output_path,
            'type': fmt,
        }

        if fmt in ('jpeg', 'webp'):
            screenshot_opts['quality'] = quality

        if selector:
            element = page.locator(selector)
            element.screenshot(**screenshot_opts)
        elif fullpage:
            screenshot_opts['full_page'] = True
            page.screenshot(**screenshot_opts)
        else:
            page.screenshot(**screenshot_opts)

        browser.close()

    elapsed = time.time() - start
    file_size = os.path.getsize(output_path)
    size_kb = file_size / 1024
    size_mb = file_size / (1024 * 1024)

    actual_w = width * scale
    actual_h = height * scale

    print(f"✅ 完成: {output_path}")
    print(f"   📏 分辨率: {actual_w}×{actual_h} ({scale}x)")
    print(f"   📦 大小: {size_kb:.0f} KB" if size_kb < 1024 else f"   📦 大小: {size_mb:.1f} MB")
    print(f"   ⏱️  耗时: {elapsed:.1f}s")

    return output_path


def main():
    parser = argparse.ArgumentParser(
        description='HTML/CSS 设计 → 高清 PNG，零API成本',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python3 render.py cover.html
  python3 render.py poster.html -o poster.png -w 1440 -h 1920 --scale 4
  python3 render.py index.html --selector "#hero" --format webp --quality 90
        """
    )
    parser.add_argument('html', help='HTML 文件路径')
    parser.add_argument('-o', '--output', default=None, help='输出路径')
    parser.add_argument('-w', '--width', type=int, default=1080, help='视口宽度 (默认: 1080)')
    parser.add_argument('-H', '--height', type=int, default=1440, help='视口高度 (默认: 1440)')
    parser.add_argument('--scale', type=int, default=2, help='缩放倍数 (默认: 2)')
    parser.add_argument('--format', default='png', choices=['png', 'jpeg', 'webp'])
    parser.add_argument('--quality', type=int, default=95, help='JPEG/WebP 质量')
    parser.add_argument('--selector', default=None, help='CSS selector 截取特定元素')
    parser.add_argument('--delay', type=float, default=1.0, help='渲染等待秒数 (默认: 1)')
    parser.add_argument('--fullpage', action='store_true', help='截取完整页面')

    args = parser.parse_args()

    # 自动生成输出路径
    if args.output is None:
        stem = Path(args.html).stem
        args.output = f"{stem}_render.{args.format}"

    render(
        html_path=args.html,
        output_path=args.output,
        width=args.width,
        height=args.height,
        scale=args.scale,
        fmt=args.format,
        quality=args.quality,
        selector=args.selector,
        delay=args.delay,
        fullpage=args.fullpage,
    )


if __name__ == '__main__':
    main()
