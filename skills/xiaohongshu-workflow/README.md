# 小红书全流程运营工作流

<p align="center">
  <b>基于 OpenClaw 的小红书运营自动化 Skill</b>
</p>

<p align="center">
  <a href="#功能特性">功能特性</a> •
  <a href="#快速开始">快速开始</a> •
  <a href="#使用方法">使用方法</a> •
  <a href="#目录结构">目录结构</a>
</p>

---

## 功能特性

| 模块 | 功能 |
|------|------|
| 账号配置 | MCP 服务安装、登录获取 Cookies、服务启动 |
| 内容发布 | 图文/视频笔记发布、内容规范检查 |
| 热点追踪 | 关键词搜索、话题监控、报告生成 |
| 互动管理 | 评论获取、自动回复、粉丝互动 |
| 数据分析 | 表现监控、趋势分析、报警规则 |
| 记忆导出 | 收藏/点赞导出为 AI 可搜索知识库 |

## 快速开始

### 1. 安装依赖

```bash
# 下载 xiaohongshu-mcp
wget https://github.com/xpzouying/xiaohongshu-mcp/releases/latest/download/xiaohongshu-mcp-linux-amd64.tar.gz
wget https://github.com/xpzouying/xiaohongshu-mcp/releases/latest/download/xiaohongshu-login-linux-amd64.tar.gz

# 解压安装
mkdir -p ~/.local/bin
tar -xzf xiaohongshu-mcp-*.tar.gz -C ~/.local/bin/
tar -xzf xiaohongshu-login-*.tar.gz -C ~/.local/bin/
chmod +x ~/.local/bin/xiaohongshu-*
```

### 2. 登录获取 Cookies

```bash
# 本地桌面环境
~/.local/bin/xiaohongshu-login

# Linux 服务器：从 Windows 复制 cookies
# Windows 运行 xiaohongshu-login-windows-amd64.exe
# Cookies 保存在 C:\Users\<用户名>\AppData\Local\Temp\cookies.json
# 复制到服务器：scp cookies.json user@server:~/.xiaohongshu/
```

### 3. 启动服务

```bash
# 进入脚本目录
cd scripts/

# 检查依赖
./install-check.sh

# 启动 MCP 服务
./start-mcp.sh

# 检查状态
./status.sh
```

### 4. 安装到 OpenClaw

```bash
# 链接到 workspace
ln -s /path/to/xiaohongshu-workflow ~/.openclaw/workspace/skills/xiaohongshu-workflow
```

## 使用方法

### 搜索内容

```bash
./scripts/search.sh "OpenClaw"
```

### 发布笔记

```bash
./scripts/mcp-call.sh publish_content '{
  "title": "标题",
  "content": "正文内容",
  "images": ["/path/to/image1.jpg"],
  "tags": ["标签1", "标签2"]
}'
```

### 热点追踪报告

```bash
./scripts/track-topic.sh "DeepSeek" --limit 10 --output report.md
```

### 获取帖子详情

```bash
./scripts/post-detail.sh <note_id> <xsec_token>
```

## 目录结构

```
xiaohongshu-workflow/
├── SKILL.md                      # Skill 主文档
├── README.md                     # 说明文档
├── LICENSE                       # MIT 许可证
├── scripts/                      # 可执行脚本
│   ├── install-check.sh          # 依赖检查
│   ├── start-mcp.sh               # 启动服务
│   ├── stop-mcp.sh               # 停止服务
│   ├── status.sh                 # 状态检查
│   ├── login.sh                  # 登录
│   ├── search.sh                 # 搜索
│   ├── recommend.sh               # 推荐
│   ├── post-detail.sh             # 帖子详情
│   ├── comment.sh                 # 评论
│   ├── user-profile.sh            # 用户主页
│   ├── track-topic.sh             # 热点追踪
│   ├── track-topic.py             # 追踪脚本
│   └── mcp-call.sh                # 通用调用
└── references/                   # 参考文档
    ├── api-reference.md           # MCP API 参考
    ├── content-strategy.md        # 内容策略指南
    └── troubleshooting.md         # 常见问题解决
```

## 注意事项

- **发布限制**：标题≤20字符，正文≤1000字符，每日≤50条
- **账号安全**：避免多设备同时登录，Cookies 约 30 天过期
- **首次运行**：会下载 headless 浏览器（约 150MB）
- **合规使用**：遵守小红书平台规则，不发布违规内容

## 依赖

- [xiaohongshu-mcp](https://github.com/xpzouying/xiaohongshu-mcp) - 小红书 MCP 服务
- [XHS-Downloader](https://github.com/JoeanAmier/XHS-Downloader) - 记忆导出（可选）

## 许可证

MIT License

## 致谢

- [@xpzouying](https://github.com/xpzouying) — [xiaohongshu-mcp](https://github.com/xpzouying/xiaohongshu-mcp)
- [@JoeanAmier](https://github.com/JoeanAmier) — [XHS-Downloader](https://github.com/JoeanAmier/XHS-Downloader)