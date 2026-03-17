# 模型自动降级 Skill 使用指南

## 📋 概述

这个 skill 提供了完整的模型自动降级和故障切换解决方案，确保在模型请求失败、超时或达到限制时自动切换到备用模型。

## 🚀 快速开始

### 1. 验证安装

检查所有脚本是否已正确安装：

```bash
ls -l ~/.openclaw/scripts/model-fallback.sh
ls -l ~/.openclaw/scripts/monitor-models.sh
ls -l ~/clawd/skills/model-fallback/scripts/auto-switch-handler.sh
```

### 2. 启动监控

```bash
# 启动后台监控
~/.openclaw/scripts/monitor-models.sh start

# 验证监控状态
~/.openclaw/scripts/monitor-models.sh status
```

### 3. 测试切换

```bash
# 运行测试脚本
~/clawd/scripts/test-model-fallback.sh
```

## 🔧 使用方式

### 方式 1: 自动监控（推荐）

启动监控后，系统会自动检测并切换：

```bash
~/.openclaw/scripts/monitor-models.sh start
```

监控会：
- 每 5 分钟检查所有模型健康状态
- 检测到故障时自动切换
- 记录详细日志
- 生成状态报告

### 方式 2: 手动触发

当需要手动检查和切换时：

```bash
~/.openclaw/scripts/model-fallback.sh
```

### 方式 3: 使用错误包装器

在执行重要命令时使用包装器，自动处理错误：

```bash
~/clawd/skills/model-fallback/scripts/model-error-wrapper.sh \
  --command "your-openclaw-command-here" \
  --max-retries 3 \
  --timeout 60
```

## 📊 监控与日志

### 查看实时日志

```bash
# 切换日志
tail -f ~/.openclaw/logs/model-fallback.log

# 监控日志
tail -f ~/.openclaw/logs/model-monitor.log

# 自动切换日志
tail -f ~/.openclaw/logs/auto-switch.log

# 所有日志
tail -f ~/.openclaw/logs/*.log
```

### 查看状态

```bash
# 当前模型状态
~/.openclaw/scripts/monitor-models.sh status

# JSON 格式状态
cat ~/.openclaw/logs/model-status.json | python3 -m json.tool

# OpenClaw 状态
openclaw status
```

### 统计信息

```bash
# 切换次数统计
grep "切换模型" ~/.openclaw/logs/model-fallback.log | wc -l

# 今日切换历史
grep "$(date '+%Y-%m-%d')" ~/.openclaw/logs/model-fallback.log | grep "切换模型"

# 错误类型统计
grep "ERROR" ~/.openclaw/logs/auto-switch.log | \
  awk '{print $NF}' | sort | uniq -c
```

## ⚙️ 配置文件

### 主配置文件

位置：`~/.openclaw/agents/main/agent/agent.json`

```json
{
  "model": "anapi/opus-4.5",
  "modelFallback": [
    "<provider>/glm-4.7",
    "openrouter-vip/gpt-5.2-codex",
    "github-copilot/claude-sonnet-4-5"
  ],
  "retry": {
    "maxAttempts": 3,
    "initialDelayMs": 1000,
    "maxDelayMs": 10000,
    "backoffMultiplier": 2.0
  }
}
```

### 修改配置后

```bash
# 重启 Gateway 使配置生效
openclaw gateway restart

# 验证配置
openclaw status | grep Model
```

## 🎯 模型优先级

当前配置的降级顺序：

1. **anapi/opus-4.5** - 最强能力，最高优先级
2. **<provider>/glm-4.7** - 中文优化，Provider-A高
3. **openrouter-vip/gpt-5.2-codex** - 编码专用
4. **github-copilot/claude-sonnet-4-5** - 免费备用

## 🛠️ 故障排查

### 问题 1: 模型未自动切换

**诊断步骤**：

```bash
# 1. 检查配置
cat ~/.openclaw/agents/main/agent/agent.json | grep -A 5 modelFallback

# 2. 检查日志
tail -50 ~/.openclaw/logs/model-fallback.log

# 3. 手动测试切换
~/.openclaw/scripts/model-fallback.sh
```

**常见原因**：
- 配置文件格式错误
- API 密钥未配置
- 网络问题
- 所有模型都不可用

### 问题 2: 监控未运行

**诊断步骤**：

```bash
# 1. 检查进程
ps aux | grep monitor-models

# 2. 检查 PID 文件
cat ~/.openclaw/logs/model-monitor.pid

# 3. 重启监控
~/.openclaw/scripts/monitor-models.sh restart
```

### 问题 3: 频繁切换

**解决方法**：

1. 增加重试次数和延迟
2. 调整冷却期设置
3. 检查网络稳定性

编辑 `agent.json`：

```json
{
  "retry": {
    "maxAttempts": 5,        // 增加到 5 次
    "initialDelayMs": 2000   // 增加到 2 秒
  },
  "errorHandling": {
    "rateLimit": {
      "cooldownMs": 120000   // 增加冷却期到 2 分钟
    }
  }
}
```

## 📈 性能优化

### 1. 减少切换开销

只在真正需要时切换，而非每次错误都切换：

```json
{
  "retry": {
    "maxAttempts": 5,
    "useFallbackOnFailure": false  // 手动控制切换
  }
}
```

### 2. 优化响应时间

为快速响应任务选择最快的模型：

```json
{
  "routing": {
    "rules": [
      {
        "name": "quick-response",
        "match": {"urgency": "high"},
        "preferModels": ["github-copilot/claude-sonnet-4-5"]
      }
    ]
  }
}
```

### 3. 成本优化

优先使用低成本模型：

```json
{
  "modelFallback": [
    "<provider>/glm-4.7",                    // 中等成本
    "github-copilot/claude-sonnet-4-5", // 免费
    "anapi/opus-4.5"                  // 高成本，必要时使用
  ]
}
```

## 🔔 告警配置

### 发送告警到 Telegram

创建告警脚本：

```bash
#!/bin/bash
# ~/.openclaw/scripts/alert-telegram.sh

MESSAGE="$1"
TOKEN="your-telegram-bot-token"
CHAT_ID="your-chat-id"

curl -s -X POST "https://api.telegram.org/bot$TOKEN/sendMessage" \
  -d chat_id="$CHAT_ID" \
  -d text="🤖 OpenClaw 模型切换通知: $MESSAGE"
```

在 `auto-switch-handler.sh` 中集成：

```bash
# 发送告警
~/.openclaw/scripts/alert-telegram.sh "已从 $CURRENT_MODEL 切换到 $NEW_MODEL"
```

## 📝 维护建议

### 每日

- 查看切换日志
- 检查模型健康状态

```bash
grep "切换模型" ~/.openclaw/logs/model-fallback.log | tail -5
~/.openclaw/scripts/monitor-models.sh status
```

### 每周

- 运行完整测试
- 检查配额使用情况
- 备份配置文件

```bash
~/clawd/scripts/test-model-fallback.sh
cp ~/.openclaw/agents/main/agent/agent.json \
   ~/.openclaw/agents/main/agent/agent.json.backup.$(date +%Y%m%d)
```

### 每月

- 评估各模型性能
- 更新模型优先级
- 清理旧日志

```bash
# 清理 30 天前的日志
find ~/.openclaw/logs -name "*.log" -mtime +30 -delete
```

## 🔗 相关资源

- [OpenClaw 文档](https://docs.openclaw.ai)
- [技术文档](~/clawd/docs/model-fallback-strategy.md)
- [配置示例](~/.openclaw/agents/main/agent/agent.json)

## 💡 提示

1. **测试配置**: 在生产环境使用前，先测试切换逻辑
2. **监控日志**: 定期查看日志，了解切换模式
3. **优化配置**: 根据实际使用情况调整参数
4. **备份配置**: 保留配置备份，方便恢复
5. **文档更新**: 记录配置变更和使用经验

## 🆘 获取帮助

如果遇到问题：

1. 查看日志文件
2. 运行诊断脚本
3. 查阅技术文档
4. 提交 Issue

---

祝使用愉快！🎉
