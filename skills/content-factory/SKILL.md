# content-factory
> 内容工厂——从热点池批量筛选评分选题，生成内容选题卡片并推送

## 使用场景
- 每日内容选题自动筛选（从 10+ 平台热点池中 AI 评分 Top 10）
- 选题卡片格式化推送到 Telegram
- 内容管线核心组件，衔接 content-source-aggregator（上游采集）和内容创作（下游）

## 使用方法
```bash
# 评分今天的热点池（默认 Top 10）
python ~/clawd/skills/content-factory/scripts/topic_scorer.py

# 指定日期 / 数量
python topic_scorer.py --date 2026-03-22 --top 5

# 不推送，只输出
python topic_scorer.py --no-send

# Dry run（不调 LLM，用随机分测试）
python topic_scorer.py --dry-run

# 只评分前 N 条热点
python topic_scorer.py --limit 20

# 推送已评分的选题到 Telegram
python ~/clawd/skills/content-factory/scripts/topic_presenter.py --date 2026-03-22 --top 5
python topic_presenter.py --dry-run
```

## 评分维度（权重可配）
| 维度 | 权重 | 说明 |
|------|------|------|
| heat | 0.35 | 热度和讨论量 |
| timeliness | 0.25 | 话题新鲜度 |
| creativity | 0.40 | 创作空间（纯新闻搬运低分） |

## 配置要求
- Python 3.10+, httpx
- LLM API（DeepSeek 或 ZAI，通过 `pass show api/deepseek` 配置）
- `~/clawd/scripts/newsbot_send.py`（推送依赖）
- 热点池目录：`~/clawd/workspace/content-pipeline/hotpool/`
- 选题输出目录：`~/clawd/workspace/content-pipeline/topics/`

## 相关文件
- `scripts/topic_scorer.py` — 核心评分脚本
- `scripts/topic_presenter.py` — 选题格式化与推送
- `scripts/aggregator/` — 内容聚合子模块
- `data/topics/` — 历史评分数据
- `data/hotpool/` — 历史热点池快照
