# 生成剧本

执行第一阶段：剧本生成。

---

## 请求

```bash
curl -X POST "http://localhost:8000/api/project/{session_id}/execute/script_generation" \
  -H "Content-Type: application/json" \
  -d '{"session_id": "xxx", "style": "anime"}'
```

---

## 停点流程

剧本生成阶段有 4 个停点：

| 停点 | phase 值 | 操作 |
|------|----------|------|
| 1 | suggest_expand | 询问用户是否需要对情节进行扩写 |
| 2 | logline_selection | 让用户从 3 个情节候选中选择 |
| 3 | mode_selection | 让用户选择电影(4幕)或微电影(1幕) |
| 4 | script_generation | 等待剧本生成完成 |

> **注意**：如果用户输入足够清晰完整丰富，`suggest_expand` 和 `logline_selection` 可能会直接跳过，直接进入 `mode_selection`。

## 处理各停点

### 停点2：建议扩写（suggest_expand）

此停点表示当前输入的情节过于简短，难以生成高质量剧情，系统建议进行创意扩写。

```bash
# 获取 artifact 查看扩写建议
curl "http://localhost:8000/api/project/{session_id}/artifact/script_generation"
```

从 `artifact.expand_suggestion` 或 `artifact.suggestion` 获取扩写建议，询问用户选择：

- **选择扩写**：调用 intervene，让系统进行创意扩写
- **跳过扩写**：直接进入下一停点（logline_selection 或 mode_selection）

```bash
# 选择扩写
curl -X POST "http://localhost:8000/api/project/{session_id}/intervene" \
  -H "Content-Type: application/json" \
  -d '{"stage": "script_generation", "modifications": {"expand_idea": true}}'

# 跳过扩写
curl -X POST "http://localhost:8000/api/project/{session_id}/intervene" \
  -H "Content-Type: application/json" \
  -d '{"stage": "script_generation", "modifications": {"expand_idea": false}}'
```

### 停点3：选择情节

```bash
# 获取 artifact 查看候选
curl "http://localhost:8000/api/project/{session_id}/artifact/script_generation"
```

从 `artifact.logline_options` 获取候选列表，询问用户选择，然后调用 intervene：

```bash
curl -X POST "http://localhost:8000/api/project/{session_id}/intervene" \
  -H "Content-Type: application/json" \
  -d '{"stage": "script_generation", "modifications": {"selected_logline": 0}}'
```

> **注意**：参数名是 `selected_logline`，不是 `selected_logline_index`！

### 停点4：选择模式

```bash
curl -X POST "http://localhost:8000/api/project/{session_id}/intervene" \
  -H "Content-Type: application/json" \
  -d '{"stage": "script_generation", "modifications": {"selected_mode": "expand"}}'
```

- `expand`: 电影模式（4幕，15-20分钟）
- `micro`: 微电影模式（1幕，3-5分钟）

### 停点5：剧本生成完成，等待用户确认后继续下一阶段

**必须向用户发送消息**，展示完整的剧本内容：

- **标题**：`artifact.title`
- **故事线**：`artifact.logline`
- **人物列表**：`artifact.characters`（包含人物名称、描述、性格特点）
- **背景列表**：`artifact.settings`（包含背景名称、描述、氛围）
- **场景列表**：`artifact.scenes`（包含场景编号、类型、描述、人物、地点）

- **发送前端 URL**（获取本地 IPv4 地址，构造 `http://{local_ip}:3000/?session={session_id}&stage=script_generation`）

询问用户确认后调用：

```bash
# 确认剧本，继续下一阶段
curl -X POST "http://localhost:8000/api/project/{session_id}/continue"
```

---

## SSE 事件监听

- `progress`: 实时进度，可能包含 `asset_complete`
- `stage_complete`: 阶段完成，检查 `data.phase` 确认是否还有下一阶段
- `error`: 执行出错

---

## 响应示例

```json
{
  "title": "标题",
  "logline": "核心故事线",
  "characters": [...],
  "settings": [...],
  "scenes": [...],
  "phase": "script_generation"
}
```

---

## 常见问题

| 错误 | 原因 | 解决方法 |
|------|------|----------|
| `curl: (7) Failed to connect` | 后端未运行 | 启动后端服务 |
| `404 Not Found` | session_id 错误或 API 路径错误 | 确认 session_id 正确 |
| SSE 无响应 | 后端任务卡住 | 检查日志 `/tmp/movie-backend.log` |
| 用户不选择 | 用户在停点未回复 | 等待用户选择，不要自行决定 |
| `"phase": "suggest_expand"` | 系统建议启用创意扩写 | 可自动调用 intervene 启用 |
