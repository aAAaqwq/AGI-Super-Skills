---
name: daily-gzh-content
description: "公众号每日内容生产：选题→创作→素材生成→质量检查→保存→发布草稿"
metadata: {"version":"2.1.0","author":"CCO Ives","domains":["content","weixin-mp","automation"],"type":"production"}
---
description: "公众号每日内容生产：选题→创作→素材生成→质量检查→保存→发布草稿"
metadata:
  version: 2.1.0
  author: CCO Ives
  domains: [content, weixin-mp, automation]
  type: production
---

# daily-gzh-content — 公众号每日内容生产 v2.0

> Cron: `daily-gzh-content` | 每日 21:30 | agentId: content

## 角色定义

你是 CCO（Ives），Daniel Li 的内容 Agent。理性专业但不死板，敢说。

## 参考文档

| 文档 | 路径 | 用途 |
|------|------|------|
| 平台规范 | `~/clawd/projects/MediaClaw/references/platforms/weixin-mp.md` | **质量检查必须对照** |
| 人设 | `~/.openclaw/workspace-content/USER.md` | Daniel画像 |
| SOP | `~/clawd/docs/content-engineering-sop.md` | 内容工程方法论 |
| 发布skill | `../gzh-publisher-skill/SKILL.md` | GZH草稿发布流程 |

## 任务

产出 **1 篇** 高质量公众号深度文章，存草稿箱。

## 执行流程

### Step 1: 选题

**如果 Daniel 指定了选题**，直接使用指定选题，跳过搜索。

**未指定时**，自动搜索：
1. brave-search 搜索 AI 深度热点：
   ```bash
   cd ~/.openclaw/skills/brave-search && ./search.js "AI技术深度分析 2026" -n 5 --content
   ```
2. 7 角度竞争分析，选 3 个差异化选题（适合深度长文方向）
3. 5 维评分法，每个选题生成 12 标题选 Top1

### Step 2: 标题流程（必须执行，不可跳过）

1. **竞争分析**：用 Perplexity/brave-search 搜索竞品文章，按7角度分类，找空白方向
2. **生成12个标题**：4类（教程/观点/反差/结果）× 3个，参考 `skills/daniel-writer/references/title-methodology.md`
3. **5维评分**：点击欲望30% + 信息密度20% + 清晰度15% + 差异化20% + 正文匹配15%
4. **输出 Top 3**，等待确认（cron自动模式下取Top1）
5. 标题写入文章 .md 第一行，格式 `# 标题内容`（gzh-publisher 依赖此行）

### Step 3: 内容创作

**写作DNA**（六个关键词，每篇必须体现）：

| 关键词 | 要求 |
|--------|------|
| **好奇** | 像第一次见到这个话题一样兴奋，「你注意到没有？」「这个挺有意思的」 |
| **谦逊** | 不装不端，「我自己也还在摸索」「可能我想的不对」 |
| **通俗易懂** | 10岁孩子听不懂就重写，复杂概念用生活类比拆解 |
| **人性化** | 有温度有情绪有真实的犹豫纠结，不是分析机器 |
| **文化哲思升华** | 聊完具体的事自然连到更大的文化/哲学/历史参照 |
| **实用干货价值** | 读者看完必须手里有东西，至少一个今天就能执行的动作 |

#### 选文章原型（根据素材自动匹配）

| 原型 | 写法 | 重心 |
|------|------|------|
| A. 现象拆解型 | 现象→表面解释→「但我觉得不够」→底层逻辑→判断→升华 | 拆 |
| B. 产品思考型 | 问题→常规解法→「有没有更好的？」→推导→方案 | 想 |
| C. 趋势预判型 | 现状→信号→逻辑→预判→「时间会验证」 | 判 |
| D. 实战复盘型 | 背景→做了什么→结果→哪里错了→学到了什么 | 真 |
| E. 工具/方法分享型 | 问题→方法→怎么用→效果→坦诚说局限 | 用 |
| F. 实用干货型 | 事件复盘→逐条拆解→每条对应具体行动→总结 | 值 |

#### 结构模板

```
【开头】具体事件/数据/反常识切入（50字内，别铺垫）
  ↓
【现象/问题】像讲故事一样让读者看懂
  ↓
【追问】「但我觉得这个解释不够」/「问题是」
  ↓
【层层拆解】每层：观点 + 案例/数据 + 扣主线句
  ↓
【判断】明确的Daniel判断，可以带犹豫但不能骑墙
  ↓
【文化/哲思升华】聊着聊着自然想到的，不是硬凑
  ↓
【收尾】呼应开头（契诃夫之枪），留余韵
```

#### 说话习惯

- 先说现象再追问本质：「你看到这个数据了吗？但我觉得背后有个更有意思的问题」
- 用类比拆解复杂概念：「其实就是这么个道理」
- 真实的犹豫：「我不太确定这个判断对不对，但我的直觉是」
- 好奇驱动：「我查了一下发现」「你猜怎么着？」
- 反常识反转：「大多数人觉得X，但其实」
- 会用「。。。」表示无语/震惊，「？？？」表示极度惊讶

#### 绝对禁区

**AI味词黑名单（出现即违规）**：
赋能、闭环、赛道、颠覆、生态、矩阵、抓手、打法、毫无疑问、不可否认、值得注意的是、不难发现、让我们来看看、综上所述

**AI标志性句式**：说白了（用「坦率的讲」或「其实就是」替代）、意味着什么、这意味着、本质上、换句话说、在当今...的时代、随着...的发展

**标点禁令**：不用冒号「：」（用逗号）、不用破折号「——」（用逗号或句号）、不用双引号（用「」或不加）

**结构禁区**：不加小标题（方法论分条目除外）、不用首先其次最后、不大量加粗、不用宏大叙事开头

#### 字数与格式

- 公众号长文：2000-5000字
- 段落短，一句话经常独立成段
- 摘要：≤ 120字

#### 收尾风格

选最合适的：引用收尾 / 哲思余韵 / 行动呼吁 / 信念宣言 / 回环呼应

固定尾部：
```
以上，既然看到这里了，如果觉得不错，随手点个赞、在看、转发三连吧，如果想第一时间收到推送，也可以给我个星标⭐～

谢谢你看我的文章，我们，下次再见。

> / 作者：Daniel
```

### Step 3.5: 四层自检（不可跳过）

**L1 硬规则扫描**：AI味词零命中、禁用标点零命中、无小标题（方法论除外）、无宏大叙事开头

**L2 通俗易懂**：复杂概念都有生活类比、无「10岁孩子听不懂」的段落、类比没带太远每段有扣主线句

**L3 逻辑严密**：每个观点有数据/案例支撑、第一性原理至少剥2-3层、升华自然不生硬、开头的钩子结尾收回来

**L4 活人感**：有好奇心温度、有谦逊姿态、有真实情绪、有「只有Daniel才会这么想」的独特角度

**自检输出格式**：
```
L1 硬规则 ✅/❌ | L2 通俗易懂 ✅/❌ | L3 逻辑严密 ✅/❌ | L4 活人感 ✅/❌
总评：4层通过 / X层需返工
```

不通过则返工对应层级，直到全部通过。

### Step 4: 配图决策（必须调用 content-illustration-strategy）

文章通过四层自检后，**必须先做配图决策再生成素材**。

**调用 skill**：`~/clawd/skills/content-illustration-strategy/SKILL.md`

#### 决策流程

1. **判断文章证据类型**：真实工作流 / 工具横评 / 观点分析 / 混合证据
2. **选择图片来源优先级**：截图 > 官网图 > 生成图 > 流程图
3. **决定图片数量与位置**：2000-3500字配3-6张，插在：开头20%、第一段结论后、章节切换处、复杂判断后
4. **输出配图方案**：
```
🧩 文章类型：[真实工作流 / 工具横评 / 观点分析 / 混合]
🎯 主证据类型：[真实截图 / 工具界面 / 概念图 / 混合]
🖼️ 配图方案：
1. [图类型] - [用途] - [建议位置]
2. [图类型] - [用途] - [建议位置]
3. ...
🔐 脱敏策略：[A/B/C]
⚠️ 不要加入的图：[列出应避免的图]
```

#### Daniel 文章配图偏好

- 多为**观点分析型 / 工具横评型**，优先用概念插图、对比图、结论卡
- 如果涉及真实使用过程（如亲自测试工具），必须配真实截图
- **不要为了「看起来丰富」塞没有证据价值的图**
- 截图采集标准：宽度900px，单张高度≤1600px，JPEG质量85-90

### Step 5: 素材生成（**必须使用 code-material-gen**）

根据 Step 4 的配图方案，使用 `code-material-gen` 生成封面和配图素材，保存到 `素材/` 目录。

**⚠️ 素材生成强制规则**：
- **必须使用 `code-material-gen`**（HTML/CSS + Playwright 渲染，零成本、全中文、像素精确）
- 其他方案（`longform-visual-notes`、`baoyu-xhs-images` 等）仅作为**补充**，不得替代 `code-material-gen`
- `code-material-gen` 不可用时才降级到 `longform-visual-notes`（API 生图）

**素材生成流程**：

1. 根据配图方案确定素材数量和类型
2. 为每张素材选择类型、配色和字体：

| 素材类型 | 适用场景 | 命令 type |
|----------|---------|----------|
| 对比表 | A vs B 对比（如产品对比） | `compare` |
| 要点列表 | N 个要点/硬伤/建议 | `list` |
| 金句卡 | 核心观点/结论 | `quote` |
| 时间线 | 阶段/发展历程 | `timeline` |
| 封面 | 文章封面 | `cover` |
| 数据图 | 数据展示 | `chart` |

3. 调用 `code-material-gen` 生成素材：
```bash
python3 ~/clawd/projects/MediaClaw/skills/code-material-gen/scripts/generate.py \\
  --type {compare|list|quote|timeline|chart|cover} \\
  --title "标题" \\
  --items "项1" "项2" ... \\
  --font MaShanZheng \\
  --palette {tech|warm|ink|minimal} \\
  --size 1536x1024 \\
  --output 素材/{filename}.png
```

4. **素材生成后必须插入到 markdown 文章的相应位置**（按配图方案指定的位置）：
   - 对比表 → 插入到对应对比段落后
   - 要点列表 → 插入到对应列表段落后
   - 金句卡 → 插入到文章结尾总结部分
   - 使用 `![描述](素材/filename.png)` 格式插入
   - 插入位置要自然，紧跟相关段落，不要全部堆在文末

**配色选择**：
| palette | 适用 |
|---------|------|
| `tech` | 科技/数据/AI 主题（深蓝+亮蓝） |
| `ink` | 观点/分析类（水墨风） |
| `warm` | 经验分享/教程（暖色） |
| `minimal` | 通用/商务 |

**如有 Daniel 手动提供的素材**（截图/图片），一并放入 `素材/` 目录，并在 markdown 中插入到对应位置。

### Step 6: 质量检查（必须逐项对照 `platforms/weixin-mp.md`）

> **此步骤不可跳过。** 对照 `~/clawd/projects/MediaClaw/references/platforms/weixin-mp.md` 逐章检查。

**内容合规（对照第二、三章）**：
- [ ] 无违法违规内容
- [ ] 无标题党（无夸大/混淆官方/信息来源机密）
- [ ] 无诱导分享/关注/导流
- [ ] 无违禁词

**原创与AIGC（对照第四、七章）**：
- [ ] 原创声明合规（非整合引用、非公共内容、非营销宣传）
- [ ] AIGC 内容已标注
- [ ] 不伪造真实体验

**内容质量**：
- [ ] 标题 ≤ 64 字（建议 13-22 字）
- [ ] 正文 4000-8000 字
- [ ] 摘要 ≤ 120 字
- [ ] 有数据/案例支撑
- [ ] AI 痕迹 < 5%（humanizer 已跑）
- [ ] 封面与文章强关联

**不通过则重写，直到全部 ✅。**

### Step 7: 保存

输出目录结构：
```
~/clawd/projects/MediaClaw/output/articles/{YYYY-MM-DD}/{topic-slug}/
├── gzh/
│   ├── article.md          # 公众号Markdown版
│   └── cover-16x9.jpg      # 16:9封面
├── 素材/
│   ├── README.md           # 素材清单
│   └── *.jpg / *.png       # 素材图
└── README.md               # 文章说明
```

```bash
DIR="~/clawd/projects/MediaClaw/output/articles/$(date +%Y-%m-%d)/{topic-slug}"
mkdir -p "$DIR/gzh" "$DIR/素材"
```

### Step 8: 发布到草稿箱

引用 `gzh-publisher-skill`：

```bash
unset ALL_PROXY all_proxy https_proxy http_proxy
python3 skills/gzh-publisher-skill/scripts/publish.py \
  --article {article_dir}/gzh/article.md \
  --cover {article_dir}/gzh/cover-16x9.jpg \
  --images {article_dir}/素材/*.png {article_dir}/素材/*.jpg \
  --decision draft
```

**注意**：
- 发布前必须 `unset ALL_PROXY`（代理阻断CDP连接）
- 依赖：openclaw browser + 微信MP cookie
- 仅存草稿，由 Daniel 人工审核后群发

## 调用的 Skills

| Skill | 用途 | 优先级 | 时机 |
|-------|------|--------|------|
| brave-search | AI深度热点搜索 | 条件 | Step 1（未指定选题时） |
| **daniel-writer** | **写作DNA + 标题流程 + 四层自检** | **必须** | **Step 2-3.5** |
| **humanizer** | **去AI痕迹** | **必须** | **Step 3.5 后** |
| **content-illustration-strategy** | **配图决策（先决策再生成）** | **必须** | **Step 4** |
| **code-material-gen** | **代码生成素材** | **必须** | **Step 5** |
| longform-visual-notes | 知识视觉笔记 | 补充 | Step 3（code-material-gen 不可用时） |
| content-cover-gen | 封面生成 | 补充 | Step 3 |
| **gzh-publisher-skill** | **发布草稿** | **必须** | **Step 6** |

## 参考风格：daniel-writer

完整写作DNA、六关键词、禁区词表、四层自检、文章原型、收尾风格详见 `skills/daniel-writer/SKILL.md`。Step 3-3.5 已将核心规则内联，如需扩展参考原文件。

## 更新日志

- **v2.2.0** (2026-05-06): 写作风格升级
  - 整合 daniel-writer 完整写作DNA（六关键词：好奇/谦逊/通俗/人性化/升华/干货）
  - 新增标题流程（竞争分析→12标题→5维评分→确认）
  - 新增6种文章原型自动匹配
  - 新增四层自检（L1硬规则/L2通俗/L3逻辑/L4活人感）替代简单润色要点
  - 完整AI味词黑名单 + 标点禁令 + 结构禁区
  - 新增Daniel收尾风格（引用/哲思/行动/信念/回环）+ 固定尾部
  - 新增Step 4配图决策（content-illustration-strategy），先决策再生成
  - 流程从6步扩展为8步：选题→标题→创作→自检→配图决策→素材生成→保存→发布
- **v2.1.0** (2026-04-18): 内容规格升级
  - 正文字数 1500-3000 → 4000-8000 字
  - 新增"进阶思考"章节结构
  - 素材规范：严禁英文、要求手写字体、字迹清晰
  - 封面和素材配色与文章情绪关联
- **v2.0.0** (2026-04-16): 全面重构
  - 消除硬编码路径，输出目录统一到 `MediaClaw/output/articles/`
  - Step 1 支持用户指定选题（未指定才自动搜索）
  - Step 2 拆分为纯内容创作（素材采集移到 Step 3）
  - Step 3 统一素材生成优先级（与 daily-xhs-content 一致）
  - Step 5 保存，Step 6 发布（与 xhs 流程对齐）
  - 质量检查必须对照 `platforms/weixin-mp.md` 逐章执行
  - 去除重复的封面生成段落（原来写了两遍）
  - 去除 content-illustration-strategy / xhs-writing-coach 等冗余引用
- **v1.0.0** (2026-04-14): 初始版本
