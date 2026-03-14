# douyin-publish

抖音视频发布 skill。使用 MCP 技术自动登录、上传并发布视频到抖音创作者平台。

## 功能

- 📹 **登录抖音** - 管理抖音账号登录状态
- 🚀 **发布视频** - 上传视频并发布到抖音
- ✅ **检查状态** - 查看登录状态和发布结果
- 🏷️ **标签管理** - 支持视频标签和话题

## 使用方式

### 发布视频到抖音

直接在对话中发布视频：

```
帮我发布视频到抖音
标题：酥脆金黄鸡腿
视频：/home/gonghaiquan/Downloads/jimeng-2026-02-13-3808-Crispy golden chicken leg.mp4
描述：外酥里嫩，美味无法挡！
标签：美食,鸡腿,烹饪
```

或更简洁：

```
发布视频 /home/gonghaiquan/Downloads/video.mp4
标题：我的视频标题
```

### 检查登录状态

```
检查抖音登录状态
```

### 重新登录

```
重新登录抖音账号
```

## 所需工具

需要配置好的 MCP 服务器：

1. **douyin-upload** - 视频上传 MCP
   - 命令：`node ~/douyin-mcp-server/mcp-server/dist/index.js`
   - 功能：登录、上传、发布视频

2. **douyin-extract** - 视频文案提取 MCP（可选）
   - 命令：`uvx douyin-mcp-server`
   - 功能：提取无水印链接、AI 文案识别

## 配置方法

确保 MCP 服务器已添加到配置：

```bash
mcporter config add douyin-upload "node ~/douyin-mcp-server/mcp-server/dist/index.js"
mcporter config add douyin-extract "uvx douyin-mcp-server"
```

## 技术细节

- **浏览器自动化**：使用 Puppeteer 控制 Chrome
- **系统 Chrome**：`/usr/bin/google-chrome`
- **Cookie 保存**：自动持久化登录状态
- **验证码处理**：支持短信验证码手动输入

## 示例对话

**用户**：帮我发布这个鸡腿视频到抖音

**助手**：
```
🚀 开始发布视频到抖音...

✅ 登录成功！账号已验证

📤 正在上传视频...
✅ 视频上传完成

🏷️ 设置标签：#美食 #鸡腿 #烹饪

🚀 正在发布...
✅ 发布成功！

📋 视频信息：
- 标题：酥脆金黄鸡腿，美味诱人！
- 状态：已发布
- 链接：https://www.douyin.com/video/...

🎉 视频已成功发布到抖音！
```

## 注意事项

- 首次使用需要手动扫码/短信验证
- Cookie 有效期有限，过期需要重新登录
- 建议使用创作者账号
- 发布频率不要过高，避免触发限制

## 文件位置

- Skill 目录：`/home/gonghaiquan/.openclaw/skills/douyin-publish/`
- MCP 服务器：`~/douyin-mcp-server/`
- Cookie 保存：`~/douyin-mcp-server/mcp-server/douyin-cookies.json`
