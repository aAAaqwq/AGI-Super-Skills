---
name: token-reporter
description: 每日自动统计 OpenClaw 实例 Token 消耗和工作产出，上报到飞书多维表格。扫描 JSONL 日志按模型聚合 token，收集各
  agent 当日工作摘要，写入飞书 Bitable。触发：'token报告'、'token report'、'日报'、'每日汇报'、'飞书上报'。
author: Daniel Li
---
# Token Reporter — 每日 Token 消耗 + 产出上报

- Author: Daniel Li
- Copyright © Daniel Li. All rights reserved.

## 功能概述

每天自动统计本机 OpenClaw 实例的 Token 消耗和 Agent 工作产出，格式化后写入飞书多维表格。

## 实例对应关系

| 实例 | CEO Agent | 上报人 |
|------|-----------|--------|
| aa (本机) | 小a (main) | Daniel |
| Peter Mini | 小兔 (xiaotu) | Peter |
| 小m | 小m bot | 小m |

## 执行流程

### Step 1: 扫描 JSONL 日志

扫描 `~/.openclaw/agents/*/sessions/*.jsonl` 中当日增量数据。

每条 assistant 消息携带 `usage` 对象：
```json
{
  "usage": {
    "input": 27813,
    "output": 246,
    "cacheRead": 6720,
    "cacheWrite": 0,
    "totalTokens": 34779,
    "cost": {
      "input": 0, "output": 0,
      "cacheRead": 0, "cacheWrite": 0,
      "total": 0
    }
  }
}
```

### Step 2: 按 Agent + Model 聚合

重点追踪 4 个模型（其他模型归入"其他"）：

| 模型 | 匹配规则 |
|------|---------|
| opus4.6 | `claude-opus-4-6` (xingsuancode, xingjiabiapi) |
| glm-5 | `zai/glm-5` |
| minimax-M2.5 | `minimax/MiniMax-M2.5` |
| gemini-3-pro | `gemini-3-pro` (xingjiabiapi) |

### Step 3: 格式化 Token 明细

```
opus4.6: input 320K / output 18K / cache 82% / $4.2
glm-5: input 1.2M / output 85K / cache 78% / $0.3
minimax-M2.5: input 200K / output 12K / cache 0% / $0.1
gemini: — (当日未使用)
```

cache% = cacheRead / (input + cacheRead + cacheWrite) × 100

### Step 4: 收集产出

汇总各 agent 当日工作摘要，格式：
```
code: KGKB工厂30/30完成, 5平台发布脚本 | content: 小红书×2, 选题推荐 | ops: cron改造, 服务器巡检
```

产出收集方式：
1. 读取当日 memory 文件 `~/clawd/memory/$(date +%Y-%m-%d).md`
2. 解析 `## Agent名` 段落或关键词匹配
3. 如无 memory 文件，从 JSONL 最后一条 user/assistant 消息摘要推断

### Step 5: 写入飞书多维表格

使用 `lark-mcp` 工具写入 Bitable：

| 字段 | 类型 | 填写者 | 说明 |
|------|------|--------|------|
| 员工名称 | 文本 | config | config.json 写死 `person` |
| Token明细 | 文本 | 脚本统计 | 4模型格式化文本 |
| 产出 | 文本 | 脚本统计 | 各agent当日工作摘要 |
| 个人总结 | 文本 | 人填 | 员工手动填写（留空） |
| 评分 | 单选 | 高层选 | 优秀/良好/不及格（留空） |
| 时间 | 日期 | 脚本自动 | 当天日期 |

### 飞书 API

- 参考 skill: `~/clawd/skills/feishu-automation/SKILL.md`
- 工具前缀: `mcp__lark-mcp_*`
- 新增记录: `mcp__lark-mcp_createRecord`
- 查询记录: `mcp__lark-mcp_listRecords`

## 脚本用法

```bash
# 统计当日 Token（只看数据，不上报）
python scripts/report.py --scan-only

# 统计 + 上报飞书
python scripts/report.py --report

# 指定日期
python scripts/report.py --date 2026-03-17 --scan-only

# 使用指定配置
python scripts/report.py --config /path/to/config.json --report
```

## Cron 配置建议

```json
{
  "name": "📊 每日 Token 报告 + 飞书上报",
  "schedule": { "kind": "cron", "expr": "0 23 * * *", "tz": "Asia/Shanghai" },
  "payload": {
    "kind": "agentTurn",
    "message": "执行每日 Token 报告任务：\n1. 运行 python3 ~/clawd/skills/token-reporter/scripts/report.py --scan-only\n2. 查看输出，确认数据合理\n3. 运行 python3 ~/clawd/skills/token-reporter/scripts/report.py --report\n4. 确认飞书写入成功后，用 message(action=send, channel=telegram, target=-1003890797239) 简要汇报\n5. 如果失败，报告错误原因"
  }
}
```

## 配置

安装时复制 `config.example.json` → `config.json` 并填写：

```json
{
  "person": "Daniel",
  "instance": "aa",
  "lark_app_id": "cli_a83467f9ecba5013",
  "bitable_app_token": "your_bitable_token",
  "bitable_table_id": "your_table_id"
}
```

## 文件结构

```
token-reporter/
├── SKILL.md
├── config.example.json    # 配置模板（安装时复制为 config.json）
├── scripts/
│   └── report.py          # 核心统计脚本
└── references/
    └── jsonl-structure.md # JSONL 数据结构参考
```

## 错误处理

| 错误 | 处理 |
|------|------|
| JSONL 文件损坏 | 跳过该行，记录警告 |
| 无当日数据 | 报告"当日无数据" |
| 飞书 API 失败 | 重试3次，失败后本地缓存结果 |
| config.json 不存在 | 提示复制 config.example.json |
| Memory 文件不存在 | 产出标记为"无记录" |
