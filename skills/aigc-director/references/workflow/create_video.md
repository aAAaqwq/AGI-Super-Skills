# 生成视频片段

执行第五阶段：视频生成。

## 请求

```bash
curl -X POST "http://localhost:8000/api/project/{session_id}/execute/video_generation" \
  -H "Content-Type: application/json" \
  -d '{"session_id": "xxx"}'
```

## 停点说明

此阶段有 1 个停点：视频生成完成后需要用户确认。

## 产物结构

```json
{
  "clips": [
    {
      "scene_id": "1",
      "shot_id": "1",
      "description": "视频描述",
      "selected": "code/result/video/xxx/clip_001.mp4",
      "versions": [...],
      "status": "done|failed"
    }
  ]
}
```

## 实时反馈

在生成过程中，SSE 会发送 `asset_complete` 事件：

```json
{
  "type": "progress",
  "data": {
    "asset_complete": {
      "type": "clips",
      "id": "1-1",
      "status": "done",
      "selected": "code/result/video/xxx.mp4",
      "versions": [...]
    }
  }
}
```

收到此事件后，必须立即下载视频并发送给用户。

## 停点9：视频片段生成完成，等待用户确认后继续下一阶段

**必须向用户发送消息**，展示每个视频片段：

从 `artifact.clips[].selected` 获取每个视频片段的路径。

**发送消息时必须**：
- 参考 [send_message/feishu.md](../send_message/feishu.md) 发送视频给用户
- 每个视频片段需附带分镜编号和描述（如"场景1-分镜1：角色A走进咖啡馆"）
- 标注视频时长和状态（done/failed）
- 按场景顺序依次发送
- **发送前端 URL**（获取本地 IPv4 地址，构造 `http://{local_ip}:3000/?session={session_id}&stage=video_generation`）
- 发送完整列表后，询问用户确认

询问内容示例：
> "视频片段生成完成，共 X 个片段，Y 个成功。请确认是否继续进行后期剪辑？"

## 继续下一阶段

用户确认后调用：

```bash
curl -X POST "http://localhost:8000/api/project/{session_id}/continue"
```

## 常见问题

| 错误 | 原因 | 解决方法 |
|------|------|----------|
| `curl: (7) Failed to connect` | 后端未运行 | 启动后端服务 |
| `asset_complete` 状态为 failed | 视频生成失败（超时/限流/不支持的内容） | 可降低并发数重试，或检查视频模型是否支持该内容 |
| 视频下载失败 | URL 路径错误 | 确认 path 格式为 `code/result/...` |
| 视频文件太小 | 生成可能失败 | 检查文件大小 > 1KB |
| SSE 连接断开 | 视频生成时间长 | 使用轮询 `/api/project/{session_id}/status` 继续 |
| 用户不确认 | 用户想修改视频 | 调用 modify_video 重新生成 |
