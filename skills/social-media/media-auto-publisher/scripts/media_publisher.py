#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
自媒体文章自动发布工具 - 主执行脚本
整合平台导航、Cookie管理、弹窗处理等功能
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List, Optional

# 添加父目录到path以便导入其他模块
SCRIPT_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPT_DIR))

from cookie_manager import CookieManager
from platform_navigator import PlatformNavigator, PopupCloseHandler, Platform


class MediaPublisher:
    """自媒体发布工具主类"""

    # 平台MCP工具映射
    MCP_TOOLS = {
        "navigate": "mcp__plugin_playwright_playwright__browser_navigate",
        "snapshot": "mcp__plugin_playwright_playwright__browser_snapshot",
        "click": "mcp__plugin_playwright_playwright__browser_click",
        "fill": "mcp__plugin_playwright_playwright__browser_fill_form",
        "list_pages": "mcp__plugin_playwright_playwright__browser_tabs",
        "select_page": "mcp__plugin_playwright_playwright__browser_tabs",
    }

    def __init__(self):
        self.cookie_manager = CookieManager()

    def get_platform_navigator(self, platform: str) -> PlatformNavigator:
        """获取平台导航器"""
        platform_map = {
            "baijiahao": Platform.BAIJIAHAO,
            "sohu": Platform.SOHU,
            "zhihu": Platform.ZHIHU,
        }
        if platform not in platform_map:
            raise ValueError(f"不支持的平台: {platform}，支持的平台: {', '.join(platform_map.keys())}")
        return PlatformNavigator(platform_map[platform])

    def generate_mcp_commands(self, platform: str, target: str = "publish") -> List[Dict]:
        """
        生成MCP命令序列

        Args:
            platform: 平台代码 (baijiahao/sohu/zhihu)
            target: 目标页面 (publish/home/login)

        Returns:
            List[Dict]: MCP命令列表
        """
        navigator = self.get_platform_navigator(platform)
        commands = []

        if target == "publish":
            # 发布页面导航流程
            commands.append({
                "tool": self.MCP_TOOLS["navigate"],
                "params": {"url": navigator.get_publish_url()},
                "description": f"导航到{navigator.config['name']}发布页面"
            })
        elif target == "home":
            commands.append({
                "tool": self.MCP_TOOLS["navigate"],
                "params": {"url": navigator.get_home_url()},
                "description": f"导航到{navigator.config['name']}首页"
            })
        elif target == "login":
            commands.append({
                "tool": self.MCP_TOOLS["navigate"],
                "params": {"url": navigator.get_login_url()},
                "description": f"导航到{navigator.config['name']}登录页面"
            })

        # 获取快照
        commands.append({
            "tool": self.MCP_TOOLS["snapshot"],
            "description": "获取页面快照"
        })

        return commands

    def generate_full_workflow(self, platform: str) -> Dict:
        """
        生成完整的工作流程

        Args:
            platform: 平台代码

        Returns:
            Dict: 完整工作流程
        """
        navigator = self.get_platform_navigator(platform)

        workflow = {
            "platform": navigator.config["name"],
            "platform_code": platform,
            "steps": [
                {
                    "step": 1,
                    "action": "导航到平台",
                    "tool": self.MCP_TOOLS["navigate"],
                    "params": {"url": navigator.get_home_url()},
                    "description": f"打开{navigator.config['name']}首页"
                },
                {
                    "step": 2,
                    "action": "获取页面快照",
                    "tool": self.MCP_TOOLS["snapshot"],
                    "description": "检查登录状态和弹窗"
                },
                {
                    "step": 3,
                    "action": "检查登录状态",
                    "description": "验证用户是否已登录",
                    "indicators": navigator.get_login_indicators()
                },
                {
                    "step": 4,
                    "action": "关闭弹窗",
                    "description": "检测并关闭广告弹窗",
                    "patterns": navigator.get_popup_close_patterns()
                },
                {
                    "step": 5,
                    "action": "进入发布页面",
                    "description": "导航到文章发布页面",
                    "method": "click" if len(navigator.get_publish_button_texts()) > 0 else "direct_url",
                    "direct_url": navigator.get_publish_url(),
                    "button_texts": navigator.get_publish_button_texts()
                },
                {
                    "step": 6,
                    "action": "确认进入发布页",
                    "tool": self.MCP_TOOLS["snapshot"],
                    "description": "验证发布页面加载成功"
                }
            ],
            "platform_info": {
                "home_url": navigator.get_home_url(),
                "publish_url": navigator.get_publish_url(),
                "login_url": navigator.get_login_url(),
                "login_indicators": navigator.get_login_indicators(),
                "publish_buttons": navigator.get_publish_button_texts()
            }
        }

        return workflow

    def export_workflow_for_claude(self, platform: str, output_file: Optional[Path] = None) -> str:
        """
        导出工作流程供Claude使用

        Args:
            platform: 平台代码
            output_file: 输出文件路径（可选）

        Returns:
            str: JSON格式的工作流程
        """
        workflow = self.generate_full_workflow(platform)
        json_str = json.dumps(workflow, ensure_ascii=False, indent=2)

        if output_file:
            output_file.write_text(json_str, encoding='utf-8')
            print(f"[OK] 工作流程已导出到: {output_file}")

        return json_str

    def detect_popup_in_snapshot(self, snapshot: str, platform: str) -> List[Dict]:
        """
        在快照中检测弹窗

        Args:
            snapshot: 页面快照文本
            platform: 平台代码

        Returns:
            List[Dict]: 检测到的弹窗信息
        """
        navigator = self.get_platform_navigator(platform)
        popups = []

        lines = snapshot.split('\n')
        for i, line in enumerate(lines):
            # 检查是否包含弹窗关键词
            for pattern in navigator.get_popup_close_patterns():
                for keyword in pattern.get("text", []):
                    if keyword in line:
                        # 提取uid
                        if 'uid=' in line:
                            uid = line.split('uid=')[1].split()[0].strip('"\'')
                            popups.append({
                                "uid": uid,
                                "keyword": keyword,
                                "line_index": i,
                                "line_text": line.strip()
                            })

        return popups

    def check_login_status(self, snapshot: str, platform: str) -> Dict:
        """
        检查登录状态

        Args:
            snapshot: 页面快照文本
            platform: 平台代码

        Returns:
            Dict: 登录状态检查结果
        """
        navigator = self.get_platform_navigator(platform)
        indicators = navigator.get_login_indicators()

        found_indicators = []
        for indicator in indicators:
            if indicator in snapshot:
                found_indicators.append(indicator)

        return {
            "platform": platform,
            "logged_in": len(found_indicators) > 0,
            "found_indicators": found_indicators,
            "expected_indicators": indicators
        }

    def print_platform_info(self, platform: str):
        """打印平台信息"""
        navigator = self.get_platform_navigator(platform)
        info = navigator.config

        print(f"\n{'='*50}")
        print(f"平台: {info['name']}")
        print(f"{'='*50}")
        print(f"首页URL: {info['home_url']}")
        print(f"发布页面: {info['publish_url']}")
        print(f"登录页面: {info['login_url']}")
        print(f"\n登录状态指示器:")
        for indicator in navigator.get_login_indicators():
            print(f"  - {indicator}")
        print(f"\n发布按钮:")
        for btn in navigator.get_publish_button_texts():
            print(f"  - {btn}")
        print(f"{'='*50}\n")

    def quick_open(self, platform: str):
        """
        快速打开平台发布页面

        生成可直接执行的MCP命令序列
        """
        commands = self.generate_mcp_commands(platform, "publish")

        print(f"\n[*] 快速打开 {platform} 发布页面:")
        print("="*50)
        for cmd in commands:
            print(f"\n{cmd.get('description', '')}")
            print(f"  工具: {cmd['tool']}")
            if 'params' in cmd:
                params_str = ', '.join([f"{k}='{v}'" for k, v in cmd['params'].items()])
                print(f"  参数: {params_str}")
        print("\n" + "="*50)

        # 输出JSON格式供程序使用
        print("\n[*] JSON格式:")
        print(json.dumps(commands, ensure_ascii=False, indent=2))


def main():
    """命令行入口"""
    parser = argparse.ArgumentParser(
        description="自媒体文章自动发布工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 快速打开百家号发布页面
  python media_publisher.py open baijiahao

  # 查看平台信息
  python media_publisher.py info sohu

  # 导出工作流程
  python media_publisher.py workflow zhihu --output workflow.json

  # 检查登录状态
  python media_publisher.py check-login baijiahao --snapshot snapshot.txt
        """
    )

    subparsers = parser.add_subparsers(dest="command", help="可用命令")

    # open命令 - 快速打开平台
    open_parser = subparsers.add_parser("open", help="快速打开平台发布页面")
    open_parser.add_argument("platform", choices=["baijiahao", "sohu", "zhihu"], help="平台代码")

    # info命令 - 查看平台信息
    info_parser = subparsers.add_parser("info", help="查看平台信息")
    info_parser.add_argument("platform", choices=["baijiahao", "sohu", "zhihu"], help="平台代码")

    # workflow命令 - 生成工作流程
    workflow_parser = subparsers.add_parser("workflow", help="生成完整工作流程")
    workflow_parser.add_argument("platform", choices=["baijiahao", "sohu", "zhihu"], help="平台代码")
    workflow_parser.add_argument("--output", "-o", help="输出文件路径")
    workflow_parser.add_argument("--format", choices=["json", "text"], default="text", help="输出格式")

    # check-login命令 - 检查登录状态
    login_parser = subparsers.add_parser("check-login", help="检查登录状态")
    login_parser.add_argument("platform", choices=["baijiahao", "sohu", "zhihu"], help="平台代码")
    login_parser.add_argument("--snapshot", "-s", help="快照文件路径")

    # detect-popup命令 - 检测弹窗
    popup_parser = subparsers.add_parser("detect-popup", help="检测页面弹窗")
    popup_parser.add_argument("platform", choices=["baijiahao", "sohu", "zhihu"], help="平台代码")
    popup_parser.add_argument("--snapshot", "-s", help="快照文件路径")

    # 命令前缀 - 快捷方式
    parser.add_argument("quick_platform", nargs="?", choices=["baijiahao", "sohu", "zhihu"],
                       help="快速打开平台（等同于 'open <platform>'）")

    args = parser.parse_args()
    publisher = MediaPublisher()

    # 处理快捷方式
    if args.quick_platform and not args.command:
        args.command = "open"
        args.platform = args.quick_platform

    if args.command == "open":
        publisher.quick_open(args.platform)

    elif args.command == "info":
        publisher.print_platform_info(args.platform)

    elif args.command == "workflow":
        workflow = publisher.generate_full_workflow(args.platform)

        if args.format == "json":
            output = json.dumps(workflow, ensure_ascii=False, indent=2)
        else:
            # 文本格式输出
            output = f"\n{'='*50}\n"
            output += f"{workflow['platform']} - 自动发布工作流程\n"
            output += f"{'='*50}\n"
            for step in workflow["steps"]:
                output += f"\n步骤 {step['step']}: {step['description']}\n"
                output += f"  操作: {step['action']}\n"
                if "tool" in step:
                    output += f"  工具: {step['tool']}\n"
                if "params" in step:
                    output += f"  参数: {step['params']}\n"
                if "indicators" in step:
                    output += f"  指示器: {', '.join(step['indicators'])}\n"
            output += f"\n{'='*50}\n"

        if args.output:
            Path(args.output).write_text(output, encoding='utf-8')
            print(f"[OK] 工作流程已导出到: {args.output}")
        else:
            print(output)

    elif args.command == "check-login":
        if not args.snapshot:
            # 显示登录指示器
            navigator = publisher.get_platform_navigator(args.platform)
            print(f"\n{navigator.config['name']} 登录状态指示器:")
            print("  检测以下元素判断是否已登录:")
            for indicator in navigator.get_login_indicators():
                print(f"    - {indicator}")
        else:
            snapshot = Path(args.snapshot).read_text(encoding='utf-8')
            result = publisher.check_login_status(snapshot, args.platform)
            print(f"\n平台: {result['platform']}")
            print(f"登录状态: {'[OK] 已登录' if result['logged_in'] else '[X] 未登录'}")
            if result['found_indicators']:
                print(f"检测到的元素: {', '.join(result['found_indicators'])}")

    elif args.command == "detect-popup":
        if not args.snapshot:
            navigator = publisher.get_platform_navigator(args.platform)
            patterns = navigator.get_popup_close_patterns()
            print(f"\n{navigator.config['name']} 弹窗检测模式:")
            for i, pattern in enumerate(patterns, 1):
                print(f"  模式{i}: {pattern}")
        else:
            snapshot = Path(args.snapshot).read_text(encoding='utf-8')
            popups = publisher.detect_popup_in_snapshot(snapshot, args.platform)
            if popups:
                print(f"\n检测到 {len(popups)} 个弹窗:")
                for popup in popups:
                    print(f"  UID: {popup['uid']}, 关键词: {popup['keyword']}")
            else:
                print("\n未检测到弹窗")

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
