# AGI Super Team — Skill 配置终版 v3

> 更新时间：2026-04-22 01:09 | v4: 10轮调研完成，高质量A+ skill清单
> 原则：每个 agent 配备**垂直领域全面通用**的 skill

## 📊 总览（v4）

| Agent | Skills数 | 覆盖度 | 状态 | 升级重点 |
|---|---|---|---|---|
| pe | 22 | ★★★★★ | 🟢 | +vue/graphql/frontend |
| cto | 10 | ★★★★★ | 🟢 | +github-actions/oauth/k8s |
| main | 10 | ★★★★★ | 🟢 | (已完善) |
| cco | 10 | ★★★★★ | 🟢 | +seo-content/social-content |
| cmo | 12 | ★★★★★ | 🟢 | +seo-content/social-media |
| cro | 8 | ★★★★★ | 🟢 | +apify-scraper(7.2K!)/BI |
| cqo | 9 | ★★★★★ | 🟢 | +charting(4.3K)/technical-analysis |
| cpo | 8 | ★★★★★ | 🟢 | +figma(2.7K)/usability-testing/ux |
| cso | 4 | ★★★★☆ | 🟢 | +enterprise-sales/customer-success |
| cfo | 7 | ★★★★☆ | 🟢 | +finance/investment |
| clo | 7 | ★★★★☆ | 🟢 | +data-privacy/patent |
| cdo | 6 | ★★★★☆ | 🟢 | +database-design/BI |
| coo | 4 | ★★★☆☆ | 🟡 | +asana/jira/project-workflow |
| batch | 5 | ★★★★☆ | 🟢 |
| cso | 4 | ★★★☆☆ | 🟡 |
| coo | 4 | ★★★☆☆ | 🟡 |
| claude | 0 | — | 🟢(ACP) |
| **总计** | **132** | | |

---

## ⚡ v4调研成果（2026-04-22 凌晨10轮调研）

通过`find-skills`系统性搜索，识别出一批A+级高质量skill（按安装量降序）：

### 🔥 超高价值发现（>1K installs）
| Skill | 安装量 | Agent | 用途 |
|---|---|---|---|
| `charting` | 4.3K | **CQO** | 技术图表分析（TradingView级） |
| `seo-content-writer` | 4K | **CCO/CMO** | SEO文章写作（CCO缺口：缺微信/B站专项） |
| `figma-implement-design` | 2.7K | **CPO** | Figma设计稿转代码 |
| `usability-testing` | 1K | **CPO** | 用户可用性测试 |
| `enterprise-sales` | 1.1K | **CSO** | 企业级销售 |
| `technical-analysis` | 1.1K | **CQO** | 技术分析指标（替代当前polymarket-api） |

### 🔴 CTO系统级补强
| Skill | 安装量 | 用途 |
|---|---|---|
| `github-actions-expert` | 146 | CI/CD标准化 |
| `devops-incident-responder` | 105 | 事件响应（补充incident-response） |
| `oauth-implementation` | 323 | OAuth认证实现（安全） |
| `k8s-helm` | 77 | K8s+Helm部署 |

### 🟠 CDO数据库补强
| Skill | 安装量 | 用途 |
|---|---|---|
| `database-design` | 272 | 数据建模（高质量） |
| `business-intelligence` | 775 | BI分析（CDO/CRO通用） |

### 🟡 CLO法律补强
| Skill | 安装量 | 用途 |
|---|---|---|
| `data-privacy-compliance` | 298 | 数据隐私合规（补充GDPR） |
| `patent-lawyer-agent` | 89 | 专利法（已有contract-review） |

### 🟢 CPO产品补强
| Skill | 安装量 | 用途 |
|---|---|---|
| `ux-researcher` | 163 | UX用户研究 |
| `design-to-component-translator` | 94 | 设计稿→组件 |
| `product-strategy` | 54 | 产品策略 |
| `product-roadmap` | 21 | 路线图规划 |

### 🔵 CSO销售补强
| Skill | 安装量 | 用途 |
|---|---|---|
| `customer-success` | 611 | 客户成功 |
| `crm-integration` | 163 | CRM集成 |
| `sales-operations` | 85 | 销售运营 |
| `account-executive` | 70 | 大客户代表 |

### 🟣 COO运营补强
| Skill | 安装量 | 用途 |
|---|---|---|
| `asana-automation` | 565 | Asana自动化 |
| `project-workflow` | 369 | 项目工作流 |
| `jira` | 273 | Jira集成 |
| `sprint-planner` | 47 | 冲刺规划 |

### ⚡ CRO研究补强（最大发现）
| Skill | 安装量 | 用途 |
|---|---|---|
| `apify-ultimate-scraper` | **7.2K** | 网页数据采集（CRITICAL） |
| `competitive-intel` | 33 | 竞品情报 |

### 💹 CQO量化交易（重大升级）
| Skill | 安装量 | 现状对比 |
|---|---|---|
| `charting` | 4.3K | 替代`polymarket-api`的图表分析 |
| `technical-analysis` | 1.1K | 替代`generating-trading-signals` |
| `tradingview-quantitative` | 620 | TradingView量化（超PE当前所有） |
| `trading-expert` | 614 | 交易专家 |
| `trade-prediction-markets` | 241 | 市场预测 |
| `pandas-ta` | 70 | 技术指标库 |

### 🎨 CCO内容创作补强
| Skill | 安装量 | 用途 |
|---|---|---|
| `seo-content-writer` | 4K | 通用SEO内容（已有xhs专项） |
| `social-content` | 57 | 社媒内容策略 |
| `douyin-auto-reply` | 10 | 抖音自动回复 |
| `bilibili-video-helper` | 20 | B站视频助手 |

### 💰 CFO财务补强
| Skill | 安装量 | 用途 |
|---|---|---|
| `finance` | 253 | 通用财务分析 |
| `investment-analyzer` | 54 | 投资分析 |

### 🛠️ PE工程补强
| Skill | 安装量 | 用途 |
|---|---|---|
| `vue` | 204 | Vue开发 |
| `frontend-development` | 153 | 前端开发综合 |
| `graphql-api-development` | 66 | GraphQL API |

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
