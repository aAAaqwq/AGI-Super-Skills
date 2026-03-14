---
name: news-daily
description: Daily AI and tech news aggregator that fetches summarizes and pushes news from authoritative tech sites. Sources include 机器之心 36氪 TechCrunch The Verge and MIT Technology Review. Use when user asks for daily tech/AI news or scheduled news delivery is needed or news aggregation and summarization from multiple sources is required or setting up automated news push notifications to Telegram/WhatsApp.
---

# News Daily - 每日科技新闻推送

## 概述

自动化每日新闻聚合和推送系统，专注于 AI 和前沿科技新闻。从权威来源抓取文章，生成 AI 摘要，通过 Telegram/WhatsApp 定时推送。

**核心特性：**
- 🔍 使用 web_fetch 从权威网站抓取真实新闻
- 🤖 AI 智能摘要（每日精选 3-5 条）
- ⏰ 定时推送（早报 8:00、午报 13:00、晚报 18:00）
- 📱 支持 Telegram 和 WhatsApp 推送
- ✅ 确保新闻真实可信，附带原文链接

## 新闻来源

### 中文来源
| 来源 | URL | 特点 |
|------|-----|------|
| 机器之心 | https://www.jiqizhixin.com | AI 深度报道 |
| 36氪 | https://36kr.com | 科技创投 |
| 量子位 | https://www.qbitai.com | AI 快讯 |
| 新智元 | https://www.xinzhiyuan.com | AI 前沿 |

### 英文来源
| 来源 | URL | 特点 |
|------|-----|------|
| TechCrunch | https://techcrunch.com | 全球科技 |
| The Verge | https://www.theverge.com | 消费科技 |
| MIT Tech Review | https://www.technologyreview.com | 前沿技术 |
| Hacker News | https://news.ycombinator.com | 技术社区 |
| Ars Technica | https://arstechnica.com | 深度技术 |

## 工作流程

### 1. 新闻抓取

使用 `web_fetch` 工具从各个来源抓取：

```
1. 访问新闻网站首页或 RSS
2. 提取文章标题、摘要、链接、时间
3. 按 AI/科技 关键词过滤
4. 去重并按时间排序
```

### 2. AI 摘要生成

```
1. 选择最重要的 3-5 条新闻
2. 生成简洁中文摘要
3. 保留原文链接和来源
4. 格式化输出
```

### 3. 推送

**使用 telegram-push skill 推送到群聊**（推荐）：

```bash
# 使用独立的 newsrebot 推送，不影响 OpenClaw 主 bot
/home/aa/clawd/skills/telegram-push/telegram-push.sh "新闻内容"

# 或直接 curl
curl -s -X POST "https://api.telegram.org/bot$(pass tokens/telegram-newsrobot)/sendMessage" \
  -H "Content-Type: application/json" \
  -d '{
    "chat_id": -1003824568687,
    "text": "新闻内容",
    "parse_mode": "HTML"
  }'
```

**推送目标**：
- DailyNews 群: `-1003824568687`
- Bot: @fkkanfnnfbot (NewsRobot)
- Token: `pass tokens/telegram-newsrobot`

详见 `/home/aa/clawd/skills/telegram-push/SKILL.md`

## Cron 任务配置

### 当前任务

| 任务 | 时间 | Cron 表达式 |
|------|------|-------------|
| 早报 | 08:00 | `0 8 * * *` |
| 午报 | 13:00 | `0 13 * * *` |
| 晚报 | 18:00 | `0 18 * * *` |

### 任务 Prompt 模板

```markdown
请抓取今日科技新闻并推送到 Telegram。

📰 **抓取步骤**：
1. 使用 web_fetch 访问以下网站：
   - https://www.jiqizhixin.com (机器之心)
   - https://36kr.com/newsflashes (36氪快讯)
   - https://techcrunch.com (TechCrunch)
   
2. 从每个来源提取 2-3 条最新 AI/科技新闻

3. 筛选标准：
   - 24小时内发布
   - AI、大模型、科技相关
   - 有实质内容（非广告）

4. 生成摘要并推送

📋 **输出格式**：
📰 科技早报 | YYYY-MM-DD

━━━━━━━━━━━━━━━━━━━━━━━━

🤖 [标题]
来源：[网站名] | [时间]
[链接]

摘要：[50-100字摘要]

━━━━━━━━━━━━━━━━━━━━━━━━

[重复 3-5 条]

📊 今日共精选 X 条重点新闻
```

## 质量保证

### 确保真实性

1. **必须使用 web_fetch** - 从真实网站抓取
2. **保留原文链接** - 每条新闻必须有可访问的链接
3. **标注来源** - 明确标注新闻来源网站
4. **时效性检查** - 只推送 24 小时内的新闻

### 避免幻觉

❌ 不要：
- 编造新闻内容
- 使用没有来源的信息
- 推送无法验证的消息

✅ 要：
- 直接引用原文
- 提供可点击的链接
- 标注抓取时间

## 故障排查

### 新闻抓取失败

```bash
# 检查网站是否可访问
curl -I https://www.jiqizhixin.com

# 检查 web_fetch 工具
# 在 OpenClaw 中测试
```

### 推送失败

```bash
# 检查 Telegram 配置
openclaw status | grep Telegram

# 检查 message 工具
openclaw channels status
```

### Cron 任务错误

```bash
# 查看任务状态
openclaw cron list

# 手动触发测试
openclaw cron run <job_id>
```

## 配置文件

### 推送目标

使用 telegram-push skill 推送到 DailyNews 群：

- **DailyNews 群**: `-1003824568687`
- **Bot**: @fkkanfnnfbot (NewsRobot)
- **Token**: `pass tokens/telegram-newsrobot`

详见 `/home/aa/clawd/skills/telegram-push/SKILL.md`

### 自定义来源

在任务 prompt 中修改网站列表即可。

## 相关资源

- [OpenClaw Cron 文档](https://docs.openclaw.ai/cli/cron)
- [Message 工具文档](https://docs.openclaw.ai/cli/message)
- [Web Fetch 工具](https://docs.openclaw.ai/tools/web)

---

*由小a维护 - 确保每日新闻真实可信*
