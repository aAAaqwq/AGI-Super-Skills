---
name: article-to-infographic
description: "长文/测评文章 → 知识视觉笔记套图（3-5张）。自动提炼核心逻辑、规划分镜、生成高阶图像Prompt（4模块结构）。支持手写笔记/思维导图/架构图/对比矩阵四种风格。Use when: 文章转知识笔记、知识笔记图片、思维导图、视觉笔记、长文转图、知识卡片、文章可视化、article to infographic、knowledge note。Output: 中文摘要 + 纯英文生图Prompt。Pair with vectronode-image/relay-image-gen to generate final images."
metadata:
  openclaw:
    emoji: 🧠
    related_skills:
      - vectronode-image
      - relay-image-gen
      - code-to-image
author: Daniel Li
---

# Article → Knowledge Visual Notes

将深度长文 / 测评 / 行业分析自动转化为 3-5 张高信息密度「视觉笔记图」的 Prompt 生成器。

## 核心能力

1. **知识拆解**：提取黄金标题、对标矩阵、核心逻辑、趋势演进
2. **分镜规划**：合理分配内容到 3-5 张图中
3. **高阶 Prompt 生成**：每张图 4 模块英文 Prompt
4. **风格定制**：支持手写笔记 / 思维导图 / 架构图 / 对比矩阵

## 触发词

`知识笔记` / `文章转图` / `思维导图` / `视觉笔记` / `长文转图` / `知识卡片` / `文章可视化` / `生成笔记图` / `article to infographic` / `knowledge note`

## 使用方法

```bash
# 1. 从文章 Markdown 生成提示词套图
python3 ~/.openclaw/skills/article-to-infographic/scripts/plan_visual_notes.py \
  --article ~/articles/my-article.md \
  --style hand-written \
  --count 4 \
  --output ~/output/prompts/

# 2. 从纯文本输入
python3 ~/.openclaw/skills/article-to-infographic/scripts/plan_visual_notes.py \
  --text "$(cat article.txt)" \
  --style mixed \
  --output ~/output/

# 3. 生成 Prompt 后接力生图
python3 ~/.openclaw/skills/vectronode-image/scripts/vectronode_image.py generate \
  --prompt "$(cat ~/output/prompts/frame-01-prompt.txt)" \
  --output ~/output/images/frame-01.png \
  --size 1536x1024
```

## 参数

| Flag | 说明 | 默认 |
|------|------|------|
| `--article` | 文章文件路径 | — |
| `--text` | 纯文本输入 | — |
| `--style` | 视觉风格 (见下方) | `mixed` |
| `--count` | 图片数量 3-5 | `4` |
| `--output` | 输出目录 | `./visual-notes/` |

## 四种视觉风格

| 风格 | `--style` | 视觉形态 |
|------|-----------|---------|
| **手写笔记** | `hand-written` | 手机屏幕/纸张上的高密度手写图表，不同颜色笔迹 |
| **思维导图** | `mind-map` | 手绘感白板/平板思维导图，中心放射结构 |
| **架构/逻辑图** | `architecture` | 专业系统演算图，带批注和连接线 |
| **对比矩阵** | `comparison` | 高对比度参数对比表，重点标红 |
| **混合风格** | `mixed` | 自动为每张图选最优风格 |

## 分镜规划原则

| 图序 | 内容定位 | 风格倾向 |
|------|---------|---------|
| 图1 | 核心概念/黄金标题/定调 | 手写笔记/标题页 |
| 图2 | 核心竞争力/数据矩阵 | 对比矩阵/数据图表 |
| 图3 | 逻辑拆解/竞争分析 | 思维导图/双边对比 |
| 图4 | 趋势演进/成本分析/总结 | 架构图/手写红框总结 |
| 图5（可选）| 金句/行动建议 | 手写笔记 |

## Prompt 四模块结构

每个生成的 Prompt 严格包含：

```
[模块1] Main Description — 环境、视角、材质、光线
[模块2] Content & Layout — 精确的文字位置、排版层级、颜色
[模块3] Context & Environment — 真实感环境细节
[模块4] Quality & Style — 画质、风格、技术关键词
```

详见 [Prompt 模板](references/prompt-template.md)。

## 工作流示例

以 Claude Fable 5 测评文章为例：

<details>
<summary>点击展开完整工作流</summary>

```bash
# Step 1: 生成 Prompt
python3 ~/.openclaw/skills/article-to-infographic/scripts/plan_visual_notes.py \
  --article ~/articles/claude-fable-5-review.md \
  --style mixed \
  --count 4 \
  --output /tmp/fable5-visual/

# 输出: /tmp/fable5-visual/
#   frame-01-prompt.txt  — 神话与寓言的命名隐喻 (手写笔记)
#   frame-02-prompt.txt  — SWE-Bench Pro 80.3% 跑分矩阵 (对比矩阵)
#   frame-03-prompt.txt  — 编程/视觉/降级 三重能力拆解 (思维导图)
#   frame-04-prompt.txt  — 定价策略与战略判断 (架构图)

# Step 2: 接力生图
for i in 01 02 03 04; do
  python3 ~/.openclaw/skills/vectronode-image/scripts/vectronode_image.py generate \
    --prompt "$(cat /tmp/fable5-visual/frame-${i}-prompt.txt)" \
    --output /tmp/fable5-visual/images/frame-${i}.png \
    --size 1536x1024
done
```

</details>

## 与图像生图 Skill 接力

```
文章 .md / text
    │
    ▼
plan_visual_notes.py  ──→  prompts/   (中文摘要 + 英文 Prompt)
    │                        ├── frame-01-prompt.txt
    │                        ├── frame-02-prompt.txt
    │                        ├── frame-03-prompt.txt
    │                        └── frame-04-prompt.txt
    │
    ▼
vectronode_image.py   ──→  images/    (出图)
    │                        ├── frame-01.png
    │                        ├── ...
    │
    ▼
小红书 / 公众号 / 企业内参 配图
```

## Prompt 注意事项

- **必须纯英文**：Midjourney / DALL-E / gpt-image-2 对英文排版支持最好
- **中文文字用双引号标记**：`"中文字符串"`
- **排版指令必须精确到坐标区域**：Top-left / Center / Right column / Bottom
- **强制生成文字**：用 `bold capital letters`, `READS:`, `TEXT MUST SAY:` 等
- **黑色笔迹 + 红色标注 + 蓝色批注**：模拟手写笔记的多色笔迹
- **避免纯白背景**：用带纹理的纸张/白板/手机屏幕增加真实感

## 相关文档

| 文档 | 内容 |
|------|------|
| [Prompt 模板](references/prompt-template.md) | 完整 4 模块模板 + 各风格的变体 |
| [使用示例](references/examples.md) | MarkItDown / Fable 5 等真实案例 |
