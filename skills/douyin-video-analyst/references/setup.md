# Setup 配置指南

## 1. 确认 mcporter 安装

```bash
which mcporter
clawhub -V
```

如未安装：`npm install -g mcporter`

## 2. 配置 douyin-mcp

mcporter 自动加载 `~/.cursor/mcp.json` 和 `~/.claude.json` 两个配置文件，在任意一个中配置即可。

### 方案 A：v1.1.0 + 硅基流动（推荐，免费额度充足）

```json
{
  "mcpServers": {
    "douyin-mcp": {
      "command": "uvx",
      "args": ["douyin-mcp-server@1.1.0"],
      "env": {
        "DOUYIN_API_KEY": "sk-xxxxxxxxxxxxxxxx"
      }
    }
  }
}
```

硅基流动 API Key：https://cloud.siliconflow.cn/

### 方案 B：v1.2.0+（最新版）+ 阿里云百炼

```json
{
  "mcpServers": {
    "douyin-mcp": {
      "command": "uvx",
      "args": ["douyin-mcp-server"],
      "env": {
        "DASHSCOPE_API_KEY": "sk-xxxxxxxxxxxxxxxx"
      }
    }
  }
}
```

阿里云百炼 API Key：https://bailian.console.aliyun.com/

## 3. 版本对照

| 版本 | API 平台 | 环境变量 |
|------|----------|----------|
| ≤ 1.1.0 | 硅基流动 | `DOUYIN_API_KEY` |
| ≥ 1.2.0 | 阿里云百炼 | `DASHSCOPE_API_KEY` |

## 4. 验证配置

```bash
mcporter list 2>&1 | grep douyin-mcp
# 期望输出：- douyin-mcp (5 tools, ...) [source: ...]

# v1.1.0 验证
DOUYIN_API_KEY="sk-xxx" mcporter call douyin-mcp.parse_douyin_video_info \
  share_link="https://www.douyin.com/video/7612354982592343675" 2>&1
# 期望：返回 {"status":"success","title":"...","download_url":"..."}

# v1.2.0+ 验证
DASHSCOPE_API_KEY="sk-xxx" mcporter call douyin-mcp.parse_douyin_video_info \
  share_link="https://www.douyin.com/video/7612354982592343675" 2>&1
```
