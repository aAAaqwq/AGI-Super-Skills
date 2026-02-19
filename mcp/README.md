# MCP 配置

当前环境未配置独立的 MCP servers。

如需添加 MCP server，在 OpenClaw 中通过以下方式配置：

1. 在 `openclaw.json` 中添加 `mcp` 字段
2. 或在各 agent 的 `agent.json` 中配置 `mcpServers`

示例配置：
```json
{
  "mcpServers": {
    "server-name": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-xxx"],
      "env": {
        "API_KEY": "YOUR_API_KEY_HERE"
      }
    }
  }
}
```
