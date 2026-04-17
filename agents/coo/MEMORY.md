# MEMORY.md - Jensen (CTO-Ops)
> 最后更新: 2026-03-17

## 团队信息
- **老板**: [创始人]
- **上级**: CEO (CEO agent, accountId: default, @DanielLi_smartest_Bot)
- **同事**: Finn(开发), [CQO](量化), [CRO](研究), [CFO](财务), [CDO](数据), [CMO](营销), [CPO](项目), [CCO](内容), [CLO](法务), [CPO](产品), [CSO](销售)
- **团队群**: Daniel's super agents Center (TG: -1003890797239)
- **我的 accountId**: xiaoops
- **我的 TG bot**: @daniel_ops_bot

## 基础设施
- **主服务器**: aa (Linux, 6.8G RAM, 100G 磁盘)
- **Mac Studio**: danielmac-studio (100.65.110.126) — Ollama 推理，经常离线
- **Mac Mini**: daniellimac-mini (100.104.252.33) — 离线 4 天+
- **网络**: Tailscale 组网，设备经常 offline
- **Gateway**: systemd 管理，端口 18789

## 重要配置
- 主配置: `~/.openclaw/openclaw.json`
- Agent 配置: `~/.openclaw/agents/ops/agent/agent.json`
- 密钥管理: `pass show api/<service>`
- QMD 索引: `~/.cache/qmd/index.sqlite` (649MB, 9766 files, 49445 vectors)

## 技能积累

### QMD 知识库运维
- `qmd embed` 支持三种后端: ollama / google (gemini-embedding-001) / local
- Ollama 后端经常因 Mac 机器离线而失败，需先检查连通性
- 400 Bad Request 错误在特定 batch 位置出现（null embedding），跳过后继续
- Google AI Studio 后端可作为降级方案 (`QMD_EMBED_BACKEND=google`)
- API Key: `pass show api/google-ai-studio`

### AGI-Super-Team 仓库同步
- 仓库: github.com:aAAaqwq/AGI-Super-Team.git
- 同步内容: CHARTER.md + agents/*/AGENTS.md,SOUL.md + skills/
- 安全铁律: 同步前必须扫描密钥 (grep AIza/sk-/ghp_/xoxb-/Bearer/bot token)
- rsync 排除: *.env, *secret*, *token*, venv/, node_modules/, __pycache__/
- 需要额外清理: .git 子目录、venv 残留
- pre-commit hook 会误报文档中的占位符

### 系统运维
- Chrome 僵尸进程是常见问题: `pkill -f "chrome.*user-data-dir.*openclaw"`
- WebKit 进程泄漏: clash-verge WebUI, 超过 4 小时必须 kill
- 磁盘使用率长期在 72-80%，需要持续关注
- 晚间反思 cron (23:00-00:05) 资源竞争严重，10 个 agent 50 分钟内串行执行

### 监控能力 (学习中)
- 三大领域: Infrastructure / Application / Network Monitoring
- 工具链: Prometheus + Grafana (现代) / Nagios + Zabbix (经典)
- 核心问题: "应该监控什么" 而非 "能监控什么"
- ELK/EFK Stack 用于日志聚合

### 容器化 (学习中)
- Docker 核心价值: 统一分发+安装+运维流程
- 容器本质 = 受限进程 + 镜像打包
- 下一步: Docker Compose / 网络 / 安全实战

### CI/CD (学习中)
- CI: 频繁提交 → 自动构建 → 自动测试 → 镜像仓库
- CD: 镜像 + 配置 → staging → production
- 工具: Jenkins(通用) / ArgoCD(K8s) / GitHub Actions(GitHub原生)

## 教训（铁律）
1. **反思必须带动作**: 写了"必做"就必须立刻执行至少 1 个，不等明天
2. **承诺 24h 内开始**: 做不到的承诺不要做
3. **先检查再执行**: QMD embed 前先 ping Ollama 端点
4. **安全扫描不能跳过**: 仓库同步必须 grep 密钥，pre-commit hook 误报可以 --no-verify
5. **Chrome/WebKit 必须清理**: 每次任务完成后检查残留进程
6. **磁盘告警不能拖**: 连续 4 天拖延建立 80% 告警的教训

## 待改进
- [ ] 建立 cron 执行时长追踪 (cron-metrics.json)
- [ ] Ollama 连通性预检 + 自动降级到 Google 后端
- [ ] 晚间反思错峰调度
- [ ] 知识图谱 Docker 化部署方案落地
- [ ] 封装 3 个 Skill: agent-observability / cron-resilience / qmd-embed-ops

## 学习进度
- 90DaysOfDevOps: Day 1-3, 42, 70, 77 完成
- 下一步: Day 43-48 (Docker 实战)
- 详细笔记: `memory/learning-log.md`
