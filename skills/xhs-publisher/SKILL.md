---
name: xhs-publisher
description: "将 Markdown 文章自动发布到小红书（XHS）草稿箱。支持多图上传（封面+素材）。"
metadata: {"version":"1.5.0","author":"xiaocode + CCO Ives","domains":["content","publishing","automation","xiaohongshu"],"type":"automation"}
---
description: "将 Markdown 文章自动发布到小红书（XHS）草稿箱。支持多图上传（封面+素材）、标题/正文填充、标签匹配、排版优化检查。基于 Playwright file_chooser API + CDP 操作。"
license: MIT
metadata:
  version: 1.5.0
  author: xiaocode + CCO Ives
  domains: [content, publishing, automation, xiaohongshu]
  type: automation
  requires: [playwright, openclaw-browser]
---

# XHS Publisher — 小红书自动发布 v1.5

> **将 Markdown 文章一键发布到小红书创作者平台草稿箱。支持多图上传。**

## 什么时候用

- 有了写好的 XHS 文章（markdown），需要上传到草稿箱
- 需要上传封面 + 多张素材图（最多18张）
- 批量发布内容到 XHS
- 自动化内容分发 pipeline 中的一环
- 其他 agent 需要发布 XHS 内容时

> 📋 **发布前请确认内容合规**：`~/clawd/projects/MediaClaw/references/platforms/xiaohongshu.md`

## 不适用

- ❌ 需要直接正式发布（不是草稿）— 当前仅支持存草稿，由人工最终发布
- ❌ 视频内容 — 仅支持图文笔记
- ❌ 需要编辑已发布笔记

## 前置条件

| 条件 | 说明 | 检查方法 |
|------|------|---------|
| Playwright | Python playwright 库 | `pip show playwright` |
| OpenClaw Browser | 浏览器服务运行中 | `curl -s http://127.0.0.1:18800/json/version` |
| XHS Cookie | Playwright state 文件有效 | `~/.playwright-data/xiaohongshu/state-default.json` |
| Cookie 未过期 | cookies.expires > 当前时间 | 检查 cookie 中 a1 的 expires 字段 |
| **unset代理** | CDP WebSocket会被代理阻断 | `unset ALL_PROXY all_proxy https_proxy http_proxy` |

## 输入

```yaml
输入参数:
  article_path: string        # Markdown 文件路径
  cover_path: string          # 封面图路径 (jpg/png/webp, 推荐 3:4 ≥720x960)
  images: list[string]        # 追加素材图片 (可选, 最多17张, 总计≤18)
  decision: draft             # 当前仅支持 draft
```

### Markdown 格式要求

```markdown
📌 标题：你的标题（≤20字）
🏷️ 标签：#标签1 #标签2 #标签3

📝 正文：

正文内容...
（≤1000字）
```

## 输出

```yaml
输出:
  status: ok | error
  draft_saved: true/false
  draft_count: "草稿箱(N)"
  title: string
  title_truncated: boolean
  content_length: number
  images_uploaded: number    # 上传图片总数 (含封面)
  tags_added: list[string]
```

## 使用方法

### 单图（封面 only）

```bash
unset ALL_PROXY all_proxy https_proxy http_proxy
python3 ~/clawd/projects/MediaClaw/skills/xhs-publisher/scripts/publish.py \
  --article /path/to/article.md \
  --cover /path/to/cover.jpg \
  --decision draft
```

### 多图（封面 + 素材图）

```bash
unset ALL_PROXY all_proxy https_proxy http_proxy
python3 ~/clawd/projects/MediaClaw/skills/xhs-publisher/scripts/publish.py \
  --article /path/to/article.md \
  --cover /path/to/cover.jpg \
  --images img1.jpg img2.png img3.jpg \
  --decision draft
```

### Shell glob 批量素材

```bash
python3 publish.py \
  --article article.md \
  --cover cover.jpg \
  --images 素材/*.png 素材/*.jpg
```

### 作为模块调用

```python
import asyncio
from scripts.publish import publish_to_xhs

result = asyncio.run(publish_to_xhs(
    article_path="/path/to/article.md",
    cover_path="/path/to/cover.jpg",
    images=["img1.jpg", "img2.png"],  # 可选
    decision="draft",
))
print(result)
```

### Agent 调用（推荐）

```
请发布文章到 XHS 草稿箱：
- 文章: ~/clawd/projects/MediaClaw/output/articles/2026-04-16/claude-vs-codex/xhs/article.md
- 封面: ~/clawd/projects/MediaClaw/output/articles/2026-04-16/claude-vs-codex/xhs/cover-3x4.jpg
- 素材: ~/clawd/projects/MediaClaw/output/articles/2026-04-16/claude-vs-codex/素材/*.png
```

## 核心流程

```
解析 Markdown → 验证图片 → 启动浏览器 → 加载 Cookie → 打开创作者页面
→ 切换到"上传图文"tab（最后一个可见tab）
→ file_chooser 上传封面 → 等待编辑器出现
→ 逐张追加素材图（通过编辑器内 file input）
→ 填充标题 → 填充正文 → 匹配标签 → 截图 → 存草稿
```

## v1.5 关键技术变更

### ❌ 旧方案（v1.4，已废弃）

```python
# 不工作：set_input_files 不触发 XHS React change 事件
await file_input.set_input_files(paths)
```

### ✅ 新方案（v1.5，已验证）

```python
# 1. 用 file_chooser API（Playwright 标准文件上传方式）
async with page.expect_file_chooser() as fc:
    await file_input.evaluate("el => el.click()")
file_chooser = await fc.value
await file_chooser.set_files(path)

# 2. 点击最后一个可见的"上传图文"tab（XHS 有3个重复 tab）
tabs = document.querySelectorAll('div.creator-tab')
imageTabs = tabs.filter(t => t.text === '上传图文' && visible)
imageTabs[imageTabs.length - 1].click()  # 最后一个！
```

### 多图上传流程

```
1. 封面 → file_chooser.set_files(cover) → 等待8s → 编辑器出现
2. 素材图1 → 编辑器内 file_input.click() → file_chooser.set_files(img1) → 等待4s
3. 素材图2 → 同上
...
N. 最多封面+17张追加（XHS 总上限18张）
```

**关键发现**：
- XHS file input 没有 `[multiple]` 属性（Playwright 读取到的 multiple=false）
- 即使注入 `multiple=true`，`set_input_files([file1, file2])` 也不触发 React
- `file_chooser.set_files()` 是唯一可靠的上传方式
- 编辑器内追加图片通过隐藏的 `input[type='file']` 触发

## 关键 Selector

| 元素 | CSS Selector | 说明 |
|------|-------------|------|
| Tab切换 | `div.creator-tab` (文本="上传图文") | **点击最后一个可见的** |
| 图片上传 | `input.upload-input[type="file"]` | 隐藏元素，用 file_chooser |
| 编辑器内图片 | `input[type="file"]` | 编辑器内的隐藏 file input |
| 标题输入 | `input.d-text[type="text"]` | placeholder="填写标题会有更多赞哦" |
| 正文编辑器 | `div.tiptap.ProseMirror[contenteditable="true"]` | TipTap ProseMirror |
| 话题按钮 | `button.contentBtn.topic-btn` | 打开标签面板 |
| 存草稿按钮 | "暂存离开" (button text) | JS click by textContent |
| 发布按钮 | "发布" (button text) | JS click by textContent |

## 边界处理

### 1. 标题 20 字限制
XHS 标题严格限制 20 字（含标点），超出自动截断并标记。

### 2. 正文 1000 字限制
XHS 正文限制 1000 字（含空格和 emoji），超出自动截断。

### 3. 图片上限 18 张
封面 + 追加图片总计不超过 18 张。超出自动截断并警告。

### 4. ProseMirror 填充
```python
await page.evaluate('''([el, html]) => {
    el.innerHTML = html;
    el.dispatchEvent(new Event("input", { bubbles: true }));
}''', [editor, body_html])
```

### 5. 标签策略
使用策略 1：将标签以 `#标签1 #标签2` 追加到正文末尾。XHS 自动识别并高亮。

### 6. 上传图文 Tab 切换（踩坑）
XHS 有 **3个** 重复的 `div.creator-tab`（文本="上传图文"）。
- 第一个：可能指向视频区域（点击后进入错误状态）
- **最后一个**：正确的图文上传入口

```python
# 点击最后一个可见的"上传图文"tab
tabs = document.querySelectorAll('div.creator-tab')
imageTabs = Array.from(tabs).filter(t => t.textContent.trim() === '上传图文' && t.getBoundingClientRect().x > 0)
imageTabs[imageTabs.length - 1].click()
```

### 7. 代理问题
`ALL_PROXY` / `socks://` 环境变量会阻断 Playwright CDP WebSocket 连接。
运行脚本前必须：
```bash
unset ALL_PROXY all_proxy https_proxy http_proxy
```

## 安全机制

### Pre-flight Health Check

每次发布前自动检查：浏览器连接、Cookie有效性、文件存在性、图片格式。

### 安全截图（Safety Screenshots）

```
打开页面 → [截图#1] → 上传封面 → [截图#2]
→ 填标题 → [截图#3] → 填正文 → [截图#4]
→ 存草稿 → [截图#5] → 草稿确认 → [截图#6]
```

截图目录：`/tmp/xhs_safety/`

### 重试机制

| 失败场景 | 重试次数 | 退避策略 |
|---------|---------|---------|
| 网络超时 | 3次 | 10s → 20s → 40s |
| Selector 未找到 | 2次 | 5s → 10s |
| 文件上传失败 | 3次 | 10s → 20s → 40s |
| 页面加载失败 | 2次 | 15s → 30s |

## 常见问题

### Q: 图片上传后编辑器没出现？
A: 可能点错了tab。XHS有3个重复tab，必须点最后一个。v1.5已修复。

### Q: 多图上传报 "Non-multiple file input"？
A: v1.5已改用file_chooser API，不再依赖input[multiple]属性。

### Q: CDP连接超时？
A: 检查是否设置了代理环境变量：`unset ALL_PROXY all_proxy https_proxy http_proxy`

### Q: Cookie 过期怎么办？
A: Daniel通过浏览器登录XHS创作者平台，Cookie自动保存。

## 依赖

```
playwright>=1.40.0
Pillow (可选, 图片尺寸验证)
```

## 触发词

- "发布到小红书"、"发XHS"、"上传到XHS草稿箱"
- "小红书发布"、"XHS publish"、"小红书草稿"
- "publish xhs"、"xhs draft"、"MediaClaw XHS"
- "XHS多图发布"、"小红书多图上传"

## 更新日志

- **v1.5.0** (2026-04-16): 多图上传 + 核心修复
  - ✅ 多图上传：封面 + 追加素材图（最多18张）
  - ✅ 修复：使用 `file_chooser` API 替代 `set_input_files`（React不响应后者）
  - ✅ 修复：点击最后一个可见"上传图文"tab（XHS有3个重复tab）
  - ✅ 新增 `--images` 参数（可选，支持shell glob）
  - ✅ 新增图片验证（存在性、格式、上限18张）
  - ✅ 新增代理环境变量 unset 提醒
  - 🧪 实测通过：单图草稿(24) ✅ 多图(1封面+2素材)草稿(26) ✅
- **v1.2.0** (2026-04-16): 安全增强
  - Pre-flight health check
  - 安全截图机制
  - 重试机制 + 指数退避
  - 错误处理策略细化
- **v1.1.0** (2026-04-14): 初始版本
  - 完整 selector 验证
  - ProseMirror 填充方案
  - 标题/正文限制处理
  - 标签嵌入策略
