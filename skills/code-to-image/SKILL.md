---
name: code-to-image
description: >
  最强免费生图方案：用前端代码(HTML/CSS/JS/Canvas/SVG)设计画面，通过 Playwright 渲染为任意分辨率高清 PNG。
  零API成本、无限分辨率、中文100%准确、代码可复用、Git可追踪。
  配合 frontend-design / canvas-design / frontend-design-ultimate 产出 HTML 设计稿后调用。
  触发: '生图' '生成图片' '代码生图' '渲染封面' 'render html' 'html to image' 'code to image' '前端生图'。
  Author: Daniel Li
license: MIT
metadata:
  openclaw:
    emoji: "🎨→🖼️"
    requires:
      bins: ["python3", "node"]
      packages: ["playwright"]
---

# Code-to-Image · 代码生图

**将前端设计代码渲染为高清图片——免费、无限分辨率、完全可控。**

## 核心理念

```
HTML/CSS/JS/Canvas 设计稿 ──→ Playwright 无头渲染 ──→ 高清 PNG
       ↑                          ↑                    ↑
   设计层                      渲染层                输出层
 frontend-design             render.py             任意分辨率
 canvas-design               @1x/@2x/@4x           PNG/JPEG/WebP
 frontend-design-ultimate    全平台兼容             100%中文准确
```

## 为什么这个方案最强

| | Code-to-Image 🆓 | AI API 生图 💰 |
|---|:---:|:---:|
| **费用** | $0 永久免费 | $0.02-0.10/张 |
| **分辨率** | 任意 (4K/8K/16K) | 通常 ≤2K |
| **中文文字** | 100% 准确 | 经常乱码/糊掉 |
| **品牌一致性** | 代码保证 | 每次随机 |
| **批量生成** | 无限，改参数即可 | API 限流 |
| **可复现性** | Git 版本管理 | 不可复现 |
| **灵活性** | HTML/CSS/JS/Canvas/SVG | 纯提示词 |
| **本地运行** | ✅ 无需网络 | ❌ 需API |

## 前置依赖

```bash
pip install playwright && playwright install chromium
```

## 默认风格：Editorial 杂志风

**Daniel 选定，所有封面默认此风格。**

特征：衬线体(Noto Serif SC) · 米白底(#faf8f5) · 红色强调(#dc2626) · 左侧8px彩条
适用：公众号封面 · 知乎头图 · 知识星球 · 内容型产品

```bash
# 基于模板快速生成
cp ~/.openclaw/skills/code-to-image/templates/editorial.html cover.html
# 编辑 cover.html 中的标题、副标题、数据
# 渲染
python3 ~/.openclaw/skills/code-to-image/render.py cover.html -o output.png -w 1080 --height 1440 --scale 2
```

## 顶尖风格模板库（15款）

| # | 风格 | 审美来源 | 主色调 | 感觉 | 适合 |
|---|------|---------|--------|------|------|
| 1 | **Editorial** ✅默认 | 财新/三联 | 米白+红黑 | 权威深度 | 公众号/知乎 |
| 2 | Monocle | FT Weekend | 三文鱼粉+棕 | 精致知识分子 | 经济/商业 |
| 3 | Art Deco | 1920s Gatsby | 金+藏蓝 | 奢华权威 | 重大事件 |
| 4 | Zen 侘寂 | 日本美学 | 纸白+柿子红 | 禅意克制 | 深度思考 |
| 5 | Blueprint | 工程图纸 | 深蓝+Cyan | 技术精密 | 硬核科技 |
| 6 | Swiss | 瑞士国际主义 | 白+青蓝几何 | 干净高端 | 品牌/官网 |
| 7 | Kinfolk | 慢生活杂志 | 暖棕+奶油 | 自然呼吸 | 人文/生活 |
| 8 | Cinematic | A24电影 | 黑+胶片颗粒 | 电影级氛围 | 重磅专题 |
| 9 | Hermès | 爱马仕 | 橙+奶油白 | 极致克制 | 高端品牌 |
| 10 | MIT Tech Review | MIT科技评论 | 白+红顶条 | 学术权威 | 科技分析 |
| 11 | WIRED | WIRED杂志 | 黑+霓虹黄 | 前卫科技 | 科技媒体 |
| 12 | Paper & Ink | 文学期刊 | 暖奶油+深红 | 印刷厚重 | 长文/文学 |
| 13 | Dark Botanical | 当代画廊 | 黑+粉金赤陶 | 优雅艺术 | 高端品牌 |
| 14 | Notebook | Moleskine | 灰底+彩标签 | 触感手工 | 知识/工具 |
| 15 | Apple | Apple.com | 灰白+蓝 | 极致简洁 | 品牌/产品 |

## 使用方式

### 基础用法

```bash
python3 ~/.openclaw/skills/code-to-image/render.py cover.html
# 输出: cover_render.png (1080×1440 @2x → 2160×2880)
```

### 常用参数

```bash
# 小红书竖版封面 (1080×1440)
python3 render.py cover.html -w 1080 -h 1440 --scale 2

# 抖音横版 (1920×1080)
python3 render.py cover.html -w 1920 -h 1080 --scale 2

# 知乎/公众号竖版 (1440×2560)
python3 render.py cover.html -w 1440 -h 2560 --scale 2

# Instagram方形 (1080×1080)
python3 render.py cover.html -w 1080 -h 1080 --scale 2

# 超高清 (4K@4x = 15360×8640)
python3 render.py poster.html -w 3840 -h 2160 --scale 4

# 指定输出
python3 render.py index.html -o final.png

# 截取特定元素
python3 render.py index.html --selector "#hero-section"

# 完整长页面
python3 render.py landing.html --fullpage
```

## 完整工作流

### Step 1: 设计 HTML

使用 `frontend-design` skill 生成设计稿：

```html
<!-- 暗黑科技风封面 -->
<!DOCTYPE html>
<html>
<head>
  <style>
    body {
      width: 1080px; height: 1440px;
      background: #0a0a0f;
      font-family: 'Noto Sans SC', sans-serif;
    }
    h1 {
      font-size: 96px;
      background: linear-gradient(135deg, #00ff88, #a78bfa);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
    }
    /* ...更多设计... */
  </style>
</head>
<body>
  <h1>AI Agent 实战指南</h1>
</body>
</html>
```

### Step 2: 渲染

```bash
python3 ~/.openclaw/skills/code-to-image/render.py cover.html -o ai-agent-cover.png
```

### Step 3: 输出

得到 `2160×2880` PNG，可直接发布到任何平台。

## 平台尺寸速查

| 平台 | 比例 | viewport | @2x 输出 | 命令 |
|------|:---:|----------|----------|------|
| 小红书封面 | 3:4 | 1080×1440 | 2160×2880 | `-w 1080 -h 1440` |
| 小红书横版 | 4:3 | 1440×1080 | 2880×2160 | `-w 1440 -h 1080` |
| 抖音/视频号 | 9:16 | 1080×1920 | 2160×3840 | `-w 1080 -h 1920` |
| 抖音横版 | 16:9 | 1920×1080 | 3840×2160 | `-w 1920 -h 1080` |
| 公众号封面 | 16:9 | 900×383 | 1800×766 | `-w 900 -h 383` |
| 知乎头图 | 16:9 | 1920×1080 | 3840×2160 | `-w 1920 -h 1080` |
| Instagram | 1:1 | 1080×1080 | 2160×2160 | `-w 1080 -h 1080` |
| Twitter/X | 16:9 | 1200×675 | 2400×1350 | `-w 1200 -h 675` |
| B站封面 | 16:9 | 1920×1080 | 3840×2160 | `-w 1920 -h 1080` |
| 海报印刷 (A3) | 1:√2 | 3508×4961 | A3@300dpi | `-w 3508 -h 4961 --scale 1` |

## 设计 → 渲染联动

**最佳实践**: 先让 `frontend-design` 产出 HTML，保存到文件，再调用本 skill 渲染。

```
用户: "生成一张AI Agent实战指南的小红书封面"
  ↓
1. 调 frontend-design → 产出 index.html (暗黑科技风, 3:4)
  ↓
2. 调 code-to-image → render.py index.html -w 1080 -h 1440 -o agent-cover.png
  ↓
3. 输出: agent-cover.png (2160×2880)
```

## 进阶技巧

### 1. 批量生成

```bash
# 改标题颜色 → 批量出图
for color in '#00ff88' '#ff6b6b' '#a78bfa' '#fbbf24'; do
  sed "s/--accent-color--/$color/g" template.html > "cover-$color.html"
  python3 render.py "cover-$color.html" -o "output/cover-$color.png"
done
```

### 2. Canvas 方案

使用 `canvas-design` skill 创建纯 Canvas 设计，同样通过本 skill 渲染。

### 3. 组件化复用

将常用 UI 组件（标签、分割线、数据面板）抽成 CSS class，跨封面复用。

### 4. 字体处理

- 谷歌字体：`@import url(...)` 会自动加载
- 本地字体：CSS `@font-face` + 文件路径
- 系统字体：直接使用，无需引入

## 故障排查

| 问题 | 解决 |
|------|------|
| 字体未加载 | 增加 `--delay 3` |
| 动画未完成 | 增加 `--delay 2` |
| 中文乱码 | 确保 HTML `<meta charset="UTF-8">` |
| 分辨率不够 | 提高 `--scale 4` |
| 只截部分 | 用 `--selector "#id"` |
| 颜色不准 | 使用 sRGB 色值，避免 Display P3 |

## 自定义规则

1. **默认 Editorial 杂志风**，除非用户明确指定其他风格
2. **不加出品署名**，除非用户要求
3. 每次生成前先问平台（小红书/公众号/抖音/知乎…）以确定尺寸
4. 渲染用 `--scale 2` 保证清晰度

## 模板文件

```
~/.openclaw/skills/code-to-image/templates/
├── editorial.html          ← 默认模板
├── monocle.html            ← FT Weekend
├── art-deco.html           ← 盖茨比黄金时代
├── zen.html                ← 日式侘寂
├── blueprint.html          ← 工程蓝图
├── swiss.html              ← 瑞士极简
├── kinfolk.html            ← 慢生活
├── cinematic.html          ← 电影海报
├── hermes.html             ← 爱马仕奢侈
├── mit-tech-review.html    ← MIT科技评论
├── wired.html              ← WIRED杂志
├── paper-ink.html          ← 文学期刊
├── dark-botanical.html     ← 当代画廊
├── notebook.html           ← Moleskine手帐
└── apple.html              ← Apple极致
```

## 与其他 Skill 的关系

```
code-to-image ← 渲染器（本 skill）
    ↑
    ├── frontend-design       → HTML/CSS 设计稿
    ├── canvas-design         → Canvas 设计稿
    ├── frontend-design-ultimate → React 组件设计
    ├── design-md-collection  → 71套设计参考
    ├── content-cover-gen     → 封面隐喻方法论
    └── poster-design-generation → 海报版式参考
```
