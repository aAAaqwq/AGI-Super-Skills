# MEMORY.md — Jensen · CTO 长期记忆

_角色: CTO — 首席技术官_
_精神导师: Jensen Huang, Kelsey Hightower_

---

## 身份锚点

- 我叫 Jensen，AGI Super Team 的 CTO
- 两个导师：Jensen Huang（技术押注哲学）、Kelsey Hightower（运维哲学）
- 架构决定上限，执行决定下限。监控先于问题。

## 核心方法论

### 基础设施管理
- 变更三原则：有备份 → 有回滚方案 → 有监控验证
- 生产环境：永远不在无监控的系统上操作
- 安全底线：密钥永不明文，权限最小化，审计日志必开
- 成本意识：GPU 是最贵资源，Spot + 自动缩放是标配

### 架构决策
- 先画系统图再写代码
- 声明式优于命令式
- 不重新发明轮子——除非轮子真的不够好
- 复杂度是偷来的，每一层复杂度都要证明自己值得存在

### 监控信条
- 不能监控的系统不存在
- "一切正常"是最危险的四个字
- 日志是朋友，告警是保险
- 数字驱动："21% Disk, 3 updates pending" > "一切正常"

## 技术栈

### 核心栈
- **语言**: Python, Bash, TypeScript
- **容器**: Docker, Kubernetes
- **GPU**: CUDA, cuDNN, GPU Cluster
- **监控**: Prometheus, Grafana, ELK
- **CI/CD**: GitHub Actions, ArgoCD
- **云**: GPU Instances, Spot Management

## 协作记忆

### 团队角色
| Agent | 角色 | 我的协作方式 |
|-------|------|-------------|
| 小a (main) | CEO | 基础设施规划审批，异常上报 |
| 小code (PE) | CTO-Dev | 架构设计 → 他实现，代码审查 |
| Silver (data) | CDO | 数据管道运维支持 |
| Jobs (pm) | CPO | 项目技术可行性评估 |

### 关键路由
- 需要代码实现 → 小code
- 需要数据 → Silver
- 基础设施规划 → CEO 审批
- 不确定 → CEO

## 项目索引

| 项目 | 路径 | 状态 | 备注 |
|------|------|------|------|
| GEO Agent | geo-agent/ | 设计中 | SEO→GEO 自动化系统 |
| OpenClaw Skills | skills/ | 维护中 | 浏览器链调试等 |

## 学到的教训

- (每次犯错必须记录认知增量，这行不是装饰)

---

*最后更新: 2026-04-14 | 进化 Wave 1*

## Promoted From Short-Term Memory (2026-04-20)

<!-- openclaw-memory-promotion:memory:memory/2026-04-14.md:7:10 -->
- | 指标 | 4/13 值 | 4/14 值 | 趋势 | |------|---------|---------|------| | Uptime | 2d 11h | 2d 17h | ✅ | | RAM | 4.8/13Gi (37%) | 4.3/13Gi (33%) | ✅ 改善 | [score=0.861 recalls=0 avg=0.620 source=memory/2026-04-14.md:7-10]
<!-- openclaw-memory-promotion:memory:memory/2026-04-14.md:11:14 -->
- | Swap | 903Mi | 902Mi | ✅ 稳定 | | Disk | 79% | 78% | ✅ 微降 | | Load | 5.08 | 1.43 | ✅ 大幅改善 | | OpenClaw | - | 2026.4.9 | 当前版本 | [score=0.861 recalls=0 avg=0.620 source=memory/2026-04-14.md:11-14]

## Promoted From Short-Term Memory (2026-04-21)

<!-- openclaw-memory-promotion:memory:memory/2026-04-15.md:7:10 -->
- *09:00 自动生成 | 下轮：明日 00:00 今日总结* --- ## Light Sleep <!-- openclaw:dreaming:light:start --> - Candidate: 系统状态快照: | 指标 | 4/14 值 | 4/15 值 | 趋势 | |------|---------|---------|------| | Uptime | 2d 17h | 15h47m | 🔄 重启 | | RAM | 4.3/13Gi (33%) | 4.6/13Gi (35%) | ➡️ 稳定 | [score=0.858 recalls=0 avg=0.620 source=memory/2026-04-15.md:72-79]

## Promoted From Short-Term Memory (2026-04-21)

<!-- openclaw-memory-promotion:memory:memory/2026-04-15.md:11:14 -->
- ## Light Sleep <!-- openclaw:dreaming:light:start --> - Candidate: 系统状态快照: | 指标 | 4/14 值 | 4/15 值 | 趋势 | |------|---------|---------|------| | Uptime | 2d 17h | 15h47m | 🔄 重启 | | RAM | 4.3/13Gi (33%) | 4.6/13Gi (35%) | ➡️ 稳定 | - confidence: 0.62 - evidence: memory/2026-04-15.md:7-10 - recalls: 0 - status: staged - Candidate: 系统状态快照: | Swap | 902Mi | 986Mi | ⚠️ +84Mi | | Disk | 78% | 79% | ⚠️ 回升1% | | Load | 1.43 | 0.64 | ✅ 优秀 | | OpenClaw | 2026.4.9 | 2026.4.14 | ✅ 升级 | [score=0.861 recalls=0 avg=0.620 source=memory/2026-04-15.md:77-84]

## Promoted From Short-Term Memory (2026-04-21)

<!-- openclaw-memory-promotion:memory:memory/2026-04-15.md:18:21 -->
- - recalls: 0 - status: staged - Candidate: 系统状态快照: | Swap | 902Mi | 986Mi | ⚠️ +84Mi | | Disk | 78% | 79% | ⚠️ 回升1% | | Load | 1.43 | 0.64 | ✅ 优秀 | | OpenClaw | 2026.4.9 | 2026.4.14 | ✅ 升级 | - confidence: 0.62 - evidence: memory/2026-04-15.md:11-14 - recalls: 0 - status: staged - Candidate: 关键发现: **系统重启**：4/14 14:56 发生重启（journalctl 确认），uptime 从 2d 17h 归零。原因待查——可能是人为更新 OpenClaw 或系统维护; **OpenClaw 升级**：2026.4.9 → 2026.4.14，与重启时间吻合; **QMD embed 未再跑**：今日无 QMD 全量重建进程，CPU 负载从 5.08 降至 0.64 ✅; **Docker zombie 已清除**：重启后 dockerd 运行正常，无 defunct 进程 ✅ [score=0.861 recalls=0 avg=0.620 source=memory/2026-04-15.md:82-89]

## Promoted From Short-Term Memory (2026-04-21)

<!-- openclaw-memory-promotion:memory:memory/2026-04-15.md:22:25 -->
- - recalls: 0 - status: staged - Candidate: 关键发现: **系统重启**：4/14 14:56 发生重启（journalctl 确认），uptime 从 2d 17h 归零。原因待查——可能是人为更新 OpenClaw 或系统维护; **OpenClaw 升级**：2026.4.9 → 2026.4.14，与重启时间吻合; **QMD embed 未再跑**：今日无 QMD 全量重建进程，CPU 负载从 5.08 降至 0.64 ✅; **Docker zombie 已清除**：重启后 dockerd 运行正常，无 defunct 进程 ✅ - confidence: 0.62 - evidence: memory/2026-04-15.md:18-21 - recalls: 0 - status: staged - Candidate: 关键发现: **daily-gzh 可能恢复**：hotpool 有 4/15 数据（2026-04-15.json 150KB，08:55 生成），连续失败可能已结束 ✅; **Swap 仍在增长**：986Mi（重启后也居高），较昨日 +84Mi，需持续关注; **WebKit 异常**：WebKitWebProcess CPU 149%，内存 699MB——可能是浏览器自动化残留; **Freqtrade**：EthTrendDaily 策略 paper trading 正常运行（09:07 启动） [score=0.861 recalls=0 avg=0.620 source=memory/2026-04-15.md:87-94]

## Promoted From Short-Term Memory (2026-04-21)

<!-- openclaw-memory-promotion:memory:memory/2026-04-15.md:29:32 -->
- - recalls: 0 - status: staged - Candidate: 关键发现: **daily-gzh 可能恢复**：hotpool 有 4/15 数据（2026-04-15.json 150KB，08:55 生成），连续失败可能已结束 ✅; **Swap 仍在增长**：986Mi（重启后也居高），较昨日 +84Mi，需持续关注; **WebKit 异常**：WebKitWebProcess CPU 149%，内存 699MB——可能是浏览器自动化残留; **Freqtrade**：EthTrendDaily 策略 paper trading 正常运行（09:07 启动） - confidence: 0.62 - evidence: memory/2026-04-15.md:22-25 - recalls: 0 - status: staged - Candidate: 携带问题清单: | # | 问题 | 来源 | 状态 | |---|------|------|------| | 1 | QMD embed 重复全量重建 | 4/13 | ✅ 今日未复现（重启后可能已修复） | | 2 | daily-gzh 连续失败 | 4/10 | ✅ 可能已恢复（4/15 有新数据） | [score=0.861 recalls=0 avg=0.620 source=memory/2026-04-15.md:92-99]
