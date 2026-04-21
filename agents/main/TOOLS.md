# TOOLS.md — main (小a)

_CEO · 本地工具配置和笔记_

## ~/clawd 目录索引

| 路径 | 说明 |
|------|------|
| ~/clawd/skills/ | 150+ 技能库 |
| ~/clawd/scripts/ | 工具脚本（newsbot_send.py, model-health-check.sh 等）|
| ~/clawd/workspace/content-pipeline/ | 内容管线（drafts, hotpool, topics）|
| ~/clawd/projects/ | 项目（MediaClaw, super-quant-claw）|
| ~/clawd/reports/ | 报告输出 |
| ~/clawd/repos/awesome-skills/ | 111 个社区 skills |
| ~/clawd/repos/AGI-Super-Team/ | 团队配置 |

## Skills 配置（2026-04-21 更新）

> 总表：`~/clawd/skills/team-foreman/output/skill-config-final.md`
> 旧表：`~/clawd/skills/team-foreman/output/skill-gap-master.md`（已归档）

### 总览：15 agents, 116 skills, 102 eligible

| Agent | # | 核心Skill |
|---|---|---|
| PE | 16 | react-expert, tdd-workflow, systematic-debugging, e2e-testing |
| CTO | 10 | kubernetes-specialist, docker-containerization, deployment-automation |
| CEO | 10 | executing-plans, brainstorming, dispatching-parallel-agents |
| CCO | 10 | content-ops-toolkit, writing-skills, xiaohongshu-viral-copy |
| CMO | 12 | traffic-acquisition, ads, video-marketing, xiaohongshu-growth |
| CQO | 9 | generating-trading-signals, backtest-expert, polymarket-api |
| CRO | 8 | deep-research, competitive-analysis, lead-intelligence |
| CPO | 8 | prd-development, user-story, roadmap-planning |
| CFO | 7 | token-budget-advisor, financial-analyst, polymarket-api |
| CLO | 7 | contract-review, gdpr-dsgvo-expert, legal-risk-assessment |
| CDO | 6 | postgresql-database-engineering, google-analytics, dashboard-builder |
| batch | 5 | executing-plans, dispatching-parallel-agents |
| CSO | 4 | lead-intelligence, cold-email-sequence-generator |
| COO | 4 | taskflow, healthcheck, verification-before-completion |
| claude | 0 | ACP运行时，不配skill |

### 新安装（2026-04-21）

| Skill | Agent | 来源 |
|---|---|---|
| backtest-expert | CQO | tradermonty/claude-trading-skills |
| contract-review | CLO | claude-office-skills/skills |
| gdpr-dsgvo-expert | CLO | borghei/claude-skills |
| legal-risk-assessment | CLO | borghei/claude-skills |
| privacy-compliance | CLO | borghei/claude-skills |
| financial-analyst | CFO | borghei/claude-skills |
| saas-metrics-coach | CFO | borghei/claude-skills |
| cold-email-sequence-generator | CSO | onewave-ai/claude-skills |

### 可直接引用（awesome-skills，无需安装）

| Skill | 适用Agent |
|---|---|
| pipedrive-automation | CSO |
| hubspot-automation | CSO/CMO |
| salesforce-automation | CSO |
| twitter-automation | CMO |
| youtube-automation | CMO |
| tiktok-automation | CMO |
| linkedin-automation | CMO |

### 本地特有 Skills（~/clawd/skills/）

| Skill | 用途 |
|---|---|
| team-foreman | 团队监工巡检 |
| model-hierarchy-skill | 模型层级调度 |
| openclaw-master-skills | OpenClaw主控 |
| orchestration-workflow | Agent编排 |
| token-guard | Token用量防护 |
| token-reporter | Token消耗报告 |
| daily-douyin-content | 抖音日更 |
| daily-xhs-content | XHS日更 |
| daily-gzh-content | 公众号日更 |
| gzh-publisher-skill | 公众号发布 |
| douyin-smart-publish | 抖音智能发布 |
| xhs-publisher | XHS发布 |
| content-repurposing-engine | 一稿多平台 |
| entropy-manager | 系统减熵 |

## 常用命令

| 操作 | 命令 |
|---|---|
| 检查skills状态 | `openclaw skills check` |
| 搜索skills | `npx skills find "关键词"` |
| 安装skill | `npx skills add owner/repo@skill -g -y` |
| 验证配置 | `openclaw config validate` |

---

_最后更新: 2026-04-21 | Skills v2_
