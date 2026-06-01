---
name: md2wechat
description: Convert Markdown to WeChat Official Account HTML, inspect supported providers/themes/prompts, generate article images, create drafts, write with creator styles, and remove AI writing traces.
homepage: https://github.com/geekjourneyx/md2wechat-skill
metadata: {"clawdbot":{"emoji":"📝","requires":{"bins":["md2wechat"],"env":["WECHAT_APPID","WECHAT_SECRET"]},"install":[{"id":"brew","kind":"brew","formula":"geekjourneyx/tap/md2wechat","bins":["md2wechat"],"label":"Install md2wechat (brew)"},{"id":"go","kind":"go","module":"github.com/geekjourneyx/md2wechat-skill/cmd/md2wechat@latest","bins":["md2wechat"],"label":"Install md2wechat (go)"}]}}
---

# md2wechat

Use `md2wechat` when the user wants to:

- convert Markdown into WeChat Official Account HTML
- inspect resolved article metadata, readiness, and publish risks before conversion
- generate a local preview artifact or upload drafts
- inspect live capabilities, providers, themes, and prompts
- generate covers, infographics, or other article images
- create image posts
- write in creator styles or remove AI writing traces

## Intent Routing

Choose the command family before doing any publish action:

- Use `convert` / `inspect` / `preview` when the user wants a standard WeChat article draft (`news`), HTML conversion, article metadata, article preview, or a draft that needs `--cover`.
- Use `create_image_post` when the user says `小绿书`, `图文笔记`, `图片消息`, `newspic`, `多图帖子`, or asks to publish an image-first post rather than an article HTML draft.
- Do not route `小绿书` / `图文笔记` requests to `convert --draft` just because the user also has a Markdown article. A Markdown file can still be the image source for `create_image_post -m article.md`.
- Treat `convert --draft` and `create_image_post` as different publish targets, not interchangeable command variants.

## Defaults And Config

- Use this skill only when `md2wechat` is already available on `PATH`.
- Draft upload and publish-related actions require `WECHAT_APPID` and `WECHAT_SECRET`.
- Image generation may require additional image-service configuration in `~/.config/md2wechat/config.yaml`.
- `convert` defaults to `api` mode unless the user explicitly asks for `--mode ai`.
- Check configuration in this order:
  1. `~/.config/md2wechat/config.yaml`
  2. environment variables such as `MD2WECHAT_BASE_URL`
  3. project-local `md2wechat.yaml`, `md2wechat.yml`, or `md2wechat.json`
- If the user asks to switch API domain, update `api.md2wechat_base_url` or `MD2WECHAT_BASE_URL`.
- Treat live CLI discovery output as the source of truth. Do not guess provider names, theme names, or prompt names from repository files alone.

## Discovery First

Run these before selecting a provider, theme, or prompt:

- `md2wechat version --json`
- `md2wechat capabilities --json`
- `md2wechat providers list --json`
- `md2wechat themes list --json`
- `md2wechat prompts list --json`
- `md2wechat prompts list --kind image --json`
- `md2wechat prompts list --kind image --archetype cover --json`

Inspect a specific resource before using it:

- `md2wechat providers show openrouter --json`
- `md2wechat providers show volcengine --json`
- `md2wechat themes show autumn-warm --json`
- `md2wechat prompts show cover-default --kind image --json`
- `md2wechat prompts show cover-hero --kind image --archetype cover --tag hero --json`
- `md2wechat prompts show infographic-victorian-engraving-banner --kind image --archetype infographic --tag victorian --json`
- `md2wechat prompts render cover-default --kind image --var article_title='Example' --json`

When choosing image presets, prefer the prompt metadata returned by `prompts show --json`, especially `primary_use_case`, `compatible_use_cases`, `recommended_aspect_ratios`, and `default_aspect_ratio`.
When choosing an image model, prefer `providers show <name> --json` and read `supported_models` before hard-coding `--model`.

## Core Commands

Configuration:

- `md2wechat config init`
- `md2wechat config show --format json`
- `md2wechat config validate`

Conversion:

- `md2wechat inspect article.md`
- `md2wechat preview article.md`
- `md2wechat convert article.md --preview`
- `md2wechat convert article.md -o output.html`
- `md2wechat convert article.md --draft --cover cover.jpg`
- `md2wechat convert article.md --mode ai --theme autumn-warm --preview`
- `md2wechat convert article.md --title "新标题" --author "作者名" --digest "摘要"`

Image handling:

- `md2wechat upload_image photo.jpg`
- `md2wechat download_and_upload https://example.com/image.jpg`
- `md2wechat generate_image "A cute cat sitting on a windowsill"`
- `md2wechat generate_image --preset cover-hero --article article.md --size 2560x1440`
- `md2wechat generate_cover --article article.md`
- `md2wechat generate_infographic --article article.md --preset infographic-comparison`
- `md2wechat generate_infographic --article article.md --preset infographic-dark-ticket-cn --aspect 21:9`
- `md2wechat generate_infographic --article article.md --preset infographic-handdrawn-sketchnote`

Drafts and image posts:

- `md2wechat create_draft draft.json`
- `md2wechat test-draft article.html cover.jpg`
- `md2wechat create_image_post --help`
- `md2wechat create_image_post -t "Weekend Trip" --images photo1.jpg,photo2.jpg`
- `md2wechat create_image_post -t "Travel Diary" -m article.md`
- `echo "Daily check-in" | md2wechat create_image_post -t "Daily" --images pic.jpg`
- `md2wechat create_image_post -t "Test" --images a.jpg,b.jpg --dry-run`

Writing and humanizing:

- `md2wechat write --list`
- `md2wechat write --style dan-koe`
- `md2wechat write --style dan-koe --input-type fragment article.md`
- `md2wechat write --style dan-koe --cover-only`
- `md2wechat write --style dan-koe --cover`
- `md2wechat write --style dan-koe --humanize --humanize-intensity aggressive`
- `md2wechat humanize article.md`
- `md2wechat humanize article.md --intensity aggressive`
- `md2wechat humanize article.md --show-changes`
- `md2wechat humanize article.md -o output.md`

## Article Metadata Rules

For `convert`, metadata resolution is:

- Title: `--title` -> `frontmatter.title` -> first Markdown heading -> `未命名文章`
- Author: `--author` -> `frontmatter.author`
- Digest: `--digest` -> `frontmatter.digest` -> `frontmatter.summary` -> `frontmatter.description`

Limits enforced by the CLI:

- `--title`: max 32 characters
- `--author`: max 16 characters
- `--digest`: max 128 characters

Draft behavior:

- If digest is still empty when creating a draft, the draft layer generates one from article HTML content with a 120-character fallback.
- Creating a draft requires either `--cover` or `--cover-media-id`.
- `--cover` is a local image path contract for article drafts. `--cover-media-id` is for an existing WeChat permanent cover asset. Do not assume a WeChat URL or `mmbiz.qpic.cn` URL can be reused as `thumb_media_id`.
- `inspect` is the source-of-truth command for resolved metadata, readiness, and checks.
- `preview` v1 writes a standalone local HTML preview file. It does not start a workbench, write back to Markdown, upload images, or create drafts.
- `convert --preview` is still the convert-path preview flag; it is not the same thing as the standalone `preview` command.
- `preview --mode ai` is degraded confirmation only; it must not be treated as final AI-generated layout.
- `--title` / `--author` / `--digest` affect draft metadata, not necessarily visible body HTML.
- Markdown images are only uploaded/replaced during `--upload` or `--draft`, not during plain `convert --preview`.

## Publish Gate（发布门禁）· MANDATORY CHECKPOINT

**Before any `--draft`, `create_draft`, or `test-draft` push to WeChat, you MUST present the following to the user and wait for explicit confirmation:**

```
┌─────────────────────────────────────────┐
│   🔴 PUBLISH GATE — 发布前审查           │
├─────────────────────────────────────────┤
│  ☐ 标题（≤32字，确认措辞）              │
│  ☐ 作者（≤16字，确认署名）              │
│  ☐ 封面图（已生成/已选择，用户看过）     │
│  ☐ 摘要（≤128字，前60字可见需精炼）     │
│  ☐ 排版风格（主题名，已确认）            │
│  ☐ 用户回复"发"/"推"/"OK"等明确批准      │
└─────────────────────────────────────────┘
```

### Gate Rules (不可越过的铁律)

1. **标题必须展示** — 把完整标题文本发给用户看，标注字数。不要说"标题没问题"而不展示内容。
2. **作者必须确认** — 不要假设作者名。默认是 frontmatter.author 或空。空值必须让用户填。
3. **封面图必须可视化** — 用图片消息发送封面图给用户。不要只说"封面已生成"。≥2 个备选方案更佳。
4. **摘要必须展示** — 展示完整摘要文本，标注微信折叠线（前 60 字）。
5. **显式批准** — 用户必须回复明确的肯定词（发/推/OK/行/好/可以/go）才能继续。沉默 ≠ 同意。
6. **每个门禁项缺失都要报** — 如果某字段为空，主动标注 ⚠️ 缺失并询问用户填写。

### Gate Output Template（审查输出模板）

```
📋 发布审查

🏷️ 标题（27/32字）：
微信排版从2小时到2秒：我用一行命令干掉了公众号最烦人的活

✍️ 作者（9/16字）：
Daniel Li

📝 摘要（73/128字，折叠线≈60字）：
从手动排版到全自动发布，md2wechat 一行命令搞定公众号 Markdown→草稿箱的全流程。含 20 个自定义主题详解，让你的文章从此有视觉人设。

🖼️ 封面：[发送封面图]

🎨 排版风格：Coffee Notes（06·暖色系·焦糖棕）

---
以上信息确认无误？回复"发"推送到草稿箱，或告知修改内容。
```

## Agent Rules

- Start with discovery commands before committing to a provider, theme, or prompt.
- Route by publish target first: article draft => `convert`; image post / 小绿书 / newspic => `create_image_post`.
- **CRITICAL: The Publish Gate above is MANDATORY. Every draft push MUST pass through it. No exceptions.**
- Prefer the confirm-first flow for article work: `inspect` -> `preview` -> **Publish Gate** -> `--draft`.
- If the user says `小绿书`, `图文笔记`, `图片消息`, `newspic`, or asks for a multi-image post, prefer `create_image_post` even when the source content lives in Markdown.
- Prefer `generate_cover` or `generate_infographic` over a raw `generate_image "prompt"` call when a bundled preset fits the task.
- Validate config before any draft, publish, or image-post action.
- If draft creation returns `45004`, check digest/summary/description before assuming the body content is too long.
- If the user asks for AI conversion or style writing, be explicit that the CLI may return an AI request/prompt rather than final HTML or prose unless the workflow completes the external model step.
- Do not perform draft creation, publishing, or remote image generation unless the user asked for it.

## Custom AI Themes (Daniel Li · agi-super-team)

When using `md2wechat convert --mode ai --theme custom`, select the appropriate theme from below based on article content and audience. Provide the full theme specification as the AI prompt for conversion.

### Theme Selection Guide

| Category | # | Theme Name | Best For |
|----------|---|------------|----------|
| 极简系 | 01 | Swiss Minimal | 设计、建筑、现代艺术 |
| 极简系 | 02 | Nordic Clean | 生活方式、家居、旅行 |
| 极简系 | 03 | Japanese Zen | 哲学、散文、东方美学 |
| 极简系 | 04 | Editorial Print | 深度报道、行业分析 |
| 暖色系 | 05 | Golden Hour | 生活方式、美食、情感 |
| 暖色系 | 06 | Coffee Notes | 创业日记、散文、感悟 |
| 暖色系 | 09 | Rose Quartz | 女性向、美妆、情感 |
| 暖色系 | 20 | Desert Dawn | 旅行、探险、自由生活 |
| 暗色系 | 07 | Elegant Noir | 品牌故事、高端生活方式 |
| 暗色系 | 08 | Deep Ocean | AI、科技、数据分析 |
| 暗色系 | 10 | Cyber Neon | 极客、Web3、未来文化 |
| 暗色系 | 18 | Midnight Blue | 深夜阅读、诗歌、哲学 |
| 文艺系 | 11 | Monet Garden | 文艺、艺术、自然 |
| 文艺系 | 12 | Academic Classic | 学术、知识、历史 |
| 文艺系 | 14 | Ink Wash | 东方文化、书画、禅 |
| 文艺系 | 17 | Forest Mist | 自然、冥想、可持续 |
| 现代系 | 13 | Aurora Gradient | 创意、设计、未来趋势 |
| 现代系 | 15 | Glass Morphism | 产品设计、UX、生活方式 |
| 现代系 | 16 | Brutalist Raw | 街头文化、独立观点 |
| 现代系 | 19 | Summer Mint | 流行文化、社交媒体 |

---

### 极简系

#### 01 · Swiss Minimal
- **风格**: 瑞士国际主义 · 红黑白 · Helvetica
- **色彩**: 主色 #000000 纯黑, 强调色 #CC0000 瑞士红, 背景 #FFFFFF 纯白, 辅助灰 #F5F5F5
- **字体**: 标题 Helvetica Bold / 正文 Helvetica Neue Light / 引用 Helvetica Neue Italic
- **布局**: 严格的网格系统, 标题左对齐大字重, 正文窄栏宽 620px, 大量留白, 段落间距 2em, 分割线极细 1px
- **特色**: 非对称排版, 数字使用大字号, 图片全幅出血, 无圆角无阴影, 红黑白三色绝不引入第四色
- **CSS 核心**: `font-family: 'Helvetica Neue', sans-serif; max-width: 620px; line-height: 1.8; h2 { font-size: 28px; font-weight: 700; border-left: 4px solid #CC0000; padding-left: 16px; }`
- **适用**: 设计理论、建筑评析、现代艺术、品牌策略

#### 02 · Nordic Clean
- **风格**: 北欧 hygge · 橡木白 · 蓝天灰
- **色彩**: 主色 #2C3E50 深蓝灰, 背景 #FAF7F2 橡木白暖奶油, 强调色 #87CEEB 天空蓝, 辅助 #E8E0D5 浅橡木
- **字体**: 标题 Playfair Display / 正文 Lora 或 Georgia / 注释 Helvetica Neue Light
- **布局**: 宽松排版, 行高 2.0, 段落间距大, 圆角卡片式引用块, 浅色背景穿插, 图片柔和圆角 8px
- **特色**: 温暖柔和不刺眼, 橡木色调底色, 卡片式内容区, 细金线分割, 没有纯黑文字
- **CSS 核心**: `body { background: #FAF7F2; color: #2C3E50; } h2 { color: #2C3E50; border-bottom: 2px solid #E8E0D5; padding-bottom: 8px; } blockquote { background: #FFF; border-radius: 8px; border-left: 3px solid #87CEEB; padding: 16px 20px; }`
- **适用**: 家居生活、旅行游记、个人随笔、慢生活

#### 03 · Japanese Zen
- **风格**: 侘寂 · 墨色 · 宣纸 · 留白
- **色彩**: 主色 #2B2B2B 墨色, 背景 #F5F0E8 宣纸色, 强调色 #8B4513 茶褐, 辅助 #D4C5B9
- **字体**: 标题 Noto Serif SC Bold / 正文 Noto Serif SC Regular / 注释楷体
- **布局**: 竖排感横排化, 超大留白, 段落短小, 标题居中, 图文分离, 文字区块窄 560px, 左右不对称留白
- **特色**: 大量空白, 墨色渐变, 宣纸纹理底色, 印章红点缀, 引用用竖线, 不设卡片不设圆角
- **CSS 核心**: `body { background: #F5F0E8; color: #2B2B2B; } h2 { text-align: center; font-size: 24px; letter-spacing: 4px; margin: 48px 0 32px; } p { max-width: 560px; margin: 0 auto 24px; } .accent { color: #C04040; }`
- **适用**: 东方哲学、禅修、书画评论、散文

#### 04 · Editorial Print
- **风格**: 编辑体 · Georgia 衬线 · 纯黑
- **色彩**: 主色 #1A1A1A, 背景 #FCFCFC, 强调色 #1A1A1A (粗体即强调), 分割线 #DDD
- **字体**: 标题 Georgia Bold / 正文 Georgia Regular / 引用 Georgia Italic / 首字下沉 3行
- **布局**: 报刊杂志感, 首字下沉, 两级标题层级分明, 引用居中斜体大号, 段落首行无缩进, 窄栏宽 600px
- **特色**: 传统编辑美学, drop cap, 衬线正文, 图片带标题说明, 无彩色强调, 纯排版说话
- **CSS 核心**: `font-family: Georgia, serif; max-width: 600px; p:first-of-type::first-letter { font-size: 3.5em; float: left; line-height: 0.8; padding-right: 8px; } blockquote { text-align: center; font-style: italic; font-size: 1.2em; }`
- **适用**: 深度报道、行业分析、长文论述、新闻特稿

---

### 暖色系

#### 05 · Golden Hour
- **风格**: 日落暖光 · 大地色 · 逆光感
- **色彩**: 主色 #5D4037 深棕, 背景 #FFF8F0 暖奶油, 强调色 #E67E22 落日橙, 渐变 #FFE0B2 → #FFCC80, 辅助 #FFECB3
- **字体**: 标题 Merriweather Bold / 正文 Noto Sans SC Light / 引用 Dancing Script 或楷体
- **布局**: 暖色渐变区块, 图片宽幅, 卡片式小标题, 温暖色调背景块交替, 分割线用渐变色
- **特色**: 落日色调, 温暖治愈, 逆光感渐变背景, 图片加暖色滤镜叠层
- **CSS 核心**: `body { background: #FFF8F0; color: #5D4037; } h2 { color: #E67E22; } .highlight-box { background: linear-gradient(135deg, #FFE0B2, #FFCC80); padding: 20px; border-radius: 12px; }`
- **适用**: 生活方式、美食摄影、旅行日记、情感散文

#### 06 · Coffee Notes
- **风格**: 咖啡馆 · 焦糖棕 · 粗粝手作感
- **色彩**: 主色 #3E2723 深咖, 背景 #FBF7F0 奶泡白, 强调色 #A0522D 焦糖, 辅助 #D7CCC8 拿铁灰, 卡色 #C8B89D
- **字体**: 标题 Amatic SC 或 ZCOOL XiaoWei / 正文 Noto Sans SC Regular / 手写注释
- **布局**: 粗粝质感, 手作标签, 纸张纹理底色, 标题手写体/毛笔, 段落短小亲切, 图标式分割
- **特色**: 咖啡馆黑板报感, 手写体标题, 粗糙边缘卡片, 焦糖色点缀, 温暖但不华丽
- **CSS 核心**: `body { background: #FBF7F0; color: #3E2723; } h2 { font-family: 'ZCOOL XiaoWei', serif; color: #3E2723; border-bottom: 2px dashed #D7CCC8; } .note { background: #EFEBE4; border-left: 4px solid #A0522D; padding: 12px 16px; }`
- **适用**: 创业日记、个人思考、读书笔记、咖啡馆随笔

#### 09 · Rose Quartz
- **风格**: 干枯玫瑰 · 柔粉 · 治愈
- **色彩**: 主色 #4A3548 深玫瑰灰, 背景 #FDF5F5 柔粉底, 强调色 #C4727F 干枯玫瑰, 渐变 #F5E0E5 → #EDD5DC, 辅助 #F0E0E5
- **字体**: 标题 Playfair Display / 正文 Noto Serif SC / 引用楷体 italic
- **布局**: 柔粉渐变卡片, 圆角 12px, 大量留白, 粉色系分隔, 图片加柔焦效果, 轻盈透气
- **特色**: 干燥玫瑰色调, 柔和不刺眼, 女性化但不甜腻, 治愈感强, 花瓣点缀
- **CSS 核心**: `body { background: #FDF5F5; color: #4A3548; } h2 { color: #C4727F; } .card { background: linear-gradient(135deg, #F5E0E5, #EDD5DC); border-radius: 12px; padding: 20px; } blockquote { border-left: 3px solid #C4727F; color: #8B6B7A; }`
- **适用**: 美妆护肤、女性成长、情感故事、生活方式

#### 20 · Desert Dawn
- **风格**: 沙漠黎明 · 赤陶 · 仙人掌
- **色彩**: 主色 #5D4037 深棕, 背景 #FAF0E6 沙色, 强调色 #C67B5C 赤陶, 辅助 #E8C9A0 沙丘金, 绿植 #7B8D6F 仙人掌绿
- **字体**: 标题 Montserrat Bold / 正文 Lora / 注释 monospace
- **布局**: 宽幅图片, 大地色调, 粗纹理, 粗线条分割, 不规则卡片, 标签式小标题
- **特色**: 沙漠色调, 赤陶质感, 仙人掌绿点缀, 粗犷自然, 自由奔放, 大图大字
- **CSS 核心**: `body { background: #FAF0E6; color: #5D4037; } h2 { color: #C67B5C; border-left: 5px solid #C67B5C; padding-left: 16px; } .accent-green { color: #7B8D6F; } hr { border: 2px solid #E8C9A0; }`
- **适用**: 旅行探险、自由职业、户外运动、游牧生活

---

### 暗色系

#### 07 · Elegant Noir
- **风格**: 黑金奢华 · VOGUE · 香槟金
- **色彩**: 主色 #0A0A0A 黑, 强调色 #D4AF37 香槟金, 文字 #EAEAEA 浅灰白, 辅助 #2A2A2A 深灰, #C9A84C 暗金
- **字体**: 标题 Playfair Display Bold / 正文 Cormorant Garamond / 引用 Playfair Display Italic
- **布局**: 暗色背景, 金字标题, 衬线字体, 极细金线分割, 图片高对比度, 文字居中或右对齐
- **特色**: 奢侈品牌感, 黑底金字, 衬线体优雅, 金色细线, 图片饱和度降低+金色滤镜
- **CSS 核心**: `body { background: #0A0A0A; color: #EAEAEA; } h2 { color: #D4AF37; font-family: 'Playfair Display', serif; text-align: center; letter-spacing: 2px; } hr { border-color: #D4AF37; height: 1px; } blockquote { border-left: 2px solid #D4AF37; color: #C9A84C; }`
- **适用**: 品牌故事、奢侈品、高端生活方式、时尚评论

#### 08 · Deep Ocean
- **风格**: 深海 · 青色荧光 · 科技感
- **色彩**: 主色 #0A1628 深海黑蓝, 强调色 #00D4FF 青色荧光, 文字 #C8D6E5 浅蓝灰, 辅助 #1A2A4A, 渐变 #0A1628 → #0D2137
- **字体**: 标题 Space Mono Bold / 正文 Inter Regular / 代码 Fira Code
- **布局**: 暗色底, 荧光标题, 等宽字体代码区, 数据卡片, 科技图标, 边框发光效果
- **特色**: 深海暗色, 青色荧光高亮, 科技感线条, 代码块终极端风格, 数据可视化卡片
- **CSS 核心**: `body { background: #0A1628; color: #C8D6E5; } h2 { color: #00D4FF; font-family: 'Space Mono', monospace; } code { background: #1A2A4A; color: #00D4FF; padding: 2px 6px; border-radius: 3px; } pre { background: #0D2137; border: 1px solid #00D4FF33; } .data-card { border: 1px solid #00D4FF44; border-radius: 8px; }`
- **适用**: AI技术、数据分析、编程教程、科技评论

#### 10 · Cyber Neon
- **风格**: 赛博朋克 · 霓虹绿 · 故障美学
- **色彩**: 主色 #0D0D0D 纯黑, 强调色 #00FF41 霓虹绿, 次强调 #FF00FF 洋红, 文字 #E0E0E0, 辅助 #1A1A1A
- **字体**: 标题 Orbtron / 正文 Share Tech Mono / 代码 VT323
- **布局**: 黑色底, 霓虹边框, 故障效果标题, 终端风格代码块, 霓虹绿下划线, 扫描线纹理
- **特色**: 赛博朋克, 霓虹发光, glitch 效果, 扫描线, 终端美学, 等宽字体贯穿
- **CSS 核心**: `body { background: #0D0D0D; color: #E0E0E0; } h2 { color: #00FF41; text-shadow: 0 0 10px #00FF4188, 0 0 20px #00FF4144; font-family: 'Share Tech Mono', monospace; } a { color: #FF00FF; } blockquote { border-left: 3px solid #00FF41; box-shadow: 0 0 10px #00FF4122; }`
- **适用**: Web3、区块链、极客文化、科幻评论、游戏

#### 18 · Midnight Blue
- **风格**: 午夜蓝 · 银月 · 星空
- **色彩**: 主色 #0C1929 午夜蓝黑, 文字 #B8C9E0 月光灰, 强调色 #7B9EC4 银蓝, 辅助 #1A2D47, 星光 #E8D5B7 暖金
- **字体**: 标题 Spectral Bold / 正文 EB Garamond / 引用 Cormorant Italic
- **布局**: 沉浸暗色, 衬线正文, 居中诗歌体, 星空点缀, 极简分割, 大留白呼吸
- **特色**: 深夜阅读感, 蓝黑底衬线体, 月白色文字, 诗意留白, 暖金星光点缀
- **CSS 核心**: `body { background: #0C1929; color: #B8C9E0; } h2 { color: #E8D5B7; font-family: 'Spectral', serif; text-align: center; } p { font-family: 'EB Garamond', serif; } .poem { text-align: center; font-style: italic; color: #7B9EC4; }`
- **适用**: 深夜文章、诗歌、哲学沉思、星空摄影

---

### 文艺系

#### 11 · Monet Garden
- **风格**: 印象派 · 莫奈 · 油画感
- **色彩**: 主色 #4A6B5D 睡莲绿, 背景 #F5F2EB 亚麻画布, 强调色 #9B7CB6 薰衣草紫, 辅助 #E8C4A0 暖黄, #C4D7E0 天空蓝, #E8B4B8 玫瑰粉
- **字体**: 标题 Dancing Script / 正文 EB Garamond / 注释楷体
- **布局**: 柔和渐变, 油画质感边框, 色彩交融, 图文叠加, 不规则形状, 朦胧滤镜
- **特色**: 印象派配色, 柔和笔触感, 色彩叠加通透, 花园气息, 莫奈睡莲色盘
- **CSS 核心**: `body { background: #F5F2EB; color: #4A6B5D; } h2 { font-family: 'Dancing Script', cursive; color: #9B7CB6; font-size: 32px; } .impression-box { background: linear-gradient(135deg, #E8C4A044, #C4D7E044, #E8B4B844); border-radius: 16px; }`
- **适用**: 艺术评论、花园生活、印象派介绍、文艺创作

#### 12 · Academic Classic
- **风格**: 牛津学院风 · 深绿 · 烫金
- **色彩**: 主色 #1B3A2D 牛津深绿, 背景 #F9F6F0 羊皮纸, 强调色 #B8943E 烫金, 辅助 #8B6F47 皮革棕
- **字体**: 标题 Playfair Display SC Bold / 正文 Libre Baskerville / 引用 EB Garamond Italic
- **布局**: 古典对称, 烫金标题, 羊皮纸底色, 首字下沉, 章节号罗马数字, 细金线分割
- **特色**: 牛津剑桥学院感, 深绿+烫金经典搭配, 衬线体, 羊皮纸暖色, 章首装饰线
- **CSS 核心**: `body { background: #F9F6F0; color: #1B3A2D; } h2 { color: #B8943E; font-family: 'Playfair Display SC', serif; text-align: center; border-top: 1px solid #B8943E; border-bottom: 1px solid #B8943E; padding: 12px 0; } p::first-letter { color: #B8943E; }`
- **适用**: 学术文章、历史考据、经典书评、知识科普

#### 14 · Ink Wash
- **风格**: 中国水墨 · 留白 · 印章红
- **色彩**: 主色 #1A1A1A 浓墨, 背景 #F7F3EC 宣纸, 强调色 #C04040 印章红, 灰阶 #888 #BBB #DDD（水墨五色）
- **字体**: 标题 ZCOOL XiaoWei / 正文 Noto Serif SC / 引用楷体 / 竖排文字
- **布局**: 大量留白, 标题印章红, 水墨渐染背景, 竖排引用, 题跋式注释, 山形分割线
- **特色**: 中国水墨画意, 墨分五色, 印章红点缀, 宣纸底色, 大面积留白, 题跋落款
- **CSS 核心**: `body { background: #F7F3EC; color: #1A1A1A; } h2 { font-family: 'ZCOOL XiaoWei', serif; color: #C04040; font-size: 28px; text-align: center; } blockquote { font-family: 'KaiTi', serif; writing-mode: vertical-rl; float: right; color: #666; } .seal { color: #C04040; }`
- **适用**: 中国书画、东方美学、古典文学、禅茶文化

#### 17 · Forest Mist
- **风格**: 晨雾森林 · 苔藓绿 · 疗愈
- **色彩**: 主色 #2D4A3E 深苔绿, 背景 #F2F7F2 晨雾白, 强调色 #7B9D6E 苔藓绿, 辅助 #C5D8C0 浅雾绿, #4A7C59 松绿
- **字体**: 标题 Nunito Light / 正文 Lora / 引用 EB Garamond Italic
- **布局**: 柔和绿调, 圆角, 大量呼吸空间, 自然纹理分隔, 卡片式, 插画风格
- **特色**: 疗愈森林感, 晨雾配色, 苔藓绿层次, 温和不刺激, 冥想气息
- **CSS 核心**: `body { background: #F2F7F2; color: #2D4A3E; } h2 { color: #4A7C59; font-weight: 300; } .card { background: #FFF; border-radius: 16px; box-shadow: 0 2px 16px rgba(45,74,62,0.06); } blockquote { border-left: 3px solid #7B9D6E; background: #F2F7F2; }`
- **适用**: 自然疗愈、冥想正念、可持续生活、森林浴

---

### 现代系

#### 13 · Aurora Gradient
- **风格**: 极光幻境 · 紫绿渐变 · 通透
- **色彩**: 主色 #1A1A2E 深紫黑, 渐变 #6C63FF → #00D2FF → #00F5A0 → #E040FB, 文字 #E8E8F0
- **字体**: 标题 Space Grotesk Bold / 正文 Inter Regular / 代码 JetBrains Mono
- **布局**: 极光渐变区块, 深色底通透感, 玻璃态卡片, 渐变边框, 发光标题, 动态视觉
- **特色**: 极光色渐变, 通透玻璃感, 紫绿蓝粉四色交融, 未来感, 创意无限
- **CSS 核心**: `body { background: #1A1A2E; color: #E8E8F0; } h2 { background: linear-gradient(135deg, #6C63FF, #00F5A0); -webkit-background-clip: text; -webkit-text-fill-color: transparent; } .glass-card { background: rgba(255,255,255,0.05); backdrop-filter: blur(10px); border: 1px solid rgba(108,99,255,0.3); border-radius: 12px; }`
- **适用**: 创意设计、未来趋势、数字艺术、品牌创新

#### 15 · Glass Morphism
- **风格**: 毛玻璃 · 半透明 · iOS 风格
- **色彩**: 主色 #2C2C2E iOS 灰, 背景 #F2F2F7 iOS 浅灰, 强调色 #007AFF Apple 蓝, 玻璃 #FFFFFF88, 辅助 #E5E5EA
- **字体**: 标题 SF Pro Display Bold / 正文 SF Pro Text Regular / 注释 SF Pro Text Light
- **布局**: 毛玻璃卡片, 半透明叠加, 圆角 16px, 柔和阴影, 极简线框, iOS 原生感
- **特色**: Apple 设计语言, 毛玻璃模糊效果, 半透明层次, 精致圆角, 干净线框
- **CSS 核心**: `body { background: #F2F2F7; color: #2C2C2E; } .glass { background: rgba(255,255,255,0.72); backdrop-filter: blur(20px); -webkit-backdrop-filter: blur(20px); border-radius: 16px; border: 1px solid rgba(0,0,0,0.08); } h2 { color: #007AFF; }`
- **适用**: 产品设计、UX评测、iOS开发、科技生活方式

#### 16 · Brutalist Raw
- **风格**: 粗野主义 · 粗边框 · 反精致
- **色彩**: 主色 #000 黑, 背景 #FFF 白, 强调色 #FF4500 警报橙, 辅助 #EEE 素灰, 无渐变
- **字体**: 标题 Impact 或 Anton / 正文 Courier New 等宽 / 注释 Arial Bold
- **布局**: 粗黑边框 4px+, 直角无圆角, 大块面分割, 黑白为主+单色暴力强调, raw HTML 感
- **特色**: 拒绝精致, 粗边框粗字体, 极简极粗, 反设计, 朋克态度, 原始 Web 1.0 美学
- **CSS 核心**: `body { background: #FFF; color: #000; } h2 { font-family: 'Anton', sans-serif; font-size: 36px; border: 4px solid #000; display: inline-block; padding: 8px 16px; } .brutal-box { border: 3px solid #000; padding: 20px; box-shadow: 6px 6px 0 #000; } a { color: #FF4500; text-decoration: underline; }`
- **适用**: 街头文化、独立观点、反主流、设计批判

#### 19 · Summer Mint
- **风格**: 夏日薄荷 · 果冻感 · Gen Z
- **色彩**: 主色 #2D3436 深灰, 背景 #F0FFF4 薄荷白, 强调色 #00B894 薄荷绿, 辅助 #55EFC4 果冻绿, #FFEAA7 柠檬黄, #FAB1A0 桃红
- **字体**: 标题 Quicksand Bold / 正文 Nunito Regular / 注释 Comic Neue
- **布局**: 圆角 16px+, 果冻感卡片, 多彩标签, 表情符号点缀, 短段落, 跳跃节奏, 气泡对话
- **特色**: Gen Z 审美, 果冻质感, 薄荷绿+糖果色, 活泼跳跃, 表情符号友好, 轻松不严肃
- **CSS 核心**: `body { background: #F0FFF4; color: #2D3436; } h2 { color: #00B894; font-family: 'Quicksand', sans-serif; } .bubble { background: #FFF; border-radius: 18px; box-shadow: 0 4px 12px rgba(0,184,148,0.12); padding: 16px; } .tag { background: #55EFC4; border-radius: 20px; color: #2D3436; padding: 4px 12px; }`
- **适用**: 流行文化、社交媒体、校园生活、Z世代话题

---

### Usage with md2wechat

To use these themes with md2wechat AI mode, specify the theme name and provide its specification as the AI prompt:

```bash
# AI mode with custom theme prompt
md2wechat convert article.md --mode ai --theme custom --preview

# Combine with humanization
md2wechat convert article.md --mode ai --theme custom --preview
md2wechat humanize article.md --intensity medium

# Full pipeline with cover generation
md2wechat convert article.md --mode ai --theme custom -o output.html
md2wechat generate_cover --article article.md --preset cover-hero
md2wechat convert output.html --draft --cover cover.jpg
```

When using AI mode conversion, embed the selected theme's color palette, font stack, layout rules, and CSS core into the AI prompt to guide the HTML generation.

## Safety And Transparency

- Reads local Markdown files and local images.
- May download remote images when asked.
- May call external image-generation services when configured.
- May upload HTML, images, drafts, and image posts to WeChat when the user explicitly requests those actions.
