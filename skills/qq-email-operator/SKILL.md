---
name: qq-email-operator
description: QQ邮箱操作技能。支持通过 IMAP/SMTP 读取邮件、搜索邮件、回复邮件、发送邮件。凭据通过 pass 安全存储。
license: MIT
metadata:
  version: 1.0.0
  domains:
  - email
  - automation
  - communication
  type: automation
author: Daniel Li
---

# QQ 邮箱操作技能

- Author: Daniel Li
- Copyright © Daniel Li. All rights reserved.

## 当使用此技能

- 读取 QQ 邮箱收件箱
- 搜索特定发件人/主题的邮件
- 回复邮件（英文/中文）
- 发送新邮件
- 查看邮件详情（正文、附件信息）

## 前置条件

1. QQ 邮箱已开启 IMAP/SMTP 服务
2. 授权码已存入 `pass`：
   - `pass show email/qq/<邮箱地址>` 或
   - `pass show email/qq/<QQ号>`

## 服务器配置

| 协议 | 服务器 | 端口 | SSL |
|------|--------|------|-----|
| IMAP | imap.qq.com | 993 | ✅ |
| SMTP | smtp.qq.com | 465 | ✅ SSL |
| SMTP | smtp.qq.com | 587 | ✅ STARTTLS |

## 使用方法

### 1. 读取最近邮件
```bash
python3 ~/clawd/skills/qq-email-operator/scripts/qq_email.py list --account 2067089451@qq.com --limit 10
```

### 2. 搜索特定邮件
```bash
python3 ~/clawd/skills/qq-email-operator/scripts/qq_email.py search --account 2067089451@qq.com --from "vince@example.com"
python3 ~/clawd/skills/qq-email-operator/scripts/qq_email.py search --account 2067089451@qq.com --subject "keyword"
```

### 3. 读取邮件正文
```bash
python3 ~/clawd/skills/qq-email-operator/scripts/qq_email.py read --account 2067089451@qq.com --id 948
```

### 4. 回复邮件
```bash
python3 ~/clawd/skills/qq-email-operator/scripts/qq_email.py reply \
  --account 2067089451@qq.com \
  --id 948 \
  --body "Your reply text here" \
  --sender-name "Daniel Li"
```

### 5. 发送新邮件
```bash
python3 ~/clawd/skills/qq-email-operator/scripts/qq_email.py send \
  --account 2067089451@qq.com \
  --to "recipient@example.com" \
  --subject "Subject" \
  --body "Email body" \
  --sender-name "Daniel Li"
```

## 触发词

- "查看QQ邮箱"
- "读取QQ邮件"
- "回复QQ邮件"
- "发送QQ邮件"
- "搜索QQ邮件"
- "QQ邮箱操作"
- "reply to email"
- "send email via QQ"

## 安全策略

| 操作 | 权限 |
|------|------|
| 读取邮件列表 | 🟢 自动 |
| 读取邮件正文 | 🟢 自动 |
| 搜索邮件 | 🟢 自动 |
| **回复邮件** | 🟡 **需确认** |
| **发送新邮件** | 🟡 **需确认** |
| 删除邮件 | 🔴 **禁止** |

## 已配置账号

| 邮箱 | pass 路径 | 状态 |
|------|----------|------|
| 2067089451@qq.com | `email/qq/2067089451` | ✅ 已验证 |

## 注意事项

- 授权码 ≠ QQ密码，需在 QQ 邮箱设置中单独生成
- 海外服务器连接 QQ 邮箱可能需要代理
- SMTP 发送建议用 465 端口（SSL）
- 回复邮件自动设置 In-Reply-To 和 References 头以保持邮件线程
