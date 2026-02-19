# AGI-Super-Skills 🦞✨

> OpenClaw 完整环境备份与快速部署仓库 — 200+ Skills、24 Agents、多模型配置、MCP 集成

[![Last Updated](https://img.shields.io/badge/Last%20Updated-2026--02--19-blue)]()
[![Skills](https://img.shields.io/badge/Skills-203-green)]()
[![Agents](https://img.shields.io/badge/Agents-24-orange)]()
[![License](https://img.shields.io/badge/License-MIT-yellow)]()

## 目录结构

```
AGI-Super-Skills/
├── skills/          # 203 个 OpenClaw Skills（自动化、开发、AI生成等）
├── agents/          # 24 个 Agent 配置（角色定义、模型绑定、系统提示词）
├── config/          # OpenClaw 核心配置模板（已脱敏，可直接复制使用）
├── workspace/       # Workspace 文件（AGENTS.md, SOUL.md, IDENTITY.md 等）
├── mcp/             # MCP Server 配置与说明
└── README.md        # 本文件
```

## Skills 列表

### 🤖 AI / 生成类
| Skill | 说明 |
|-------|------|
| ai-video-gen | AI 视频生成 |
| fal-ai | Fal.ai 图像生成 |
| image-enhancer | 图像增强 |
| krea-api | Krea AI API |
| multimodal-gen | 多模态内容生成 |
| pollinations | Pollinations 图像生成 |
| veo | Google Veo 视频生成 |
| veo3-video-gen | Veo 3 视频生成 |
| ffmpeg-video-editor | FFmpeg 视频编辑 |
| video-downloader | 视频下载 |
| video-frames | 视频帧提取 |

### 💻 开发工具
| Skill | 说明 |
|-------|------|
| backend-development | 后端开发 |
| frontend-development | 前端开发 |
| frontend-design | 前端设计 |
| electron-app-dev | Electron 应用开发 |
| debug-pro | 高级调试 |
| tdd-guide | TDD 指南 |
| test-runner | 测试运行器 |
| webapp-testing | Web 应用测试 |
| commit-analyzer | Commit 分析 |
| conventional-commits | 约定式提交 |
| changelog-generator | 变更日志生成 |
| senior-architect | 高级架构师 |
| senior-devops | 高级 DevOps |
| multi-coding-agent | 多编码 Agent |
| claude-optimised | Claude 优化 |
| prompt-optimizer | Prompt 优化 |
| uml-diagram-design | UML 图设计 |

### 🔧 基础设施 / DevOps
| Skill | 说明 |
|-------|------|
| docker-deployment | Docker 部署 |
| docker-essentials | Docker 基础 |
| env-setup | 环境配置 |
| linux-service-triage | Linux 服务排障 |
| security-audit | 安全审计 |
| security-monitor | 安全监控 |
| render-automation | Render 自动化 |
| vercel-automation | Vercel 自动化 |

### 📊 项目管理 / 协作
| Skill | 说明 |
|-------|------|
| project-management | 项目管理 |
| project-planner | 项目规划 |
| project-context-sync | 项目上下文同步 |
| task-status | 任务状态追踪 |
| team-daily-report | 团队日报 |
| meeting-insights-analyzer | 会议洞察分析 |
| deepwork-tracker | 深度工作追踪 |
| daily-rhythm | 日常节奏管理 |

### 📝 内容 / 写作
| Skill | 说明 |
|-------|------|
| content-research-writer | 内容研究写作 |
| seo-content-writing | SEO 内容写作 |
| doc-coauthoring | 文档协作 |
| brand-guidelines | 品牌指南 |
| media-auto-publisher | 媒体自动发布 |
| internal-comms | 内部通讯 |
| moltbook / moltbook-interact | Moltbook 电子书 |
| docx / docx-perfect | DOCX 文档处理 |
| pdf | PDF 处理 |
| pptx | PPTX 演示文稿 |
| xlsx | Excel 处理 |

### 🌐 平台自动化（SaaS 集成）
| Skill | 说明 |
|-------|------|
| github-automation | GitHub |
| gitlab-automation | GitLab |
| bitbucket-automation | Bitbucket |
| slack-automation | Slack |
| discord-automation | Discord |
| telegram-automation | Telegram |
| telegram-push | Telegram 推送 |
| whatsapp-automation | WhatsApp |
| feishu-automation | 飞书 |
| feishu-channel | 飞书频道 |
| wecom-automation | 企业微信 |
| wecom-cs-automation | 企微客服 |
| wechat-channel | 微信视频号 |
| notion-automation | Notion |
| jira-automation | Jira |
| linear-automation | Linear |
| trello-automation | Trello |
| asana-automation | Asana |
| clickup-automation | ClickUp |
| monday-automation | Monday |
| basecamp-automation | Basecamp |
| confluence-automation | Confluence |
| coda-automation | Coda |
| miro-automation | Miro |
| figma-automation | Figma |
| canva-automation | Canva |
| hubspot-automation | HubSpot |
| salesforce-automation | Salesforce |
| pipedrive-automation | Pipedrive |
| close-automation | Close CRM |
| zoho-crm-automation | Zoho CRM |
| stripe-automation | Stripe |
| square-automation | Square |
| shopify-automation | Shopify |
| gmail-automation | Gmail |
| outlook-automation | Outlook |
| email-automation | 邮件自动化 |
| google-calendar-automation | Google Calendar |
| google-drive-automation | Google Drive |
| googlesheets-automation | Google Sheets |
| one-drive-automation | OneDrive |
| dropbox-automation | Dropbox |
| box-automation | Box |
| microsoft-teams-automation | Microsoft Teams |
| zoom-automation | Zoom |
| cal-com-automation | Cal.com |
| calendly-automation | Calendly |
| todoist-automation | Todoist |
| airtable-automation | Airtable |
| nocodb | NocoDB |
| supabase / supabase-automation | Supabase |
| webflow-automation | Webflow |
| make-automation | Make (Integromat) |
| sendgrid-automation | SendGrid |
| postmark-automation | Postmark |
| mailchimp-automation | Mailchimp |
| convertkit-automation | ConvertKit |
| brevo-automation | Brevo |
| klaviyo-automation | Klaviyo |
| activecampaign-automation | ActiveCampaign |
| instagram-automation | Instagram |
| linkedin-automation | LinkedIn |
| twitter-automation | Twitter/X |
| reddit-automation | Reddit |
| tiktok-automation | TikTok |
| youtube-automation | YouTube |
| amplitude-automation | Amplitude |
| mixpanel-automation | Mixpanel |
| posthog-automation | PostHog |
| segment-automation | Segment |
| google-analytics-automation | Google Analytics |
| datadog-automation | Datadog |
| sentry-automation | Sentry |
| pagerduty-automation | PagerDuty |
| circleci-automation | CircleCI |
| freshdesk-automation | Freshdesk |
| freshservice-automation | Freshservice |
| zendesk-automation | Zendesk |
| helpdesk-automation | Helpdesk |
| intercom-automation | Intercom |
| docusign-automation | DocuSign |

### 🔍 研究 / 数据
| Skill | 说明 |
|-------|------|
| web-scraping-automation | 网页抓取 |
| firecrawl-skills | Firecrawl 爬虫 |
| google-web-search | Google 搜索 |
| serper | Serper 搜索 API |
| readwise | Readwise 阅读 |
| competitive-ads-extractor | 竞品广告提取 |
| lead-research-assistant | 线索研究助手 |
| osint-graph-analyzer | OSINT 图谱分析 |
| developer-growth-analysis | 开发者增长分析 |
| langsmith-fetch | LangSmith 数据获取 |
| news-daily | 每日新闻 |

### 💰 金融 / 商业
| Skill | 说明 |
|-------|------|
| expense-tracker-pro | 费用追踪 |
| invoice-organizer | 发票整理 |
| cost-report | 成本报告 |
| polymarket-profit | Polymarket 交易 |
| tech-decision | 技术决策 |
| domain-name-brainstormer | 域名头脑风暴 |

### 🏥 健康
| Skill | 说明 |
|-------|------|
| healthcare-monitor | 健康监测 |

### 🛠 OpenClaw 内部
| Skill | 说明 |
|-------|------|
| skill-creator | Skill 创建器 |
| skillforge | Skill 锻造 |
| mcp-builder | MCP 构建器 |
| mcp-installer | MCP 安装器 |
| mcp-manager | MCP 管理器 |
| agent-builder | Agent 构建器 |
| multi-agent-architecture | 多 Agent 架构 |
| context-manager | 上下文管理 |
| context-recovery | 上下文恢复 |
| model-fallback | 模型降级 |
| permission-manager | 权限管理 |
| auth-manager | 认证管理 |
| pass-secrets | 密钥管理 (pass) |
| api-toolkit | API 工具包 |
| api-provider-setup | API Provider 配置 |
| api-provider-status | API Provider 状态 |
| cron-manager | 定时任务管理 |
| memory | 记忆系统 |
| memory-hygiene | 记忆清理 |
| second-brain | 第二大脑 |
| self-reflection | 自我反思 |
| git-sync | Git 同步 |
| gitclaw | GitClaw |
| openclaw-inter-instance | OpenClaw 实例间通信 |
| chirp | Chirp 通知 |
| spool | Spool 队列 |
| canvas-design | Canvas 设计 |
| web-artifacts-builder | Web Artifacts 构建 |
| theme-factory | 主题工厂 |

### 🌐 浏览器 / 自动化
| Skill | 说明 |
|-------|------|
| browser-use | 浏览器使用 |
| chrome-automation | Chrome 自动化 |
| playwright-automation | Playwright 自动化 |
| playwright-cli | Playwright CLI |
| bat-cat | Bat/Cat 文件查看 |
| file-cleaner | 文件清理 |
| fabric-pattern | Fabric Pattern |
| cursor-agent | Cursor Agent |
| xiaomo-assistant-template | 小墨助手模板 |

## Agents 列表

| Agent | 默认模型 | 用途 |
|-------|---------|------|
| main | aixn/claude-opus-4-6 | 主 Agent，支持所有子 Agent |
| batch | zai/glm-4.7 | 批处理任务 |
| code | aixn/claude-opus-4-6 | 代码开发 |
| content | moonshot/kimi-k2.5 | 内容创作 |
| critic | aixn/claude-opus-4-6 | 代码/方案评审 |
| crm | moonshot/kimi-k2.5 | CRM 管理 |
| data | aixn/claude-opus-4-6 | 数据分析 |
| feishu-agent | aixn/claude-opus-4-6 | 飞书集成 |
| finance | zai/glm-4.7 | 财务分析 |
| healthcare-monitor | aixn/claude-opus-4-6 | 健康监测 |
| isolated | aixn/claude-opus-4-6 | 隔离执行环境 |
| knowledge | xingjiabiapi/gemini-3-pro | 知识管理 |
| legal | aixn/claude-opus-4-6 | 法律咨询 |
| marketing | moonshot/kimi-k2.5 | 营销策划 |
| multimodal-agent | aixn/claude-opus-4-6 | 多模态生成 |
| news | moonshot/kimi-k2.5 | 新闻聚合 |
| ops | zai/glm-4.7 | 运维管理 |
| pm | zai/glm-4.7 | 项目管理 |
| product | zai/glm-4.7 | 产品设计 |
| quant | zai/glm-4.7 | 量化交易（子Agent: finance, research, news） |
| quick | xingjiabiapi/gemini-3-pro | 快速响应 |
| research | aixn/claude-opus-4-6 | 深度研究 |
| sales | moonshot/kimi-k2.5 | 销售支持 |
| support | xingjiabiapi/gemini-3-pro | 客户支持 |
| telegram-agent | aixn/claude-opus-4-6 | Telegram 集成 |
| whatsapp-agent | aixn/claude-opus-4-6 | WhatsApp 集成 |

## 模型 Provider

| Provider | API | 模型 |
|----------|-----|------|
| aixn | OpenAI Completions | Claude Opus 4.6 |
| zai | Anthropic Messages | GLM-4.7 |
| xingjiabiapi | OpenAI Completions | Gemini 3 Pro, Gemini 3 Pro Image, Gemini 2.5 Pro TTS, Veo 3.1 |
| moonshot | OpenAI Completions | Kimi K2.5 |
| github-copilot | OpenAI Completions | Claude Opus 4.5, Claude Sonnet 4.5, GPT-5.2 |
| openrouter-vip | OpenAI Completions | GPT-5 系列, GPT-5.1 系列, GPT-5.2 系列 |

## 快速部署

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
| 最后更新 | 2026-02-19 |
| OpenClaw 版本 | 2026.2.15+ |

---

*由 [OpenClaw](https://github.com/openclaw/openclaw) 驱动 🦞*
