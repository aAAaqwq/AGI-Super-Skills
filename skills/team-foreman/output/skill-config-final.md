# AGI Super Team — Skill 配置终版 v3

> 更新时间：2026-04-21 19:05 | CTO战略级重构完成
> 原则：每个 agent 配备**垂直领域全面通用**的 skill

## 📊 总览（v3）

| Agent | Skills数 | 覆盖度 | 状态 |
|---|---|---|---|
| pe | 22 | ★★★★★ | 🟢 |
| cto | 10 | ★★★★★ | 🟢 |
| main | 10 | ★★★★★ | 🟢 |
| cco | 10 | ★★★★★ | 🟢 |
| cmo | 12 | ★★★★★ | 🟢 |
| cro | 8 | ★★★★★ | 🟢 |
| cqo | 9 | ★★★★★ | 🟢 |
| cpo | 8 | ★★★★★ | 🟢 |
| cfo | 7 | ★★★★☆ | 🟢 |
| clo | 7 | ★★★★☆ | 🟢 |
| cdo | 6 | ★★★★☆ | 🟢 |
| batch | 5 | ★★★★☆ | 🟢 |
| cso | 4 | ★★★☆☆ | 🟡 |
| coo | 4 | ★★★☆☆ | 🟡 |
| claude | 0 | — | 🟢(ACP) |
| **总计** | **132** | | |

---

## ⚡ CTO/PE 重大调整（2026-04-21）

**CTO从工具层→战略层**：移出kubernetes/docker/deployment等工具skill给PE，CTO改为架构决策+方法论定位。

### CTO 新配置：10个战略级skill

| # | Skill | 行数 | 质量 | 来源 |
|---|---|---|---|---|
| 1 | `cto-advisor` | 498行 | A+ | borghei/claude-skills (128 installs) |
| 2 | `software-architecture-design` | 166行 | A+ | vasilyu1983/ai-agents-public (418 installs) |
| 3 | `architecture-decision` | 196行 | A+ | jwynia/agent-skills (285 installs) |
| 4 | `incident-response-incident-response` | 176行 | A+ | sickn33/antigravity-awesome-skills (184 installs) |
| 5 | `postmortem-writer` | 203行 | A+ | patricio0312rev/skills (78 installs) |
| 6 | `monitoring-observability` | — | A | travisjneuman/.claude (57 installs) |
| 7 | `microservices-patterns` | 997行 | A+ | manutej/luxor-claude-marketplace (78 installs) |
| 8 | `distributed-tracing` | 458行 | A+ | sickn33/antigravity-awesome-skills (186 installs) |
| 9 | `tech-selection-research` | 184行 | A | jssfy/k-skills (23 installs) |
| 10 | `architecture-patterns` | 580行 | A+ | miles990/claude-software-skills (153 installs) |

### PE 新配置：22个工具级skill

接收CTO移出的工具skill + 原有的开发测试skill。

| # | Skill | 来源 |
|---|---|---|
| 1-16 | react-expert, tdd-workflow, test-driven-development, code-review-quality, e2e-testing, e2e-testing-patterns, systematic-debugging, receiving-code-review, requesting-code-review, gh-issues, github, finishing-a-development-branch, Tailwind CSS, tailwindcss, frontend-design, style-guide-generator | 原PE skill |
| 17 | `kubernetes-specialist` | CTO移出 |
| 18 | `docker-containerization` | CTO移出 |
| 19 | `deployment-automation` | CTO移出 |
| 20 | `nginx-configuration` | CTO移出 |
| 21 | `ghost-scan-code` | CTO移出 |
| 22 | `cli-developer` | CTO移出 |

---

## 各 Agent 详细配置

### main（CEO）
executing-plans, continuous-learning-v2, dispatching-parallel-agents, brainstorming, writing-plans, verification-before-completion, using-superpowers, find-skills, skills-search, healthcheck

### batch
executing-plans, dispatching-parallel-agents, find-skills, skills-search, healthcheck

### cfo
token-budget-advisor, cost-aware-llm-pipeline, polymarket-api, polymarket, dashboard-builder, financial-analyst, saas-metrics-coach

### cto（战略级）
cto-advisor, software-architecture-design, architecture-decision, incident-response-incident-response, postmortem-writer, monitoring-observability, microservices-patterns, distributed-tracing, tech-selection-research, architecture-patterns

### cdo
postgresql-database-engineering, redis-inspect, sql-optimization, google-analytics, dashboard-builder, eval-harness

### clo
hookify-rules, code-review-quality, ghost-scan-code, contract-review, gdpr-dsgvo-expert, legal-risk-assessment, privacy-compliance

### pe（工具级）
react-expert, tdd-workflow, test-driven-development, code-review-quality, e2e-testing, e2e-testing-patterns, systematic-debugging, receiving-code-review, requesting-code-review, gh-issues, github, finishing-a-development-branch, Tailwind CSS, tailwindcss, frontend-design, style-guide-generator, kubernetes-specialist, docker-containerization, deployment-automation, nginx-configuration, ghost-scan-code, cli-developer

### cqo
generating-trading-signals, scanning-market-movers, synthetic-market-research, polymarket-api, polymarket, cost-aware-llm-pipeline, deep-research, dashboard-builder, backtest-expert

### cro
deep-research, competitive-analysis, competitor-alternatives, competitor-price-tracker, apify-competitor-intelligence, lead-intelligence, search-first, synthetic-market-research

### cmo
traffic-acquisition, ads, ads-agent, video-marketing, xiaohongshu-growth, postbridge-social-growth, skill-amazon-ads, content-ops-toolkit, ecommerce-competitor-analyzer, poster-design-generation, brand-identity, brand-dna

### cco
content-ops-toolkit, writing-skills, baoyu-xhs-images, xiaohongshu-viral-copy, xiaohongshu-growth, poster-design-generation, humanizer, video-marketing, video-generation, video-frames

### cpo
prd-development, user-story, roadmap-planning, prototype-prompt-generator, vp-cpo-readiness-advisor, design-thinking, api-design, api-design-patterns

### cso
lead-intelligence, traffic-acquisition, postbridge-social-growth, cold-email-sequence-generator

### coo
taskflow, taskflow-inbox-triage, healthcheck, verification-before-completion

### claude
（ACP运行时，不配skill）

---

*最后更新：2026-04-21 19:05 | v3: CTO战略级重构完成*
