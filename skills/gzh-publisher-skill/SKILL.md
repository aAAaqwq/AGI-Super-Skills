---
name: gzh-publisher-skill
description: "微信公众号统一发布技能：通过 OpenClaw Browser 自动化完成登录、写文章、一键排版、封面、存草稿。唯一官方公众号发布方式。"
license: MIT
metadata:
  version: 2.5.0
  author: Daniel Li / 小a CEO
  domains: [content, publishing, automation, wechat]
  type: automation
  requires: [openclaw-browser]
---

# GZH Publisher Skill — 公众号统一发布

> **唯一官方微信公众号发布方式。基于 OpenClaw Browser 自动化。**

## 🚀 快速使用（脚本模式）

```bash
# 基础用法
python3 scripts/publish.py \
  --article output/articles/2026-04-17/claude-opus-4-7/gzh/article-v3.md \
  --cover output/articles/2026-04-17/claude-opus-4-7/gzh/cover-16x9.jpg \
  --author Daniel

# 带素材图片
python3 scripts/publish.py \
  --article article.md \
  --cover cover.jpg \
  --author Daniel \
  --images img1.png img2.jpg
```

脚本自动完成：登录验证 → 新建文章 → 填标题作者 → 上传图片 → 注入正文 → 一键排版 → 设置封面 → 存草稿。

> 需要 OpenClaw Browser 运行中（`openclaw browser start`）。

---

## 什么时候用

- 有 Markdown 文章需要发布到微信公众号草稿箱
- Agent 需要"发布公众号"、"公众号草稿"、"发微信"时
- MediaClaw content pipeline 的公众号发布环节

> 📋 **发布前请确认内容合规**：`~/clawd/projects/MediaClaw/references/platforms/weixin-mp.md`（内容规范、违规类型、AIGC标识要求）

## 不适用

- ❌ 直接正式发布 — 仅存草稿，人工最终审核发布
- ❌ 视频内容 — 仅支持图文消息
- ❌ 编辑已发布文章 — 只能新建

---

## 🔄 完整 Workflow

```
┌─────────────────────────────────────────────────────┐
│  Step 1: 检查登录状态                                 │
│  browser → navigate(mp.weixin.qq.com)                │
│  └─ 已登录 → 看到"新的创作" → Step 2                  │
│  └─ 未登录 → QR码页面 → 截图发Daniel → 等待扫码        │
├─────────────────────────────────────────────────────┤
│  Step 2: 新建文章                                     │
│  JS click "新的创作" → 等待编辑器加载                   │
├─────────────────────────────────────────────────────┤
│  Step 3: 填入标题                                     │
│  JS fill textarea[placeholder*="标题"]                 │
├─────────────────────────────────────────────────────┤
│  Step 4: 填入作者                                     │
│  JS fill input[placeholder*="作者"]                    │
├─────────────────────────────────────────────────────┤
│  Step 5a: 上传素材图片 → 获取微信CDN URL              │
│  Step 5b: 注入正文HTML（含图片URL，推荐CDP注入）        │
├─────────────────────────────────────────────────────┤
│  Step 6: 一键排版                                     │
│  click "一键排版" → 等待排版完成 → 截图确认             │
├─────────────────────────────────────────────────────┤
│  Step 7: 设置封面（默认从正文第一张图片选择）            │
├─────────────────────────────────────────────────────┤
│  Step 8: 保存到草稿箱                                  │
│  click "保存为草稿" → 截图确认                         │
└─────────────────────────────────────────────────────┘
```

---

## 📋 逐步操作指南

### Step 1: 检查登录状态

```
browser(action="navigate", profile="openclaw", url="https://mp.weixin.qq.com")
browser(action="snapshot", profile="openclaw")
```

**判断逻辑**：
- 页面包含 `新的创作` 文字 + 账号名（如"DanielAI编程实验室"）→ **已登录** ✅
- 页面包含 `请登录` 或 QR 码 `img` → **未登录** ❌

**未登录处理**：
```
browser(action="screenshot", profile="openclaw")
message(action="send", message="🔑 公众号需要登录，请扫码...", media=screenshot_path)
```
→ 截图发送到群 → 等待 Daniel 扫码 → 扫码后重新 navigate 确认登录

**QR码有效期**：约 5 分钟，超时需刷新页面重新获取

### Step 2: 新建文章

使用 JS 点击（CSS selector 不可靠，用 JS 更稳定）：
```
browser(action="act", kind="evaluate", fn="""
  () => {
    const links = document.querySelectorAll('a');
    for (const link of links) {
      if (link.textContent.includes('文章') && link.closest('[class*="create"], [class*="new"]')) {
        link.click();
        return 'clicked';
      }
    }
    // 备选：点击"新的创作"区域的第一个可点击元素
    const items = document.querySelectorAll('[class*="create"] *');
    for (const item of items) {
      if (item.textContent.trim() === '文章') {
        item.click();
        return 'clicked fallback';
      }
    }
    return 'not found';
  }
""")
```

点击后等待新标签页打开：
```
browser(action="tabs", profile="openclaw")
```
找到 URL 包含 `appmsg_edit_v2` 的标签页 → 切换到该 `targetId`

### Step 3: 填入标题

**关键**：标题是 `<textarea>`，不是 `<input>`（2026-04-15 验证）

```
browser(action="act", kind="evaluate", targetId=编辑器targetId, fn="""
  () => {
    const ta = document.querySelector('textarea[placeholder*="标题"]');
    if (!ta) return 'not found';
    ta.value = '文章标题（≤64字）';
    ta.dispatchEvent(new Event('input', { bubbles: true }));
    ta.dispatchEvent(new Event('change', { bubbles: true }));
    return 'filled: ' + ta.value;
  }
""")
```

**注意**：标题最多 64 字，超出部分会被截断

### Step 4: 填入作者

```
browser(action="act", kind="evaluate", targetId=编辑器targetId, fn="""
  () => {
    const inp = document.querySelector('input[placeholder*="作者"]');
    if (!inp) return 'not found';
    inp.value = '作者名';
    inp.dispatchEvent(new Event('input', { bubbles: true }));
    return 'filled';
  }
""")
```

### Step 5: 注入正文内容

**关键**：编辑器是 **ProseMirror**（不是 UEditor），使用 `.ProseMirror` div

**Markdown → HTML 转换规则**：

| Markdown | HTML | 样式 |
|----------|------|------|
| `# H1` | `<h1>` | 22px bold, text-align center |
| `## H2` | `<h2>` | 18px bold, 左边框 4px #1a73e8 |
| `### H3` | `<h3>` | 16px bold |
| `**bold**` | `<strong>` | — |
| `*italic*` | `<em>` | — |
| `` `code` `` | `<code>` | bg #f6f8fa, padding 2px 6px |
| `` ```block``` `` | `<pre><code>` | bg #f6f8fa, 左边框 3px #fe6 |
| `> quote` | `<blockquote>` | 左边框 3px #ddd, color #666 |
| `- item` | `<li>` (in `<ul>`) | — |
| `---` | `<hr>` | border #eee |
| `\| table \|` | `<table>` | border-collapse, zebra stripe |
| `![img](url)` | `<img>` | max-width 100% |

**Step 5a：上传素材图片并获取微信CDN URL**

⚠️ **关键**：微信编辑器**不支持外部链接图片**（如GitHub、Reddit截图URL），必须先上传到微信服务器获取 `mmbiz.qpic.cn` 域名的URL。

**推荐流程**（逐张上传 → 记录CDN URL → 后续嵌入HTML）：

```
// 1. 复制素材图片到 OpenClaw uploads 目录
exec(command="cp /path/to/image1.jpg /tmp/openclaw/uploads/")

// 2. 通过工具栏 file input 上传单张图片
browser(action="upload", profile="openclaw", targetId=编辑器targetId,
  selector="input[type='file']", paths=["/tmp/openclaw/uploads/image1.jpg"])

// 3. 等待上传完成（图片会插入到编辑器光标位置）
browser(action="act", kind="wait", timeMs=3000, targetId=编辑器targetId)

// 4. 获取所有已上传图片的微信CDN URL
browser(action="act", kind="evaluate", targetId=编辑器targetId, fn="""
  () => {
    const imgs = document.querySelectorAll('.ProseMirror img');
    return Array.from(imgs).map(img => ({
      src: img.src,
      isWx: img.src.includes('mmbiz')
    }));
  }
""")
// 5. 记录每张图片的 CDN URL，用于 Step 5b 嵌入HTML
//    格式：https://mmbiz.qpic.cn/...
```

**重复步骤2-4**，直到所有素材图片上传完毕。

**重要**：上传后图片会插到编辑器光标位置（通常在末尾），这不影响后续操作——Step 5b 会用完整的 innerHTML 覆盖整个编辑器内容。

**上传前准备**：
```bash
# 批量复制素材图片到 uploads 目录
mkdir -p /tmp/openclaw/uploads
cp ~/clawd/projects/MediaClaw/output/articles/{DATE}/{slug}/*.png /tmp/openclaw/uploads/
cp ~/clawd/projects/MediaClaw/output/articles/{DATE}/{slug}/*.jpg /tmp/openclaw/uploads/
```

**Step 5b：注入正文（含图片URL）**

⚠️ **注意**：HTML内容太长时，直接写在 `fn` 字符串里会被截断。**必须用CDP直接注入**：

```
// 方法A（推荐）：通过CDP直接注入长HTML
// 1. 先将完整HTML写入临时文件
write(path="/tmp/wechat-article.html", content=生成的HTML)

// 2. 通过CDP WebSocket注入（避免OpenClaw fn字符串长度限制）
exec(command="""
  unset ALL_PROXY all_proxy https_proxy
  python3 -c "
  import json, base64, websockets, httpx, asyncio
  async def inject():
      async with httpx.AsyncClient() as c:
          r = await c.get('http://127.0.0.1:18800/json/list')
          ws_url = next(t['webSocketDebuggerUrl'] for t in r.json() if 'TARGET_ID' in t['id'])
      with open('/tmp/wechat-article.html') as f:
          html = f.read()
      async with websockets.connect(ws_url) as ws:
          await ws.send(json.dumps({'id':1,'method':'Runtime.evaluate','params':{
              'expression': '(() => { const e = document.querySelector(\\".ProseMirror\\"); e.innerHTML = ' + json.dumps(html) + '; e.dispatchEvent(new Event(\\"input\\", {bubbles:true})); return \"injected: \" + html.length; })()',
              'returnByValue': True
          }}))
          resp = json.loads(await ws.recv())
          print(resp['result']['result']['value'])
  asyncio.run(inject())
  """
)

// 方法B（短文章可用）：直接通过OpenClaw evaluate
browser(action="act", kind="evaluate", targetId=编辑器targetId, fn="""
  () => {
    const editor = document.querySelector('.ProseMirror');
    if (!editor) return 'ProseMirror not found';
    const html = `... (2000字以内) ...`;
    editor.innerHTML = html;
    editor.dispatchEvent(new Event('input', { bubbles: true }));
    return 'injected: ' + html.length;
  }
""")
```

**HTML中嵌入图片的标准格式**（使用 Step 5a 获取的微信CDN URL）：
```html
<!-- 图片：居中 + 说明文字 -->
<p style="text-align:center;margin:16px 0">
  <img src="https://mmbiz.qpic.cn/..." style="max-width:100%;border-radius:4px" />
</p>
<p style="text-align:center;color:#888;font-size:13px;margin:4px 0 16px">图片说明文字</p>
```

**图片映射表**（在注入HTML前准备好）：
```javascript
const imageMap = {
  'github-repo.png': 'https://mmbiz.qpic.cn/.../0?wx_fmt=png',
  'reddit-claudeai.png': 'https://mmbiz.qpic.cn/.../0?wx_fmt=png',
  // ...
};
```

**图片嵌入规范**：
- 图片居中显示：`text-align:center`
- 最大宽度100%：`max-width:100%`
- 圆角：`border-radius:4px`
- 图片前后各留空段落
- 必须使用微信服务器上的图片URL（不支持外部链接图片）

**推荐正文样式**（直接写在 HTML style 里）：
```css
/* 段落 */
font-size: 15px; color: #3f3f3f; line-height: 1.75; margin: 8px 0;

/* H1 */
font-size: 22px; font-weight: bold; text-align: center; margin: 20px 0;

/* H2 */
font-size: 18px; font-weight: bold; border-left: 4px solid #1a73e8; 
padding-left: 10px; margin: 24px 0 12px;

/* H3 */
font-size: 16px; font-weight: bold; margin: 16px 0 8px;

/* 代码块 */
background: #f6f8fa; border-left: 3px solid #fe6; 
padding: 12px; overflow-x: auto; font-size: 13px;

/* 引用 */
border-left: 3px solid #ddd; color: #666; 
padding: 8px 12px; margin: 12px 0; background: #f9f9f9;

/* 表格 */
border-collapse: collapse; width: 100%; font-size: 14px; margin: 10px 0;
/* th */ background: #f5f5f5; border: 1px solid #ddd; padding: 8px;
/* td */ border: 1px solid #ddd; padding: 8px;

/* 图片 */
max-width: 100%; border-radius: 4px; margin: 12px 0;
```

### Step 6: 一键排版

⚠️ **重要**：一键排版会打开一个**新标签页**（`articlestruct` URL），不在编辑器页面内弹窗。

**Step 6a**：在编辑器页面点击"一键排版"：
```
browser(action="act", kind="evaluate", targetId=编辑器targetId, fn="""
  () => {
    const btns = document.querySelectorAll('span, div, button, a');
    for (const btn of btns) {
      if (btn.textContent.trim() === '一键排版' && btn.offsetParent !== null) {
        btn.click();
        return 'clicked 一键排版';
      }
    }
    return 'not found';
  }
""")
```

**Step 6b**：获取所有标签页，找到 `articlestruct` 页面：
```
browser(action="tabs", profile="openclaw")
```
找到 URL 包含 `articlestruct` 的标签页 → 使用该 `targetId`

**Step 6c**：在排版预览页面底部点击**"使用此排版"**确认按钮：
```
browser(action="snapshot", profile="openclaw", targetId=排版页targetId)
// 找到 button "使用此排版"
browser(action="act", kind="click", profile="openclaw", ref="使用此排版ref", targetId=排版页targetId)
```

点击后排版会自动应用并关闭排版页，回到编辑器标签页。

**Step 6d**：切回编辑器标签页，截图确认排版效果：
```
browser(action="screenshot", profile="openclaw", targetId=编辑器targetId)
```

### Step 7: 设置封面图

⚠️ **重要**：封面区域**没有** `input[type="file"]`！工具栏里的 file input 是正文图片上传。

**默认策略：从正文第一张图片选封面**（最简单可靠）

前提：Step 5 已将素材图片嵌入正文，编辑器中有图片。

**Step 7a（默认）**：点击封面区域的"从正文选择"链接：
```
browser(action="act", kind="evaluate", targetId=编辑器targetId, fn="""
  () => {
    const items = document.querySelectorAll('#js_cover_description_area a');
    for (const el of items) {
      if (el.textContent.includes('从正文选择') && el.offsetParent !== null) {
        el.click();
        return 'clicked 从正文选择';
      }
    }
    return 'not found';
  }
""")
browser(action="act", kind="wait", timeMs=2000, targetId=编辑器targetId)
```

此时弹出正文图片列表（class: `appmsg_content_img_item`），**默认选中第一张**：
```
browser(action="act", kind="evaluate", targetId=编辑器targetId, fn="""
  () => {
    const items = document.querySelectorAll('.appmsg_content_img_item');
    if (items.length > 0) { items[0].click(); return 'selected: ' + items.length; }
    return 'not found';
  }
""")
```

点击"**下一步**"进入裁剪确认页：
```
browser(action="act", kind="evaluate", targetId=编辑器targetId, fn="""
  () => {
    const btns = document.querySelectorAll('.weui-desktop-dialog__ft button');
    for (const btn of btns) {
      if (btn.textContent.trim() === '下一步' && btn.offsetParent !== null) {
        btn.click(); return 'clicked 下一步';
      }
    }
    return 'not found';
  }
""")
browser(action="act", kind="wait", timeMs=2000, targetId=编辑器targetId)
```

在裁剪确认页点击"**确认**"完成封面设置：
```
browser(action="act", kind="evaluate", targetId=编辑器targetId, fn="""
  () => {
    const btns = document.querySelectorAll('.weui-desktop-dialog__ft button');
    for (const btn of btns) {
      if (btn.textContent.trim() === '确认' && btn.offsetParent !== null) {
        btn.click(); return 'clicked 确认';
      }
    }
    return 'not found';
  }
""")
```

**Step 7b（备选）**：如果需要从图片库选特定封面（如专门的cover.png）：
```
// 1. 点击"从图片库选择"
browser(action="act", kind="evaluate", targetId=编辑器targetId, fn="""
  () => {
    const items = document.querySelectorAll('#js_cover_description_area a');
    for (const el of items) {
      if (el.textContent.includes('从图片库选择') && el.offsetParent !== null) {
        el.click();
        return 'clicked 从图片库选择';
      }
    }
    return 'not found';
  }
""")
browser(action="act", kind="wait", timeMs=2000, targetId=编辑器targetId)

// 2. 点击目标图片（通过图片名匹配）
browser(action="act", kind="evaluate", targetId=编辑器targetId, fn="""
  () => {
    const items = document.querySelectorAll('.weui-desktop-img-picker__item');
    for (const item of items) {
      const name = item.querySelector('strong');
      if (name && name.textContent.includes('cover')) {
        item.click();
        return 'selected: ' + name.textContent;
      }
    }
    return 'not found';
  }
""")
browser(action="act", kind="wait", timeMs=1000, targetId=编辑器targetId)

// 3. 点击"下一步"确认
browser(action="act", kind="evaluate", targetId=编辑器targetId, fn="""
  () => {
    const btns = document.querySelectorAll('button');
    for (const btn of btns) {
      if (btn.textContent.trim() === '下一步' && btn.offsetParent !== null) {
        btn.click();
        return 'clicked 下一步';
      }
    }
    return 'not found';
  }
""")
```

**封面图要求**：
- 比例：2.35:1（推荐）或 1:1
- 最小尺寸：900 × 383
- 格式：JPG / PNG
- 大小：≤ 2MB

**封面选择决策树**：
```
正文有图片？
├─ 是 → Step 7a「从正文选择」（默认第一张）
└─ 否 → Step 7b「从图片库选择」→ 选 cover.png
    └─ 图片库也没有？ → 先上传封面到图片库，再选
```

### Step 8: 保存到草稿箱

```
browser(action="act", kind="click", selector="保存为草稿", targetId=编辑器targetId)
```

或 JS：
```
browser(action="act", kind="evaluate", targetId=编辑器targetId, fn="""
  () => {
    const btns = document.querySelectorAll('button');
    for (const btn of btns) {
      if (btn.textContent.includes('保存为草稿') || btn.textContent.includes('草稿')) {
        btn.click();
        return 'clicked save draft';
      }
    }
    return 'save button not found';
  }
""")
```

等待保存完成 + 最终截图：
```
browser(action="act", kind="wait", timeMs=3000)
browser(action="screenshot", profile="openclaw", targetId=编辑器targetId)
```

---

## 🧩 辅助函数：Markdown → WeChat HTML

```javascript
function mdToWechatHtml(md) {
  let html = md;
  // 代码块
  html = html.replace(/```(\w*)\n([\s\S]*?)```/g, 
    '<pre style="background:#f6f8fa;border-left:3px solid #fe6;padding:12px;overflow-x:auto;font-size:13px"><code>$2</code></pre>');
  // H1
  html = html.replace(/^# (.+)$/gm, 
    '<h1 style="font-size:22px;font-weight:bold;text-align:center;margin:20px 0">$1</h1>');
  // H2
  html = html.replace(/^## (.+)$/gm, 
    '<h2 style="font-size:18px;font-weight:bold;border-left:4px solid #1a73e8;padding-left:10px;margin:24px 0 12px">$1</h2>');
  // H3
  html = html.replace(/^### (.+)$/gm, 
    '<h3 style="font-size:16px;font-weight:bold;margin:16px 0 8px">$1</h3>');
  // 粗体
  html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
  // 斜体
  html = html.replace(/\*(.+?)\*/g, '<em>$1</em>');
  // 行内代码
  html = html.replace(/`(.+?)`/g, '<code style="background:#f6f8fa;padding:2px 6px;border-radius:3px">$1</code>');
  // 引用
  html = html.replace(/^> (.+)$/gm, 
    '<blockquote style="border-left:3px solid #ddd;color:#666;padding:8px 12px;margin:12px 0;background:#f9f9f9">$1</blockquote>');
  // 无序列表
  html = html.replace(/^- (.+)$/gm, '<li style="margin:4px 0">$1</li>');
  // 分割线
  html = html.replace(/^---$/gm, '<hr style="border:none;border-top:1px solid #eee;margin:16px 0">');
  // 段落（空行分割）
  html = html.replace(/\n\n/g, '</p><p style="font-size:15px;color:#3f3f3f;line-height:1.75;margin:8px 0">');
  // 单换行
  html = html.replace(/\n/g, '<br>');
  return html;
}
```

---

## ⚠️ 已知陷阱（2026-04-15 实战验证）

### 1. 编辑器已从 UEditor 升级为 ProseMirror
- ❌ 旧：`#ueditor_0` iframe、`.edit_area`
- ✅ 新：`.ProseMirror` div（contenteditable）
- 内容注入必须用 `.innerHTML`，不能用 iframe 操作

### 2. 标题是 textarea 不是 input
- `document.querySelector('textarea[placeholder*="标题"]')` ✅
- `document.querySelector('input[placeholder*="标题"]')` ❌

### 3. "新的创作"点击可能打开新标签页
- 必须用 `browser(action="tabs")` 获取所有标签页
- 找到 URL 包含 `appmsg_edit_v2` 的标签页
- 后续所有操作使用该标签页的 `targetId`

### 4. QR码登录可能有验证码弹窗
- 腾讯会弹出滑块验证（captcha.gtimg.com）
- 需要人工处理或刷新页面重试

### 4.5 "一键排版"打开的是新标签页
- 点击"一键排版"后，排版预览在 `articlestruct` 新标签页中打开
- 必须用 `browser(action="tabs")` 找到该标签页
- 在排版页底部点击"使用此排版"确认
- 排版应用后自动返回编辑器标签页

### 4.6 封面区域没有 file input
- 工具栏的 `input[type="file"]` 是正文图片上传，**不是封面上传**
- 封面通过"从图片库选择" → 选图 → "下一步"流程
- 封面区域关键 CSS：`#js_cover_description_area`，按钮类名：`.js_cover_btn_area`

#### 4.6.1 「从正文选择」封面是3步流程，不是1步
- **Step 1**：点击正文图片列表中的目标图（class: `appmsg_content_img_item`）
- **Step 2**：点击"下一步"进入裁剪确认页
- **Step 3**：点击"确认"完成封面设置
- ❌ 错误：点击"从正文选择"后直接找"确定"按钮 → 找不到
- ✅ 正确：选图 → 下一步 → 确认

### 4.7 可能有多个干扰弹窗
- "未授权使用切换账号能力" → 点击"我知道了"
- "公众号尚未实名" → 点击"取消"或"前往实名"
- 多个弹窗叠加时需逐个关闭

### 5. OpenClaw `upload` 工具对微信编辑器无效
- `browser(action="upload")` 触发了 file chooser 但文件未真正传入编辑器
- ❌ OpenClaw upload: `browser(action="upload", selector="input[type='file']", paths=[...])`
- ✅ **必须用 CDP `DOM.setFileInputFiles`**:
```python
import json, websockets, httpx, asyncio

async def cdp_upload(ws_url, file_path):
    async with httpx.AsyncClient() as c:
        r = await c.get(f"http://127.0.0.1:18800/json/list")
        ws_url = next(t['webSocketDebuggerUrl'] for t in r.json() if TARGET in t['id'])
    async with websockets.connect(ws_url) as ws:
        # 获取 input 的 CDP objectId
        await ws.send(json.dumps({"id":1,"method":"Runtime.evaluate",
            "params":{"expression":"document.querySelector('input[type=\"file\"]')",
            "returnByValue":False}}))
        obj_id = json.loads(await ws.recv())['result']['result']['objectId']
        # 通过 CDP 设置文件
        await ws.send(json.dumps({"id":2,"method":"DOM.setFileInputFiles",
            "params":{"objectId":obj_id,"files":[file_path]}}))
        await ws.recv()

asyncio.run(cdp_upload(ws_url, "/tmp/openclaw/uploads/image.png"))
```
- 上传后等3-5秒，然后用 `.ProseMirror img` 获取 `mmbiz.qpic.cn` CDN URL
- 图片会插到编辑器光标位置，不影响后续 innerHTML 覆盖

### 6. 长HTML注入会被截断
- OpenClaw `evaluate` 的 `fn` 字段有字符长度限制
- ❌ 文章>2000字的HTML直接写在 fn 字符串里 → 截断报错 `Unexpected end of input`
- ✅ **必须用CDP直接注入**（见 Step 5b 方法A），将HTML先写入文件再通过CDP WebSocket传入

### 7. Cookie 不会自动持久化到文件
- OpenClaw Browser 使用自己的 Chromium profile
- 不像 Playwright 那样有 state.json
- 每次重启 OpenClaw Browser 可能需要重新扫码
- **解决方案**：保持 OpenClaw Browser 长期运行，避免频繁重启

### 8. URL 导航需要 token
- 直接访问 `mp.weixin.qq.com/cgi-bin/appmsg?...` 会跳转到登录页
- 必须从首页（带 token 的 URL）进入，或通过点击导航
- **不要直接 navigate 到需要 token 的 URL**

---

## 📦 输入规范

```yaml
输入:
  article_path: string     # Markdown 文章路径（必需）
  cover_path: string       # 封面图路径，2.35:1 比例（必需）
  author: string           # 作者名（可选，默认留空）
  image_paths: list        # 素材图片路径列表（可选，嵌入正文）
```

**注意**：不填写摘要字段（留空，微信自动抓取正文开头）。

## 📤 输出

```yaml
输出:
  status: ok | error
  draft_saved: true/false
  screenshot_path: string
  title: string
  content_length: number
```

---

## 🏗️ 与其他 Skill 的关系

| Skill | 关系 |
|-------|------|
| `wemp-operator` | **保留** — 全 API 封装（统计/评论/粉丝/素材/群发），不走浏览器 |
| `wechat-toolkit` | **保留** — 文章下载工具 |
| `wechat-channel` | **保留** — 视频号发布 |
| `daily-gzh-content` | **保留** — 公众号内容生成 |
| ~~wechat-mp-smart-publish~~ | **已删除** — 被 gzh-publisher 替代 |
| ~~wechat-mp-api-draft~~ | **已删除** — 被 gzh-publisher 替代 |

---

## 更新日志

- **v2.5.0** (2026-04-17): 新增 publish.py 脚本
  - 新增 `scripts/publish.py`，一行命令完成完整发布流程
  - CDP-based 图片上传（DOM.setFileInputFiles）
  - Markdown → WeChat HTML 转换内置
  - 一键排版 + 封面设置自动化
  - 快速使用文档加到 SKILL.md 顶部

- **v2.4.0** (2026-04-15): 实战踩坑补全
  - 新增陷阱5: OpenClaw `upload` 对微信无效，必须用 CDP `DOM.setFileInputFiles`
  - 新增陷阱6: 长HTML注入截断问题，必须用CDP WebSocket
  - 修正陷阱4.6.1: 「从正文选择」封面是3步（选图→下一步→确认），不是1步
  - Step 7a: 补全完整3步代码（`appmsg_content_img_item` 选择器）

- **v2.3.0** (2026-04-15): Step 5/7 重构
  - Step 5a: 完整素材图片上传流程（逐张上传 → 记录CDN URL）
  - Step 5b: 新增CDP直接注入方法（解决长HTML截断问题）
  - Step 7: 封面默认从正文第一张图片选择（简化流程）
  - 新增封面选择决策树
  - 新增图片嵌入标准格式（居中 + 说明文字）
  - 新增素材图片上传+嵌入正文流程（Step 5a/5b）
  - 移除摘要填写（留空，微信自动抓取）
  - 图片必须使用微信服务器URL（不支持外部链接）

- **v2.1.0** (2026-04-15): 实战修复
  - 修复一键排版流程：排版预览在 `articlestruct` 新标签页中打开，需切换标签页后点击"使用此排版"确认
  - 修复封面上传流程：封面区域无 `input[type="file"]`，需通过"从图片库选择" → 选图 → "下一步"
 - 新增干扰弹窗处理："未授权切换账号"、"公众号尚未实名"等
  - 新增 Step 2 修正：使用 `new-creation__menu-item` 类名精确定位"文章"按钮

- **v2.0.0** (2026-04-15): 统一重建
  - 废弃所有旧公众号发布 skill（smart-publish / api-draft / adapter）
  - 基于 OpenClaw Browser 重写，不依赖 Playwright 独立实例
  - 更新编辑器 selector（UEditor → ProseMirror）
  - 新增"一键排版"步骤
  - 新增未登录自动截图发QR码流程
  - 新增完整 Markdown → WeChat HTML 转换指南
