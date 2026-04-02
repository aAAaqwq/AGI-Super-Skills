# 修改分镜

在第三阶段完成后，用户可以修改或续写分镜。

## 修改分镜

```bash
curl -X PATCH "http://localhost:8000/api/project/{session_id}/artifact/storyboard" \
  -H "Content-Type: application/json" \
  -d '{
    "shots": [
      {
        "scene_id": "1",
        "shot_id": "1",
        "duration": "8",
        "description": "新的分镜描述",
        "visual_prompt": "新的视觉提示词"
      }
    ]
  }'
```

## 智能续写

根据已有剧情自动生成新场景：

```bash
curl -X POST "http://localhost:8000/api/project/{session_id}/intervene" \
  -H "Content-Type: application/json" \
  -d '{"stage": "storyboard", "modifications": {"continue_story": true}}'
```

## 重新执行分镜设计

```bash
curl -X POST "http://localhost:8000/api/project/{session_id}/execute/storyboard" \
  -H "Content-Type: application/json" \
  -d '{"session_id": "xxx"}'
```

## 常见问题

| 错误 | 原因 | 解决方法 |
|------|------|----------|
| `curl: (7) Failed to connect` | 后端未运行 | 启动后端服务 |
| PATCH 成功但无变化 | 需要重新执行阶段 | 调用 execute/storyboard 重新生成 |
| scene_id/shot_id 不存在 | ID 错误 | 从 artifact 中获取正确的 ID |
| 续写失败 | 剧本内容不足 | 检查剧本阶段产物是否完整 |