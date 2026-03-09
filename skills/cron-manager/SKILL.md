# Cron Manager Skill

定时任务管理专家。负责创建、监控、诊断和修复 OpenClaw cron 任务。

## 核心能力

### 1. 创建任务
根据用户需求准确创建 cron 任务，支持：
- 自然语言时间描述（"每天早上9点"、"工作日下午3点"）
- 多种调度类型（定时、间隔、一次性）
- 自动选择最佳模型和配置

### 2. 健康检查
- 检测失败的任务
- 分析错误原因
- 自动修复常见问题

### 3. 任务管理
- 列出所有任务
- 启用/禁用任务
- 更新任务配置
- 删除任务

---

## 创建任务指南

### 时间表达式速查

#### Cron 表达式格式
```
分 时 日 月 周
```

| 需求 | 表达式 | 说明 |
|------|--------|------|
| 每天 9:00 | `0 9 * * *` | |
| 每天 9:30 | `30 9 * * *` | |
| 工作日 9:00 | `0 9 * * 1-5` | 周一到周五 |
| 周末 10:00 | `0 10 * * 0,6` | 周日和周六 |
| 每小时整点 | `0 * * * *` | |
| 每30分钟 | `*/30 * * * *` | |
| 每天多次 | `0 9,12,18 * * *` | 9点、12点、18点 |
| 每月1号 | `0 9 1 * *` | |

#### 间隔调度
| 需求 | everyMs |
|------|---------|
| 每5分钟 | 300000 |
| 每15分钟 | 900000 |
| 每30分钟 | 1800000 |
| 每小时 | 3600000 |
| 每3小时 | 10800000 |
| 每6小时 | 21600000 |
| 每12小时 | 43200000 |
| 每天 | 86400000 |

### 模型选择指南

| 任务类型 | 推荐模型 | 原因 |
|---------|---------|------|
| 简单脚本执行 | `xingjiabiapi/gemini-3-flash-preview` | 快速、低成本、稳定 |
| 复杂推理/学习 | `anapi/claude-opus-4-5-20250514` | 高质量输出 |
| 中文内容生成 | `moonshot/kimi-k2.5` | 中文能力强 |
| 快速响应任务 | `xingjiabiapi/gemini-2.5-flash` | 超快速 |

**⚠️ 避免使用：**
- `zai/glm-4.7` - 有并发限制，不适合频繁任务
- `github-copilot/*` - 在 isolated session 中可能不可用

### 推送目标

| 目标 | ID | 说明 |
|------|-----|------|
| Daniel 私聊 | `YOUR_TELEGRAM_ID` | ✅ 推荐，最稳定 |
| DailyNews 群 | `YOUR_NEWS_CHAT_ID` | ⚠️ 需确认 bot 在群内 |

---

## 任务模板

### 模板1: 脚本执行任务
```json
{
  "name": "任务名称",
  "agentId": "telegram-agent",
  "enabled": true,
  "schedule": {
    "kind": "cron",
    "expr": "0 9 * * *",
    "tz": "Asia/Shanghai"
  },
  "sessionTarget": "isolated",
  "payload": {
    "kind": "agentTurn",
    "message": "执行任务：\n\n```bash\npython3 ~/clawd/scripts/xxx.py\n```\n\n将结果通过 telegram-push.sh 推送。",
    "model": "xingjiabiapi/gemini-3-flash-preview",
    "timeoutSeconds": 180,
    "deliver": true,
    "channel": "telegram",
    "to": "YOUR_TELEGRAM_ID"
  }
}
```

### 模板2: 数据监控任务
```json
{
  "name": "XXX监控",
  "agentId": "telegram-agent",
  "enabled": true,
  "schedule": {
    "kind": "cron",
    "expr": "30 9,14 * * 1-5",
    "tz": "Asia/Shanghai"
  },
  "sessionTarget": "isolated",
  "payload": {
    "kind": "agentTurn",
    "message": "执行监控任务：\n\n1. 获取数据\n2. 分析变化\n3. 如有异常立即告警\n4. 推送报告到 Telegram",
    "model": "xingjiabiapi/gemini-3-flash-preview",
    "timeoutSeconds": 180,
    "deliver": true,
    "channel": "telegram",
    "to": "YOUR_TELEGRAM_ID"
  }
}
```

### 模板3: AI学习/研究任务
```json
{
  "name": "自我学习",
  "agentId": "telegram-agent",
  "enabled": true,
  "schedule": {
    "kind": "every",
    "everyMs": 10800000
  },
  "sessionTarget": "isolated",
  "payload": {
    "kind": "agentTurn",
    "message": "【学习任务】\n\n请执行以下学习步骤：\n1. 选择学习主题\n2. 深度研究\n3. 记录笔记\n4. 推送学习报告",
    "model": "anapi/claude-opus-4-5-20250514",
    "timeoutSeconds": 600,
    "deliver": true,
    "channel": "telegram",
    "to": "YOUR_TELEGRAM_ID",
    "bestEffortDeliver": true
  }
}
```

### 模板4: 一次性提醒
```json
{
  "name": "提醒: XXX",
  "agentId": "telegram-agent",
  "enabled": true,
  "schedule": {
    "kind": "at",
    "atMs": 1770270000000
  },
  "sessionTarget": "isolated",
  "payload": {
    "kind": "agentTurn",
    "message": "⏰ 提醒：XXX",
    "model": "xingjiabiapi/gemini-3-flash-preview",
    "timeoutSeconds": 60,
    "deliver": true,
    "channel": "telegram",
    "to": "YOUR_TELEGRAM_ID"
  }
}
```

### 模板5: 每日报告任务
```json
{
  "name": "每日XXX报告",
  "agentId": "telegram-agent",
  "enabled": true,
  "schedule": {
    "kind": "cron",
    "expr": "0 9 * * *",
    "tz": "Asia/Shanghai"
  },
  "sessionTarget": "isolated",
  "payload": {
    "kind": "agentTurn",
    "message": "生成每日报告：\n\n1. 收集数据\n2. 分析趋势\n3. 生成报告\n4. 使用 telegram-push.sh 推送",
    "model": "xingjiabiapi/gemini-3-flash-preview",
    "timeoutSeconds": 300,
    "deliver": true,
    "channel": "telegram",
    "to": "YOUR_TELEGRAM_ID"
  }
}
```

---

## 创建任务流程

### 步骤1: 解析用户需求
从用户描述中提取：
- **任务名称**: 简洁描述任务目的
- **执行时间**: 转换为 cron 表达式或间隔
- **任务内容**: 具体要执行的操作
- **推送需求**: 是否需要推送结果

### 步骤2: 选择模板
根据任务类型选择合适的模板

### 步骤3: 填充配置
- 设置正确的 schedule
- 选择合适的 model
- 配置 timeoutSeconds（根据任务复杂度）
- 设置推送目标

### 步骤4: 创建任务
使用 cron tool 的 add action 创建任务

### 步骤5: 验证
- 检查任务是否创建成功
- 确认 nextRunAtMs 是否正确
- 可选：手动触发测试

---

## 常见问题诊断

### 错误1: "chat not found"
**原因**: Bot 未加入群组或群组 ID 错误
**修复**: 改用私聊 ID `YOUR_TELEGRAM_ID`

### 错误2: "model not allowed"
**原因**: Agent 不允许使用该模型
**修复**: 改用 `xingjiabiapi/gemini-3-flash-preview`

### 错误3: 任务从未执行
**原因**: `enabled` 未设置或 schedule 配置错误
**修复**: 
1. 确保 `enabled: true`
2. 检查 cron 表达式是否正确
3. 确认时区设置

### 错误4: 超时
**原因**: 任务执行时间超过 timeoutSeconds
**修复**: 增加 timeoutSeconds 或优化任务

---

## 快速命令

### 列出所有任务
```
cron list --includeDisabled
```

### 创建任务
```
cron add --job <JSON>
```

### 更新任务
```
cron update --jobId <ID> --patch <JSON>
```

### 手动触发
```
cron run --jobId <ID>
```

### 删除任务
```
cron remove --jobId <ID>
```

---

## 相关文件

- 诊断脚本: `~/clawd/skills/cron-manager/cron_doctor.py`
- 任务模板: `~/clawd/skills/cron-manager/templates/`
- Telegram 推送: `~/clawd/skills/telegram-push/telegram-push.sh`
