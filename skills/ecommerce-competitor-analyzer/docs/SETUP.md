# 环境变量配置指南

## 快速开始

```bash
# 1. 复制示例配置文件
cp .env.example .env

# 2. 编辑 .env 文件，填入你的 API Keys
nano .env  # 或使用你喜欢的编辑器
```

## 获取 API Keys

### 1. Olostep API Key（必需）

**用途**: 网页抓取服务（100条评论深度抓取）

**获取步骤**:
1. 访问: https://olostep.com/
2. 注册账号
3. 登录后进入 Dashboard
4. 找到 API Key 部分
5. 复制你的 API Key

**定价**:
- 免费额度: 1000 次/月
- 超出后: $0.002/请求

**配置**:
```bash
OLOSTEP_API_KEY=olostep_xxxxxxxxxxxxx
```

---

### 2. Google Gemini API Key（必需）

**用途**: AI 竞品分析（gemini-3-flash-preview）

**获取步骤**:
1. 访问: https://aistudio.google.com/app/apikey
2. 点击 "Create API Key" 或 "创建 API 密钥"
3. 选择或创建一个 Google Cloud 项目
4. 复制生成的 API Key

**定价**:
- 免费额度: 每月一定请求数
- 按量付费: 性价比高

**配置**:
```bash
GEMINI_API_KEY=AIzaSyXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
```

---

### 3. Google Sheets Credentials（可选）

**用途**: 自动写入分析结果到 Google Sheets

**注意**: 阶段 1 MVP 可以先不配置，使用 Markdown 输出

**获取步骤**:
1. 访问: https://console.cloud.google.com/apis/credentials
2. 选择一个项目或创建新项目
3. 点击 "Create Credentials" → "OAuth Client ID"
4. 应用类型选择 "Web application"
5. 添加授权重定向 URI:
   ```
   http://localhost:8080
   ```
6. 下载 JSON 凭证文件
7. 将 JSON 内容（单行）复制到 .env

**配置**:
```bash
GOOGLE_SHEETS_CREDENTIALS='{"web":{"client_id":"...","client_secret":"...","auth_uri":"...","token_uri":"...","redirect_uris":["..."]}}'
```

---

## 配置验证

配置完成后，运行验证脚本：

```bash
node scripts/verify-env.js
```

预期输出：
```
✅ OLOSTEP_API_KEY: Configured
✅ GEMINI_API_KEY: Configured
✅ GOOGLE_SHEETS_CREDENTIALS: Optional (not configured)

Environment setup complete!
```

---

## 测试 API Keys

### 测试 Olostep API
```bash
curl -X POST https://api.olostep.com/v2/agent/web-agent \
  -H "Authorization: Bearer YOUR_OLOSTEP_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://www.amazon.com/dp/B0C4YT8S6H",
    "comments_number": 10
  }'
```

### 测试 Gemini API
```bash
curl -X POST \
  "https://generativelanguage.googleapis.com/v1beta/models/gemini-3-flash-preview:generateContent?key=YOUR_GEMINI_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "contents": [{
      "parts": [{"text": "Hello"}]
    }]
  }'
```

---

## 安全提醒

1. **永远不要**将 .env 文件提交到 Git
2. **永远不要**在公开代码中暴露 API Keys
3. 定期轮换你的 API Keys
4. 为不同环境使用不同的 Keys

---

## 故障排除

### 问题 1: Olostep API 返回 401
**原因**: API Key 无效或过期
**解决**: 检查 .env 中的 OLOSTEP_API_KEY 是否正确

### 问题 2: Gemini API 返回 403
**原因**: API Key 没有权限或配额用尽
**解决**: 检查 Google Cloud Console 中的配额和权限

### 问题 3: Google Sheets 认证失败
**原因**: OAuth2 凭证格式错误或重定向 URI 不匹配
**解决**: 确保重定向 URI 完全匹配（注意末尾不要有斜杠）

---

## n8n 工作流凭证参考

如果你已经在 n8n 中配置过这些凭证，可以在 n8n 界面查看：

- **n8n URL**: Your n8n workflow URL (if applicable)
- **Settings** → **Credentials**

但是注意：n8n 使用加密的凭证存储，无法直接复制 API Keys。
你需要按照上述步骤重新获取。

---

## 下一步

环境变量配置完成后，你就可以使用 skill 了：

```
"分析 B0C4YT8S6H"
```

或者批量分析：

```
"分析 B0C4YT8S6H, B08N5WRQ1Y, B0CLFH7CCV"
```
