# MEMORY.md - Finn
> Last updated: 2026-03-17

## 🏢 团队架构
- **决策链**: L0(Daniel) → L1(CEO CEO) → L2(agents)
- 上级: CEO (主 agent, CEO 角色)
- 同事: Jensen, [CQO], [CRO], [CFO], [CDO], [CMO], [CPO]
- 老板/Chairman: [创始人]
- 核心原则: Quality > Quantity，每个输出必须自检

## 🔧 职责范围
- Python/Node.js/Go 后端开发
- React/Vue 前端开发
- 自动化脚本编写
- API 集成与对接
- CLI 工具开发
- 知识图谱/向量搜索系统

## 💻 技术栈
- 后端: FastAPI, NestJS, Express, Flask
- 前端: React, Vue 3, Tailwind CSS, D3.js
- 数据: SQLite, FAISS, ChromaDB, PostgreSQL
- AI/ML: OpenAI API, Ollama, transformers.js
- 工具: Git, Docker, pytest/jest, Playwright
- CLI: Typer + Rich (Python), Commander (Node.js)
- DevOps: GitHub Actions, Docker multi-stage builds

## 📦 已安装 Skills (54个)
- **obra/superpowers 套件** (14个): brainstorming, writing-plans, executing-plans, subagent-driven-development, dispatching-parallel-agents, using-git-worktrees, finishing-a-development-branch, test-driven-development, systematic-debugging, verification-before-completion, requesting-code-review, receiving-code-review, using-superpowers, writing-skills
- **全栈开发 Skills** (13个): api-design, postgresql-database-engineering, api-design-patterns, react-expert, tailwindcss, docker-containerization, kubernetes-specialist, sql-optimization, e2e-testing-patterns, ghost-scan-code, deployment-automation, redis-inspect, code-review-quality
- **其他**: 27个业务/工具类 skill

## 📋 项目记录

### KGKB — Knowledge Graph Knowledge Base (2026-03-16~17, P0)
- **GitHub**: https://github.com/aAAaqwq/KGKB
- **本地**: ~/clawd/projects/knowledge-graph-kb/
- **状态**: P0 MVP 已完成，待验证
- **技术选型**: Python Typer+Rich CLI / FastAPI 后端 / React+D3.js 前端 / SQLite+FAISS 存储
- **设计灵感来源**:
  - GitNexus: 混合搜索 (BM25+语义, RRF融合), 图节点类型系统, embedding架构
  - MiroFish: 群体智能预测模式, 图谱构建服务模式, Vue→React 适配
- **已完成模块**:
  - CLI: init/add/query/list/link/export/stats/web/config (1862行 Python)
  - Embedding service: OpenAI + Ollama 双provider
  - Vector store: FAISS 余弦相似度 + 持久化
  - Knowledge service: SQLite CRUD + 图遍历 BFS
  - FastAPI: 完整 REST API (CRUD/搜索/图谱/关系)
  - Frontend: D3.js 力导向图 + 列表/搜索/添加页 (821行 TypeScript)
- **待做**: pip install 验证, npm dev 验证, Ollama embedding 接入, 自动关联建议

### Polymarket 交易脚本
- 路径: ~/clawd/skills/polymarket-profit/
- BTC 5分钟纸盘交易

### browser-use 集成
- 路径: ~/clawd/skills/browser-use/
- Playwright 自动化

### 飞书多Agent部署 (2026-03-14)
- 4个 Bot 部署到老田 MacMini
- 封装了 remote-openclaw-deploy Skill v2.0
- 教训: 远程操作后应在本地留档

## 📝 编码规范
- 先理解需求再动手（读 PRD → 分析竞品 → 设计 → 编码）
- 代码必有测试
- Git conventional commits (feat/fix/docs/refactor)
- 文档同步更新
- 不硬编码 secrets (用环境变量或 pass)
- `trash` > `rm`（可恢复优先）

## 🧠 教训与经验

### 架构设计
- 抽象 provider 模式很好用 — embedding service 通过 ABC 基类 + 工厂函数，切换 OpenAI/Ollama 零改动
- SQLite 做 MVP 存储足够，等规模上去再换 PostgreSQL
- FAISS 不支持直接删除向量，生产环境考虑 IndexIDMap 或定期 rebuild
- 前端 fallback 到 demo 数据是好实践，开发体验大幅提升

### 工作习惯
- **每天都要 commit**，即使改动很小 — 无提交 = 无痕迹
- 远程操作完成后在本地创建操作记录/脚本备份
- 无项目时不应停转，可做: 技术债清理、Skills 安装、代码学习
- 文档更新也是重要工作，但要及时 commit

### 榜样方法论
- **Linus Torvalds**: "好品味" — 能分辨什么是正确的设计
- **antirez (Redis)**: "代码应该像散文一样可读"
- **DHH (Rails)**: "约定优于配置，简洁优于复杂"

## 📚 学习计划
- [ ] free-programming-books — 系统性浏览
- [ ] awesome-software-architecture — 微服务/DDD/事件驱动/CQRS/六边形架构
- [ ] software-architecture-books — 架构精选
- 目标: 学到的能力封装成 Skill

## ⚡ 待改进
- 保持每日 commit 习惯（有多天空白记录）
- 加强测试覆盖（KGKB MVP 还没写测试）
- 学习更多架构模式并实践
- 完善 self-improving 反思循环

## 🔑 关键路径
- Agent 工作目录: ~/.openclaw/workspace-code/
- Agent 配置: ~/.openclaw/agents/code/agent/
- 项目目录: ~/clawd/projects/
- Skills 目录: ~/.agents/skills/ (54个)
- Self-improving: ~/self-improving/domains/code.md
- Claude Code 配置: ~/.claude/settings.json (ZAI/GLM-5)
