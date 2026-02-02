#!/usr/bin/env python3
"""
MCP 健康检测脚本
"""
import json
import subprocess
import time
from datetime import datetime
from pathlib import Path

class MCPHealthChecker:
    def __init__(self, config_path=None):
        self.config_path = Path.home() / ".claude.json"
        self.config = self.load_config()
        self.results = {}

    def load_config(self):
        """加载 MCP 配置"""
        if self.config_path.exists():
            with open(self.config_path, 'r') as f:
                config = json.load(f)
                return config.get('mcpServers', {})
        return {}

    def test_mcp_connection(self, name, config):
        """测试 MCP 连接"""
        start_time = time.time()

        try:
            # 尝试运行 MCP 命令
            command = config.get('command', '')
            args = config.get('args', [])

            if not command:
                return {
                    'status': 'error',
                    'error': 'No command specified'
                }

            # 测试命令是否可用
            result = subprocess.run(
                ['which', command] if command != 'npx' else ['which', 'npx'],
                capture_output=True,
                timeout=5
            )

            if result.returncode != 0:
                return {
                    'status': 'error',
                    'error': f'Command not found: {command}'
                }

            # 计算响应时间
            elapsed = (time.time() - start_time) * 1000

            return {
                'status': 'ok',
                'response_time': round(elapsed, 2),
                'command': command
            }

        except subprocess.TimeoutExpired:
            return {
                'status': 'timeout',
                'error': 'Connection timeout'
            }
        except Exception as e:
            return {
                'status': 'error',
                'error': str(e)
            }

    def check_all(self):
        """检查所有 MCP"""
        print("🔍 MCP Health Check")
        print("=" * 50)
        print()

        results = {}
        for name, config in self.config.items():
            result = self.test_mcp_connection(name, config)
            results[name] = result

            # 显示结果
            status_icon = {
                'ok': '✅',
                'timeout': '⏱️',
                'error': '❌'
            }.get(result['status'], '❓')

            print(f"{status_icon} {name}")

            if result['status'] == 'ok':
                print(f"   Status: OK ({result['response_time']}ms)")
                print(f"   Command: {result['command']}")
            else:
                print(f"   Status: {result['status'].upper()}")
                print(f"   Error: {result['error']}")

            print()

        self.results = results
        return results

    def check_single(self, name):
        """检查单个 MCP"""
        if name not in self.config:
            print(f"❌ MCP not found: {name}")
            return None

        print(f"🔍 Checking MCP: {name}")
        print("=" * 50)
        print()

        result = self.test_mcp_connection(name, config=self.config[name])

        status_icon = {
            'ok': '✅',
            'timeout': '⏱️',
            'error': '❌'
        }.get(result['status'], '❓')

        print(f"{status_icon} {name}")

        if result['status'] == 'ok':
            print(f"   Status: OK ({result['response_time']}ms)")
            print(f"   Command: {result['command']}")
            print(f"   Args: {' '.join(result.get('args', []))}")
        else:
            print(f"   Status: {result['status'].upper()}")
            print(f"   Error: {result['error']}")

        return result

    def get_summary(self):
        """获取摘要"""
        if not self.results:
            return "No results available"

        ok_count = sum(1 for r in self.results.values() if r['status'] == 'ok')
        error_count = len(self.results) - ok_count

        return f"OK: {ok_count}, Errors: {error_count}, Total: {len(self.results)}"

def main():
    import argparse

    parser = argparse.ArgumentParser(description="MCP Health Checker")
    parser.add_argument('name', nargs='?', help='MCP name to check (optional)')
    parser.add_argument('--json', action='store_true', help='Output as JSON')

    args = parser.parse_args()

    checker = MCPHealthChecker()

    if args.name:
        result = checker.check_single(args.name)
        if args.json and result:
            print(json.dumps(result, indent=2))
    else:
        results = checker.check_all()
        if args.json:
            print(json.dumps(results, indent=2))
        else:
            print()
            print("📊 Summary:", checker.get_summary())

if __name__ == "__main__":
    main()
