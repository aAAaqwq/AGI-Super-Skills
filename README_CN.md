# 🚀 AGI Super Skills

中文 | [English](./README.md)

> **285+ 精选 Skills** 适用于 [OpenClaw](https://github.com/openclaw/openclaw) — 开源 AI Agent 框架。
> 用 AI 团队构建你的一人公司 (OPC)。

## 📊 概览

| 指标 | 数值 |
|------|------|
| **Skills** | 285+ |
| **分类** | 18 |
| **Agents** | 13 |
| **框架** | [OpenClaw](https://github.com/openclaw/openclaw) |

## 🏗️ 团队架构

```
Daniel (创始人/决策者)
  └── 小a (AI CEO / 协调者)
        ├── 小code (首席工程师)
        ├── 小quant (首席交易官)
        ├── 小data (首席数据官)
        ├── 小ops (首席运维官)
        ├── 小content (首席内容官)
        ├── 小research (首席研究官)
        ├── 小finance (首席财务官)
        ├── 小market (首席营销官)
        ├── 小pm (首席项目官)
        ├── 小law (首席法务官)
        ├── 小product (首席产品官)
        └── 小sales (首席销售官)
```

## 👥 Agent 团队

| ID | 名称 | 职责 | 模型 |
|----|------|------|------|
| `main` | 小a | CEO / 战略决策 | `xingsuancode/claude-opus-4-6` |
| `code` | 小code | 首席工程师 | `zai/glm-5` |
| `quant` | 小quant | 首席交易官 | `zai/glm-5` |
| `data` | 小data | 首席数据官 | `zai/glm-5` |
| `ops` | 小ops | 首席运维官 | `zai/glm-5` |
| `content` | 小content | 首席内容官 | `zai/glm-5` |
| `research` | 小research | 首席研究官 | `zai/glm-5` |
| `finance` | 小finance | 首席财务官 | `zai/glm-5` |
| `market` | 小market | 首席营销官 | `zai/glm-5` |
| `pm` | 小pm | 首席项目官 | `zai/glm-5` |
| `law` | 小law | 首席法务官 | `minimax/MiniMax-M2.5` |
| `product` | 小product | 首席产品官 | `zai/glm-5` |
| `sales` | 小sales | 首席销售官 | `zai/glm-5` |

> Agent 配置在 [`agents/<id>/agent.json`](./agents/)（已脱敏）。

## 🛠️ Skills 目录

- [⚙️ OpenClaw Tools OpenClaw 配置工具 (21)](#-OpenClaw-配置工具)
- [🤖 AI Agent Patterns AI Agent 模式 (20)](#-AI-Agent-模式)
- [🔧 Development 开发工具 (26)](#-开发工具)
- [💰 Trading & Finance 交易与金融 (27)](#-交易与金融)
- [📝 Content & Writing 内容创作 (22)](#-内容创作)
- [📊 Data & Analytics 数据与分析 (15)](#-数据与分析)
- [📈 Marketing & SEO 营销与 SEO (14)](#-营销与-SEO)
- [🎨 Design & Media 设计与媒体 (12)](#-设计与媒体)
- [🌐 Browser Automation 浏览器自动化 (6)](#-浏览器自动化)
- [🏢 Business & Strategy 商业与战略 (10)](#-商业与战略)
- [📋 Project Management 项目管理 (13)](#-项目管理)
- [🧠 Knowledge & Research 知识与研究 (3)](#-知识与研究)
- [💬 Communication 通讯与推送 (10)](#-通讯与推送)
- [🔌 SaaS Integrations SaaS 集成 (61)](#-SaaS-集成)
- [⚙️ DevOps & Infra 运维与基础设施 (7)](#-运维与基础设施)
- [🔒 Security 安全 (4)](#-安全)
- [⚖️ Legal & Compliance 法务与合规 (1)](#-法务与合规)
- [🧩 Other 其他 (13)](#-其他)

### ⚙️ OpenClaw Tools

| Skill | 描述 |
|-------|------|
| [`api-provider-setup`](./skills/api-provider-setup/) | 添加和配置第三方 API 中转站供应商到 OpenClaw。当用户需要添加新的 API 供应商、配置中转站、设置自定义模型端点时使用此技能。支持 Anthropic 兼容和 OpenAI 兼容的 API 格式。 |
| [`api-provider-status`](./skills/api-provider-status/) | API 供应商状态查询与余额监控。 |
| [`auth-manager`](./skills/auth-manager/) | 网页登录态管理。使用 fast-browser-use (fbu) 管理各平台登录状态，定期检查可用性，新平台授权时自动保存 profile。 |
| [`context-manager`](./skills/context-manager/) | AI-powered context management for OpenClaw sessions |
| [`cron-manager`](./skills/cron-manager/) | 定时任务管理专家。负责创建、监控、诊断和修复 OpenClaw cron 任务。 |
| [`evomap`](./skills/evomap/) | Connect to the EvoMap collaborative evolution marketplace. Publish Gene+Capsule bundles, fetch promoted assets, claim bo |
| [`feishu-channel`](./skills/feishu-channel/) | 飞书 (Lark/Feishu) 与 OpenClaw 的双向集成通道。通过飞书机器人实现消息的接收和发送，支持私聊、群聊、@提及检测、卡片消息、文件传输。当需要通过飞书与 AI 助手交互、接收飞书消息触发 AI 响应、或从 OpenCla |
| [`mcp-installer`](./skills/mcp-installer/) | 从GitHub搜索并自动安装配置MCP(Model Context Protocol)服务器工具到Claude配置文件。当用户需要安装MCP工具时触发此技能。工作流程：搜索GitHub上的MCP项目 -> 提取npx配置 -> 添加到~/. |
| [`mcp-manager`](./skills/mcp-manager/) | MCP 服务器智能管理助手。自动检测 MCP 可用性、智能开关、功能问答，提供人性化的 MCP 管理体验。 |
| [`model-fallback`](./skills/model-fallback/) | 模型自动降级与故障切换。当主模型请求失败、超时、达到速率限制或配额耗尽时，自动切换到备用模型，确保服务连续性。支持多供应商、多优先级的智能模型选择，提供健康监控、自动重试和错误恢复机制。 |
| [`model-health-check`](./skills/model-health-check/) | 检查所有配置的模型供应商连通性和延迟。 |
| [`openclaw-config-helper`](./skills/openclaw-config-helper/) | OpenClaw 配置修改助手。修改任何 OpenClaw 配置前必须先查阅官方文档，确保格式正确，避免系统崩溃或功能异常。强制执行：查 schema → 查文档 → 确认 → 修改的流程。 |
| [`openclaw-inter-instance`](./skills/openclaw-inter-instance/) | OpenClaw 实例间通信。当需要在多个 OpenClaw 实例之间传递消息、同步数据、远程执行命令时使用此技能。覆盖 agent-to-agent 消息、nodes.run 远程执行、文件级通信等多种方式。 |
| [`openrouter-usage`](./skills/openrouter-usage/) | Track OpenRouter API spending — credit balance, per-model cost breakdown, and spending projections from OpenClaw session |
| [`permission-manager`](./skills/permission-manager/) | 管理Claude Code的全局工具权限配置，自动将MCP命令或其他工具添加到allowedTools中，避免每次使用时都需要手动批准。工作流程：确认用户需要添加的命令 -> 确认添加级别(默认全局~/.claude.json) -> 执行 |
| [`skill-finder-cn`](./skills/skill-finder-cn/) | Skill 查找器 \| Skill Finder. 帮助发现和安装 ClawHub Skills \| Discover and install ClawHub Skills. 回答'有什么技能可以X'、'找一个技能' \| Answer |
| [`skillforge`](./skills/skillforge/) | Intelligent skill router and creator. Analyzes ANY input to recommend existing skills, improve them, or create new ones. |
| [`telegram-push`](./skills/telegram-push/) | 通过独立的 Telegram Bot 推送消息到群聊或私聊，不依赖 OpenClaw 的 telegram channel 配置。 |
| [`token-guard`](./skills/token-guard/) | Monitor and control OpenClaw token usage and costs. Set daily budgets, track spending, auto-downgrade models when limits |
| [`wechat-channel`](./skills/wechat-channel/) | 微信 (WeChat) 与 OpenClaw 的双向集成通道。基于 Wechaty + PadLocal 实现微信消息的接收和发送，支持私聊、群聊、@提及检测、图片/文件传输。当需要通过微信与 AI 助手交互、接收微信消息触发 AI 响应、 |
| [`xiaomo-assistant-template`](./skills/xiaomo-assistant-template/) | 小a助手配置模板。基于 xiaomo-starter-kit 改编，提供预配置的 OpenClaw 助手框架文件。当用户需要快速配置新助手、设置助手身份、创建助手配置文件时使用此技能。 |

### 🤖 AI Agent Patterns

| Skill | 描述 |
|-------|------|
| [`agent-patterns`](./skills/agent-patterns/) | Execute this skill should be used when the user asks about "SPAWN REQUEST format", "agent reports", "agent coordination" |
| [`env-setup`](./skills/env-setup/) | Claude Code 环境一键同步工具。从 GitHub 仓库同步所有配置到本地：output-styles 风格、CLAUDE.md 全局提示词、MCP 服务器配置、Agent 配置、Plugin 配置。适用于多设备统一环境、换电脑恢复 |
| [`erc-8004`](./skills/erc-8004/) | Register AI agents on Ethereum mainnet using ERC-8004 (Trustless Agents). Use when the user wants to register their agen |
| [`fabric-pattern`](./skills/fabric-pattern/) | Integration for the Fabric AI framework (https://github.com/danielmiessler/Fabric). This skill manages text processing b |
| [`kubernetes-deployment`](./skills/kubernetes-deployment/) | Kubernetes deployment workflow for container orchestration, Helm charts, service mesh, and production-ready K8s configur |
| [`multi-agent-architecture`](./skills/multi-agent-architecture/) | 多 Agent 架构设计与智能 Spawn 系统。当需要设计多 Agent 系统、配置专业化 Agent、实现智能任务分发、或优化并发处理能力时使用此技能。 |
| [`multimodal-gen`](./skills/multimodal-gen/) | 多模态内容生成（图片、视频）。当用户需要生成图片、生成图像、生成视频、AI绘画、AI作图、画一张图、做个视频、文生图、文生视频时使用此技能。自动调用 multimodal-agent 进行生成。 |
| [`parallel-agents`](./skills/parallel-agents/) | Multi-agent orchestration patterns. Use when multiple independent tasks can run with different domain expertise or when  |
| [`prompt-optimizer`](./skills/prompt-optimizer/) | Evaluate, optimize, and enhance prompts using 58 proven prompting techniques. Use when user asks to improve, optimize, o |
| [`sp-collision-zone-thinking`](./skills/sp-collision-zone-thinking/) | Force unrelated concepts together to discover emergent properties - "What if we treated X like Y?" |
| [`sp-dispatching-parallel-agents`](./skills/sp-dispatching-parallel-agents/) | Use multiple Claude agents to investigate and fix independent problems concurrently |
| [`sp-executing-plans`](./skills/sp-executing-plans/) | Execute detailed plans in batches with review checkpoints |
| [`sp-inversion-exercise`](./skills/sp-inversion-exercise/) | Flip core assumptions to reveal hidden constraints and alternative approaches - "what if the opposite were true?" |
| [`sp-meta-pattern-recognition`](./skills/sp-meta-pattern-recognition/) | Spot patterns appearing in 3+ domains to find universal principles |
| [`sp-preserving-productive-tensions`](./skills/sp-preserving-productive-tensions/) | Recognize when disagreements reveal valuable context, preserve multiple valid approaches instead of forcing premature re |
| [`sp-remembering-conversations`](./skills/sp-remembering-conversations/) | Search previous Claude Code conversations for facts, patterns, decisions, and context using semantic or text search |
| [`sp-scale-game`](./skills/sp-scale-game/) | Test at extremes (1000x bigger/smaller, instant/year-long) to expose fundamental truths hidden at normal scales |
| [`sp-simplification-cascades`](./skills/sp-simplification-cascades/) | Find one insight that eliminates multiple components - "if this is true, we don't need X, Y, or Z" |
| [`sp-when-stuck`](./skills/sp-when-stuck/) | Dispatch to the right problem-solving technique based on how you're stuck |
| [`subagent-driven-development`](./skills/subagent-driven-development/) | Use when executing implementation plans with independent tasks in the current session |

### 🔧 Development

| Skill | 描述 |
|-------|------|
| [`architecture-decision-records`](./skills/architecture-decision-records/) | Write and maintain Architecture Decision Records (ADRs) following best practices for technical decision documentation. U |
| [`backend-development`](./skills/backend-development/) | 后端服务开发专家（通才）。精通多种后端技术栈，能够根据需求选择最合适的技术方案。  当用户需要开发API、数据库设计、微服务架构或后端业务逻辑时使用此技能。  根据用户需求的技术栈，自动切换到对应语言的专家模式： - Python → 查看 |
| [`bat-cat`](./skills/bat-cat/) | A cat clone with syntax highlighting, line numbers, and Git integration - a modern replacement for cat. |
| [`billing-automation`](./skills/billing-automation/) | Build automated billing systems for recurring payments, invoicing, subscription lifecycle, and dunning management. Use w |
| [`changelog-generator`](./skills/changelog-generator/) | Automatically creates user-facing changelogs from git commits by analyzing commit history, categorizing changes, and tra |
| [`commit-analyzer`](./skills/commit-analyzer/) | Analyzes git commit patterns to monitor autonomous operation health. Uses commit frequency, category distribution, and t |
| [`docker-essentials`](./skills/docker-essentials/) | Essential Docker commands and workflows for container management, image operations, and debugging. |
| [`electron-app-dev`](./skills/electron-app-dev/) | Electron桌面应用开发专家。精通electron-vite、TypeScript、React、IPC通信、窗口管理、原生功能集成等Electron全栈开发技术。  适用场景： - 创建electron-vite + TypeScrip |
| [`frontend-design`](./skills/frontend-design/) | Create distinctive, production-grade frontend interfaces with high design quality. Use this skill when the user asks to  |
| [`frontend-development`](./skills/frontend-development/) | 前端页面开发。当用户需要开发 Web 应用、创建 UI 组件、实现交互功能或优化前端性能时使用此技能。 |
| [`github-automation`](./skills/github-automation/) | 自动化 GitHub 操作。当用户需要推送代码到 GitHub、管理仓库、创建 PR、处理 Issue、git push 失败时使用此技能。优先使用 mcporter call github.push_files 而不是 git push。 |
| [`langsmith-fetch`](./skills/langsmith-fetch/) | Debug LangChain and LangGraph agents by fetching execution traces from LangSmith Studio. Use when debugging agent behavi |
| [`mcp-builder`](./skills/mcp-builder/) | Guide for creating high-quality MCP (Model Context Protocol) servers that enable LLMs to interact with external services |
| [`ml-engineer`](./skills/ml-engineer/) | name: ml-engineer |
| [`pass-secrets`](./skills/pass-secrets/) | 使用 Pass (Password Store) 统一管理所有 API 密钥和敏感凭证。Pass 基于 GPG 加密，支持 Git 同步，安全可靠。 |
| [`payment-integration`](./skills/payment-integration/) | name: payment-integration |
| [`python-performance-optimization`](./skills/python-performance-optimization/) | Profile and optimize Python code using cProfile, memory profilers, and performance best practices. Use when debugging sl |
| [`react-component-generator`](./skills/react-component-generator/) | Generate react component generator operations. Auto-activating skill for Frontend Development. Triggers on: react compon |
| [`requesting-code-review`](./skills/requesting-code-review/) | Use when completing tasks, implementing major features, or before merging to verify work meets requirements |
| [`sql-optimization-patterns`](./skills/sql-optimization-patterns/) | Master SQL query optimization, indexing strategies, and EXPLAIN analysis to dramatically improve database performance an |
| [`sql-pro`](./skills/sql-pro/) | name: sql-pro |
| [`systematic-debugging`](./skills/systematic-debugging/) | Use when encountering any bug, test failure, or unexpected behavior, before proposing fixes |
| [`tdd-guide`](./skills/tdd-guide/) | Test-driven development workflow with test generation, coverage analysis, and multi-framework support |
| [`test-automator`](./skills/test-automator/) | name: test-automator |
| [`vibe-code-auditor`](./skills/vibe-code-auditor/) | Audit rapidly generated or AI-produced code for structural flaws, fragility, and production risks. |
| [`web-artifacts-builder`](./skills/web-artifacts-builder/) | Suite of tools for creating elaborate, multi-component claude.ai HTML artifacts using modern frontend web technologies ( |

### 💰 Trading & Finance

| Skill | 描述 |
|-------|------|
| [`arbitrage-opportunity-finder`](./skills/arbitrage-opportunity-finder/) | Detect profitable arbitrage opportunities across CEX, DEX, and cross-chain markets in real-time. Use when scanning for p |
| [`backtesting-frameworks`](./skills/backtesting-frameworks/) | Build robust backtesting systems for trading strategies with proper handling of look-ahead bias, survivorship bias, and  |
| [`bankr`](./skills/bankr/) | AI-powered crypto trading agent and LLM gateway via natural language. Use when the user wants to trade crypto, check por |
| [`bankr-signals`](./skills/bankr-signals/) | Transaction-verified trading signals on Base. Register agent as signal provider, publish trades with TX hash proof, cons |
| [`clanker`](./skills/clanker/) | Deploy ERC20 tokens on Base, Ethereum, Arbitrum, and other EVM chains using the Clanker SDK. Use when the user wants to  |
| [`crypto-bd-agent`](./skills/crypto-bd-agent/) | Autonomous crypto business development patterns — multi-chain token discovery, 100-point scoring with wallet forensics,  |
| [`crypto-derivatives-tracker`](./skills/crypto-derivatives-tracker/) | Track cryptocurrency futures, options, and perpetual swaps with funding rates, open interest, liquidations, and comprehe |
| [`crypto-portfolio-management`](./skills/crypto-portfolio-management/) | Guide to cryptocurrency portfolio management — asset allocation, rebalancing strategies, risk-adjusted returns, benchmar |
| [`crypto-portfolio-tracker`](./skills/crypto-portfolio-tracker/) | Track cryptocurrency portfolio with real-time valuations, allocation analysis, and P&L tracking. Use when checking portf |
| [`crypto-signal-generator`](./skills/crypto-signal-generator/) | Generate trading signals using technical indicators (RSI, MACD, Bollinger Bands, etc.). Combines multiple indicators int |
| [`defi-risk-assessment`](./skills/defi-risk-assessment/) | Framework for evaluating DeFi protocol risk — smart contract audits, TVL analysis, governance structure, oracle dependen |
| [`invoice-organizer`](./skills/invoice-organizer/) | Automatically organizes invoices and receipts for tax preparation by reading messy files, extracting key information, re |
| [`market-movers-scanner`](./skills/market-movers-scanner/) | Detect significant price movements and unusual volume across crypto markets. Calculates significance scores combining pr |
| [`market-price-tracker`](./skills/market-price-tracker/) | Track real-time cryptocurrency prices across exchanges with historical data and alerts. Provides price data infrastructu |
| [`market-sentiment-analyzer`](./skills/market-sentiment-analyzer/) | Analyze cryptocurrency market sentiment using Fear & Greed Index, news analysis, and market momentum. Use when gauging o |
| [`options-flow-analyzer`](./skills/options-flow-analyzer/) | Track crypto options flow to identify institutional positioning and market sentiment. Use when tracking institutional op |
| [`polyclaw`](./skills/polyclaw/) | Trade on Polymarket via split + CLOB execution. Browse markets, track positions with P&L, discover hedges via LLM. Polyg |
| [`polymarket-data`](./skills/polymarket-data/) | Polymarket prediction markets — live odds, prices, order books, events, series, market search, leaderboards, portfolio a |
| [`polymarket-profit`](./skills/polymarket-profit/) | 真实交易系统，$3 本金在 Polymarket 预测市场上执行量化策略。 |
| [`polymarket-skill`](./skills/polymarket-skill/) | Query and trade on Polymarket prediction markets - check odds, trending markets, search events, view order books, place  |
| [`polymarket-trading`](./skills/polymarket-trading/) | 系统性的 Polymarket 预测市场量化交易体系。浏览器自动化 + API 双通道。 |
| [`quant-analyst`](./skills/quant-analyst/) | name: quant-analyst |
| [`risk-metrics-calculation`](./skills/risk-metrics-calculation/) | Calculate portfolio risk metrics including VaR, CVaR, Sharpe, Sortino, and drawdown analysis. Use when measuring portfol |
| [`sperax-defi-guide`](./skills/sperax-defi-guide/) | Comprehensive guide to DeFi yield farming strategies — lending, liquidity provision, auto-compounding, stablecoin yield, |
| [`trading-strategy-backtester`](./skills/trading-strategy-backtester/) | Backtest crypto and traditional trading strategies against historical data. Calculates performance metrics (Sharpe, Sort |
| [`unum-strat`](./skills/unum-strat/) | Unum (Strat) is a universal, fee-aware, capital-scalable strategy design and audit skill for crypto, stocks, ETFs, forex |
| [`whale-alert-monitor`](./skills/whale-alert-monitor/) | Track large cryptocurrency transactions and whale wallet movements in real-time. Use when tracking large holder movement |

### 📝 Content & Writing

| Skill | 描述 |
|-------|------|
| [`content-creator`](./skills/content-creator/) | Create SEO-optimized marketing content with consistent brand voice. Includes brand voice analyzer, SEO optimizer, conten |
| [`content-marketer`](./skills/content-marketer/) | Elite content marketing strategist specializing in AI-powered content creation, omnichannel distribution, SEO optimizati |
| [`content-research-writer`](./skills/content-research-writer/) | Assists in writing high-quality content by conducting research, adding citations, improving hooks, iterating on outlines |
| [`content-source-aggregator`](./skills/content-source-aggregator/) | 统一信息源热点采集。从 X/Twitter、YouTube、B站、GitHub、Reddit、LinuxDo 六大平台免费获取热门内容，输出标准化热点池供内容创作流水线使用。全部使用免费公开 API，无需付费。 |
| [`conventional-commits`](./skills/conventional-commits/) | Format commit messages using the Conventional Commits specification. Use when creating commits, writing commit messages, |
| [`copy-editing`](./skills/copy-editing/) | When the user wants to edit, review, or improve existing marketing copy. Also use when the user mentions 'edit this copy |
| [`copywriting`](./skills/copywriting/) | name: copywriting |
| [`docx`](./skills/docx/) | Comprehensive document creation, editing, and analysis with support for tracked changes, comments, formatting preservati |
| [`docx-perfect`](./skills/docx-perfect/) | Word文档美化与格式化专家。专门用于将Word文档中的文本内容转换为专业表格格式，应用一致的样式（深蓝色表头、斑马纹数据行、边框），支持版本化迭代管理。当用户需要美化Word文档、创建专业表格、或递增式优化文档章节时使用此技能。 |
| [`internal-comms`](./skills/internal-comms/) | A set of resources to help me write all kinds of internal communications, using the formats that my company likes to use |
| [`podcast-generation`](./skills/podcast-generation/) | Generate AI-powered podcast-style audio narratives using Azure OpenAI's GPT Realtime Mini model via WebSocket. Use when  |
| [`react-best-practices`](./skills/react-best-practices/) | React and Next.js performance optimization guidelines from Vercel Engineering. This skill should be used when writing, r |
| [`reddit-automation`](./skills/reddit-automation/) | Automate Reddit tasks via Rube MCP (Composio): search subreddits, create posts, manage comments, and browse top content. |
| [`seo-content-writer`](./skills/seo-content-writer/) | Writes SEO-optimized content based on provided keywords and topic briefs. Creates engaging, comprehensive content follow |
| [`seo-content-writing`](./skills/seo-content-writing/) | SEO 文章撰写。当用户需要创建搜索引擎优化的内容、撰写营销文案或优化网站内容时使用此技能。 |
| [`skill-search-optimizer`](./skills/skill-search-optimizer/) | Optimize agent skills for discoverability on ClawdHub/MoltHub. Use when improving search ranking, writing descriptions f |
| [`social-content`](./skills/social-content/) | When the user wants help creating, scheduling, or optimizing social media content for LinkedIn, Twitter/X, Instagram, Ti |
| [`sp-using-skills`](./skills/sp-using-skills/) | Skills wiki intro - mandatory workflows, search tool, brainstorming triggers |
| [`sp-writing-plans`](./skills/sp-writing-plans/) | Create detailed implementation plans with bite-sized tasks for engineers with zero codebase context |
| [`wiki-page-writer`](./skills/wiki-page-writer/) | Generates rich technical documentation pages with dark-mode Mermaid diagrams, source code citations, and first-principle |
| [`wiki-qa`](./skills/wiki-qa/) | Answers questions about a code repository using source file analysis. Use when the user asks a question about how someth |
| [`xiaohongshu-workflow`](./skills/xiaohongshu-workflow/) | 小红书全流程运营工作流。使用场景： - 账号配置和登录设置 - 内容策划与发布（图文、视频） - 热点追踪与话题监控 - 互动管理与自动回复 - 数据分析与运营优化 - "帮我配置小红书账号" - "发布一篇小红书笔记" - "跟踪小红书上 |

### 📊 Data & Analytics

| Skill | 描述 |
|-------|------|
| [`analytics-tracking`](./skills/analytics-tracking/) | name: analytics-tracking |
| [`arxiv-automation`](./skills/arxiv-automation/) | Search and monitor arXiv papers. Query by topic, author, or category. Track new papers, download PDFs, and summarize abs |
| [`data-engineering-data-pipeline`](./skills/data-engineering-data-pipeline/) | You are a data pipeline architecture expert specializing in scalable, reliable, and cost-effective data pipelines for ba |
| [`data-storytelling`](./skills/data-storytelling/) | Transform data into compelling narratives using visualization, context, and persuasive structure. Use when presenting an |
| [`firecrawl`](./skills/firecrawl/) | 专业网页抓取和数据提取。使用 Firecrawl API 抓取网页、提取结构化数据、批量爬取网站。当用户需要抓取复杂网页、提取结构化数据、批量爬取时使用此技能。 |
| [`football-data`](./skills/football-data/) | Football (soccer) data across 13 leagues — standings, schedules, match stats, xG, transfers, player profiles. Zero confi |
| [`google-analytics-automation`](./skills/google-analytics-automation/) | Automate Google Analytics tasks via Rube MCP (Composio): run reports, list accounts/properties, funnels, pivots, key eve |
| [`googlesheets-automation`](./skills/googlesheets-automation/) | Automate Google Sheets operations (read, write, format, filter, manage spreadsheets) via Rube MCP (Composio). Read/write |
| [`pdf`](./skills/pdf/) | Comprehensive PDF manipulation toolkit for extracting text and tables, creating new PDFs, merging/splitting documents, a |
| [`programmatic-seo`](./skills/programmatic-seo/) | Design and evaluate programmatic SEO strategies for creating SEO-driven pages at scale using templates and structured da |
| [`sendgrid-automation`](./skills/sendgrid-automation/) | Automate SendGrid email operations including sending emails, managing contacts/lists, sender identities, templates, and  |
| [`tavily`](./skills/tavily/) | AI 优化的网络搜索。使用 Tavily API 进行智能搜索，获取实时信息。当用户需要搜索互联网、获取实时数据、查找最新信息时使用此技能。 |
| [`web-scraping-automation`](./skills/web-scraping-automation/) | 自动化爬取网站数据和 API 接口。当用户需要抓取网页内容、调用 API、解析数据或创建爬虫脚本时使用此技能。 |
| [`web-search`](./skills/web-search/) | 网络搜索与网页内容获取。当用户需要搜索互联网信息、获取网页内容、查找实时数据、进行 websearch 时使用此技能。支持多种搜索工具：WebFetch、Firecrawl skill、Tavily skill。 |
| [`xlsx`](./skills/xlsx/) | Comprehensive spreadsheet creation, editing, and analysis with support for formulas, formatting, data analysis, and visu |

### 📈 Marketing & SEO

| Skill | 描述 |
|-------|------|
| [`brand-guidelines`](./skills/brand-guidelines/) | Applies Anthropic's official brand colors and typography to any sort of artifact that may benefit from having Anthropic' |
| [`competitive-ads-extractor`](./skills/competitive-ads-extractor/) | Extracts and analyzes competitors' ads from ad libraries (Facebook, LinkedIn, etc.) to understand what messaging, proble |
| [`competitor-alternatives`](./skills/competitor-alternatives/) | When the user wants to create competitor comparison or alternative pages for SEO and sales enablement. Also use when the |
| [`deep-research`](./skills/deep-research/) | Execute autonomous multi-step research using Google Gemini Deep Research Agent. Use for: market analysis, competitive la |
| [`geo-agent`](./skills/geo-agent/) | Automated GEO (Generative Engine Optimization) agent for boosting brand visibility in AI search engines. Manages keyword |
| [`lead-research-assistant`](./skills/lead-research-assistant/) | Identifies high-quality leads for your product or service by analyzing your business, searching for target companies, an |
| [`linkedin-automation`](./skills/linkedin-automation/) | Automate LinkedIn tasks via Rube MCP (Composio): create posts, manage profile, company info, comments, and image uploads |
| [`marketing-ideas`](./skills/marketing-ideas/) | Provide proven marketing strategies and growth ideas for SaaS and software products, prioritized using a marketing feasi |
| [`marketing-psychology`](./skills/marketing-psychology/) | When the user wants to apply psychological principles, mental models, or behavioral science to marketing. Also use when  |
| [`one-drive-automation`](./skills/one-drive-automation/) | Automate OneDrive file management, search, uploads, downloads, sharing, permissions, and folder operations via Rube MCP  |
| [`paid-ads`](./skills/paid-ads/) | When the user wants help with paid advertising campaigns on Google Ads, Meta (Facebook/Instagram), LinkedIn, Twitter/X,  |
| [`seo-audit`](./skills/seo-audit/) | name: seo-audit |
| [`seo-meta-optimizer`](./skills/seo-meta-optimizer/) | name: seo-meta-optimizer |
| [`twitter-algorithm-optimizer`](./skills/twitter-algorithm-optimizer/) | Analyze and optimize tweets for maximum reach using Twitter's open-source algorithm insights. Rewrite and edit user twee |

### 🎨 Design & Media

| Skill | 描述 |
|-------|------|
| [`ai-image-generation`](./skills/ai-image-generation/) | Generate images using ModelScope Z-Image-Turbo API. Use when user asks to generate, create, or make images, pictures, or |
| [`figma-automation`](./skills/figma-automation/) | Automate Figma tasks via Rube MCP (Composio): files, components, design tokens, comments, exports. Always search tools f |
| [`image-enhancer`](./skills/image-enhancer/) | Improves the quality of images, especially screenshots, by enhancing resolution, sharpness, and clarity. Perfect for pre |
| [`kpi-dashboard-design`](./skills/kpi-dashboard-design/) | Design effective KPI dashboards with metrics selection, visualization best practices, and real-time monitoring patterns. |
| [`pricing-strategy`](./skills/pricing-strategy/) | Design pricing, packaging, and monetization strategies based on value, customer willingness to pay, and growth objective |
| [`senior-architect`](./skills/senior-architect/) | This skill should be used when the user asks to "design system architecture", "evaluate microservices vs monolith", "cre |
| [`slidev-agent-skill`](./skills/slidev-agent-skill/) | Create, edit, theme, build, and export Slidev presentations using a script-first workflow with detailed local references |
| [`sp-brainstorming`](./skills/sp-brainstorming/) | Interactive idea refinement using Socratic method to develop fully-formed designs |
| [`theme-factory`](./skills/theme-factory/) | Toolkit for styling artifacts with a theme. These artifacts can be slides, docs, reportings, HTML landing pages, etc. Th |
| [`ui-ux-pro-max`](./skills/ui-ux-pro-max/) | UI/UX design intelligence. 50 styles, 21 palettes, 50 font pairings, 20 charts, 9 stacks (React, Next.js, Vue, Svelte, S |
| [`uml-diagram-design`](./skills/uml-diagram-design/) | UML 图表设计和绘制。当用户需要创建系统架构图、类图、时序图、用例图或其他 UML 图表时使用此技能。 |
| [`video-downloader`](./skills/video-downloader/) | Download YouTube videos with customizable quality and format options. Use this skill when the user asks to download, sav |

### 🌐 Browser Automation

| Skill | 描述 |
|-------|------|
| [`browser-use`](./skills/browser-use/) | AI驱动的智能浏览器自动化工具。使用LLM理解页面并自动执行任务，比传统Playwright更智能、更省token。适用于复杂交互、动态页面、需要智能决策的浏览器操作。Chrome浏览器优先。 |
| [`chrome-automation`](./skills/chrome-automation/) | Chrome 浏览器自动化操作。当用户需要自动化浏览器操作、网页测试、数据抓取或 UI 自动化时使用此技能。 |
| [`fast-browser-use`](./skills/fast-browser-use/) | name: fast-browser-use |
| [`media-auto-publisher`](./skills/media-auto-publisher/) | 通用自媒体文章自动发布工具。支持百家号、搜狐号、知乎、微信公众号、小红书、抖音号六个平台的自动化发布流程。使用Playwright自动化实现平台导航和发布，支持通过storageState管理Cookie实现账号切换。 |
| [`playwright-automation`](./skills/playwright-automation/) | Playwright 浏览器自动化。用于自动化爬虫、数据采集、表单填写、UI 测试等需要浏览器自动化的场景。无需人工干预，适合 cron 定时任务。 |
| [`webapp-testing`](./skills/webapp-testing/) | Toolkit for interacting with and testing local web applications using Playwright. Supports verifying frontend functional |

### 🏢 Business & Strategy

| Skill | 描述 |
|-------|------|
| [`business-analyst`](./skills/business-analyst/) | name: business-analyst |
| [`market-sizing-analysis`](./skills/market-sizing-analysis/) | name: market-sizing-analysis |
| [`meeting-insights-analyzer`](./skills/meeting-insights-analyzer/) | Analyzes meeting transcripts and recordings to uncover behavioral patterns, communication insights, and actionable feedb |
| [`micro-saas-launcher`](./skills/micro-saas-launcher/) | Expert in launching small, focused SaaS products fast - the indie hacker approach to building profitable software. Cover |
| [`notion-template-business`](./skills/notion-template-business/) | Expert in building and selling Notion templates as a business - not just making templates, but building a sustainable di |
| [`startup-analyst`](./skills/startup-analyst/) | name: startup-analyst |
| [`startup-business-analyst-business-case`](./skills/startup-business-analyst-business-case/) | Generate comprehensive investor-ready business case document with market, solution, financials, and strategy  |
| [`startup-business-analyst-financial-projections`](./skills/startup-business-analyst-financial-projections/) | name: startup-business-analyst-financial-projections |
| [`startup-financial-modeling`](./skills/startup-financial-modeling/) | name: startup-financial-modeling |
| [`startup-metrics-framework`](./skills/startup-metrics-framework/) | This skill should be used when the user asks about \\\"key startup metrics", "SaaS metrics", "CAC and LTV", "unit econom |

### 📋 Project Management

| Skill | 描述 |
|-------|------|
| [`daily-rhythm`](./skills/daily-rhythm/) | Automated daily planning and reflection system with morning briefs, wind-down prompts, sleep nudges, and weekly reviews. |
| [`domain-name-brainstormer`](./skills/domain-name-brainstormer/) | Generates creative domain name ideas for your project and checks availability across multiple TLDs (.com, .io, .dev, .ai |
| [`gitlab-automation`](./skills/gitlab-automation/) | Automate GitLab project management, issues, merge requests, pipelines, branches, and user operations via Rube MCP (Compo |
| [`posthog-automation`](./skills/posthog-automation/) | Automate PostHog tasks via Rube MCP (Composio): events, feature flags, projects, user profiles, annotations. Always sear |
| [`project-management`](./skills/project-management/) | 项目管理和产品需求分析。当用户需要制定项目计划、编写 PRD 文档、管理任务或进行需求分析时使用此技能。 |
| [`project-planner`](./skills/project-planner/) | 项目路径规划与执行助手。帮助分析项目需求、规划执行路径、分解任务、识别风险、管理进度，确保项目高质量交付。 |
| [`ralph`](./skills/ralph/) | name: ralph |
| [`ralph-ceo-loop`](./skills/ralph-ceo-loop/) | > CEO 不是执行者，CEO 是调度者。Ralph 循环的本质：持续调度团队，检查反馈，调整方向，直到项目真正能跑。 |
| [`render-automation`](./skills/render-automation/) | Automate Render tasks via Rube MCP (Composio): services, deployments, projects. Always search tools first for current sc |
| [`sentry-automation`](./skills/sentry-automation/) | Automate Sentry tasks via Rube MCP (Composio): manage issues/events, configure alerts, track releases, monitor projects  |
| [`task-status`](./skills/task-status/) | Send short status descriptions in chat for long-running tasks. Use when you need to provide periodic updates during mult |
| [`team-coordinator`](./skills/team-coordinator/) | 团队协调与智能任务分配。作为高管，将用户任务拆解并分配给最合适的员工 agent 执行，协调多 agent 并行协作，汇总审核产出。 |
| [`team-daily-report`](./skills/team-daily-report/) | 每日自动生成并推送团队日报，汇总当天所有agent工作、cron执行、skill进度、关键事件。 |

### 🧠 Knowledge & Research

| Skill | 描述 |
|-------|------|
| [`memory-hygiene`](./skills/memory-hygiene/) | Audit, clean, and optimize Clawdbot's vector memory (LanceDB). Use when memory is bloated with junk, token usage is high |
| [`research-engineer`](./skills/research-engineer/) | An uncompromising Academic Research Engineer. Operates with absolute scientific rigor, objective criticism, and zero fla |
| [`search-specialist`](./skills/search-specialist/) | Expert web researcher using advanced search techniques and synthesis. Masters search operators, result filtering, and mu |

### 💬 Communication

| Skill | 描述 |
|-------|------|
| [`email-automation`](./skills/email-automation/) | 邮箱自动化：读取、搜索、草拟、发送邮件。 |
| [`email-manager`](./skills/email-manager/) | 多邮箱统一管理与智能助手。支持 Gmail、QQ邮箱等 IMAP 邮箱，定时查看邮件，AI 生成摘要和回复草稿，发送前需用户确认。 |
| [`feishu-automation`](./skills/feishu-automation/) | 飞书（Lark）全通道自动化。使用 lark-mcp 工具操作飞书多维表格（Bitable）、发送消息、管理文档、创建群组、自动化工作流等。当用户需要操作飞书平台、同步数据到飞书表格、发送飞书通知、管理飞书文档或自动化飞书业务流程时使用此技 |
| [`feishu-doc-optimizer`](./skills/feishu-doc-optimizer/) | 飞书云文档内容优化与格式美化。当用户需要优化飞书文档的排版、结构、格式、美观度时使用此技能。支持：(1) 读取飞书文档内容 (2) 优化文档结构和层次 (3) 清空并替换文档内容 (4) 通过浏览器自动化编辑文档。触发词：优化飞书文档、美化 |
| [`freshservice-automation`](./skills/freshservice-automation/) | Automate Freshservice ITSM tasks via Rube MCP (Composio): create/update tickets, bulk operations, service requests, and  |
| [`healthcare-monitor`](./skills/healthcare-monitor/) | 医疗行业企业融资监控系统。实时监控医疗健康企业的工商变更，识别融资信号，自动推送告警。支持天眼查/企查查数据采集、AI融资判断、多渠道推送。 |
| [`klaviyo-automation`](./skills/klaviyo-automation/) | Automate Klaviyo tasks via Rube MCP (Composio): manage email/SMS campaigns, inspect campaign messages, track tags, and m |
| [`outlook-automation`](./skills/outlook-automation/) | Automate Outlook tasks via Rube MCP (Composio): emails, calendar, contacts, folders, attachments. Always search tools fi |
| [`postmark-automation`](./skills/postmark-automation/) | Automate Postmark email delivery tasks via Rube MCP (Composio): send templated emails, manage templates, monitor deliver |
| [`wecom-cs-automation`](./skills/wecom-cs-automation/) | 企业微信客服自动化系统。自动同意好友添加、基于知识库的智能问答、未知问题人工介入提醒。适用于企业微信客服场景的 AI 助手机器人。 |

### 🔌 SaaS Integrations

| Skill | 描述 |
|-------|------|
| [`activecampaign-automation`](./skills/activecampaign-automation/) | Automate ActiveCampaign tasks via Rube MCP (Composio): manage contacts, tags, list subscriptions, automation enrollment, |
| [`airtable-automation`](./skills/airtable-automation/) | Automate Airtable tasks via Rube MCP (Composio): records, bases, tables, fields, views. Always search tools first for cu |
| [`amplitude-automation`](./skills/amplitude-automation/) | Automate Amplitude tasks via Rube MCP (Composio): events, user activity, cohorts, user identification. Always search too |
| [`asana-automation`](./skills/asana-automation/) | Automate Asana tasks via Rube MCP (Composio): tasks, projects, sections, teams, workspaces. Always search tools first fo |
| [`basecamp-automation`](./skills/basecamp-automation/) | Automate Basecamp project management, to-dos, messages, people, and to-do list organization via Rube MCP (Composio). Alw |
| [`bitbucket-automation`](./skills/bitbucket-automation/) | Automate Bitbucket repositories, pull requests, branches, issues, and workspace management via Rube MCP (Composio). Alwa |
| [`box-automation`](./skills/box-automation/) | Automate Box cloud storage operations including file upload/download, search, folder management, sharing, collaborations |
| [`brevo-automation`](./skills/brevo-automation/) | Automate Brevo (Sendinblue) tasks via Rube MCP (Composio): manage email campaigns, create/edit templates, track senders, |
| [`cal-com-automation`](./skills/cal-com-automation/) | Automate Cal.com tasks via Rube MCP (Composio): manage bookings, check availability, configure webhooks, and handle team |
| [`calendly-automation`](./skills/calendly-automation/) | Automate Calendly scheduling, event management, invitee tracking, availability checks, and organization administration v |
| [`canva-automation`](./skills/canva-automation/) | Automate Canva tasks via Rube MCP (Composio): designs, exports, folders, brand templates, autofill. Always search tools  |
| [`canvas-design`](./skills/canvas-design/) | Create beautiful visual art in .png and .pdf documents using design philosophy. You should use this skill when the user  |
| [`circleci-automation`](./skills/circleci-automation/) | Automate CircleCI tasks via Rube MCP (Composio): trigger pipelines, monitor workflows/jobs, retrieve artifacts and test  |
| [`clickup-automation`](./skills/clickup-automation/) | Automate ClickUp project management including tasks, spaces, folders, lists, comments, and team operations via Rube MCP  |
| [`close-automation`](./skills/close-automation/) | Automate Close CRM tasks via Rube MCP (Composio): create leads, manage calls/SMS, handle tasks, and track notes. Always  |
| [`coda-automation`](./skills/coda-automation/) | Automate Coda tasks via Rube MCP (Composio): manage docs, pages, tables, rows, formulas, permissions, and publishing. Al |
| [`confluence-automation`](./skills/confluence-automation/) | Automate Confluence page creation, content search, space management, labels, and hierarchy navigation via Rube MCP (Comp |
| [`convertkit-automation`](./skills/convertkit-automation/) | Automate ConvertKit (Kit) tasks via Rube MCP (Composio): manage subscribers, tags, broadcasts, and broadcast stats. Alwa |
| [`datadog-automation`](./skills/datadog-automation/) | Automate Datadog tasks via Rube MCP (Composio): query metrics, search logs, manage monitors/dashboards, create events an |
| [`discord-automation`](./skills/discord-automation/) | Automate Discord tasks via Rube MCP (Composio): messages, channels, roles, webhooks, reactions. Always search tools firs |
| [`docusign-automation`](./skills/docusign-automation/) | Automate DocuSign tasks via Rube MCP (Composio): templates, envelopes, signatures, document management. Always search to |
| [`dropbox-automation`](./skills/dropbox-automation/) | Automate Dropbox file management, sharing, search, uploads, downloads, and folder operations via Rube MCP (Composio). Al |
| [`facebook-automation`](./skills/facebook-automation/) | Automate Facebook tasks via Rube MCP (Composio): pages, posts, insights, comments, and ad accounts. Always search tools  |
| [`freshdesk-automation`](./skills/freshdesk-automation/) | Automate Freshdesk helpdesk operations including tickets, contacts, companies, notes, and replies via Rube MCP (Composio |
| [`gmail-automation`](./skills/gmail-automation/) | Automate Gmail tasks via Rube MCP (Composio): send/reply, search, labels, drafts, attachments. Always search tools first |
| [`grafana-dashboards`](./skills/grafana-dashboards/) | Create and manage production Grafana dashboards for real-time visualization of system and application metrics. Use when  |
| [`helpdesk-automation`](./skills/helpdesk-automation/) | Automate HelpDesk tasks via Rube MCP (Composio): list tickets, manage views, use canned responses, and configure custom  |
| [`hubspot-automation`](./skills/hubspot-automation/) | Automate HubSpot CRM operations (contacts, companies, deals, tickets, properties) via Rube MCP using Composio integratio |
| [`instagram-automation`](./skills/instagram-automation/) | Automate Instagram tasks via Rube MCP (Composio): create posts, carousels, manage media, get insights, and publishing li |
| [`intercom-automation`](./skills/intercom-automation/) | Automate Intercom tasks via Rube MCP (Composio): conversations, contacts, companies, segments, admins. Always search too |
| [`jira-automation`](./skills/jira-automation/) | Automate Jira tasks via Rube MCP (Composio): issues, projects, sprints, boards, comments, users. Always search tools fir |
| [`linear-automation`](./skills/linear-automation/) | Automate Linear tasks via Rube MCP (Composio): issues, projects, cycles, teams, labels. Always search tools first for cu |
| [`mailchimp-automation`](./skills/mailchimp-automation/) | Automate Mailchimp email marketing including campaigns, audiences, subscribers, segments, and analytics via Rube MCP (Co |
| [`make-automation`](./skills/make-automation/) | Automate Make (Integromat) tasks via Rube MCP (Composio): operations, enums, language and timezone lookups. Always searc |
| [`microsoft-teams-automation`](./skills/microsoft-teams-automation/) | Automate Microsoft Teams tasks via Rube MCP (Composio): send messages, manage channels, create meetings, handle chats, a |
| [`miro-automation`](./skills/miro-automation/) | Automate Miro tasks via Rube MCP (Composio): boards, items, sticky notes, frames, sharing, connectors. Always search too |
| [`mixpanel-automation`](./skills/mixpanel-automation/) | Automate Mixpanel tasks via Rube MCP (Composio): events, segmentation, funnels, cohorts, user profiles, JQL queries. Alw |
| [`monday-automation`](./skills/monday-automation/) | Automate Monday.com work management including boards, items, columns, groups, subitems, and updates via Rube MCP (Compos |
| [`notion-automation`](./skills/notion-automation/) | 自动化 Notion 操作。当用户需要管理 Notion 页面、数据库、块内容、项目跟踪或进行内容组织和搜索时使用此技能。 |
| [`pagerduty-automation`](./skills/pagerduty-automation/) | Automate PagerDuty tasks via Rube MCP (Composio): manage incidents, services, schedules, escalation policies, and on-cal |
| [`pipedrive-automation`](./skills/pipedrive-automation/) | Automate Pipedrive CRM operations including deals, contacts, organizations, activities, notes, and pipeline management v |
| [`salesforce-automation`](./skills/salesforce-automation/) | Automate Salesforce tasks via Rube MCP (Composio): leads, contacts, accounts, opportunities, SOQL queries. Always search |
| [`segment-automation`](./skills/segment-automation/) | Automate Segment tasks via Rube MCP (Composio): track events, identify users, manage groups, page views, aliases, batch  |
| [`shopify-automation`](./skills/shopify-automation/) | Automate Shopify tasks via Rube MCP (Composio): products, orders, customers, inventory, collections. Always search tools |
| [`slack-automation`](./skills/slack-automation/) | Automate Slack messaging, channel management, search, reactions, and threads via Rube MCP (Composio). Send messages, sea |
| [`square-automation`](./skills/square-automation/) | Automate Square tasks via Rube MCP (Composio): payments, orders, invoices, locations. Always search tools first for curr |
| [`stripe-automation`](./skills/stripe-automation/) | Automate Stripe tasks via Rube MCP (Composio): customers, charges, subscriptions, invoices, products, refunds. Always se |
| [`supabase-automation`](./skills/supabase-automation/) | Automate Supabase database queries, table management, project administration, storage, edge functions, and SQL execution |
| [`sysadmin-toolbox`](./skills/sysadmin-toolbox/) | Tool discovery and shell one-liner reference for sysadmin, DevOps, and security tasks. AUTO-CONSULT this skill when the  |
| [`telegram-automation`](./skills/telegram-automation/) | Automate Telegram tasks via Rube MCP (Composio): send messages, manage chats, share photos/documents, and handle bot com |
| [`tiktok-automation`](./skills/tiktok-automation/) | Automate TikTok tasks via Rube MCP (Composio): upload/publish videos, post photos, manage content, and view user profile |
| [`todoist-automation`](./skills/todoist-automation/) | Automate Todoist task management, projects, sections, filtering, and bulk operations via Rube MCP (Composio). Always sea |
| [`trello-automation`](./skills/trello-automation/) | Automate Trello boards, cards, and workflows via Rube MCP (Composio). Create cards, manage lists, assign members, and se |
| [`vercel-automation`](./skills/vercel-automation/) | Automate Vercel tasks via Rube MCP (Composio): manage deployments, domains, DNS, env vars, projects, and teams. Always s |
| [`webflow-automation`](./skills/webflow-automation/) | Automate Webflow CMS collections, site publishing, page management, asset uploads, and ecommerce orders via Rube MCP (Co |
| [`wecom-automation`](./skills/wecom-automation/) | 企业微信个人账号直连自动化。基于 Wechaty 框架实现企业微信消息接收、自动同意好友、知识库问答、人工介入提醒。适用于企业微信个人机器人和自动化助手场景。 |
| [`whatsapp-automation`](./skills/whatsapp-automation/) | Automate WhatsApp Business tasks via Rube MCP (Composio): send messages, manage templates, upload media, and handle cont |
| [`youtube-automation`](./skills/youtube-automation/) | Automate YouTube tasks via Rube MCP (Composio): upload videos, manage playlists, search content, get analytics, and hand |
| [`zendesk-automation`](./skills/zendesk-automation/) | Automate Zendesk tasks via Rube MCP (Composio): tickets, users, organizations, replies. Always search tools first for cu |
| [`zoho-crm-automation`](./skills/zoho-crm-automation/) | Automate Zoho CRM tasks via Rube MCP (Composio): create/update records, search contacts, manage leads, and convert leads |
| [`zoom-automation`](./skills/zoom-automation/) | Automate Zoom meeting creation, management, recordings, webinars, and participant tracking via Rube MCP (Composio). Alwa |

### ⚙️ DevOps & Infra

| Skill | 描述 |
|-------|------|
| [`aws-cost-cleanup`](./skills/aws-cost-cleanup/) | Automated cleanup of unused AWS resources to reduce costs |
| [`cost-optimization`](./skills/cost-optimization/) | Optimize cloud costs through resource rightsizing, tagging strategies, reserved instances, and spending analysis. Use wh |
| [`docker-deployment`](./skills/docker-deployment/) | Docker container deployment with Nginx HTTPS configuration and Cloudflare Tunnel integration. Use when deploying web app |
| [`file-cleaner`](./skills/file-cleaner/) | 系统文件清理工具。扫描和识别大文件、垃圾文件（临时文件、缓存、日志、备份等），提供交互式清理界面让用户选择删除。当用户需要清理磁盘空间、整理系统文件、查找大文件、删除垃圾文件或释放存储空间时使用此技能。 |
| [`linux-service-triage`](./skills/linux-service-triage/) | Diagnoses common Linux service issues using logs, systemd/PM2, file permissions, Nginx reverse proxy checks, and DNS san |
| [`linux-troubleshooting`](./skills/linux-troubleshooting/) | Linux system troubleshooting workflow for diagnosing and resolving system issues, performance problems, and service fail |
| [`senior-devops`](./skills/senior-devops/) | Comprehensive DevOps skill for CI/CD, infrastructure automation, containerization, and cloud platforms (AWS, GCP, Azure) |

### 🔒 Security

| Skill | 描述 |
|-------|------|
| [`openssf-security`](./skills/openssf-security/) | Comprehensive OpenSSF security guidance for software projects. Invoke this skill when developers need help with: - Creat |
| [`performing-security-code-review`](./skills/performing-security-code-review/) | Execute this skill enables AI assistant to conduct a security-focused code review using the security-agent plugin. it an |
| [`security-audit`](./skills/security-audit/) | Comprehensive security auditing for Clawdbot deployments. Scans for exposed credentials, open ports, weak configs, and v |
| [`security-monitor`](./skills/security-monitor/) | Real-time security monitoring for Clawdbot. Detects intrusions, unusual API calls, credential usage patterns, and alerts |

### ⚖️ Legal & Compliance

| Skill | 描述 |
|-------|------|
| [`web-design-guidelines`](./skills/web-design-guidelines/) | Review UI code for Web Interface Guidelines compliance. Use when asked to "review my UI", "check accessibility", "audit  |

### 🧩 Other

| Skill | 描述 |
|-------|------|
| [`api-toolkit`](./skills/api-toolkit/) | 通用 API 调用工具包，用于快速接入任何 RESTful API。 |
| [`context-recovery`](./skills/context-recovery/) | Automatically recover working context after session compaction or when continuation is implied but context is missing. W |
| [`deepwork-tracker`](./skills/deepwork-tracker/) | Track deep work sessions locally (start/stop/status) and generate a GitHub-contribution-graph style minutes-per-day heat |
| [`developer-growth-analysis`](./skills/developer-growth-analysis/) | Analyzes your recent Claude Code chat history to identify coding patterns, development gaps, and areas for improvement,  |
| [`doc-coauthoring`](./skills/doc-coauthoring/) | Guide users through a structured workflow for co-authoring documentation. Use when user wants to write documentation, pr |
| [`google-calendar-automation`](./skills/google-calendar-automation/) | Automate Google Calendar events, scheduling, availability checks, and attendee management via Rube MCP (Composio). Creat |
| [`google-drive-automation`](./skills/google-drive-automation/) | Automate Google Drive file operations (upload, download, search, share, organize) via Rube MCP (Composio). Upload/downlo |
| [`pptx`](./skills/pptx/) | Presentation creation, editing, and analysis. When Claude needs to work with presentations (.pptx files) for: (1) Creati |
| [`rss-automation`](./skills/rss-automation/) | RSS feed aggregation and monitoring. Parse RSS/Atom feeds, filter entries, track new items, and integrate with notificat |
| [`skill-creator`](./skills/skill-creator/) | Guide for creating effective skills. This skill should be used when users want to create a new skill (or update an exist |
| [`skill-search`](./skills/skill-search/) | 从GitHub和SkillsMP等官方网站搜索符合用户描述的优质skill，供用户选择，然后自动克隆并安装相应skill到全局~/.claude/skills/目录。当用户需要搜索或安装新skill时触发此技能。 |
| [`tech-decision`](./skills/tech-decision/) | This skill should be used when the user asks to "기술 의사결정", "뭐 쓸지 고민", "A vs B", "비교 분석", "라이브러리 선택", "아키텍처 결정", "어떤 걸 써야 |
| [`twitter-automation`](./skills/twitter-automation/) | Automate Twitter/X tasks via Rube MCP (Composio): posts, search, users, bookmarks, lists, media. Always search tools fir |

## 📦 安装

```bash
# 克隆仓库
git clone https://github.com/aAAaqwq/AGI-Super-Skills.git

# 复制 skill 到 OpenClaw 目录
cp -r AGI-Super-Skills/skills/<skill-name> ~/.openclaw/skills/

# 或创建软链接（方便更新）
ln -s $(pwd)/AGI-Super-Skills/skills/<skill-name> ~/.openclaw/skills/
```

## 📄 许可证

MIT
