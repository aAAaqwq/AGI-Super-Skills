# 内容工厂流水线 v2 — 数据驱动 + 去AI味

## 流程（5步闭环）

### Step 1: 选题确认
CEO 确认选题 + 目标平台 + 调性要求

### Step 2: 实时数据调研（小research）
**必须使用搜索工具获取实时数据，禁止凭记忆编造。**

调研流程：
1. 用 `tavily` / `web-search` / `deep-research` skill 搜索最新信息
2. 搜索维度：
   - 最新产品/工具动态（如 Cursor 0.50, Claude Code, OpenClaw, Gemini 2.5）
   - 真实数据和统计（Stack Overflow Survey, GitHub Copilot 报告等）
   - 真实事件/新闻（带来源链接）
   - 社交媒体热议观点（Twitter/X, Reddit, 知乎）
3. 每条素材必须标注来源URL
4. 输出：`research_v2.md`（带来源的结构化素材）

### Step 3: 内容创作（小content）
基于 research_v2.md 写作，要求：
1. 读 `humanize-zh` skill 的去AI味方法论
2. 案例必须来自 research_v2.md 的真实素材
3. 数据必须有出处
4. 禁止使用：赋能、助力、值得一提、不言而喻、综上所述
5. 禁止"姐妹们""宝子们"等过度套路化称呼
6. 观点锋利，有争议性

### Step 4: CEO 审核
- AI味检查（自然度）
- 信息新鲜度（是否用了最新数据）
- 来源可信度
- 不通过 → 反馈给小content修改

### Step 5: 排版发布（小content / CEO）
- 用 `xiaohongshu-publish` skill 通过 browser 发布
- 或导出排版后人工发布

## 关键原则
- **无搜索不动笔** — 调研必须用搜索工具，不许凭记忆
- **无来源不引用** — 每个数据点和案例都要有出处
- **去AI味是硬指标** — 过不了自检不许提交
