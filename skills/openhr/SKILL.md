---
name: openhr
description: Boss直聘全流程AI自动化招聘智能体。自动登录、筛选候选人、个性化打招呼、智能聊天跟进、简历解析、飞书同步。触发词：启动招聘、自动打招呼、boss greet、openhr、简历解析、上传飞书。
license: MIT
metadata:
  author: 小code
  version: "1.0"
read_when:
  - User mentions "openhr" or "招聘" or "boss" or "打招呼"
  - User says "打招呼" or "启动招聘" in recruitment context
  - User wants to start automated recruiting or check recruiting progress
  - User wants to parse resumes or upload to Feishu
triggers:
  - openhr
  - openhr start
  - openhr greet
  - openhr candidates
  - openhr chat
  - openhr monitor
  - openhr status
  - openhr resume
  - openhr feishu
  - boss greet
  - boss login
  - 启动招聘
  - 自动打招呼
  - 打招呼
  - 查看候选人
  - 启动聊天引擎
  - 招聘监控
  - 登录Boss
  - 查看招聘进度
  - 简历解析
  - 上传飞书
---

# OpenHR — Boss直聘自动化招聘智能体

> 6 大模块全部通过验收 ✅
> 项目路径：`~/clawd/projects/openhr/`

---

## ⚠️ 安全警告（必读）

1. **Boss 直聘有严格反爬虫机制**，所有操作间隔必须 ≥ 5 秒
2. **每日打招呼上限 100 次**（Boss 官方产品限制，不可突破）
3. **验证码出现时必须暂停**，等人工处理完成后再继续
4. **封号风险提示**：频繁操作、异常行为可能触发风控导致封号
5. **必须使用 headed 浏览器**（有界面，会弹窗），不能 headless
6. **首次使用需要人工扫码登录**
7. **建议先用 `--dry-run` 测试，确认无误后再正式运行**

---

## 路由表

| 触发词 | 子模块 | 执行脚本 | 说明 |
|--------|--------|----------|------|
| 登录Boss / boss login | boss-login | `scripts/boss_login.py` | 扫码登录 + Cookie 持久化 |
| 自动打招呼 / openhr greet / boss greet / 打招呼 | boss-greet | `scripts/boss_greet.py` | 遍历筛选 + 个性化打招呼 |
| 启动聊天引擎 / openhr chat | chat-engine | `scripts/chat_engine.py` | 监控回复 + LLM 智能跟进 |
| 简历解析 / openhr resume | resume-parser | `scripts/resume_parser.py` | 提取简历信息 |
| 上传飞书 / openhr feishu | resume-parser | `scripts/feishu_upload.py` | 写入飞书多维表格 |
| 查看候选人 / openhr candidates | boss-greet | `scripts/boss_greet.py --list` | 列出已筛选候选人 |
| 招聘监控 / openhr monitor | chat-engine | `scripts/chat_engine.py --monitor` | 持续监控聊天消息 |
| 查看招聘进度 / openhr status | — | 直接读取状态 | 汇总 greet_count.json + chat_logs |
| 启动招聘 | boss-greet | `scripts/boss_greet.py` | 完整招聘流程入口 |

---

## 模块一览

| 模块 | 脚本 | 用途 |
|------|------|------|
| 登录 | `scripts/boss_login.py` | 扫码登录 + Cookie 持久化 |
| 风控 | `scripts/anti_detect.py` | 随机间隔 + 验证码检测 + 封号预警 |
| 打招呼 | `scripts/boss_greet.py` | 自动筛选 + 个性化打招呼 |
| 聊天 | `scripts/chat_engine.py` | 监控回复 + LLM 智能跟进 |
| 简历 | `scripts/resume_parser.py` | 简历信息提取 |
| 飞书 | `scripts/feishu_upload.py` | 飞书多维表格写入 |
| 知识库 | `scripts/knowledge_base.py` | 话术 + 岗位需求管理 |

---

## 快速开始

### 第一步：登录 Boss 直聘

```bash
cd ~/clawd/projects/openhr
python scripts/boss_login.py
```

- 首次运行会弹出浏览器二维码
- 用 Boss 直聘 APP 扫码确认登录
- Cookie 自动持久化到 `data/cookies/boss_cookies.json`
- 后续运行无需重复登录（Cookie 过期需重新扫码）

### 第二步：Dry-run 测试（强烈建议）

```bash
cd ~/clawd/projects/openhr
python scripts/boss_greet.py --dry-run
```

- 只筛选候选人，**不发送任何消息**
- 预览打招呼话术，确认无误后再正式运行
- 查看 `data/logs/dry_run.json` 了解模拟结果

### 第三步：正式打招呼

```bash
cd ~/clawd/projects/openhr
python scripts/boss_greet.py
```

- 默认每日上限 100 次（自动遵守 Boss 限制）
- 所有操作间隔 5-15 秒随机（内置风控保护）
- 运行日志实时输出，可随时 Ctrl+C 中断

### 第四步：启动聊天引擎

```bash
cd ~/clawd/projects/openhr
python scripts/chat_engine.py
```

- 监控新消息，LLM 生成智能回复
- 支持多种聊天模式（主动跟进、被动响应、催入职等）
- 聊天记录存入 `data/chat_logs/`

---

## 查看招聘进度

```bash
# 直接读取状态文件
cat ~/clawd/projects/openhr/data/greet_count.json

# 或运行 status 命令
cd ~/clawd/projects/openhr
python -c "
import json, os
gc = json.load(open('data/greet_count.json'))
print(f'打招呼总数: {gc.get(\"total\",0)}')
print(f'今日打招呼: {gc.get(\"today\",0)}')
print(f'昨日打招呼: {gc.get(\"yesterday\",0)}')
logs = sorted([f for f in os.listdir('data/chat_logs') if f.endswith('.json')])
print(f'聊天记录数: {len(logs)}')
"
```

---

## 简历解析 + 飞书同步

```bash
# 解析简历（支持 PDF、DOCX、图片）
cd ~/clawd/projects/openhr
python scripts/resume_parser.py <简历文件路径>

# 上传解析结果到飞书多维表格
python scripts/feishu_upload.py <简历文件路径>
```

飞书配置：`config/feishu.json`（需填写 app_id、table_id）

---

## 配置文件

| 文件 | 说明 |
|------|------|
| `config/anti_detect.json` | 风控参数（间隔、验证码检测规则） |
| `config/feishu.json` | 飞书多维表格配置（app_id、table_id、fields） |
| `config/templates.json` | 打招呼话术模板（8 个场景） |
| `config/llm.json` | LLM 模型配置（provider、model、api_key） |
| `data/knowledge/` | 岗位需求、话术库、聊天模式、反馈模板 |

---

## 子模块详细文档

- [boss-login](file://~/clawd/projects/openhr/skills/boss-login/SKILL.md)
- [anti-detect](file://~/clawd/projects/openhr/skills/anti-detect/SKILL.md)
- [boss-greet](file://~/clawd/projects/openhr/skills/boss-greet/SKILL.md)
- [chat-engine](file://~/clawd/projects/openhr/skills/chat-engine/SKILL.md)
- [resume-parser](file://~/clawd/projects/openhr/skills/resume-parser/SKILL.md)
- [knowledge-base](file://~/clawd/projects/openhr/skills/knowledge-base/SKILL.md)

---

## 执行命令速查

```bash
cd ~/clawd/projects/openhr

# 登录
python scripts/boss_login.py

# 打招呼（测试）
python scripts/boss_greet.py --dry-run

# 打招呼（正式）
python scripts/boss_greet.py

# 列出候选人
python scripts/boss_greet.py --list

# 聊天引擎
python scripts/chat_engine.py

# 聊天监控
python scripts/chat_engine.py --monitor

# 简历解析
python scripts/resume_parser.py path/to/resume.pdf

# 飞书上传统一简历
python scripts/feishu_upload.py path/to/resume.pdf
```
