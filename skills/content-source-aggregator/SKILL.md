---
name: content-source-aggregator
description: "实时数据采集中心。从 Reddit/GitHub/HackerNews/ArXiv/YouTube/B站/微博/知乎等 16+ 平台免费获取实时热点、技术趋势、AI前沿论文，输出标准化热点池。小data 专属管理。"
allowed-tools: Read, Write, Edit, Bash, WebFetch
---

# 📡 实时数据采集中心（小data 专属）

**角色定位**：你是团队的数据调控大师。所有团队成员需要的实时数据、热点趋势、市场信号，都由你通过此 skill 统一采集和管理。

## 核心能力

### 覆盖 16+ 平台（按优先级排序）

| 优先级 | 平台 | 数据类型 | 方式 | 状态 |
|--------|------|----------|------|------|
| 🥇 | **Reddit** | AI/Tech社区讨论 | old.reddit.com JSON API | ✅ 15个子板块 |
| 🥇 | **GitHub** | 开源项目趋势 | Trending + Search API | ✅ |
| 🥇 | **HackerNews** | 技术创业热点 | Firebase API | ✅ |
| 🥇 | **ArXiv** | AI/ML前沿论文 | Atom API | ✅ cs.AI/LG/CL/CV |
| 🥈 | **Twitter/X** | AI KOL动态 | syndication API | ⚠️ 需代理 |
| 🥈 | **YouTube** | AI/Tech视频 | RSS Feed | ✅ 12频道 |
| 🥈 | **ProductHunt** | 新产品发布 | RSS Feed | ✅ |
| 🥉 | **B站** | 国内视频热点 | 公开API | ✅ |
| 🥉 | **知乎** | 中文问答热榜 | 60s API | ✅ |
| 🥉 | **微博** | 社会热搜 | 60s API | ✅ |
| 🥉 | **头条** | 新闻热榜 | 60s API | ✅ |
| 🥉 | **抖音** | 短视频热搜 | 60s API | ✅ |
| 🥉 | **LinuxDo** | 技术社区 | Discourse API | ✅ |
| ⏳ | 小红书 | 生活消费 | 需登录态 | 待接入 |
| ⏳ | 微信公众号 | 深度文章 | 需登录态 | 待接入 |

## 使用方法

### 全量采集（按优先级顺序）
```bash
python3 ~/clawd/skills/content-source-aggregator/scripts/fetch_all.py
```

### 单平台采集
```bash
python3 ~/clawd/skills/content-source-aggregator/scripts/fetch_all.py --source reddit
python3 ~/clawd/skills/content-source-aggregator/scripts/fetch_all.py --source github
python3 ~/clawd/skills/content-source-aggregator/scripts/fetch_all.py --source hackernews
python3 ~/clawd/skills/content-source-aggregator/scripts/fetch_all.py --source arxiv
python3 ~/clawd/skills/content-source-aggregator/scripts/fetch_all.py --source youtube
python3 ~/clawd/skills/content-source-aggregator/scripts/fetch_all.py --source producthunt
python3 ~/clawd/skills/content-source-aggregator/scripts/fetch_all.py --source bilibili
```

### 预览模式（不保存文件）
```bash
python3 ~/clawd/skills/content-source-aggregator/scripts/fetch_all.py --dry-run
```

## 输出格式

标准化 JSON 写入 `~/clawd/workspace/content-pipeline/hotpool/YYYY-MM-DD.json`

```json
{
  "date": "2026-03-08",
  "fetched_at": "2026-03-08T10:00:00+08:00",
  "total": 150,
  "sources": {"reddit": 54, "github": 11, "hackernews": 15, ...},
  "items": [
    {
      "source": "reddit",
      "title": "...",
      "url": "...",
      "summary": "...",
      "category": "r/artificial",
      "engagement": {"upvotes": 1200, "comments": 340},
      "author": "...",
      "fetched_at": "..."
    }
  ]
}
```

## 配置

编辑 `scripts/config.json` 自定义：
- `source_priority` — 采集优先级顺序
- `reddit.subreddits` — 关注的子板块（当前15个AI/Tech核心板块）
- `twitter.accounts` — 关注的X账号（当前28个AI KOL）
- `youtube.channels` — 关注的频道（当前12个）
- `github.min_stars` — 最低星数阈值
- `arxiv.categories` — ArXiv分类（cs.AI/LG/CL/CV）
- `hackernews.limit` — HackerNews获取数量

## 数据管理职责（小data 必读）

### 日常职责
1. **每日 3 次采集**：08:00 / 14:00 / 20:00 运行全量采集
2. **数据质量监控**：检查各源是否正常返回，异常立即报告
3. **热点池维护**：去重、评分、分类，输出高质量热点池
4. **按需采集**：团队成员（小content/小research/小market）请求特定数据时即时响应

### 数据服务接口
其他 agent 可以通过以下方式获取数据：
- **读文件**：直接读 `~/clawd/workspace/content-pipeline/hotpool/YYYY-MM-DD.json`
- **发指令**：通过 sessions_send 请求小data采集特定平台/话题
- **Cron 产出**：每日定时采集结果自动写入热点池

### 数据质量标准
- 每条数据必须有 `source`、`title`、`url`
- engagement 数据尽量完整（upvotes/comments/views）
- 去除广告、spam、低质量内容
- 中文和英文内容均保留

## API 详情

### Reddit
- 端点: `https://old.reddit.com/r/{sub}/hot.json?limit=5`
- 直连可用，无需代理，无需认证
- 子板块: artificial, MachineLearning, LocalLLaMA, singularity, ChatGPT, ClaudeAI, OpenAI, StableDiffusion, technology, programming, deeplearning, datascience, ArtificialIntelligence, compsci, startups

### GitHub
- Trending: 页面解析
- Search API: `https://api.github.com/search/repositories?q=stars:>{min_stars}+pushed:>{date}&sort=stars`
- 无认证 60次/小时

### HackerNews
- Top Stories: `https://hacker-news.firebaseio.com/v0/topstories.json`
- Item: `https://hacker-news.firebaseio.com/v0/item/{id}.json`
- 完全免费，无限制

### ArXiv
- Atom API: `http://export.arxiv.org/api/query?search_query=cat:cs.AI+OR+cat:cs.LG&sortBy=submittedDate&sortOrder=descending&max_results=10`
- 完全免费

### Twitter/X ⚠️
- syndication API: `https://syndication.twitter.com/srv/timeline-profile/screen-name/{username}`
- **国内需代理**（被墙）
- 代理配置: 环境变量 `CONTENT_PROXY`（默认 `http://127.0.0.1:7890`）

### YouTube
- RSS: `https://www.youtube.com/feeds/videos.xml?channel_id={id}`
- 免费无限制

### B站
- 热门排行: `https://api.bilibili.com/x/web-interface/ranking/v2?rid=0&type=all`
- 需 Referer: https://www.bilibili.com

### 中文热搜（60s API）
- 微博: `https://60s.viki.moe/v2/weibo`
- 知乎: `https://60s.viki.moe/v2/zhihu`
- 头条: `https://60s.viki.moe/v2/toutiao`
- 抖音: `https://60s.viki.moe/v2/douyin`

## 与团队协作

本 skill 是内容工厂流水线的 **Phase 1（数据采集层）**：
```
小data(采集) → 小research(选题评分) → 小content(内容创作) → 小market(分发推广)
```

数据流向：
- 热点池 → 小research 做话题筛选和深度调研
- GitHub Trending → 小content 写技术解读文章
- ArXiv 论文 → 小research 做论文摘要和解读
- Reddit 讨论 → 小content 写社区观点汇总
