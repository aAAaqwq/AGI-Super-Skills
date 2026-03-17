# Provider Configurations

API供应商/服务的查询配置。按类型分组。

## 官方供应商 (API 直查)

### xAI (Grok)

- **API Base**: `https://api.x.ai/v1` (Inference) / `https://management-api.x.ai` (Management)
- **Auth**:
  - Inference: `XAI_API_KEY`
  - Management: `XAI_MGMT_KEY` (from console.x.ai → Settings → Management Keys)
  - Team ID: `XAI_TEAM_ID`
- **Billing API**: ✅ 有 Management API
  ```bash
  # 预付费余额
  curl -s "https://management-api.x.ai/v1/billing/teams/$XAI_TEAM_ID/prepaid/balance" \
    -H "Authorization: Bearer $XAI_MGMT_KEY"

  # 后付费账单预览
  curl -s "https://management-api.x.ai/v1/billing/teams/$XAI_TEAM_ID/postpaid/invoice/preview" \
    -H "Authorization: Bearer $XAI_MGMT_KEY"

  # 用量历史 (POST)
  curl -s -X POST "https://management-api.x.ai/v1/billing/teams/$XAI_TEAM_ID/usage" \
    -H "Authorization: Bearer $XAI_MGMT_KEY" \
    -H "Content-Type: application/json" \
    -d '{"analyticsRequest":{"timeRange":{"startTime":"2026-03-01 00:00:00","endTime":"2026-03-15 23:59:59"},"values":[{"name":"usd","aggregation":"AGGREGATION_SUM"}],"groupBy":["description"]}}'
  ```
- **返回**:
  - `total.val`: 预付费余额（负数 cents，如 -500 = $5.00）
  - `changes[]`: 充值记录
- **Docs**: https://docs.x.ai/developers/rest-api-reference/management/billing

### Google AI (Gemini)

- **API Base**: `https://generativelanguage.googleapis.com/v1`
- **Auth**: `GOOGLE_API_KEY` 或 `GEMINI_API_KEY`
- **Usage API**: ❌ 需要浏览器抓 Google AI Studio
- **Browser**: https://aistudio.google.com/apikey

### ZAI (智谱 GLM)

- **API Base**: `https://open.bigmodel.cn/api/paas/v4`
- **Auth**: `ZAI_API_KEY` 或 `ZHIPU_API_KEY`
- **Usage API**: ❌ 无公开余额API
- **Browser**: https://open.bigmodel.cn/oa/userCenter

### Minimax

- **API Base**: `https://api.minimax.chat/v1`
- **Auth**: `MINIMAX_API_KEY` + `MINIMAX_GROUP_ID`
- **Usage API**: 
  ```bash
  curl -s "https://api.minimax.chat/v1/user/balance" \
    -H "Authorization: Bearer $MINIMAX_API_KEY" \
    -H "GroupId: $MINIMAX_GROUP_ID"
  ```
- **返回**: `{"data": {"balance": 10.0, "unit": "CNY"}}`

### OpenRouter

- **API Base**: `https://openrouter.ai/api/v1`
- **Auth**: `OPENROUTER_API_KEY`
- **Usage API**: 
  ```bash
  curl -s "https://openrouter.ai/api/v1/auth/key" \
    -H "Authorization: Bearer $OPENROUTER_API_KEY"
  ```
- **返回**: `{"data": {"limit_remaining": 50.0, "usage": 10.0}}`

### Anthropic (Claude)

- **API Base**: `https://api.anthropic.com/v1`
- **Auth**: `ANTHROPIC_API_KEY`
- **Usage API**: ❌ 无公开API，需浏览器抓 console.anthropic.com

---

## 中转站 (浏览器抓取)

通用模板，需用户提供：
- 登录URL
- 余额页面URL
- 账号/密码（首次登录）
- 或使用现有 browser profile (openclaw)

### AIXN (XAPI)

- **Console**: `https://ai.9w7.cn/console`
- **检查方式**: Browser + snapshot
- **提取**: `Portfolio`, `余额`, `消耗`

### Provider-A

- **Console**: `https://your-provider.example.com/dashboard`
- **检查方式**: Browser + snapshot
- **提取**: 余额、令牌使用量

---

## 订阅服务 (API 直查)

### Brave Search API

- **API Base**: `https://api.search.brave.com/res/v1`
- **Auth**: `BRAVE_API_KEY`
- **Usage API**: ❌ 无公开API，API调用会301重定向到dashboard
- **Browser**: https://api-dashboard.search.brave.com

### Tavily API

- **API Base**: `https://api.tavily.com`
- **Auth**: `TAVILY_API_KEY`
- **Usage API**:
  ```bash
  curl -s "https://api.tavily.com/balance" \
    -H "Authorization: Bearer $TAVILY_API_KEY"
  ```
- **返回**: `{"balance": 1000, "used": 500}`

### Serper API

- **API Base**: `https://serper.dev/api`
- **Auth**: `SERPER_API_KEY`
- **Usage API**:
  ```bash
  curl -s "https://serper.dev/api/account" \
    -H "X-API-KEY: $SERPER_API_KEY"
  ```

### Jina AI Reader

- **API Base**: `https://r.jina.ai`
- **Auth**: `JINA_API_KEY` (optional for free tier)
- **Usage API**: 检查响应头 `X-RateLimit-Remaining`

---

## 本地缓存的供应商

从 OpenClaw 配置和 auth 状态读取已配置的供应商：

```bash
# 读取 OpenClaw config
cat ~/.openclaw/openclaw.json | jq '.models'

# 读取环境变量
env | grep -iE "_API_KEY|_TOKEN"

# 读取 auth 状态
cat ~/.openclaw/auth-session-state.json
```
