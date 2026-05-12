#!/usr/bin/env python3
"""
测试Gamma API连接和Elon市场获取
"""

import sys
import os
import re
import requests
import time
import logging

# 复制trade.py中的必要函数
GAMMA_API = "https://gamma-api.polymarket.com"

def retry_get(url, *, max_retries=3, backoff=2, timeout=10, **kwargs):
    """requests.get with automatic retry on SSL/connection errors."""
    kwargs.setdefault('timeout', timeout)
    for attempt in range(1, max_retries + 1):
        try:
            r = requests.get(url, **kwargs)
            return r
        except (requests.exceptions.SSLError,
                requests.exceptions.ConnectionError,
                requests.exceptions.ChunkedEncodingError,
                ConnectionResetError,
                OSError) as e:
            if attempt < max_retries:
                wait = backoff * attempt
                print(f"retry_get attempt {attempt}/{max_retries} failed: {type(e).__name__}: {e}, retrying in {wait}s...")
                time.sleep(wait)
            else:
                print(f"retry_get failed after {max_retries} attempts: {url[:80]}")
                raise
        except requests.exceptions.Timeout:
            if attempt < max_retries:
                wait = backoff * attempt
                print(f"retry_get timeout attempt {attempt}/{max_retries}, retrying in {wait}s...")
                time.sleep(wait)
            else:
                raise
import json

def test_elon_markets():
    """测试获取Elon市场数据"""
    
    # 尝试不同的搜索方式
    search_queries = [
        "elon",
        "musk", 
        "tweet",
        "elon-musk-of-tweets",
        "tweets"
    ]
    
    for query in search_queries:
        print(f"\n🔍 搜索: {query}")
        
        try:
            # 方法1: 搜索events
            url = f"{GAMMA_API}/events"
            params = {"query": query, "active": "true"}
            
            response = retry_get(url, params=params, timeout=10)
            if response.status_code == 200:
                data = response.json()
                print(f"✅ 找到 {len(data)} 个事件")
                
                for event in data[:5]:  # 只显示前5个
                    markets = event.get('markets', [])
                    if markets:
                        print(f"  🎯 事件: {event.get('name', 'N/A')}")
                        print(f"    📊 市场: {len(markets)} 个")
                        
                        for market in markets[:3]:  # 只显示前3个市场
                            question = market.get('question', 'N/A')[:100]
                            print(f"      📝 问题: {question}")
                            
                            # 检查是否是推文相关
                            if any(word in question.lower() for word in ['tweet', 'post', 'elon']):
                                print(f"      ✅ 推文相关!")
                                print(f"      🏷️ Slug: {market.get('slug', 'N/A')}")
                                
                                # 检查结算时间
                                end_date = market.get('endDate')
                                if end_date:
                                    from datetime import datetime, timezone, timedelta
                                    try:
                                        end_dt = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
                                        now = datetime.now(timezone.utc)
                                        remaining = (end_dt - now).total_seconds() / 3600
                                        print(f"      ⏰ 剩余时间: {remaining:.1f}h")
                                        
                                        if 0 < remaining <= 168:  # 7天内
                                            print(f"      🎯 活跃市场!")
                                            return market
                                    except:
                                        pass
                                
                                print(f"      💰 价格: {market.get('outcomePrices', 'N/A')}")
                                
                        print()
            else:
                print(f"❌ 搜索失败: {response.status_code}")
                
        except Exception as e:
            print(f"❌ 错误: {e}")
    
    return None

if __name__ == '__main__':
    print("🧪 测试Gamma API连接和Elon市场获取")
    result = test_elon_markets()
    
    if result:
        print(f"\n✅ 找到活跃的Elon市场:")
        print(f"  Slug: {result.get('slug', 'N/A')}")
        print(f"  问题: {result.get('question', 'N/A')[:100]}...")
    else:
        print(f"\n❌ 未找到活跃的Elon市场")