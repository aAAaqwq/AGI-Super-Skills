---
name: gzh-publisher
description: "微信公众号统一发布技能：通过 OpenClaw Browser 自动化完成登录、写文章、一键排版、封面、存草稿。"
metadata: {"version":"3.2.0","author":"Daniel Li","domains":["content","publishing","automation","wechat"],"type":"automation"}
---
description: "微信公众号统一发布技能：通过 OpenClaw Browser 自动化完成登录、写文章、一键排版、封面、存草稿。唯一官方公众号发布方式。"
license: MIT
metadata:
  version: 3.2.0
  author: Daniel Li / 小a CEO
  domains: [content, publishing, automation, wechat]
  type: automation
  requires: [openclaw-browser]
---

# GZH Publisher Skill — 公众号统一发布

> **唯一官方微信公众号发布方式。基于 OpenClaw Browser 自动化。**

## 🚀 快速使用（脚本模式）

```bash
# 推荐：自动扫描 gzh/ 目录图片
python3 scripts/publish.py --article gzh/article.md --author "Daniel"

# 跳过一键排版
python3 scripts/publish.py --article gzh/article.md --author "Daniel" --no-format

# 跳过封面
python3 scripts/publish.py --article gzh/article.md --author "Daniel" --no-cover
```

需要 OpenClaw Browser 运行中（`openclaw browser start`）。

---

## 什么时候用

- 有 Markdown 文章需要发布到微信公众号草稿箱
- Agent 需要"发布公众号"、"公众号草稿"、"发微信"时

> 📋 **发布前确认内容合规**：`~/clawd/projects/MediaClaw/references/platforms/weixin-mp.md`

## 不适用

- ❌ 直接正式发布 — 仅存草稿，人工最终审核发布
- ❌ 视频内容 — 仅支持图文消息
- ❌ 编辑已发布文章 — 只能新建

---

## 🔄 完整 Workflow（2026-04-18 实战验证）

```
┌─────────────────────────────────────────────────────┐
│  Step 1: 检查登录状态                                 │
│  browser → navigate(mp.weixin.qq.com)                │
├─────────────────────────────────────────────────────┤
│  Step 2: 新建文章（新标签页 appmsg_edit）              │
├─────────────────────────────────────────────────────┤
│  Step 3: 填标题（JS evaluate, textarea）              │
├─────────────────────────────────────────────────────┤
│  Step 4: 填作者（JS evaluate, input）                 │
├─────────────────────────────────────────────────────┤
│  Step 5: 粘贴素材图片（clipboard + Ctrl+V）            │
│  → 每张等8秒 CDN 转换 → 收集 mmbiz URL               │
├─────────────────────────────────────────────────────┤
│  Step 6: 设封面「从正文选择」← 必须在 HTML 注入前！    │
├─────────────────────────────────────────────────────┤
│  Step 7: 注入正文 HTML（CDP WebSocket, 含 CDN 图片）  │
├─────────────────────────────────────────────────────┤
│  Step 8: 一键排版（新标签页 articlestruct）             │
│  → 点"使用此排版" → 图片不会丢失 ✅                   │
├─────────────────────────────────────────────────────┤
│  Step 9: 保存草稿                                     │
└─────────────────────────────────────────────────────┘
```

---

## ⚡ 关键发现（踩坑总结）

### 1. 图片粘贴：唯一可行方案
- ❌ `innerHTML` 注入 `<img>` → 图片不加载
- ❌ CDP `DOM.setFileInputFiles` → 上传但不插入编辑器
- ❌ OpenClaw `browser upload` → 同上
- ❌ clipboard 只支持 PNG，JPEG 会报 `Type not supported`
- ✅ **clipboard.write(PNG blob) + keyboard Ctrl+V** → 唯一可行

### 2. 封面必须在 HTML 注入前设置
- ❌ HTML 注入后点"从正文选择" → 弹窗为空（innerHTML 不注册图片到微信服务端）
- ❌ 排版后点"从正文选择" → 弹窗为空（排版可能清除服务端注册）
- ✅ **粘贴图片后立即设封面**（此时 ProseMirror 追踪了粘贴的图片）

### 3. 一键排版不会丢图片
- ❌ innerHTML 注入后排版 → 排版读的是 ProseMirror 内部状态（空的），内容丢失
- ✅ **先粘贴图片让 ProseMirror 追踪 → 再注入 HTML → 再排版** → 图片保留
- 一键排版打开新标签页 `articlestruct`，需切换 targetId 后点"使用此排版"

### 4. 标题/作者用 JS evaluate
- ❌ Playwright `fill()` 在微信 textarea 上会超时
- ✅ `ta.value = ...` + `dispatchEvent('input')` via browser evaluate

### 5. 长 HTML 必须用 CDP 注入
- ❌ OpenClaw `evaluate` 的 fn 有字符长度限制，>2000字会被截断
- ✅ 先写 `/tmp/wechat-article.html` → CDP WebSocket `Runtime.evaluate` 注入

---

## 📋 逐步操作指南

### Step 1: 检查登录

```
browser(action="navigate", profile="openclaw", url="https://mp.weixin.qq.com")
browser(action="snapshot", profile="openclaw")
```

- 包含"新的创作"+ 账号名 → **已登录** ✅
- 包含"请登录"或 QR 码 → **未登录** → 截图发 Daniel 扫码

### Step 2: 新建文章

```
// 点"新的创作"
browser(action="act", kind="evaluate", fn="""
  () => {
    const h2s = document.querySelectorAll('h2');
    for (const h of h2s) {
      if (h.textContent.trim() === '新的创作') { h.click(); return 'clicked'; }
    }
  }
""")
// 等1秒 → 点"文章"（y>300 的第一个文本="文章"的元素）
// 等待6秒 → 用 tabs 找 appmsg_edit 标签页
browser(action="tabs", profile="openclaw")
```

### Step 3: 填标题

```
browser(action="act", kind="evaluate", targetId=编辑器, fn="""
  () => {
    const ta = document.querySelector('textarea[placeholder*="标题"]');
    ta.focus(); ta.value = '文章标题';
    ta.dispatchEvent(new Event('input', {bubbles:true}));
    return 'filled: ' + ta.value;
  }
""")
```

### Step 4: 填作者

```
browser(action="act", kind="evaluate", targetId=编辑器, fn="""
  () => {
    const inp = document.querySelector('input[placeholder*="作者"]');
    inp.focus(); inp.value = 'Daniel';
    inp.dispatchEvent(new Event('input', {bubbles:true}));
    return 'filled';
  }
""")
```

### Step 5: 粘贴素材图片

**必须用 CDP WebSocket 方式**（browser 工具的 evaluate 传 base64 太大）：

```python
# 写成独立脚本 /tmp/paste_images.py，exec 运行
import asyncio, json, base64, httpx, websockets, os

async def paste_all(images, target_id):
    async with httpx.AsyncClient() as c:
        r = await c.get("http://127.0.0.1:18800/json/list")
        ws_url = next(t["webSocketDebuggerUrl"] for t in r.json() if target_id in t["id"])
    async with websockets.connect(ws_url, max_size=50*1024*1024) as ws:
        # Grant clipboard
        await ws.send(json.dumps({"id":0,"method":"Browser.grantPermissions",
            "params":{"permissions":["clipboard-read","clipboard-write"],"origin":"https://mp.weixin.qq.com"}}))
        await ws.recv()
        
        for img_path in images:
            with open(img_path, "rb") as f:
                b64 = base64.b64encode(f.read()).decode()
            # Write to clipboard
            await ws.send(json.dumps({"id":1,"method":"Runtime.evaluate",
                "params":{"expression":f"""
                    (async () => {{
                        const b = await fetch('data:image/png;base64,{b64}').then(r=>r.blob());
                        await navigator.clipboard.write([new ClipboardItem({{'image/png': b}})]);
                    }})()
                """}}))
            await ws.recv()
            await asyncio.sleep(0.5)
            # Focus + Ctrl+V
            await ws.send(json.dumps({"id":2,"method":"Runtime.evaluate",
                "params":{"expression":"document.querySelector('.ProseMirror').focus()"}}))
            await ws.recv()
            for ev in ["keyDown","keyUp"]:
                await ws.send(json.dumps({"id":3,"method":"Input.dispatchKeyEvent",
                    "params":{"type":ev,"modifiers":2,"key":"v","code":"KeyV","windowsVirtualKeyCode":86}}))
                await ws.recv()
            await asyncio.sleep(8)  # Wait for CDN conversion
```

**JPG 必须先转 PNG**（Pillow）：`Image.open(p).save(p.with_suffix('.png'), 'PNG')`

**收集 CDN URL**：
```
browser(action="act", kind="evaluate", targetId=编辑器, fn="""
  () => JSON.stringify(
    Array.from(document.querySelectorAll('.ProseMirror img'))
      .filter(i => i.src.includes('mmbiz')).map(i => i.src)
  )
""")
```

### Step 6: 设封面（从正文选择）

⚠️ **必须在 Step 7 HTML 注入之前做！**

```
// 1. 点"从正文选择"
browser(action="act", kind="evaluate", targetId=编辑器, fn="""
  () => {
    const items = document.querySelectorAll('#js_cover_description_area a, a');
    for (const el of items) {
      if (el.textContent.includes('从正文选择')) { el.click(); return 'clicked'; }
    }
    return 'not found';
  }
""")
// 2. 选第一张图
browser(action="act", kind="evaluate", targetId=编辑器, fn="""
  () => {
    const items = document.querySelectorAll('.appmsg_content_img_item');
    if (items.length > 0) { items[0].click(); return 'selected'; }
    return 'empty';
  }
""")
// 3. 下一步 → 确认
```

### Step 7: 注入正文 HTML

**长 HTML 必须用 CDP**（先写文件再注入）：

```bash
# 1. 生成 HTML 写入文件（图片 URL 替换为 CDN）
write(path="/tmp/wechat-article.html", content=生成的HTML)

# 2. CDP 注入
python3 << 'EOF'
import json, asyncio, httpx, websockets

async def inject():
    async with httpx.AsyncClient() as c:
        r = await c.get("http://127.0.0.1:18800/json/list")
        ws_url = next(t["webSocketDebuggerUrl"] for t in r.json() if TARGET in t["id"])
    with open("/tmp/wechat-article.html") as f:
        html = f.read()
    async with websockets.connect(ws_url) as ws:
        await ws.send(json.dumps({"id":1,"method":"Runtime.evaluate","params":{
            "expression": f"(() => {{ const e = document.querySelector('.ProseMirror'); e.innerHTML = {json.dumps(html)}; e.dispatchEvent(new Event('input', {{bubbles:true}})); return 'ok'; }})()",
            "returnByValue": True
        }}))
        print(json.loads(await ws.recv())["result"]["result"]["value"])

asyncio.run(inject())
EOF
```

### Step 8: 一键排版

```
// 1. 在编辑器页点"一键排版"
browser(action="act", kind="evaluate", targetId=编辑器, fn="""
  () => {
    const all = document.querySelectorAll('span, div, button, a');
    for (const el of all) {
      if (el.textContent.trim() === '一键排版' && el.offsetParent !== null) {
        el.click(); return 'clicked';
      }
    }
  }
""")
// 2. 等待 → 用 tabs 找 articlestruct 标签页
// 3. 在排版页点"使用此排版"
browser(action="act", kind="click", ref=使用此排版ref, targetId=排版页)
// 4. 排版自动应用，回到编辑器
```

### Step 9: 保存草稿

```
browser(action="act", kind="evaluate", targetId=编辑器, fn="""
  () => {
    const btns = document.querySelectorAll('button');
    for (const b of btns) {
      if (b.textContent.includes('保存为草稿') && b.offsetParent !== null) {
        b.click(); return 'clicked';
      }
    }
  }
""")
```

---

## 🎨 Markdown → WeChat HTML 样式

| Markdown | HTML 样式 |
|----------|-----------|
| `# H1` | 22px bold, text-align center |
| `## H2` | 18px bold, border-left 4px #1a73e8 |
| `### H3` | 16px bold |
| `**bold**` | `<strong>` |
| `*italic*` | `<em>` |
| `` `code` `` | bg #f6f8fa, padding 2px 6px |
| `> quote` | border-left 3px #ddd, color #666 |
| `![img](url)` | 居中, max-width 100% |

正文段落：`font-size:15px; color:#3f3f3f; line-height:1.75; margin:8px 0`

---

## 📦 输入输出

```yaml
输入:
  article_path: string     # Markdown 文章路径（必需）
  author: string           # 作者名（可选）
  image_paths: list        # 素材图片（可选，默认自动扫描 gzh/ 目录）

输出:
  status: ok | error
  draft_saved: true/false
  appmsgid: string
  title: string
  images_uploaded: number
  format_applied: boolean
  cover_set: boolean
```

---

## 🏗️ 与其他 Skill 的关系

| Skill | 关系 |
|-------|------|
| `wemp-operator` | 全 API（统计/评论/粉丝/素材/群发） |
| `daily-gzh-content` | 公众号内容生成 |
| `wechat-toolkit` | 文章下载工具 |

---

## 更新日志

- **v3.2.0** (2026-04-22): 修复图片位置bug
  - auto_insert_images: 检测到已有图片引用时跳过，不再重复插入
  - 粘贴顺序修正: clipboard write → select placeholder → Ctrl+V（防止剪贴板写入破坏ProseMirror选区）
  - 拆分 paste_image_at_selection 为 write_clipboard_image + paste_at_current_position
- **v3.1.0** (2026-04-18): 实战验证固化
  - ✅ 确认一键排版不会丢失图片（需先粘贴图片让 ProseMirror 追踪）
  - ✅ 封面必须在 HTML 注入前设置
  - ✅ 移除排版后重新注入 HTML（不需要了）
  - ✅ 精简 SKILL.md，删除过时陷阱和冗余流程
  - 📋 9 步流程全部手动验证通过

- **v3.0.0** (2026-04-18): 大重写
  - 自动扫描 gzh/ 目录图片
  - 一键排版支持（articlestruct 新标签页）
  - 封面从正文选择
  - JPG→PNG 自动转换
  - --no-format / --no-cover 标志
