---
name: provider-key-manager
description: Provider key manager — rotate and sync API keys across multi-agent workspaces
---

# Provider Key Manager

> 一条命令更换供应商 API Key，全员生效，零遗漏。

## 痛点

OpenClaw 多 agent 架构下，每个 agent 都有独立的 `models.json`，更换一个 provider key 需要：
1. 修改 `openclaw.json` 全局配置
2. 修改 13+ 个 agent 的 `models.json`
3. 更新 `pass` 存储
4. 重启 Gateway
5. 逐个验证

**一个 key 要改 15+ 处，漏改一个就报错。**

## 方案：环境变量统一引用

OpenClaw 原生支持 `${ENV_VAR}` 语法引用环境变量：

```json
// openclaw.json
{
  "env": {
    "vars": {
      "ZAI_API_KEY": "actual-key-value-here"
    }
  },
  "models": {
    "providers": {
      "zai": {
        "apiKey": "${ZAI_API_KEY}",  // ← 引用环境变量，不硬编码
        "baseUrl": "https://open.bigmodel.cn/api/coding/paas/v4"
      }
    }
  }
}
```

**核心原则**：
- API Key 只存在 `env.vars` 中（单一真相源）
- 所有 provider 的 `apiKey` 用 `"${ENV_VAR}"` 引用
- 各 agent 的 `models.json` **删除 apiKey 字段**，继承全局 provider
- 换 key = 改一个 env var + 重启，全员自动生效

## 触发词

`换key`, `更换key`, `provider key`, `API key 更换`, `模型key`, `key管理`, `供应商密钥`

## 命令

### 1. 审计当前配置

```bash
python3 ~/clawd/skills/provider-key-manager/scripts/manager.py audit
```

扫描所有 agent 的 models.json，报告：
- ✅ 使用 `${ENV_VAR}` 引用的 provider
- ❌ 硬编码 apiKey 的 provider
- ⚠️ key 值不一致的 agent

### 2. 迁移到环境变量模式

```bash
python3 ~/clawd/skills/provider-key-manager/scripts/manager.py migrate [--provider zai] [--dry-run]
```

自动执行：
1. 将 `openclaw.json` 中的硬编码 key 移入 `env.vars`
2. 替换 provider apiKey 为 `"${ENV_VAR}"`
3. 从各 agent models.json 中**删除** apiKey 字段（继承全局）
4. 更新 `pass` 存储
5. 生成迁移报告

### 3. 更换 API Key

```bash
python3 ~/clawd/skills/provider-key-manager/scripts/manager.py update <provider> <new-key> [--base-url <url>]
```

一条命令完成：
1. 更新 `env.vars` 中的 key
2. 如有 agent 仍硬编码，同步更新
3. 更新 `pass` 存储
4. 测试 key 可用性
5. 输出重启命令

### 4. 测试 Key 可用性

```bash
python3 ~/clawd/skills/provider-key-manager/scripts/manager.py test <provider>
```

对指定 provider 发送最小请求，验证 key 有效。

### 5. 查看 Provider 总览

```bash
python3 ~/clawd/skills/provider-key-manager/scripts/manager.py status
```

显示所有 provider 的 key 来源、baseUrl、模型列表。

## Provider ↔ 环境变量映射

| Provider | 环境变量 | pass 路径 |
|----------|---------|----------|
| zai | `ZAI_API_KEY` | `api/zai` |
| xingjiabiapi | `XINGJIABIAPI_KEY` | `api/xingjiabiapi` |
| xai | `XAI_API_KEY` | `api/xai` |
| xingsuancode | `XINGSUANCODE_KEY` | `api/xingsuancode` |
| moonshot | `MOONSHOT_API_KEY` | `api/kimi` |
| minimax | `MINIMAX_API_KEY` | `api/minimax` |
| xinyuan | `XINYUAN_API_KEY` | `api/xinyuan` |
| boluobao | `BOLUOBAO_API_KEY` | `api/boluobao` |
| google | `GOOGLE_API_KEY` | `api/google-ai-studio` |

## 架构图

```
┌─────────────────────────────────┐
│     openclaw.json               │
│  ┌───────────────────────┐      │
│  │ env.vars              │      │
│  │  ZAI_API_KEY: "xxx"   │ ← 单一真相源 (Single Source of Truth)
│  │  XAI_API_KEY: "yyy"   │      │
│  └───────────┬───────────┘      │
│              │ ${ZAI_API_KEY}   │
│  ┌───────────▼───────────┐      │
│  │ models.providers.zai  │      │
│  │  apiKey: "${ZAI_API_KEY}"    │
│  │  baseUrl: "https://..." │    │
│  └───────────────────────┘      │
└─────────────────────────────────┘
              │ 继承
    ┌─────────┼─────────┐
    ▼         ▼         ▼
 agent/     agent/    agent/
 main/      ops/     code/ ...
 models.json models.json
 (无 apiKey，继承全局)
```

## 注意事项

1. **env.vars 中的 key 是明文** — 但 openclaw.json 已在 .gitignore，不会被 commit
2. **per-agent models.json 仍需保留 provider 结构** — 只是删除 apiKey 字段
3. **迁移后换 key 流程**：`manager.py update zai <new-key>` → Gateway 重启 → 完成
4. **回退方案**：迁移前自动备份所有 models.json 到 `/tmp/provider-key-backup/`
