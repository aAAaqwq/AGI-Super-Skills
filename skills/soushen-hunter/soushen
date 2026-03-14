#!/usr/bin/env python3
"""
搜神猎手 (SouShen Hunter) - 主入口
高性能 Bing 搜索引擎 - 零 API 费用
"""

import sys
import os

# 将 scripts 目录添加到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'scripts'))

from bing_search import main as bing_main

if __name__ == '__main__':
    # 添加品牌标识
    if len(sys.argv) < 2 or '--help' in sys.argv:
        print("╔══════════════════════════════════════╗")
        print("║     🔍 搜神猎手 (SouShen Hunter)      ║")
        print("║   高性能搜索引擎 - 零 API 费用       ║")
        print("╚══════════════════════════════════════╝")
        print()
    
    # 调用主函数
    import asyncio
    asyncio.run(bing_main())
