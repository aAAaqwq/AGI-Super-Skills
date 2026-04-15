# 🧠 OpenClaw 蜂群学习 — 最终落地方案 v1.0

**日期**: 2026-04-03 (Fri)
**角色**: 小a CEO
**版本**: v1.0 — 10 轮学习收敛成果
**状态**: ✅ 定稿，待 Daniel 审阅

---

## 目录

1. [执行摘要](#一执行摘要)
2. [组织结构与军团编制](#二组织结构与军团编制)
3. [技术栈全景](#三技术栈全景)
4. [设备接入规范](#四设备接入规范)
5. [跨机通信协议](#五跨机通信协议)
6. [权限模型与安全基线](#六权限模型与安全基线)
7. [日志审计体系](#七日志审计体系)
8. [MVP 路线图](#八mvp-路线图)
9. [各军团模板](#九各军团模板)
10. [Daniel 的执行清单](#十daniel-的执行清单)

---

## 一、执行摘要

### 10 轮学习核心结论

| # | 轮次 | 主题 | 核心洞察 |
|---|------|------|---------|
| R1 | OpenClaw 基础架构 | Gateway + Agent + Skill 三层模型 | Agent 是数字员工，不是聊天机器人 |
| R2 | Skill 体系 | SKILL.md + scripts/ 标准化封装 | 每个能力封装为可复用 Skill |
| R3 | Agent 协作 | sessions_spawn 并行 + sessions_send 串行 | CEO 调度，agent 执行，职责不交叉 |
| R4 | 量化军团 | 信号→策略→执行→风控闭环 | 金融操作必须人工确认 |
| R5 | 开发军团 | PRD→拆解→编码→评审→部署→复盘 | 不写 PRD 就编码 = 浪费时间 |
| R6 | 内容军团 | 热点→调研→创作→发布→数据反馈 | 内容工厂流水线分工 |
| R7 | AIGC/GEO 军团 | 视频生成全流程 + AI 搜索优化 | 多模态是下一个增长曲线 |
| R8 | 物理信息交互 | Nodes + 设备控制 + Canvas + A2UI | 物理交互是 AI→数字员工的关键跃迁 |
| R9 | 安全治理 | 权限矩阵 + 审计 + 治理 + 多租户 | 4 次密钥泄露事故，安全不能事后补 |
| **R10** | **终极整合** | **本文件** | **从学习到落地的完整蓝图** |

### 三大核心信念

1. **CEO 做决策，agent 做执行** — 职责矩阵是铁律，不允许交叉
2. **安全第一，效率第二** — 4 次密钥泄露教训，零容忍
3. **MVP 先行，迭代优化** — 先跑通最小版本，再追求完美

---

## 二、组织结构与军团编制

### 2.1 三层治理架构

```
┌─────────────────────────────────────────────────────────┐
│                    董事长 Daniel                          │
│  战略方向 / 最终审批 / 金融操作 / 对外发布               │
└────────────────────────┬────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────┐
│                    CEO 小a (main)                         │
│  执行决策 / 团队调度 / 质量把控 / P0 响应               │
│  Spawn 权限: allowAgents: ["*"]                          │
└────────────────────────┬────────────────────────────────┘
                         │
    ┌──────────┬─────────┼─────────┬──────────┐
    │          │         │         │          │
┌───▼──┐ ┌────▼───┐ ┌───▼──┐ ┌────▼───┐ ┌───▼──────┐
│开发军团│ │内容军团 │ │量化军团│ │运维军团 │ │物理交互军团│
│code   │ │content │ │quant │ │ops     │ │nodes     │
│pm     │ │market  │ │finance│ │        │ │agent-browse│
│       │ │research│ │data  │ │        │ │          │
└───────┘ └────────┘ └──────┘ └────────┘ └──────────┘
```

### 2.2 C-Suite 全员编制（13 Agent）

| Agent | ID | 军团 | 职责 | 主模型 | Skills 数量 |
|-------|-----|------|------|--------|------------|
| **小a (CEO)** | main | 指挥部 | 战略决策、调度、质量把控 | shibacc/opus-4-6 | 全局 |
| **小code** | code | 开发 | 编码、架构、部署、CI/CD | shibacc/opus-4-6 | 6 |
| **小ops** | ops | 运维 | Gateway、监控、cron、安全 | shibacc/opus-4-6 | 4 |
| **小pm** | pm | 开发 | PRD、任务拆解、验收 | shibacc/opus-4-6 | 2 |
| **小quant** | q | 量化 | 策略、回测、信号、盯盘 | shibacc/opus-4-6 | 13 |
| **小data** | data | 量化 | 数据采集、清洗、分析 | shibacc/opus-4-6 | 7 |
| **小finance** | finance | 量化 | 财务核算、盈亏分析 | shibacc/opus-4-6 | 5 |
| **小content** | content | 内容 | 写作、文案、视频脚本 | shibacc/opus-4-6 | 7 |
| **小research** | research | 内容 | 调研、情报、行业报告 | shibacc/opus-4-6 | 8 |
| **小market** | market | 内容 | SEO、渠道、增长策略 | shibacc/opus-4-6 | 7 |
| **小law** | law | 顾问 | 法务、合规、合同审查 | shibacc/opus-4-6 | 11 |
| **小product** | product | 顾问 | 产品设计、竞品分析 | shibacc/opus-4-6 | 5 |
| **小sales** | sales | 顾问 | 拓客、企业分析、营销 | shibacc/opus-4-6 | 5 |

### 2.3 军团协同模式

| 模式 | 触发条件 | 参与者 | 典型流程 |
|------|---------|--------|---------|
| **独立执行** | 单一职责任务 | 1 个 agent | Daniel 说 → CEO 派 → agent 做 → 汇报 |
| **串行流水线** | 有前后依赖 | 2-3 个 agent | A完成 → B接手 → C完成 → 汇报 |
| **并行突击** | 可拆分的独立子任务 | 2-5 个 agent | CEO 同时 spawn → 各自独立 → 汇报 → CEO 整合 |
| **跨军团联合作战** | 大型项目 | 5+ 个 agent | PRD → 任务拆解 → 按军团并行 → 联调 → 部署 → 复盘 |

---

## 三、技术栈全景

### 3.1 基础设施层

| 组件 | 技术 | 版本/规格 | 用途 |
|------|------|----------|------|
| **Gateway** | OpenClaw | 2026.3.x | Agent 运行时、消息路由、Cron 调度 |
| **内网** | Tailscale | tail0db0a3.ts.net | 跨设备加密隧道 |
| **密钥管理** | pass (gpg) | — | 唯一密钥真相源 |
| **运行时密钥** | `.env` (chmod 600) | — | Gateway 环境变量注入 |
| **版本控制** | Git + GitHub | gh CLI | 代码/配置/Skill 管理 |
| **服务管理** | systemd | — | Gateway 守护进程 |

### 3.2 供应商矩阵

| 供应商 | 主模型 | 用途 | 状态 |
|--------|--------|------|------|
| **shibacc** | claude-opus-4-6 / sonnet-4-6 | 主力推理 | ✅ 23 models |
| **zai** | glm-5.1 | 快速/中文/fallback | ✅ 稳定 |
| **xingsuancode** | claude-sonnet | Fallback | ✅ 18 models |
| **xai** | grok-3 | 推理/X搜索 | ✅ |
| **github-copilot** | claude | 代码 | ✅ |
| **moonshot** | kimi | 中文长文 | ✅ |
| **deepseek** | deepseek | 代码/推理 | ✅ |
| **google-ai-studio** | gemini/veo/imagen | 视频/图像生成 | ✅ |
| **openrouter** | 多模型 | 路由 | ✅ |

### 3.3 本地模型节点

| 节点 | 模型 | 用途 |
|------|------|------|
| **小m Ollama** | qwen3-embedding:0.6b | Embedding (1024维) |
| **小m Ollama** | qwen3:8b / deepseek-r1:8b | 本地推理 |
| **Mac Studio Ollama** | qwen3.5:9b + qwen3.5:cloud | 本地推理 |

### 3.4 Skill 体系

| 分类 | 数量 | 管理 |
|------|------|------|
| 全局 Skill (`~/.openclaw/skills/`) | ~20 | 安全、自省、工具类 |
| Workspace Skill (`~/clawd/skills/`) | ~30+ | 业务逻辑、项目专属 |
| ClawHub 市场 | 3425+ | 社区贡献，按需安装 |

### 3.5 Cron 任务

| 统计 | 数量 |
|------|------|
| 总计 | ~42 |
| 正常运行 | 40 |
| 异常 | 2 |
| 类型覆盖 | CEO巡检、量化分析、内容创作、蜂群学习、模型健康 |

---

## 四、设备接入规范

### 4.1 当前设备矩阵

| 设备 | Tailscale IP | 系统 | 角色 | OpenClaw | 节点状态 |
|------|-------------|------|------|---------|---------|
| **daniel-ubuntu** | 100.112.88.20 | Linux x64 | 主力 Gateway | ✅ 运行中 | — (本机) |
| **小m Mac Mini** | 动态 | macOS ARM | 辅助节点 + Ollama | ✅ 已部署 | ⚠️ 偶尔离线 |
| **Mac Studio** | 100.65.110.126 | macOS | GPU 推理 + 未来多租户 | ❌ 未部署 | ❌ |
| **老田 Mac Mini** | 100.91.44.116 | macOS M4 | 远程测试节点 | ❌ 未部署 | — |
| **Peter Mac Mini** | 100.118.109.75 | macOS ARM | 丘比特团队 | ✅ 运行中 | — |
| **Daniel Win11** | 100.92.207.37 | Windows | ❌ 离线 | — | — |
| **Redmi Turbo 4** | 100.83.164.113 | Android | ❌ 离线 | — | — |

### 4.2 设备接入标准流程（新设备 SOP）

```bash
# Step 1: Tailscale 连网
tailscale up --accept-routes
# 验证: tailscale status

# Step 2: SSH 公钥认证
ssh-copy-id user@<tailscale-ip>
# 验证: ssh user@<tailscale-ip> "uname -a"

# Step 3: OpenClaw 安装
curl -fsSL https://get.openclaw.ai | bash  # 或 npm install -g openclaw
openclaw init

# Step 4: Gateway 启动
openclaw gateway start
# 验证: curl http://localhost:18789/health

# Step 5: Agent 配置
# 复制本机 agent 模板到新设备
scp -r ~/.openclaw/agents/ user@<ip>:~/.openclaw/agents/
# 修改 agent.json 的模型/技能配置

# Step 6: 节点配对（移动设备）
openclaw qr --json  # 本机生成
# 设备扫码 → 网关审批
openclaw devices approve <requestId>

# Step 7: 验证
openclaw nodes status
openclaw gateway status
```

### 4.3 设备分类与职责

| 设备类型 | 持续在线 | 推荐角色 | 典型设备 |
|---------|---------|---------|---------|
| **Linux VPS/服务器** | ✅ 7×24 | 主 Gateway + 全量 Agent | daniel-ubuntu |
| **Mac Mini** | ✅ 接近 7×24 | 辅助节点 + 本地推理 + Ollama | 小m |
| **Mac Studio** | ✅ 接近 7×24 | GPU 推理 + 多租户主机 | Daniel Mac Studio |
| **Android** | ❌ 随身携带 | 移动感知（通知/位置/SMS/相机） | Redmi Turbo 4 |
| **iOS** | ❌ 随身携带 | 语音交互 + Talk Mode | iPhone |

### 4.4 网络代理注意事项

| 设备 | 代理 | 注意事项 |
|------|------|---------|
| daniel-ubuntu | Clash fake-ip | 已修复：telegram.org + ts.net 加入 fake-ip-filter |
| 小m Mac Mini | Mac Clash | **不稳定**，Telegram 依赖 Linux 代理转发 |
| 其他设备 | 无/直连 | 无特殊处理 |

**铁律**: 所有 Tailscale 100.x.x.x 请求必须 `--noproxy "*"` 或 `no_proxy=100.0.0.0/8`

---

## 五、跨机通信协议

### 5.1 通信方式矩阵

| 方式 | 延迟 | 适用场景 | 安全等级 | 命令 |
|------|------|---------|---------|------|
| **SSH 直接执行** | <1s | 一次性命令、部署 | 🟢 加密隧道 | `ssh user@host "cmd"` |
| **Gateway API** | <1s | Agent 间通信 | 🟢 Token 认证 | `curl Gateway/api/...` |
| **sessions_send** | ~1s | 给活跃 agent 派任务 | 🟡 Session 绑定 | `sessions_send(key, msg)` |
| **sessions_spawn** | ~2s | 创建隔离子任务（并行） | 🟡 隔离 session | `sessions_spawn(agent, task)` |
| **nodes.run** | ~1s | 远程节点命令执行 | 🟡 需审批 | `nodes run --node X -- cmd` |
| **消息通道** | ~1-5s | Telegram/Discord 群通知 | 🟢 平台加密 | `message(action=send)` |
| **飞书 API** | ~2s | 飞书群/文档操作 | 🟢 App 认证 | `feishu-send.sh` |

### 5.2 通信决策树

```
需要通信？
├── 本机 agent 间？
│   ├── 独立任务 → sessions_spawn (并行隔离)
│   ├── 需上下文 → sessions_send (群聊内)
│   └── 需群聊反馈 → message (群发)
├── 跨机器？
│   ├── 已有 Gateway → Gateway API / sessions_send
│   ├── 无 Gateway → SSH 直接执行
│   └── 移动设备 → nodes.run (需先配对)
└── 对外通信？
    ├── Telegram/Discord → message tool
    ├── 飞书 → feishu-send.sh
    └── 邮件/社交媒体 → 需 Daniel 确认
```

### 5.3 小m 跨机通信实战配置

```bash
# Gateway API 通信
TOKEN=$(pass show api/xiaom-gateway-token)
curl -X POST "http://daniellimac-mini.tail0db0a3.ts.net:18789/api/sessions/send" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"sessionKey":"agent:main:telegram:group:<chatId>","message":"消息内容"}'

# SSH 执行（绕过 Clash）
ssh danielli@daniellimac-mini.tail0db0a3.ts.net "command"

# Ollama 调用（绕过 Clash）
IP=$(tailscale status | grep daniellimac-mini | awk '{print $1}')
curl --noproxy "*" "http://$IP:11434/api/generate" -d '{"model":"qwen3:8b","prompt":"test"}'
```

---

## 六、权限模型与安全基线

### 6.1 分层安全模型

```
┌──────────────────────────────────────────┐
│ Layer 5: 治理层 — 审计/回顾/审批流       │
├──────────────────────────────────────────┤
│ Layer 4: 数据层 — 密钥/隐私/金融         │
├──────────────────────────────────────────┤
│ Layer 3: 行为层 — Tool allow/deny/宪法   │
├──────────────────────────────────────────┤
│ Layer 2: 调度层 — Spawn矩阵/并发/超时   │
├──────────────────────────────────────────┤
│ Layer 1: 基础设施 — Gateway/Tailscale    │
└──────────────────────────────────────────┘
```

### 6.2 Agent 权限矩阵

| Agent | Spawn | Shell | 金融 | 对外通信 | 密钥 |
|-------|-------|-------|------|---------|------|
| **main (CEO)** | ✅ 全部 | ✅ 任意 | ⚠️ 需确认 | ⚠️ 需确认 | ✅ pass |
| **ops** | ❌ | ✅ 运维 | ❌ | ✅ 告警 | ✅ pass |
| **code** | ❌ | ✅ 开发 | ❌ | ❌ | ❌ |
| **quant** | ✅ 3个下游 | ❌ | ⚠️ 只读+信号 | ❌ | ❌ |
| **research** | ❌ | ✅ 只读 | ❌ | ❌ | ❌ |
| **content** | ❌ | ❌ | ❌ | ⚠️ 需确认 | ❌ |
| **data** | ❌ | ✅ 数据 | ❌ | ❌ | ❌ |
| **finance** | ❌ | ❌ | ✅ 只读分析 | ❌ | ❌ |
| **market** | ❌ | ❌ | ❌ | ⚠️ 需确认 | ❌ |
| **pm/law/product/sales** | ❌ | ❌ | ❌ | ❌ | ❌ |

### 6.3 三条安全铁律（历史 4 次事故总结）

**铁律 1: 永不明文记录密钥**
- ❌ 禁止在 memory/*.md、MEMORY.md、任何 .md 文件中记录真实密钥
- ✅ 统一用 `pass show api/xxx` 引用

**铁律 2: Push 前三层安全扫描**
1. `grep -rn` 扫描关键模式（sk-、api_key、token、secret）
2. `pre-push-security-scan.sh` 覆盖 `.md` 文件
3. 人工确认 git diff 输出

**铁律 3: 第三方 Skill 安全审计**
- 新 Skill 安装前检查是否内含作者密钥
- `git-filter-repo` 作为最后清理手段

### 6.4 密钥管理架构

```
pass (金库，唯一真相源)
  ↓ rebuild-env.sh
~/.openclaw/.env (运行时环境变量，chmod 600)
  ↓ systemd EnvironmentFile=
Gateway 进程环境变量
  ↓ ${VAR_NAME} 引用
openclaw.json + agents/*/models.json（零硬编码）
```

**换 key 流程**: `pass insert api/xxx` → `rebuild-env.sh` → `systemctl restart` → `verify-keys.sh`

---

## 七、日志审计体系

### 7.1 审计事件分级

| 级别 | 事件类型 | 保留 | 示例 |
|------|---------|------|------|
| **P0** | 金融操作 | 永久 | quant 下单、资金转移 |
| **P1** | 权限/配置变更 | 90d | config.apply、allowAgents |
| **P1** | 对外通信 | 90d | 邮件、社交媒体发布 |
| **P2** | Shell 执行 | 30d | exec 调用及返回值 |
| **P2** | Agent spawn | 30d | sessions_spawn 调用 |
| **P3** | 日常操作 | 7d | read/write/search |

### 7.2 当前替代方案（OpenClaw 原生审计未上线前）

| 方案 | 实现 | 优点 | 缺点 |
|------|------|------|------|
| **Git 审计** | 所有变更 git commit | 天然审计链 | 仅覆盖文件操作 |
| **Memory 审计** | 关键操作写入 daily memory | 已有基础设施 | 非结构化 |
| **Cron 审计脚本** | `audit-log.py` 定期扫描 | 自动化 | 需开发 |

### 7.3 安全响应 SOP

```
P0 事故响应:
1. 止血 (5min) — 轮换密钥/kill session/停止服务
2. 评估 (10min) — 影响范围/数据泄露/操作记录
3. 通知 Daniel (15min) — 简报+决策事项
4. 根因分析 (1h) — 5-Why + 防复发措施
5. 记录复盘 — memory + MEMORY.md 更新
```

---

## 八、MVP 路线图

### Phase 0: 基线加固（本周，~2 天）

| # | 任务 | 负责 | 工作量 | 优先级 |
|---|------|------|-------|-------|
| 1 | exec allowlist 配置 | 小ops | 1h | P0 |
| 2 | per-agent tool deny (content/law/pm/sales 无 exec) | 小ops | 2h | P0 |
| 3 | Polymarket 钱包私钥轮换 | Daniel | 30min | P0 |
| 4 | audit-log.py 脚本 | 小code | 3h | P1 |
| 5 | pre-push 扫描覆盖 .md 文件 | 小code | 1h | P1 |

### Phase 1: 节点恢复与扩展（第 2 周）

| # | 任务 | 负责 | 工作量 | 优先级 |
|---|------|------|-------|-------|
| 6 | 小m Mac Mini 节点恢复持续在线 | 小ops | 2h | P1 |
| 7 | Android 节点配对（通知/位置/相机） | Daniel | 30min | P1 |
| 8 | 浏览器自动化实战验证 | 小data | 4h | P1 |
| 9 | 小m SSH 反向隧道持久化 (autossh) | 小ops | 3h | P0 |
| 10 | Canvas 监控面板 MVP | 小code | 1天 | P2 |

### Phase 2: 军团实战（第 3-4 周）

| # | 任务 | 负责 | 工作量 | 优先级 |
|---|------|------|-------|-------|
| 11 | MediaClaw R4-R5 真实发布验证 | 小code | 3天 | P1 |
| 12 | 内容工厂流水线上线 | 小content + 小data | 5天 | P1 |
| 13 | Quant 量化系统 cron 修复 + 验证 | 小quant + 小ops | 2天 | P0 |
| 14 | deploy-to-remote Skill 开发 | 小code | 2天 | P2 |
| 15 | 统一知识库整合 (QMD) | 小data | 5天 | P1 |

### Phase 3: 规模化（第 2 个月）

| # | 任务 | 负责 | 工作量 | 优先级 |
|---|------|------|-------|-------|
| 16 | Mac Studio 多租户部署 | 小code + 小ops | 5天 | P1 |
| 17 | Talk Mode 语音对话配置 | 小ops | 2天 | P2 |
| 18 | Security Dashboard 可视化 | 小code | 3天 | P2 |
| 19 | 自动密钥轮换 cron | 小ops | 1天 | P2 |
| 20 | 拓客智能体 MVP | 小pm + 小sales | 10天 | P2 |

### Phase 4: 生态（第 3 个月+）

| # | 任务 | 负责 | 优先级 |
|---|------|------|-------|
| 21 | 自研 Skill 发布到 ClawHub | CEO | P2 |
| 22 | 零信任 Agent 网络 | 小ops | P3 |
| 23 | 灾难恢复方案 | 小ops | P2 |
| 24 | 移动端全面集成 (iOS + Android) | Daniel | P3 |

### 路线图时间线

```
Week 1 (04/03-04/09):  Phase 0 基线加固 + Phase 1 启动
Week 2 (04/10-04/16):  Phase 1 节点恢复 + Phase 2 开始
Week 3-4 (04/17-04/30): Phase 2 军团实战
Month 2 (05/01-05/31): Phase 3 规模化（Mac Studio 多租户）
Month 3+ (06/01+):     Phase 4 生态建设
```

---

## 九、各军团模板

### 9.1 开发军团模板

**触发**: 新项目开发、Bug 修复、功能迭代

```
角色: 小pm (拆解) → 小code (编码) → 小ops (部署) → CEO (审核)

SOP:
1. PRD 编写 → 小pm (含验收标准)
2. CEO 审阅 → Daniel 确认
3. 任务拆解 → 小pm (标注依赖/并行)
4. 编码实现 → 小code (自测+安全扫描)
5. 代码评审 → CEO/小pm
6. 部署上线 → 小code (Nginx/Docker/SSL)
7. 监控配置 → 小ops
8. 复盘归档 → CEO

文件结构:
projects/<name>/
├── PRD-*.md
├── tasks.md
├── acceptance-criteria.md
├── src/
└── deploy.sh

关键教训:
- 不写 PRD 就编码 = 浪费时间
- 职责清晰：小code 做部署，小ops 管 Gateway
- 评审是质量最后防线
```

### 9.2 内容军团模板

**触发**: 小红书/公众号/抖音内容生产

```
角色: 小data (热点) → 小research (调研) → 小content (创作) → 小market (发布)

SOP:
1. 热点采集 → 小data (cron 定时 + API)
2. 话题调研 → 小research (深度素材)
3. 内容创作 → 小content (文案+配图)
4. 平台适配 → 小content (不同平台不同风格)
5. 发布策略 → 小market (时机/标签/渠道)
6. 数据反馈 → 小data (阅读/互动数据)

平台风格矩阵:
| 平台 | 风格 | 长度 | 图片 |
|------|------|------|------|
| 小红书 | 口语化、emoji、清单体 | 500-1000字 | 3-9张 |
| 公众号 | 专业、深度、结构化 | 2000-5000字 | 封面+内嵌 |
| 抖音 | 短平快、反转、吸引注意力 | 脚本30-60秒 | 封面 |
| 视频号 | 正式、权威 | 脚本30-120秒 | 封面 |

内容方向: AI最新技术 + 先进思想 (Daniel 明确指定)
```

### 9.3 量化军团模板

**触发**: 市场分析、交易信号、策略回测

```
角色: 小quant (策略) → 小data (数据) → 小finance (核算) → Daniel (决策)

SOP:
1. 市场扫描 → 小quant (cron 每3h)
2. 策略分析 → 小quant (每天9:00)
3. 信号生成 → 小quant (只生成信号，不自动执行)
4. 人工确认 → Daniel (必须确认后才执行)
5. 执行记录 → 小finance (盈亏记录)
6. 定期复盘 → 小quant + 小finance

风控铁律:
- 70% 稳健策略 (90%+ 胜率) + 30% 猎手策略
- 任何交易信号必须经 Daniel 确认
- 止损线严格执行 (SL1 提醒, SL2 自动告警)
- 仓位控制：单笔 ≤ 总资金 10%

当前产品: Polymarket 预测市场
未来扩展: A股、BTC、外汇
```

### 9.4 运维军团模板

**触发**: 系统维护、监控告警、故障响应

```
角色: 小ops (执行) → CEO (协调)

SOP:
1. 健康检查 → cron (每6h API检查, 每12h 自省)
2. 告警响应 → P0 立即处理, P1 当天, P2 排期
3. 配置变更 → schema lookup → 最小修改 → 验证 → restart
4. Cron 维护 → 每日巡检, 异常立即修复
5. 磁盘/资源监控 → 定期清理, session 文件管理

工具链:
- healthcheck skill (API健康检查)
- linux-service-triage (服务诊断)
- sysadmin-toolbox (系统运维)
- entropy-scan.sh (熵扫描)

关键职责边界:
- ✅ Gateway 管理、Agent 配置、cron、监控、安全巡检
- ❌ 项目部署 (交给小code)
- ❌ 业务代码 (交给小code)
```

### 9.5 物理交互军团模板

**触发**: 设备控制、摄像头、屏幕、语音、位置

```
角色: CEO (调度) → Nodes (执行)

SOP:
1. 节点状态检查 → nodes status
2. 权限验证 → 确认节点在线 + 权限已开启
3. 执行操作 → camera/screen/location/run
4. 结果分析 → AI 分析感知数据
5. 行动响应 → 通知/Canvas/语音/TTS

SDA 闭环 (感知→决策→行动):
  感知: 摄像头/屏幕/位置/通知
  决策: Agent 分析 + 规则引擎
  行动: Canvas推送/语音播报/远程执行/消息通知

设备优先级:
1. Android — 移动感知中心 (通知/位置/SMS/相机)
2. Mac Mini — 持续在线节点 (Canvas/Ollama/远程执行)
3. iOS — 语音交互终端 (Talk Mode)
```

### 9.6 顾问军团模板

**触发**: 法务审查、产品评审、竞品分析、拓客

```
角色: 小law / 小product / 小sales (独立执行) → CEO (审核)

SOP:
1. 需求分析 → CEO 理解 Daniel 需求
2. 派任务 → 按职责分配
3. 独立执行 → 各自产出
4. CEO 审核 → 质量把控
5. 汇报 Daniel → 带结论和建议

当前项目:
- 小law: 法务合规审查 (11个skill)
- 小product: 产品设计/竞品分析 (5个skill)
- 小sales: 拓客智能体 (5个skill)
```

---

## 十、Daniel 的执行清单

### 🔴 立即执行（今天）

```bash
# 1. Polymarket 钱包私钥轮换（已泄露 40+ 天）
# → 登录 Polymarket 网站执行

# 2. 审阅本文件
# → 确认路线图优先级是否正确

# 3. 决定 Android 节点配对时机
# → Redmi Turbo 4 离线 16 天，需上线后配对
```

### 🟡 本周执行

```bash
# 4. Mac Studio 部署规划
# → 购买确认后，按 Phase 3 多租户方案执行

# 5. 确认小m OpenClaw 升级状态
# → 昨晚群聊 session 在执行 npm 升级，确认是否成功

# 6. 删除旧仓库（待确认）
# → opencaio/tuoke-agent 是否删除？
# → ~/clawd/agent-pack-tuoke/ 空仓库是否清理？
```

### 🟢 下周执行

```bash
# 7. 内容工厂流水线启动
# → 小data 采集热点 → 小content 创作 → 小market 发布

# 8. MediaClaw R4 真实发布验证
# → 至少 1 个平台 live 跑通

# 9. Quant cron 修复验证
# → 确保 3 个失败 cron 全部恢复
```

---

## 附录 A: 关键文件路径速查

| 文件 | 路径 |
|------|------|
| 主配置 | `~/.openclaw/openclaw.json` |
| CEO 模型 | `~/.openclaw/agents/main/agent/models.json` |
| 密钥环境 | `~/.openclaw/.env` |
| 工作空间 | `~/clawd/` |
| 项目目录 | `~/clawd/projects/` |
| Skills | `~/clawd/skills/` + `~/.openclaw/skills/` |
| 报告 | `~/clawd/reports/` |
| 日记忆 | `~/clawd/memory/YYYY-MM-DD.md` |
| 长期记忆 | `~/clawd/MEMORY.md` |
| 灵魂宪章 | `~/clawd/SOUL.md` |
| 团队规则 | `~/clawd/AGENTS.md` |
| 用户画像 | `~/clawd/USER.md` |

## 附录 B: 关键命令速查

```bash
# Gateway
openclaw gateway status/start/stop/restart

# Agent 调度
sessions_spawn(agentId="code", task="...", label="xxx")
sessions_send(sessionKey="agent:code:telegram:group:xxx", message="...")

# 跨机
ssh danielli@daniellimac-mini.tail0db0a3.ts.net "cmd"
curl --noproxy "*" "http://$IP:11434/api/generate" -d '...'

# 密钥
pass show api/xxx
pass insert api/xxx

# 安全
~/clawd/scripts/pre-push-security-scan.sh
git-filter-repo --invert-paths --path <bad-file>

# 监控
openclaw status
tailscale status
```

---

## 附录 C: 蜂群学习产出清单

| 产出 | 路径 |
|------|------|
| R5 开发军团 | `reports/openclaw-swarm-learning/round-05.md` |
| R8 物理交互军团 | `reports/openclaw-swarm-learning/round-08.md` |
| R9 安全治理 | `reports/openclaw-swarm-learning/round-09.md` |
| R10 最终方案 | `reports/openclaw-swarm-learning/final-plan.md` (本文件) |
| 量化学习 20 轮 | `reports/quant-learning/` (20份, 236KB) |

---

*蜂群学习 10/10 完成 | 2026-04-03 09:03*
*从学习到落地，从理论到实战。这不是终点，是起跑线。*
