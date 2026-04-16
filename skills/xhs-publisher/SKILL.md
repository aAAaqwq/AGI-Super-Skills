---
name: xhs-publisher
description: "将 Markdown 文章自动发布到小红书（XHS）草稿箱。支持封面图上传、标题/正文填充、标签匹配、排版优化检查。基于 OpenClaw Browser（优先）+ Playwright CDP 操作。"
license: MIT
metadata:
  version: 1.2.0
  author: xiaocode + CCO Ives
  domains: [content, publishing, automation, xiaohongshu]
  type: automation
  requires: [playwright, openclaw-browser]
---

# XHS Publisher — 小红书自动发布 v1.2

> **将 Markdown 文章一键发布到小红书创作者平台草稿箱。**

## 什么时候用

- 有了写好的 XHS 文章（markdown），需要上传到草稿箱
- 批量发布内容到 XHS
- 自动化内容分发 pipeline 中的一环
- 其他 agent（小content等）需要发布 XHS 内容时

> 📋 **发布前请确认内容合规**：`~/clawd/projects/MediaClaw/references/platforms/xiaohongshu.md`（社区规范、AIGC标注要求、导流禁止）

## 不适用

- ❌ 需要直接正式发布（不是草稿）— 当前仅支持存草稿，由人工最终发布
- ❌ 视频内容 — 仅支持图文笔记
- ❌ 需要编辑已发布笔记

## 前置条件

| 条件 | 说明 | 检查方法 |
|------|------|---------|
| Playwright | Python playwright 库 | `pip show playwright` |
| OpenClaw Browser | 浏览器服务运行中 | `openclaw browser status` 或检查 `127.0.0.1:18800` |
| XHS Cookie | Playwright state 文件有效 | `cat ~/.playwright-data/xiaohongshu/state-default.json \| python3 -c "import json,sys; d=json.load(sys.stdin); print(f'Cookies: {len(d.get(\"cookies\",[]))}')"` |
| Cookie 未过期 | cookies.expires > 当前时间 | 检查 cookie 中 a1 的 expires 字段 |

## 输入

```yaml
输入参数:
  article_path: string    # Markdown 文件路径
  cover_path: string      # 封面图路径 (jpg/png/webp, 推荐 3:4 比例, ≥720x960)
  decision: draft         # 当前仅支持 draft
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
  draft_count: "草稿箱(N)"  # 保存后草稿箱数量
  screenshot_path: string   # 截图路径
  title: string             # 实际使用的标题
  title_truncated: boolean  # 标题是否被截断
  content_length: number    # 正文字数
```

## 使用方法

### 方式一：直接运行脚本

```bash
python3 ~/clawd/skills/xhs-publisher/scripts/publish.py \
  --article /path/to/article.md \
  --cover /path/to/cover.jpg \
  --decision draft
```

### 方式二：作为模块调用

```python
import asyncio
from scripts.publish import publish_to_xhs

result = asyncio.run(publish_to_xhs(
    article_path="/path/to/article.md",
    cover_path="/path/to/cover.jpg",
    decision="draft",
))
print(result)
```

### 方式三：Agent 调用（推荐）

其他 agent 通过 sessions_send 请小code 执行：

```
请发布文章到 XHS 草稿箱：
- 文章: ~/clawd/docs/daily-content/2026-04-14/xhs/article.md
- 封面: ~/clawd/docs/daily-content/2026-04-14/xhs/cover-1.jpg
```

## 核心流程

```
解析 Markdown → 启动浏览器 → 加载 Cookie → 打开创作者页面
→ 切换到"上传图文"tab → 上传封面图 → 等待编辑器出现
→ 填充标题 → 填充正文 → 匹配标签 → 截图 → 存草稿
```

## 关键 Selector（2026-04-14 验证）

| 元素 | CSS Selector | 说明 |
|------|-------------|------|
| Tab切换 | `div.creator-tab` (文本="上传图文") | 需 JS click，筛选可见元素 |
| 图片上传 | `input.upload-input[type="file"]` | 隐藏元素 (0x0)，必须用 CSS selector |
| 标题输入 | `input.d-text[type="text"]` | placeholder="填写标题会有更多赞哦" |
| 正文编辑器 | `div.tiptap.ProseMirror[contenteditable="true"]` | TipTap ProseMirror |
| 话题按钮 | `button.contentBtn.topic-btn` | 打开标签面板 |
| 标签输入 | `input.d-text.--color-text-title` | 输入后 XHS 自动推荐 |
| 存草稿按钮 | "暂存离开" (button text) | JS click by textContent |
| 发布按钮 | "发布" (button text) | JS click by textContent |

## 边界处理（踩坑记录）

### 1. 标题 20 字限制
```python
TITLE_MAX = 20
if len(title) > TITLE_MAX:
    title = title[:TITLE_MAX]
    # 标记截断，输出中提示
```
XHS 标题严格限制 20 字（含标点），超出无法输入。

### 2. 正文 1000 字限制
```python
CONTENT_MAX = 1000
if len(body) > CONTENT_MAX:
    body = body[:CONTENT_MAX]
```
XHS 正文限制 1000 字（含空格和 emoji）。

### 3. ProseMirror 特殊填充
ProseMirror 是富文本编辑器，不能直接 `fill()`。必须用 `innerHTML` + 事件触发：
```python
await page.evaluate('''([el, html]) => {
    el.innerHTML = html;
    el.dispatchEvent(new Event("input", { bubbles: true }));
}''', [editor, body_html])
```
其中 `body_html` 是每行用 `<p>` 标签包裹的 HTML。

### 4. 标签处理策略
XHS 有两种标签机制：
1. **正文内 #话题**：直接在正文中写 `#标签名`，XHS 自动识别并高亮（推荐）
2. **话题面板**：点击"话题"按钮→输入→选择推荐（不稳定，容易超时）

Skill 默认使用策略 1：将标签以 `#标签1 #标签2` 格式追加到正文末尾。
这避免了话题面板的不稳定性，且 XHS 会自动将 # 开头的文字转为可点击标签。

### 5. 图片上传触发编辑器
XHS 图文编辑器是懒加载的——只有上传图片后，标题/正文输入框才会出现。
```
上传图片 → 等待 5-6 秒 → 编辑器出现
```

### 6. 上传图文 Tab 切换
页面默认显示"上传视频"tab，需要 JS 点击切换到"上传图文"：
```python
await page.evaluate('''() => {
    const tabs = document.querySelectorAll('div.creator-tab');
    for (const tab of tabs) {
        if (tab.textContent.trim() === '上传图文') {
            const r = tab.getBoundingClientRect();
            if (r.x > 0 && r.y > 0) { tab.click(); return; }
        }
    }
}''')
```

### 7. Cookie 管理
- Cookie 文件位置：`~/.playwright-data/xiaohongshu/state-default.json`
- 有效期约 3 天，需要定期通过浏览器登录续期
- 加载方式：`await context.add_cookies(cookies_from_state)`
- 检查登录：页面出现"创作服务平台"文字即为已登录

## ⚡ v1.2 安全增强（新增）

### Pre-flight Health Check（飞行前检查）

**每次发布前必须执行以下检查项**：

```bash
# 1. 浏览器健康检查
browser(action="status", profile="openclaw")
# 必须 running=true，否则 start 并等待

# 2. Cookie 有效性检查
python3 -c "
import json
from pathlib import Path
state = json.loads(Path.home().joinpath('.playwright-data/xiaohongshu/state-default.json').read_text())
cookies = state.get('cookies', [])
now = __import__('time').time()
for c in cookies:
    exp = c.get('expires', -1)
    if exp > 0 and exp < now:
        print(f'EXPIRED: {c[\"name\"]} (expired {exp})')
        exit(1)
print(f'OK: {len(cookies)} cookies, all valid')
"

# 3. 文件存在性检查
ls -lh "$ARTICLE_PATH" "$COVER_PATH"

# 4. 封面尺寸检查（推荐 ≥720x960）
python3 -c "
from PIL import Image
img = Image.open('$COVER_PATH')
w, h = img.size
print(f'Cover: {w}x{h}', '✅' if w>=720 and h>=960 else '⚠️ 建议≥720x960')
"
```

### 安全截图机制（Safety Screenshots）

**在每个关键操作后截图，作为安全备份**：

```
流程: 打开页面 → [安全截图#1] → 上传封面 → [安全截图#2] 
→ 填标题 → [安全截图#3] → 填正文 → [安全截图#4] 
→ 存草稿 → [安全截图#5]
```

**截图文件命名规范**：
```bash
/tmp/xhs_safety_01_page_loaded.png
/tmp/xhs_safety_02_cover_uploaded.png
/tmp/xhs_safety_03_title_filled.png
/tmp/xhs_safety_04_content_filled.png
/tmp/xhs_safety_05_before_draft.png
/tmp/xhs_safety_06_draft_confirm.png
```

**原则**：任何操作前都截图当前状态，即使失败也有证可查。

### 重试机制

| 失败场景 | 重试次数 | 退避策略 |
|---------|---------|---------|
| 网络超时 | 3次 | 10s → 30s → 60s |
| Selector 未找到 | 2次 | 5s → 10s |
| 文件上传失败 | 3次 | 10s → 30s → 60s |
| 页面加载失败 | 2次 | 15s → 30s |

**超过最大重试**：停止，截图当前状态，报告错误，转交 Daniel 接管。

### 恢复模式（Recovery）

如果浏览器在发布过程中意外关闭：

1. **重启浏览器**：`openclaw browser start --profile openclaw`
2. **检查草稿箱**：手动访问 `https://creator.xiaohongshu.com/publish/publish`
3. **查看安全截图**：`ls /tmp/xhs_safety_*.png`
4. **判断是否需要重试**：如果安全截图#5已存在，说明存草稿前失败了，需要重跑

### 错误处理策略

| 错误类型 | 行为 |
|---------|------|
| Cookie 过期 | 停止 → 提示 Daniel 重新扫码登录 |
| Selector 找不到 | 重试2次 → 失败则截图+停止 |
| 网络超时 | 重试3次 → 失败则截图+停止 |
| 封面上传失败 | 重试3次 → 失败则截图+停止 |
| 存草稿按钮找不到 | 截图+停止，提示 Daniel 手动存 |

---

## 常见问题

### Q: 图片上传后编辑器没出现？
A: 等待时间不够。XHS 上传后需要 5-8 秒处理，建议 `asyncio.sleep(6)`。

### Q: 标签添加失败？
A: XHS 标签有推荐匹配机制，如果输入的标签没有推荐结果，会被忽略。建议使用热门标签。

### Q: 浏览器连接失败？
A: 检查 OpenClaw browser 是否运行：`curl -s http://127.0.0.1:18800/json/version`

### Q: Cookie 过期怎么办？
A: 需要 Daniel 通过浏览器登录 XHS 创作者平台，保存 Playwright state：
```bash
# 通过 OpenClaw browser 登录
openclaw browser open --url https://creator.xiaohongshu.com
# 手动扫码登录后
# Cookie 会自动保存
```

## 示例

### 完整发布流程

```bash
# 1. 确保 browser 运行
openclaw browser status

# 2. 运行发布
python3 ~/clawd/skills/xhs-publisher/scripts/publish.py \
  --article ~/clawd/docs/daily-content/2026-04-10/xhs/article-1.md \
  --cover ~/clawd/docs/daily-content/2026-04-10/xhs/cover-1-qingyun.jpg \
  --decision draft

# 3. 检查结果
# 输出示例：
# ✅ Login verified
# ✅ Tab switched
# ✅ Cover uploaded
# ✅ Title: 21岁用AI Agent搭了一家公司 (18 chars)
# ✅ Content: 748 chars
# ✅ Tags: 5 added
# ✅ Screenshot saved: /tmp/xhs_publish_20260414103000.png
# ✅ Draft saved → 草稿箱(3)
```

## 依赖

```
playwright>=1.40.0
Pillow (用于图片尺寸验证，可选)
```

## 触发词

- "发布到小红书"、"发XHS"、"上传到XHS草稿箱"
- "小红书发布"、"XHS publish"、"小红书草稿"
- "publish xhs"、"xhs draft"
- "MediaClaw XHS"

## 更新日志

- **v1.2.0** (2026-04-16): 安全增强
  - Pre-flight health check（浏览器、Cookie、文件、封面尺寸）
  - 安全截图机制（6个关键节点截图）
  - 重试机制（3次/2次，指数退避）
  - 恢复模式文档
  - 错误处理策略细化
- **v1.1.0** (2026-04-14): 初始版本，基于 MediaClaw XHS 发布实战验证
  - 完整 selector 验证（7个关键元素）
  - ProseMirror 填充方案
  - 标题/正文限制处理
  - 标签推荐机制适配
  - 10/10 步骤 live test 通过
  - 真实文章发布验证
