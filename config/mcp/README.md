# MCP Servers 配置

> 更新时间: 2026-02-04

## 🔌 MCP 列表 (5个)

| MCP | 说明 | 包名 |
|-----|------|------|
| `github` | GitHub 操作 | `@modelcontextprotocol/server-github` |
| `context7` | 代码文档搜索 | `@upstash/context7-mcp` |
| `chrome-devtools` | Chrome 开发工具 | `chrome-devtools-mcp` |
| `lark-mcp` | 飞书操作 | `@larksuiteoapi/lark-mcp` |
| `notion` | Notion 操作 | `engram-notion-mcp` |

---

## 🔧 配置示例

### ~/.claude.json

```json
{
  "mcpServers": {
    "github": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-github"],
      "env": {
        "GITHUB_PERSONAL_ACCESS_TOKEN": "ghp_xxx"
      }
    },
    "context7": {
      "command": "npx",
      "args": [
        "-y",
        "@upstash/context7-mcp",
        "--api-key",
        "ctx7sk-xxx"
      ]
    },
    "chrome-devtools": {
      "command": "npx",
      "args": ["-y", "chrome-devtools-mcp@latest"]
    },
    "lark-mcp": {
      "command": "npx",
      "args": [
        "-y",
        "@larksuiteoapi/lark-mcp",
        "mcp",
        "-a", "cli_xxx",
        "-s", "xxx",
        "-t", "preset.light,preset.default,preset.im.default,preset.base.default,preset.base.batch,preset.doc.default,preset.task.default,preset.calendar.default"
      ]
    },
    "notion": {
      "command": "npx",
      "args": ["-y", "engram-notion-mcp"],
      "env": {
        "NOTION_API_KEY": "ntn_xxx"
      }
    }
  }
}
```

---

## 📝 MCP 详情

### github

**功能**:
- 仓库管理
- Issue/PR 操作
- 代码搜索
- Actions 管理

**获取 Token**: https://github.com/settings/tokens

### context7

**功能**:
- 代码文档语义搜索
- 技术文档查询
- API 文档检索

**获取 API Key**: https://context7.com

### lark-mcp

**功能**:
- 发送消息
- 多维表格操作
- 文档管理
- 日历/任务

**配置参数**:
- `-a`: App ID
- `-s`: App Secret
- `-t`: 预设功能集

### notion

**功能**:
- 页面管理
- 数据库操作
- 内容搜索

**获取 API Key**: https://www.notion.so/my-integrations

### chrome-devtools

**功能**:
- 浏览器调试
- 网络请求监控
- DOM 操作
