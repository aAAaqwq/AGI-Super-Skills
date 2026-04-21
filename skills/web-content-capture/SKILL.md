---
name: web-content-capture
description: 为内容生产提供**网页截图和素材采集**能力。所有内容生成类 skill 在素材阶段应调用本 skill。
  网页内容截图与素材采集。优先使用OpenClaw browser（保持登录态），备选Playwright（公开页面）。
  用法: (1) 文章调研时采集GitHub/Reddit/X等平台截图 (2) 获取社交媒体讨论素材 (3) 抓取网页关键内容作为配图。
  Trigger: "截图", "采集素材", "web capture", "screenshot", "爬取内容", "获取素材", "素材采集".
  Author: Daniel Li
---

# 网页内容截图与素材采集

> MediaClaw 通用素材采集工具

## 定位

为内容生产提供**网页截图和素材采集**能力。所有内容生成类 skill 在素材阶段应调用本 skill。

## 优先级链

```
1. OpenClaw browser (profile="openclaw")
   → 保持登录态，适合 X/Reddit/需登录平台
   → 截图保存到 ~/.openclaw/media/browser/

2. OpenClaw browser (profile="user")
   → 使用 Daniel 的 Chrome session（需 debug port 9222）

3. Playwright headless (exec + python3)
   → 无登录态，适合 GitHub/文档站/博客等公开页面
   → 最快最稳定

4. web_fetch
   → 仅获取文本，无法截图
   → 代理环境可能导致 SSRF 拦截
```

## 标准流程

### 1. 确认浏览器状态

```
browser(action="status", profile="openclaw")
```

- `running: false` → `browser(action="start", profile="openclaw")`
- 超时 → `gateway(action="restart")` 等待5秒重试

### 2. 打开页面（用 open，不用 navigate）

```
browser(action="open", profile="openclaw", targetUrl="https://...")
```

保留返回的 `targetId` 用于后续操作。**每个平台用独立 tab。**

### 3. 等待加载

```
browser(action="act", profile="openclaw", targetId="xxx",
  request={"kind": "wait", "timeMs": 8000})
```

| 平台 | 建议 |
|------|------|
| GitHub | 3-5秒 |
| Reddit（公开） | 5-8秒 |
| X/Twitter | 8-12秒 |
| Google搜索 | 3-5秒 |
| Medium/Blog | 5-8秒 |

### 4. 截图

```
browser(action="screenshot", profile="openclaw", targetId="xxx", type="png")
```

### 5. 保存到项目输出目录

OpenClaw browser 截图存在 `~/.openclaw/media/browser/`，**必须复制到项目输出目录**：

```bash
# 找到最新截图（按时间倒序，取 >20KB 的有效文件）
ls -lt ~/.openclaw/media/browser/*.{png,jpg} | head -10

# 复制到目标文章素材目录
cp ~/.openclaw/media/browser/<file> <OUTPUT_DIR>/<descriptive-name>.png
```

### 6. 验证有效性

```bash
# 快速检查：文件大小 > 20KB
ls -lh <screenshot>

# 深度检查：是否空白
python3 -c "
from PIL import Image; import numpy as np
img = np.array(Image.open('<path>'))
print('BLANK' if img.mean() > 250 else 'OK')
"
```

## 备选: Playwright 无头截图

当 OpenClaw browser 不可用或无需登录时：

```python
import asyncio
from playwright.async_api import async_playwright

async def capture(url, output_path):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(
            user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
            viewport={"width": 1400, "height": 900}
        )
        await page.goto(url, timeout=25000)
        await page.wait_for_load_state("domcontentloaded", timeout=15000)
        await asyncio.sleep(5)
        await page.screenshot(path=output_path)
        await browser.close()

asyncio.run(capture("https://github.com/user/repo", "github-repo.png"))
```

## 平台 URL 模板

| 平台 | URL | 登录 |
|------|-----|------|
| X | `https://x.com/search?q=关键词&f=live` | ✅ |
| Reddit | `https://reddit.com/r/{sub}/search/?q=关键词&sort=top&t=month` | 部分 |
| GitHub | `https://github.com/{user}/{repo}` | ❌ |
| Google | `https://google.com/search?q=关键词` | ❌ |
| Medium | `https://medium.com/search?q=关键词` | ❌ |
| 知乎 | `https://zhihu.com/search?type=content&q=关键词` | 部分 |

## 输出路径

**由调用方指定**，不写死。标准结构：

```
<OUTPUT_DIR>/
├── github-*.png
├── reddit-*.png
├── x-*.png
├── google-*.png
├── cover-*.png
└── article.md
```

`OUTPUT_DIR` 由内容生成 skill 在调用时传入，通常为：
```
~/clawd/projects/MediaClaw/output/articles/{YYYY-MM-DD}/{topic-slug}/
```

## 安全注意事项

### 截图不暴露个人信息

**严禁截取全页面**（可能暴露 profile、通知、DM、关注列表等）。

**正确做法：只截目标推文/评论**
- 使用 CDP `Page.captureScreenshot` + `clip` 参数裁剪单条内容
- 优先截取**数据最好**的那条（likes/reposts 最高的）
- 社交媒体截图只保留内容区域，裁掉左侧导航栏和右侧推荐栏

```python
# CDP 裁剪单条推文（示例）
import json, base64, websockets

async with websockets.connect(ws_url) as ws:
    # 1. 定位目标推文的 bounding box
    await ws.send(json.dumps({
        "id": 1,
        "method": "Runtime.evaluate",
        "params": {
            "expression": """
                (() => {
                    const articles = document.querySelectorAll('article');
                    let best = null, bestScore = 0;
                    for (const a of articles) {
                        const t = a.textContent;
                        // 找 likes 最高的相关推文
                        const m = t.match(/([\d,.]+)\s*[Ll]ikes?/);
                        const score = m ? parseInt(m[1].replace(/,/g,'')) : 0;
                        if (score > bestScore && t.includes('KEYWORD')) {
                            bestScore = score;
                            best = a.getBoundingClientRect();
                        }
                    }
                    return best ? {x:best.x, y:best.y, w:best.width, h:best.height} : null;
                })()
            """,
            "returnByValue": True
        }
    }))
    bbox = json.loads(await ws.recv())['result']['result']['value']

    # 2. 裁剪截图（scale=2 对应 deviceScaleFactor）
    clip = {"x": bbox['x']*2, "y": bbox['y']*2,
            "width": bbox['w']*2, "height": bbox['h']*2, "scale": 1}
    await ws.send(json.dumps({
        "id": 2,
        "method": "Page.captureScreenshot",
        "params": {"format": "png", "clip": clip}
    }))
    data = json.loads(await ws.recv())['result']['data']
    with open('output.png', 'wb') as f:
        f.write(base64.b64decode(data))
```

### 裁剪区域规范

| 平台 | 裁剪策略 | 裁掉什么 |
|------|---------|--------|
| X/Twitter | 单条推文 bounding box | 导航栏、侧栏、推荐关注 |
| Reddit | 搜索结果区域 | 顶栏、侧栏、广告 |
| GitHub | 仓库主体区域（去掉侧边栏） | 右侧推荐、赞助 |
| Google | 搜索结果主体 | 顶栏、广告、侧栏 |

### 截完后检查
- 确认无 profile 头像/用户名露出（除非是目标内容本身）
- 确认无通知数、DM、浏览历史泄露
- 如有暴露 → 删除重截，不要心存侥幸

---

## 常见问题

| 问题 | 解决 |
|------|------|
| browser 超时 | `gateway restart` + `browser start` |
| 截图空白 | 增加等待时间 / 换 Playwright / 检查登录态 |
| SSRF 拦截 | 用 OpenClaw browser 替代 web_fetch |
| X 需登录 | 用 OpenClaw browser (openclaw profile)，首次需扫码 |
| 截图暴露隐私 | 用 CDP clip 裁剪单条内容，不截全页 |
