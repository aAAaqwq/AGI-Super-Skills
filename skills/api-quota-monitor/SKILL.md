---
name: api-quota-monitor
description: "查询监控 API 供应商/服务的额度、余额、消耗情况。支持官方供应商(Gemini/xAI/ZAI/Minimax/OpenRouter等)、中转站(AIXN/Provider-A等)、订阅服务(Brave/Tavily/Serper)。触发词：查额度、查余额、API用量、供应商额度、quota、balance、usage、billing。"
---

# API Quota Monitor

查询监控各类 API 供应商和订阅服务的额度/余额/消耗。

## 快速使用

```bash
# 查询所有已配置的供应商
python3 scripts/query_quota.py

# 查询特定供应商
python3 scripts/query_quota.py xai
python3 scripts/query_quota.py openrouter
python3 scripts/query_quota.py brave

# 只查官方供应商
python3 scripts/query_quota.py --type official

# 只查订阅服务
python3 scripts/query_quota.py --type service

# JSON 输出
python3 scripts/query_quota.py --format json

# 发现已配置的供应商
python3 scripts/query_quota.py --discover
```

## 工作流

```
1. 发现本地已配置的 API/供应商（从环境变量、auth-session-state.json）
   ↓
2. 按类型查询：API 直查 > 浏览器抓取
   ↓
3. 生成报告：供应商 | 消耗 | 总额度 | 状态
```

## 供应商分类

### 官方供应商 (Official)

| 供应商 | 查询方式 | 环境变量 | 状态 |
|--------|----------|----------|------|
| ZAI (智谱) | API 直查 | `ZAI_API_KEY` | ✅ 支持 |
| Minimax | API 直查 | `MINIMAX_API_KEY` + `MINIMAX_GROUP_ID` | ✅ 支持 |
| OpenRouter | API 直查 | `OPENROUTER_API_KEY` | ✅ 支持 |
| xAI (Grok) | 浏览器 | `XAI_API_KEY` | 🔍 需浏览器 |
| Gemini | 浏览器 | `GOOGLE_API_KEY` | 🔍 需浏览器 |
| Anthropic | 浏览器 | `ANTHROPIC_API_KEY` | 🔍 需浏览器 |

### 中转站 (Reseller)

| 平台 | 查询方式 | 状态来源 |
|------|----------|----------|
| AIXN | 浏览器抓 ai.9w7.cn | auth-session-state.json |
| Provider-A | 浏览器抓 your-provider.example.com | auth-session-state.json |

中转站查询流程：
1. 检查 `~/.openclaw/auth-session-state.json` 获取登录状态
2. 使用 `browser(action='navigate', profile='openclaw')` 访问控制台
3. 从 snapshot 提取余额/消耗信息

### 订阅服务 (Services)

| 服务 | 查询方式 | 环境变量 |
|------|----------|----------|
| Brave Search API | API 直查 | `BRAVE_API_KEY` |
| Tavily API | API 直查 | `TAVILY_API_KEY` |
| Serper API | API 直查 | `SERPER_API_KEY` |

## 浏览器查询 (需浏览器抓取的供应商)

当供应商没有公开的 usage API 时，使用 browser 工具：

```
# 1. 导航到控制台页面
browser(action='navigate', profile='openclaw', targetUrl='<console_url>')

# 2. 等待加载后获取快照
browser(action='snapshot', profile='openclaw', compact=true, maxChars=2000)

# 3. 从快照中提取余额/消耗信息
# 查找关键词：余额、balance、usage、消耗、tokens、额度
```

**各供应商控制台 URL：**
- xAI: https://console.x.ai/usage
- Gemini: https://aistudio.google.com/apikey
- Anthropic: https://console.anthropic.com/settings/billing
- AIXN: https://ai.9w7.cn/console
- Provider-A: https://your-provider.example.com/dashboard

## 报告格式

```
📊 API Quota Report
⏰ 2026-03-15 20:30

━━ 官方供应商 ━━
✅ ZAI (智谱): ¥50.00
✅ Minimax: ¥10.00 CNY
✅ OpenRouter: $45.00 remaining
🔍 xAI (Grok): 需浏览器查询

━━ 订阅服务 ━━
✅ Brave Search: 1500/2000 requests
✅ Tavily: 800 remaining

━━ 中转站 ━━
✅ AIXN: ¥238.81
✅ Provider-A: ¥9.35
```

## 扩展新供应商

在 `scripts/query_quota.py` 中添加新供应商配置：

```python
OFFICIAL_PROVIDERS = {
    "new_provider": {
        "name": "New Provider",
        "env_key": "NEW_PROVIDER_API_KEY",
        "api_url": "https://api.newprovider.com/v1/usage",
        "method": "api",  # 或 "browser"
        "extract": lambda data: {
            "balance": data.get("balance", 0),
        }
    },
}
```

## 缓存策略

- API 查询结果可缓存 1-6 小时（避免频繁请求）
- 缓存文件: `~/.openclaw/quota-cache.json`
- 格式:
```json
{
  "openrouter": {
    "queried_at": "2026-03-15T20:00:00",
    "balance": 45.0,
    "cached": true
  }
}
```

## 定时监控

可配置 cron 定期检查并推送报告：

```bash
# 在 OpenClaw cron 中添加
# 每 6 小时检查一次 API 供应商额度
0 */6 * * * python3 ~/clawd/skills/api-quota-monitor/scripts/query_quota.py --report | newsbot_send
```

## 参考文档

详细的 API 端点和响应格式见 [references/providers.md](references/providers.md)
