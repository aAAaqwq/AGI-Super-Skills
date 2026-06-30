<div align="center">

# 雷达Skill | ai-radar

> 对Agent说一句"今天AI圈有什么"，10秒拿到一份带原文链接的中文AI简报。

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](../../LICENSE)
[![Agent Skills](https://img.shields.io/badge/Agent%20Skills-ai--radar-blueviolet)](https://github.com/LearnPrompt/ai-news-radar)
[![Zero API](https://img.shields.io/badge/API-Zero-green)](#为什么是零api)

![ai-radar demo](assets/demo.gif)

[安装](#快速开始) · [触发方式](#触发方式) · [它和同类有什么不同](#它和同类有什么不同) · [安全边界](#安全边界) · [English](#english)

</div>

---

## 你什么时候需要它

- 每天打开十几个网站追AI新闻，想让Agent替你跑腿。
- 用过那些"AI日报Skill"，但不想依赖谁家的服务器和API——服务一下线，Skill就成砖。
- 想要一个**问完即走**的入口：一句话，一份简报，每条都有原文链接。

## 它会交付什么

一份按"模型发布 / 产品更新 / 开发者工具 / 值得注意"分组的中文简报：

- 每条带原文链接和信源名，官方一手源优先；
- 数据来自 [AI News Radar](https://github.com/LearnPrompt/ai-news-radar) 公开管道：150+ 信源、AI相关性过滤、信源分层；
- 简报永远标注数据时间——数据过期会直说，不装新鲜。

## 快速开始

```bash
npx skills add LearnPrompt/ai-news-radar -s ai-radar -g
```

装完直接说：

```text
今天AI圈有什么？
```

## 触发方式

这些话都会唤醒它：

- "今天AI圈有什么" / "过去24小时AI新闻"
- "最近有什么大模型发布"
- "OpenAI/Anthropic/Google 最近发了什么"
- "Agent工具有什么新东西"
- "看下AI雷达" / "AI日报"
- "哪些AI信源值得看"

## 为什么是零API

本Skill不调用任何API服务。它读的是 GitHub Pages 上的**公开静态JSON**——GitHub Actions 每30分钟刷新一次，无鉴权、无限流、无UA黑名单，`curl` 即取。

这带来一个根本差异：**数据管道是可fork的**。上游页面哪天没了？fork仓库，你自己的 Pages 上就长出一份一模一样的数据，把Skill的 Base URL 一换就续上了。

## 它和同类有什么不同

| | 中心化API型资讯Skill | Agent现抓现总结 | **ai-radar** |
|---|---|---|---|
| 依赖 | 别人的服务器 | 每次烧Agent额度 | 公开静态JSON |
| 服务下线后 | Skill变砖 | — | fork即复活 |
| 信源可定制 | 不能 | 每次重新教 | fork后伯乐Skill录入 |
| 数据新鲜度 | 取决于服务方 | 实时但贵 | 每30分钟，自动 |

## 想换信源？

这正是它和兄弟Skill的分工：**ai-radar 管读，[伯乐Skill](../ai-news-radar/README.md) 管选。**

1. fork [LearnPrompt/ai-news-radar](https://github.com/LearnPrompt/ai-news-radar)；
2. 用伯乐Skill判断和录入你的信源（RSS/OPML/公开feed/静态页/AgentMail）；
3. 把 ai-radar 的 Base URL 指向你自己的 Pages。

信源你选，数据归你。

## 安全边界

- 只发 GET 请求，只读公开静态文件；
- 不需要也不接受 API Key、token、cookie；
- 不抓取需要登录的页面；
- 数据过期、类别为空、历史超窗时如实说明，不编造新闻。

## 文件结构

```text
skills/radar/
├── SKILL.md          # Agent工作流：路由表、新鲜度检查、失败模式
├── README.md         # 本文件
└── assets/
    ├── demo.gif      # 上面的演示
    ├── demo.tape     # vhs录制脚本（GIF可复现）
    └── demo.sh       # 演示用的真实数据拉取脚本
```

## 验证与测试

装完可以用这两句验收：

```text
今天AI圈有什么？        → 应返回分组中文简报，每条带链接，文末有数据时间
最近有什么模型发布？     → 应只返回 model_release 类条目
```

或者不装Skill直接验证数据管道：

```bash
bash skills/radar/assets/demo.sh
```

---

## English

**ai-radar** answers "What happened in AI today?" by reading the public static JSON that [AI News Radar](https://github.com/LearnPrompt/ai-news-radar) publishes on GitHub Pages every 30 minutes. Zero API, zero key, zero server — and because the whole data pipeline is forkable, the skill can never be bricked by someone else's service going down.

```bash
npx skills add LearnPrompt/ai-news-radar -s ai-radar -g
```

Then ask your agent: `What happened in AI today?`

Want your own sources? Fork the repo, let the in-repo [Scout Skill](../ai-news-radar/README.md) classify and ingest them, and point ai-radar at your own Pages URL.
