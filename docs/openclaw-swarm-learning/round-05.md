# 🧠 蜂群学习 Round 5/10 — 开发军团

**日期**: 2026-04-01 14:32 (Wed)
**角色**: 小a CEO
**主题**: 开发军团 — 代码开发、评审、部署、跨机执行链路

---

## 一、开发军团组成

### 核心成员

| 角色 | Agent ID | 职责 | Skills 装备 |
|------|----------|------|-------------|
| **首席工程师** | `code` | 编码、架构、部署、CI/CD | backend-dev, frontend-dev, conventional-commits, github-automation, mcp-builder, openssf-security |
| **首席项目官** | `pm` | 需求拆解、验收、进度管理 | project-management, project-planner, kanbanflow-skill, agent-team-orchestration |
| **首席运维** | `ops` | 环境搭建、Gateway管理、监控 | linux-service-triage, sysadmin-toolbox, healthcheck, docker-essentials, model-provider-manager |
| **CEO** | `main` | 战略决策、调度、质量终审 | ralph-ceo-loop, 全局调度 |

### 协作规则（从实战提炼）

1. **小code ≠ 小ops**: 项目部署(Nginx/Docker/SSL)归小code，Gateway管理归小ops。边界清晰。
2. **小pm 先行**: 任何开发项目，小pm 先拆任务→CEO审核→再派小code。
3. **CEO 做决策不做执行**: 不亲自写代码/测API，全部派给对应agent。

---

## 二、标准开发工作流（SOP）

### Phase 1: 需求 → PRD

```
Daniel 提需求 → CEO 评估可行性 → 派小pm 写PRD → CEO 审阅 → Daniel 确认
```

**产出**: `projects/<project-name>/PRD-*.md` + `acceptance-criteria.md`

**关键教训（TCM项目验证）**:
- PRD 必须包含验收标准（可量化、可测试）
- 不写 PRD 就编码 = 浪费时间（铁律）

### Phase 2: 架构 → 任务拆解

```
小pm 拆解任务清单 → 标注依赖关系 → CEO 审核调整 → 分配给对应agent
```

**产出**: `projects/<project-name>/tasks.md`（每任务含：目标、范围、输出格式、验收标准）

**任务拆解原则**:
- 可并行的任务标注 `[PARALLEL]`，同时派出
- 有依赖的任务标注 `[DEPENDS: task-N]`，按序执行
- 跨职责任务拆成子任务，各派各的

### Phase 3: 编码 → 评审

```
小code 开发 → 自测 → CEO/小pm 评审 → 不达标退回 → 达标→下一步
```

**编码规范（从 openssf-security skill 提炼）**:
- 所有密钥走 `pass show`，零硬编码
- Push 前三层安全扫描（grep + pre-push-scan + 人工确认）
- 提交信息遵循 conventional-commits（feat/fix/chore/docs）

**代码评审检查清单**:
- [ ] 功能是否满足验收标准
- [ ] 有无硬编码密钥/API key
- [ ] 错误处理是否完善
- [ ] 是否有测试覆盖

### Phase 4: 部署 → 验证

```
小code 部署（Nginx/Docker/SSL/systemd）→ 小ops 配置监控 → CEO 最终验收
```

**部署层级**:

| 层级 | 负责人 | 内容 |
|------|--------|------|
| 应用部署 | 小code | Nginx配置、Dockerfile、systemd service、SSL证书 |
| 系统运维 | 小ops | Gateway配置、cron任务、日志轮转、资源监控 |
| 跨机同步 | CEO协调 | Tailscale连接、Gateway API、SSH执行 |

### Phase 5: 复盘 → 归档

```
项目完成 → CEO组织复盘 → 记录教训 → 更新SOP → git push
```

---

## 三、跨机执行链路

### 当前基础设施

```
daniel-ubuntu (本机, Linux, 主力)
  ├── Tailscale → daniellimac-mini (小m, macOS, 8GB)
  ├── Tailscale → danielmac-studio (Mac Studio, macOS)
  ├── Tailscale → marcus-mac-mini (yuewen, macOS M4)
  └── Tailscale → laotianmac-mini (老田, macOS M4)
```

### 跨机执行方式矩阵

| 方式 | 命令 | 适用场景 | 限制 |
|------|------|----------|------|
| **SSH 直接执行** | `ssh user@host "command"` | 一次性命令、部署脚本 | 需公钥认证、非交互 |
| **SSH + PTY** | `exec(pty=true, ssh ...)` | 需要交互的安装/配置 | 需活跃终端 |
| **Gateway API** | `nodes.run(node, command)` | OpenClaw 已部署的节点 | 需 Gateway 运行中 |
| **sessions_send** | `sessions_send(sessionKey, msg)` | 给远程 agent 派任务 | 需 agent session 活跃 |
| **Gateway API (curl)** | `curl Gateway/api/sessions/send` | 跨实例通信 | 需 token 认证 |

### 跨机部署标准流程

```bash
# 1. 验证连通性
ssh user@host "uname -a && df -h"

# 2. 同步项目代码
scp -r ~/clawd/projects/<project>/ user@host:~/projects/

# 3. 远程执行部署脚本
ssh user@host "cd ~/projects/<project> && ./deploy.sh"

# 4. 验证服务
curl http://<tailscale-ip>:<port>/health

# 5. 配置监控
# → 小ops 在本机添加 cron 监控远程服务
```

### 小m 特殊注意事项
- Mac Clash VPN 海外节点不稳定 → Telegram 依赖 Linux 代理转发
- Ollama 服务需 `--noproxy "*"` 绕过 Clash
- SSH: `ssh danielli@daniellimac-mini.tail0db0a3.ts.net`
- Gateway: `ws://daniellimac-mini.tail0db0a3.ts.net:18789`

---

## 四、实战案例复盘

### 案例 1: TCM 经络推理 MVP（成功 ✅）

**项目**: `tcm-meridian-inference-mvp`
**结果**: 10/10 验收标准全部通过

**关键成功因素**:
1. PRD V2.1 精确定义了验收标准
2. 任务按优先级有序拆解
3. 小code 单一负责编码，职责清晰
4. CEO + 小pm 双重质量把关

### 案例 2: TCM 部署到小m（成功 ✅）

**项目**: `tcm-deploy-xiaom`
**结果**: 13/13 部署步骤全部完成

**关键成功因素**:
1. 标准化部署脚本
2. 跨机 SSH 执行链路验证
3. 分步验证（每步确认后再继续）

### 案例 3: Polymarket 量化系统（失败教训 ⚠️）

**问题**: 跳过 PRD 直接开发 → API 签名问题 → browser-use 超时 → 项目停滞

**教训**: 不写 PRD 就编码 = 浪费时间。铁律必须遵守。

---

## 五、开发军团 SOP 雏形

### 开发项目启动检查清单

```markdown
## 项目启动前 (CEO)
- [ ] 第一性原理评估通过（市场/成本/壁垒/闭环/风险 ≥ 4/5）
- [ ] Daniel 确认方向
- [ ] 创建 projects/<name>/ 目录

## PRD 阶段 (小pm)
- [ ] PRD 文档完成（含目标、范围、技术方案）
- [ ] 验收标准定义（可量化、可测试）
- [ ] CEO 审阅通过
- [ ] Daniel 确认

## 任务拆解 (小pm + CEO)
- [ ] 任务清单（每任务含：目标、范围、输出、验收标准）
- [ ] 依赖关系标注
- [ ] 可并行任务识别
- [ ] 按职责分配到对应 agent

## 编码阶段 (小code)
- [ ] 代码开发
- [ ] 自测通过
- [ ] 安全扫描（无硬编码密钥）
- [ ] 提交信息规范

## 评审阶段 (小pm + CEO)
- [ ] 功能验收
- [ ] 代码评审
- [ ] 不达标→退回重做（最多3次）

## 部署阶段 (小code + 小ops)
- [ ] 部署脚本/配置
- [ ] 服务启动验证
- [ ] 监控配置

## 复盘阶段 (CEO)
- [ ] 项目复盘文档
- [ ] 教训记录到 MEMORY.md
- [ ] SOP 更新
- [ ] git commit + push
```

### 紧急修复流程（P0 Bug）

```
发现P0 → CEO评估影响 → 直接派小code修复 → 小ops配合部署 → 验证→汇报Daniel
（跳过PRD，但事后必须补复盘）
```

---

## 六、工具链总览

| 工具 | 用途 | 谁用 |
|------|------|------|
| `sessions_spawn` | 并行派独立任务 | CEO |
| `sessions_send` | 群聊内派有上下文任务 | CEO |
| `gh` CLI | GitHub 操作 | 小code/CEO |
| `pass` | 密钥管理 | 所有人 |
| SSH | 跨机执行 | 小code/小ops |
| `nodes.run` | Gateway远程命令 | CEO |
| `exec` | 本机shell执行 | CEO |
| ACP (Codex/Claude Code) | 复杂编码任务 | CEO → 小code |

---

## 七、本轮关键洞察

1. **职责边界是效率的保障**: 小code做部署、小ops管Gateway、小pm管流程。交叉 = 混乱。
2. **PRD 是不可跳过的**: TCM成功 vs Polymarket停滞，唯一区别是有没有写PRD。
3. **跨机执行需要标准化脚本**: 每次手动SSH操作容易出错，scp + deploy.sh 是可复用模式。
4. **评审是质量的最后防线**: CEO + 小pm 双重把关比单一评审可靠。
5. **安全不能事后补**: 从02-05到03-14共4次密钥泄露事故，每次都是"偷懒"导致。三层扫描必须自动化。

---

## 八、下一步行动

- [ ] 将本 SOP 雏形完善为 `~/clawd/SOP.md` 的开发部分
- [ ] 创建 `deploy-to-remote` Skill（标准化跨机部署流程）
- [ ] 小code 创建通用 deploy.sh 模板
- [ ] 小ops 建立远程服务健康监控模板

---

*蜂群学习 Round 5/10 | 开发军团 | 2026-04-01*
