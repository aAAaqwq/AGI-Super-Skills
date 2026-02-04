#!/usr/bin/env python3
"""
飞书多租户 API 工具包
支持：个人应用 + 汉兴企业应用
"""

import os
import json
import time
import requests
from typing import Optional, Dict, Any, List

# ==================== 租户配置 ====================

TENANTS = {
    "personal": {
        "name": "个人应用",
        "app_id": "cli_a83467f9ecba5013",
        "app_secret": "bX21pNOyAXHwFXWf0SVGphWQrqrgC5Gd",
        "default_chat": "oc_356d77ff689d91280b4d33befb0eccb8",  # 知识云文档
    },
    "hanxing": {
        "name": "汉兴企业",
        "app_id": "cli_a9f758c0efa2dcc4",
        "app_secret": "5djHWjk8t6QHRquDJXG9JiNEgPynmnIN",
        "default_chat": "oc_e92f9edcb7d078c9853d09ce844c15af",  # 技术开发群
    }
}

DEFAULT_TENANT = "hanxing"  # 默认使用汉兴企业

class FeishuClient:
    """飞书 API 客户端"""
    
    BASE_URL = "https://open.feishu.cn/open-apis"
    
    def __init__(self, tenant: str = None):
        tenant = tenant or DEFAULT_TENANT
        if tenant not in TENANTS:
            raise ValueError(f"未知租户: {tenant}，可选: {list(TENANTS.keys())}")
        
        config = TENANTS[tenant]
        self.tenant_name = config["name"]
        self.app_id = config["app_id"]
        self.app_secret = config["app_secret"]
        self.default_chat = config.get("default_chat")
        self._token = None
        self._token_expires = 0
    
    @property
    def token(self) -> str:
        """获取 tenant_access_token（自动刷新）"""
        if self._token and time.time() < self._token_expires - 60:
            return self._token
        
        resp = requests.post(
            f"{self.BASE_URL}/auth/v3/tenant_access_token/internal",
            json={"app_id": self.app_id, "app_secret": self.app_secret}
        )
        data = resp.json()
        if data.get("code") != 0:
            raise Exception(f"获取 token 失败: {data}")
        
        self._token = data["tenant_access_token"]
        self._token_expires = time.time() + data["expire"]
        return self._token
    
    def _request(self, method: str, endpoint: str, **kwargs) -> Dict:
        """发送 API 请求"""
        headers = kwargs.pop("headers", {})
        headers["Authorization"] = f"Bearer {self.token}"
        headers.setdefault("Content-Type", "application/json")
        
        url = f"{self.BASE_URL}{endpoint}"
        resp = requests.request(method, url, headers=headers, **kwargs)
        return resp.json()
    
    # ==================== 消息 API ====================
    
    def send_message(
        self,
        receive_id: str,
        content: str,
        msg_type: str = "text",
        receive_id_type: str = "open_id"
    ) -> Dict:
        """发送消息"""
        return self._request(
            "POST",
            f"/im/v1/messages?receive_id_type={receive_id_type}",
            json={
                "receive_id": receive_id,
                "msg_type": msg_type,
                "content": content
            }
        )
    
    def send_text(self, receive_id: str, text: str, receive_id_type: str = "open_id") -> Dict:
        """发送文本消息"""
        return self.send_message(
            receive_id,
            json.dumps({"text": text}),
            "text",
            receive_id_type
        )
    
    def send_card(self, receive_id: str, card: Dict, receive_id_type: str = "open_id") -> Dict:
        """发送卡片消息"""
        return self.send_message(
            receive_id,
            json.dumps(card),
            "interactive",
            receive_id_type
        )
    
    # ==================== 群组 API ====================
    
    def list_chats(self, page_size: int = 50) -> Dict:
        """获取群组列表"""
        return self._request("GET", f"/im/v1/chats?page_size={page_size}")
    
    def get_chat(self, chat_id: str) -> Dict:
        """获取群组信息"""
        return self._request("GET", f"/im/v1/chats/{chat_id}")
    
    def create_chat(self, name: str, user_ids: List[str] = None) -> Dict:
        """创建群组"""
        data = {"name": name}
        if user_ids:
            data["user_id_list"] = user_ids
        return self._request("POST", "/im/v1/chats", json=data)
    
    # ==================== 多维表格 API ====================
    
    def list_bitable_tables(self, app_token: str) -> Dict:
        """获取多维表格的数据表列表"""
        return self._request("GET", f"/bitable/v1/apps/{app_token}/tables")
    
    def get_bitable_records(
        self,
        app_token: str,
        table_id: str,
        page_size: int = 20,
        filter_str: str = None
    ) -> Dict:
        """获取多维表格记录"""
        params = f"page_size={page_size}"
        if filter_str:
            params += f"&filter={filter_str}"
        return self._request("GET", f"/bitable/v1/apps/{app_token}/tables/{table_id}/records?{params}")
    
    def add_bitable_record(self, app_token: str, table_id: str, fields: Dict) -> Dict:
        """添加多维表格记录"""
        return self._request(
            "POST",
            f"/bitable/v1/apps/{app_token}/tables/{table_id}/records",
            json={"fields": fields}
        )
    
    def update_bitable_record(
        self,
        app_token: str,
        table_id: str,
        record_id: str,
        fields: Dict
    ) -> Dict:
        """更新多维表格记录"""
        return self._request(
            "PUT",
            f"/bitable/v1/apps/{app_token}/tables/{table_id}/records/{record_id}",
            json={"fields": fields}
        )
    
    def delete_bitable_record(self, app_token: str, table_id: str, record_id: str) -> Dict:
        """删除多维表格记录"""
        return self._request(
            "DELETE",
            f"/bitable/v1/apps/{app_token}/tables/{table_id}/records/{record_id}"
        )
    
    # ==================== 文档 API ====================
    
    def search_docs(self, query: str, count: int = 20) -> Dict:
        """搜索文档"""
        return self._request(
            "POST",
            "/suite/docs-api/search/object",
            json={"search_key": query, "count": count}
        )
    
    # ==================== 用户 API ====================
    
    def get_user(self, user_id: str, user_id_type: str = "open_id") -> Dict:
        """获取用户信息"""
        return self._request(
            "GET",
            f"/contact/v3/users/{user_id}?user_id_type={user_id_type}"
        )


# ==================== 便捷函数 ====================

_clients = {}

def get_client(tenant: str = None) -> FeishuClient:
    """获取客户端实例"""
    tenant = tenant or DEFAULT_TENANT
    if tenant not in _clients:
        _clients[tenant] = FeishuClient(tenant)
    return _clients[tenant]

def send_text(receive_id: str, text: str, receive_id_type: str = "open_id", tenant: str = None) -> Dict:
    """发送文本消息"""
    return get_client(tenant).send_text(receive_id, text, receive_id_type)

def send_to_chat(chat_id: str, text: str, tenant: str = None) -> Dict:
    """发送消息到群组"""
    return get_client(tenant).send_text(chat_id, text, "chat_id")

def list_chats(tenant: str = None) -> List[Dict]:
    """获取群组列表"""
    result = get_client(tenant).list_chats()
    return result.get("data", {}).get("items", [])


# ==================== CLI ====================

if __name__ == "__main__":
    import sys
    
    def print_help():
        print("""
飞书多租户 API 工具

用法:
  python feishu_api.py [--tenant <name>] <command> [args...]

租户:
  personal  - 个人应用 (cli_a83467f9...)
  hanxing   - 汉兴企业 (cli_a9f758c0...) [默认]

命令:
  test                         # 测试连接
  chats                        # 列出群组
  send <chat_id> <text>        # 发送消息到群组
  user <open_id>               # 获取用户信息

示例:
  python feishu_api.py test
  python feishu_api.py --tenant personal chats
  python feishu_api.py --tenant hanxing send oc_xxx "Hello"
""")
    
    # 解析参数
    args = sys.argv[1:]
    tenant = None
    
    if len(args) >= 2 and args[0] == "--tenant":
        tenant = args[1]
        args = args[2:]
    
    if len(args) < 1:
        print_help()
        sys.exit(1)
    
    cmd = args[0]
    
    try:
        client = get_client(tenant)
        print(f"[{client.tenant_name}] ", end="")
        
        if cmd == "test":
            print(f"Token 获取成功: {client.token[:20]}...")
            
        elif cmd == "chats":
            result = client.list_chats()
            if result.get("code") == 0:
                chats = result.get("data", {}).get("items", [])
                if not chats:
                    print("没有找到群组（机器人可能还未加入任何群）")
                else:
                    print(f"找到 {len(chats)} 个群组:\n")
                    for chat in chats:
                        print(f"  - {chat.get('name', 'N/A')}")
                        print(f"    ID: {chat.get('chat_id')}")
                        print()
            else:
                print(f"错误: {result}")
                
        elif cmd == "send" and len(args) >= 3:
            chat_id = args[1]
            text = " ".join(args[2:])
            result = client.send_text(chat_id, text, "chat_id")
            if result.get("code") == 0:
                print(f"消息已发送")
            else:
                print(f"发送失败: {result}")
        
        elif cmd == "send-default" and len(args) >= 2:
            # 发送到默认群组
            if not client.default_chat:
                print(f"错误: 该租户未配置默认群组")
                sys.exit(1)
            text = " ".join(args[1:])
            result = client.send_text(client.default_chat, text, "chat_id")
            if result.get("code") == 0:
                print(f"消息已发送到默认群组")
            else:
                print(f"发送失败: {result}")
                
        elif cmd == "user" and len(args) >= 2:
            user_id = args[1]
            result = client.get_user(user_id)
            print(json.dumps(result, indent=2, ensure_ascii=False))
            
        else:
            print(f"未知命令或参数不足: {cmd}")
            print_help()
            sys.exit(1)
            
    except Exception as e:
        print(f"错误: {e}")
        sys.exit(1)
