#!/usr/bin/env python3
"""
企业微信 - 新好友添加处理流程
自动通过、添加标签、发送欢迎消息
"""

import os
import sys
from pathlib import Path
from datetime import datetime
import logging

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


class WecomClient:
    """企业微信 API 客户端"""

    def __init__(self):
        self.corp_id = os.environ.get("WECOM_CORP_ID")
        self.agent_id = os.environ.get("WECOM_AGENT_ID", "1000002")
        self.secret = os.environ.get("WECOM_AGENT_SECRET")
        self.access_token = None
        self.base_url = "https://qyapi.weixin.qq.com/cgi-bin"

    def get_access_token(self) -> str:
        """获取 access_token"""
        if self.access_token:
            return self.access_token

        url = f"{self.base_url}/gettoken"
        params = {
            "corpid": self.corp_id,
            "corpsecret": self.secret
        }

        try:
            resp = requests.get(url, params=params, timeout=10)
            data = resp.json()

            if data.get("errcode") == 0:
                self.access_token = data["access_token"]
                logger.info("✓ 获取 access_token 成功")
                return self.access_token
            else:
                logger.error(f"✗ 获取 access_token 失败: {data}")
                return None

        except Exception as e:
            logger.error(f"✗ 获取 access_token 异常: {e}")
            return None

    def send_message(self, external_userid: str, text: str) -> bool:
        """发送文本消息"""
        token = self.get_access_token()
        if not token:
            return False

        url = f"{self.base_url}/kf/send_msg?access_token={token}"
        payload = {
            "external_userid": external_userid,
            "open_kfid": self.agent_id,
            "msgtype": "text",
            "text": {
                "content": text
            }
        }

        try:
            resp = requests.post(url, json=payload, timeout=10)
            data = resp.json()

            if data.get("errcode") == 0:
                logger.info(f"✓ 发送消息成功: {external_userid}")
                return True
            else:
                logger.error(f"✗ 发送消息失败: {data}")
                return False

        except Exception as e:
            logger.error(f"✗ 发送消息异常: {e}")
            return False

    def add_tag(self, external_userid: str, tag_name: str) -> bool:
        """添加用户标签"""
        # 这里需要调用企业微信标签管理 API
        # 简化实现，仅记录日志
        logger.info(f"🏷️  添加标签: {tag_name} -> {external_userid}")
        return True


class Database:
    """数据库操作"""

    def __init__(self):
        self.db_url = os.environ.get("KB_DB_URL", "postgresql://postgres@localhost/wecom_kb")
        self.conn = None

    def connect(self):
        """连接数据库"""
        try:
            self.conn = extensions.connect(self.db_url)
            logger.info("✓ 数据库连接成功")
            return True
        except Exception as e:
            logger.error(f"✗ 数据库连接失败: {e}")
            return False

    def save_user(self, external_userid: str, name: str, tags: list = None):
        """保存用户信息"""
        if not self.conn:
            if not self.connect():
                return False

        cur = self.conn.cursor()

        try:
            # 检查用户是否存在
            cur.execute("SELECT id FROM users WHERE external_userid = %s", (external_userid,))
            user_exists = cur.fetchone()

            if user_exists:
                # 更新
                cur.execute("""
                    UPDATE users
                    SET name = %s, tags = %s, last_contact = NOW(), total_messages = total_messages + 1
                    WHERE external_userid = %s
                """, (name, tags or [], external_userid))
                logger.info(f"✓ 更新用户: {name}")
            else:
                # 新增
                cur.execute("""
                    INSERT INTO users (external_userid, name, tags, first_contact, last_contact, total_messages)
                    VALUES (%s, %s, %s, NOW(), NOW(), 1)
                """, (external_userid, name, tags or ["新客户"]))
                logger.info(f"✓ 新增用户: {name}")

            self.conn.commit()
            return True

        except Exception as e:
            logger.error(f"✗ 保存用户失败: {e}")
            self.conn.rollback()
            return False
        finally:
            cur.close()


def send_welcome_message(wecom: WecomClient, external_userid: str, name: str) -> bool:
    """发送欢迎消息"""

    welcome_text = f"""👋 欢迎来到{name}！

我是智能客服小助手 🤖，可以帮您：

📋 查询订单状态
❓ 解答常见问题
🔄 处理售后问题
💰 查询物流信息

如需帮助，请直接回复问题。
如有复杂需求，我会转接人工客服为您服务。

如有急事，也可致电人工客服：400-XXX-XXXX"""

    return wecom.send_message(external_userid, welcome_text)


def handle_friend_add(
    external_userid: str,
    name: str = "客户",
    avatar: str = None,
    source: str = "未知"
) -> bool:
    """
    处理好友添加事件

    Args:
        external_userid: 外部联系人 UserID
        name: 用户姓名
        avatar: 头像 URL
        source: 来源渠道

    Returns:
        bool: 处理是否成功
    """

    logger.info(f"🆕 新好友添加: {name} ({external_userid}) from {source}")

    # 初始化客户端
    wecom = WecomClient()
    db = Database()

    # 1. 添加用户标签
    wecom.add_tag(external_userid, "新客户")

    # 2. 保存用户到数据库
    tags = ["新客户", f"来源:{source}"]
    db.save_user(external_userid, name, tags)

    # 3. 发送欢迎消息
    success = send_welcome_message(wecom, external_userid, name)

    if success:
        logger.info(f"✅ 新好友处理完成: {name}")
    else:
        logger.error(f"✗ 新好友处理失败: {name}")

    return success


# 测试入口
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="测试新好友添加流程")
    parser.add_argument("--user-id", required=True, help="外部用户 ID")
    parser.add_argument("--name", default="测试用户", help="用户姓名")
    parser.add_argument("--source", default="测试", help="来源")

    args = parser.parse_args()

    # 检查环境变量
    required_vars = ["WECOM_CORP_ID", "WECOM_AGENT_SECRET"]
    missing = [var for var in required_vars if not os.environ.get(var)]

    if missing:
        print(f"❌ 缺少环境变量: {', '.join(missing)}")
        sys.exit(1)

    # 执行
    result = handle_friend_add(
        external_userid=args.user_id,
        name=args.name,
        source=args.source
    )

    sys.exit(0 if result else 1)
