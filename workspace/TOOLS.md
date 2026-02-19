# TOOLS.md - Local Notes

## Telegram

| Bot | Chat ID | 用途 |
|-----|---------|------|
| @DanielLi_smartest_Bot | YOUR_CHAT_ID | 主 bot (OpenClaw) |
| @fkkanfnnfbot | YOUR_GROUP_CHAT_ID | 新闻推送 (DailyNews 群) |

## 飞书

| 租户 | App ID | 默认群 |
|------|--------|--------|
| hanxing | `YOUR_FEISHU_APP_ID` | `YOUR_FEISHU_GROUP_ID` (技术开发) |
| personal | `YOUR_FEISHU_APP_ID` | `YOUR_FEISHU_GROUP_ID` (知识云文档) |

```bash
./skills/feishu-automation/feishu-send.sh "消息"          # 汉兴
./skills/feishu-automation/feishu-send.sh --personal "消息" # 个人
```

## 密钥 (pass)

| 服务 | 路径 |
|------|------|
| xingjiabiapi | `api/xingjiabiapi` |
| 飞书汉兴 | `api/feishu-hanxing` |
| 飞书个人 | `api/feishu-personal` |
| OpenRouter VIP | `api/openrouter-vip` |
| ZAI | `api/zai` |
| Firecrawl | `api/firecrawl` |
| DeepSeek | `api/deepseek` |
| Notion | `api/notion` |
| KlingAI | `api/klingai` |
| 天眼查 | `api/tianyancha` |

**原则**: 永不硬编码。`pass show api/xxx` 获取。

## 安全分层

| 🟢 自由 | 🟡 需确认 | 🔴 禁止 |
|---------|----------|---------|
| 读取、查询 | 发邮件、发布内容 | 金融、账户安全 |

## Playwright 登录态

| 平台 | 存储 |
|------|------|
| GitHub | `~/.playwright-data/github` |
| 性价比 | `~/.playwright-data/xingjiabiapi` |
