---
name: content-cover-gen
description: >
  内容驱动封面生成：从文章标题/核心观点自动生成视觉隐喻提示词，调用 relay-image-gen 出图。
  每张封面3秒内传达文章核心观点，杜绝通用背景。
  支持小红书(3:4)、抖音(9:16)、公众号(16:9)、知识星球(1:1)、掘金(16:9)。
  触发：'生成封面'、'封面生成'、'cover'、'thumbnail'、'封面图'、'缩略图'。
---

# 内容驱动封面生成

把文章核心观点变成一张3秒能看懂的封面图。

## 核心原则

**❌ 封面不是背景图。套哪篇都能用的封面 = 没有价值。**
**✅ 封面是视觉摘要。3秒内让读者知道这篇文章/视频在讲什么。**

## 快速工作流

```
输入：文章标题 + 核心观点（一句话）+ 目标平台
  ↓
Step 1: 匹配视觉隐喻（从隐喻库选择或自创）
  ↓
Step 2: 构建提示词（5要素公式）
  ↓
Step 3: 调用 relay-image-gen 出图
  ↓
Step 4: 输出封面文件路径 + 提示词（可追溯）
```

## Step 1: 匹配视觉隐喻

### 隐喻速查表

| 文章角度 | 视觉隐喻 | 色彩情绪 | 示例场景 |
|---------|---------|---------|---------|
| 警告/封禁 | 盾牌、门锁、红叉、警告标志、墙 | 红黑 | 盾牌挡住机器人 |
| 对比/测评 | 天平、排行榜、VS分屏、赛车 | 蓝白 | 6个角色站在排行榜上 |
| 批判/反共识 | 破裂面具、气泡破裂、碎镜、空盒子 | 红金 | 礼物盒打开是空的 |
| 教程/攻略 | 地图、钥匙、阶梯、工具箱、指南针 | 蓝绿 | 打开的地图上有路径 |
| 个人故事 | 人影剪影+场景、时间线、日记本 | 暖色调 | 人站在岔路口 |
| 趋势/预测 | 望远镜、火箭、道路分叉、上升曲线 | 紫蓝 | 火箭升空 |
| 创业/商业 | 拼图、积木搭建、蓝图、种子发芽 | 金黑 | 积木搭成城堡 |
| 效率/工具 | 齿轮、涡轮、加速器、杠杆 | 青橙 | 杠杆撬动巨石 |
| 深度分析 | 放大镜、解剖图、层叠透视 | 深蓝白 | 放大镜下的芯片 |
| 热点/争议 | 火焰、火山、辩论台、麦克风 | 红橙 | 两个火焰对撞 |
| 真实经历 | 场景复现（工位/校园/咖啡厅） | 自然色 | 深夜工位+屏幕光芒 |
| 避坑/教训 | 地雷、陷阱、警告牌、路障 | 黄黑 | 前方有地雷标志 |

### 匹配逻辑

1. 提炼文章核心观点（一句话，≤15字）
2. 判断文章角度（从上表匹配，或自创隐喻）
3. 如果没有现成隐喻，问自己：**"这个观点像什么画面？"**
4. 选择对应色彩情绪

## Step 2: 构建提示词

### 5要素公式

```
[主体场景] + [视觉隐喻/故事] + [色彩情绪] + [风格] + [格式]
```

| 要素 | 说明 | 要求 |
|------|------|------|
| 主体场景 | 封面主要视觉元素 | 必须具体，不能用"抽象图形" |
| 视觉隐喻 | 把观点变成画面 | 必须有故事性，让人一看就懂 |
| 色彩情绪 | 跟文章情绪匹配 | 最多2-3种颜色，高对比度 |
| 风格 | 插画/照片/3D等 | 推荐：editorial illustration / flat design |
| 格式 | 比例+约束 | 按平台规格，加 "no text overlay" |

### ❌ 错误示例

```
# 纯风格，跟内容无关
"Dark background with blue accent color, abstract geometric shapes, minimal design"

# 太抽象
"A beautiful image about AI, modern style, 3:4"
```

### ✅ 正确示例

**文章：小红书封杀AI代发**
> Xiaohongshu app icon with a red shield and warning symbol overlaid on it, a robot arm being pushed away by a hand, dark red and black color scheme, social media concept art, clean modern illustration, no text overlay, 3:4 vertical format

**文章：90% AI Agent是噱头**
> A cracked open gift box revealing a cheap toy robot inside with a big red X mark over it, next to it a plain cardboard box glowing gold from inside, metaphor for fake vs real value, bold editorial illustration, red and gold color scheme, 3:4 vertical format, no text

**文章：试了6个AI编程工具，说几句大实话**
> A split comparison showing 6 AI coding tool mascots as stylized robot characters on a leaderboard, tech startup style, neon blue and dark theme, modern flat illustration, competitive ranking concept, 3:4 vertical format, no text

**文章：大学生用AI月入过万的5个副业**
> A student sitting at a desk with holographic money floating around, a laptop showing multiple income streams, warm golden and green color scheme, motivational illustration style, 3:4 vertical format, no text

## Step 3: 调用出图

```bash
uv run ~/.openclaw/skills/relay-image-gen/scripts/relay_image_gen.py \
  -p "你的提示词" \
  -f "输出路径/cover.jpg" \
  -a "比例" \
  -r "1k"
```

### 各平台规格

| 平台 | 比例 | 参数 | 特殊要求 |
|------|------|------|---------|
| 小红书 | 3:4 竖版 | `-a "3:4"` | 3秒传达核心观点 |
| 抖音 | 9:16 竖版 | `-a "9:16"` | 高视觉冲击，手机屏可读 |
| 公众号 | 16:9 横版 | `-a "16:9"` | 编辑风格，专业感 |
| 知识星球 | 1:1 方形 | `-a "1:1"` | 简洁干净 |
| 掘金 | 16:9 横版 | `-a "16:9"` | 科技感 |
| B站 | 16:9 横版 | `-a "16:9"` | 醒目+信息密度 |
| 通用 | 1:1 方形 | `-a "1:1"` | 默认 |

## Step 4: 输出格式

```markdown
🖼️ 封面提示词：[完整提示词，可追溯]
🖼️ 封面文件：[文件路径]
📐 规格：[平台] [比例] [分辨率]
🎨 视觉隐喻：[一句话解释封面含义]
```

## 质量检查清单

- [ ] 封面3秒内能传达文章核心观点？
- [ ] 提示词包含具体物体/场景（非抽象）？
- [ ] 色彩跟文章情绪匹配？
- [ ] 没有文字覆盖（后期叠加更可控）？
- [ ] 比例正确？

## 高级技巧

### 多封面生成（A/B测试）
同一篇文章生成2-3张不同隐喻的封面，选最好的：
```bash
# 版本A：用隐喻1
uv run ~/.openclaw/skills/relay-image-gen/scripts/relay_image_gen.py -p "版本A提示词" -f "cover-a.jpg" -a "3:4" -r "1k"
# 版本B：用隐喻2
uv run ~/.openclaw/skills/relay-image-gen/scripts/relay_image_gen.py -p "版本B提示词" -f "cover-b.jpg" -a "3:4" -r "1k"
```

### 封面+文字合成
如果需要带文字的封面，先用此 skill 生成背景图，再用 image editing 工具叠加标题文字（推荐中文字体思源黑体）。

**如果用户明确提到：**
- 优化字体排版
- 调整标题版式
- 封面字不好看 / 信息层级不清
- 想把标题排得更有冲击 / 更专业

先读取并使用：`/home/aa/clawd/skills/content-typography/SKILL.md`

它专门处理：
- 中文标题压缩
- 分行规则
- 字重/对齐/留白
- 小红书 / 公众号 / 抖音封面的排版适配

### 批量生成
多篇文章的封面可以并行生成（3个 exec 同时跑），每篇用不同内容提示词。
