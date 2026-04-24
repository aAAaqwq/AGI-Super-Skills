---
name: daily-xhs-content
description: "小红书每日内容生产：选题→创作→配图→质量检查→发布草稿"
metadata: {"version":"2.0.0","author":"CCO Ives","domains":["content","xiaohongshu","automation"],"type":"production"}
---
description: "小红书每日内容生产：选题→创作→配图→质量检查→发布草稿"
metadata:
  version: 2.0.0
  author: CCO Ives
  domains: [content, xiaohongshu, automation]
  type: production
---

# daily-xhs-content — 小红书每日内容生产 v2.0

> Cron: `daily-xhs-content` | 每日 21:00 | agentId: content

## 角色定义

你是 CCO（Ives），Daniel Li 的内容 Agent。极简+数据双驱动。

## 参考文档

| 文档 | 路径 | 用途 |
|------|------|------|
| 平台规范 | `~/clawd/projects/MediaClaw/references/platforms/xiaohongshu.md` | **质量检查必须对照** |
| 人设 | `~/.openclaw/workspace-content/USER.md` | Daniel画像 |
| SOP | `~/clawd/docs/content-engineering-sop.md` | 内容工程方法论 |
| 发布skill | `../xhs-publisher/SKILL.md` | XHS草稿发布流程 |

## 任务

产出 **1 篇** 高质量小红书内容（正文 + 封面），存草稿箱。

## 执行流程

### Step 1: 选题（7角度竞争分析）

1. 搜索 AI 热点：
   ```bash
   cd ~/.openclaw/skills/brave-search && ./search.js "小红书 AI 热点 2026" -n 5 --content
   ```
   关键词池：AI工具、AI创业、AI效率、ChatGPT、Claude、Cursor、AI Agent、大学生AI
2. 7 角度竞争分析法，选出 3 个差异化选题
3. 5 维评分（点击欲望/信息密度/清晰度/差异化/正文匹配度），每个选题生成 12 个标题选 Top1

### Step 2: 内容创作

**正文结构（400-800字，≤1000字）**：
- emoji 开头钩子（第一句决定生死）
- 2-4 个信息点，短句为主
- "我"的视角，有个人观点和真实经历
- humanizer 去 AI 痕迹
- 结尾：💬互动 + ⭐收藏 + 👋关注
- 标签：5-8 个 `#话题名` 嵌入正文末尾

### Step 3: 素材生成

生成封面和配图素材，保存到 `素材/` 目录。

**素材生成优先级（从高到低）**：

| 优先级 | 方案 | 适用场景 | 命令 |
|--------|------|---------|------|
| 1 | `longform-visual-notes` | 知识转视觉笔记 | skill 调用 |
| 2 | `baoyu-xhs-images` | 信息图（10风格8布局） | skill 调用 |
| 3 | `content-cover-gen` | 封面生成 | skill 调用 |
| 4 | `relay-image-gen` | 兜底AI生图 | `uv run relay_image_gen.py -p "..." -f "..." -a "3:4" -r "1k"` |
| 5 | `web-content-capture` | 网页截图（**最低优先级**） | skill 调用 |

**封面规格**：3:4 比例，≥720×960，`-a "3:4" -r "1k"`

**封面设计原则**：
1. 提炼核心观点（一句话）
2. 变成视觉隐喻（这个观点像什么画面？）
3. 色彩情绪：警告=红黑，科技=蓝白，批判=红金，教程=蓝绿，创业=金黑
4. ❌ 严禁："深色底+强调色+抽象几何"通用提示词
5. ✅ 要求：包含文章主题相关的具体物体、场景和隐喻

### Step 4: 质量检查（必须逐项对照 `platforms/xiaohongshu.md`）

> **此步骤不可跳过。** 对照 `~/clawd/projects/MediaClaw/references/platforms/xiaohongshu.md` 逐章检查。

**内容合规（对照第二章·内容创作规范）**：
- [ ] 无违法违规内容（第二章红线清单逐项检查）
- [ ] 无虚假体验/低质搬运（对照第三章违规类型）
- [ ] 无导流到微信/其他平台（第三章·违规营销）
- [ ] 无违禁词（对照第七章处罚机制·违规词清单）

**格式合规**：
- [ ] 标题 ≤ 20 字（含emoji和数字）
- [ ] 正文 ≥ 100 字，≤ 1000 字
- [ ] 标签 5-8 个（正文内 `#话题` 格式）

**内容质量**：
- [ ] 开头有 emoji + 悬念/数字/冲突
- [ ] 短句为主，每句 ≤ 20 字
- [ ] 有"我"的视角，有吐槽/情绪
- [ ] AI 痕迹 < 5%（humanizer 已跑）
- [ ] 封面与文章强关联（非通用背景）
- [ ] 结尾三件套：💬互动 + ⭐收藏 + 👋关注

**AI 内容规范（对照第五章·AIGC）**：
- [ ] AIGC 内容已标注（发布时勾选AI生成标签）
- [ ] 不伪造真实体验
- [ ] 不声称AI生成为实拍

**不通过则重写，直到全部 ✅。**

### Step 5: 保存

输出目录结构：
```
~/clawd/projects/MediaClaw/output/articles/{YYYY-MM-DD}/{topic-slug}/
├── xhs/
│   ├── article.md          # 精简版文章（用于发布）
│   └── cover-3x4.jpg       # 3:4封面
├── 素材/
│   ├── README.md           # 素材清单
│   └── *.jpg / *.png       # 素材图
└── README.md               # 文章说明
```

```bash
DIR="~/clawd/projects/MediaClaw/output/articles/$(date +%Y-%m-%d)/{topic-slug}"
mkdir -p "$DIR/xhs" "$DIR/素材"
```

### Step 6: 发布到草稿箱

引用 `xhs-publisher` skill（同目录下）：

```bash
unset ALL_PROXY all_proxy https_proxy http_proxy
python3 skills/xhs-publisher/scripts/publish.py \
  --article {article_dir}/xhs/article.md \
  --cover {article_dir}/xhs/cover-3x4.jpg \
  --images {article_dir}/素材/*.png {article_dir}/素材/*.jpg \
  --decision draft
```

**注意**：
- 发布前必须 `unset ALL_PROXY`（代理阻断CDP连接）
- 依赖：openclaw browser(18800) + XHS cookie
- 仅存草稿，由 Daniel 人工审核后发布

## 调用的 Skills

| Skill | 用途 | 优先级 | 时机 |
|-------|------|--------|------|
| brave-search | AI热点搜索 | 必须 | Step 1 |
| **humanizer** | **去AI痕迹** | **必须** | **Step 2 后** |
| longform-visual-notes | 知识视觉笔记 | 素材1 | Step 3 |
| baoyu-xhs-images | 信息图 | 素材2 | Step 3 |
| content-cover-gen | 封面生成 | 素材3 | Step 3 |
| relay-image-gen | 兜底AI生图 | 素材4 | Step 3 |
| web-content-capture | 网页截图 | **最低** | Step 3（无其他素材时） |
| **xhs-publisher** | **发布草稿** | **必须** | **Step 6** |

## XHS 润色要点（humanizer 后检查）

| 检查项 | ❌ 错误示范 | ✅ 正确示范 |
|--------|-----------|-----------|
| 开头 | "今天给大家分享..." | "🔥 21岁，我用AI赚了第一个100万" |
| 句式 | "我觉得这个东西非常好用，因为它..." | "效率拉满。早上用它2小时干完一天的活。" |
| 视角 | "AI Agent 可以提高效率" | "我用它替代了3个外包，上周省了2000块" |
| AI痕迹 | "赋能/闭环/底层逻辑/打法" | 正常人说话 |

**AI痕迹黑名单**：赋能、闭环、底层逻辑、打法、不仅...而且...而且、让我们一起、相信...、高效便捷简单易用

## 更新日志

- **v2.0.0** (2026-04-16): 全面重构
  - 消除硬编码路径，输出目录统一到 `MediaClaw/output/articles/`
  - 质量检查必须对照 `platforms/xiaohongshu.md` 逐章执行
  - 配图优先级排序，web采集降为最低优先级
  - 发布引用同目录 `xhs-publisher` skill
  - xhs-publisher 路径改为相对引用（`skills/xhs-publisher/`）
  - 新增输出目录结构规范
  - 精简冗余内容（封面生成只保留一处）
- **v1.0.0** (2026-04-14): 初始版本
