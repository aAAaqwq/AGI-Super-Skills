# 路由逻辑与定价分析

## 核心决策：按提示词长度 + 复杂度路由

VectorNode 提供两个同源模型：
- `gpt-image-2`：**按 Token 计费**（prompt+output token）
- `gpt-image-2-all`：**按次计费**（无论 prompt 多长，一个固定价）

## 决策树

```
用户发起 generate/edit 请求
  │
  ├─ 指定了 model？──→ 用指定的
  │
  ├─ prompt > 200 字符 ──→ gpt-image-2-all
  │   (理由：长 prompt 走 Token 计费会很贵)
  │
  ├─ n > 1 ──→ gpt-image-2-all
  │   (理由：批量生成，按次更可预期)
  │
  ├─ size ∈ 2K/4K ──→ gpt-image-2-all
  │   (理由：高分辨率输出，单次按次更划算)
  │
  ├─ quality == "high" ──→ gpt-image-2-all
  │   (理由：high quality 资源消耗大，按次更稳)
  │
  └─ 默认 ──→ gpt-image-2
      (理由：短 prompt + 简单参数，Token 计费最便宜)
```

## 阈值依据

| 信号 | 阈值 | 路由 |
|------|------|------|
| prompt 字符数 | > 200 | → all |
| 批量张数 n | > 1 | → all |
| 尺寸 | 2K / 4K | → all |
| 质量 | high | → all |

阈值 **200 字符** 来自经验值：
- 短 prompt（≤200 字符）通常包含 1-2 句描述，按 Token 计费单价低
- 长 prompt（>200 字符）通常含多细节/多风格要求，Token 累计高，按次更划算

## 路由示例表

| Prompt | n | size | quality | 路由 | 理由 |
|--------|---|------|---------|------|------|
| "A cute cat" | 1 | 1024x1024 | auto | gpt-image-2 | 短、简单、Token 便宜 |
| "Detailed cyberpunk cat with neon lights, rain, street market..." | 1 | 1024x1024 | auto | gpt-image-2-all | prompt 280 字符 |
| "Logo" | 4 | 1024x1024 | auto | gpt-image-2-all | n=4 批量 |
| "Poster" | 1 | 2048x2048 | auto | gpt-image-2-all | 2K |
| "Hero image" | 1 | 1024x1024 | high | gpt-image-2-all | quality=high |
| "复杂长 prompt..." | 1 | 1024x1024 | auto | gpt-image-2-all | prompt 长 |

## 调用流程图

```
vectronode_image.py generate --prompt "..."
  │
  ├─ 加载 VECTORNODE_API_KEY（env → ~/.openclaw/.env）
  ├─ 校验 prompt ≤ 1000 字符
  ├─ decide_model() ──→ 选择 gpt-image-2 或 gpt-image-2-all
  │
  ├─ dry-run? ─→ 打印决策，退出
  │
  ├─ 构建 payload
  │   generate: JSON
  │   edit: multipart/form-data + 文件
  │
  ├─ POST https://www.vectronode.com/v1/images/generations
  │   Headers: Authorization: Bearer sk-...
  │
  ├─ 重试逻辑: 429 / 5xx → sleep 2s → retry 一次
  │
  └─ 解码 b64_json → 保存到 --output
```

## 凭据加载顺序

1. 环境变量 `VECTORNODE_API_KEY`
2. `~/.openclaw/.env` 中的 `VECTORNODE_API_KEY=...`
3. 报错退出

**不要**写到代码里、git 仓库里。

## 失败处理

| 错误 | 原因 | 解决 |
|------|------|------|
| ❌ `VECTORNODE_API_KEY not found` | env 和 .env 都没设 | 在 `~/.openclaw/.env` 加 `VECTORNODE_API_KEY=sk-...` |
| ❌ `HTTP 401` | API Key 无效 | 检查 key 拼写、是否过期 |
| ❌ `Prompt too long: 1200 chars` | 超过 1000 字符限制 | 精简 prompt |
| ❌ `Image not found` | 输入图路径错 | 检查 `--image` 参数 |
| ⚠️  `HTTP 429` | 触发限流 | 脚本自动 retry，2s 后重试 |
| ⚠️  `HTTP 5xx` | 上游故障 | 脚本自动 retry 一次 |

## 何时手动指定 model

- **不信任自动路由**（罕见） → `--model gpt-image-2-all`
- **调试/对比成本** → 先 `--dry-run` 看决策
- **强制按次**：长任务链，每个调用都按次预知成本
