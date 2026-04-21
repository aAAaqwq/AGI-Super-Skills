---
name: tcm-meridian-inference
description: TCM meridian inference engine — health scoring from 6-meridian measurements
---

# TCM Meridian Inference Skill

中医经络推理引擎 — 输入6经络（肝/脾/肾/胃/胆/膀胱）左右测量值，输出：健康评分、经络状态、组合判症、门店讲解文案、调理建议。

## 触发词

经络推理、TCM推理、经络分析、meridian diagnosis、tcm inference

## 功能概述

- **输入**：6条经络的左右温度测量值（足部采集）
- **输出**：
  - `healthScore` — 综合健康评分（0-100）
  - `meridians` — 每条经络的状态（stable / left_low / right_low / cross）、评分、症状标签
  - `combinations` — 跨经络组合判症（如「转氨酶偏高」「颈椎风险提示」）
  - `summary` — 总体概述
  - `storefront` — 门店讲解文案（焦点标题、客户解释、话术引导、复测提示）
  - `advice` — 调理建议列表
  - `riskTags` — 风险标签
- **引擎**：纯规则推理（Python stdlib-only），无需外部依赖
- **经络列表**：liver（肝）、spleen（脾）、kidney（肾）、stomach（胃）、gallbladder（胆）、bladder（膀胱）

## 目录结构

```
tcm-meridian-inference/
├── SKILL.md              # 本文件
├── scripts/
│   ├── infer.py          # 推理引擎核心
│   ├── tcm_api.py        # HTTP API 服务
│   └── start_api.sh      # 一键启动脚本
└── rules/
    ├── thresholds.json       # 温度阈值与评分参数
    ├── meridian_rules.json   # 单经络规则（18条）
    └── combination_rules.json # 组合判症规则（6条）
```

## HTTP API 接口定义

TCM 推理引擎以独立 HTTP 服务运行（默认端口 **18790**），所有功能通过 HTTP 调用。

### 启动服务

```bash
cd ~/clawd/skills/tcm-meridian-inference
bash scripts/start_api.sh          # 默认 18790
bash scripts/start_api.sh 8080     # 指定端口
TCM_API_PORT=9090 bash scripts/start_api.sh  # 环境变量
```

### 接口列表

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/inference/meridian-diagnosis` | 完整推理（评分+状态+组合判症+门店文案+建议） |
| POST | `/test` | 用内置示例数据测试 |
| GET | `/healthz` | 健康检查 |
| GET | `/` | 服务信息 |

### 请求体（POST /api/inference/meridian-diagnosis）

```json
{
  "subject": {"id": "test-001", "name": "测试用户"},
  "measurements": {
    "liver":       {"left": 35.0, "right": 36.1},
    "spleen":      {"left": 35.1, "right": 35.9},
    "kidney":      {"left": 35.0, "right": 35.8},
    "stomach":     {"left": 35.1, "right": 36.0},
    "gallbladder": {"left": 35.0, "right": 35.9},
    "bladder":     {"left": 35.2, "right": 35.9}
  }
}
```

字段说明：
- `subject`：可选，被测者标识
- `measurements`：必填，6条经络的左右值
  - 每条经络需包含 `left` 和 `right`（浮点数，单位：°C）
  - 可选 `trendDelta` 字段（默认 = right - left）

### 响应体

```json
{
  "engine": {"mode": "rule-based-mvp", "version": "0.2.0"},
  "subject": {"id": "test-001", "name": "测试用户"},
  "healthScore": 84.0,
  "scores": {"liver": 84.0, "spleen": 100.0, "kidney": 100.0, "stomach": 100.0, "gallbladder": 100.0, "bladder": 100.0},
  "meridians": {
    "liver": {
      "status": "left_low",
      "score": 84.0,
      "symptoms": ["代谢差", "气虚", ...],
      "tags": ["left_low"]
    },
    ...
  },
  "sixDimensionScores": [...],
  "riskTags": ["left_low"],
  "combinations": [],
  "summary": "肝左低：代谢侧偏弱",
  "reportSummary": "...",
  "advice": ["关注代谢与睡眠节律", ...],
  "storefront": {
    "focusHeadline": "左侧偏低",
    "clientExplanation": "...",
    "talkTrack": ["...", "...", "..."],
    "retestPrompt": "建议间隔 20-30 分钟复测一次，连续 2-3 次趋势更可靠。"
  },
  "trace": {...}
}
```

### 响应字段说明

| 字段 | 类型 | 说明 |
|------|------|------|
| `healthScore` | float | 综合评分（0-100），6经络均值 |
| `scores` | object | 各经络评分 |
| `meridians` | object | 各经络状态详情（status / score / symptoms / tags） |
| `combinations` | array | 命中的组合判症规则 |
| `summary` | string | 机器可读的简短摘要 |
| `storefront` | object | 门店讲解用文案 |
| `advice` | array[string] | 调理建议 |
| `riskTags` | array[string] | 去重后的风险标签 |
| `trace` | object | 完整推理轨迹（调试用） |

### 经络状态枚举

| 状态 | 含义 |
|------|------|
| `stable` | 正常范围 |
| `left_low` | 左侧偏低 |
| `right_low` | 右侧偏低 |
| `cross` | 左右差异明显 |

### 组合判症（combinations）

| 组合名 | 触发条件 | 标签 |
|--------|----------|------|
| 转氨酶偏高 | 肝左低 + 胆左低 | transaminase, liver_combo |
| 颈椎风险提示 | 肾与膀胱相反侧低 | cervical |
| 腰椎风险提示 | 肾与膀胱同侧低 | lumbar |
| 心脏供血注意 | ≥4条经络右低 | heart_supply |
| 头部供血注意 | ≥4条经络左低 | head_supply |
| 颈椎加重提示 | 肾+膀胱相反低且脾左低 | cervical_plus |

## CLI 单次推理

无需启动 HTTP 服务，直接用推理引擎：

```bash
cd ~/clawd/skills/tcm-meridian-inference
python3 scripts/infer.py path/to/case.json --pretty
python3 scripts/infer.py path/to/case.json --out result.json
```

## OpenClaw 调用方式

### 方式A：Agent 通过 exec tool 调用 TCM API

OpenClaw agent 可以直接通过 exec 执行 curl 调用 TCM API：

```bash
# 确保 API 正在运行
curl -s http://localhost:18790/healthz

# 完整推理
curl -s -X POST http://localhost:18790/api/inference/meridian-diagnosis \
  -H "Content-Type: application/json" \
  -d '{
    "subject": {"id": "user-001", "name": "张三"},
    "measurements": {
      "liver": {"left": 34.5, "right": 34.3},
      "spleen": {"left": 34.8, "right": 34.6},
      "kidney": {"left": 33.5, "right": 34.2},
      "stomach": {"left": 34.0, "right": 34.5},
      "gallbladder": {"left": 34.2, "right": 34.0},
      "bladder": {"left": 33.8, "right": 34.8}
    }
  }'
```

### 方式B：CLI 命令行触发

从任何脚本中向 OpenClaw agent 发送消息请求推理：

```bash
openclaw agent --agent main --deliver --message "请帮我推理经络数据: liver左35右36, spleen左35.1右35.9, kidney左35右35.8, stomach左35.1右36, gallbladder左35右35.9, bladder左35.2右35.9"
```

### 方式C：Cron 定时推理 + 结果推送

通过 OpenClaw cron 配置定时推理任务，将结果推送到外部 webhook：

```json
{
  "schedule": "0 9 * * *",
  "task": "调用 TCM API 推理经络数据并将结果 POST 到外部 URL",
  "delivery": {
    "mode": "webhook",
    "to": "https://your-app.com/api/tcm-callback"
  }
}
```

### 方式D：反向集成（外部系统调 TCM）

外部系统直接调用 TCM API：

```bash
curl -X POST http://<HOST_IP>:18790/api/inference/meridian-diagnosis \
  -H "Content-Type: application/json" \
  -d @request.json
```

适用于：门店系统、小程序后端、IoT 设备网关等。

## 使用示例

```bash
# 1. 启动 API
cd ~/clawd/skills/tcm-meridian-inference
bash scripts/start_api.sh

# 2. 健康检查
curl http://localhost:18790/healthz

# 3. 用示例数据测试
curl -X POST http://localhost:18790/test

# 4. 完整推理
curl -s -X POST http://localhost:18790/api/inference/meridian-diagnosis \
  -H "Content-Type: application/json" \
  -d '{"measurements":{"liver":{"left":34.5,"right":34.3},"spleen":{"left":34.8,"right":34.6},"kidney":{"left":33.5,"right":34.2},"stomach":{"left":34.0,"right":34.5},"gallbladder":{"left":34.2,"right":34.0},"bladder":{"left":33.8,"right":34.8}}}' | python3 -m json.tool

# 5. CLI 单次推理（无需 API）
python3 scripts/infer.py /path/to/case.json --pretty
```

## 与 AI 推理集成

当需要把 TCM 规则推理结果交给 AI 做进一步分析时：

1. **先调 TCM API** 获取结构化推理结果（healthScore、经络状态、组合判症等）
2. **把结果作为 prompt 的一部分**发给 OpenClaw agent
3. **Agent 用 AI 能力**做自然语言解读、个性化建议、用户友好的报告生成

示例流程：
```
用户提交经络数据 → TCM API 规则推理 → 结构化 JSON → Agent AI 解读 → 用户友好报告
```

规则引擎擅长精确的阈值判断和组合逻辑；AI 擅长自然语言理解和个性化表达。两者结合效果最佳。

## 技术说明

- **Python stdlib-only**：零外部依赖，Python 3.6+ 即可运行
- **规则库热加载**：修改 `rules/` 下的 JSON 文件后重启 API 即生效
- **默认端口**：18790（可通过环境变量 `TCM_API_PORT` 或启动参数修改）
- **原项目路径**：`~/clawd/projects/tcm-meridian-inference-mvp/`（勿直接修改）

## 规则调优

规则文件位于 `rules/` 目录：

- `thresholds.json` — 温度阈值（lowMin=35.3, normalMin=35.6 等）和评分参数（每项扣分分值）
- `meridian_rules.json` — 单经络规则（每条经络 3 个状态 × 6 条经络 = 18 条规则）
- `combination_rules.json` — 跨经络组合判症规则（6 条）

修改规则后重启 API 即可生效，无需修改代码。
