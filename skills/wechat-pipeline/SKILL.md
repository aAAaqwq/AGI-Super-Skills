---
name: wechat-pipeline
description: >
  公众号文章全自动流水线：写作→封面→发布。三段式编排 wechat-article-writer / code-to-image / md2wechat，
  每段设断点检查，用户确认后才进入下一段。触发: '公众号创作' '写公众号文章' '公众号发布' '公众号流水线' '发公众号'。
  Author: Daniel Li
homepage: https://github.com/aAAaqwq/AGI-Super-Team
metadata:
  openclaw:
    emoji: "📝→🎨→📤"
  requires:
    bins: ["python3", "node", "md2wechat"]
    packages: ["playwright"]
    env: ["WECHAT_APPID", "WECHAT_SECRET"]
    skills:
      - wechat-article-writer
      - code-to-image
      - md2wechat
---

# 公众号流水线 · WeChat Pipeline

**三段式自动流水线：写作 → 封面 → 发布，每段设断点检查，用户拍板才继续。**

## 核心理念

```
用户说"写一篇公众号文章"
        │
        ▼
┌──────────────────────────────────────┐
│  STAGE 1 — 内容创作                   │
│  wechat-article-writer               │
│  搜索→撰写→标题→排版                  │
│                                      │
│  🔴 CHECKPOINT 1: 内容审查           │
│  → 展示文章 + 5个标题，等用户确认     │
└──────────────┬───────────────────────┘
               │ 用户回复"继续"
               ▼
┌──────────────────────────────────────┐
│  STAGE 2 — 封面生成                   │
│  code-to-image                       │
│  设计HTML→渲染PNG                     │
│                                      │
│  🔴 CHECKPOINT 2: 封面审查           │
│  → 展示封面图，等用户确认或要求重做    │
└──────────────┬───────────────────────┘
               │ 用户回复"继续"
               ▼
┌──────────────────────────────────────┐
│  STAGE 3 — 发布推送                   │
│  md2wechat                           │
│  门禁审查→create_draft→草稿入库       │
│                                      │
│  🔴 CHECKPOINT 3: 发布门禁           │
│  → 标题/作者/封面/摘要全展示          │
│  → 等用户回复"发"                    │
└──────────────────────────────────────┘
```

## 触发词

以下任一关键词触发此流水线：
- `公众号创作`、`写公众号文章`、`公众号发布`
- `公众号流水线`、`发公众号`、`公众号全流程`
- `写一篇公众号`、`帮我发公众号`

## 核心铁律（不可违反）

1. **三段必须串行** — 不能跳过任何一段，不能两段并行
2. **每段必须断点** — 每段结束后必须停下来等用户确认，不得自动进入下一段
3. **不得跳过门禁** — Stage 3 的发布门禁必须完整展示标题/作者/封面/摘要
4. **封面必须代码生成** — 禁止用 `image_generate`（AI 生图）替代 `code-to-image`（代码渲染），因为中文文字准确率、主题直连度、风格可复现性差距悬殊
5. **发布必须 create_draft** — 禁止用 `test-draft`（测试命令不传标题/作者，会导致「AI生成测试文章」）
6. **错误必记录** — 每段失败时截图保存、记录根因，不静默重试

---

## Stage 1: 内容创作

### 子 skill: `wechat-article-writer`

**4 步流程**：搜索资料 → 撰写文章 → 生成标题 → 排版建议

#### Step 1.1: 搜索资料

使用 WebSearch 并行搜索：
- 官方文档 / GitHub / 技术论坛
- 优先当月/当季资料
- 深度总结，标注来源

#### Step 1.2: 撰写文章

- 读取 CLAUDE.md 获取写作风格（如存在）
- 字数：按用户要求，默认 2000-3000 字
- 结构：故事化开头 → 问题描述 → 步骤教学 → 升华总结
- 准备 2-3 个备选标题
- 输出 Markdown 文件到 `output/` 目录

#### Step 1.3: 生成标题

生成 5 个爆款标题：
- 痛点明确（"还在手动..."）
- 数字吸引（"3分钟""5个技巧"）
- 结果导向（"效率暴涨10倍"）
- 情绪调动（"惊艳""神技"）
- 标题 ≤ 32 字符（微信限制）

#### Step 1.4: 排版建议

- 段落结构：每段 3-5 行
- 代码块：前后留白，标注语言
- 金句：单独成段加粗
- 配图标记：标注 `[图: 描述]` 供后续生成

---

### 🔴 CHECKPOINT 1: 内容审查

**必须展示给用户并等待确认：**

```
📝 内容审查

📖 文章标题候选（选一个）：
   1. xxx
   2. xxx
   3. xxx
   4. xxx
   5. xxx

📊 文章概况：
   - 字数：约 X,XXX 字
   - 结构：[段落数] 段，[代码块数] 个代码块

📄 内容预览：
   [展示文章前 3 段或关键段落]

---
请选择标题编号，或告诉我修改意见。
回复"继续"进入封面生成阶段。
```

**用户未确认前，绝对不进入 Stage 2。**

---

## Stage 2: 封面生成

### 子 skill: `code-to-image`

#### Step 2.1: 选择模板

从 15 套模板库中推荐 2-3 个跟文章主题匹配的风格：
- 科技教程 → Blueprint / MIT Tech Review / Swiss
- 创业感悟 → Kinfolk / Coffee Notes / Notebook
- 深度分析 → Editorial / Monocle / Paper & Ink

#### Step 2.2: 设计封面 HTML

- 封面尺寸：**公众号 900×383（16:9）**，渲染 `-w 900 -H 383 --scale 2`
- 必须跟文章主题直连（不是通用图！）
- 包含：核心概念视觉化 + 关键数据指标 + 风格色调
- 示例：md2wechat 教程 → 终端命令 + 排版转换箭头 + "1行命令/20套主题/2min全流程"

#### Step 2.3: 渲染

```bash
python3 ~/.openclaw/skills/code-to-image/render.py cover.html -w 900 -H 383 --scale 2 -o cover.png
```

---

### 🔴 CHECKPOINT 2: 封面审查

**必须发送封面图给用户，等待确认：**

```
🖼️ 封面审查

[发送封面图片]

🎨 封面信息：
   - 风格：[模板名]
   - 尺寸：1800×766 (2x)
   - 色调：[主色/强调色]

---
封面满意吗？
- 回复"继续"接受此封面
- 回复"重做 + 要求"重新生成（如"重做 更暗的色调"）
```

**用户未确认前，绝对不进入 Stage 3。**

---

## Stage 3: 发布推送

### 子 skill: `md2wechat`

#### Step 3.1: 前置校验

```bash
md2wechat config validate      # 检查 WECHAT_APPID/SECRET
md2wechat inspect article.md   # 检查标题/摘要/图片
```

#### Step 3.2: 渲染 HTML

根据用户选择的排版主题（如 Coffee Notes / Deep Ocean / Swiss Minimal），将 Markdown 转换为带内联 CSS 的 WeChat 兼容 HTML。

**如果 md2wechat.cn API key 不可用**：
- 使用 Python 脚本渲染 HTML（内联 CSS + 主题色板）
- 参考：coffee_notes_renderer.py（Coffee Notes 示例）

#### Step 3.3: 上传封面

```bash
md2wechat upload_image cover.png
# 获取 thumb_media_id
```

#### Step 3.4: 生成摘要

- 从文章前 120 字提取
- 微信折叠线在 ~60 字处，核心信息必须在 60 字内露出
- 可通过 `--digest` 覆盖

---

### 🔴 CHECKPOINT 3: 发布门禁（Publish Gate）

**这是最后一道关卡。必须展示所有字段，等用户说"发"。**

```
📋 发布审查

🏷️ 标题（XX/32字）：
[完整标题文本]

✍️ 作者（XX/16字）：
[作者名]

📝 摘要（XX/128字，折叠线≈60字）：
[完整摘要文本]

🖼️ 封面：
[发送封面图]

🎨 排版风格：[主题名]

---
以上信息确认无误？回复"发"推送到草稿箱，或告知修改内容。
```

#### Step 3.5: 推草稿

用户回复"发"/"推"/"OK"后：

```bash
md2wechat create_draft draft.json
```

**draft.json 必须包含完整字段：**
```json
{
  "articles": [{
    "title": "完整标题",
    "author": "完整作者",
    "digest": "完整摘要",
    "thumb_media_id": "封面media_id",
    "content": "HTML正文",
    "show_cover_pic": 1,
    "need_open_comment": 0,
    "only_fans_can_comment": 0
  }]
}
```

⚠️ **禁止使用 `test-draft`** — 它不传 title/author/digest，会导致标题显示「AI生成测试文章」。

#### Step 3.6: 完成确认

```
✅ 发布完成

📋 草稿信息：
   media_id: dpn_xxx
   位置：微信公众号后台 → 内容管理 → 草稿箱

🧹 如有旧版草稿，请手动删除。
   去后台扫码预览，满意后一键群发。
```

---

## 常见错误与对策

| 错误 | 根因 | 对策 |
|------|------|------|
| 标题显示「AI生成测试文章」 | 用了 `test-draft` 而非 `create_draft` | 改用 `create_draft` + 完整 JSON |
| 封面跟文章无关 | 用了 `image_generate` 通用生图 | 改用 `code-to-image` 代码渲染 |
| md2wechat.cn API key 失效 | `wme_*` key 过期 | 用 Python 内联 CSS 渲染 + `create_draft` 推送 |
| 火山引擎生图 key 过期 | ARK API key 过期 | 改用 `code-to-image`（永远免费） |
| create_draft 报「no articles」 | JSON 缺少 `articles` 数组包裹 | 用 `{"articles":[{...}]}` 格式 |

---

## 版本历史

| 版本 | 日期 | 变更 |
|------|------|------|
| v1.0 | 2026-06-01 | 初始版本。基于真实发布过程沉淀：写作(wechat-article-writer) → 封面(code-to-image) → 发布(md2wechat+Publish Gate)。记录 5 个踩坑经验。 |

---

*Copyright © Daniel Li. All rights reserved.*
