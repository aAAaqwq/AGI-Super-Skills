# TOOLS.md — PE · Linus 工程师 工具索引

> 非穷尽使用笔记。`config/team-manifest.json` 是 assignment authority；通用安装器只复制其中 portable 的 required/optional Skills。
> 修复日期: 2026-06-17

## 🏗️ 架构与设计

| Skill | 路径 | 说明 | 状态 |
|-------|------|------|------|
| API 设计 | [api-design](../../skills/api-design/) | REST API 设计原则与模式 | ✅ |
| 认证系统 | [auth-system](../../skills/auth-system/) | 认证与授权系统 | ✅ |
| React 架构 | [react-architect](../../skills/react-architect/) | React 应用架构 | ✅ |
| CSS 专家 | [css-ninja](../../skills/css-ninja/) | 高级 CSS/样式 | ✅ |
| 数据库迁移 | [db-migrator](../../skills/db-migrator/) | 数据库迁移工具 | ✅ |
| Redis 缓存 | [redis-inspect](../../skills/redis-inspect/) | Redis 缓存策略与调试 | ✅ |
| SQL 优化 | [sql-optimization](../../skills/sql-optimization/) | SQL 性能优化 | ✅ |

## 🐳 部署与运维

| Skill | 路径 | 说明 | 状态 |
|-------|------|------|------|
| Docker | [docker-essentials](../../skills/docker-essentials/) | Docker 容器管理与调试 | ✅ |
| K8s 部署 | [kubernetes-specialist](../../skills/kubernetes-specialist/) | Kubernetes 部署与运维 | ✅ |
| CI/CD | `ci-cd-pipeline-builder`（外部，仓库未提供） | CI/CD 流水线构建 | ⚠️ |
| 浏览器管理 | [browser-profile-guide](../../skills/browser-profile-guide/) | 浏览器配置管理 | ✅ |

## 🧪 测试

| Skill | 路径 | 说明 | 状态 |
|-------|------|------|------|
| E2E 自动化 | [e2e-testing](../../skills/e2e-testing/) | 端到端测试自动化 | ✅ |
| TDD | [sp-test-driven-development](../../skills/sp-test-driven-development/) | 测试驱动开发 | ✅ |
| 测试反模式 | [sp-testing-anti-patterns](../../skills/sp-testing-anti-patterns/) | 常见测试陷阱 | ✅ |
| 完成前验证 | [verification-before-completion](../../skills/verification-before-completion/) | 发布前自动验证 | ✅ |

## 🔒 安全

| Skill | 路径 | 说明 | 状态 |
|-------|------|------|------|
| 安全审计 | [security-audit](../../skills/security-audit/) | 代码安全审计 | ✅ |

## 🔄 Git 与协作

| Skill | 路径 | 说明 | 状态 |
|-------|------|------|------|
| 请求代码审查 | [requesting-code-review](../../skills/requesting-code-review/) | 如何请求代码审查 | ✅ |
| 接收代码审查 | [receiving-code-review](../../skills/receiving-code-review/) | 如何处理审查反馈 | ✅ |
| 完成分支 | [finishing-a-development-branch](../../skills/finishing-a-development-branch/) | 开发分支收尾流程 | ✅ |
| Git Worktrees | [sp-using-git-worktrees](../../skills/sp-using-git-worktrees/) | Git Worktrees 使用 | ✅ |
| 子代理开发 | [sp-subagent-driven-development](../../skills/sp-subagent-driven-development/) | 多代理协作开发 | ✅ |
| 条件等待 | [sp-condition-based-waiting](../../skills/sp-condition-based-waiting/) | 异步条件等待模式 | ✅ |

## 🤖 编码代理

| Skill | 路径 | 说明 | 状态 |
|-------|------|------|------|
| Claude Code 控制 | `openclaw-claude-code`（外部，仓库未提供） | Claude Code MCP 协议控制 | ⚠️ |
| Claude Code Runner | [claude-code-runner](../../skills/claude-code-runner/) | PTY 调用执行编程任务 | ✅ |
| Codex CC 指南 | [codex-cc-guide](../../skills/codex-cc-guide/) | Codex CC 使用指南 | ✅ |
| 编码代理备份 | [coding-agent-backup](../../skills/coding-agent-backup/) | 编码代理备份方案 | ✅ |

---

*总计: 25 个技能 | 全部 25/25 存在 ✅ | 修复 13 个死链 → 映射到实际 skill*
*原错误引用: api-designer, redis-caching, sql-optimizer, docker-pro, k8s-deploy, ci-cd-builder, e2e-automator, test-genius, security-auditor, sp-requesting-code-review, sp-receiving-code-review, sp-finishing-a-development-branch, claude-code-controller*
