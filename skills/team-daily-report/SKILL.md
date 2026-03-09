# 小a团队日报 Skill

每日自动生成并推送团队日报，汇总当天所有agent工作、cron执行、skill进度、关键事件。

## 触发方式

- Cron: 每天 23:00 自动执行
- 手动: `python3 ~/clawd/scripts/team_daily_report.py`

## 推送渠道

| 目标 | 方式 | Bot |
|------|------|-----|
| DailyNews群 (YOUR_NEWS_CHAT_ID) | 脚本内置 sendPhoto + sendText | NewsRobot (@fkkanfnnfbot) |
| Daniel私聊 (YOUR_TELEGRAM_ID) | cron agent 用 message tool | 主Bot |

## 执行流程

### 步骤1: Dump当日cron状态

cron agent 用 `cron(action='list')` 获取所有job，筛选今天执行过的，写入：

```
~/clawd/config/cron-status-today.json
```

格式：
```json
[
  {"name": "任务名", "status": "ok", "time": "HH:MM", "dur": 秒数},
  ...
]
```

提取逻辑：遍历每个job的 `state.lastRunAtMs`，转为日期，匹配今天的，提取 name/lastStatus/time/lastDurationMs。

### 步骤2: 运行日报脚本

```bash
python3 ~/clawd/scripts/team_daily_report.py
```

脚本自动完成：
1. 读取数据源（见下方）
2. 生成文字报告
3. 通过NewsRobot推送封面图+文字到DailyNews群
4. 保存到 `~/clawd/reports/daily/team-report-{date}.txt`

### 步骤3: 发送到Daniel私聊

cron agent 读取生成的 txt 文件，用 message tool 发送给 Daniel。

## 数据源

| 数据 | 来源 | 变化频率 |
|------|------|---------|
| Cron执行记录 | `~/clawd/config/cron-status-today.json` | 每日dump |
| Skill装备进度 | `~/clawd/config/agent-learning-progress.json` | 每小时（skill收集cron更新） |
| 今日亮点 | `~/clawd/memory/{YYYY-MM-DD}.md` | 全天累积 |
| 学习记录数 | `~/clawd/memory/learning-log.md` | 夜间学习cron更新 |
| 天气 | wttr.in/Shanghai API | 实时 |
| 封面图 | `~/clawd/assets/daily-report-covers/` | 按日期轮换 |

## 报告格式

```
🤖 小a团队日报 | 2026-02-11 周三
📍 上海 12°C Partly Cloudy · 封面: 莱依拉
━━━━━━━━━━━━━━━━━━━━

📊 今日概览
  成员 15 · 任务 10 · 成功 9 · 失败 1
  Skill 59/475 (12%) · 学习 1
  ██░░░░░░░░░░░░░░░░░░ 12%

👥 各Agent今日状态

🟣 claude-opus-4-6
  📊 数据分析师 █░░░░░░░ 3/31
  ⚖️ 法务顾问 █░░░░░░░ 5/32
  ...

🔵 glm-4.7
  📋 项目经理 █░░░░░░░ 3/32
  ...

🟢 kimi-k2.5
  💼 销售专家 ██░░░░░░ 8/33
  ...

🟡 gemini-3-pro
  🎧 客服专家 █░░░░░░░ 5/32
  ...

⚡ Cron执行记录
  06:29 ✅ 小a 夜间自我学习 (303s)
  09:01 ✅ 医疗企业融资监控 (72s)
  ...

💡 今日亮点
  · 亮点1
  · 亮点2

━━━━━━━━━━━━━━━━━━━━
⏰ 23:00 · v2.3
```

## 封面轮换规则

12张原神cosplay封面，按 `day_of_year % 12` 轮换：

| 序号 | 角色 | 文件 |
|------|------|------|
| 0 | 神里绫华 | ayaka.jpeg |
| 1 | 芭芭拉 | barbara.jpeg |
| 2 | 哥伦比娅 | colombina.jpeg |
| 3 | 甘雨 | ganyu.jpeg |
| 4 | 胡桃 | hutao.jpeg |
| 5 | 刻晴 | keqing.jpeg |
| 6 | 莱依拉 ||
| 7 | 丽莎 | lisa.jpeg |
| 8 | 琳妮特 | lynette.jpeg |
| 9 | 纳西妲 | nahida.jpeg |
| 10 | 雷电将军 | raiden.jpeg |
| 11 | 宵宫 | yoimiya.jpeg |

## 15个Agent配置

| Agent | 模型 | Emoji |
|-------|------|-------|
| sales | kimi-k2.5 | 💼 |
| support | gemini-3-pro | 🎧 |
| data | claude-opus-4-6 | 📊 |
| pm | glm-4.7 | 📋 |
| crm | kimi-k2.5 | 🤝 |
| finance | glm-4.7 | 💰 |
| legal | claude-opus-4-6 | ⚖️ |
| marketing | kimi-k2.5 | 🚀 |
| product | glm-4.7 | 🎯 |
| research | claude-opus-4-6 | 🔬 |
| ops | glm-4.7 | 🔧 |
| content | kimi-k2.5 | ✍️ |
| knowledge | gemini-3-pro | 📚 |
| news | kimi-k2.5 | 📰 |
| healthcare-monitor | claude-opus-4-6 | 🏥 |

## 关键文件

| 文件 | 用途 |
|------|------|
| `~/clawd/scripts/team_daily_report.py` | 日报生成+推送脚本 |
| `~/clawd/scripts/newsbot_send.py` | NewsRobot通用推送 |
| `~/clawd/config/cron-status-today.json` | 当日cron执行状态 |
| `~/clawd/config/agent-learning-progress.json` | Skill装备进度 |
| `~/clawd/config/agent-skills-map.json` | Agent-Skill映射 |
| `~/clawd/memory/learning-log.md` | 学习日志 |
| `~/clawd/assets/daily-report-covers/` | 12张cosplay封面 |
| `~/clawd/reports/daily/` | 历史日报存档 |

## Telegram限制

- sendPhoto caption: 最大1024字符
- sendMessage text: 最大4096字符
- 策略: 封面图用短caption，详细报告作为reply消息发送

## 注意事项

- NewsRobot token: `pass show tokens/telegram-newsrobot`
- 密钥永不硬编码
- 天气API偶尔超时，显示N/A不影响整体
- cron-status-today.json 必须在脚本运行前由agent dump，否则cron记录为空
