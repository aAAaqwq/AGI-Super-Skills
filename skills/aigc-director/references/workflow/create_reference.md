# 生成参考图

执行第四阶段：为每个分镜生成参考图。

## 请求

```bash
curl -X POST "http://localhost:8000/api/project/{session_id}/execute/reference_generation" \
  -H "Content-Type: application/json" \
  -d '{"session_id": "xxx"}'
```

## 停点说明

此阶段有 1 个停点：参考图生成完成后需要用户确认。

## 产物结构

```json
{
  "shots": [
    {
      "scene_id": "1",
      "shot_id": "1",
      "selected": "code/result/image/xxx/shot_001.png",
      "versions": [...],
      "visual_prompt": "优化后的视觉提示词"
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
      "type": "images",
      "id": "1-1",
      "status": "done",
      "selected": "code/result/image/xxx.png",
      "versions": [...]
    }
  }
}
```

收到此事件后，必须立即下载图片并发送给用户。

## 停点8：参考图生成完成，等待用户确认后继续下一阶段

**必须向用户发送消息**，展示每个分镜的参考图：

从 `artifact.shots[].selected` 获取每个分镜的参考图路径。

**发送消息时必须**：
- 参考 [send_message/feishu.md](../send_message/feishu.md) 发送图片给用户
- 每张参考图需附带分镜编号和简短描述（如"场景1-分镜1：角色A在咖啡馆"）
- 按场景顺序依次发送
- **发送前端 URL**（获取本地 IPv4 地址，构造 `http://{local_ip}:3000/?session={session_id}&stage=reference_generation`）
- 发送完整列表后，询问用户确认

询问内容示例：
> "参考图生成已完成，共 X 张参考图。请确认是否继续生成视频片段？"

## 继续下一阶段

用户确认后调用：

```bash
curl -X POST "http://localhost:8000/api/project/{session_id}/continue"
```

## 常见问题

| 错误 | 原因 | 解决方法 |
|------|------|----------|
| `curl: (7) Failed to connect` | 后端未运行 | 启动后端服务 |
| `asset_complete` 状态为 failed | 图片生成失败（超时/限流） | 可在请求中设置 `"enable_concurrency": false` 降低并发重试 |
| 图片下载失败 | URL 路径错误 | 确认 path 格式为 `code/result/...` |
| SSE 连接断开 | 网络超时 | 使用轮询 `/api/project/{session_id}/status` 继续 |
| 用户不确认 | 用户想修改参考图 | 调用 modify_reference 重新生成 |
