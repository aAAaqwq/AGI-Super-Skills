# SKILL.md

# AI Market Intelligence Agent

自动收集、分析和报告市场/行业信息。

## 能力

- 定时监控关键词/公司/产品
- 跨平台信息聚合（新闻、社交媒体、报告）
- 结构化输出：趋势、机会、风险、竞品动态
- 定制化报告模板

## 使用方式

```bash
# 生成市场监控报告
openclaw run market-intelligence --keyword "AI agent" --platform "news, twitter, reddit" --format "markdown"

# 监控特定公司
openclaw run market-intelligence --company "OpenAI" --focus "competitors, funding"

# 生成周报
openclaw run market-intelligence --period "week" --output "weekly_report.md"
```

## 配置

在 `config.json` 中设置：
- `sources`: 数据源列表（news_api, twitter_api, reddit_api, arxiv等）
- `template`: 报告模板路径
- `frequency`: 监控频率（cron表达式）

## 输出

- Markdown 报告
- JSON 数据（供其他工具使用）
- 可发送到指定频道/邮件

## 定价

- 单次报告：$5-20
- 月度订阅：$50-200
- 企业定制：按需报价

## 开发者

OpenClaw AI Agent
License: MIT
Version: 1.0.0
