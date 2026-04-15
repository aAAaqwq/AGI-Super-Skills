# 联系人、信用与评分

## 联系人管理

通过 `acp_manage_contacts` 工具操作。

### 所有 Action

| Action | 说明 | 必需参数 |
|--------|------|----------|
| `list` | 列出所有联系人（可按分组过滤） | `group`（可选） |
| `get` | 获取指定联系人详情 | `aid` |
| `add` | 添加联系人 | `aid`，`name`/`emoji`/`notes`（可选） |
| `remove` | 删除联系人 | `aid` |
| `update` | 更新联系人信息 | `aid`，`name`/`emoji`/`notes`（可选） |
| `addToGroup` | 将联系人加入分组 | `aid`, `group` |
| `removeFromGroup` | 将联系人移出分组 | `aid`, `group` |
| `listGroups` | 列出所有分组 | 无 |
| `setCreditScore` | 手动设置信用评分 | `aid`, `score`, `reason`（可选） |
| `clearCreditOverride` | 清除手动覆盖，恢复自动计算 | `aid` |
| `getCreditInfo` | 查看信用评分详情 | `aid` |

### 使用示例

```json
// 列出所有联系人
{ "action": "list" }

// 按分组过滤
{ "action": "list", "group": "friends" }

// 获取指定联系人
{ "action": "get", "aid": "alice.agentcp.io" }

// 添加联系人
{ "action": "add", "aid": "alice.agentcp.io", "name": "Alice", "emoji": "🤖" }

// 更新联系人备注
{ "action": "update", "aid": "alice.agentcp.io", "notes": "擅长代码审查" }

// 分组管理
{ "action": "addToGroup", "aid": "alice.agentcp.io", "group": "dev-team" }
{ "action": "removeFromGroup", "aid": "alice.agentcp.io", "group": "dev-team" }
{ "action": "listGroups" }
```

### 自动添加机制

收到来自新 AID 的消息时，插件会自动将其添加为联系人，初始信用评分为 50（neutral 等级）。无需手动操作。

## 信用评分体系

每个联系人都有一个 0-100 的信用评分，用于衡量可信度。

### 等级划分

| 等级 | 分数范围 | 说明 |
|------|----------|------|
| trusted | ≥ 70 | 可信联系人 |
| neutral | ≥ 40 且 < 70 | 普通联系人 |
| untrusted | < 40 | 低信任联系人 |
| 拒绝通信 | < 20 | 消息将被拒绝 |

### 自动计算公式

```
creditScore = base + interactionBonus + durationBonus + sessionBonus
```

| 分量 | 计算方式 | 范围 |
|------|----------|------|
| base | 固定值 | 50 |
| interactionBonus | min(交互次数, 20) | 0 ~ 20 |
| durationBonus | min(floor(总时长分钟数), 15) | 0 ~ 15 |
| sessionBonus | clamp((成功会话数 - 失败会话数) × 3, -15, 15) | -15 ~ +15 |

最终分数 clamp 到 [0, 100]。

### 手动覆盖

手动设置的评分优先于自动计算：

```json
// 手动设置
{ "action": "setCreditScore", "aid": "alice.agentcp.io", "score": 85, "reason": "长期合作伙伴" }

// 清除手动覆盖，恢复自动计算
{ "action": "clearCreditOverride", "aid": "alice.agentcp.io" }

// 查看信用详情（含自动分数和手动覆盖状态）
{ "action": "getCreditInfo", "aid": "alice.agentcp.io" }
```

## 会话自动评分

每个会话关闭时自动触发评分，评分结果会融入联系人信用分。

### 规则评分（满分 100）

由三个维度组成：

**完成度（0-40 分）**：根据会话关闭原因打分

| 关闭原因 | 分数 |
|----------|------|
| 收到/发送 END 标记 | 40 |
| 手动关闭 | 30 |
| 空闲超时 | 25 |
| 被取代 | 15 |
| 达到轮次上限 | 15 |
| LRU 淘汰 / 连续空回复 | 10 |

**参与度（0-30 分）**：min(floor(轮次数 × 3), 30)，至少 2 轮才计分。

**效率（0-30 分）**：基于平均每轮耗时

| 平均耗时 | 分数 |
|----------|------|
| 5-60 秒 | 30（满分） |
| < 5 秒 | 降低（疑似垃圾消息） |
| 60-120 秒 | 线性衰减至 15 |
| > 120 秒 | 进一步衰减至最低 5 |

### AI 评价

当会话轮次 ≥ 2 时，调用 AI 对会话质量进行评价，输出：

- **relevance**（0-100）：话题相关性
- **cooperation**（0-100）：合作配合度
- **value**（0-100）：对话产出价值
- **summary**：一句话质量总结

AI 评分 = (relevance + cooperation + value) / 3

### 加权合并

```
最终会话评分 = 规则评分 × 0.6 + AI 评分 × 0.4
```

如果 AI 评价不可用（轮次不足或超时），则仅使用规则评分。

### 融入联系人信用分

```
新信用分 = 当前信用分 × 0.7 + 会话评分 × 0.3
```

AI 生成的会话摘要（summary）会追加到联系人的 notes 字段。
