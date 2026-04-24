---
name: content-cover-gen
description: >
  内容驱动封面生成：从文章标题/核心观点自动生成视觉隐喻提示词，调用图片模型出图。
  封面必须包含与文章相关的文字内容，3秒内传达核心观点。
  支持小红书(3:4)、抖音(9:16)、公众号(16:9)、知识星球(1:1)、掘金(16:9)、B站(16:9)。
  输出路径由调用方指定，默认存入 output/articles/{YYYY-MM-DD}/。
  触发：'生成封面'、'封面生成'、'cover'、'thumbnail'、'封面图'、'缩略图'。
  Author: Daniel Li
---

# 内容驱动封面生成

把文章核心观点变成一张 **3秒能看懂、带文字、有设计感** 的封面图。

> Skill 作者: Daniel Li
> 文章作者: 由调用方指定，未指定时留空

## 核心原则

**❌ 封面不是纯背景图。套哪篇都能用的封面 = 没有价值。**
**❌ 封面不是艺术展。追求美感牺牲信息量 = 浪费点击率。**
**✅ 封面是视觉摘要 + 信息卡。3秒内让读者知道这篇文章在讲什么。**
**✅ 封面必须有文字。主标题 + 可选副标题，信息层级清晰。**

## 设计美学标准（CPO级品味）

### 字体选择

| 用途 | 推荐字体 | 风格 | 备注 |
|------|---------|------|------|
| **主标题** | 思源黑体 Bold / Noto Sans SC Bold | 现代简洁 | 中文首选 |
| **主标题备选** | 阿里巴巴普惠体 Heavy | 亲切有力 | 偏年轻化 |
| **副标题** | 思源黑体 Medium / Noto Sans SC Medium | 清晰易读 | 比主标题轻 |
| **数字/英文** | Space Grotesk Bold / DM Sans Bold | 科技感 | 与中文混排 |
| **标签/标注** | 思源黑体 Regular | 轻量信息 | 不喧宾夺主 |

**字体质量红线**：
- ❌ 永远不用系统默认宋体/楷体
- ❌ 永远不用手写体做主标题（可做签名/装饰）
- ❌ 永远不用 Comic Sans / Papyrus 类
- ✅ 字重层级：主标题 Bold/Heavy > 副标题 Medium > 标签 Regular
- ✅ 行高 1.2-1.4，字间距 0.02-0.05em

### 配色系统

| 情绪方向 | 主色 | 辅色 | 背景色 | 适用场景 |
|---------|------|------|--------|---------|
| 专业科技 | `#0F172A` 深蓝黑 | `#38BDF8` 天蓝 | `#F8FAFC` 冷白 | 工具测评、技术深度 |
| 犀利观点 | `#DC2626` 正红 | `#FEF2F2` 浅红 | `#FFFFFF` 纯白 | 反共识、批判性内容 |
| 温暖故事 | `#78350F` 琥珀棕 | `#FDE68A` 暖黄 | `#FFFBEB` 暖白 | 个人经历、成长故事 |
| 前沿趋势 | `#4C1D95` 深紫 | `#A78BFA` 薰衣草 | `#F5F3FF` 薰衣白 | AI趋势、预测分析 |
| 实用教程 | `#065F46` 翡翠绿 | `#34D399` 翠绿 | `#ECFDF5` 薄荷白 | 工具教程、工作流 |
| 警示避坑 | `#92400E` 暗橙 | `#FBBF24` 明黄 | `#1C1917` 深灰黑 | 避坑、封禁、风险 |
| 对比测评 | `#1E40AF` 蓝 vs `#DC2626` 红 | `#E2E8F0` 浅灰 | `#FFFFFF` 纯白 | 横评、PK、选择 |
| 数据洞察 | `#0E7490` 青蓝 | `#67E8F9` 亮青 | `#F0FDFA` 极浅青 | 数据报告、行业分析 |

**配色红线**：
- ❌ 最多3种颜色（主+辅+背景），严禁渐变彩虹
- ❌ 禁止荧光色做主色
- ❌ 禁止红绿搭配（色盲不友好）
- ✅ 对比度 ≥ 4.5:1（WCAG AA标准）
- ✅ 同一系列封面用统一色系

### 版式规范

**信息层级（从上到下）**：
```
┌──────────────────────────┐
│  [视觉元素/图标/场景]      │  ← 顶部30%: 视觉吸引
│                          │
│  ┌──────────────────┐    │
│  │  主标题 (8-16字)  │    │  ← 中部40%: 核心信息
│  └──────────────────┘    │
│  副标题 / 标签组          │  ← 底部30%: 补充信息
└──────────────────────────┘
```

**文字排版规则**：
- 主标题字号：占画面宽度 60-75%
- 副标题字号：主标题的 40-50%
- 文字区域居中，左右各留 10-15% 安全边距
- 文字与背景必须有对比层（半透明遮罩/色块/阴影）

### 视觉风格

| 风格 | 适用 | 描述 |
|------|------|------|
| **Editorial Flat** | 大部分场景 | 编辑插画风格，扁平但有层次 |
| **Infographic Card** | 清单/数据/对比 | 信息卡片式，图表+数据可视化 |
| **Split Comparison** | 横评/观点对立 | 分屏对比，左vs右 |
| **Scene Realism** | 真实经历/场景复现 | 接近摄影的真实场景 |
| **Neon Tech** | AI/编程/科技前沿 | 深色背景+霓虹光效（克制使用） |

**永远禁止**：
- 发光机器人 / 全息投影 / 科幻粒子特效
- 纯抽象几何图形无任何信息
- 英文大段文字作为中文封面
- 3D立体弹窗/气泡/标签云
- 任何像"AI生成的模板感"

---

## 快速工作流

```
输入：文章标题 + 核心观点 + 目标平台 + 输出路径
  ↓
Step 1: 匹配视觉隐喻 + 版式（隐喻库选择或自创）
  ↓
Step 2: 构建提示词（8要素公式，必须含文字要求）
  ↓
Step 3: 调用图片模型出图（优先 qingyun Gemini）
  ↓
Step 4: 质量检查 → 输出封面文件路径
```

## Step 1: 匹配视觉隐喻 + 版式

### 隐喻速查表

| 文章角度 | 视觉隐喻 | 色彩情绪 | 版式 | 示例场景 |
|---------|---------|---------|------|---------|
| 警告/封禁 | 盾牌、门锁、红叉、警告标志 | 红黑 | Infographic Card | 盾牌挡住机器人 |
| 对比/测评 | 天平、排行榜、VS分屏、赛车 | 蓝白/蓝红 | Split Comparison | 6个角色站在排行榜上 |
| 批判/反共识 | 破裂面具、气泡破裂、碎镜、空盒子 | 红金 | Editorial Flat | 礼物盒打开是空的 |
| 教程/攻略 | 地图、钥匙、阶梯、工具箱、指南针 | 蓝绿 | Infographic Card | 打开的地图上有路径 |
| 个人故事 | 人影剪影+场景、时间线、日记本 | 暖色调 | Scene Realism | 人站在岔路口 |
| 趋势/预测 | 望远镜、火箭、道路分叉、上升曲线 | 紫蓝 | Editorial Flat | 火箭升空 |
| 创业/商业 | 拼图、积木搭建、蓝图、种子发芽 | 金黑 | Editorial Flat | 积木搭成城堡 |
| 效率/工具 | 齿轮、涡轮、加速器、杠杆 | 青橙 | Infographic Card | 杠杆撬动巨石 |
| 深度分析 | 放大镜、解剖图、层叠透视 | 深蓝白 | Infographic Card | 放大镜下的芯片 |
| 热点/争议 | 火焰、火山、辩论台、麦克风 | 红橙 | Split Comparison | 两个火焰对撞 |
| 真实经历 | 场景复现（工位/校园/咖啡厅） | 自然色 | Scene Realism | 深夜工位+屏幕光芒 |
| 避坑/教训 | 地雷、陷阱、警告牌、路障 | 黄黑 | Infographic Card | 前方有地雷标志 |

### 小红书封面类型判断

先选版式再写提示词：
- **大标题卡片型**：观点 / 趋势 / 避坑
- **对比评测型**：工具 PK / 方案选择
- **清单总结型**：3个工具 / 5个步骤 / 合集
- **截图解释型**：界面拆解 / 工作流演示 / 案例分析

## Step 2: 构建提示词

### 8要素公式（封面必须有文字）

```
[版式] + [主体场景] + [主标题文字] + [副标题/标签] + [视觉隐喻] + [配色] + [字体风格] + [比例]
```

| 要素 | 说明 | 要求 |
|------|------|------|
| 版式 | 封面结构类型 | 必须指定：Editorial Flat / Infographic Card / Split Comparison / Scene Realism |
| 主体场景 | 封面主要视觉元素 | 必须具体，有故事性 |
| 主标题文字 | **必须包含**，8-16字 | 封面的灵魂信息 |
| 副标题/标签 | 补充信息，2-4个标签 | 可选但推荐 |
| 视觉隐喻 | 把观点变成画面 | 让人一看就懂 |
| 配色 | 按配色系统选择 | 最多2-3种，高对比 |
| 字体风格 | 中文字体要求 | "bold Chinese text, clean modern font" |
| 比例 | 按平台规格 | 小红书3:4 / 公众号16:9 / 抖音9:16 |

### ✅ 优秀提示词示例

**文章：小红书封杀AI代发**
```
Infographic card cover for social media article. Center: a smartphone with Xiaohongshu app icon, a large red shield symbol overlapping it. Main title text "小红书封杀AI代发" in bold Chinese characters, white text on dark red banner. Subtitle "3个自救方案" in smaller white text below. Color scheme: #DC2626 red, #1C1917 dark background, #FEF2F2 light accents. Editorial flat illustration style with clean bold Chinese typography (Noto Sans SC Bold). No English text. 3:4 vertical format.
```

**文章：90% AI Agent是噱头**
```
Split comparison cover. Left side: a glowing premium robot labeled "包装" with gold sparkle effects. Right side: a plain cheap toy robot labeled "实际" with a red question mark. Center divider with main title "90% AI Agent是噱头" in bold white Chinese text on dark banner. Bottom tags: "实测" "避坑" "真相". Color scheme: gold vs red on #0F172A dark blue-black background. Bold editorial illustration, strong Chinese typography, no English. 3:4 vertical format.
```

**文章：试了6个AI编程工具，说几句大实话**
```
Infographic card cover. Top: stylized code editor window with colorful syntax highlighting. Center: main title "6个AI编程工具" in large bold white Chinese text. Below: subtitle "大实话横评" in medium cyan text. Bottom: 6 small tool icon cards arranged in 2 rows of 3, each with a checkmark or X. Color scheme: #0F172A deep blue-black background, #38BDF8 sky blue accents, #F8FAFC white text. Clean modern tech aesthetic, bold Chinese typography (Space Grotesk for numbers, Noto Sans SC for Chinese). No English body text. 3:4 vertical format.
```

**文章：大学生用AI月入过万的5个副业**
```
Scene realism cover. A young person sitting at a modern desk at night, laptop screen glowing warm, holographic-style income charts floating around (but tasteful, not cheesy). Top banner: main title "大学生AI副业" in bold white Chinese text with dark semi-transparent background. Bottom: "5个真实路径" + tags "月入过万" "可复制" "零门槛". Color scheme: #78350F amber-brown warm tones, #FDE68A warm yellow highlights, #FFFBEB warm white background elements. Realistic but slightly stylized illustration, warm inviting Chinese typography. No English. 3:4 vertical format.
```

**公众号封面示例：AI Agent工程化2.0**
```
Editorial flat illustration for tech article cover. A large architectural blueprint showing interconnected modules and data flow arrows, representing an AI agent system architecture. Main title "AI Agent工程化2.0" in bold white Chinese text positioned at center-bottom with dark semi-transparent overlay for readability. Subtitle "从概念到生产的完整路径". Color scheme: #0E7490 teal blue, #67E8F9 bright cyan accents on #F0FDFA light background. Clean professional design, bold Chinese typography (Noto Sans SC Bold), modern tech publication style. 16:9 horizontal format.
```

### ❌ 禁止的提示词写法

```
# 纯风格，跟内容无关
"Dark background with blue accent, abstract geometric shapes, minimal"

# 太抽象
"A beautiful image about AI, modern style, 3:4"

# 只有英文
"Top 5 AI Tools You Must Know, cyberpunk style, neon glow"

# 没有文字
"No text overlay, pure background image"  ← 这是旧做法，已废弃
```

## Step 3: 调用出图

### 出图链路优先级

1. **首选**：`qingyun-api` → Gemini `gemini-3-pro-image-preview`（已验证，出图直接）
2. **备选**：`relay-image-gen`（多 provider fallback：boluobao → gemini → xingjiabi）

```bash
# 首选：qingyun Gemini（推荐）
export QINGYUN_API_KEY=$(pass show api/qingyun | head -n 1)
bash ~/clawd/skills/qingyun-api/scripts/qingyun-image-gemini.sh \
  "你的内容封面提示词" \
  --ratio 3:4 \
  -o "{output_path}"

# 备选：relay unified wrapper
bash ~/.openclaw/skills/relay-image-gen/scripts/img-gen.sh \
  -p "你的提示词" \
  -f "{output_path}" \
  -a "3:4" \
  -r "1k"
```

### 输出路径规范

**不写死路径**。由调用方指定，默认遵循：

```
~/clawd/projects/MediaClaw/output/articles/{YYYY-MM-DD}/{topic-slug}-cover.{ext}
```

| 参数 | 说明 |
|------|------|
| `{YYYY-MM-DD}` | 当天日期 |
| `{topic-slug}` | 文章slug（小写、连字符、无空格） |
| `{ext}` | `.png` 或 `.jpg` |

### 各平台规格

| 平台 | 比例 | 参数 | 特殊要求 |
|------|------|------|---------|
| 小红书 | 3:4 竖版 | `-a "3:4"` | 必须有中文文字，3秒传达核心 |
| 抖音 | 9:16 竖版 | `-a "9:16"` | 高冲击，文字醒目 |
| 公众号 | 16:9 横版 | `-a "16:9"` | 编辑风格，专业感 |
| 知识星球 | 1:1 方形 | `-a "1:1"` | 简洁干净 |
| 掘金 | 16:9 横版 | `-a "16:9"` | 科技感 |
| B站 | 16:9 横版 | `-a "16:9"` | 醒目+信息密度 |

> 📋 **平台封面规范详情**：各平台的封面违规/推荐标准见 `~/clawd/projects/MediaClaw/references/platforms/` 下对应文档（weixin-mp.md / xiaohongshu.md / douyin.md）

## Step 4: 输出格式

```markdown
🖼️ 封面提示词：[完整提示词，可追溯]
🖼️ 封面文件：[文件路径]
📐 规格：[平台] [比例] [分辨率]
🎨 视觉隐喻：[一句话解释封面含义]
📝 封面文字：主标题「xxx」+ 副标题「xxx」
🎯 配色方案：[主色] + [辅色] + [背景色]
```

## 质量检查清单

- [ ] 封面3秒内能传达文章核心观点？
- [ ] **有中文文字？主标题清晰可读？**
- [ ] 字体美观（非默认宋体/楷体）？
- [ ] 信息层级清晰（主标题 > 副标题 > 标签）？
- [ ] 配色符合美学标准（≤3色，对比度≥4.5:1）？
- [ ] 提示词包含具体物体/场景（非抽象）？
- [ ] 比例正确？
- [ ] 没有英文大段文字？
- [ ] 没有AI模板感（发光机器人/粒子特效/全息投影）？
- [ ] 输出路径正确（`output/articles/{date}/`）？

## 高级技巧

### 多封面A/B测试
同一篇文章生成2-3张不同版式的封面，选最好的：
```bash
# 版本A：Infographic Card
# 版本B：Split Comparison
# 版本C：Scene Realism
```

### 封面文字叠加
如果模型直接生成的文字不理想：
1. 先生成**纯背景图**（提示词末尾加 "no text, leave space for text overlay"）
2. 使用 **content-typography** skill 叠加标题文字（思源黑体/Noto Sans SC）
3. 确保 `~/clawd/skills/content-typography/SKILL.md` 存在

### 批量生成
多篇文章的封面可以并行生成（3个 exec 同时跑），每篇用不同内容提示词。

### 与发布 skill 的协作约定

1. 输出真实文件路径（不写死，由调用方传参）
2. 文件名可被文章元数据直接引用
3. 封面先在本地生成，再交给发布 skill 上传
4. 本 skill 负责：**生成正确封面** → 交给 `gzh-publisher-skill` / `xhs-publisher` / `douyin-smart-publish` 发布
