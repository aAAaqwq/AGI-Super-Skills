#!/usr/bin/env python3
"""
百度热搜榜获取脚本
Baidu Hot Topics Fetcher
"""

import json
import sys
from datetime import datetime

def get_baidu_hot(limit=10):
    """获取百度热搜榜"""
    try:
        import requests
        
        # 百度热搜 API（需要实际可用 API）
        # 这里使用模拟数据
        hot_list = get_mock_data(limit)
        
        return {
            "status": "success",
            "data": hot_list,
            "count": len(hot_list),
            "timestamp": datetime.now().isoformat(),
            "source": "mock"
        }
        
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "data": get_mock_data(limit)
        }


def get_mock_data(limit=10):
    """模拟数据"""
    mock_hot = [
        {"rank": 1, "title": "春节档票房破100亿", "search_count": 1234567, "category": "娱乐"},
        {"rank": 2, "title": "AI大模型最新进展", "search_count": 987654, "category": "科技"},
        {"rank": 3, "title": "2026春运返程高峰", "search_count": 876543, "category": "社会"},
        {"rank": 4, "title": "新能源汽车补贴政策", "search_count": 765432, "category": "汽车"},
        {"rank": 5, "title": "央行降准最新消息", "search_count": 654321, "category": "财经"},
        {"rank": 6, "title": "春季养生指南", "search_count": 543210, "category": "健康"},
        {"rank": 7, "title": "北京天气", "search_count": 432109, "category": "生活"},
        {"rank": 8, "title": "A股今日走势", "search_count": 321098, "category": "财经"},
        {"rank": 9, "title": "教育改革新政策", "search_count": 210987, "category": "教育"},
        {"rank": 10, "title": "NBA常规赛战报", "search_count": 109876, "category": "体育"},
    ]
    return mock_hot[:limit]


def format_output(data):
    """格式化输出"""
    output = "🔍 百度热搜榜\n\n"
    for item in data:
        search_str = f"{item['search_count'] / 10000:.1f}万"
        output += f"{item['rank']}. [{item['category']}] {item['title']} - {search_str}搜索\n"
    return output


def main():
    limit = 10
    if len(sys.argv) > 1:
        try:
            limit = int(sys.argv[1])
        except:
            pass
    
    result = get_baidu_hot(limit)
    
    if "--json" in sys.argv:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(format_output(result["data"]))


if __name__ == "__main__":
    main()
