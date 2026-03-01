# GitHub 上传指南

## Skill 已创建完成！

**位置:** `/home/shengz/.openclaw/workspace/skills/xiaohongshu-workflow/`

**已打包文件:** `/home/shengz/.openclaw/workspace/xiaohongshu-workflow.skill`

---

## 上传到 GitHub 的步骤

### 方式一：手动上传（推荐）

1. **创建 GitHub 仓库**
   - 访问 https://github.com/new
   - 仓库名: `xiaohongshu-workflow`
   - 描述: 小红书全流程运营工作流 OpenClaw Skill
   - 设为 Public
   - 不要勾选 "Add a README file"
   - 点击 "Create repository"

2. **在服务器上配置 Git**
   ```bash
   # 如果没有 SSH key，创建一个
   ssh-keygen -t ed25519 -C "your-email@example.com"
   
   # 查看公钥
   cat ~/.ssh/id_ed25519.pub
   
   # 将公钥添加到 GitHub: Settings -> SSH and GPG keys -> New SSH key
   ```

3. **推送代码**
   ```bash
   cd /home/shengz/.openclaw/workspace/skills/xiaohongshu-workflow
   
   # 添加远程仓库（替换为你的用户名）
   git remote add origin git@github.com:YOUR_USERNAME/xiaohongshu-workflow.git
   
   # 重命名分支为 main
   git branch -M main
   
   # 推送
   git push -u origin main
   ```

### 方式二：上传 .skill 文件

1. 访问 https://github.com/new 创建新仓库
2. 将 `/home/shengz/.openclaw/workspace/xiaohongshu-workflow.skill` 文件上传到仓库
3. 这个 .skill 文件可以直接被 OpenClaw 安装

### 方式三：使用 GitHub CLI（需要安装）

```bash
# 安装 GitHub CLI
sudo apt install gh

# 登录
gh auth login

# 创建仓库并推送
cd /home/shengz/.openclaw/workspace/skills/xiaohongshu-workflow
gh repo create xiaohongshu-workflow --public --source=. --push
```

---

## Skill 内容概览

```
xiaohongshu-workflow/
├── SKILL.md                      # 主文档 (415 行)
├── README.md                     # 说明文档
├── LICENSE                       # MIT 许可证
├── .gitignore
├── scripts/                      # 可执行脚本 (13 个)
│   ├── install-check.sh
│   ├── start-mcp.sh
│   ├── stop-mcp.sh
│   ├── status.sh
│   ├── login.sh
│   ├── search.sh
│   ├── recommend.sh
│   ├── post-detail.sh
│   ├── comment.sh
│   ├── user-profile.sh
│   ├── track-topic.sh
│   ├── track-topic.py
│   └── mcp-call.sh
└── references/                   # 参考文档 (3 个)
    ├── api-reference.md          # MCP API 完整参考
    ├── content-strategy.md       # 内容策略指南
    └── troubleshooting.md        # 常见问题解决
```

**总计:** 20 个文件, 2260 行代码

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