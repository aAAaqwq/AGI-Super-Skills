# AGI Super Team — Skill 配置终版 v2

> 更新时间：2026-04-21 00:30 | 覆盖率全面提升
> 原则：每个 agent 配备**垂直领域全面通用**的 skill

## 📊 总览

| Agent | Skills数 | 覆盖度 | 状态 |
|---|---|---|---|
| pe | 16 | ★★★★★ | 🟢 |
| cmo | 12 | ★★★★★ | 🟢 |
| main | 10 | ★★★★★ | 🟢 |
| cto | 10 | ★★★★★ | 🟢 |
| cco | 10 | ★★★★★ | 🟢 |
| cqo | 9 | ★★★★★ | 🟢 |
| cro | 8 | ★★★★★ | 🟢 |
| cpo | 8 | ★★★★★ | 🟢 |
| cfo | 7 | ★★★★☆ | 🟢 |
| clo | 7 | ★★★★☆ | 🟢 |
| cdo | 6 | ★★★★☆ | 🟢 |
| batch | 5 | ★★★★☆ | 🟢 |
| cso | 4 | ★★★☆☆ | 🟡 |
| coo | 4 | ★★★☆☆ | 🟡 |
| claude | 0 | ★★☆☆☆ | 🔴 |
| **总计** | **116** | | |

## 📦 新安装 Skill（v2 新增）

| Skill | Agent | 来源 | 用途 |
|---|---|---|---|
| backtest-expert | CQO | tradermonty/claude-trading-skills | 策略回测P0 |
| contract-review | CLO | claude-office-skills/skills | 合同审查P0 |
| gdpr-dsgvo-expert | CLO | borghei/claude-skills | 数据隐私P0 |
| legal-risk-assessment | CLO | borghei/claude-skills | 法律风险评估 |
| privacy-compliance | CLO | borghei/claude-skills | 多法规隐私合规 |
| financial-analyst | CFO | borghei/claude-skills | 财务分析DCF |
| saas-metrics-coach | CFO | borghei/claude-skills | SaaS指标 |
| cold-email-sequence-generator | CSO | onewave-ai/claude-skills | 冷邮件序列 |

## 各 Agent 详细配置

### batch

| # | Skill | 状态 |
|---|---|---|
| 1 | `executing-plans` | ✅ |
| 2 | `dispatching-parallel-agents` | ✅ |
| 3 | `find-skills` | ✅ |
| 4 | `skills-search` | ✅ |
| 5 | `healthcheck` | ✅ |

### cco

| # | Skill | 状态 |
|---|---|---|
| 1 | `content-ops-toolkit` | ✅ |
| 2 | `writing-skills` | ✅ |
| 3 | `baoyu-xhs-images` | ✅ |
| 4 | `xiaohongshu-viral-copy` | ✅ |
| 5 | `xiaohongshu-growth` | ✅ |
| 6 | `poster-design-generation` | ✅ |
| 7 | `humanizer` | ✅ |
| 8 | `video-marketing` | ✅ |
| 9 | `video-generation` | ✅ |
| 10 | `video-frames` | ✅ |

### cdo

| # | Skill | 状态 |
|---|---|---|
| 1 | `postgresql-database-engineering` | ✅ |
| 2 | `redis-inspect` | ✅ |
| 3 | `sql-optimization` | ✅ |
| 4 | `google-analytics` | ✅ |
| 5 | `dashboard-builder` | ✅ |
| 6 | `eval-harness` | ✅ |

### cfo

| # | Skill | 状态 |
|---|---|---|
| 1 | `token-budget-advisor` | ✅ |
| 2 | `cost-aware-llm-pipeline` | ✅ |
| 3 | `polymarket-api` | ✅ |
| 4 | `polymarket` | ✅ |
| 5 | `dashboard-builder` | ✅ |
| 6 | `financial-analyst` | ✅ |
| 7 | `saas-metrics-coach` | ✅ |

### claude

| # | Skill | 状态 |
|---|---|---|

### clo

| # | Skill | 状态 |
|---|---|---|
| 1 | `hookify-rules` | ✅ |
| 2 | `code-review-quality` | ✅ |
| 3 | `ghost-scan-code` | ✅ |
| 4 | `contract-review` | ✅ |
| 5 | `gdpr-dsgvo-expert` | ✅ |
| 6 | `legal-risk-assessment` | ✅ |
| 7 | `privacy-compliance` | ✅ |

### cmo

| # | Skill | 状态 |
|---|---|---|
| 1 | `traffic-acquisition` | ✅ |
| 2 | `ads` | ✅ |
| 3 | `ads-agent` | ✅ |
| 4 | `video-marketing` | ✅ |
| 5 | `xiaohongshu-growth` | ✅ |
| 6 | `postbridge-social-growth` | ✅ |
| 7 | `skill-amazon-ads` | ✅ |
| 8 | `content-ops-toolkit` | ✅ |
| 9 | `ecommerce-competitor-analyzer` | ✅ |
| 10 | `poster-design-generation` | ✅ |
| 11 | `brand-identity` | ✅ |
| 12 | `brand-dna` | ✅ |

### coo

| # | Skill | 状态 |
|---|---|---|
| 1 | `taskflow` | ✅ |
| 2 | `taskflow-inbox-triage` | ✅ |
| 3 | `healthcheck` | ✅ |
| 4 | `verification-before-completion` | ✅ |

### cpo

| # | Skill | 状态 |
|---|---|---|
| 1 | `prd-development` | ✅ |
| 2 | `user-story` | ✅ |
| 3 | `roadmap-planning` | ✅ |
| 4 | `prototype-prompt-generator` | ✅ |
| 5 | `vp-cpo-readiness-advisor` | ✅ |
| 6 | `design-thinking` | ✅ |
| 7 | `api-design` | ✅ |
| 8 | `api-design-patterns` | ✅ |

### cqo

| # | Skill | 状态 |
|---|---|---|
| 1 | `generating-trading-signals` | ✅ |
| 2 | `scanning-market-movers` | ✅ |
| 3 | `synthetic-market-research` | ✅ |
| 4 | `polymarket-api` | ✅ |
| 5 | `polymarket` | ✅ |
| 6 | `cost-aware-llm-pipeline` | ✅ |
| 7 | `deep-research` | ✅ |
| 8 | `dashboard-builder` | ✅ |
| 9 | `backtest-expert` | ✅ |

### cro

| # | Skill | 状态 |
|---|---|---|
| 1 | `deep-research` | ✅ |
| 2 | `competitive-analysis` | ✅ |
| 3 | `competitor-alternatives` | ✅ |
| 4 | `competitor-price-tracker` | ✅ |
| 5 | `apify-competitor-intelligence` | ✅ |
| 6 | `lead-intelligence` | ✅ |
| 7 | `search-first` | ✅ |
| 8 | `synthetic-market-research` | ✅ |

### cso

| # | Skill | 状态 |
|---|---|---|
| 1 | `lead-intelligence` | ✅ |
| 2 | `traffic-acquisition` | ✅ |
| 3 | `postbridge-social-growth` | ✅ |
| 4 | `cold-email-sequence-generator` | ✅ |

### cto

| # | Skill | 状态 |
|---|---|---|
| 1 | `kubernetes-specialist` | ✅ |
| 2 | `docker-containerization` | ✅ |
| 3 | `deployment-automation` | ✅ |
| 4 | `nginx-configuration` | ✅ |
| 5 | `systematic-debugging` | ✅ |
| 6 | `ghost-scan-code` | ✅ |
| 7 | `healthcheck` | ✅ |
| 8 | `cli-developer` | ✅ |
| 9 | `code-review-quality` | ✅ |
| 10 | `finishing-a-development-branch` | ✅ |

### main

| # | Skill | 状态 |
|---|---|---|
| 1 | `executing-plans` | ✅ |
| 2 | `continuous-learning-v2` | ✅ |
| 3 | `dispatching-parallel-agents` | ✅ |
| 4 | `brainstorming` | ✅ |
| 5 | `writing-plans` | ✅ |
| 6 | `verification-before-completion` | ✅ |
| 7 | `using-superpowers` | ✅ |
| 8 | `find-skills` | ✅ |
| 9 | `skills-search` | ✅ |
| 10 | `healthcheck` | ✅ |

### pe

| # | Skill | 状态 |
|---|---|---|
| 1 | `react-expert` | ✅ |
| 2 | `tdd-workflow` | ✅ |
| 3 | `test-driven-development` | ✅ |
| 4 | `code-review-quality` | ✅ |
| 5 | `e2e-testing` | ✅ |
| 6 | `e2e-testing-patterns` | ✅ |
| 7 | `systematic-debugging` | ✅ |
| 8 | `receiving-code-review` | ✅ |
| 9 | `requesting-code-review` | ✅ |
| 10 | `gh-issues` | ✅ |
| 11 | `github` | ✅ |
| 12 | `finishing-a-development-branch` | ✅ |
| 13 | `Tailwind CSS` | ✅ |
| 14 | `tailwindcss` | ✅ |
| 15 | `frontend-design` | ✅ |
| 16 | `style-guide-generator` | ✅ |

---
*最后更新：2026-04-21 00:30 | v2 覆盖率全面提升*