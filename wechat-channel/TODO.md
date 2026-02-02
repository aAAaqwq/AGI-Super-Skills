# WeChat Channel TODO

## 必需配置项

### 1. PadLocal Token
- **获取方式**: https://pad-local.com
- **费用**: 约 ¥200/月
- **说明**: 单 Token 只能登录一个微信号

### 2. OpenClaw Webhook 配置
- 需要在 OpenClaw Gateway 中配置 Webhook 接收端点
- 当前 OpenClaw 可能不原生支持自定义 channel，需要：
  - 方案 A: 开发 OpenClaw 插件 (参考 telegram/whatsapp 插件)
  - 方案 B: 使用 Webhook 转发到现有 channel

## 待解决问题

### 架构问题

1. **OpenClaw Channel 插件开发**
   - 当前 OpenClaw 的 channel 插件是 TypeScript 编写
   - 需要研究如何创建自定义 channel 插件
   - 或者使用 Webhook 方式桥接

2. **消息路由**
   - 如何将微信消息正确路由到 OpenClaw Agent
   - 如何将 Agent 回复发送回微信

3. **会话管理**
   - 如何维护微信用户与 OpenClaw 会话的对应关系
   - 多轮对话上下文保持

### 技术问题

1. **登录状态持久化**
   - PadLocal 登录状态如何持久化
   - 服务重启后是否需要重新扫码

2. **消息可靠性**
   - 消息发送失败的重试机制
   - 消息队列（高并发场景）

3. **媒体消息处理**
   - 图片/文件的上传下载
   - 语音消息转文字（需要额外服务）

### 安全问题

1. **权限控制**
   - 私聊白名单
   - 群聊白名单
   - 群内用户白名单

2. **敏感信息**
   - Token 安全存储
   - 日志脱敏

## 后续优化方向

### 功能增强

- [ ] 支持语音消息（转文字）
- [ ] 支持图片识别
- [ ] 支持文件处理
- [ ] 支持表情包
- [ ] 支持小程序卡片解析

### 稳定性

- [ ] 断线自动重连
- [ ] 心跳检测
- [ ] 消息队列
- [ ] 日志监控告警

### 部署

- [ ] Docker 容器化
- [ ] PM2 进程管理
- [ ] 系统服务配置
- [ ] 健康检查端点

## 替代方案

如果 PadLocal 不可用，可考虑：

1. **itchat** (Python)
   - 免费，但不稳定
   - 容易被封号

2. **WxPusher**
   - 仅支持发送，不支持接收
   - 适合单向通知场景

3. **企业微信**
   - 官方 API，稳定
   - 需要企业认证
   - 功能受限

4. **微信公众号**
   - 官方 API
   - 需要认证
   - 只能被动回复

## 参考资源

- Wechaty 文档: https://wechaty.js.org/docs/
- PadLocal 官网: https://pad-local.com/
- OpenClaw 插件开发: 参考 `~/.npm-global/lib/node_modules/openclaw/extensions/`
