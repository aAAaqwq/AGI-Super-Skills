---
name: content-cover-gen
description: |
  Generate platform-specific cover images optimized for content posts.
  Anti-AI aesthetic: produces realistic, editorial-style covers that don't look AI-generated.
  Supports Xiaohongshu (3:4), WeChat (1.8:1), Douyin (9:16), and custom ratios.
  Use when: creating cover images for social media posts, articles, or videos.
  Key principle: covers should look like a human designer made them, not AI.
---

# Content Cover Generator

Generate cover images that look professionally designed by a human, not AI-generated.

## Core Anti-AI Principles

### What makes a cover look "AI-generated" (AVOID):
- Generic tech gradients (purple-blue nebula, particle effects)
- AI-specific visual tropes (floating holograms, glowing circuits, digital rain)
- English text on Chinese content
- Overly symmetric compositions
- Glossy/futuristic textures
- Stock-photo-look backgrounds (abstract shapes, light beams)
- Too many elements competing for attention

### What makes a cover look "human-designed" (AIM FOR):
- **Clean solid or subtle gradient backgrounds** (2 colors max)
- **Bold Chinese text** that's the visual anchor
- **Negative space** — let the title breathe
- **Real-feeling textures**: paper, matte, slight grain
- **Simple geometric accents** (line, dot, arrow, bracket)
- **Tool screenshots** with annotations for tech content
- **Handwritten-style** or bold sans-serif Chinese typography
- **Color palette**: dark backgrounds (深灰/黑/深蓝) with 1 accent color

## Cover Style Matrix

| Platform | Ratio | Style | Text Style |
|----------|-------|-------|-----------|
| 小红书 | 3:4 | 信息图/截图风 | Bold, 3-5字主标题 |
| 公众号 | 1.8:1 | 杂志封面/编辑风 | Clean headline |
| 抖音 | 9:16 | 视觉冲击/大字风 | 超大号标题 |

## Prompt Architecture

### Template Structure
```
[Style Directive] + [Background] + [Text Content] + [Layout] + [Anti-AI Rules] + [Technical]
```

### 小红书 Prompt Template

For tech/AI content (Daniel's niche):
```
A social media cover image, vertical 3:4 ratio.

Style: Clean, modern, information-graphic inspired. NOT AI-generated looking.
Background: Solid dark charcoal (#1a1a2e) with a subtle matte texture.
Main visual: A simple line-art icon or schematic related to {TOPIC} in the center, drawn with thin white lines.
Text overlay area: Large empty space at top 40% for Chinese text overlay.
Accent: One thin horizontal line in electric blue (#00d4ff) separating icon from text area.

IMPORTANT: 
- Do NOT generate any text/letters/characters in the image
- Leave clear space for text overlay to be added later
- No gradients, no glow effects, no particle effects, no holograms
- The image should look like a clean infographic background, not a sci-fi poster
- Matte finish, no glossy reflections
```

For tool/product content:
```
A social media cover image, vertical 3:4 ratio.

Style: Product showcase, clean white/light gray background.
Main visual: Stylized screenshot mockup of {TOOL_NAME} interface, flat design, slightly tilted with drop shadow.
Layout: Tool mockup takes up center 60% of frame, white border on all sides.
Accent: Minimal — a small colored dot or line in corner.

IMPORTANT:
- Do NOT generate any text/characters in the image
- Clean product shot aesthetic, like a tech blog header
- No gradients, no sci-fi elements
- White or very light gray background only
```

### 公众号 Prompt Template

```
A wide article header image, horizontal 16:9 ratio.

Style: Editorial magazine cover, professional and clean.
Background: Solid dark navy (#0f0f23) with very subtle paper grain texture.
Layout: Left 60% is clean space, right 40% has a minimal geometric pattern (dots, lines, or a simple abstract shape) in muted gold (#c9a96e).
Accent: A thin vertical gold line separating the two sections.

IMPORTANT:
- Do NOT generate any text/characters
- Editorial, sophisticated look — think Monocle or Wired magazine header
- No gradients, no glow, no tech clichés
- Matte finish
```

### 抖音 Prompt Template

```
A vertical video thumbnail, 9:16 ratio.

Style: Bold, eye-catching, designed for small phone screens.
Background: Solid black or very dark color.
Layout: Large empty center area for bold text overlay (60% of frame).
Visual element: One simple, high-contrast icon or shape at the bottom, in bright yellow (#ffd700) or electric cyan (#00ffff).
Typography area: Center of frame, clearly marked negative space.

IMPORTANT:
- Do NOT generate any text/characters
- Maximum visual simplicity — one focal point only
- Designed to be readable at thumbnail size
- No busy backgrounds, no gradients, no particle effects
```

## Topic-to-Visual Mapping

| Content Topic | Visual Element | Color Accent |
|--------------|---------------|-------------|
| AI Agent / 智能体 | Network nodes connecting, simple line art | #00d4ff cyan |
| AI编程工具 | Code bracket icon < / >, terminal cursor | #00ff88 green |
| AI创业 / 一人公司 | Simple rocket or arrow-up icon | #ffd700 gold |
| AI效率 / 工具推荐 | Gear/cog icon or checklist | #ff6b6b coral |
| AI趋势 / 行业分析 | Upward trending line graph, minimal | #a78bfa purple |
| 大学生 / 学习 | Graduation cap outline or book icon | #4fc3f7 blue |
| 观点 / 批判 | Lightbulb or speech bubble outline | #ffb74d orange |
| 教程 / 操作指南 | Step arrows or numbered circles | #81c784 green |

## Text Overlay (Post-Generation)

After generating the background image, add Chinese text overlay. Use relay-image-gen with a text overlay tool, or:

1. Generate the **background-only** image (no text in prompt)
2. Use HTML/CSS to overlay text (for automated pipelines)
3. Or use the image as background in Canva/Figma and add text manually

### Text Overlay Guidelines

| Element | 小红书 | 公众号 | 抖音 |
|---------|--------|--------|------|
| 主标题 | 3-5字, 超大号, 白色/亮色 | 8-15字, 大号 | 4-8字, 超大号 |
| 副标题 | 可选, 8字以内 | 可选 | 不建议 |
| 字体风格 | 粗体/手写体 | 粗无衬线 | 超粗体 |
| 位置 | 上部1/3或居中 | 左侧或居中 | 居中偏上 |
| 阴影 | 必需(文字阴影) | 可选 | 必需 |

## Workflow Integration

### In Content Production SOP
```
1. Read the article content
2. Identify the topic category (from mapping table above)
3. Select the appropriate platform template
4. Customize the prompt with topic-specific visual elements
5. Generate background image via relay-image-gen
6. (Optional) Add text overlay
7. Quality check: Does it look AI-generated? If yes, regenerate with more constraints
```

### Quick Generate Command
```bash
# 小红书封面 (background only)
uv run ~/.openclaw/skills/relay-image-gen/scripts/relay_image_gen.py \
  -p "$(cat ~/.openclaw/agents/content/agent/skills/content-cover-gen/templates/xhs-bg-prompt.txt)" \
  -f "cover-xhs.jpg" -a "3:4" -r "1k"

# 公众号封面 (background only)  
uv run ~/.openclaw/skills/relay-image-gen/scripts/relay_image_gen.py \
  -p "$(cat ~/.openclaw/agents/content/agent/skills/content-cover-gen/templates/gzh-bg-prompt.txt)" \
  -f "cover-gzh.jpg" -a "16:9" -r "1k"

# 抖音封面 (background only)
uv run ~/.openclaw/skills/relay-image-gen/scripts/relay_image-gen.py \
  -p "$(cat ~/.openclaw/agents/content/agent/skills/content-cover-gen/templates/douyin-bg-prompt.txt)" \
  -f "cover-douyin.jpg" -a "9:16" -r "1k"
```

## Quality Checklist (Anti-AI Validation)

Before accepting a generated cover, check:

- [ ] No AI-generated text/letters visible in the image
- [ ] No sci-fi/tech gradient clichés (purple nebula, glowing particles)
- [ ] No holographic or futuristic elements
- [ ] Background is clean (solid or simple gradient, max 2 colors)
- [ ] Clear negative space for text overlay
- [ ] Looks like a real designer made it (minimal, intentional)
- [ ] Appropriate color accent for the content topic
- [ ] Correct aspect ratio for the target platform

## References

- `templates/xhs-bg-prompt.txt` — 小红书背景图prompt模板
- `templates/gzh-bg-prompt.txt` — 公众号背景图prompt模板
- `templates/douyin-bg-prompt.txt` — 抖音背景图prompt模板
- `references/anti-ai-cover-principles.md` — 反AI感封面设计原则
