#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Cookie管理脚本 - 用于自媒体平台账号切换
支持百家号、搜狐、知乎三个平台
"""

import json
import os
import sys
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional

# 默认存储路径
DEFAULT_STORAGE_DIR = Path.home() / ".claude" / "media-auto-publisher"
STORAGE_FILE = DEFAULT_STORAGE_DIR / "cookies.json"


class CookieManager:
    """Cookie管理器"""

    SUPPORTED_PLATFORMS = {
        "baijiahao": {
            "name": "百家号",
            "base_url": "https://baijiahao.baidu.com",
            "publish_url": "https://baijiahao.baidu.com/builder/rc/edit?type=news",
            "login_url": "https://baijiahao.baidu.com/"
        },
        "sohu": {
            "name": "搜狐",
            "base_url": "https://mp.sohu.com",
            "publish_url": "https://mp.sohu.com/api/author/article/new",
            "login_url": "https://mp.sohu.com/"
        },
        "zhihu": {
            "name": "知乎",
            "base_url": "https://zhuanlan.zhihu.com",
            "publish_url": "https://zhuanlan.zhihu.com/write",
            "login_url": "https://www.zhihu.com/signin"
        }
    }

    def __init__(self, storage_path: Path = None):
        self.storage_path = storage_path or STORAGE_FILE
        self.storage_dir = self.storage_path.parent
        self._ensure_storage_dir()

    def _ensure_storage_dir(self):
        """确保存储目录存在"""
        self.storage_dir.mkdir(parents=True, exist_ok=True)

    def _load_data(self) -> Dict:
        """加载数据"""
        if self.storage_path.exists():
            with open(self.storage_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {"platforms": {}, "accounts": {}}

    def _save_data(self, data: Dict):
        """保存数据"""
        with open(self.storage_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def add_account(self, platform: str, account_name: str, cookies: List[Dict],
                    user_agent: str = None, metadata: Dict = None) -> bool:
        """
        添加账号Cookie

        Args:
            platform: 平台代码 (baijiahao/sohu/zhihu)
            account_name: 账号名称/标识
            cookies: Cookie列表，格式: [{"name": "xxx", "value": "xxx", "domain": "xxx"}, ...]
            user_agent: User-Agent字符串
            metadata: 额外元数据

        Returns:
            bool: 是否成功
        """
        if platform not in self.SUPPORTED_PLATFORMS:
            print(f"错误: 不支持的平台 '{platform}'，支持的平台: {', '.join(self.SUPPORTED_PLATFORMS.keys())}")
            return False

        data = self._load_data()

        if platform not in data["accounts"]:
            data["accounts"][platform] = {}

        data["accounts"][platform][account_name] = {
            "cookies": cookies,
            "user_agent": user_agent,
            "metadata": metadata or {},
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat()
        }

        self._save_data(data)
        print(f"✓ 已添加账号: {platform}/{account_name}")
        return True

    def get_account(self, platform: str, account_name: str) -> Optional[Dict]:
        """获取指定账号的Cookie信息"""
        data = self._load_data()
        return data.get("accounts", {}).get(platform, {}).get(account_name)

    def list_accounts(self, platform: str = None) -> List[Dict]:
        """
        列出所有账号

        Args:
            platform: 平台代码，为空则列出所有平台

        Returns:
            List[Dict]: 账号列表
        """
        data = self._load_data()
        result = []

        platforms = [platform] if platform else data.get("accounts", {}).keys()

        for plat in platforms:
            if plat in data.get("accounts", {}):
                for acc_name, acc_info in data["accounts"][plat].items():
                    result.append({
                        "platform": plat,
                        "platform_name": self.SUPPORTED_PLATFORMS[plat]["name"],
                        "account": acc_name,
                        "created_at": acc_info.get("created_at"),
                        "updated_at": acc_info.get("updated_at")
                    })

        return result

    def delete_account(self, platform: str, account_name: str) -> bool:
        """删除账号"""
        data = self._load_data()
        if platform in data.get("accounts", {}) and account_name in data["accounts"][platform]:
            del data["accounts"][platform][account_name]
            self._save_data(data)
            print(f"✓ 已删除账号: {platform}/{account_name}")
            return True
        print(f"错误: 账号不存在 {platform}/{account_name}")
        return False

    def get_platform_info(self, platform: str) -> Optional[Dict]:
        """获取平台信息"""
        return self.SUPPORTED_PLATFORMS.get(platform)

    def export_cookies_for_browser(self, platform: str, account_name: str,
                                   format: str = "json") -> Optional[str]:
        """
        导出Cookie供浏览器使用

        Args:
            platform: 平台代码
            account_name: 账号名称
            format: 导出格式 (json/netscape/header)

        Returns:
            str: 导出的Cookie字符串
        """
        account = self.get_account(platform, account_name)
        if not account:
            return None

        cookies = account["cookies"]

        if format == "json":
            return json.dumps(cookies, ensure_ascii=False)
        elif format == "netscape":
            # Netscape Cookie格式
            lines = ["# Netscape HTTP Cookie File"]
            for c in cookies:
                domain = c.get("domain", "").lstrip(".")
                lines.append(f"\t{domain}\t{'TRUE' if c.get('domain','').startswith('.') else 'FALSE'}\t"
                           f"{c.get('path', '/')}\t{'TRUE' if c.get('secure') else 'FALSE'}\t"
                           f"{c.get('expiration', '0')}\t{c.get('name')}\t{c.get('value')}")
            return "\n".join(lines)
        elif format == "header":
            # HTTP Header格式
            return "; ".join([f"{c['name']}={c['value']}" for c in cookies])
        else:
            return json.dumps(cookies, ensure_ascii=False)


def print_accounts_table(accounts: List[Dict]):
    """打印账号表格"""
    if not accounts:
        print("没有找到任何账号")
        return

    print("\n" + "=" * 70)
    print(f"{'平台':<12} {'账号名称':<20} {'创建时间':<20}")
    print("=" * 70)
    for acc in accounts:
        print(f"{acc['platform_name']:<12} {acc['account']:<20} {acc['created_at'][:19]:<20}")
    print("=" * 70)


def main():
    """命令行入口"""
    import argparse

    parser = argparse.ArgumentParser(description="自媒体平台Cookie管理器")
    subparsers = parser.add_subparsers(dest="command", help="可用命令")

    # 添加账号
    add_parser = subparsers.add_parser("add", help="添加账号Cookie")
    add_parser.add_argument("platform", choices=["baijiahao", "sohu", "zhihu"], help="平台")
    add_parser.add_argument("account", help="账号名称")
    add_parser.add_argument("--cookies-file", help="Cookie JSON文件路径")
    add_parser.add_argument("--user-agent", help="User-Agent")

    # 列出账号
    list_parser = subparsers.add_parser("list", help="列出所有账号")
    list_parser.add_argument("--platform", choices=["baijiahao", "sohu", "zhihu"], help="过滤平台")

    # 删除账号
    del_parser = subparsers.add_parser("delete", help="删除账号")
    del_parser.add_argument("platform", choices=["baijiahao", "sohu", "zhihu"], help="平台")
    del_parser.add_argument("account", help="账号名称")

    # 导出Cookie
    export_parser = subparsers.add_parser("export", help="导出Cookie")
    export_parser.add_argument("platform", choices=["baijiahao", "sohu", "zhihu"], help="平台")
    export_parser.add_argument("account", help="账号名称")
    export_parser.add_argument("--format", choices=["json", "netscape", "header"], default="json", help="导出格式")

    # 显示平台信息
    info_parser = subparsers.add_parser("info", help="显示平台信息")
    info_parser.add_argument("platform", choices=["baijiahao", "sohu", "zhihu"], nargs="?",
                             help="平台代码（留空显示所有）")

    args = parser.parse_args()
    manager = CookieManager()

    if args.command == "add":
        # 从文件读取cookies或提示输入
        if args.cookies_file:
            with open(args.cookies_file, 'r', encoding='utf-8') as f:
                cookies = json.load(f)
        else:
            print("请输入Cookie JSON（按Ctrl+D结束输入）:")
            cookies = json.load(sys.stdin)

        manager.add_account(args.platform, args.account, cookies, args.user_agent)

    elif args.command == "list":
        accounts = manager.list_accounts(args.platform)
        print_accounts_table(accounts)

    elif args.command == "delete":
        manager.delete_account(args.platform, args.account)

    elif args.command == "export":
        result = manager.export_cookies_for_browser(args.platform, args.account, args.format)
        if result:
            print(result)
        else:
            print(f"错误: 未找到账号 {args.platform}/{args.account}")

    elif args.command == "info":
        if args.platform:
            info = manager.get_platform_info(args.platform)
            if info:
                print(f"\n平台: {info['name']}")
                print(f"基础URL: {info['base_url']}")
                print(f"发布页面: {info['publish_url']}")
                print(f"登录页面: {info['login_url']}")
        else:
            print("\n支持的平台:")
            for code, info in manager.SUPPORTED_PLATFORMS.items():
                print(f"  {code}: {info['name']}")

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
