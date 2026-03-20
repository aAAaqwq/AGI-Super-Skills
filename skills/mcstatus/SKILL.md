# SKILL.md - Model Configuration Status (mcstatus)

## 触发条件
- `/mcstatus` 命令
- 用户询问模型配备、模型配置、model status、模型列表等

## 功能
实时生成 Agent + Cron 的模型配置报告，展示当前所有 agent 的主模型/fallback链和所有 cron 任务的模型分配。

## 执行步骤

### Step 1: 收集 Agent 模型配置

读取各 agent 的 models.json 获取主模型和 fallback 链：

```bash
for agent in main ops code quant data research content market finance pm law product sales batch; do
  config=$(cat ~/.openclaw/agents/$agent/agent/models.json 2>/dev/null)
  if [ -n "$config" ]; then
    echo "=== $agent ==="
    echo "$config" | python3 -c "
import sys,json
d=json.load(sys.stdin)
primary=d.get('primary','inherit')
fallbacks=d.get('fallbacks',d.get('fallback',[]))
print(f'  主模型: {primary}')
print(f'  Fallback: {\" → \".join(fallbacks)}')
" 2>/dev/null
  fi
done
```

### Step 2: 收集 Cron 任务模型

```bash
# 使用 cron list API 获取所有任务
# 然后提取每个 job 的 model 字段
```

实际使用 `cron(action='list')` 工具获取完整任务列表，提取每个任务的：
- `payload.model`（显式指定的模型）
- `agentId`（所属 agent）
- `name`（任务名）
- `enabled`（是否启用）
- `schedule`（执行时间）

### Step 3: 生成报告

按以下格式生成报告：

```
📊 模型配置总览 | {YYYY-MM-DD HH:MM}
━━━━━━━━━━━━━━━━━━━━

## 🤖 Agent 模型 ({N}个)

| Agent | 主模型 | Fallback |
|-------|--------|----------|
| main | xsc-opus46 | → zai-turbo → kimi → m2.5 → ollama/qwen3.5:9b |
| ... | ... | ... |

## ⏰ Cron 模型分布 ({N}个活跃)

| 模型 | 数量 | 占比 |
|------|------|------|
| zai/glm-5-turbo | X | X% |
| ... | ... | ... |

### 按模型分组

**zai/glm-5-turbo ({N}个)**
- 任务1 (agent, 时间)
- 任务2 (agent, 时间)

**minimax/MiniMax-M2.5 ({N}个)**
- ...

**ollama/qwen3.5:9b ({N}个)**
- ...

### ⚠️ 异常任务
- [任务名]: [原因]

## 📊 成本估算
- 云API任务: X个 ({X}%)
- 本地Ollama任务: X个 ({X}%)
- systemEvent: X个
```

## 报告规则

1. **Agent 配置**：从 `~/.openclaw/agents/<id>/agent/models.json` 实时读取
2. **Cron 配置**：从 `cron(action='list')` 实时获取
3. **模型别名**：使用简短别名显示（见下表）
4. **异常检测**：标记 consecutiveErrors > 0 的任务
5. **禁用任务**：单独列出已禁用的任务

## 模型别名映射

| 全称 | 别名 |
|------|------|
| xingsuancode/claude-opus-4-6 | xsc-opus46 |
| zai/glm-5-turbo | zai-turbo |
| minimax/MiniMax-M2.5 | m2.5 |
| xingjiabiapi/gemini-3-pro-preview | xjb-g3p |
| moonshot/kimi-k2.5 | kimi |
| ollama/qwen3.5:9b | ollama/qwen3.5:9b |
| zai/glm-5 | glm5 |

## 注意事项
- 每次调用都是实时数据，反映最新配置
- 不缓存结果
- 报告控制在 3000 字以内
- 适配 Telegram 格式（纯文本/Markdown）
