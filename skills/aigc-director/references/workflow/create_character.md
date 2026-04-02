# 生成角色与场景

执行第二阶段：角色和场景设计。

---

## 请求

```bash
curl -X POST "http://localhost:8000/api/project/{session_id}/execute/character_design" \
  -H "Content-Type: application/json" \
  -d '{"session_id": "xxx"}'
```

---

## 停点说明

此阶段有 1 个停点：角色/场景设计完成后需要用户确认。

## 产物结构

```json
{
  "characters": [
    {
      "id": "char_1",
      "name": "角色名",
      "description": "角色描述",
      "visual_prompt": "视觉提示词",
      "selected": "code/result/image/xxx/character_001.png",
      "versions": ["code/result/xxx.png"]
    }
  ],
  "settings": [
    {
      "id": "set_1",
      "name": "场景名",
      "description": "场景描述",
      "visual_prompt": "视觉提示词",
      "selected": "code/result/image/xxx/setting_001.png",
      "versions": [...]
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
      "type": "characters|settings",
      "id": "char_1",
      "status": "done",
      "selected": "code/result/image/xxx.png",
      "versions": [...]
    }
  }
}
```

收到此事件后，必须立即下载图片并发送给用户。

## 停点6：角色/场景设计完成，等待用户确认后继续下一阶段

**必须向用户发送消息**，展示完整的角色和场景设计：

1. **人物图片**：从 `artifact.characters[].selected` 获取每个人物的图片路径
2. **场景图片**：从 `artifact.settings[].selected` 获取每个场景的图片路径
3. **人物列表**：包含角色名、描述、视觉提示词
4. **场景列表**：包含场景名、描述、视觉提示词

**发送消息时必须**：
- 根据消息渠道参考 [send_message/feishu.md](../send_message/feishu.md) 或 [send_message/wechat.md](../send_message/wechat.md) 发送图片
- 每张图片需附带简短说明（角色名/场景名）
- **发送前端 URL**（获取本地 IPv4 地址，构造 `http://{local_ip}:3000/?session={session_id}&stage=character_design`）
- 发送完整列表后，询问用户确认

询问内容示例：
> "角色和场景设计已完成，共生成 X 个人物和 Y 个场景。请确认是否继续进行分镜设计？"

## 继续下一阶段

用户确认后调用：

```bash
curl -X POST "http://localhost:8000/api/project/{session_id}/continue"
```

---

## 常见问题

| 错误 | 原因 | 解决方法 |
|------|------|----------|
| `curl: (7) Failed to connect` | 后端未运行 | 启动后端服务 |
| `asset_complete` 状态为 failed | 图片生成失败 | 检查 API Key 配置，记录失败原因 |
| 图片下载失败 | URL 路径错误 | 确认 path 格式为 `code/result/...` |
| SSE 连接断开 | 网络超时 | 使用轮询 `/api/project/{session_id}/status` 继续 |
| 用户不确认 | 用户想修改角色 | 调用 modify_character 重新生成 |
