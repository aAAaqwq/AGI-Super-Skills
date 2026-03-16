# team-memory-sync

团队记忆同步与认知审计工具。

## 功能

### 1. sync-user
将 USER-TEMPLATE.md 同步到所有 agent。

```bash
./scripts/sync.sh sync-user
```

### 2. sync-charter
确保所有 agent AGENTS.md 引用 CHARTER.md。

```bash
./scripts/sync.sh sync-charter
```

### 3. audit
认知审计 — 要求所有 agent 汇报对 Daniel 和团队宪章的认知。

```bash
./scripts/sync.sh audit
```

### 4. freshness
检查各 agent 记忆文件新鲜度（最后修改时间）。

```bash
./scripts/sync.sh freshness
```

### 5. broadcast
向所有 agent 广播重要更新。

```bash
./scripts/sync.sh broadcast "重要消息内容"
```

## 使用场景

- **新人入职**: `sync-user` + `sync-charter`
- **定期审计**: 每周执行 `audit` 确保认知对齐
- **宪章更新**: `sync-charter` 通知所有 agent
- **紧急通知**: `broadcast "消息"`

## Agent 列表

12 个 C-Suite Agent:
- ops, code, quant, content, data, finance
- research, market, pm, law, product, sales

## 依赖

- OpenClaw sessions_send API
- CHARTER.md 在 ~/clawd/
- USER-TEMPLATE.md 在 ~/.openclaw/agents/

---

*Created: 2026-03-16*
*Author: 小a (CEO)*
