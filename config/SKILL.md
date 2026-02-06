# Config - 配置模板

OpenClaw 的配置模板和示例集合。

## 概述

此目录包含 OpenClaw/Claude Code 的配置模板，用于快速初始化新的 AI 工作空间。

## 文件说明

| 文件/目录 | 说明 |
|-----------|------|
| `AGENTS.md` | Agent 行为规范指南 |
| `SOUL.md` | Agent 身份定义模板 |
| `USER.md` | 用户信息模板 |
| `TOOLS.md` | 本地工具配置笔记 |
| `IDENTITY.md` | 身份标识配置 |
| `mcp_config.json` | MCP (Model Context Protocol) 配置示例 |
| `agents/` | Agent 配置模板 |
| `mcp/` | MCP 服务器配置 |
| `plugins/` | 插件配置 |
| `output-styles/` | 输出样式配置 |

## 使用方法

复制此目录到新的工作空间：

```bash
cp -r ~/clawd/skills/config/* ~/my-project/
```

然后编辑各文件以适应当前项目需求。

## 主要配置项

### AGENTS.md
定义 Agent 行为准则：
- 记忆管理（短期/长期）
- 安全规则
- 群聊参与规范
- 心跳任务处理

### SOUL.md
定义 Agent 身份：
- 名称和角色
- 语言风格
- 性格特点

### TOOLS.md
记录环境特定的信息：
- API 密钥位置
- 服务器地址
- 设备名称

## 相关技能

- [openclaw-config](../openclaw-config/) - OpenClaw 配置规范
- [pass-secrets](../pass-secrets/) - 密钥管理
- [env-setup](../env-setup/) - 环境配置同步
