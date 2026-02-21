# 安全策略与密钥管理

本仓库包含敏感配置，**严禁**直接提交任何真实密钥、Token 或密码。

## 🚫 密钥管理原则

1. **绝对禁止硬编码**：任何 API Key、App Secret、Token 都必须通过环境变量或 `pass` 管理。
2. **提交前检查**：使用 `git diff` 检查即将提交的代码中是否包含 `sk-`、`secret` 等关键词。
3. **发现泄露立即轮换**：一旦密钥进入 git 历史，视为已泄露，必须立即在服务提供商处重置。

## 🔑 受影响的密钥（需立即轮换）

以下密钥曾出现在历史记录中，**不再安全**，请立即轮换：

1. **飞书应用 (汉兴企业)**
   - App ID: `REDACTED_FEISHU_HANXING_APP_ID`
   - Secret: `***...IN` (已泄露)
   
2. **飞书应用 (个人)**
   - App ID: `REDACTED_FEISHU_PERSONAL_APP_ID`
   - Secret: `***...Gd` (已泄露)

3. **OpenRouter API Key**
   - Key: `sk-3J...Nd` (已泄露)

## 🛠 配置方法

推荐使用环境变量或 `pass` 密钥管理器。

### 方式 A: 环境变量 (推荐)

在 `~/.bashrc` 或 `.env` (需加入 .gitignore) 中配置：

```bash
# 飞书
export FEISHU_APP_ID_HANXING="REDACTED_FEISHU_HANXING_APP_ID"
export FEISHU_APP_SECRET_HANXING="your_new_secret_here"
export FEISHU_APP_ID_PERSONAL="REDACTED_FEISHU_PERSONAL_APP_ID"
export FEISHU_APP_SECRET_PERSONAL="your_new_secret_here"

# AI 服务
export OPENROUTER_API_KEY="sk-..."
```

### 方式 B: pass 密钥管理

本仓库的工具已集成自动从 `pass` 读取密钥的功能：

```bash
pass insert api/feishu-hanxing
# 输入格式:
# app_id=cli_...
# app_secret=your_new_secret
```

## 🚨 紧急响应流程

如果发现新的泄露：
1. **立即撤销密钥**：去对应平台删除旧密钥。
2. **清理代码**：移除代码中的密钥。
3. **修改历史**：如果需要，使用 `git filter-repo` 清理历史（慎用，会改变 commit hash）。
4. **通知团队**：告知所有协作者更新密钥。
