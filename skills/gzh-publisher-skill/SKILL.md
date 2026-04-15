---
name: gzh-publisher-skill
description: "微信公众号统一发布技能：通过 OpenClaw Browser 自动化完成登录、写文章、一键排版、封面、存草稿。唯一官方公众号发布方式。"
license: MIT
metadata:
  version: 2.2.0
  author: Daniel Li / 小a CEO
  domains: [content, publishing, automation, wechat]
  type: automation
  requires: [openclaw-browser]
---

# GZH Publisher Skill — 公众号统一发布

> **唯一官方微信公众号发布方式。基于 OpenClaw Browser 自动化。**

## 什么时候用

- 有 Markdown 文章需要发布到微信公众号草稿箱
- Agent 需要"发布公众号"、"公众号草稿"、"发微信"时
- MediaClaw content pipeline 的公众号发布环节

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
│  Step 5: 注入正文内容                                  │
│  JS → .ProseMirror div.innerHTML = HTML               │
│  （含素材图片: 先上传到正文 → 记录URL → 嵌入HTML）       │
├─────────────────────────────────────────────────────┤
│  Step 6: 一键排版                                     │
│  click "一键排版" → 等待排版完成 → 截图确认             │
├─────────────────────────────────────────────────────┤
│  Step 7: 上传封面图                                   │
│  JS set input[type="file"] → 选择封面图文件             │
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

**Step 5a：上传素材图片到正文**

如果有素材图片（`image_paths`），需要先通过工具栏上传到微信服务器获取图片URL，再嵌入HTML：

```
// 对每张素材图片，上传并获取URL
browser(action="upload", profile="openclaw", targetId=编辑器targetId,
  selector="input[type='file']", paths=["/path/to/image1.jpg"])
// 上传后微信会在编辑器中插入图片，获取其src URL
browser(action="act", kind="evaluate", targetId=编辑器targetId, fn="""
  () => {
    const imgs = document.querySelectorAll('.ProseMirror img');
    return Array.from(imgs).map(img => img.src);
  }
""")
```

或者使用"从图片库选择"上传素材图片到微信图片库，再获取URL。

**Step 5b：注入正文（含图片）**

```
browser(action="act", kind="evaluate", targetId=编辑器targetId, fn="""
  () => {
    const editor = document.querySelector('.ProseMirror');
    if (!editor) return 'ProseMirror not found';
    
    const html = `<section>
      <h1 style="...">标题</h1>
      <p style="...">正文段落...</p>
      <!-- 素材图片嵌入 -->
      <p style="text-align:center;margin:16px 0">
        <img src="上传后获取的图片URL" style="max-width:100%;border-radius:4px" />
      </p>
      <p style="...">图片说明文字...</p>
      <h2 style="...">子标题</h2>
      ...
    </section>`;
    
    editor.innerHTML = html;
    editor.dispatchEvent(new Event('input', { bubbles: true }));
    return 'injected, length: ' + html.length;
  }
""")
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

### Step 7: 上传封面图

⚠️ **重要**：封面区域**没有** `input[type="file"]`！工具栏里的 file input 是正文图片上传。

封面上传通过点击封面区域触发，有4种方式：
- **从图片库选择**（推荐自动化）
- 从正文选择
- 微信扫码上传
- AI 配图

**Step 7a**：点击封面区域的"从图片库选择"链接：
```
browser(action="act", kind="evaluate", targetId=编辑器targetId, fn="""
  () => {
    const items = document.querySelectorAll('#js_cover_description_area a');
    for (const el of items) {
      if (el.textContent.trim() === '从图片库选择' && el.offsetParent !== null) {
        el.click();
        return 'clicked 从图片库选择';
      }
    }
    return 'not found';
  }
""")
```

**Step 7b**：等待图片库弹窗打开，找到目标图片（如 cover.jpg）并**点击选中**（需要高亮/checkmark）：
```
browser(action="snapshot", profile="openclaw", targetId=编辑器targetId)
// 找到图片名对应的 strong 或 link 元素，点击选中
```

**Step 7c**：点击"**下一步**"按钮确认选择：
```
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

**备选方案**：如果图片库没有合适图片，先通过工具栏 `input[type="file"]` 上传到正文，然后用"从正文选择"

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

### 4.7 可能有多个干扰弹窗
- "未授权使用切换账号能力" → 点击"我知道了"
- "公众号尚未实名" → 点击"取消"或"前往实名"
- 多个弹窗叠加时需逐个关闭

### 5. Cookie 不会自动持久化到文件
- OpenClaw Browser 使用自己的 Chromium profile
- 不像 Playwright 那样有 state.json
- 每次重启 OpenClaw Browser 可能需要重新扫码
- **解决方案**：保持 OpenClaw Browser 长期运行，避免频繁重启

### 6. URL 导航需要 token
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

- **v2.2.0** (2026-04-15): 素材图片嵌入 + 移除摘要
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
