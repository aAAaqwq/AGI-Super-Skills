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

## 小红书首图专用规则（2026-04-06 夜间补充）

如果目标平台是 **小红书**，封面默认遵循下面规则：

### 1) 先判断封面类型
不要直接让模型自由发挥，先选一种：
- **大标题卡片型**：观点 / 趋势 / 避坑
- **对比评测型**：工具 PK / 方案选择
- **清单总结型**：3个工具 / 5个步骤 / 合集
- **截图解释型**：界面拆解 / 工作流演示 / 案例分析

### 2) 图里必须有字
- 主标题优先 8-16 字
- 可补 1 行副标题或 2-4 个结果标签
- 不要只靠笔记标题承载信息
- 缩略图状态下必须还能读到重点

### 3) 主体必须具体
优先出现：
- 人物 + 工位 / 设备
- 工具 UI / 产品界面 / 截图
- 对比关系 / 清单卡片 / 流程图
- 真实任务场景

默认禁止：
- 发光机器人
- 抽象几何图形
- hologram 漂浮 UI
- 为了“高级感”牺牲信息量的极简科技图

### 4) 封面目标不是艺术感，是点击率
一张合格的小红书首图，应该满足：
- 0.5-3 秒知道内容主题
- 像经验总结 / 教程 / 观点卡，而不是品牌海报
- 单看首图就知道：这篇在讲结论 / 对比 / 清单 / 步骤

### 5) 新提示词结构
如果是小红书首图，提示词建议写成：

```text
[封面版式] + [主体场景] + [主标题文案] + [副标题/标签] + [具体工具/对象] + [视觉隐喻] + [配色] + [风格] + [比例]
```

示例：
```text
清单总结型小红书封面，一个21岁创业者坐在电脑前，画面中有3个AI工具卡片并排展示，主标题“我只留这3个AI工具”，副标题“删掉47个后效率反而翻倍”，红白黑高对比配色，中文信息卡片风格，真实工作台场景，3:4 竖版
```

### 6) 不再默认走“纯背景图”路线
以前常见但效果差的做法：
- 先生成一张很美的 AI 图
- 留大片空白
- 后面再想办法补字

现在改成：
- 先定信息结构
- 再定版式
- 再让图服务内容

**一句话：封面是视觉摘要，不是氛围壁纸。**

## Step 3: 调用出图

### 默认出图链路（2026-04-06 起）

如果任务是**内容封面**而不是普通插画，默认顺序改为：

1. 先按本 skill 的方法论提炼核心观点与视觉隐喻
2. **优先调用本地 `qingyun-api` 的 Gemini 图片模型：`gemini-3-pro-image-preview`**
3. 仅当青云链路不可用或用户明确指定其它 provider 时，再退回 `relay-image-gen`

**原因**：这条链路已经在小红书封面实战里验证过，出图更直接、比例控制明确、和本地 skill 维护边界更清晰。

### 小红书封面特别规则（新增）
- 默认比例：`3:4`
- 不要把整段提示词直接当站内“文字配图”素材丢给平台生成；很容易产出**英文文字卡片/海报**而不是封面
- 封面必须先在本地生成，再上传到发布页
- 目标不是“好看”而已，而是**3 秒看懂这篇内容在讲什么**

```bash
# 默认推荐：直接走 qingyun Gemini
export QINGYUN_API_KEY=$(pass show api/qingyun | head -n 1)
bash ~/clawd/skills/qingyun-api/scripts/qingyun-image-gemini.sh \
  "你的内容型封面提示词" \
  --ratio 3:4 \
  -o "/path/to/cover"

# 备用：relay-image-gen
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

### 与 `xhs-smart-publisher` 的协作约定（新增 SOP）

如果目标平台是**小红书**，本 skill 产出后要满足下面 4 点，方便发布 skill 直接接手：

1. **输出真实文件路径**
   - 例如：`/home/aa/clawd/docs/daily-content/2026-04-04/xhs/cover-3-qingyun.jpg`
2. **优先 3:4 竖版**
3. **文件名可被文章元数据直接引用**
   - 文章里的 `🖼️ 封面：待生成` 要及时回填成真实路径
4. **不要把站内“文字配图”当作封面生成步骤的一部分**
   - 本 skill 负责的是：**先在本地把正确封面生成出来**
   - 然后交给 `xhs-smart-publisher` 上传

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
- [ ] **没有误生成“文字海报 / 提示词卡片 / 英文大段字”这种伪封面？**

## 高级技巧

### 小红书首图推荐套路（2026-04-06 验证）

对于“观点反差 / AI 反思 / 批判式内容”，优先用：
- **分屏对比**
- **左边主动思考 / 右边被工具反向削弱**
- **暖色 = 主动思考，冷色 = 被动依赖**

这类图在小红书封面上非常直接，用户 1-3 秒就能看懂。

示例：
> A split-scene editorial illustration: left side active thinking with warm golden brain glow, right side passive AI overuse with dim blue brain, emotionally sharp, no text overlay, 3:4 vertical cover.

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
