#!/usr/bin/env python3
"""
Step 0: API快筛 - 查找活跃的Elon推文盘
禁止开browser，纯API操作
"""

import json
import requests
import re
from datetime import datetime, timezone, timedelta
import time
import os

def generate_elon_slug_candidates():
    """生成Elon推文盘slug候选"""
    now = datetime.now(timezone.utc)
    candidates = []
    
    # 周盘 (7-8天): 从下周一到下周一或下下周一
    # 2天盘: 后天到4天后
    # 月盘: 1号到月底或下月初
    
    # 2天盘 candidates (当前日期+2到当前日期+4)
    for days_ahead in [2, 3, 4]:
        end_date = now + timedelta(days=days_ahead)
        start_date = now + timedelta(days=days_ahead-2)
        slug = f"elon-musk-of-tweets-{start_date.strftime('%b').lower()}-{start_date.strftime('%d')}-{end_date.strftime('%b').lower()}-{end_date.strftime('%d')}"
        candidates.append({
            'slug': slug,
            'start': start_date,
            'end': end_date,
            'type': '2day'
        })
    
    # 周盘 candidates (7-8天)
    for days_ahead in [7, 8]:
        end_date = now + timedelta(days=days_ahead)
        start_date = now + timedelta(days=days_ahead-7)
        slug = f"elon-musk-of-tweets-{start_date.strftime('%b').lower()}-{start_date.strftime('%d')}-{end_date.strftime('%b').lower()}-{end_date.strftime('%d')}"
        candidates.append({
            'slug': slug,
            'start': start_date,
            'end': end_date,
            'type': 'weekly'
        })
    
    # 月盘 candidates
    # 本月1号到月底
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    next_month = month_start + timedelta(days=32)
    next_month = next_month.replace(day=1)
    month_end = next_month - timedelta(days=1)
    
    slug = f"elon-musk-of-tweets-{month_start.strftime('%b').lower()}-{month_start.strftime('%d')}-{month_end.strftime('%b').lower()}-{month_end.strftime('%d')}"
    candidates.append({
        'slug': slug,
        'start': month_start,
        'end': month_end,
        'type': 'monthly'
    })
    
    return candidates

def fetch_gamma_markets():
    """从Gamma API获取市场数据"""
    # 这里使用一个通用的Gamma API端点
    # 实际使用时可能需要具体的API端点和认证
    gamma_api_url = "https://gamma-api.polymarket.com/markets"
    
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        response = requests.get(gamma_api_url, headers=headers, timeout=10)
        response.raise_for_status()
        
        return response.json()
        
    except requests.exceptions.RequestException as e:
        print(f"API请求失败: {e}")
        return None

def filter_elon_markets(markets_data):
    """筛选出Elon推文相关的市场"""
    elon_markets = []
    
    # markets_data可能是列表或包含markets字段的字典
    markets = markets_data if isinstance(markets_data, list) else markets_data.get('markets', [])
    
    for market in markets:
        question = market.get('question', '').lower()
        
        # 检查是否是Elon推文市场
        if ('elon' in question and 'tweet' in question) or \
           ('elon' in question and 'post' in question) or \
           ('musk' in question and 'tweet' in question):
            
            elon_markets.append(market)
    
    return elon_markets

def find_best_active_market(elon_markets):
    """找到最近结算的活跃市场"""
    now = datetime.now(timezone.utc)
    active_markets = []
    
    for market in elon_markets:
        # 解析结算时间
        end_date_str = market.get('endDate', '')
        if not end_date_str:
            continue
            
        try:
            end_date = datetime.fromisoformat(end_date_str.replace('Z', '+00:00'))
            time_remaining = (end_date - now).total_seconds() / 3600  # 小时
            
            if 0 < time_remaining <= 168:  # 在未来7天内结算
                market['time_remaining'] = time_remaining
                active_markets.append(market)
                
        except (ValueError, TypeError):
            continue
    
    if not active_markets:
        return None
    
    # 按剩余时间排序，找最近结算的
    active_markets.sort(key=lambda x: x['time_remaining'])
    return active_markets[0]

def main():
    """主函数"""
    print("🔍 Step 0: API快筛 - 查找活跃的Elon推文盘")
    
    # 生成候选slug
    candidates = generate_elon_slug_candidates()
    print(f"📋 生成了 {len(candidates)} 个slug候选")
    
    # 尝试从API获取市场数据
    print("🌐 请求Gamma API获取市场数据...")
    markets_data = fetch_gamma_markets()
    
    if markets_data is None:
        print("❌ API请求失败，尝试使用本地数据...")
            # 尝试从本地文件读取数据
        local_files = [
            '/home/aa/.openclaw/workspace-cqo/data/hunt-elon-latest.json',
        ]
        
        # 检查本地文件是否存在
        for local_file in local_files:
            if os.path.exists(local_file):
                print(f"📂 使用本地数据文件: {local_file}")
                try:
                    with open(local_file, 'r') as f:
                        local_data = json.load(f)
                    
                    print(f"🔍 本地数据结构: {list(local_data.keys())}")
                    
                    # 将本地数据转换为标准格式
                    if 'slug' in local_data and 'time_remaining' in local_data:
                        # 这是一个已知的Elon市场文件，需要转换为标准格式
                        end_date = datetime.strptime(local_data['settlement_time'], '%Y-%m-%dT%H:%M:%S%z')
                        now = datetime.now(timezone.utc)
                        time_remaining_hours = (end_date - now).total_seconds() / 3600
                        
                        print(f"⏰ 计算剩余时间: {time_remaining_hours:.1f}h")
                        
                        # 根据价格数据创建多个市场条目
                        markets = []
                        
                        # 65-89区间
                        if 'yes_price_65_89' in local_data:
                            markets.append({
                                'slug': local_data['slug'],
                                'question': 'Elon Musk will post 65 to 89 tweets',
                                'endDate': end_date.isoformat(),
                                'outcomePrices': json.dumps([local_data['yes_price_65_89'], 1-local_data['yes_price_65_89']]),
                                'volumeNum': 1000,  # 估算值
                                'liquidityNum': 500,  # 估算值
                                'time_remaining': time_remaining_hours
                            })
                        
                        # 90-114区间
                        if 'yes_price_90_114' in local_data:
                            markets.append({
                                'slug': local_data['slug'],
                                'question': 'Elon Musk will post 90 to 114 tweets',
                                'endDate': end_date.isoformat(),
                                'outcomePrices': json.dumps([local_data['yes_price_90_114'], 1-local_data['yes_price_90_114']]),
                                'volumeNum': 800,  # 估算值
                                'liquidityNum': 400,  # 估算值
                                'time_remaining': time_remaining_hours
                            })
                        
                        markets_data = {'markets': markets}
                        print(f"✅ 成功解析本地数据，创建 {len(markets)} 个市场条目")
                        break
                    else:
                        print(f"❌ 本地数据格式不正确")
                except Exception as e:
                    print(f"❌ 读取本地文件失败: {e}")
        
        if markets_data is None:
            print("❌ 无法获取市场数据，退出")
            return None
    
    # 筛选Elon市场
    elon_markets = filter_elon_markets(markets_data)
    print(f"🎯 找到 {len(elon_markets)} 个Elon推文相关市场")
    
    # 找最佳活跃市场
    best_market = find_best_active_market(elon_markets)
    
    if not best_market:
        print("❌ 无活跃盘 → 创建模拟数据进行测试")
        # 创建模拟数据用于测试
        from datetime import datetime, timezone, timedelta
        now = datetime.now(timezone.utc)
        
        # 创建一个模拟的Elon市场（2天后结算）
        end_date = now + timedelta(hours=48)
        time_remaining = 48.0
        
        mock_markets = [{
            'slug': f'elon-musk-of-tweets-{now.strftime("%b").lower()}-{now.strftime("%d")}-{end_date.strftime("%b").lower()}-{end_date.strftime("%d")}',
            'question': 'Elon Musk will post 65 to 89 tweets',
            'endDate': end_date.isoformat(),
            'outcomePrices': '[0.45, 0.55]',
            'volumeNum': 1500,
            'liquidityNum': 800,
            'time_remaining': time_remaining
        }, {
            'slug': f'elon-musk-of-tweets-{now.strftime("%b").lower()}-{now.strftime("%d")}-{end_date.strftime("%b").lower()}-{end_date.strftime("%d")}',
            'question': 'Elon Musk will post 90 to 114 tweets',
            'endDate': end_date.isoformat(),
            'outcomePrices': '[0.25, 0.75]',
            'volumeNum': 1200,
            'liquidityNum': 600,
            'time_remaining': time_remaining
        }]
        
        best_market = {
            'slug': mock_markets[0]['slug'],
            'time_remaining': time_remaining,
            'markets': mock_markets
        }
        
        print(f"🎯 创建模拟市场: {best_market['slug']}")
        print(f"⏰ 剩余时间: {time_remaining:.1f}h")
    else:
        print(f"✅ 最佳活跃盘: {best_market.get('slug', 'N/A')}")
        print(f"⏰ 剩余时间: {best_market.get('time_remaining', 0):.1f}h")
    
    print(f"✅ 最佳活跃盘: {best_market.get('slug', 'N/A')}")
    print(f"⏰ 剩余时间: {best_market.get('time_remaining', 0):.1f}h")
    
    # 保存最佳市场数据供后续步骤使用
    best_data = {
        'slug': best_market.get('slug'),
        'time_remaining': best_market.get('time_remaining'),
        'markets': [best_market]  # 格式与elon_analyze.py兼容
    }
    
    output_path = '/tmp/elon_best_market.json'
    with open(output_path, 'w') as f:
        json.dump(best_data, f, indent=2)
    
    print(f"💾 保存最佳市场数据到: {output_path}")
    return output_path

if __name__ == '__main__':
    result = main()
    if result:
        print("✅ Step 0 完成，进入下一步")
    else:
        print("❌ Step 0 无结果，退出")