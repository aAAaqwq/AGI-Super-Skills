# JSONL 数据结构参考

## 文件位置
```
~/.openclaw/agents/<agent_name>/sessions/<session_uuid>.jsonl
```

## 行类型

### session (第一行)
```json
{"type":"session","version":3,"id":"<uuid>","timestamp":"...","cwd":"/home/aa/clawd"}
```

### model_change (模型切换)
```json
{"type":"model_change","id":"...","parentId":"...","timestamp":"...","provider":"zai","modelId":"glm-5-turbo"}
```

### message (用户/AI消息)
```json
{
  "type": "message",
  "id": "...",
  "parentId": "...",
  "timestamp": "2026-03-18T03:18:02.948Z",
  "message": {
    "role": "assistant",
    "content": [...],
    "usage": {
      "input": 27813,
      "output": 246,
      "cacheRead": 6720,
      "cacheWrite": 0,
      "totalTokens": 34779,
      "cost": {
        "input": 0,
        "output": 0.0117,
        "cacheRead": 0,
        "cacheWrite": 0,
        "total": 0.0117
      }
    }
  }
}
```

## Agent 列表
main, code, content, data, finance, law, market, ops, pm, product, quant, research, sales, batch

## 模型映射
| 显示名 | 匹配规则 |
|--------|---------|
| opus4.6 | `claude-opus-4-6` |
| glm-5 | `zai/glm-5` (不含 turbo) |
| glm-5-turbo | `zai/glm-5-turbo` |
| minimax-M2.5 | `MiniMax-M2.5` |
| gemini-3-pro | `gemini-3-pro` |
