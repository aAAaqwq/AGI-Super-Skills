# Feishu Channel TODO

## 必需配置项

### 1. 飞书应用凭证
- **App ID**: 在飞书开放平台创建应用后获取
- **App Secret**: 应用密钥
- **Verification Token**: 事件订阅验证 Token
- **Encrypt Key**: 事件加密密钥（推荐）

### 2. 应用权限
需要在飞书开放平台开启以下权限：
- `im:message` - 消息读写
- `im:message.group_at_msg` - 群聊@消息
- `im:message.p2p_msg` - 私聊消息
- `im:chat` - 群聊信息
- `contact:user.base` - 用户基本信息

### 3. 事件订阅
- 配置 Webhook URL（需要公网可访问）
- 订阅 `im.message.receive_v1` 事件

## 待解决问题

### 架构问题

1. **OpenClaw Channel 插件开发**
   - 当前方案使用独立 Webhook 服务桥接
   - 可考虑开发原生 OpenClaw 插件（参考 telegram 插件）
   - 需要研究 OpenClaw 插件 SDK

2. **消息路由**
   - Webhook 服务如何与 OpenClaw Gateway 通信
   - 会话上下文如何保持

3. **卡片消息交互**
   - 按钮点击回调需要额外配置
   - 需要实现卡片交互处理逻辑

### 技术问题

1. **Webhook URL**
   - 需要公网可访问的 URL
   - 可使用 ngrok/frp 等内网穿透工具
   - 或部署到云服务器

2. **Access Token 管理**
   - Token 有效期 2 小时
   - 需要自动刷新机制

3. **消息可靠性**
   - 飞书事件推送有重试机制
   - 需要实现幂等处理

### 安全问题

1. **事件验证**
   - 必须验证 Verification Token
   - 推荐启用 Encrypt Key 加密

2. **权限控制**
   - 私聊白名单
   - 群聊白名单

## 后续优化方向

### 功能增强

- [ ] 支持图片消息
- [ ] 支持文件消息
- [ ] 支持卡片消息交互
- [ ] 支持消息撤回
- [ ] 支持消息已读回执

### 稳定性

- [ ] Token 自动刷新
- [ ] 事件去重
- [ ] 错误重试
- [ ] 日志监控

### 部署

- [ ] Docker 容器化
- [ ] 系统服务配置
- [ ] 健康检查
- [ ] 自动重启

## 与 feishu-automation 的集成

feishu-channel 专注于消息通道，可以与 feishu-automation 配合使用：

1. **消息触发自动化**
   - 用户发送消息 → feishu-channel 接收
   - AI 处理后调用 feishu-automation 操作多维表格

2. **自动化结果通知**
   - feishu-automation 完成任务
   - 通过 feishu-channel 发送通知

## 替代方案

如果不想自建 Webhook 服务：

1. **使用 lark-mcp 的消息功能**
   - 仅支持发送，不支持接收
   - 适合单向通知场景

2. **飞书机器人 Webhook**
   - 仅支持发送到群聊
   - 不需要创建应用

## 参考资源

- 飞书开放平台: https://open.feishu.cn/
- 事件订阅文档: https://open.feishu.cn/document/ukTMukTMukTM/uUTNz4SN1MjL1UzM
- 消息 API 文档: https://open.feishu.cn/document/uAjLw4CM/ukTMukTMukTM/im-v1/message/create
- 卡片搭建工具: https://open.feishu.cn/tool/cardbuilder
