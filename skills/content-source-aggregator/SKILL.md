# content-source-aggregator
> 统一信息源热点采集器——从 16+ 平台采集热门内容，生成结构化热点池

## 使用场景
- 每日多平台热点自动采集（微博/知乎/头条/抖音/B站/GitHub/YouTube/Twitter/Reddit/HackerNews 等）
- 内容管线上游数据源，为 content-factory 提供原始热点
- 海外源自动走代理（Clash），国内源直连

## 使用方法
```bash
# 采集所有平台
python ~/clawd/skills/content-source-aggregator/scripts/fetch_all.py

# 只采集指定平台
python fetch_all.py --source github
python fetch_all.py --source hackernews

# Dry run（只打印不保存）
python fetch_all.py --dry-run
```

## 支持平台（16+）
| 分类 | 平台 |
|------|------|
| 国内社交 | 微博、知乎、头条、抖音 |
| 国内社区 | B站、LinuxDo、小红书 |
| 海外社交 | Twitter/X、Reddit、YouTube |
| 开发者 | GitHub Trending、HackerNews、ArXiv、ProductHunt |
| 微信生态 | 微信公众号（搜狗）、微信视频号（无 API） |

## 配置要求
- Python 3.10+, curl
- 代理（海外源）：`CONTENT_PROXY` 环境变量（默认 `http://127.0.0.1:7897`）
- Cookie 文件（可选）：`~/.playwright-data/linuxdo/cookies.txt`、`xiaohongshu/cookies.txt` 等
- 配置文件：`scripts/config.json`（账号列表、subreddit、频道 ID、优先级等）
- 输出目录：`~/clawd/workspace/content-pipeline/hotpool/`

## 相关文件
- `scripts/fetch_all.py` — 采集主脚本
- `scripts/config.json` — 平台配置（账号、优先级等）
- `~/clawd/workspace/content-pipeline/hotpool/` — 热点池输出
