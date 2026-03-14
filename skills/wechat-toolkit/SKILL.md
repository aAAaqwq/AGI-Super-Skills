---
name: wechat-toolkit
description: "微信公众号一站式工具包 — 集成文章搜索、文章下载、AI洗稿改写、公众号发布四大功能。当用户需要搜索/下载/改写/发布微信公众号文章时使用。"
metadata:
  {
    "openclaw":
      {
        "emoji": "📦",
        "requires": { "bins": ["node"] },
        "platforms": ["macos", "linux", "windows"],
        "install":
          [
            {
              "id": "node-brew",
              "kind": "brew",
              "formula": "node",
              "bins": ["node"],
              "label": "Install Node.js (brew)",
            },
          ],
      },
  }
---

# 📦 微信公众号工具包 (wechat-toolkit)

集成四大功能模块：**搜索 → 下载 → 洗稿 → 发布**，覆盖公众号内容创作全流程。

---

## 模块一览

| 模块 | 功能 | 触发词示例 |
|------|------|-----------|
| 🔍 搜索 | 按关键词搜索公众号文章 | "搜XX的公众号文章" |
| 📰 下载 | 下载文章内容/图片/视频 | "下载这篇公众号文章" |
| ✍️ 洗稿 | AI去痕迹+原创改写 | "帮我洗稿/改写这篇文章" |
| 📱 发布 | 发布Markdown到草稿箱 | "发布到公众号" |

---

# 🔍 模块一：文章搜索

通过搜狗微信搜索获取公众号文章列表，支持抓取正文。

## 首次安装依赖

```bash
npm install -g cheerio
```

## 使用方法

```bash
# 基础搜索
node {baseDir}/scripts/search/search_wechat.js "关键词"

# 指定数量
node {baseDir}/scripts/search/search_wechat.js "关键词" -n 15

# 保存到文件
node {baseDir}/scripts/search/search_wechat.js "关键词" -n 20 -o result.json

# 解析真实链接
node {baseDir}/scripts/search/search_wechat.js "关键词" -n 5 -r

# 抓取文章正文（自动启用 -r）
node {baseDir}/scripts/search/search_wechat.js "关键词" -n 5 -c
```

### 参数说明
- `query`：搜索关键词（必填）
- `-n, --num`：返回数量（默认 10，最大 50）
- `-o, --output`：输出 JSON 文件路径
- `-r, --resolve-url`：解析微信文章真实链接
- `-c, --fetch-content`：抓取文章正文内容（自动启用 -r）

### 输出字段
- 文章标题、地址、概要、发布时间、来源公众号
- `content`：正文内容（使用 -c 时）
- `word_count`：字数统计（使用 -c 时）

---

# 📰 模块二：文章下载

输入公众号文章链接，自动下载内容（Markdown+HTML）、配图和视频。

## 首次安装依赖

```bash
cd {baseDir}/scripts/downloader && npm install
```

## 下载前：确认保存位置

```bash
# 查看当前配置
node {baseDir}/scripts/downloader/download.js --show-config

# 设置默认下载路径（仅需一次）
node {baseDir}/scripts/downloader/download.js --set-output ~/Downloads/wechat-articles
```

- `"isDefault": true` → 尚未配置，需询问用户
- `"isDefault": false` → 已配置，告知用户当前路径

## 下载文章

```bash
# 使用默认路径
node {baseDir}/scripts/downloader/download.js "<文章URL>"

# 临时指定路径
node {baseDir}/scripts/downloader/download.js "<文章URL>" --output <临时目录>

# 跳过图片/视频
node {baseDir}/scripts/downloader/download.js "<文章URL>" --no-image
node {baseDir}/scripts/downloader/download.js "<文章URL>" --no-video
```

### 输出结构
```
<下载目录>/<文章标题>/
├── content/article.html      # 完整 HTML
├── metadata.json              # 标题、作者、时间等
├── images/                    # 所有配图
└── videos/                    # 所有视频/音频
```

### 前置要求
- Node.js ≥ 18、Google Chrome、`npm install`（首次）

---

# ✍️ 模块三：文章洗稿与改写

将文章改写为自然、原创的风格，去除 AI 写作痕迹，提升原创度。

## 触发词
- "帮我洗稿这篇文章"
- "改写成原创"
- "降低查重率"
- "去掉 AI 味"

## 洗稿工作流

### 标准洗稿流程

1. **获取原文** — 通过搜索（-c 抓正文）或下载获得原文
2. **分析结构** — 识别文章类型、核心论点、段落层次
3. **深度改写** — 按以下策略执行改写
4. **添加 frontmatter** — 补充 title + cover
5. **发布** — 推送到公众号草稿箱

### 改写策略

#### A. 结构重组（降重核心）
- **段落重排**：调整段落顺序，打乱原文结构
- **段落拆合**：将长段拆为短段，或合并碎片段落
- **叙事角度转换**：时间线 ↔ 问题导向 ↔ 对比分析 ↔ 故事引入
- **论据重组**：保留核心论据，改变展开方式

#### B. 语言改写（去 AI 痕迹）
- **删除意义膨胀句**："标志性"、"里程碑"、"深远影响" → 替换为具体事实
- **去虚假权威**："专家认为"、"业内普遍认为" → 写明来源或删除
- **去伪深度动词**："提升能力"、"赋能"、"推动进程" → 改为具体动作
- **去广告语气**："卓越"、"极致体验"、"全方位" → 客观描述
- **去 AI 高频词**：赋能、闭环、生态、抓手、底层逻辑、范式、沉淀、势能
- **去填充短语**：事实上、值得注意的是、总体来说、不难发现
- **去空洞结尾**："未来可期"、"值得期待" → 实际结论或行动项

#### C. 标题改写
为每篇文章生成 3-5 个备选标题，涵盖：
- **疑问型**：用问题引发好奇（"为什么XX还在用这种方法？"）
- **数字型**：用数字增强可信度（"3个被忽略的XX技巧"）
- **悬念型**：制造信息差（"XX的真相，90%的人不知道"）
- **痛点型**：戳中读者痛点（"别再XX了，试试这个方法"）

#### D. 开头改写
将原文开头转换为以下风格之一：
- **故事引入**：用一个小故事或场景切入
- **数据引入**：用震撼数据开头
- **痛点引入**：直击读者困扰
- **反问引入**：抛出反直觉问题

#### E. SEO 优化（可选）
- 在标题和首段自然植入核心关键词
- 在小标题中分布长尾关键词
- 控制关键词密度（2%-5%），保持自然可读

### AI 痕迹识别清单

改写完成后，逐项检查：

| # | 检查项 | 处理方式 |
|---|--------|---------|
| 1 | 意义膨胀句 | 替换为具体事实 |
| 2 | 虚假权威引用 | 写明来源或删除 |
| 3 | 伪深度动词 | 改为具体动作 |
| 4 | 广告语气 | 客观描述 |
| 5 | 模板段落（挑战→机遇→展望） | 删除模板，保留结论 |
| 6 | AI 高频词密集出现 | 替换为日常用语 |
| 7 | 负向并列滥用（不仅…而且…） | 直接表达 |
| 8 | 三段式强拆 | 保留重点，删填充项 |
| 9 | 同义词机械轮换 | 同一概念固定用词 |
| 10 | 破折号滥用 | 改为句号或逗号 |
| 11 | 加粗强调滥用 | 去掉不必要强调 |
| 12 | 列表模板（**X：**…） | 合并为自然段 |
| 13 | 概念堆砌标题 | 改为口语化标题 |
| 14 | Emoji 泛滥 | 除非指定风格，默认删除 |
| 15 | 聊天语残留 | 删除 |
| 16 | 知识截止声明 | 删除 |
| 17 | 过度讨好语气 | 客观回应 |
| 18 | 填充短语 | 删除 |
| 19 | 过度模糊（可能会、或许） | 改为条件判断 |
| 20 | 空洞结尾 | 改为实际结论 |
| 21 | 假区间表达（从…到…） | 列举具体事实 |

### 输出格式

1. **改写后全文**（Markdown 格式，含 frontmatter）
2. **备选标题**（3-5 个）
3. **修改说明**（可选，简要列出主要改动）

### 判断标准

改写成功的标志：
- ✅ 读起来像真人写的，能直接朗读不拗口
- ✅ 没有空洞句、模板段、"像 AI" 的气味
- ✅ 信息密度高，每句话都有具体内容
- ✅ 结构与原文明显不同
- ✅ 保持原文核心信息完整性

---

# 📱 模块四：文章发布

一键发布 Markdown 到微信公众号草稿箱，基于 wenyan-cli。

## 首次安装

```bash
npm install -g @wenyan-md/cli
```

## 配置 API 凭证

确保环境变量已设置（或在 TOOLS.md 中配置）：
```bash
export WECHAT_APP_ID=your_wechat_app_id
export WECHAT_APP_SECRET=your_wechat_app_secret
```

**重要：** IP 必须在微信公众号后台白名单中！

## Markdown 格式要求

文件顶部**必须**包含完整 frontmatter：

```markdown
---
title: 文章标题（必填！）
cover: https://example.com/cover.jpg  # 封面图（必填！）
---

# 正文...
```

⚠️ `title` 和 `cover` **缺一不可**，否则报错。

**⚠️ 图片路径必须使用绝对路径**，避免 wenyan 路径解析问题。包括 cover 和正文中的所有图片引用：
```markdown
cover: /Users/minruiqing/photos/cover.jpg        # ✅ 绝对路径
cover: ./assets/cover.jpg                         # ❌ 相对路径可能出错

![配图](/Users/minruiqing/photos/image.jpg)       # ✅ 绝对路径
![配图](./images/photo.jpg)                       # ❌ 相对路径可能出错
```

## 配图生成

发布前，**主动询问用户是否需要生成配图**：

> 📸 文章准备就绪！需要我帮你生成配图吗？
> - 封面图（cover，建议 1080×864）
> - 正文插图（根据段落主题生成）
> - 不需要，直接发布

**如果用户需要配图：**
1. 根据文章标题和内容，生成合适的图片描述 prompt
2. 调用用户提供的**生图 skill**（如 doubao-image、openai-image-gen 等）生成图片
3. 将生成的图片保存到文章目录，使用**绝对路径**引用
4. 封面图设置到 frontmatter 的 `cover` 字段
5. 正文插图在合适位置插入 `![描述](绝对路径)`

**prompt 建议：**
- 封面图：与标题强相关，简洁有冲击力，适合小尺寸预览
- 正文插图：与对应段落内容一致，辅助理解

## 发布方式

```bash
# 方式 1: 使用 publish.js
node {baseDir}/scripts/publisher/publish.js /path/to/article.md

# 方式 2: 直接用 wenyan-cli
wenyan publish -f article.md -t lapis -h solarized-light

# 方式 3: stdin（推荐，解决路径问题）
# macOS/Linux:
cat "/path/to/article.md" | WECHAT_APP_ID=xxx WECHAT_APP_SECRET=xxx wenyan publish -t lapis -h solarized-light

# 方式 4: 含视频文章（必须用这个）
node {baseDir}/scripts/publisher/publish_with_video.js /path/to/article.md
```

## 主题选项

**内置主题**：`default`、`lapis`（推荐）、`phycat`

**代码高亮**：`atom-one-dark`、`dracula`、`github`、`monokai`、`solarized-light`（推荐）、`xcode`

```bash
wenyan publish -f article.md -t lapis -h solarized-light
wenyan theme -l  # 查看所有主题
```

## 视频嵌入（关键）

微信视频必须用 iframe + data-mpvid 格式，`publish_with_video.js` 已内置此逻辑。

Markdown 中引用：
```markdown
![视频描述](media/video.mp4)   # 自动上传并嵌入
```

## 故障排查

| 问题 | 解决方法 |
|------|---------|
| IP 不在白名单 | `curl ifconfig.me` → 添加到公众号后台 |
| wenyan 未安装 | `npm install -g @wenyan-md/cli` |
| 环境变量未设置 | `export WECHAT_APP_ID=xxx` |
| 缺少 frontmatter | 添加 title + cover |
| 40001 token 失效 | 用 `publish_with_video.js`（已内置 token 管理） |

---

# 完整工作流示例

## 搜索 → 洗稿 → 发布

```
1. 搜索文章：node {baseDir}/scripts/search/search_wechat.js "AI教程" -n 5 -c
2. 选择目标文章，执行洗稿改写
3. 保存为 Markdown（含 frontmatter）
4. 发布：node {baseDir}/scripts/publisher/publish.js article.md
```

## 下载 → 洗稿 → 发布

```
1. 下载文章：node {baseDir}/scripts/downloader/download.js "https://mp.weixin.qq.com/s/xxx"
2. 读取下载的 HTML/Markdown，执行洗稿改写
3. 保存为 Markdown（含 frontmatter）
4. 发布：node {baseDir}/scripts/publisher/publish.js article.md
```

---

## 注意事项

- 所有工具仅供个人学习使用，请遵守版权法规
- 搜索功能内置防封禁机制（随机UA、请求延迟），请勿高频使用
- 配置文件：下载器 `{baseDir}/scripts/downloader/config.json`
