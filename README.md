# 🚀 AGI Super Team

[中文](./README_CN.md) | English

> **285+ curated AI skills + 13 ready-to-deploy agents** for [OpenClaw](https://github.com/openclaw/openclaw) — build your own AI-native company with a full C-suite of digital employees.

## 💡 What Is This?

A **plug-and-play AI team template** — deploy a complete virtual company in minutes using OpenClaw. Each agent has its own role, personality, and skill stack. Fully customizable: swap models, rename agents, add your own skills.

## 📊 Overview

| Metric | Value |
|--------|-------|
| **Skills** | 285+ |
| **Categories** | 18 |
| **Agents** | 13 (fully customizable) |
| **Framework** | [OpenClaw](https://github.com/openclaw/openclaw) |

## 🏗️ Architecture

```
You (CEO / Creator)
  └── AI Coordinator (Main Agent)
        ├── Engineer — code, architecture, debugging
        ├── Quant — trading, market analysis, backtesting
        ├── Data Officer — scraping, ETL, data analysis
        ├── DevOps — monitoring, deployment, infra
        ├── Content — writing, copywriting, publishing
        ├── Researcher — deep research, papers, intelligence
        ├── Finance — accounting, P&L, financial modeling
        ├── Marketing — SEO, ads, growth strategy
        ├── PM — project planning, task tracking, QA
        ├── Legal — compliance, contracts, regulations
        ├── Product — design, competitor analysis, UX
        └── Sales — lead gen, BD, customer analysis
```

> **Extensible**: Add more agents (HR, Support, etc.) by creating a new `agents/<id>/` folder.

## 👥 Agents

| ID | Role | Default Model | Customizable |
|-----|------|------|:---:|
| `main` | Coordinator / CEO | `claude-opus-4-6` | ✅ |
| `code` | Chief Engineer | `glm-5` | ✅ |
| `quant` | Chief Trading Officer | `glm-5` | ✅ |
| `data` | Chief Data Officer | `glm-5` | ✅ |
| `ops` | Chief DevOps | `glm-5` | ✅ |
| `content` | Chief Content Officer | `glm-5` | ✅ |
| `research` | Chief Research Officer | `glm-5` | ✅ |
| `finance` | Chief Financial Officer | `glm-5` | ✅ |
| `market` | Chief Marketing Officer | `glm-5` | ✅ |
| `pm` | Chief Project Officer | `glm-5` | ✅ |
| `law` | Chief Legal Officer | `MiniMax-M2.5` | ✅ |
| `product` | Chief Product Officer | `glm-5` | ✅ |
| `sales` | Chief Sales Officer | `glm-5` | ✅ |

> Each agent config is in [`agents/<id>/agent.json`](./agents/) — sanitized templates, ready to customize with your own API keys, names, and personalities.

## 🛠️ Skill Categories

| Category | Count | Highlights |
|----------|:-----:|-----------|
| [⚙️ OpenClaw Tools](#-openclaw-tools) | 21 | Config helpers, auth manager, cron, token guard |
| [🤖 AI Agent Patterns](#-ai-agent-patterns) | 20 | Multi-agent orchestration, parallel execution, prompt optimization |
| [🔧 Development](#-development) | 26 | Backend/frontend dev, Docker, Git, TDD, debugging |
| [💰 Trading & Finance](#-trading--finance) | 27 | Crypto trading, Polymarket, DeFi, portfolio management |
| [📝 Content & Writing](#-content--writing) | 22 | SEO writing, social media, documentation, copywriting |
| [📊 Data & Analytics](#-data--analytics) | 15 | Web scraping, spreadsheets, arXiv, data pipelines |
| [📈 Marketing & SEO](#-marketing--seo) | 14 | SEO audits, paid ads, competitor analysis, GEO |
| [🎨 Design & Media](#-design--media) | 12 | Image generation, UI/UX, slides, video |
| [🌐 Browser Automation](#-browser-automation) | 6 | Playwright, Chrome, headless browsing |
| [🏢 Business & Strategy](#-business--strategy) | 10 | SaaS launch, financial modeling, startup analysis |
| [📋 Project Management](#-project-management) | 13 | Task tracking, daily reports, team coordination |
| [🧠 Knowledge & Research](#-knowledge--research) | 3 | Memory management, academic research, web search |
| [💬 Communication](#-communication) | 10 | Email, Feishu/Lark, WeChat, Slack integration |
| [🔌 SaaS Integrations](#-saas-integrations) | 61 | Notion, Airtable, HubSpot, Stripe, Shopify, 55+ more |
| [⚙️ DevOps & Infra](#-devops--infra) | 7 | AWS, Docker, Linux troubleshooting, monitoring |
| [🔒 Security](#-security) | 4 | Code review, security audit, credential scanning |
| [⚖️ Legal & Compliance](#-legal--compliance) | 1 | Web accessibility guidelines |
| [🧩 Other](#-other) | 13 | RSS, calendars, presentations, skill creation |

<details>
<summary>📋 Full Skill List (click to expand)</summary>

### ⚙️ OpenClaw Tools

| Skill | Description |
|-------|-------------|
| [`api-provider-setup`](./skills/api-provider-setup/) | Configure third-party API providers for OpenClaw (Anthropic/OpenAI compatible) |
| [`api-provider-status`](./skills/api-provider-status/) | API provider status and balance monitoring |
| [`auth-manager`](./skills/auth-manager/) | Web login session management with browser automation |
| [`context-manager`](./skills/context-manager/) | AI-powered context management for sessions |
| [`cron-manager`](./skills/cron-manager/) | Cron job management — create, monitor, diagnose, and fix scheduled tasks |
| [`evomap`](./skills/evomap/) | EvoMap collaborative evolution marketplace integration |
| [`feishu-channel`](./skills/feishu-channel/) | Feishu/Lark ↔ OpenClaw bidirectional messaging channel |
| [`mcp-installer`](./skills/mcp-installer/) | Search and auto-install MCP servers from GitHub |
| [`mcp-manager`](./skills/mcp-manager/) | MCP server smart management — auto-detect, toggle, Q&A |
| [`model-fallback`](./skills/model-fallback/) | Automatic model failover with multi-provider support |
| [`model-health-check`](./skills/model-health-check/) | Check all configured model provider connectivity and latency |
| [`openclaw-config-helper`](./skills/openclaw-config-helper/) | Safe config editing with schema validation |
| [`openclaw-inter-instance`](./skills/openclaw-inter-instance/) | Cross-instance communication between OpenClaw deployments |
| [`openrouter-usage`](./skills/openrouter-usage/) | Track OpenRouter API spending and projections |
| [`permission-manager`](./skills/permission-manager/) | Manage global tool permissions and allowlists |
| [`skill-finder-cn`](./skills/skill-finder-cn/) | Discover and install skills from ClawHub |
| [`skillforge`](./skills/skillforge/) | Intelligent skill router — recommend, improve, or create skills |
| [`telegram-push`](./skills/telegram-push/) | Push messages to Telegram via standalone bot |
| [`token-guard`](./skills/token-guard/) | Token usage monitoring with budgets and auto-downgrade |
| [`wechat-channel`](./skills/wechat-channel/) | WeChat ↔ OpenClaw bidirectional messaging channel |
| [`xiaomo-assistant-template`](./skills/xiaomo-assistant-template/) | Quick-start assistant configuration template |

### 🤖 AI Agent Patterns

| Skill | Description |
|-------|-------------|
| [`agent-patterns`](./skills/agent-patterns/) | Agent coordination, spawn requests, and report formats |
| [`env-setup`](./skills/env-setup/) | One-click environment sync from GitHub repo |
| [`erc-8004`](./skills/erc-8004/) | Register AI agents on Ethereum via ERC-8004 |
| [`fabric-pattern`](./skills/fabric-pattern/) | Fabric AI framework integration for text processing |
| [`kubernetes-deployment`](./skills/kubernetes-deployment/) | K8s deployment, Helm charts, service mesh |
| [`multi-agent-architecture`](./skills/multi-agent-architecture/) | Multi-agent system design and intelligent task dispatch |
| [`multimodal-gen`](./skills/multimodal-gen/) | Multimodal content generation (images, video) |
| [`parallel-agents`](./skills/parallel-agents/) | Multi-agent orchestration for parallel task execution |
| [`prompt-optimizer`](./skills/prompt-optimizer/) | Evaluate and optimize prompts with 58 techniques |
| [`sp-collision-zone-thinking`](./skills/sp-collision-zone-thinking/) | Force unrelated concepts together for emergent insights |
| [`sp-dispatching-parallel-agents`](./skills/sp-dispatching-parallel-agents/) | Investigate and fix independent problems concurrently |
| [`sp-executing-plans`](./skills/sp-executing-plans/) | Execute plans in batches with review checkpoints |
| [`sp-inversion-exercise`](./skills/sp-inversion-exercise/) | Flip assumptions to reveal hidden constraints |
| [`sp-meta-pattern-recognition`](./skills/sp-meta-pattern-recognition/) | Spot patterns across 3+ domains for universal principles |
| [`sp-preserving-productive-tensions`](./skills/sp-preserving-productive-tensions/) | Preserve valuable disagreements instead of forcing consensus |
| [`sp-remembering-conversations`](./skills/sp-remembering-conversations/) | Search previous conversations for facts and decisions |
| [`sp-scale-game`](./skills/sp-scale-game/) | Test at 1000x extremes to expose fundamental truths |
| [`sp-simplification-cascades`](./skills/sp-simplification-cascades/) | Find one insight that eliminates multiple components |
| [`sp-when-stuck`](./skills/sp-when-stuck/) | Dispatch to the right problem-solving technique |
| [`subagent-driven-development`](./skills/subagent-driven-development/) | Execute implementation plans with independent sub-tasks |

### 🔧 Development

| Skill | Description |
|-------|-------------|
| [`architecture-decision-records`](./skills/architecture-decision-records/) | Write and maintain ADRs for technical decisions |
| [`backend-development`](./skills/backend-development/) | Backend expert — Python, Node.js, Go, Java |
| [`bat-cat`](./skills/bat-cat/) | Modern cat replacement with syntax highlighting |
| [`billing-automation`](./skills/billing-automation/) | Automated billing, invoicing, and subscription management |
| [`changelog-generator`](./skills/changelog-generator/) | Auto-generate changelogs from git commits |
| [`commit-analyzer`](./skills/commit-analyzer/) | Analyze git commit patterns for operation health |
| [`docker-essentials`](./skills/docker-essentials/) | Essential Docker commands and workflows |
| [`electron-app-dev`](./skills/electron-app-dev/) | Electron desktop app development with electron-vite |
| [`frontend-design`](./skills/frontend-design/) | Production-grade frontend with high design quality |
| [`frontend-development`](./skills/frontend-development/) | Web app development, UI components, interactions |
| [`github-automation`](./skills/github-automation/) | GitHub ops — push, PRs, issues, CI/CD |
| [`langsmith-fetch`](./skills/langsmith-fetch/) | Debug LangChain agents via LangSmith traces |
| [`mcp-builder`](./skills/mcp-builder/) | Create high-quality MCP servers |
| [`ml-engineer`](./skills/ml-engineer/) | Machine learning engineering workflows |
| [`pass-secrets`](./skills/pass-secrets/) | Manage API keys with Pass (GPG-encrypted) |
| [`payment-integration`](./skills/payment-integration/) | Payment gateway integration patterns |
| [`python-performance-optimization`](./skills/python-performance-optimization/) | Profile and optimize Python performance |
| [`react-component-generator`](./skills/react-component-generator/) | Generate React components from specs |
| [`requesting-code-review`](./skills/requesting-code-review/) | Structured code review before merging |
| [`sql-optimization-patterns`](./skills/sql-optimization-patterns/) | SQL query optimization and indexing strategies |
| [`sql-pro`](./skills/sql-pro/) | Advanced SQL workflows |
| [`systematic-debugging`](./skills/systematic-debugging/) | Systematic approach to any bug or test failure |
| [`tdd-guide`](./skills/tdd-guide/) | Test-driven development workflow |
| [`test-automator`](./skills/test-automator/) | Automated test generation |
| [`vibe-code-auditor`](./skills/vibe-code-auditor/) | Audit AI-generated code for production risks |
| [`web-artifacts-builder`](./skills/web-artifacts-builder/) | Multi-component HTML artifacts with modern frontend |

### 💰 Trading & Finance

| Skill | Description |
|-------|-------------|
| [`arbitrage-opportunity-finder`](./skills/arbitrage-opportunity-finder/) | Detect arbitrage across CEX, DEX, and cross-chain |
| [`backtesting-frameworks`](./skills/backtesting-frameworks/) | Robust backtesting with bias handling |
| [`bankr`](./skills/bankr/) | AI crypto trading agent via natural language |
| [`bankr-signals`](./skills/bankr-signals/) | Transaction-verified trading signals on Base |
| [`clanker`](./skills/clanker/) | Deploy ERC20 tokens on EVM chains |
| [`crypto-bd-agent`](./skills/crypto-bd-agent/) | Crypto business development with wallet forensics |
| [`crypto-derivatives-tracker`](./skills/crypto-derivatives-tracker/) | Track futures, options, perpetuals, funding rates |
| [`crypto-portfolio-management`](./skills/crypto-portfolio-management/) | Portfolio allocation and rebalancing strategies |
| [`crypto-portfolio-tracker`](./skills/crypto-portfolio-tracker/) | Real-time portfolio valuations and P&L |
| [`crypto-signal-generator`](./skills/crypto-signal-generator/) | Generate signals from RSI, MACD, Bollinger Bands |
| [`defi-risk-assessment`](./skills/defi-risk-assessment/) | Evaluate DeFi protocol risks |
| [`invoice-organizer`](./skills/invoice-organizer/) | Auto-organize invoices for tax prep |
| [`market-movers-scanner`](./skills/market-movers-scanner/) | Detect significant price movements and volume |
| [`market-price-tracker`](./skills/market-price-tracker/) | Real-time crypto prices across exchanges |
| [`market-sentiment-analyzer`](./skills/market-sentiment-analyzer/) | Fear & Greed Index, news sentiment analysis |
| [`options-flow-analyzer`](./skills/options-flow-analyzer/) | Track institutional options positioning |
| [`polyclaw`](./skills/polyclaw/) | Trade on Polymarket via CLOB execution |
| [`polymarket-data`](./skills/polymarket-data/) | Polymarket live odds, order books, leaderboards |
| [`polymarket-profit`](./skills/polymarket-profit/) | Quantitative trading system for Polymarket |
| [`polymarket-skill`](./skills/polymarket-skill/) | Query and trade Polymarket prediction markets |
| [`polymarket-trading`](./skills/polymarket-trading/) | Systematic Polymarket quant trading |
| [`quant-analyst`](./skills/quant-analyst/) | Quantitative analysis workflows |
| [`risk-metrics-calculation`](./skills/risk-metrics-calculation/) | VaR, CVaR, Sharpe, Sortino, drawdown analysis |
| [`sperax-defi-guide`](./skills/sperax-defi-guide/) | DeFi yield farming strategies guide |
| [`trading-strategy-backtester`](./skills/trading-strategy-backtester/) | Backtest crypto and traditional strategies |
| [`unum-strat`](./skills/unum-strat/) | Universal fee-aware strategy design and audit |
| [`whale-alert-monitor`](./skills/whale-alert-monitor/) | Track whale transactions and wallet movements |

### 📝 Content & Writing

| Skill | Description |
|-------|-------------|
| [`content-creator`](./skills/content-creator/) | SEO-optimized marketing content with brand voice |
| [`content-marketer`](./skills/content-marketer/) | Content marketing strategy and distribution |
| [`content-research-writer`](./skills/content-research-writer/) | Research-backed content with citations |
| [`content-source-aggregator`](./skills/content-source-aggregator/) | Aggregate trending content from 6 platforms |
| [`conventional-commits`](./skills/conventional-commits/) | Conventional Commits formatting |
| [`copy-editing`](./skills/copy-editing/) | Edit and improve marketing copy |
| [`copywriting`](./skills/copywriting/) | Persuasive copy for landing pages, emails, ads |
| [`docx`](./skills/docx/) | Word document creation, editing, and analysis |
| [`docx-perfect`](./skills/docx-perfect/) | Professional Word document formatting |
| [`internal-comms`](./skills/internal-comms/) | Internal communications templates |
| [`podcast-generation`](./skills/podcast-generation/) | AI podcast-style audio narratives |
| [`react-best-practices`](./skills/react-best-practices/) | React/Next.js performance guidelines |
| [`reddit-automation`](./skills/reddit-automation/) | Reddit posts, comments, and subreddit management |
| [`seo-content-writer`](./skills/seo-content-writer/) | SEO-optimized content from keyword briefs |
| [`seo-content-writing`](./skills/seo-content-writing/) | SEO article writing |
| [`skill-search-optimizer`](./skills/skill-search-optimizer/) | Optimize skills for ClawHub discoverability |
| [`social-content`](./skills/social-content/) | Social media content for all platforms |
| [`sp-using-skills`](./skills/sp-using-skills/) | Skills wiki and search workflows |
| [`sp-writing-plans`](./skills/sp-writing-plans/) | Detailed implementation plans |
| [`wiki-page-writer`](./skills/wiki-page-writer/) | Technical documentation with Mermaid diagrams |
| [`wiki-qa`](./skills/wiki-qa/) | Answer questions about a code repository |
| [`xiaohongshu-workflow`](./skills/xiaohongshu-workflow/) | Xiaohongshu (RED) full operations workflow |

### 📊 Data & Analytics

| Skill | Description |
|-------|-------------|
| [`analytics-tracking`](./skills/analytics-tracking/) | Analytics tracking setup |
| [`arxiv-automation`](./skills/arxiv-automation/) | Search and monitor arXiv papers |
| [`data-engineering-data-pipeline`](./skills/data-engineering-data-pipeline/) | Scalable data pipeline architecture |
| [`data-storytelling`](./skills/data-storytelling/) | Transform data into compelling narratives |
| [`firecrawl`](./skills/firecrawl/) | Professional web scraping via Firecrawl API |
| [`football-data`](./skills/football-data/) | Football data across 13 leagues |
| [`google-analytics-automation`](./skills/google-analytics-automation/) | Google Analytics reports and funnels |
| [`googlesheets-automation`](./skills/googlesheets-automation/) | Google Sheets read, write, format, filter |
| [`pdf`](./skills/pdf/) | PDF manipulation — extract, create, merge, split |
| [`programmatic-seo`](./skills/programmatic-seo/) | Programmatic SEO at scale |
| [`sendgrid-automation`](./skills/sendgrid-automation/) | SendGrid email delivery automation |
| [`tavily`](./skills/tavily/) | AI-optimized web search via Tavily API |
| [`web-scraping-automation`](./skills/web-scraping-automation/) | Automated web scraping and API data extraction |
| [`web-search`](./skills/web-search/) | Multi-tool web search and content fetching |
| [`xlsx`](./skills/xlsx/) | Spreadsheet creation, editing, and analysis |

### 📈 Marketing & SEO

| Skill | Description |
|-------|-------------|
| [`brand-guidelines`](./skills/brand-guidelines/) | Brand color and typography application |
| [`competitive-ads-extractor`](./skills/competitive-ads-extractor/) | Extract competitor ads from ad libraries |
| [`competitor-alternatives`](./skills/competitor-alternatives/) | Competitor comparison pages for SEO/sales |
| [`deep-research`](./skills/deep-research/) | Multi-step research via Gemini Deep Research |
| [`geo-agent`](./skills/geo-agent/) | Generative Engine Optimization for AI search |
| [`lead-research-assistant`](./skills/lead-research-assistant/) | High-quality lead identification |
| [`linkedin-automation`](./skills/linkedin-automation/) | LinkedIn posts, profile, and company management |
| [`marketing-ideas`](./skills/marketing-ideas/) | Proven marketing strategies for SaaS |
| [`marketing-psychology`](./skills/marketing-psychology/) | Behavioral science applied to marketing |
| [`one-drive-automation`](./skills/one-drive-automation/) | OneDrive file management automation |
| [`paid-ads`](./skills/paid-ads/) | Paid advertising on Google, Meta, LinkedIn, X |
| [`seo-audit`](./skills/seo-audit/) | SEO audit workflows |
| [`seo-meta-optimizer`](./skills/seo-meta-optimizer/) | SEO meta tag optimization |
| [`twitter-algorithm-optimizer`](./skills/twitter-algorithm-optimizer/) | Optimize tweets for Twitter's algorithm |

### 🎨 Design & Media

| Skill | Description |
|-------|-------------|
| [`ai-image-generation`](./skills/ai-image-generation/) | Image generation via ModelScope Z-Image-Turbo |
| [`figma-automation`](./skills/figma-automation/) | Figma files, components, design tokens |
| [`image-enhancer`](./skills/image-enhancer/) | Enhance image quality and resolution |
| [`kpi-dashboard-design`](./skills/kpi-dashboard-design/) | KPI dashboard design and visualization |
| [`pricing-strategy`](./skills/pricing-strategy/) | Pricing, packaging, and monetization strategies |
| [`senior-architect`](./skills/senior-architect/) | System architecture design and evaluation |
| [`slidev-agent-skill`](./skills/slidev-agent-skill/) | Create Slidev presentations |
| [`sp-brainstorming`](./skills/sp-brainstorming/) | Interactive idea refinement via Socratic method |
| [`theme-factory`](./skills/theme-factory/) | Styling toolkit for slides, docs, landing pages |
| [`ui-ux-pro-max`](./skills/ui-ux-pro-max/) | UI/UX design — 50 styles, 21 palettes, 9 stacks |
| [`uml-diagram-design`](./skills/uml-diagram-design/) | UML diagrams — class, sequence, use case |
| [`video-downloader`](./skills/video-downloader/) | Download YouTube videos |

### 🌐 Browser Automation

| Skill | Description |
|-------|-------------|
| [`browser-use`](./skills/browser-use/) | AI-driven intelligent browser automation |
| [`chrome-automation`](./skills/chrome-automation/) | Chrome browser automation |
| [`fast-browser-use`](./skills/fast-browser-use/) | Fast Rust-based headless browser CLI |
| [`media-auto-publisher`](./skills/media-auto-publisher/) | Auto-publish to 6 Chinese content platforms |
| [`playwright-automation`](./skills/playwright-automation/) | Playwright browser automation for scraping/testing |
| [`webapp-testing`](./skills/webapp-testing/) | Web application testing with Playwright |

### 🏢 Business & Strategy

| Skill | Description |
|-------|-------------|
| [`business-analyst`](./skills/business-analyst/) | Business analysis workflows |
| [`market-sizing-analysis`](./skills/market-sizing-analysis/) | Market sizing and TAM/SAM/SOM analysis |
| [`meeting-insights-analyzer`](./skills/meeting-insights-analyzer/) | Analyze meeting transcripts for behavioral patterns |
| [`micro-saas-launcher`](./skills/micro-saas-launcher/) | Launch micro-SaaS products fast |
| [`notion-template-business`](./skills/notion-template-business/) | Build and sell Notion templates |
| [`startup-analyst`](./skills/startup-analyst/) | Startup analysis frameworks |
| [`startup-business-analyst-business-case`](./skills/startup-business-analyst-business-case/) | Investor-ready business case documents |
| [`startup-business-analyst-financial-projections`](./skills/startup-business-analyst-financial-projections/) | Financial projections for startups |
| [`startup-financial-modeling`](./skills/startup-financial-modeling/) | Startup financial modeling |
| [`startup-metrics-framework`](./skills/startup-metrics-framework/) | SaaS metrics — CAC, LTV, unit economics |

### 📋 Project Management

| Skill | Description |
|-------|-------------|
| [`daily-rhythm`](./skills/daily-rhythm/) | Automated daily planning and reflection |
| [`domain-name-brainstormer`](./skills/domain-name-brainstormer/) | Creative domain name generation + availability check |
| [`gitlab-automation`](./skills/gitlab-automation/) | GitLab issues, MRs, pipelines, branches |
| [`posthog-automation`](./skills/posthog-automation/) | PostHog events, feature flags, annotations |
| [`project-management`](./skills/project-management/) | Project planning and PRD writing |
| [`project-planner`](./skills/project-planner/) | Project path planning and execution |
| [`ralph`](./skills/ralph/) | Autonomous project delivery agent |
| [`ralph-ceo-loop`](./skills/ralph-ceo-loop/) | CEO dispatch loop — continuous team orchestration |
| [`render-automation`](./skills/render-automation/) | Render.com services and deployments |
| [`sentry-automation`](./skills/sentry-automation/) | Sentry issues, alerts, releases |
| [`task-status`](./skills/task-status/) | Status updates for long-running tasks |
| [`team-coordinator`](./skills/team-coordinator/) | Intelligent task dispatch across team agents |
| [`team-daily-report`](./skills/team-daily-report/) | Auto-generate team daily reports |

### 🧠 Knowledge & Research

| Skill | Description |
|-------|-------------|
| [`memory-hygiene`](./skills/memory-hygiene/) | Audit and optimize vector memory |
| [`research-engineer`](./skills/research-engineer/) | Academic research with scientific rigor |
| [`search-specialist`](./skills/search-specialist/) | Advanced web research and synthesis |

### 💬 Communication

| Skill | Description |
|-------|-------------|
| [`email-automation`](./skills/email-automation/) | Email read, search, draft, send |
| [`email-manager`](./skills/email-manager/) | Multi-mailbox unified management |
| [`feishu-automation`](./skills/feishu-automation/) | Feishu/Lark full automation — bitable, messages, docs |
| [`feishu-doc-optimizer`](./skills/feishu-doc-optimizer/) | Feishu document formatting and optimization |
| [`freshservice-automation`](./skills/freshservice-automation/) | Freshservice ITSM ticket automation |
| [`healthcare-monitor`](./skills/healthcare-monitor/) | Healthcare industry financing monitor |
| [`klaviyo-automation`](./skills/klaviyo-automation/) | Klaviyo email/SMS campaign management |
| [`outlook-automation`](./skills/outlook-automation/) | Outlook email, calendar, contacts |
| [`postmark-automation`](./skills/postmark-automation/) | Postmark email delivery automation |
| [`wecom-cs-automation`](./skills/wecom-cs-automation/) | WeCom customer service automation |

### 🔌 SaaS Integrations

| Skill | Description |
|-------|-------------|
| [`activecampaign-automation`](./skills/activecampaign-automation/) | ActiveCampaign contacts, tags, automations |
| [`airtable-automation`](./skills/airtable-automation/) | Airtable records, bases, tables, views |
| [`amplitude-automation`](./skills/amplitude-automation/) | Amplitude events, cohorts, user activity |
| [`asana-automation`](./skills/asana-automation/) | Asana tasks, projects, sections, teams |
| [`basecamp-automation`](./skills/basecamp-automation/) | Basecamp projects, to-dos, messages |
| [`bitbucket-automation`](./skills/bitbucket-automation/) | Bitbucket repos, PRs, branches, issues |
| [`box-automation`](./skills/box-automation/) | Box file management and sharing |
| [`brevo-automation`](./skills/brevo-automation/) | Brevo email campaigns and templates |
| [`cal-com-automation`](./skills/cal-com-automation/) | Cal.com bookings and availability |
| [`calendly-automation`](./skills/calendly-automation/) | Calendly scheduling and event management |
| [`canva-automation`](./skills/canva-automation/) | Canva designs, exports, brand templates |
| [`canvas-design`](./skills/canvas-design/) | Visual art and design creation |
| [`circleci-automation`](./skills/circleci-automation/) | CircleCI pipelines, workflows, artifacts |
| [`clickup-automation`](./skills/clickup-automation/) | ClickUp tasks, spaces, folders, lists |
| [`close-automation`](./skills/close-automation/) | Close CRM leads, calls, SMS, tasks |
| [`coda-automation`](./skills/coda-automation/) | Coda docs, pages, tables, formulas |
| [`confluence-automation`](./skills/confluence-automation/) | Confluence pages, spaces, search |
| [`convertkit-automation`](./skills/convertkit-automation/) | ConvertKit subscribers, tags, broadcasts |
| [`datadog-automation`](./skills/datadog-automation/) | Datadog metrics, logs, monitors |
| [`discord-automation`](./skills/discord-automation/) | Discord messages, channels, roles |
| [`docusign-automation`](./skills/docusign-automation/) | DocuSign templates, envelopes, signatures |
| [`dropbox-automation`](./skills/dropbox-automation/) | Dropbox file management and sharing |
| [`facebook-automation`](./skills/facebook-automation/) | Facebook pages, posts, insights |
| [`freshdesk-automation`](./skills/freshdesk-automation/) | Freshdesk tickets, contacts, companies |
| [`gmail-automation`](./skills/gmail-automation/) | Gmail send, search, labels, drafts |
| [`grafana-dashboards`](./skills/grafana-dashboards/) | Grafana dashboard creation and management |
| [`helpdesk-automation`](./skills/helpdesk-automation/) | HelpDesk tickets, views, canned responses |
| [`hubspot-automation`](./skills/hubspot-automation/) | HubSpot CRM — contacts, deals, tickets |
| [`instagram-automation`](./skills/instagram-automation/) | Instagram posts, carousels, insights |
| [`intercom-automation`](./skills/intercom-automation/) | Intercom conversations, contacts, segments |
| [`jira-automation`](./skills/jira-automation/) | Jira issues, sprints, boards |
| [`linear-automation`](./skills/linear-automation/) | Linear issues, projects, cycles |
| [`mailchimp-automation`](./skills/mailchimp-automation/) | Mailchimp campaigns, audiences, segments |
| [`make-automation`](./skills/make-automation/) | Make (Integromat) automation operations |
| [`microsoft-teams-automation`](./skills/microsoft-teams-automation/) | Teams messages, channels, meetings |
| [`miro-automation`](./skills/miro-automation/) | Miro boards, sticky notes, frames |
| [`mixpanel-automation`](./skills/mixpanel-automation/) | Mixpanel events, funnels, cohorts |
| [`monday-automation`](./skills/monday-automation/) | Monday.com boards, items, columns |
| [`notion-automation`](./skills/notion-automation/) | Notion pages, databases, blocks |
| [`pagerduty-automation`](./skills/pagerduty-automation/) | PagerDuty incidents, services, schedules |
| [`pipedrive-automation`](./skills/pipedrive-automation/) | Pipedrive deals, contacts, activities |
| [`salesforce-automation`](./skills/salesforce-automation/) | Salesforce leads, contacts, SOQL |
| [`segment-automation`](./skills/segment-automation/) | Segment events, users, groups |
| [`shopify-automation`](./skills/shopify-automation/) | Shopify products, orders, customers |
| [`slack-automation`](./skills/slack-automation/) | Slack messages, channels, search |
| [`square-automation`](./skills/square-automation/) | Square payments, orders, invoices |
| [`stripe-automation`](./skills/stripe-automation/) | Stripe customers, subscriptions, invoices |
| [`supabase-automation`](./skills/supabase-automation/) | Supabase DB, storage, edge functions |
| [`sysadmin-toolbox`](./skills/sysadmin-toolbox/) | Sysadmin tool discovery and shell one-liners |
| [`telegram-automation`](./skills/telegram-automation/) | Telegram messages, chats, bots |
| [`tiktok-automation`](./skills/tiktok-automation/) | TikTok video upload and content management |
| [`todoist-automation`](./skills/todoist-automation/) | Todoist tasks, projects, filtering |
| [`trello-automation`](./skills/trello-automation/) | Trello boards, cards, workflows |
| [`vercel-automation`](./skills/vercel-automation/) | Vercel deployments, domains, env vars |
| [`webflow-automation`](./skills/webflow-automation/) | Webflow CMS, publishing, ecommerce |
| [`wecom-automation`](./skills/wecom-automation/) | WeCom personal account automation |
| [`whatsapp-automation`](./skills/whatsapp-automation/) | WhatsApp Business messages, templates |
| [`youtube-automation`](./skills/youtube-automation/) | YouTube videos, playlists, analytics |
| [`zendesk-automation`](./skills/zendesk-automation/) | Zendesk tickets, users, organizations |
| [`zoho-crm-automation`](./skills/zoho-crm-automation/) | Zoho CRM records, leads, contacts |
| [`zoom-automation`](./skills/zoom-automation/) | Zoom meetings, recordings, webinars |

### ⚙️ DevOps & Infra

| Skill | Description |
|-------|-------------|
| [`aws-cost-cleanup`](./skills/aws-cost-cleanup/) | Clean up unused AWS resources |
| [`cost-optimization`](./skills/cost-optimization/) | Cloud cost optimization strategies |
| [`docker-deployment`](./skills/docker-deployment/) | Docker + Nginx HTTPS + Cloudflare Tunnel |
| [`file-cleaner`](./skills/file-cleaner/) | System file cleanup and disk space recovery |
| [`linux-service-triage`](./skills/linux-service-triage/) | Diagnose Linux service issues |
| [`linux-troubleshooting`](./skills/linux-troubleshooting/) | Linux system troubleshooting workflow |
| [`senior-devops`](./skills/senior-devops/) | Comprehensive DevOps for CI/CD and cloud |

### 🔒 Security

| Skill | Description |
|-------|-------------|
| [`openssf-security`](./skills/openssf-security/) | OpenSSF security guidance for software projects |
| [`performing-security-code-review`](./skills/performing-security-code-review/) | Security-focused code review |
| [`security-audit`](./skills/security-audit/) | Security auditing for deployments |
| [`security-monitor`](./skills/security-monitor/) | Real-time security monitoring |

### ⚖️ Legal & Compliance

| Skill | Description |
|-------|-------------|
| [`web-design-guidelines`](./skills/web-design-guidelines/) | Web accessibility and UI compliance |

### 🧩 Other

| Skill | Description |
|-------|-------------|
| [`api-toolkit`](./skills/api-toolkit/) | Universal RESTful API calling toolkit |
| [`context-recovery`](./skills/context-recovery/) | Recover working context after session compaction |
| [`deepwork-tracker`](./skills/deepwork-tracker/) | Track deep work sessions with heatmap |
| [`developer-growth-analysis`](./skills/developer-growth-analysis/) | Analyze coding patterns and growth areas |
| [`doc-coauthoring`](./skills/doc-coauthoring/) | Structured documentation co-authoring |
| [`google-calendar-automation`](./skills/google-calendar-automation/) | Google Calendar events and scheduling |
| [`google-drive-automation`](./skills/google-drive-automation/) | Google Drive file operations |
| [`pptx`](./skills/pptx/) | PowerPoint creation, editing, and analysis |
| [`rss-automation`](./skills/rss-automation/) | RSS feed aggregation and monitoring |
| [`skill-creator`](./skills/skill-creator/) | Guide for creating new skills |
| [`skill-search`](./skills/skill-search/) | Search and install skills from GitHub/SkillsMP |
| [`tech-decision`](./skills/tech-decision/) | Technical decision making — A vs B analysis |
| [`twitter-automation`](./skills/twitter-automation/) | Twitter/X posts, search, bookmarks, media |

</details>

## 🚀 Quick Start

```bash
# 1. Clone
git clone https://github.com/aAAaqwq/AGI-Super-Team.git
cd AGI-Super-Team

# 2. Install a single skill
cp -r skills/<skill-name> ~/.openclaw/skills/

# 3. Or symlink for easy updates
ln -s $(pwd)/skills/<skill-name> ~/.openclaw/skills/

# 4. Deploy an agent template
cp -r agents/<agent-id> ~/.openclaw/agents/
# Then edit agent.json with your API keys and preferences
```

## 🧩 Create Your Own Team

The agent configs are **templates** — customize them for your needs:

1. **Rename agents** — change display names and personalities in `agent.json`
2. **Swap models** — use any OpenClaw-compatible model (GPT, Claude, Gemini, GLM, etc.)
3. **Mix skills** — assign any combination of skills to any agent
4. **Add agents** — create new roles by copying an existing `agents/<id>/` folder
5. **Scale up** — run 10, 50, or 100+ agents across multiple machines via Tailscale

## 🤝 Contributing

PRs welcome! To add a new skill:

1. Create `skills/<your-skill>/SKILL.md` with description and instructions
2. Add any scripts to `skills/<your-skill>/scripts/`
3. Submit a PR

## ⭐ Star This Repo

If this project helps you build your AI team, please give it a ⭐!

Every star motivates us to add more skills, improve agent templates, and build better tooling.

[![Star History Chart](https://api.star-history.com/svg?repos=aAAaqwq/AGI-Super-Team&type=Date)](https://star-history.com/#aAAaqwq/AGI-Super-Team&Date)

## 📄 License

MIT
