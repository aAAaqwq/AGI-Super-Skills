#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
平台导航助手 - 配合Playwright MCP使用
提供各平台的导航和弹窗处理逻辑
"""

import json
from typing import Dict, List, Optional, Callable
from enum import Enum


class Platform(Enum):
    """支持的平台枚举"""
    BAIJIAHAO = "baijiahao"
    SOHU = "sohu"
    ZHIHU = "zhihu"


class PlatformNavigator:
    """平台导航器 - 为Playwright MCP提供导航指令"""

    # 平台配置
    PLATFORMS = {
        Platform.BAIJIAHAO: {
            "name": "百家号",
            "home_url": "https://baijiahao.baidu.com/",
            "publish_url": "https://baijiahao.baidu.com/builder/rc/edit?type=news",
            "login_url": "https://baijiahao.baidu.com/",
            "login_indicators": [
                # 登录后的元素特征
                "头像", "发布作品", "内容管理"
            ],
            "publish_button_selectors": [
                "发布作品",
                "发布图文"
            ],
            "popup_close_selectors": [
                # 广告/弹窗关闭按钮
                {"text": ["关闭", "close", "×", "✕"], "role": ["button", "dialog"]},
                {"text": ["不再提示", "不再显示"], "role": ["button"]},
                {"text": ["跳过", "跳过此"], "role": ["button"]},
            ],
            "wait_for_navigation": True
        },
        Platform.SOHU: {
            "name": "搜狐号",
            "home_url": "https://mp.sohu.com/",
            "publish_url": "https://mp.sohu.com/api/author/article/new",
            "login_url": "https://mp.sohu.com/",
            "login_indicators": [
                "发布文章", "内容管理", "个人中心"
            ],
            "publish_button_selectors": [
                "发布文章",
                "写文章"
            ],
            "popup_close_selectors": [
                {"text": ["关闭", "close", "×", "✕"], "role": ["button", "dialog"]},
                {"text": ["我知道了", "知道了"], "role": ["button"]},
            ],
            "wait_for_navigation": True
        },
        Platform.ZHIHU: {
            "name": "知乎",
            "home_url": "https://www.zhihu.com/",
            "publish_url": "https://zhuanlan.zhihu.com/write",
            "login_url": "https://www.zhihu.com/signin",
            "login_indicators": [
                "写文章", "首页", "通知", "私信"
            ],
            "publish_button_selectors": [
                "写文章",
                "发布"
            ],
            "popup_close_selectors": [
                {"text": ["关闭", "close", "×", "✕"], "role": ["button", "dialog"]},
                {"text": ["跳过", "以后再说"], "role": ["button"]},
                {"text": ["不再提示"], "role": ["button"]},
            ],
            "wait_for_navigation": True
        }
    }

    def __init__(self, platform: Platform):
        self.platform = platform
        self.config = self.PLATFORMS[platform]
        self.current_url = None

    def get_home_url(self) -> str:
        """获取首页URL"""
        return self.config["home_url"]

    def get_publish_url(self) -> str:
        """获取发布页面URL"""
        return self.config["publish_url"]

    def get_login_url(self) -> str:
        """获取登录页面URL"""
        return self.config["login_url"]

    def get_login_indicators(self) -> List[str]:
        """获取登录状态指示器文本"""
        return self.config["login_indicators"]

    def get_publish_button_texts(self) -> List[str]:
        """获取发布按钮文本列表"""
        return self.config["publish_button_selectors"]

    def get_popup_close_patterns(self) -> List[Dict]:
        """获取弹窗关闭按钮匹配模式"""
        return self.config["popup_close_selectors"]

    def check_if_logged_in(self, snapshot_text: str) -> bool:
        """
        检查是否已登录

        Args:
            snapshot_text: 页面快照的文本内容

        Returns:
            bool: 是否已登录
        """
        indicators = self.get_login_indicators()
        return any(indicator in snapshot_text for indicator in indicators)

    def find_popup_in_snapshot(self, snapshot: str) -> Optional[str]:
        """
        在快照中查找弹窗

        Args:
            snapshot: 页面快照文本

        Returns:
            弹窗的uid或None
        """
        # 简化版：检查常见弹窗关键词
        popup_keywords = ["广告", "推广", "活动", "邀请", "升级", "会员", "优惠券"]
        popup_lines = []

        for line in snapshot.split('\n'):
            for keyword in popup_keywords:
                if keyword in line:
                    # 提取uid（格式如 uid=xxx）
                    if 'uid=' in line:
                        uid = line.split('uid=')[1].split()[0].strip('"\'')
                        return uid

        return None

    def generate_navigate_commands(self, target: str = "publish") -> str:
        """
        生成导航指令（供Claude Playwright使用）

        Args:
            target: 目标页面类型 ("home", "publish", "login")

        Returns:
            str: JSON格式的导航步骤说明
        """
        url_map = {
            "home": self.get_home_url(),
            "publish": self.get_publish_url(),
            "login": self.get_login_url()
        }

        steps = [
            {
                "action": "navigate",
                "url": url_map.get(target, self.get_home_url()),
                "description": f"导航到{self.config['name']}{target}页面"
            },
            {
                "action": "wait_for_load",
                "description": "等待页面加载完成"
            },
            {
                "action": "take_snapshot",
                "description": "获取页面快照"
            },
            {
                "action": "check_login",
                "description": "检查登录状态",
                "indicators": self.get_login_indicators()
            },
            {
                "action": "close_popups",
                "description": "关闭广告弹窗",
                "patterns": self.get_popup_close_patterns()
            }
        ]

        return json.dumps(steps, ensure_ascii=False, indent=2)

    def get_mcp_workflow(self) -> Dict:
        """
        获取完整的MCP工作流程

        Returns:
            Dict: 包含完整Playwright MCP调用步骤的字典
        """
        return {
            "platform": self.config["name"],
            "platform_code": self.platform.value,
            "workflow": [
                {
                    "step": 1,
                    "action": "mcp__plugin_playwright_playwright__browser_navigate",
                    "params": {"type": "url", "url": self.get_home_url()},
                    "description": f"打开{self.config['name']}首页"
                },
                {
                    "step": 2,
                    "action": "mcp__plugin_playwright_playwright__browser_snapshot",
                    "description": "获取页面快照检查状态"
                },
                {
                    "step": 3,
                    "action": "check_and_close_popups",
                    "description": "检测并关闭广告弹窗",
                    "patterns": self.get_popup_close_patterns()
                },
                {
                    "step": 4,
                    "action": "verify_login",
                    "description": "验证登录状态",
                    "indicators": self.get_login_indicators()
                },
                {
                    "step": 5,
                    "action": "navigate_to_publish",
                    "params": {
                        "method": "click" if len(self.get_publish_button_texts()) > 0 else "direct_url",
                        "direct_url": self.get_publish_url(),
                        "button_texts": self.get_publish_button_texts()
                    },
                    "description": "进入发布文章页面"
                },
                {
                    "step": 6,
                    "action": "mcp__plugin_playwright_playwright__browser_snapshot",
                    "description": "确认进入发布页面"
                }
            ]
        }


class PopupCloseHandler:
    """弹窗关闭处理器"""

    # 常见弹窗关闭按钮文本模式
    CLOSE_PATTERNS = {
        "zh": ["关闭", "关闭按钮", "关闭广告", "×", "✕", "我知道了", "知道了", "不再提示",
               "不再显示", "跳过", "以后再说", "暂不", "取消", "不升级", "稍后", "关闭此"],
        "en": ["close", "close button", "×", "✕", "got it", "skip", "not now",
               "later", "cancel", "dismiss", "hide"]
    }

    # 常见弹窗容器关键词
    POPUP_CONTAINER_KEYWORDS = {
        "zh": ["广告", "弹窗", "弹框", "浮层", "蒙层", "遮罩", "dialog", "modal", "popup"],
        "en": ["ad", "advertisement", "popup", "modal", "dialog", "overlay", "banner"]
    }

    @classmethod
    def find_close_button_in_snapshot(cls, snapshot: str, language: str = "zh") -> List[str]:
        """
        在快照中查找关闭按钮

        Args:
            snapshot: 页面快照文本
            language: 语言 ("zh" 或 "en")

        Returns:
            List[str]: 找到的关闭按钮uid列表
        """
        close_patterns = cls.CLOSE_PATTERNS.get(language, cls.CLOSE_PATTERNS["zh"])
        popup_keywords = cls.POPUP_CONTAINER_KEYWORDS.get(language, cls.POPUP_CONTAINER_KEYWORDS["zh"])

        found_uids = []

        lines = snapshot.split('\n')
        for i, line in enumerate(lines):
            # 检查是否包含关闭按钮文本
            if any(pattern in line for pattern in close_patterns):
                # 提取uid
                if 'uid=' in line:
                    uid = line.split('uid=')[1].split()[0].strip('"\'')
                    # 检查是否是button类型
                    if i > 0:
                        prev_line = lines[i-1]
                        if 'button' in prev_line.lower() or 'btn' in prev_line.lower():
                            found_uids.append(uid)
                    found_uids.append(uid)

        return found_uids

    @classmethod
    def detect_popup(cls, snapshot: str, language: str = "zh") -> bool:
        """
        检测页面是否有弹窗

        Args:
            snapshot: 页面快照文本
            language: 语言

        Returns:
            bool: 是否检测到弹窗
        """
        popup_keywords = cls.POPUP_CONTAINER_KEYWORDS.get(language, cls.POPUP_CONTAINER_KEYWORDS["zh"])
        close_patterns = cls.CLOSE_PATTERNS.get(language, cls.CLOSE_PATTERNS["zh"])

        has_popup_keyword = any(kw in snapshot.lower() for kw in popup_keywords)
        has_close_button = any(pattern in snapshot for pattern in close_patterns)

        return has_popup_keyword or has_close_button


def main():
    """命令行入口"""
    import argparse

    parser = argparse.ArgumentParser(description="平台导航助手")
    parser.add_argument("platform", choices=["baijiahao", "sohu", "zhihu"], help="平台代码")

    subparsers = parser.add_subparsers(dest="command", help="可用命令")

    # info命令
    info_parser = subparsers.add_parser("info", help="显示平台信息")

    # workflow命令
    workflow_parser = subparsers.add_parser("workflow", help="生成MCP工作流程")
    workflow_parser.add_argument("--format", choices=["json", "text"], default="text",
                                help="输出格式")

    # test命令
    test_parser = subparsers.add_parser("test", help="测试弹窗检测")
    test_parser.add_argument("snapshot_file", help="快照文件路径")

    args = parser.parse_args()

    platform = Platform(args.platform)
    navigator = PlatformNavigator(platform)

    if args.command == "info":
        print(f"\n平台: {navigator.config['name']}")
        print(f"首页: {navigator.get_home_url()}")
        print(f"发布页: {navigator.get_publish_url()}")
        print(f"登录页: {navigator.get_login_url()}")
        print(f"登录指示器: {', '.join(navigator.get_login_indicators())}")

    elif args.command == "workflow":
        workflow = navigator.get_mcp_workflow()
        if args.format == "json":
            print(json.dumps(workflow, ensure_ascii=False, indent=2))
        else:
            print(f"\n{navigator.config['name']} - MCP工作流程:")
            print("=" * 50)
            for step in workflow["workflow"]:
                print(f"\n步骤 {step['step']}: {step['description']}")
                print(f"  操作: {step['action']}")
                if "params" in step:
                    print(f"  参数: {step['params']}")

    elif args.command == "test":
        with open(args.snapshot_file, 'r', encoding='utf-8') as f:
            snapshot = f.read()
        has_popup = PopupCloseHandler.detect_popup(snapshot)
        print(f"弹窗检测: {'发现弹窗' if has_popup else '未发现弹窗'}")
        if has_popup:
            uids = PopupCloseHandler.find_close_button_in_snapshot(snapshot)
            print(f"关闭按钮UID: {uids}")

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
