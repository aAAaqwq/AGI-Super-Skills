# MovieAssistant API 文档

## 概述

MovieAssistant 是一个 AI 视频生成系统，提供 REST API 供外部调用。API 与前端共享同一个历史数据库，支持在 API 和前端之间无缝切换。

**基础 URL**: `http://localhost:8000`

---

## 认证

当前版本无需认证，所有接口均可公开访问。

---

## 可用阶段

| 阶段 ID | 名称 | 说明 |
|---------|------|------|
| `script_generation` | 剧本生成 | 将灵感转化为结构化剧本 |
| `character_design` | 角色/场景设计 | 生成角色设计图和场景背景 |
| `storyboard` | 分镜设计 | 设计镜头语言和分镜脚本 |
| `reference_generation` | 参考图生成 | 生成高精度参考图 |
| `video_generation` | 视频生成 | 将参考图/分镜图生成视频 |
| `post_production` | 后期剪辑 | 拼接视频片段为最终成片 |

---

## API 接口列表

### 1. 创建项目

创建一个新的视频生成项目。

**接口**: `POST /api/project/start`

**请求体**:
```json
{
  "idea": "故事线描述",
  "style": "anime",
  "llm_model": "qwen3.5-plus",
  "vlm_model": "qwen-vl-plus",
  "image_t2i_model": "doubao-seedream-5-0",
  "image_it2i_model": "doubao-seedream-5-0",
  "video_model": "wan2.6-i2v-flash",
  "enable_concurrency": true
}
```

**参数说明**:
| 参数 | 类型 | 必填 | 说明 | 默认值 |
|------|------|------|------|--------|
| idea | string | 是 | 故事线描述 | - |
| style | string | 否 | 视频风格 | anime |
| llm_model | string | 否 | LLM 模型 | qwen3.5-plus |
| vlm_model | string | 否 | VLM 评估模型 | qwen-vl-plus |
| image_t2i_model | string | 否 | 文生图模型 | doubao-seedream-5-0 |
| image_it2i_model | string | 否 | 图生图模型 | doubao-seedream-5-0 |
| video_model | string | 否 | 视频模型 | wan2.6-i2v-flash |
| enable_concurrency | bool | 否 | 开启并发生成（可同时生成多张图片/视频） | true |

**响应示例**:
```json
{
  "session_id": "1773208355389",
  "status": "running",
  "params": {
    "idea": "故事线描述",
    "style": "anime",
    "llm_model": "gemini-3-flash-preview"
  }
}
```

---

### 2. 执行阶段

执行指定的生成阶段。

**接口**: `POST /api/project/{session_id}/execute/{stage}`

**路径参数**:
- `session_id`: 项目会话 ID
- `stage`: 阶段 ID（见上表）

**请求体**:
```json
{
  "style": "anime"
}
```

> 请求体参数与创建项目相同（可选），会覆盖项目中已有的对应参数。

**响应**: SSE 流式返回，包含以下事件类型：
- `progress`: 进度更新
- `stage_complete`: 阶段完成
- `error`: 执行错误

**示例 - 进度事件**:
```json
{
  "type": "progress",
  "message": "剧本生成: 正在生成...",
  "phase": "剧本生成",
  "step_desc": "正在生成...",
  "percent": 50
}
```

**示例 - 阶段完成事件**:
```json
{
  "type": "stage_complete",
  "stage": "script_generation",
  "status": "stage_completed",
  "requires_intervention": false
}
```

---

### 3. 获取项目状态

获取项目的当前状态。

**接口**: `GET /api/project/{session_id}/status`

**响应示例**:
```json
{
  "session_id": "1773208355389",
  "current_stage": "script_generation",
  "status": "running",
  "error": null,
  "stages_completed": [],
  "artifacts": {},
  "meta": {
    "idea": "故事线描述",
    "style": "anime"
  },
  "updated_at": 1773208355389
}
```

---

### 4. 获取阶段产物

获取指定阶段的产物数据。

**接口**: `GET /api/project/{session_id}/artifact/{stage}`

**响应示例** (剧本生成阶段):
```json
{
  "stage": "script_generation",
  "artifact": {
    "title": "影弑",
    "logline": "...",
    "characters": [...],
    "settings": [...],
    "scenes": [...]
  }
}
```

---

### 5. 更新阶段产物

更新指定阶段的产物数据（如用户修改提示词、选择版本）。

**接口**: `PATCH /api/project/{session_id}/artifact/{stage}`

请求体格式**因阶段而异**：

#### storyboard — 修改分镜（时长/剧情/视觉提示词）
```json
{
  "shots": [
    {"shot_id": "shot_001_01", "duration": 5, "plot": "新剧情描述", "visual_prompt": "新视觉提示词"}
  ]
}
```

#### reference_generation — 修改视觉提示词
```json
{
  "shots": [
    {"shot_id": "shot_001_01", "visual_prompt": "新提示词"}
  ]
}
```

#### reference_generation — 选择参考图版本
```json
{
  "shot_001_01": "code/result/image/xxx/shot_001_01_v2.jpg"
}
```

#### video_generation — 修改片段描述/时长
```json
{
  "shot_001_01": {"description": "新描述", "duration": 5}
}
```

#### video_generation — 选择视频版本
```json
{
  "shot_001_01": "code/result/video/xxx/shot_001_01_v2.mp4"
}
```

**响应**: `{"status": "ok"}`

---

### 6. 干预阶段

对已完成的阶段进行修改并重新执行（重新生成部分产物）。

**接口**: `POST /api/project/{session_id}/intervene`

**请求体**:
```json
{
  "stage": "reference_generation",
  "modifications": {
    "regenerate_scenes": ["shot_001_01", "shot_001_02"]
  }
}
```

- `stage`：要干预的阶段
- `modifications`：修改内容，目前支持 `regenerate_scenes`（要重新生成的镜头 ID 列表）

**响应**: SSE 流式返回，包含以下事件类型：
- `progress`: 进度更新
- `stage_complete`: 阶段完成
- `error`: 执行错误

---

### 7. 确认并继续

确认当前阶段的修改，进入下一阶段。

**接口**: `POST /api/project/{session_id}/continue`

**响应示例**:
```json
{
  "status": "ready",
  "next_stage": "character_design"
}
```

---

### 8. 停止执行

停止当前正在执行的阶段。

**接口**: `POST /api/project/{session_id}/stop`

**响应示例**:
```json
{
  "status": "stopped"
}
```

---

### 9. 获取会话列表

获取所有历史项目列表。

**接口**: `GET /api/sessions`

**响应示例**:
```json
{
  "sessions": [
    {
      "id": "1773208355389",
      "idea": "故事线",
      "style": "anime",
      "date": 1773208355389,
      "stages": ["script_generation", "character_design"]
    }
  ]
}
```

---

### 10. 获取阶段列表

获取所有可用阶段列表。

**接口**: `GET /api/stages`

**响应示例**:
```json
{
  "stages": [
    {"id": "script_generation", "name": "剧本生成", "order": 1, "description": "将灵感转化为结构化剧本"},
    {"id": "character_design", "name": "角色/场景设计", "order": 2},
    {"id": "storyboard", "name": "分镜设计", "order": 3},
    {"id": "reference_generation", "name": "参考图生成", "order": 4},
    {"id": "video_generation", "name": "视频生成", "order": 5},
    {"id": "post_production", "name": "后期剪辑", "order": 6}
  ]
}
```

---

## 调用示例

### 完整流程示例

```bash
# 1. 创建项目
SESSION_ID=$(curl -s -X POST http://localhost:8000/api/project/start \
  -H "Content-Type: application/json" \
  -d '{
    "idea": "失忆女刺客刺杀目标时恢复记忆,与爱人联手复仇师兄",
    "style": "anime"
  }' | jq -r '.session_id')

echo "Session ID: $SESSION_ID"

# 2. 执行第一阶段（剧本生成）- 监听 SSE
curl -X POST "http://localhost:8000/api/project/${SESSION_ID}/execute/script_generation" \
  -H "Content-Type: application/json" \
  -d '{"style": "anime"}'

# 3. 获取剧本产物
curl -s "http://localhost:8000/api/project/${SESSION_ID}/artifact/script_generation"

# 4. 确认并继续到下一阶段
curl -s -X POST "http://localhost:8000/api/project/${SESSION_ID}/continue"

# 5. 执行第二阶段（角色设计）
curl -X POST "http://localhost:8000/api/project/${SESSION_ID}/execute/character_design" \
  -H "Content-Type: application/json" \
  -d '{"style": "anime"}'

# 6. 确认并继续
curl -s -X POST "http://localhost:8000/api/project/${SESSION_ID}/continue"

# 7. 执行第三阶段（分镜设计）
curl -X POST "http://localhost:8000/api/project/${SESSION_ID}/execute/storyboard" \
  -H "Content-Type: application/json" \
  -d '{"style": "anime"}'

# 8. 确认并继续
curl -s -X POST "http://localhost:8000/api/project/${SESSION_ID}/continue"

# 9. 执行第四阶段（参考图生成）
curl -X POST "http://localhost:8000/api/project/${SESSION_ID}/execute/reference_generation" \
  -H "Content-Type: application/json" \
  -d '{"style": "anime"}'

# 10. 确认并继续
curl -s -X POST "http://localhost:8000/api/project/${SESSION_ID}/continue"

# 11. 执行第五阶段（视频生成）
curl -X POST "http://localhost:8000/api/project/${SESSION_ID}/execute/video_generation" \
  -H "Content-Type: application/json" \
  -d '{"style": "anime"}'

# 12. 确认并继续
curl -s -X POST "http://localhost:8000/api/project/${SESSION_ID}/continue"

# 13. 执行第六阶段（后期剪辑）
curl -X POST "http://localhost:8000/api/project/${SESSION_ID}/execute/post_production" \
  -H "Content-Type: application/json" \
  -d '{"style": "anime"}'
```

### 使用 jq 简化

```bash
# 创建项目并提取 session_id
SESSION_ID=$(curl -s -X POST http://localhost:8000/api/project/start \
  -H "Content-Type: application/json" \
  -d '{"idea": "故事线", "style": "anime"}' | python3 -c "import json,sys; print(json.load(sys.stdin)['session_id'])")

# 查看项目状态
curl -s "http://localhost:8000/api/project/${SESSION_ID}/status" | python3 -m json.tool
```

---

## 错误处理

### HTTP 状态码

| 状态码 | 说明 |
|--------|------|
| 200 | 请求成功 |
| 400 | 请求参数错误 |
| 404 | 资源不存在 |
| 500 | 服务器内部错误 |

### 错误响应格式

```json
{
  "detail": "错误描述"
}
```

### 常见错误

| 错误 | 说明 |
|------|------|
| Session not found | 指定的 session_id 不存在 |
| Artifact for stage 'xxx' not found | 指定阶段的产物不存在 |
| 阶段执行失败 | 阶段执行过程中发生错误 |

---

## 前端与 API 共享

API 和前端共享同一个 session 存储：
- Session 文件位置: `backend/code/data/sessions/{session_id}.json`
- 产物位置: `backend/code/result/`

这意味着：
1. API 创建的项目可以在前端查看和继续
2. 前端创建的项目可以继续使用 API 操作
3. 两种方式可以随时切换
