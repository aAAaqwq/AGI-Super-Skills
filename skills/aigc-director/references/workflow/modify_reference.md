# 修改参考图提示词

在第四阶段完成后，用户可以修改某个分镜的视觉提示词并重新生成参考图。

## 修改分镜提示词

```bash
curl -X PATCH "http://localhost:8000/api/project/{session_id}/artifact/reference_generation" \
  -H "Content-Type: application/json" \
  -d '{
    "shots": [
      {
        "scene_id": "1",
        "shot_id": "1",
        "visual_prompt": "新的视觉提示词"
      }
    ]
  }'
```

## 重新执行参考图生成

```bash
curl -X POST "http://localhost:8000/api/project/{session_id}/execute/reference_generation" \
  -H "Content-Type: application/json" \
  -d '{"session_id": "xxx"}'
```

## 常见问题

| 错误 | 原因 | 解决方法 |
|------|------|----------|
| `curl: (7) Failed to connect` | 后端未运行 | 启动后端服务 |
| PATCH 成功但无变化 | 需要重新执行阶段 | 调用 execute/reference_generation 重新生成 |
| scene_id/shot_id 不存在 | ID 错误 | 从 artifact 中获取正确的 ID |
| 图片生成失败 | 提示词包含不支持的内容 | 修改提示词后重试 |