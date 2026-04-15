---
name: douyin-publisher
description: "将 Markdown 文章自动发布到抖音（Douyin）草稿箱（图文模式）。支持图片上传、标题/描述填充、标签嵌入。基于 Playwright CDP 直连浏览器操作。"
license: MIT
metadata:
  version: 1.0.0
  author: xiaocode
  domains: [content, publishing, automation, douyin]
  type: automation
  requires: [playwright, browser-access]
---

# Douyin Publisher — 抖音自动发布（图文）

> **将 Markdown 文章一键发布到抖音创作者平台草稿箱（图文模式）。**

## 什么时候用

- 有了写好的文章（markdown），需要上传到抖音草稿箱
- 图文笔记模式（非视频）
- 批量发布或自动化内容分发 pipeline

## 不适用

- ❌ 视频内容 — 当前仅支持图文
- ❌ 直接正式发布 — 仅支持存草稿
- ❌ 需要编辑已发布内容

## 前置条件

| 条件 | 说明 | 检查 |
|------|------|------|
| Playwright | Python playwright 库 | `pip show playwright` |
| OpenClaw Browser | 浏览器运行中 | `curl -s http://127.0.0.1:18800/json/version` |
| 抖音 Cookie | 有效 Playwright state | `ls ~/.playwright-data/douyin/state-default.json` |

## 输入

```yaml
输入参数:
  article_path: string    # Markdown 文件路径
  cover_path: string      # 封面图路径 (jpg/png, 推荐 3:4, ≤50MB)
  decision: draft         # 当前仅支持 draft
```

## 输出

```yaml
输出:
  status: ok | error
  draft_saved: true/false
  screenshot_path: string
  title: string
  title_truncated: boolean
  content_length: number
  tags_added: list
```

## 使用方法

```bash
python3 ~/clawd/skills/douyin-publisher/scripts/publish.py \
  --article article.md --cover cover.jpg --decision draft
```

## 核心流程

```
解析 Markdown → 加载 Cookie → 打开创作者页面 → 切换"发布图文" tab
→ 关闭草稿恢复弹窗 → 上传图片 → 填充标题 → 填充描述(含标签)
→ 截图 → 存草稿(暂存离开)
```

## 关键 Selector（2026-04-14 验证）

| 元素 | CSS Selector |
|------|-------------|
| Tab切换 | `div[class*='tab-item']` (text="发布图文") |
| 图片上传 | `input[type="file"][accept*="image"]` (multiple=true) |
| 标题输入 | `input[placeholder="添加作品标题"]` |
| 描述编辑器 | `div.editor-comp-publish[contenteditable="true"]` |
| 发布按钮 | `button[class*='primary']` (发布) |
| 草稿按钮 | `button[class*='cancel-btn']` (暂存离开) |

## 边界处理

### 1. 标题 20 字限制
抖音图文标题限制 20 字，智能截断在标点处。

### 2. 描述 1000 字限制
正文+标签总计不超过 1000 字。

### 3. contenteditable 编辑器
抖音使用普通 contenteditable div（非 ProseMirror），用 innerHTML + input event 填充。

### 4. 标签嵌入描述
标签以 `#话题` 格式追加到描述正文末尾。

### 5. 草稿恢复弹窗
如果上次有未发布图文，会出现"继续编辑/放弃"弹窗。脚本自动点击"放弃"。

### 6. 登录态管理
- Cookie 位置：`~/.playwright-data/douyin/state-default.json`
- 首次使用需扫码登录
- Cookie 过期后需重新扫码

## 与 XHS 的差异

| 维度 | XHS | 抖音 |
|------|-----|------|
| 编辑器 | TipTap ProseMirror | 普通 contenteditable |
| 标签 | 话题面板或正文嵌入 | 正文嵌入 #话题 |
| 登录 | Cookie 即可 | 必须扫码/验证码登录 |
| 草稿恢复 | 无弹窗 | 有"继续编辑/放弃"弹窗 |

## 触发词

- "发布到抖音"、"发抖音"、"douyin发布"
- "抖音草稿"、"douyin draft"
- "publish douyin"

## 更新日志

- **v1.0.0** (2026-04-14): 初始版本
  - 10/10 selector 验证
  - 图文模式支持
  - 草稿恢复弹窗处理
  - 标签嵌入描述
