#!/usr/bin/env python3
"""
code-material-gen v2.1 — 紧凑暖色调配图素材

设计原则: 丰满紧凑、无多余留白、统一暖色调、中文手写字体。
"""

import argparse, os
from playwright.sync_api import sync_playwright

FONT_DIR = os.path.expanduser("~/.fonts/chinese-handwriting")
FONT_MAP = {
    "MaShanZheng": "MaShanZheng-Regular.ttf",
    "ZCOOLKuaiLe": "ZCOOLKuaiLe-Regular.ttf",
    "LiuJianMaoCao": "LiuJianMaoCao-Regular.ttf",
    "ZhiMangXing": "ZhiMangXing-Regular.ttf",
}

def get_font_css(font_name):
    f = FONT_MAP.get(font_name, FONT_MAP["MaShanZheng"])
    fp = os.path.join(FONT_DIR, f)
    if not os.path.exists(fp):
        for v in FONT_MAP.values():
            alt = os.path.join(FONT_DIR, v)
            if os.path.exists(alt):
                fp = alt
                break
    return f"@font-face{{font-family:'H';src:url('file://{fp}');font-display:swap;}}"

# ── Warm palette (only one, Daniel said 简洁暖色) ──
P = {
    "bg": "#fdf8f0", "bg2": "#f9f0e3", "card": "#ffffff",
    "border": "#e8ddd0", "text": "#2d1f10", "sub": "#7a6555",
    "accent": "#c2410c", "accent2": "#9a3412", "gold": "#d97706",
    "red": "#b91c1c", "green": "#15803d",
    "tag": "#fff7ed", "tag2": "#fef3c7",
    "grad": "linear-gradient(135deg,#c2410c,#9a3412)",
    "grad2": "linear-gradient(135deg,#d97706,#c2410c)",
    "shadow": "0 2px 12px rgba(45,31,16,0.08)",
    "font": "'H','Noto Sans CJK SC','PingFang SC',sans-serif",
}

# ── Renderers ──────────────────────────────────────────────

def render_timeline(title, items, size):
    w, h = size.split("x")
    cards = ""
    colors = [P["accent"], P["gold"], P["green"]]
    for i, item in enumerate(items):
        parts = item.split(":", 1)
        label = parts[0] if len(parts) > 1 else f"第{i+1}步"
        desc = parts[1] if len(parts) > 1 else item
        c = colors[i % len(colors)]
        cards += f"""
        <div style="display:flex;gap:20px;align-items:stretch;">
            <div style="display:flex;flex-direction:column;align-items:center;gap:0;">
                <div style="width:44px;height:44px;border-radius:12px;background:{c};color:#fff;display:flex;align-items:center;justify-content:center;font-size:22px;font-weight:800;flex-shrink:0;font-family:{P['font']};">{i+1}</div>
                {f'<div style="width:2px;flex:1;background:{c}22;"></div>' if i < len(items)-1 else ''}
            </div>
            <div style="flex:1;background:{P['card']};border:1px solid {P['border']};border-radius:14px;padding:20px 24px;border-left:4px solid {c};box-shadow:{P['shadow']};margin-bottom:{'16' if i < len(items)-1 else '0'}px;">
                <div style="font-size:26px;font-weight:700;color:{P['text']};font-family:{P['font']};margin-bottom:6px;">{label}</div>
                <div style="font-size:19px;color:{P['sub']};line-height:1.65;">{desc}</div>
            </div>
        </div>"""
    
    return f"""
    <div style="width:{w}px;height:{h}px;background:{P['bg']};padding:44px 52px;display:flex;flex-direction:column;font-family:{P['font']};">
        <div style="text-align:center;margin-bottom:28px;">
            <div style="font-size:40px;font-weight:800;color:{P['text']};letter-spacing:1px;">{title}</div>
            <div style="width:50px;height:3px;background:{P['grad']};border-radius:2px;margin:10px auto 0;"></div>
        </div>
        <div style="flex:1;display:flex;flex-direction:column;justify-content:center;">{cards}</div>
    </div>"""


def render_compare(title, items, size):
    w, h = size.split("x")
    rows = [item.split("|") for item in items]
    headers = rows[0] if rows else ["A", "B"]
    data = rows[1:] if len(rows) > 1 else []
    ncols = len(headers)
    
    head = ""
    for i, hh in enumerate(headers):
        head += f'<div style="flex:1;padding:14px 16px;text-align:center;font-size:20px;font-weight:700;color:#fff;font-family:{P["font"]};">{hh.strip()}</div>'
    
    body = ""
    for ri, row in enumerate(data):
        bg = P["card"] if ri % 2 else P["tag"]
        cells = ""
        for ci, c in enumerate(row):
            val = c.strip()
            # Highlight numbers
            is_pct = any(x in val for x in ["+", "-", "%", ":", "/", "笔"])
            color = P["accent"] if (ci == 0) else (P["text"] if is_pct else P["sub"])
            fw = "font-weight:700;" if ci == 0 or is_pct else ""
            br = f"border-right:1px solid {P['border']};" if ci < ncols - 1 else ""
            cells += f'<div style="flex:1;padding:12px 16px;text-align:center;font-size:19px;color:{color};{fw}font-family:{P["font"]};{br}">{val}</div>'
        body += f'<div style="display:flex;background:{bg};border-bottom:1px solid {P["border"]};">{cells}</div>'
    
    return f"""
    <div style="width:{w}px;height:{h}px;background:{P['bg']};padding:36px 40px;display:flex;flex-direction:column;font-family:{P['font']};">
        <div style="text-align:center;margin-bottom:22px;">
            <div style="font-size:40px;font-weight:800;color:{P['text']};">{title}</div>
            <div style="width:50px;height:3px;background:{P['grad']};border-radius:2px;margin:10px auto 0;"></div>
        </div>
        <div style="flex:1;display:flex;align-items:center;">
            <div style="width:100%;border-radius:16px;overflow:hidden;box-shadow:{P['shadow']};border:1px solid {P['border']};">
                <div style="display:flex;background:{P['grad']};">{head}</div>
                {body}
            </div>
        </div>
    </div>"""


def render_list(title, items, size):
    w, h = size.split("x")
    n = len(items)
    # 1-3 items: single col; 4+: two cols
    if n <= 3:
        layout = "flex-direction:column;"
    else:
        layout = "display:grid;grid-template-columns:1fr 1fr;gap:16px;"
    
    cards = ""
    colors = [P["accent"], P["gold"], P["red"], P["green"], P["accent2"]]
    for i, item in enumerate(items):
        parts = item.split(":", 1)
        t = parts[0] if len(parts) > 1 else item
        d = parts[1] if len(parts) > 1 else ""
        c = colors[i % len(colors)]
        if n <= 3:
            cards += f"""
            <div style="display:flex;gap:16px;background:{P['card']};border:1px solid {P['border']};border-radius:14px;padding:22px 24px;border-top:3px solid {c};box-shadow:{P['shadow']};margin-bottom:{'14' if i < n-1 else '0'}px;">
                <div style="width:38px;height:38px;border-radius:10px;background:{c};color:#fff;display:flex;align-items:center;justify-content:center;font-size:20px;font-weight:800;flex-shrink:0;">{i+1}</div>
                <div style="flex:1;">
                    <div style="font-size:24px;font-weight:700;color:{P['text']};margin-bottom:4px;font-family:{P['font']};">{t}</div>
                    {"<div style='font-size:18px;color:" + P['sub'] + ";line-height:1.6;'>" + d + "</div>" if d else ""}
                </div>
            </div>"""
        else:
            cards += f"""
            <div style="background:{P['card']};border:1px solid {P['border']};border-radius:14px;padding:18px 20px;border-top:3px solid {c};box-shadow:{P['shadow']};">
                <div style="display:flex;align-items:center;gap:10px;margin-bottom:6px;">
                    <div style="width:32px;height:32px;border-radius:8px;background:{c};color:#fff;display:flex;align-items:center;justify-content:center;font-size:17px;font-weight:800;">{i+1}</div>
                    <div style="font-size:21px;font-weight:700;color:{P['text']};font-family:{P['font']};">{t}</div>
                </div>
                {"<div style='font-size:17px;color:" + P['sub'] + ";line-height:1.55;padding-left:42px;'>" + d + "</div>" if d else ""}
            </div>"""
    
    gap = "gap:14px;" if n > 3 else ""
    return f"""
    <div style="width:{w}px;height:{h}px;background:{P['bg']};padding:40px 48px;display:flex;flex-direction:column;font-family:{P['font']};">
        <div style="text-align:center;margin-bottom:24px;">
            <div style="font-size:40px;font-weight:800;color:{P['text']};">{title}</div>
            <div style="width:50px;height:3px;background:{P['grad']};border-radius:2px;margin:10px auto 0;"></div>
        </div>
        <div style="flex:1;display:flex;align-items:center;justify-content:center;">
            <div style="width:100%;{layout}{gap}">{cards}</div>
        </div>
    </div>"""


def render_quote(title, items, size):
    w, h = size.split("x")
    q = items[0] if items else title
    a = items[1] if len(items) > 1 else ""
    return f"""
    <div style="width:{w}px;height:{h}px;background:{P['bg']};padding:60px 80px;display:flex;flex-direction:column;align-items:center;justify-content:center;font-family:{P['font']};">
        <div style="font-size:120px;line-height:0.8;color:{P['accent']};opacity:0.12;font-family:Georgia,serif;">"</div>
        <div style="font-size:36px;color:{P['text']};text-align:center;line-height:1.9;max-width:1100px;margin-top:-10px;letter-spacing:0.5px;">{q}</div>
        <div style="width:48px;height:3px;background:{P['grad']};border-radius:2px;margin:28px 0;"></div>
        {"<div style='font-size:22px;color:" + P['sub'] + ";'>" + a + "</div>" if a else ""}
    </div>"""


def render_cover(title, items, size):
    w, h = size.split("x")
    sub = items[0] if items else ""
    tags = items[1].split(",") if len(items) > 1 else []
    tags_html = "".join(
        '<span style="display:inline-block;padding:5px 14px;border-radius:16px;font-size:16px;background:' + P['tag'] + ';color:' + P['accent'] + ';font-family:' + P['font'] + ';">' + t.strip() + '</span>'
        for t in tags
    )
    return f"""
    <div style="width:{w}px;height:{h}px;background:{P['bg']};padding:70px 80px;display:flex;flex-direction:column;align-items:center;justify-content:center;font-family:{P['font']};">
        <div style="text-align:center;max-width:1100px;">
            <div style="font-size:52px;font-weight:800;color:{P['text']};line-height:1.35;letter-spacing:1px;">{title}</div>
            <div style="font-size:22px;color:{P['sub']};margin-top:18px;line-height:1.6;">{sub}</div>
            <div style="margin-top:24px;display:flex;gap:10px;justify-content:center;flex-wrap:wrap;">{tags_html}</div>
        </div>
    </div>"""


RENDERERS = {
    "timeline": render_timeline, "compare": render_compare,
    "list": render_list, "quote": render_quote, "cover": render_cover,
}


def generate(title, items, material_type="list", font="MaShanZheng",
             palette_name="warm", size="1536x1024", output="output.png"):
    renderer = RENDERERS.get(material_type, render_list)
    font_css = get_font_css(font)
    body = renderer(title, items, size)
    html = f"""<!DOCTYPE html><html><head><meta charset="utf-8">
    <style>{font_css}*{{margin:0;padding:0;box-sizing:border-box;}}body{{margin:0;overflow:hidden;}}</style>
    </head><body>{body}</body></html>"""
    w, h = size.split("x")
    os.makedirs(os.path.dirname(os.path.abspath(output)), exist_ok=True)
    with sync_playwright() as p:
        cdp_url = os.getenv("OPENCLAW_CDP_URL", "http://127.0.0.1:18800")
        try:
            browser = p.chromium.connect_over_cdp(cdp_url)
            page = browser.new_page(viewport={"width": int(w), "height": int(h)}, device_scale_factor=2)
        except Exception:
            browser = p.chromium.launch()
            page = browser.new_page(viewport={"width": int(w), "height": int(h)}, device_scale_factor=2)
        page.set_content(html, wait_until="networkidle")
        page.screenshot(path=output, full_page=False)
        page.close()
    sz = os.path.getsize(output)
    print(f"✅ {output} ({sz//1024}KB)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--type", choices=list(RENDERERS.keys()), default="list")
    ap.add_argument("--title", default="标题")
    ap.add_argument("--items", nargs="+", default=[])
    ap.add_argument("--font", default="MaShanZheng", choices=list(FONT_MAP.keys()))
    ap.add_argument("--palette", default="warm")
    ap.add_argument("--size", default="1536x1024")
    ap.add_argument("--output", default="output.png")
    a = ap.parse_args()
    generate(a.title, a.items, a.type, a.font, a.palette, a.size, a.output)


if __name__ == "__main__":
    main()
