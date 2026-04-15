---
name: wechat-mp-smart-publish
description: "微信公众号智能发布全流程：标题优化、排版、封面图、发布。支持 Markdown→微信HTML转换、UEditor排版(15px/#3f3f3f/1.75倍行高)、封面图上传、自动存草稿。基于 Playwright CDP 直连浏览器操作。"
license: MIT
metadata:
  version: 1.0.0
  author: ives-cco
  domains: [content, publishing, automation, wechat]
  type: automation
  requires: [playwright, browser-access]
---

# WeChat MP Smart Publish — 公众号自动发布

> **将 Markdown 文章一键发布到微信公众号草稿箱。**

## 什么时候用

- 有了写好的公众号文章（markdown），需要上传到草稿箱
- 批量发布内容到微信公众号
- 自动化内容分发 pipeline 中的一环
- 其他 agent（小content等）需要发布公众号内容时

## 不适用

- ❌ 需要直接正式发布（不是草稿）— 当前仅支持存草稿，由人工最终发布
- ❌ 视频内容 — 仅支持图文消息
- ❌ 需要编辑已发布文章

## 前置条件

| 条件 | 说明 | 检查方法 |
|------|------|---------|
| Playwright | Python playwright 库 | `pip show playwright` |
| OpenClaw Browser | 浏览器服务运行中 | `openclaw browser status` 或检查 `127.0.0.1:18800` |
| 微信 Cookie | Playwright state 文件有效 | `cat ~/.playwright-data/wechat/state-default.json \| python3 -c "import json,sys; d=json.load(sys.stdin); print(f'Cookies: {len(d.get(\"cookies\",[]))}')"` |
| Cookie 未过期 | cookies 包含 qname 和 uin | 检查 cookie 中 qname 字段 |

## 输入

```yaml
输入参数:
  article_path: string    # Markdown 文件路径
  cover_path: string      # 封面图路径 (jpg/png, 推荐 2.35:1 比例, ≥900x383)
  decision: draft         # 当前仅支持 draft
```

### Markdown 格式要求

```markdown
# 标题（文章标题，≤64字）

正文内容，支持 **加粗**、*斜体*、`行内代码` 等常见 Markdown 语法。

## 子标题

段落文字...
```

## 输出

```yaml
输出:
  status: ok | error
  draft_saved: true/false
  draft_url: string       # 草稿箱URL
  screenshot_path: string # 截图路径
  title: string           # 实际使用的标题
  content_length: number  # 正文字数
```

## 使用方法

### 方式一：直接运行脚本

```bash
python3 ~/clawd/skills/wechat-mp-smart-publish/scripts/publish.py \
  --article /path/to/article.md \
  --cover /path/to/cover.jpg \
  --decision draft
```

### 方式二：作为模块调用

```python
import asyncio
from scripts.publish import publish_to_wechat

result = asyncio.run(publish_to_wechat(
    article_path="/path/to/article.md",
    cover_path="/path/to/cover.jpg",
    decision="draft",
))
print(result)
```

### 方式三：Agent 调用（推荐）

其他 agent 通过 sessions_send 请小code 执行：

```
请发布文章到微信公众号草稿箱：
- 文章: ~/clawd/docs/daily-content/2026-04-14/gzh/amd-gaia-article.md
- 封面: ~/clawd/docs/daily-content/2026-04-14/gzh/cover.jpg
```

## 核心流程

```
解析 Markdown → Markdown→HTML 转换 → 启动浏览器 → 加载 Cookie
→ 打开公众号首页 → 点击"新的创作" → 上传封面图
→ 填充标题 → 切换到图文消息 → 粘贴正文HTML
→ 截图 → 存草稿
```

## 排版规范

| 参数 | 值 |
|------|-----|
| 正文字号 | 15px |
| 正文字色 | #3f3f3f |
| 行高 | 1.75 倍 |
| 段落间距 | 1em |
| 标题字号 | H2: 18px bold, H3: 16px bold |
| 代码块 | 背景 #f6f8fa，左边框 3px solid #fe6 |

## 关键 Selector（2026-04-14 验证）

| 元素 | CSS Selector | 说明 |
|------|-------------|------|
| 首页入口 | "新的创作" (button/tab text) | 新建图文 |
| 封面图上传 | `input[type="file"]` | 图片上传 input |
| 标题输入 | `input[name="title"]` | 文章标题 |
| 图文切换 | "图文" (tab text) | 切换到富文本编辑器 |
| 富文本编辑器 | `#ueditor_0` iframe 或 `.edit_area` | UEditor iframe |
| 预览按钮 | "预览" (button text) | 预览草稿 |
| 存草稿按钮 | "保存" (button text) | 存为草稿 |

## 边界处理

### 1. 标题 64 字限制
标题超出 64 字时自动截断。

### 2. Markdown→HTML 转换
使用基础转换规则：
- `# H1` → `<h1>`
- `**bold**` → `<strong>bold</strong>`
- `*italic*` → `<em>italic</em>`
- `` `code` `` → `<code>code</code>`
- 空行 → `<br>`
- `---` → `<hr>`

### 3. UEditor 特殊填充
UEditor 是富文本 iframe，不能直接操作内容。需通过：
```python
# 切换到编辑模式
await page.evaluate('''() => {
    const editor = document.querySelector('#ueditor_0');
    if (editor && editor.contentWindow) {
        editor.contentWindow.postMessage({type: 'setContent', content: html}, '*');
    }
}''')
```

### 4. 封面图比例
微信封面图推荐比例 2.35:1，最小尺寸 900x383。

### 5. Cookie 管理
- Cookie 文件位置：`~/.playwright-data/wechat/state-default.json`
- 有效期约 7-30 天，需要定期通过浏览器登录续期
- 加载方式：`await context.add_cookies(cookies_from_state)`
- 检查登录：页面出现"新的创作"按钮即为已登录

## 常见问题

### Q: 页面找不到"新的创作"按钮？
A: Cookie 过期，需重新扫码登录。执行：`openclaw browser open --url https://mp.weixin.qq.com`

### Q: 富文本编辑器无法填充内容？
A: UEditor 需要切换到编辑模式。先点击编辑器区域激活，再执行 JS 注入。

### Q: 浏览器连接失败？
A: 检查 OpenClaw browser 是否运行：`curl -s http://127.0.0.1:18800/json/version`

### Q: Cookie 过期怎么办？
A: 需要 Daniel 通过浏览器登录微信公众号平台，保存 Playwright state：
```bash
openclaw browser open --url https://mp.weixin.qq.com
# 手动扫码登录后
# Cookie 会自动保存
```

## 依赖

```
playwright>=1.40.0
Pillow>=10.0.0 (图片验证)
markdown>=3.4.0 (可选，markdown→html)
```

## 触发词

- "发布到公众号"、"发布微信公众号"、"发微信"
- "公众号草稿"、"wechat publish"、"wechat mp"
- "公众号发布"、"mp.weixin publish"

## 更新日志

- **v1.0.0** (2026-04-14): 初始版本
  - 基础 Markdown→HTML 转换
  - UEditor 富文本填充
  - 封面图上传
  - 草稿箱保存
