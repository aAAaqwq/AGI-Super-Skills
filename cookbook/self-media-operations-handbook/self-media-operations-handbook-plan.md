# 《自媒体创作运营手册》编纂方案

> 整理自 Daniel CEO 指令 | 整理时间：2026-04-09 | 状态：✅ 方案完成

---

## 一、扫描结果汇总

### 扫描路径
- `~/clawd/skills/` — 主 skills 目录
- `~/.agents/skills/` — Agent 专属 skills
- `~/.openclaw/skills/` — OpenClaw 内置 skills

### 有效 Skill 统计（共 43 个）

| 类别 | 数量 | 总行数 |
|------|------|--------|
| 内容创作与排版 | 4 | ~1,250 |
| 小红书运营 | 4 | ~1,747 |
| 抖音/短视频 | 3 | ~432 |
| YouTube | 3 | ~834 |
| 视频制作全流程 | 14 | ~2,600 |
| 多平台分发 | 4 | ~1,080 |
| 流量增长 | 3 | ~683 |
| 数据分析与竞品 | 3 | ~571 |
| 广告投放 | 4 | ~616 |
| 写作与文案 | 3 | ~1,252 |

**注：部分目录存在但缺少 SKILL.md**（douyin-creator、content-distributor、content-factory、media-auto-publisher、wechat-channel、wechat-toolkit、wemp-operator、juejin-publisher-custom、zhihu-post-skill 等），其内容以 references/scripts 形式存在，需在编纂时决定是否补写 SKILL 或直接引用。

---

## 二、章节大纲

### 第 1 章 · 内容战略与选题
**（源头：怎么永远有东西可写）**

| 节 | 内容来源 Skill | 路径 | 行数 | 工作量 |
|----|--------------|------|------|--------|
| 1.1 选题竞争分析 | content-ops-toolkit | ~/.agents/skills/content-ops-toolkit/SKILL.md | 205 | 低 |
| 1.2 选题库构建 | prototype-prompt-generator | ~/.agents/skills/prototype-prompt-generator/SKILL.md | 497 | 中 |
| 1.3 创意头脑风暴 | brainstorming | ~/.agents/skills/brainstorming/SKILL.md | 164 | 低 |

**工作量预估：低**（主要是内容整合和重组）

---

### 第 2 章 · 封面与视觉设计
**（3秒定生死：决定点击率的核心视觉）**

| 节 | 内容来源 Skill | 路径 | 行数 | 工作量 |
|----|--------------|------|------|--------|
| 2.1 内容驱动封面生成 | content-cover-gen | ~/clawd/skills/content-cover-gen/SKILL.md | 278 | 低 |
| 2.2 封面字体排版优化 | content-typography | ~/clawd/skills/content-typography/SKILL.md | 319 | 低 |
| 2.3 配图决策流程 | content-illustration-strategy | ~/clawd/skills/content-illustration-strategy/SKILL.md | 208 | 低 |
| 2.4 AI 图像生成 | relay-image-gen | ~/.openclaw/skills/relay-image-gen/SKILL.md | 66 | 低 |
| 2.5 海报设计生成 | poster-design-generation | ~/.agents/skills/poster-design-generation/SKILL.md | 327 | 中 |

**工作量预估：低**（主要是格式调整，skills 已成熟）

---

### 第 3 章 · 小红书（小红书）运营
**（核心平台：种草 + 品牌 + 转化）**

| 节 | 内容来源 Skill | 路径 | 行数 | 工作量 |
|----|--------------|------|------|--------|
| 3.1 爆款文案创作 | xiaohongshu-viral-copy | ~/clawd/skills/xiaohongshu-viral-copy/SKILL.md | 89 | 低 |
| 3.2 账号增长策略 | xiaohongshu-growth | ~/.agents/skills/xiaohongshu-growth/SKILL.md | 134 | 低 |
| 3.3 红书图文系列生成 | baoyu-xhs-images | ~/.agents/skills/baoyu-xhs-images/SKILL.md | 494 | 中 |
| 3.4 红书 CLI 运营工具 | redbook | ~/.agents/skills/redbook/SKILL.md | 1030 | 中 |
| 3.5 每日内容生产流 | daily-xhs-content | ~/clawd/skills/daily-xhs-content/SKILL.md | 105 | 低 |
| 3.6 公众号图文排版 | （参考 content-typography + content-cover-gen） | — | — | 低 |
| 3.7 掘金发文 | juejin-publisher-custom | ~/clawd/skills/juejin-publisher-custom/ | 无 SKILL.md | 高* |

**工作量预估：中**（redbook 1030行 + baoyu 需深度整合；juejin 无 SKILL.md 需新建）

---

### 第 4 章 · 抖音 & 短视频运营
**（流量最大：娱乐内容 + 知识内容双线）**

| 节 | 内容来源 Skill | 路径 | 行数 | 工作量 |
|----|--------------|------|------|--------|
| 4.1 TikTok 增长公式 | tiktok-growth | ~/clawd/skills/tiktok-growth/SKILL.md | 208 | 低 |
| 4.2 抖音账号视频分析 | douyin-video-analyst | ~/clawd/skills/douyin-video-analyst/SKILL.md | 131 | 低 |
| 4.3 每日内容生产流 | daily-douyin-content | ~/clawd/skills/daily-douyin-content/SKILL.md | 93 | 低 |
| 4.4 抖音创作者工作流 | douyin-creator | ~/clawd/skills/douyin-creator/ | 无 SKILL.md | 高* |
| 4.5 短视频脚本营销 | video-marketing | ~/.agents/skills/video-marketing/SKILL.md | 83 | 低 |

**工作量预估：中**（douyin-creator 缺 SKILL.md，需补充或重构）

---

### 第 5 章 · YouTube 长视频运营
**（深度内容：搜索引擎流量持续）**

| 节 | 内容来源 Skill | 路径 | 行数 | 工作量 |
|----|--------------|------|------|--------|
| 5.1 YouTube 完整视频生成 | youtube-factory | ~/clawd/skills/youtube-factory/SKILL.md | 164 | 低 |
| 5.2 YouTube 知识提取 | youtube-knowledge-extractor | ~/clawd/skills/youtube-knowledge-extractor/SKILL.md | 335 | 中 |
| 5.3 YouTube 视频多模态分析 | youtube-video-analyzer | ~/clawd/skills/youtube-video-analyzer/SKILL.md | 335 | 中 |

**工作量预估：中**（3个 skills 内容重叠，合并工作量大）

---

### 第 6 章 · 视频制作全流程
**（从剧本到成片：AI 驱动工业化生产）**

| 节 | 内容来源 Skill | 路径 | 行数 | 工作量 |
|----|--------------|------|------|--------|
| 6.1 AI 视频生成全流程 | aigc-director | ~/clawd/skills/aigc-director/SKILL.md | 279 | 低 |
| 6.2 AI 视频脚本生成 | ai-video-gen | ~/clawd/skills/ai-video-gen/SKILL.md | 126 | 低 |
| 6.3 AI 数字人视频 | heygen-avatar-lite | ~/clawd/skills/heygen-avatar-lite/SKILL.md | 144 | 低 |
| 6.4 即梦数字人全流程 | jimeng-digital-human | ~/.openclaw/skills/jimeng-digital-human/SKILL.md | 370 | 中 |
| 6.5 即梦分镜脚本生成 | jimeng-storyboard | ~/.openclaw/skills/jimeng-storyboard/SKILL.md | 99 | 低 |
| 6.6 多片段视频合并发送 | video-merge-send | ~/.openclaw/skills/video-merge-send/SKILL.md | 73 | 低 |
| 6.7 视频字幕生成 | video-subtitles | ~/clawd/skills/video-subtitles/SKILL.md | 67 | 低 |
| 6.8 字幕烧录进视频 | video-caption-burner | ~/clawd/skills/video-caption-burner/SKILL.md | 53 | 低 |
| 6.9 视频转写工作流 | video-transcriber | ~/clawd/skills/video-transcriber/SKILL.md | 56 | 低 |
| 6.10 视频内容分析 | video-content-analyzer | ~/clawd/skills/video-content-analyzer/SKILL.md | 328 | 中 |
| 6.11 FFmpeg 专业剪辑 | ffmpeg-video-editor | ~/clawd/skills/ffmpeg-video-editor/SKILL.md | 393 | 中 |
| 6.12 自动建筑视频剪辑 | arch-video-cut | ~/clawd/skills/arch-video-cut/SKILL.md | 246 | 中 |
| 6.13 展示视频构建 | showcase-video-builder | ~/clawd/skills/showcase-video-builder/SKILL.md | 95 | 低 |
| 6.14 Relay 视频生成 | relay-video-gen | ~/.openclaw/skills/relay-video-gen/SKILL.md | 61 | 低 |
| 6.15 多模态内容生成 | multimodal-gen | ~/clawd/skills/multimodal-gen/SKILL.md | 134 | 低 |
| 6.16 MiniMax TTS 语音 | minimax-tts | ~/clawd/skills/minimax-tts/SKILL.md | 58 | 低 |

**工作量预估：高**（14个skills，部分内容重叠需合并去重，aigc-director 和 jimeng-digital-human 为主干）

---

### 第 7 章 · 多平台内容分发
**（一鱼多吃：同一内容多平台适配）**

| 节 | 内容来源 Skill | 路径 | 行数 | 工作量 |
|----|--------------|------|------|--------|
| 7.1 内容再利用引擎 | content-repurposing-engine | ~/clawd/skills/content-repurposing-engine/SKILL.md | 40 | 低 |
| 7.2 内容分发自动化 | content-distributor | ~/clawd/skills/content-distributor/ | 无 SKILL.md | 高* |
| 7.3 多平台自动发布 | media-auto-publisher | ~/clawd/skills/media-auto-publisher/ | 无 SKILL.md | 高* |
| 7.4 公众号每日内容 | daily-gzh-content | ~/clawd/skills/daily-gzh-content/SKILL.md | 103 | 低 |

**工作量预估：高**（content-distributor 和 media-auto-publisher 缺 SKILL.md，需新建）

---

### 第 8 章 · 流量获取与增长运营
**（突破增长天花板：从 0 到规模化）**

| 节 | 内容来源 Skill | 路径 | 行数 | 工作量 |
|----|--------------|------|------|--------|
| 8.1 外部流量获取 | traffic-acquisition | ~/.agents/skills/traffic-acquisition/SKILL.md | 483 | 中 |
| 8.2 TikTok/INS 有机增长 | postbridge-social-growth | ~/.agents/skills/postbridge-social-growth/SKILL.md | 105 | 低 |
| 8.3 增长运营方法论 | content-ops-toolkit（复用 Ch1） | ~/.agents/skills/content-ops-toolkit/SKILL.md | — | 低 |

**工作量预估：中**（主要是内容整合）

---

### 第 9 章 · 数据分析与竞品研究
**（用数据驱动决策：不靠感觉靠数字）**

| 节 | 内容来源 Skill | 路径 | 行数 | 工作量 |
|----|--------------|------|------|--------|
| 9.1 竞品分析框架 | competitive-analysis | ~/.agents/skills/competitive-analysis/SKILL.md | 71 | 低 |
| 9.2 电商竞品监控 | ecommerce-competitor-analyzer | ~/.agents/skills/ecommerce-competitor-analyzer/SKILL.md | 347 | 中 |
| 9.3 Google Analytics | google-analytics | ~/.agents/skills/google-analytics/SKILL.md | 153 | 低 |

**工作量预估：低-中**

---

### 第 10 章 · 广告投放（付费放大）
**（精准流量：让好内容被更多人看到）**

| 节 | 内容来源 Skill | 路径 | 行数 | 工作量 |
|----|--------------|------|------|--------|
| 10.1 全平台广告审计 | ads | ~/.agents/skills/ads/SKILL.md | 157 | 低 |
| 10.2 Google Ads 管理 | google-ads | ~/.agents/skills/google-ads/SKILL.md | 191 | 低 |
| 10.3 Amazon Ads | skill-amazon-ads | ~/.agents/skills/skill-amazon-ads/SKILL.md | 73 | 低 |
| 10.4 Meta/Facebook Ads | ads-agent | ~/.agents/skills/ads-agent/SKILL.md | 195 | 低 |

**工作量预估：低**（主要是内容整合）

---

### 第 11 章 · 内容质量保障
**（让 AI 内容读起来像人写的）**

| 节 | 内容来源 Skill | 路径 | 行数 | 工作量 |
|----|--------------|------|------|--------|
| 11.1 去除 AI 写作痕迹 | humanizer | ~/.agents/skills/humanizer/SKILL.md | 438 | 中 |
| 11.2 专业写作技巧 | writing-skills | ~/.agents/skills/writing-skills/SKILL.md | 655 | 中 |
| 11.3 图片视觉分析 | image-vision | ~/clawd/skills/image-vision/SKILL.md | 99 | 低 |

**工作量预估：中**（humanizer 和 writing-skills 内容较深，需理解后重写）

---

## 三、工作量汇总

| 章节 | 涉及 Skills 数 | 合并工作量 |
|------|--------------|-----------|
| Ch1 · 内容战略与选题 | 3 | 低 |
| Ch2 · 封面与视觉设计 | 5 | 低 |
| Ch3 · 小红书运营 | 6（含1个缺文档） | 中 |
| Ch4 · 抖音 & 短视频 | 5（含2个缺文档） | 中-高 |
| Ch5 · YouTube | 3（内容重叠） | 中 |
| Ch6 · 视频制作全流程 | 16（部分重叠） | 高 |
| Ch7 · 多平台分发 | 4（含2个缺文档） | 高 |
| Ch8 · 流量获取 | 3 | 中 |
| Ch9 · 数据分析 | 3 | 低-中 |
| Ch10 · 广告投放 | 4 | 低 |
| Ch11 · 内容质量保障 | 3 | 中 |

### 瓶颈识别
1. **缺 SKILL.md 的目录**（共 ~8 个）：douyin-creator、content-distributor、media-auto-publisher、wechat-channel、wechat-toolkit、wemp-operator、juejin-publisher-custom、zhihu-post-skill。这些目录有 scripts/references 但没有标准 SKILL.md 入口，需要决定是补写 SKILL.md 还是跳过。
2. **重复 Skills**：`redbook`（~/.agents + ~/.openclaw）、`writing-skills`、`video-marketing`、`video-generation`、`traffic-acquisition`、`postbridge-social-growth`、`aigc-director` 均有多份，需要去重。
3. **内容重叠**：`youtube-knowledge-extractor` 与 `youtube-video-analyzer` 完全相同（均为335行），只保留一个即可。

---

## 四、执行建议

### Phase 1：建骨架（工作量：低）
直接以现有 SKILL.md 为蓝本，按 11 章大纲创建书的目录结构和各章引言。

### Phase 2：填内容（工作量：高）
- 优先处理有 SKILL.md 的 skills（可直接引用）
- 对缺文档的目录：先判断其 scripts 是否完整，完整则补写 SKILL.md，不完整则降级为"参考"而非"主干"
- 合并重复 skills，删除冗余副本

### Phase 3：交叉引用 + 案例补全（工作量：中）
建立 skills 之间的互引关系，补充实操案例。

### 输出文件
- 主文件：`~/clawd/docs/self-media-operations-handbook/`
- 单文件版（便于阅读）：`~/clawd/docs/self-media-operations-handbook.md`
- 规划案：`~/clawd/docs/self-media-operations-handbook-plan.md`（本文）

---

## 五、推荐执行顺序

1. **先 Ch2 + Ch11**（视觉 + 文字质量，最独立）
2. **再 Ch3 + Ch4 + Ch5**（各平台运营，并行）
3. **再 Ch6**（视频全流程，最复杂，单独处理）
4. **再 Ch7**（分发，需先完成 Ch3-5）
5. **再 Ch1 + Ch8 + Ch9 + Ch10**（战略 + 流量 + 数据，并行）
6. **最后整体交叉引用**

---
*整理：daniel_pm_bot | 2026-04-09*
