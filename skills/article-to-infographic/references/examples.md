# 使用示例

## 示例 1：Claude Fable 5 测评文章

```bash
python3 ~/.openclaw/skills/article-to-infographic/scripts/plan_visual_notes.py \
  --article ~/articles/claude-fable-5-review.md \
  --style mixed \
  --count 4 \
  --output /tmp/fable5-notes/
```

### 输出分镜规划

```
图 1：核心概念：神话与寓言 — [Hand-written Note] — 概念定调与标题页
图 2：数据矩阵：跑分屠榜 — [Comparison Chart] — 跑分/对比数据矩阵页
图 3：逻辑拆解：编程从辅助到主力 — [Mind Map] — 能力拆解与竞争分析
图 4：战略判断与行动建议 — [Architecture Diagram] — 趋势演进与决策框架
```

### 生成的 Prompt 文件（节选）

**frame-01-prompt.txt**（手写笔记风格）：
> A photorealistic, ultra-clear, ultra-high-resolution close-up photograph of a dense hand-written study note on textured cream-white paper...
> Title: "Claude Fable 5 深度测评：你摸到了神话，但只摸到了一部分"
> Bullet points: SWE-Bench Pro: 80.3% ★, FrontiCode Diamond: 29.3% ★...

**frame-02-prompt.txt**（对比矩阵风格）：
> A photorealistic, high-resolution close-up photograph of a dense hand-drawn comparison matrix table on off-white paper...
> Headers: "Model" | "SWE-Bench" | "FrontierCode" | "HealthBench" | "Advantage"

### 接力生图

```bash
for f in /tmp/fable5-notes/frame-*-prompt.txt; do
  num=$(basename "$f" | grep -o '\d\d')
  python3 ~/.openclaw/skills/vectronode-image/scripts/vectronode_image.py generate \
    --prompt "$(cat "$f")" \
    --output "/tmp/fable5-notes/images/frame-${num}.png" \
    --size 1536x1024
done
```

---

## 示例 2：纯文本输入（无需文件）

```bash
python3 ~/.openclaw/skills/article-to-infographic/scripts/plan_visual_notes.py \
  --text "OpenAI released GPT-5.5 with 58.6% on SWE-Bench Pro. The model supports 2M token context..." \
  --style hand-written \
  --count 3 \
  --output /tmp/quick-notes/
```

---

## 示例 3：JSON 输出（Swift Agent 调用）

```bash
python3 ~/.openclaw/skills/article-to-infographic/scripts/plan_visual_notes.py \
  --article ~/articles/markitdown-review.md \
  --style comparison \
  --json
```

```json
{
  "title": "MarkItDown 深度测评",
  "section_count": 8,
  "frame_count": 4,
  "frames": [
    {
      "num": 1,
      "theme": "核心概念：Microsoft开源的文件转换神器",
      "style": "comparison",
      "reason": "概念定调与标题页"
    },
    ...
  ]
}
```

---

## 示例 4：强制全部用思维导图风格

```bash
python3 ~/.openclaw/skills/article-to-infographic/scripts/plan_visual_notes.py \
  --article ~/articles/ai-tools-comparison.md \
  --style mind-map \
  --count 5
```

---

## 示例 5：集成到 CI/自动化流水线

```bash
#!/bin/bash
set -e

ARTICLE="$1"
OUTPUT_BASE="/tmp/visual-notes/$(date +%Y%m%d-%H%M)"

echo "📝 Step 1: Extract & plan visual notes..."
python3 ~/.openclaw/skills/article-to-infographic/scripts/plan_visual_notes.py \
  --article "$ARTICLE" \
  --style mixed \
  --count 4 \
  --output "$OUTPUT_BASE"

echo "🎨 Step 2: Generate images via VectorNode..."
mkdir -p "$OUTPUT_BASE/images"
for prompt_file in "$OUTPUT_BASE"/frame-*-prompt.txt; do
  num=$(basename "$prompt_file" | grep -o '\d\d')
  python3 ~/.openclaw/skills/vectronode-image/scripts/vectronode_image.py generate \
    --prompt "$(cat "$prompt_file")" \
    --output "$OUTPUT_BASE/images/frame-${num}.png" \
    --size 1536x1024
  echo "  ✅ frame-${num}.png generated"
done

echo "📊 Step 3: Upload to WeChat as image post..."
# md2wechat create_image_post ...

echo "✅ Pipeline complete — $OUTPUT_BASE/images/"
```

---

## 适用文章类型

| 文章类型 | 推荐风格 | 理由 |
|---------|---------|------|
| **AI 模型测评** | `mixed`（手写笔记+对比矩阵+架构图） | 跑分数据多、逻辑层次丰富 |
| **工具开源项目介绍** | `architecture`（架构图+思维导图） | 技术架构是核心卖点 |
| **行业趋势分析** | `mind-map`（思维导图+手写总结） | 逻辑线索和分支判断多 |
| **竞品对比** | `comparison`（对比矩阵+架构图） | 数据对比优先 |
| **创业/商业分析** | `hand-written`（手写笔记+架构图） | 真实感、接地气 |
| **教程/操作指南** | `hand-written`（手写笔记+步骤图） | 手写感增强信任感和可读性 |

## 提示词质量检查清单

每个生成的 Prompt 必须满足：

- ✅ 全英文（中文用双引号包裹）
- ✅ 包含 4 个模块（Main Description / Content Layout / Context / Quality）
- ✅ 明确指定了至少 3 处精确文字及其位置
- ✅ 指定了颜色（black ink / red marker / blue pen）
- ✅ 描述了环境细节（纸张纹理/白板擦痕/光线角度）
- ✅ 包含 photorealistic / 8K / detailed texture 等画质关键词
- ✅ 所有中文字符串都在双引号内
- ✅ Prompt 长度 ≤ 950 字符（适配生图模型限制）
