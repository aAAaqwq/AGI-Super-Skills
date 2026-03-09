#!/usr/bin/env python3
"""
人工介入提醒模块
当 AI 无法回答时，通知人工客服
"""

import os
import sys
from pathlib import Path
from datetime import datetime
import logging
import json

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    import requests
    from psycopg2 import extensions
except ImportError as e:
    print(f"❌ 缺少依赖: {e}")
    sys.exit(1)


# 日志配置
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class NotificationChannel:
    """通知渠道"""

    def __init__(self):
        self.channel_config = os.environ.get("NOTIFICATION_CHANNEL", "telegram:YOUR_TELEGRAM_ID")

    def parse_channel(self) -> tuple:
        """解析渠道配置: "telegram:YOUR_TELEGRAM_ID" -> ("telegram", "YOUR_TELEGRAM_ID")"""
        parts = self.channel_config.split(":")
        if len(parts) != 2:
            logger.error(f"无效的渠道配置: {self.channel_config}")
            return None, None
        return parts[0], parts[1]

    def send(self, message: str) -> bool:
        """发送通知"""
        channel, target = self.parse_channel()

        if not channel:
            return False

        if channel == "telegram":
            return self._send_telegram(target, message)
        elif channel == "feishu":
            return self._send_feishu(target, message)
        else:
            logger.error(f"不支持的渠道: {channel}")
            return False

    def _send_telegram(self, chat_id: str, message: str) -> bool:
        """发送 Telegram 通知"""
        token = os.environ.get("TELEGRAM_BOT_TOKEN")

        if not token:
            logger.error("缺少 TELEGRAM_BOT_TOKEN")
            return False

        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": message,
            "parse_mode": "Markdown"
        }

        try:
            resp = requests.post(url, json=payload, timeout=10)
            data = resp.json()

            if data.get("ok"):
                logger.info("✓ Telegram 通知发送成功")
                return True
            else:
                logger.error(f"✗ Telegram 通知失败: {data}")
                return False

        except Exception as e:
            logger.error(f"✗ Telegram 通知异常: {e}")
            return False

    def _send_feishu(self, webhook_url: str, message: str) -> bool:
        """发送飞书通知"""
        payload = {
            "msg_type": "text",
            "content": {"text": message}
        }

        try:
            resp = requests.post(webhook_url, json=payload, timeout=10)

            if resp.status_code == 200:
                logger.info("✓ 飞书通知发送成功")
                return True
            else:
                logger.error(f"✗ 飞书通知失败: {resp.text}")
                return False

        except Exception as e:
            logger.error(f"✗ 飞书通知异常: {e}")
            return False


class Database:
    """数据库操作"""

    def __init__(self):
        self.db_url = os.environ.get("KB_DB_URL", "postgresql://postgres@localhost/wecom_kb")

    def save_unknown_question(self, user_id: str, user_name: str, question: str, context: dict = None):
        """保存未解决的问题"""
        conn = extensions.connect(self.db_url)
        cur = conn.cursor()

        try:
            cur.execute("""
                INSERT INTO unknown_questions (user_id, user_name, question, conversation_context)
                VALUES (%s, %s, %s, %s)
            """, (user_id, user_name, question, json.dumps(context or {})))

            conn.commit()
            logger.info("✓ 已记录未解决问题")
            return True

        except Exception as e:
            logger.error(f"✗ 保存未解决问题失败: {e}")
            conn.rollback()
            return False
        finally:
            cur.close()
            conn.close()

    def log_escalation(self, user_id: str, user_name: str, question: str, reason: str = "低置信度"):
        """记录人工介入日志"""
        conn = extensions.connect(self.db_url)
        cur = conn.cursor()

        try:
            cur.execute("""
                INSERT INTO escalation_log (user_id, user_name, reason, question, notified)
                VALUES (%s, %s, %s, %s, %s)
            """, (user_id, user_name, reason, question, True))

            conn.commit()
            logger.info("✓ 已记录介入日志")
            return True

        except Exception as e:
            logger.error(f"✗ 记录介入日志失败: {e}")
            conn.rollback()
            return False
        finally:
            cur.close()
            conn.close()


def escalate_to_human(
    user_id: str,
    user_name: str,
    question: str,
    context: dict = None
) -> bool:
    """
    转接人工客服

    Returns:
        bool: 是否成功
    """

    logger.info(f"🚨 转人工: {user_name} ({user_id})")

    # 初始化组件
    notifier = NotificationChannel()
    db = Database()

    # 1. 构建通知消息
    notification = f"""🚨 *需要人工介入*

👤 用户：{user_name}
🆔 ID: {user_id}
❓ 问题：{question}
⏰ 时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

请及时处理，避免用户等待过久。

---
由企业微信客服 AI 助手自动推送"""

    # 2. 发送通知
    notified = notifier.send(notification)

    # 3. 记录到数据库
    db.save_unknown_question(user_id, user_name, question, context)
    db.log_escalation(user_id, user_name, question, "低置信度")

    return notified


def get_escalation_stats() -> dict:
    """获取人工介入统计"""
    db_url = os.environ.get("KB_DB_URL", "postgresql://postgres@localhost/wecom_kb")
    conn = extensions.connect(db_url)
    cur = conn.cursor()

    try:
        # 今日介入次数
        cur.execute("""
            SELECT COUNT(*)
            FROM escalation_log
            WHERE DATE(created_at) = CURRENT_DATE
        """)
        today_count = cur.fetchone()[0]

        # 未解决问题 Top 5
        cur.execute("""
            SELECT question, COUNT(*) as count
            FROM unknown_questions
            WHERE created_at > NOW() - INTERVAL '7 days'
            GROUP BY question
            ORDER BY count DESC
            LIMIT 5
        """)
        top_questions = [(row[0][:30] + "...", row[1]) for row in cur.fetchall()]

        return {
            "today_escalations": today_count,
            "top_questions": top_questions
        }

    except Exception as e:
        logger.error(f"获取统计失败: {e}")
        return {}
    finally:
        cur.close()
        conn.close()


# 测试入口
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="测试人工介入流程")
    parser.add_argument("--user-id", required=True, help="外部用户 ID")
    parser.add_argument("--name", default="测试用户", help="用户姓名")
    parser.add_argument("--question", required=True, help="用户问题")
    parser.add_argument("--stats", action="store_true", help="显示统计信息")

    args = parser.parse_args()

    if args.stats:
        stats = get_escalation_stats()
        print(f"\n📊 今日介入次数: {stats.get('today_escalations', 0)}")
        print("\n🔝 Top 未解决问题:")
        for q, c in stats.get('top_questions', []):
            print(f"   {c}x - {q}")
    else:
        # 执行转人工
        result = escalate_to_human(
            user_id=args.user_id,
            user_name=args.name,
            question=args.question
        )

        print(f"\n{'✅' if result else '❌'} 转人工{'成功' if result else '失败'}")
