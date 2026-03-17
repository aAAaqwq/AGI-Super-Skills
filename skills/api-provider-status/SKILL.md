# API Provider Status Skill

API 供应商状态查询与余额监控。

## 功能

- 查询各 API 供应商的余额/用量
- 生成统计报告
- 支持定时自动查询

## 支持的供应商

| 供应商 | 查询方式 | 登录状态存储 | 状态 |
|--------|----------|--------------|------|
| ~~Anapi (Claude)~~ | ~~API 直接查询~~ | - | ❌ 已废弃 |
| Provider-B | Playwright / Browser Tool | `~/.playwright-data/provider-b` | ✅ 可用 |
| GitHub Copilot | Playwright 抓取 | `~/.playwright-data/github` | ✅ 可用 |
| Provider-A (your-provider) | Playwright 抓取 | `~/.playwright-data/your-provider` | ✅ 可用 |
| OpenRouter VIP | API 暂不支持 | - | ⏳ |
| ZAI (智谱) | 无公开 API，不查询 | - | ⏭️ 跳过 |

## 查询方法详解

### 1. Provider-B

**方式**: Browser Tool 或 Playwright 抓取

**查询页面**: `https://ai.9w7.cn/console`

**登录状态**: `~/.playwright-data/<provider>/model`

**抓取数据**:
- 当前余额 (¥)
- 历史消耗 (¥)
- 请求次数
- 统计 Tokens
- 统计额度 (¥)
- 平均 RPM / TPM

**使用 Browser Tool 查询**:
1. 打开 `https://ai.9w7.cn/console`（openclaw browser 已保存登录状态）
2. 从页面 snapshot 中提取数据看板信息

### 2. GitHub Copilot Pro

**方式**: Playwright 抓取（需要先登录）

**查询页面**: `https://github.com/settings/copilot`

**登录流程**:
```python
from playwright.sync_api import sync_playwright
import os

user_data_dir = os.path.expanduser('~/.playwright-data/github')
os.makedirs(user_data_dir, exist_ok=True)

with sync_playwright() as p:
    context = p.chromium.launch_persistent_context(
        user_data_dir,
        headless=False,  # 显示浏览器让用户登录
    )
    page = context.pages[0] if context.pages else context.new_page()
    page.goto('https://github.com/settings/copilot')
    # 用户手动登录后，登录状态会保存到 user_data_dir
```

**抓取数据**:
- Premium requests 用量百分比
- 订阅状态 (Active/Inactive)

**正则匹配**:
```python
import re
usage_match = re.search(r'Premium requests\s*([\d.]+)%', text)
is_active = 'Copilot Pro is active' in text
```

### 3. Provider-A (your-provider)

**方式**: Playwright 抓取（需要先登录）

**查询页面**: `https://your-provider.example.com/console`

**登录流程**:
```python
user_data_dir = os.path.expanduser('~/.playwright-data/your-provider')
# 同上，使用 launch_persistent_context
```

**抓取数据**:
- 当前余额
- 历史消耗
- 请求次数
- 总 Tokens

**正则匹配**:
```python
balance_match = re.search(r'当前余额💰([\d.]+)', text)
consumed_match = re.search(r'历史消耗💰([\d.]+)', text)
requests_match = re.search(r'请求次数(\d+)', text)
tokens_match = re.search(r'总Tokens(\d+)', text)
```

## 使用方法

### 命令行

```bash
# 生成完整报告
python3 ~/clawd/skills/api-provider-status/balance_checker.py report

# 查询指定供应商
python3 ~/clawd/skills/api-provider-status/balance_checker.py query anapi
python3 ~/clawd/skills/api-provider-status/balance_checker.py query github-copilot
python3 ~/clawd/skills/api-provider-status/balance_checker.py query your-provider

# JSON 格式查询所有
python3 ~/clawd/skills/api-provider-status/balance_checker.py all
```

### 用量统计

```bash
# 最近 12 小时用量
python3 ~/clawd/skills/api-provider-status/usage_tracker.py report 12

# 最近 24 小时用量
python3 ~/clawd/skills/api-provider-status/usage_tracker.py report 24

# JSON 格式
python3 ~/clawd/skills/api-provider-status/usage_tracker.py stats 12
```

## 首次登录设置

如果 Playwright 登录状态过期，需要重新登录：

```python
# GitHub 登录
cd ~/clawd/skills/playwright-automation
python3 << 'EOF'
from playwright.sync_api import sync_playwright
import os

user_data_dir = os.path.expanduser('~/.playwright-data/github')
os.makedirs(user_data_dir, exist_ok=True)

with sync_playwright() as p:
    context = p.chromium.launch_persistent_context(
        user_data_dir, headless=False
    )
    page = context.pages[0] if context.pages else context.new_page()
    page.goto('https://github.com/login')
    input('登录完成后按 Enter...')
    context.close()
EOF

# Provider-A登录
python3 << 'EOF'
from playwright.sync_api import sync_playwright
import os

user_data_dir = os.path.expanduser('~/.playwright-data/your-provider')
os.makedirs(user_data_dir, exist_ok=True)

with sync_playwright() as p:
    context = p.chromium.launch_persistent_context(
        user_data_dir, headless=False
    )
    page = context.pages[0] if context.pages else context.new_page()
    page.goto('https://your-provider.example.com/')
    input('登录完成后按 Enter...')
    context.close()
EOF
```

## 定时任务

### OpenClaw 健康监控

**任务名**: OpenClaw 健康监控
**模型**: <provider>/glm-4.7
**频率**: 每天 2:00, 8:00, 14:00, 20:00 (每6小时)
**功能**:
- 检查 OpenClaw 系统状态
- 查询 Provider-B 和 your-provider 余额
- 生成健康报告推送到 Telegram
- 异常时发送 ⚠️ 告警

## 文件结构

```
skills/api-provider-status/
├── SKILL.md              # 本文档
├── balance_checker.py    # 余额查询脚本
└── usage_tracker.py      # 用量统计脚本（从 OpenClaw 日志读取）
```

## 登录状态存储

```
~/.playwright-data/
├── <provider>/model                 # Provider-B 登录状态
├── github/               # GitHub 登录状态
└── your-provider/         # Provider-A登录状态
```

## OpenClaw 系统数据 (2026-02-07)

**系统状态**: ✅ Gateway 运行中 | 11 Agents | 7 活跃会话

**通道**: Telegram ✅ | WhatsApp ✅

**API 供应商**:
| 供应商 | 余额 | 状态 |
|--------|------|------|
| Provider-B | ¥321.83 | ✅ 正常 |
| your-provider | ¥41.79 | ⚠️ 偏低 |
| GitHub Copilot | 免费额度 | ✅ 可用 |
| ZAI (智谱) | - | ✅ 可用 |
| OpenRouter VIP | - | ✅ 可用 |
