# AGI-Super-Skills 🦞✨

> OpenClaw 完整环境备份与快速部署仓库 — 339+ Skills、27 Agents、多模型配置、MCP 集成

[![Last Updated](https://img.shields.io/badge/Last%20Updated-2026--03--01-blue)]()
[![Skills](https://img.shields.io/badge/Skills-339-green)]()
[![Agents](https://img.shields.io/badge/Agents-27-orange)]()
[![License](https://img.shields.io/badge/License-MIT-yellow)]()

## 快速导航

- [🤖 AI / 生成类](#-ai--生成类)
- [💻 开发工具](#-开发工具)
- [🔧 基础设施 / DevOps](#-基础设施--devops)
- [📊 项目管理 / 协作](#-项目管理--协作)
- [📝 内容 / 写作](#-内容--写作)
- [🌐 平台自动化（SaaS 集成）](#-平台自动化saas-集成)
- [🔍 研究 / 数据](#-研究--数据)
- [💰 金融 / 商业](#-金融--商业)
- [📈 量化交易 / 加密货币](#-量化交易--加密货币)
- [🎯 营销 / SEO / 增长](#-营销--seo--增长)
- [🏥 健康](#-健康)
- [🛠 OpenClaw 内部](#-openclaw-内部)
- [🌐 浏览器 / 自动化](#-浏览器--自动化-1)
- [🔐 安全](#-安全)
- [🧠 AI 框架 / 思维模式](#-ai-框架--思维模式)
- [📦 其他工具](#-其他工具)
- [🤖 Agents 列表](#-agents-列表)
- [📡 模型 Provider](#-模型-provider)
- [🚀 快速部署](#-快速部署)

## 目录结构

```
AGI-Super-Skills/
├── skills/          # 339 个 OpenClaw Skills（自动化、开发、AI生成等）
├── agents/          # 27 个 Agent 配置（角色定义、模型绑定、系统提示词）
├── config/          # OpenClaw 核心配置模板（已脱敏，可直接复制使用）
├── workspace/       # Workspace 文件（AGENTS.md, SOUL.md, IDENTITY.md 等）
├── mcp/             # MCP Server 配置与说明
└── README.md        # 本文件
```

## Skills 列表

### 🤖 AI / 生成类
| Skill | 说明 |
|-------|------|
| [ai-image-generation](skills/ai-image-generation/) | AI 图像生成 |
| [ai-video-gen](skills/ai-video-gen/) | AI 视频生成 |
| [fal-ai](skills/fal-ai/) | Fal.ai 图像生成 |
| [image-enhancer](skills/image-enhancer/) | 图像增强 |
| [krea-api](skills/krea-api/) | Krea AI API |
| [multimodal-gen](skills/multimodal-gen/) | 多模态内容生成 |
| [pollinations](skills/pollinations/) | Pollinations 图像生成 |
| [veo](skills/veo/) | Google Veo 视频生成 |
| [veo3-video-gen](skills/veo3-video-gen/) | Veo 3 视频生成 |
| [ffmpeg-video-editor](skills/ffmpeg-video-editor/) | FFmpeg 视频编辑 |
| [video-downloader](skills/video-downloader/) | 视频下载 |
| [video-frames](skills/video-frames/) | 视频帧提取 |
| [podcast-generation](skills/podcast-generation/) | 播客生成 |

### 💻 开发工具
| Skill | 说明 |
|-------|------|
| [backend-development](skills/backend-development/) | 后端开发 |
| [frontend-development](skills/frontend-development/) | 前端开发 |
| [frontend-design](skills/frontend-design/) | 前端设计 |
| [electron-app-dev](skills/electron-app-dev/) | Electron 应用开发 |
| [debug-pro](skills/debug-pro/) | 高级调试 |
| [systematic-debugging](skills/systematic-debugging/) | 系统化调试 |
| [tdd-guide](skills/tdd-guide/) | TDD 指南 |
| [test-runner](skills/test-runner/) | 测试运行器 |
| [test-automator](skills/test-automator/) | 测试自动化 |
| [webapp-testing](skills/webapp-testing/) | Web 应用测试 |
| [commit-analyzer](skills/commit-analyzer/) | Commit 分析 |
| [conventional-commits](skills/conventional-commits/) | 约定式提交 |
| [changelog-generator](skills/changelog-generator/) | 变更日志生成 |
| [senior-architect](skills/senior-architect/) | 高级架构师 |
| [senior-devops](skills/senior-devops/) | 高级 DevOps |
| [multi-coding-agent](skills/multi-coding-agent/) | 多编码 Agent |
| [claude-optimised](skills/claude-optimised/) | Claude 优化 |
| [prompt-optimizer](skills/prompt-optimizer/) | Prompt 优化 |
| [uml-diagram-design](skills/uml-diagram-design/) | UML 图设计 |
| [architecture-decision-records](skills/architecture-decision-records/) | 架构决策记录 |
| [react-best-practices](skills/react-best-practices/) | React 最佳实践 |
| [react-component-generator](skills/react-component-generator/) | React 组件生成器 |
| [sql-optimization-patterns](skills/sql-optimization-patterns/) | SQL 优化模式 |
| [sql-pro](skills/sql-pro/) | SQL 专家 |
| [python-performance-optimization](skills/python-performance-optimization/) | Python 性能优化 |
| [ml-engineer](skills/ml-engineer/) | ML 工程师 |
| [research-engineer](skills/research-engineer/) | 研究工程师 |
| [ui-ux-pro-max](skills/ui-ux-pro-max/) | UI/UX 专家 |
| [web-design-guidelines](skills/web-design-guidelines/) | Web 设计指南 |
| [requesting-code-review](skills/requesting-code-review/) | 代码审查请求 |
| [vibe-code-auditor](skills/vibe-code-auditor/) | Vibe 代码审计 |
| [slidev-agent-skill](skills/slidev-agent-skill/) | Slidev 演示文稿 |
| [data-engineering-data-pipeline](skills/data-engineering-data-pipeline/) | 数据管道工程 |
| [subagent-driven-development](skills/subagent-driven-development/) | 子Agent驱动开发 |

### 🔧 基础设施 / DevOps
| Skill | 说明 |
|-------|------|
| [docker-deployment](skills/docker-deployment/) | Docker 部署 |
| [docker-essentials](skills/docker-essentials/) | Docker 基础 |
| [kubernetes-deployment](skills/kubernetes-deployment/) | Kubernetes 部署 |
| [env-setup](skills/env-setup/) | 环境配置 |
| [linux-service-triage](skills/linux-service-triage/) | Linux 服务排障 |
| [linux-troubleshooting](skills/linux-troubleshooting/) | Linux 故障排查 |
| [sysadmin-toolbox](skills/sysadmin-toolbox/) | 系统管理工具箱 |
| [security-audit](skills/security-audit/) | 安全审计 |
| [security-monitor](skills/security-monitor/) | 安全监控 |
| [render-automation](skills/render-automation/) | Render 自动化 |
| [vercel-automation](skills/vercel-automation/) | Vercel 自动化 |
| [grafana-dashboards](skills/grafana-dashboards/) | Grafana 仪表板 |
| [cost-optimization](skills/cost-optimization/) | 成本优化 |
| [aws-cost-cleanup](skills/aws-cost-cleanup/) | AWS 成本清理 |

### 📊 项目管理 / 协作
| Skill | 说明 |
|-------|------|
| [project-management](skills/project-management/) | 项目管理 |
| [project-planner](skills/project-planner/) | 项目规划 |
| [project-context-sync](skills/project-context-sync/) | 项目上下文同步 |
| [task-status](skills/task-status/) | 任务状态追踪 |
| [team-daily-report](skills/team-daily-report/) | 团队日报 |
| [team-coordinator](skills/team-coordinator/) | 团队协调 |
| [meeting-insights-analyzer](skills/meeting-insights-analyzer/) | 会议洞察分析 |
| [deepwork-tracker](skills/deepwork-tracker/) | 深度工作追踪 |
| [daily-rhythm](skills/daily-rhythm/) | 日常节奏管理 |
| [planning-with-files](skills/planning-with-files/) | 文件规划 |
| [parallel-agents](skills/parallel-agents/) | 并行 Agent 调度 |
| [ralph-ceo-loop](skills/ralph-ceo-loop/) | Ralph CEO 循环 |

### 📝 内容 / 写作
| Skill | 说明 |
|-------|------|
| [content-research-writer](skills/content-research-writer/) | 内容研究写作 |
| [content-creator](skills/content-creator/) | 内容创作者 |
| [content-marketer](skills/content-marketer/) | 内容营销 |
| [seo-content-writing](skills/seo-content-writing/) | SEO 内容写作 |
| [seo-content-writer](skills/seo-content-writer/) | SEO 写手 |
| [copy-editing](skills/copy-editing/) | 文案编辑 |
| [copywriting](skills/copywriting/) | 文案写作 |
| [doc-coauthoring](skills/doc-coauthoring/) | 文档协作 |
| [brand-guidelines](skills/brand-guidelines/) | 品牌指南 |
| [media-auto-publisher](skills/media-auto-publisher/) | 媒体自动发布 |
| [internal-comms](skills/internal-comms/) | 内部通讯 |
| [social-content](skills/social-content/) | 社交媒体内容 |
| [wiki-page-writer](skills/wiki-page-writer/) | Wiki 页面写作 |
| [wiki-qa](skills/wiki-qa/) | Wiki 问答 |
| [moltbook](skills/moltbook/) | Moltbook 电子书 |
| [moltbook-interact](skills/moltbook-interact/) | Moltbook 交互 |
| [moltbook-registry](skills/moltbook-registry/) | Moltbook 注册中心 |
| [docx](skills/docx/) | DOCX 文档处理 |
| [docx-perfect](skills/docx-perfect/) | DOCX 完美处理 |
| [pdf](skills/pdf/) | PDF 处理 |
| [pptx](skills/pptx/) | PPTX 演示文稿 |
| [xlsx](skills/xlsx/) | Excel 处理 |
| [data-storytelling](skills/data-storytelling/) | 数据叙事 |
| [xiaohongshu-workflow](skills/xiaohongshu-workflow/) | 小红书工作流 |
| [content-source-aggregator](skills/content-source-aggregator/) | 内容源聚合 |

### 🌐 平台自动化（SaaS 集成）
| Skill | 说明 |
|-------|------|
| [github-automation](skills/github-automation/) | GitHub |
| [gitlab-automation](skills/gitlab-automation/) | GitLab |
| [bitbucket-automation](skills/bitbucket-automation/) | Bitbucket |
| [slack-automation](skills/slack-automation/) | Slack |
| [discord-automation](skills/discord-automation/) | Discord |
| [telegram-automation](skills/telegram-automation/) | Telegram |
| [telegram-push](skills/telegram-push/) | Telegram 推送 |
| [whatsapp-automation](skills/whatsapp-automation/) | WhatsApp |
| [feishu-automation](skills/feishu-automation/) | 飞书 |
| [feishu-channel](skills/feishu-channel/) | 飞书频道 |
| [feishu-doc-optimizer](skills/feishu-doc-optimizer/) | 飞书文档优化 |
| [wecom-automation](skills/wecom-automation/) | 企业微信 |
| [wecom-cs-automation](skills/wecom-cs-automation/) | 企微客服 |
| [wechat-channel](skills/wechat-channel/) | 微信视频号 |
| [notion-automation](skills/notion-automation/) | Notion |
| [jira-automation](skills/jira-automation/) | Jira |
| [linear-automation](skills/linear-automation/) | Linear |
| [trello-automation](skills/trello-automation/) | Trello |
| [asana-automation](skills/asana-automation/) | Asana |
| [clickup-automation](skills/clickup-automation/) | ClickUp |
| [monday-automation](skills/monday-automation/) | Monday |
| [basecamp-automation](skills/basecamp-automation/) | Basecamp |
| [confluence-automation](skills/confluence-automation/) | Confluence |
| [coda-automation](skills/coda-automation/) | Coda |
| [miro-automation](skills/miro-automation/) | Miro |
| [figma-automation](skills/figma-automation/) | Figma |
| [canva-automation](skills/canva-automation/) | Canva |
| [hubspot-automation](skills/hubspot-automation/) | HubSpot |
| [salesforce-automation](skills/salesforce-automation/) | Salesforce |
| [pipedrive-automation](skills/pipedrive-automation/) | Pipedrive |
| [close-automation](skills/close-automation/) | Close CRM |
| [zoho-crm-automation](skills/zoho-crm-automation/) | Zoho CRM |
| [stripe-automation](skills/stripe-automation/) | Stripe |
| [square-automation](skills/square-automation/) | Square |
| [shopify-automation](skills/shopify-automation/) | Shopify |
| [gmail-automation](skills/gmail-automation/) | Gmail |
| [outlook-automation](skills/outlook-automation/) | Outlook |
| [email-automation](skills/email-automation/) | 邮件自动化 |
| [email-manager](skills/email-manager/) | 邮件管理 |
| [google-calendar-automation](skills/google-calendar-automation/) | Google Calendar |
| [google-drive-automation](skills/google-drive-automation/) | Google Drive |
| [googlesheets-automation](skills/googlesheets-automation/) | Google Sheets |
| [google-analytics-automation](skills/google-analytics-automation/) | Google Analytics |
| [one-drive-automation](skills/one-drive-automation/) | OneDrive |
| [dropbox-automation](skills/dropbox-automation/) | Dropbox |
| [box-automation](skills/box-automation/) | Box |
| [microsoft-teams-automation](skills/microsoft-teams-automation/) | Microsoft Teams |
| [zoom-automation](skills/zoom-automation/) | Zoom |
| [cal-com-automation](skills/cal-com-automation/) | Cal.com |
| [calendly-automation](skills/calendly-automation/) | Calendly |
| [todoist-automation](skills/todoist-automation/) | Todoist |
| [airtable-automation](skills/airtable-automation/) | Airtable |
| [nocodb](skills/nocodb/) | NocoDB |
| [supabase](skills/supabase/) | Supabase |
| [supabase-automation](skills/supabase-automation/) | Supabase 自动化 |
| [webflow-automation](skills/webflow-automation/) | Webflow |
| [make-automation](skills/make-automation/) | Make (Integromat) |
| [sendgrid-automation](skills/sendgrid-automation/) | SendGrid |
| [postmark-automation](skills/postmark-automation/) | Postmark |
| [mailchimp-automation](skills/mailchimp-automation/) | Mailchimp |
| [convertkit-automation](skills/convertkit-automation/) | ConvertKit |
| [brevo-automation](skills/brevo-automation/) | Brevo |
| [klaviyo-automation](skills/klaviyo-automation/) | Klaviyo |
| [activecampaign-automation](skills/activecampaign-automation/) | ActiveCampaign |
| [instagram-automation](skills/instagram-automation/) | Instagram |
| [linkedin-automation](skills/linkedin-automation/) | LinkedIn |
| [twitter-automation](skills/twitter-automation/) | Twitter/X |
| [reddit-automation](skills/reddit-automation/) | Reddit |
| [tiktok-automation](skills/tiktok-automation/) | TikTok |
| [youtube-automation](skills/youtube-automation/) | YouTube |
| [facebook-automation](skills/facebook-automation/) | Facebook |
| [amplitude-automation](skills/amplitude-automation/) | Amplitude |
| [mixpanel-automation](skills/mixpanel-automation/) | Mixpanel |
| [posthog-automation](skills/posthog-automation/) | PostHog |
| [segment-automation](skills/segment-automation/) | Segment |
| [datadog-automation](skills/datadog-automation/) | Datadog |
| [sentry-automation](skills/sentry-automation/) | Sentry |
| [pagerduty-automation](skills/pagerduty-automation/) | PagerDuty |
| [circleci-automation](skills/circleci-automation/) | CircleCI |
| [freshdesk-automation](skills/freshdesk-automation/) | Freshdesk |
| [freshservice-automation](skills/freshservice-automation/) | Freshservice |
| [zendesk-automation](skills/zendesk-automation/) | Zendesk |
| [helpdesk-automation](skills/helpdesk-automation/) | Helpdesk |
| [intercom-automation](skills/intercom-automation/) | Intercom |
| [docusign-automation](skills/docusign-automation/) | DocuSign |
| [rss-automation](skills/rss-automation/) | RSS 订阅 |

### 🔍 研究 / 数据
| Skill | 说明 |
|-------|------|
| [web-scraping-automation](skills/web-scraping-automation/) | 网页抓取 |
| [firecrawl](skills/firecrawl/) | Firecrawl 爬虫 |
| [firecrawl-skills](skills/firecrawl-skills/) | Firecrawl 技能 |
| [google-web-search](skills/google-web-search/) | Google 搜索 |
| [web-search](skills/web-search/) | Web 搜索 |
| [serper](skills/serper/) | Serper 搜索 API |
| [tavily](skills/tavily/) | Tavily 搜索 |
| [search-specialist](skills/search-specialist/) | 搜索专家 |
| [readwise](skills/readwise/) | Readwise 阅读 |
| [arxiv-automation](skills/arxiv-automation/) | arXiv 论文 |
| [deep-research](skills/deep-research/) | 深度研究 |
| [competitive-ads-extractor](skills/competitive-ads-extractor/) | 竞品广告提取 |
| [lead-research-assistant](skills/lead-research-assistant/) | 线索研究助手 |
| [osint-graph-analyzer](skills/osint-graph-analyzer/) | OSINT 图谱分析 |
| [developer-growth-analysis](skills/developer-growth-analysis/) | 开发者增长分析 |
| [langsmith-fetch](skills/langsmith-fetch/) | LangSmith 数据获取 |
| [news-daily](skills/news-daily/) | 每日新闻 |
| [analytics-tracking](skills/analytics-tracking/) | 分析追踪 |
| [football-data](skills/football-data/) | 足球数据 |
| [geo-agent](skills/geo-agent/) | 地理信息 Agent |

### 💰 金融 / 商业
| Skill | 说明 |
|-------|------|
| [expense-tracker-pro](skills/expense-tracker-pro/) | 费用追踪 |
| [invoice-organizer](skills/invoice-organizer/) | 发票整理 |
| [cost-report](skills/cost-report/) | 成本报告 |
| [billing-automation](skills/billing-automation/) | 账单自动化 |
| [payment-integration](skills/payment-integration/) | 支付集成 |
| [tech-decision](skills/tech-decision/) | 技术决策 |
| [domain-name-brainstormer](skills/domain-name-brainstormer/) | 域名头脑风暴 |
| [business-analyst](skills/business-analyst/) | 商业分析 |
| [startup-analyst](skills/startup-analyst/) | 创业分析 |
| [startup-business-analyst-business-case](skills/startup-business-analyst-business-case/) | 创业商业案例 |
| [startup-financial-modeling](skills/startup-financial-modeling/) | 创业财务建模 |
| [startup-metrics-framework](skills/startup-metrics-framework/) | 创业指标框架 |
| [market-sizing-analysis](skills/market-sizing-analysis/) | 市场规模分析 |
| [pricing-strategy](skills/pricing-strategy/) | 定价策略 |
| [micro-saas-launcher](skills/micro-saas-launcher/) | Micro-SaaS 启动器 |
| [notion-template-business](skills/notion-template-business/) | Notion 模板商业 |
| [kpi-dashboard-design](skills/kpi-dashboard-design/) | KPI 仪表板设计 |
| [moneyclaw](skills/moneyclaw/) | MoneyClaw 赚钱引擎 |

### 📈 量化交易 / 加密货币
| Skill | 说明 |
|-------|------|
| [polymarket-profit](skills/polymarket-profit/) | Polymarket 交易 |
| [polymarket-trading](skills/polymarket-trading/) | Polymarket 交易策略 |
| [polymarket-data](skills/polymarket-data/) | Polymarket 数据 |
| [polymarket-skill](skills/polymarket-skill/) | Polymarket 技能 |
| [polyclaw](skills/polyclaw/) | PolyClaw 交易 |
| [openclaw-ai-polymarket-trading-bot](skills/openclaw-ai-polymarket-trading-bot/) | OpenClaw Polymarket 机器人 |
| [openclaw-polymarket-skills](skills/openclaw-polymarket-skills/) | OpenClaw Polymarket 技能 |
| [openclaw-crypto-ai-quant](skills/openclaw-crypto-ai-quant/) | OpenClaw 加密量化 |
| [quant-analyst](skills/quant-analyst/) | 量化分析师 |
| [quant-subagents](skills/quant-subagents/) | 量化子Agent |
| [arbitrage-opportunity-finder](skills/arbitrage-opportunity-finder/) | 套利机会发现 |
| [backtesting-frameworks](skills/backtesting-frameworks/) | 回测框架 |
| [crypto-signal-generator](skills/crypto-signal-generator/) | 加密信号生成 |
| [crypto-derivatives-tracker](skills/crypto-derivatives-tracker/) | 加密衍生品追踪 |
| [crypto-portfolio-tracker](skills/crypto-portfolio-tracker/) | 加密组合追踪 |
| [crypto-portfolio-management](skills/crypto-portfolio-management/) | 加密组合管理 |
| [crypto-bd-agent](skills/crypto-bd-agent/) | 加密BD Agent |
| [market-price-tracker](skills/market-price-tracker/) | 市场价格追踪 |
| [market-movers-scanner](skills/market-movers-scanner/) | 市场异动扫描 |
| [market-sentiment-analyzer](skills/market-sentiment-analyzer/) | 市场情绪分析 |
| [options-flow-analyzer](skills/options-flow-analyzer/) | 期权流分析 |
| [risk-metrics-calculation](skills/risk-metrics-calculation/) | 风险指标计算 |
| [trading-strategy-backtester](skills/trading-strategy-backtester/) | 交易策略回测 |
| [trading-assistant](skills/trading-assistant/) | 交易助手 |
| [whale-alert-monitor](skills/whale-alert-monitor/) | 巨鲸警报监控 |
| [bankr](skills/bankr/) | Bankr 加密交易 |
| [bankr-signals](skills/bankr-signals/) | Bankr 交易信号 |
| [clanker](skills/clanker/) | Clanker 代币部署 |
| [erc-8004](skills/erc-8004/) | ERC-8004 链上身份 |
| [token-guard](skills/token-guard/) | Token 安全守卫 |
| [defi-risk-assessment](skills/defi-risk-assessment/) | DeFi 风险评估 |
| [sperax-defi-guide](skills/sperax-defi-guide/) | Sperax DeFi 指南 |
| [unum-strat](skills/unum-strat/) | Unum 策略 |
| [autonomys-skills](skills/autonomys-skills/) | Autonomys 技能 |

### 🎯 营销 / SEO / 增长
| Skill | 说明 |
|-------|------|
| [ai-marketing-skills](skills/ai-marketing-skills/) | AI 营销技能 |
| [marketing-ideas](skills/marketing-ideas/) | 营销创意 |
| [marketing-psychology](skills/marketing-psychology/) | 营销心理学 |
| [paid-ads](skills/paid-ads/) | 付费广告 |
| [competitor-alternatives](skills/competitor-alternatives/) | 竞品替代分析 |
| [seo-audit](skills/seo-audit/) | SEO 审计 |
| [seo-meta-optimizer](skills/seo-meta-optimizer/) | SEO Meta 优化 |
| [programmatic-seo](skills/programmatic-seo/) | 程序化 SEO |
| [twitter-algorithm-optimizer](skills/twitter-algorithm-optimizer/) | Twitter 算法优化 |

### 🏥 健康
| Skill | 说明 |
|-------|------|
| [healthcare-monitor](skills/healthcare-monitor/) | 健康监测 |

### 🛠 OpenClaw 内部
| Skill | 说明 |
|-------|------|
| [skill-creator](skills/skill-creator/) | Skill 创建器 |
| [skillforge](skills/skillforge/) | Skill 锻造 |
| [skill-finder-cn](skills/skill-finder-cn/) | Skill 中文搜索 |
| [skill-search](skills/skill-search/) | Skill 搜索 |
| [skill-search-optimizer](skills/skill-search-optimizer/) | Skill 搜索优化 |
| [mcp-builder](skills/mcp-builder/) | MCP 构建器 |
| [mcp-installer](skills/mcp-installer/) | MCP 安装器 |
| [mcp-manager](skills/mcp-manager/) | MCP 管理器 |
| [agent-builder](skills/agent-builder/) | Agent 构建器 |
| [agent-patterns](skills/agent-patterns/) | Agent 模式 |
| [multi-agent-architecture](skills/multi-agent-architecture/) | 多 Agent 架构 |
| [context-manager](skills/context-manager/) | 上下文管理 |
| [context-recovery](skills/context-recovery/) | 上下文恢复 |
| [model-fallback](skills/model-fallback/) | 模型降级 |
| [model-health-check](skills/model-health-check/) | 模型健康检查 |
| [permission-manager](skills/permission-manager/) | 权限管理 |
| [auth-manager](skills/auth-manager/) | 认证管理 |
| [pass-secrets](skills/pass-secrets/) | 密钥管理 (pass) |
| [api-toolkit](skills/api-toolkit/) | API 工具包 |
| [api-provider-setup](skills/api-provider-setup/) | API Provider 配置 |
| [api-provider-status](skills/api-provider-status/) | API Provider 状态 |
| [cron-manager](skills/cron-manager/) | 定时任务管理 |
| [memory](skills/memory/) | 记忆系统 |
| [memory-hygiene](skills/memory-hygiene/) | 记忆清理 |
| [second-brain](skills/second-brain/) | 第二大脑 |
| [self-reflection](skills/self-reflection/) | 自我反思 |
| [git-sync](skills/git-sync/) | Git 同步 |
| [gitclaw](skills/gitclaw/) | GitClaw |
| [openclaw-inter-instance](skills/openclaw-inter-instance/) | OpenClaw 实例间通信 |
| [openclaw-config-helper](skills/openclaw-config-helper/) | OpenClaw 配置助手 |
| [openclaw-dashboard](skills/openclaw-dashboard/) | OpenClaw 仪表板 |
| [openrouter-usage](skills/openrouter-usage/) | OpenRouter 用量 |
| [chirp](skills/chirp/) | Chirp 通知 |
| [spool](skills/spool/) | Spool 队列 |
| [canvas-design](skills/canvas-design/) | Canvas 设计 |
| [web-artifacts-builder](skills/web-artifacts-builder/) | Web Artifacts 构建 |
| [theme-factory](skills/theme-factory/) | 主题工厂 |
| [evomap](skills/evomap/) | EvoMap 技能地图 |

### 🌐 浏览器 / 自动化
| Skill | 说明 |
|-------|------|
| [browser-use](skills/browser-use/) | 浏览器使用 |
| [chrome-automation](skills/chrome-automation/) | Chrome 自动化 |
| [fast-browser-use](skills/fast-browser-use/) | 快速浏览器使用 |
| [playwright-automation](skills/playwright-automation/) | Playwright 自动化 |
| [playwright-cli](skills/playwright-cli/) | Playwright CLI |
| [bat-cat](skills/bat-cat/) | Bat/Cat 文件查看 |
| [file-cleaner](skills/file-cleaner/) | 文件清理 |
| [fabric-pattern](skills/fabric-pattern/) | Fabric Pattern |
| [cursor-agent](skills/cursor-agent/) | Cursor Agent |
| [xiaomo-assistant-template](skills/xiaomo-assistant-template/) | 小墨助手模板 |

### 🔐 安全
| Skill | 说明 |
|-------|------|
| [1password](skills/1password/) | 1Password 集成 |
| [bitwarden](skills/bitwarden/) | Bitwarden 集成 |
| [openssf-security](skills/openssf-security/) | OpenSSF 安全 |
| [performing-security-code-review](skills/performing-security-code-review/) | 安全代码审查 |

### 🧠 AI 框架 / 思维模式
| Skill | 说明 |
|-------|------|
| [sp-brainstorming](skills/sp-brainstorming/) | 头脑风暴 |
| [sp-collision-zone-thinking](skills/sp-collision-zone-thinking/) | 碰撞区思维 |
| [sp-dispatching-parallel-agents](skills/sp-dispatching-parallel-agents/) | 并行Agent调度 |
| [sp-executing-plans](skills/sp-executing-plans/) | 执行计划 |
| [sp-inversion-exercise](skills/sp-inversion-exercise/) | 反转练习 |
| [sp-meta-pattern-recognition](skills/sp-meta-pattern-recognition/) | 元模式识别 |
| [sp-preserving-productive-tensions](skills/sp-preserving-productive-tensions/) | 保持生产性张力 |
| [sp-remembering-conversations](skills/sp-remembering-conversations/) | 记忆对话 |
| [sp-scale-game](skills/sp-scale-game/) | 规模游戏 |
| [sp-simplification-cascades](skills/sp-simplification-cascades/) | 简化级联 |
| [sp-using-skills](skills/sp-using-skills/) | 使用技能 |
| [sp-when-stuck](skills/sp-when-stuck/) | 遇到困难时 |
| [sp-writing-plans](skills/sp-writing-plans/) | 编写计划 |
| [ralph](skills/ralph/) | Ralph 框架 |

### 📦 其他工具
| Skill | 说明 |
|-------|------|
| [archive](skills/archive/) | 归档管理 |
| [core](skills/core/) | 核心技能 |
| [extended](skills/extended/) | 扩展技能 |
| [disabled](skills/disabled/) | 已禁用技能 |

## 🤖 Agents 列表

| Agent | 默认模型 | 用途 |
|-------|---------|------|
| [main](agents/main/) | aixn/claude-opus-4-6 | 主 Agent，支持所有子 Agent |
| [batch](agents/batch/) | zai/glm-4.7 | 批处理任务 |
| [code](agents/code/) | aixn/claude-opus-4-6 | 代码开发 |
| [content](agents/content/) | moonshot/kimi-k2.5 | 内容创作 |
| [critic](agents/critic/) | aixn/claude-opus-4-6 | 代码/方案评审 |
| [crm](agents/crm/) | moonshot/kimi-k2.5 | CRM 管理 |
| [data](agents/data/) | aixn/claude-opus-4-6 | 数据分析 |
| [feishu-agent](agents/feishu-agent/) | aixn/claude-opus-4-6 | 飞书集成 |
| [finance](agents/finance/) | zai/glm-4.7 | 财务分析 |
| [healthcare-monitor](agents/healthcare-monitor/) | aixn/claude-opus-4-6 | 健康监测 |
| [isolated](agents/isolated/) | aixn/claude-opus-4-6 | 隔离执行环境 |
| [knowledge](agents/knowledge/) | xingjiabiapi/gemini-3-pro | 知识管理 |
| [legal](agents/legal/) | aixn/claude-opus-4-6 | 法律咨询 |
| [marketing](agents/marketing/) | moonshot/kimi-k2.5 | 营销策划 |
| [multimodal-agent](agents/multimodal-agent/) | aixn/claude-opus-4-6 | 多模态生成 |
| [news](agents/news/) | moonshot/kimi-k2.5 | 新闻聚合 |
| [ops](agents/ops/) | zai/glm-4.7 | 运维管理 |
| [pm](agents/pm/) | zai/glm-4.7 | 项目管理 |
| [product](agents/product/) | zai/glm-4.7 | 产品设计 |
| [quant](agents/quant/) | zai/glm-4.7 | 量化交易 |
| [quick](agents/quick/) | xingjiabiapi/gemini-3-pro | 快速响应 |
| [research](agents/research/) | aixn/claude-opus-4-6 | 深度研究 |
| [sales](agents/sales/) | moonshot/kimi-k2.5 | 销售支持 |
| [support](agents/support/) | xingjiabiapi/gemini-3-pro | 客户支持 |
| [telegram-agent](agents/telegram-agent/) | aixn/claude-opus-4-6 | Telegram 集成 |
| [whatsapp-agent](agents/whatsapp-agent/) | aixn/claude-opus-4-6 | WhatsApp 集成 |

## 📡 模型 Provider

| Provider | API | 模型 |
|----------|-----|------|
| aixn | OpenAI Completions | Claude Opus 4.6 |
| zai | Anthropic Messages | GLM-4.7 |
| xingjiabiapi | OpenAI Completions | Gemini 3 Pro, Gemini 3 Pro Image, Gemini 2.5 Pro TTS, Veo 3.1 |
| moonshot | OpenAI Completions | Kimi K2.5 |
| github-copilot | OpenAI Completions | Claude Opus 4.5, Claude Sonnet 4.5, GPT-5.2 |
| openrouter-vip | OpenAI Completions | GPT-5 系列, GPT-5.1 系列, GPT-5.2 系列 |

## 🚀 快速部署

### 1. 克隆仓库

```bash
git clone git@github.com:aAAaqwq/AGI-Super-Skills.git
cd AGI-Super-Skills
```

### 2. 安装 OpenClaw

参考 [OpenClaw 官方文档](https://github.com/openclaw) 安装。

### 3. 复制配置

```bash
# 复制核心配置模板
cp config/openclaw.template.json ~/.openclaw/openclaw.json

# 复制 Agent 配置
for agent in agents/*/; do
  agent_name=$(basename "$agent")
  mkdir -p ~/.openclaw/agents/$agent_name/agent
  cp -r "$agent"/* ~/.openclaw/agents/$agent_name/agent/
done

# 复制 Skills 到 workspace
cp -r skills/ /path/to/your/workspace/skills/

# 复制 Workspace 文件
cp workspace/*.md /path/to/your/workspace/
```

### 4. 配置 API Key

编辑 `~/.openclaw/openclaw.json`，将所有 `YOUR_API_KEY_HERE` 替换为你的实际 API Key。

同样更新各 Agent 的 `~/.openclaw/agents/*/agent/models.json`。

### 5. 启动

```bash
openclaw gateway start
```

## 安全说明

本仓库已脱敏处理，所有 API Key、Token 均已替换为 `YOUR_API_KEY_HERE`。请勿在此仓库中提交任何真实密钥。

## 维护

| 项目 | 说明 |
|------|------|
| 维护者 | Daniel Li (@danielli) |
| 更新频率 | 持续同步 |
| 最后更新 | 2026-03-01 |
| OpenClaw 版本 | 2026.2.15+ |

---

*由 [OpenClaw](https://github.com/openclaw/openclaw) 驱动 🦞*
