# Session 数据格式

Session 数据存储在 `code/data/sessions/{session_id}.json`，包含完整的项目会话信息。

## 根级字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `session_id` | string | 会话唯一 ID |
| `idea` | string | 用户原始创意/故事想法 |
| `style` | string | 视觉风格，如 `realistic`、`anime` |
| `video_ratio` | string | 视频比例，如 `16:9`、`9:16` |
| `expand_idea` | bool | 是否扩展创意 |
| `llm_model` | string | LLM 模型名称 |
| `vlm_model` | string | VLM 模型名称 |
| `image_t2i_model` | string | 文生图模型 |
| `image_it2i_model` | string | 图生图模型 |
| `video_model` | string | 视频生成模型 |
| `enable_concurrency` | string/bool | 是否启用并发 |
| `web_search` | bool | 是否启用网络搜索 |
| `created_at` | float | 创建时间戳 |
| `updated_at` | float | 更新时间戳 |
| `current_stage` | string | 当前阶段 |
| `status` | string | 会话状态 |
| `stages_completed` | string[] | 已完成的阶段列表 |
| `error` | null / string | 错误信息 |
| `artifacts` | object | 各阶段产物（见下文） |

## Status 状态值

| 状态 | 说明 |
|------|------|
| `idle` | 初始状态 |
| `running` | 运行中 |
| `waiting` | 等待用户确认 |
| `stage_completed` | 阶段完成 |
| `session_completed` | 会话完成 |

## Stages Completed 阶段列表

按顺序完成的所有阶段：
```
script_generation → character_design → storyboard → reference_generation → video_generation → post_production
```

---

## Artifacts 各阶段产物

### 1. script_generation

```json
{
  "session_id": "...",
  "title": "守",
  "logline": "一句话概括故事",
  "genre": ["奇幻", "温情"],
  "target_duration": 180,
  "synopsis": "详细故事梗概",
  "characters": [
    {
      "name": "角色名",
      "character_id": "char_xxx",
      "description": "角色描述",
      "personality": ["特质1", "特质2"],
      "motivation": "角色动机",
      "arc_description": "角色弧线描述",
      "role": "主角/配角/反派",
      "age": "年龄",
      "species": "物种（人类/狗等）"
    }
  ],
  "settings": [
    {
      "name": "场景名",
      "setting_id": "set_xxx",
      "description": "场景描述"
    }
  ],
  "scenes": [
    {
      "scene_number": 1,
      "location": "场景位置",
      "characters": ["角色名"],
      "plot": "场景剧情描述"
    }
  ],
  "overall_style": "realistic",
  "mood": "整体情绪基调",
  "project_id": "proj_xxx",
  "version": 1,
  "metadata": {
    "generation_model": "模型名",
    "generation_prompt": "原始生成提示词",
    "mode": "movie/micro"
  },
  "logline_data": {
    "logline": "完整logline",
    "who": "主角是谁",
    "goal": "主角目标",
    "conflict": "核心冲突",
    "twist": "反转点",
    "theme": "主题"
  }
}
```

### 2. character_design

```json
{
  "session_id": "...",
  "characters": [
    {
      "id": "char_xxx",
      "name": "角色名",
      "description": "角色外观描述",
      "selected": "选中的角色图路径",
      "versions": ["所有版本路径"]
    }
  ],
  "settings": [
    {
      "id": "set_xxx",
      "name": "场景名",
      "description": "场景描述",
      "selected": "选中的场景图路径",
      "versions": ["所有版本路径"]
    }
  ]
}
```

### 3. storyboard

```json
{
  "session_id": "...",
  "shots": [
    {
      "shot_number": 1,
      "duration": 5,
      "characters": ["角色名"],
      "location": "场景位置",
      "plot": "镜头剧情描述",
      "visual_prompt": "视觉生成提示词",
      "shot_id": "shot_001_01",
      "scene_number": 1,
      "act": 1
    }
  ],
  "user_modified": true,
  "new_shot_ids": []
}
```

> **注意**：storyboard 结构是 `{shots: [...]}`，**没有** `payload` 包装层。

### 4. reference_generation

```json
{
  "session_id": "...",
  "scenes": [
    {
      "id": "shot_001_01",
      "name": "场景1-镜头1",
      "index": 1,
      "description": "视觉生成提示词（由 storyboard.visual_prompt 同步过来）",
      "selected": "用户选中的参考图路径",
      "versions": ["所有版本路径"],
      "status": "done/pending/failed"
    }
  ],
  "shots": [
    {
      "shot_id": "shot_001_01",
      "video_prompt": "视频生成提示词"
    }
  ]
}
```

> **注意**：
> - `scenes[].id` = `storyboard.shots[].shot_id`，用于跨阶段关联
> - `shots[]` 是给视频生成用的提示词，格式为 `{shot_id, video_prompt}`

### 5. video_generation

```json
{
  "session_id": "...",
  "clips": [
    {
      "id": "shot_001_01",
      "name": "场景1-镜头1",
      "index": 1,
      "description": "视频片段描述（由 storyboard.plot 同步）",
      "duration": 5,
      "selected": "用户选中的视频路径",
      "versions": ["所有版本路径"],
      "status": "done/pending/failed"
    }
  ]
}
```

> **注意**：`clips[].id` = `storyboard.shots[].shot_id`

### 6. post_production

```json
{
  "session_id": "...",
  "final_video": "code/result/video/xxx_final.mp4"
}
```

---

## 跨阶段数据同步关系

```
storyboard (修改 plot/visual_prompt/duration)
    ↓
video_generation.clips (description/duration)
    ↑ (修改 description/duration)
    ↑
video_generation (修改 clips.description/clips.duration)
    ↓ (修改后同步回 storyboard)
storyboard (修改后同步回 storyboard.shots.plot)

reference_generation (修改 scenes.description)
    ↓
storyboard.shots.visual_prompt (由 reference_generation 同步)
    ↑ (修改后同步)
    ↑
reference_generation (修改 scenes.description)
```

---

## PATCH /artifact/{stage} 请求格式

### storyboard
```json
{
  "shots": [
    {"shot_id": "shot_001_01", "duration": 5, "plot": "新描述", "visual_prompt": "新提示词"}
  ]
}
```

### reference_generation（修改视觉提示词）
```json
{
  "shots": [
    {"shot_id": "shot_001_01", "visual_prompt": "新提示词"}
  ]
}
```

### reference_generation（选择图片版本）
```json
{
  "shot_001_01": "code/result/image/xxx/shot_001_01_v2.jpg"
}
```

### video_generation（修改片段描述/时长）
```json
{
  "shot_001_01": {"description": "新描述", "duration": 5}
}
```

### video_generation（选择视频版本）
```json
{
  "shot_001_01": "code/result/video/xxx/shot_001_01_v2.mp4"
}
```
