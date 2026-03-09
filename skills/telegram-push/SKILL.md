# Telegram Push Skill

通过独立的 Telegram Bot 推送消息到群聊或私聊，不依赖 OpenClaw 的 telegram channel 配置。

## Bot 配置

| Bot | Username | Token路径 | 用途 |
|-----|----------|----------|------|
| NewsRobot | @fkkanfnnfbot | `pass show tokens/telegram-newsrobot` | DailyNews群信息推送 |
| 主Bot | @DanielLi_smartest_Bot | OpenClaw内置 | 私聊交互 |

## 推送目标

| 群/对象 | Chat ID | 推送Bot | 说明 |
|---------|---------|---------|------|
| DailyNews群 | `YOUR_NEWS_CHAT_ID` | NewsRobot | 新闻、skill收集、学习报告等 |
| Daniel私聊 | `YOUR_TELEGRAM_ID` | 主Bot (message tool) | 告警、私人通知 |

## 推送规则

**核心原则：DailyNews群的所有推送必须通过 NewsRobot，不要用 message tool。**

| Cron任务 | 推送目标 | 推送方式 | 说明 |
|----------|---------|---------|------|
| 科技日报推送 | DailyNews群 | `news_push.py`（内置NewsRobot） | 8:00/13:00/19:00 |
| 小a skill收集 | DailyNews群 | `newsbot_send.py` | 每小时 |
| 小a 夜间自我学习 | DailyNews群 + Daniel私聊 | DailyNews用`newsbot_send.py`，私聊用`message tool` | 1:00-6:30每30min，06:30推总报告 |
| 小a团队日报总结 | Daniel私聊 | message tool | 23:00 |
| API用量与余额统计 | Daniel私聊 | announce/message tool | 2/8/14/20点 |
| A股基金实时监控 | Daniel私聊 | announce/message tool | 工作日10/13/15点 |
| 医疗企业融资监控 | Daniel私聊 | announce/message tool | 每天9:00 |

## 推送脚本

### 1. newsbot_send.py（推荐）

通用的NewsRobot推送脚本，所有往DailyNews群的推送都应该用这个：

```bash
# 直接传参
python3 ~/clawd/scripts/newsbot_send.py "消息内容"

# 管道传入
echo "消息内容" | python3 ~/clawd/scripts/newsbot_send.py
```

路径: `~/clawd/scripts/newsbot_send.py`

### 2. news_push.py

科技新闻专用脚本，内置新闻抓取 + NewsRobot推送：

```bash
python3 ~/clawd/scripts/news_push.py
```

路径: `~/clawd/scripts/news_push.py`

### 3. Shell快捷方式

```bash
# 快速推送到DailyNews群
~/clawd/skills/telegram-push/telegram-push.sh "消息内容"
```

### 4. Python直接调用

```python
import subprocess
def push_to_dailynews(text):
    subprocess.run(['python3', '/home/aa/clawd/scripts/newsbot_send.py', text])
```

## Telegram API 参考

### 发送文本
```bash
TOKEN=$(pass show tokens/telegram-newsrobot)
curl -s -X POST "https://api.telegram.org/bot${TOKEN}/sendMessage" \
  -H "Content-Type: application/json" \
  -d '{"chat_id": YOUR_NEWS_CHAT_ID, "text": "消息", "parse_mode": "HTML"}'
```

### 发送图片
```bash
curl -s -X POST "https://api.telegram.org/bot${TOKEN}/sendPhoto" \
  -H "Content-Type: application/json" \
  -d '{"chat_id": YOUR_NEWS_CHAT_ID, "photo": "URL", "caption": "说明"}'
```

### 发送带按钮的消息
```bash
curl -s -X POST "https://api.telegram.org/bot${TOKEN}/sendMessage" \
  -H "Content-Type: application/json" \
  -d '{
    "chat_id": YOUR_NEWS_CHAT_ID,
    "text": "消息",
    "reply_markup": {"inline_keyboard": [[{"text": "按钮", "url": "https://..."}]]}
  }'
```

## 添加新群组

1. 把 @fkkanfnnfbot 拉入目标群
2. 在群里发一条消息
3. 获取 chat_id:
   ```bash
   curl -s "https://api.telegram.org/bot$(pass show tokens/telegram-newsrobot)/getUpdates" | python3 -c "import json,sys; d=json.load(sys.stdin); [print(r['message']['chat']) for r in d.get('result',[]) if 'message' in r]"
   ```
4. 更新本文档的推送目标表格
5. 如需新脚本，参考 `newsbot_send.py` 修改 `CHAT_ID`

## 注意事项

- 超级群的 chat_id 以 `-100` 开头
- 发送频率限制：同一群每分钟约 20 条
- HTML parse_mode 支持: `<b>`, `<i>`, `<code>`, `<pre>`, `<a href="">`
- **密钥永不硬编码**，统一用 `pass show tokens/telegram-newsrobot`

## 错误处理

| 错误 | 原因 | 解决方案 |
|------|------|----------|
| chat not found | Bot未加入群 | 把bot拉入群 |
| 429 Too Many Requests | 发送太频繁 | 等待retry_after秒后重试 |
| bot was blocked | 用户屏蔽了bot | 需用户解除屏蔽 |
| Unauthorized | Token无效 | 检查 `pass show tokens/telegram-newsrobot` |
