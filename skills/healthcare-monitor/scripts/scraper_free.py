#!/usr/bin/env python3
"""
免费多平台轮换爬虫
在天眼查、企查查、爱企查、国家公示系统之间轮换，最大化免费额度
"""

import json
import os
import re
import asyncio
import random
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

# 尝试导入 playwright
try:
    from playwright.async_api import async_playwright
    HAS_PLAYWRIGHT = True
except ImportError:
    HAS_PLAYWRIGHT = False
    print("⚠️ Playwright 未安装，将使用手动模式")


class FreePlatformRotator:
    """免费平台轮换器"""
    
    # 平台配置（按优先级排序）
    PLATFORMS = [
        {
            "name": "天眼查",
            "id": "tianyancha",
            "search_url": "https://www.tianyancha.com/search?key={query}",
            "daily_limit": 20,
            "delay_range": (3, 8),
            "selectors": {
                "result_link": "a[href*='/company/']",
                "company_name": ".company-name",
                "legal_person": ".legal-person",
                "capital": ".capital",
                "established": ".establish-date"
            }
        },
        {
            "name": "企查查",
            "id": "qichacha",
            "search_url": "https://www.qcc.com/search?key={query}",
            "daily_limit": 10,
            "delay_range": (5, 12),
            "selectors": {
                "result_link": "a[href*='/firm/']",
                "company_name": ".company-name",
                "legal_person": ".legal-person",
                "capital": ".capital",
                "established": ".establish-date"
            }
        },
        {
            "name": "爱企查",
            "id": "aiqicha",
            "search_url": "https://aiqicha.baidu.com/s?q={query}",
            "daily_limit": 50,  # 百度系的，限制较松
            "delay_range": (2, 6),
            "selectors": {
                "result_link": "a[href*='/company/']",
            }
        },
        {
            "name": "国家企业信用信息公示系统",
            "id": "gsxt",
            "search_url": "https://www.gsxt.gov.cn/",
            "daily_limit": 999,  # 官方系统，无限制
            "delay_range": (3, 10),
            "note": "需要精确公司名称搜索"
        }
    ]
    
    def __init__(self):
        self.data_dir = Path(__file__).parent.parent / "data" / "snapshots"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        # 使用统计
        self.stats_file = self.data_dir.parent / "usage_stats.json"
        self.stats = self._load_stats()
    
    def _load_stats(self):
        """加载使用统计"""
        if self.stats_file.exists():
            with open(self.stats_file, "r") as f:
                return json.load(f)
        return {
            "date": datetime.now().strftime("%Y-%m-%d"),
            "platforms": {}
        }
    
    def _save_stats(self):
        """保存使用统计"""
        with open(self.stats_file, "w") as f:
            json.dump(self.stats, f, indent=2)
    
    def _reset_daily_stats(self):
        """重置每日统计"""
        today = datetime.now().strftime("%Y-%m-%d")
        if self.stats.get("date") != today:
            self.stats = {
                "date": today,
                "platforms": {}
            }
            self._save_stats()
    
    def _get_available_platforms(self):
        """获取当前可用的平台"""
        self._reset_daily_stats()
        available = []
        
        for platform in self.PLATFORMS:
            usage = self.stats["platforms"].get(platform["id"], 0)
            if usage < platform["daily_limit"]:
                available.append(platform)
        
        # 按优先级排序（未使用的优先）
        available.sort(key=lambda p: self.stats["platforms"].get(p["id"], 0))
        return available
    
    def _record_usage(self, platform_id):
        """记录使用次数"""
        if platform_id not in self.stats["platforms"]:
            self.stats["platforms"][platform_id] = 0
        self.stats["platforms"][platform_id] += 1
        self._save_stats()
    
    def get_usage_report(self):
        """获取使用报告"""
        self._reset_daily_stats()
        report = []
        report.append(f"📊 **今日使用统计** ({self.stats['date']})\n")
        
        for platform in self.PLATFORMS:
            pid = platform["id"]
            used = self.stats["platforms"].get(pid, 0)
            limit = platform["daily_limit"]
            remaining = max(0, limit - used)
            pct = int(used / limit * 100) if limit < 999 else 0
            
            status = "🟢" if remaining > 5 else "🟡" if remaining > 0 else "🔴"
            report.append(f"{status} **{platform['name']}**: {used}/{limit} 已用 ({remaining} 次剩余)")
        
        return "\n".join(report)
    
    async def scrape_company(self, company_name):
        """
        采集企业信息，自动轮换平台
        返回: {
            "success": True/False,
            "source": "平台名",
            "data": {...},
            "platform_used": "平台ID"
        }
        """
        if not HAS_PLAYWRIGHT:
            return self._manual_fallback(company_name)
        
        available = self._get_available_platforms()
        
        if not available:
            return {
                "success": False,
                "error": "所有平台今日免费额度已用完",
                "usage_report": self.get_usage_report()
            }
        
        # 依次尝试可用平台
        for platform in available:
            try:
                result = await self._scrape_from_platform(platform, company_name)
                if result["success"]:
                    self._record_usage(platform["id"])
                    return result
            except Exception as e:
                print(f"⚠️ {platform['name']} 采集失败: {e}")
                continue
        
        # 所有平台都失败，返回手动指令
        return self._manual_fallback(company_name)
    
    async def _scrape_from_platform(self, platform, company_name):
        """从指定平台采集"""
        async with async_playwright() as p:
            # 启动浏览器
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            page = await context.new_page()
            
            # 随机延迟
            delay_min, delay_max = platform["delay_range"]
            await asyncio.sleep(random.uniform(delay_min, delay_max))
            
            # 搜索
            search_url = platform["search_url"].format(query=quote(company_name))
            
            try:
                await page.goto(search_url, wait_until="domcontentloaded", timeout=20000)
                await asyncio.sleep(random.uniform(2, 5))
                
                # 国家公示系统特殊处理
                if platform["id"] == "gsxt":
                    data = await self._scrape_gsxt(page, company_name)
                else:
                    data = await self._scrape_generic(page, platform, company_name)
                
                await browser.close()
                
                if data:
                    return {
                        "success": True,
                        "source": platform["name"],
                        "platform_used": platform["id"],
                        "data": data
                    }
                else:
                    return {"success": False, "error": "未找到企业信息"}
                    
            except Exception as e:
                await browser.close()
                raise e
    
    async def _scrape_generic(self, page, platform, company_name):
        """通用采集逻辑"""
        # 点击第一个搜索结果
        link = await page.query_selector(platform["selectors"]["result_link"])
        if not link:
            return None
        
        await link.click()
        await asyncio.sleep(random.uniform(3, 8))
        
        # 解析页面
        content = await page.content()
        return self._parse_html_content(content, company_name)
    
    async def _scrape_gsxt(self, page, company_name):
        """国家公示系统特殊采集"""
        # 输入公司名称
        try:
            await page.fill('input[name="keyword"]', company_name)
            await page.click('button:has-text("搜索")')
            await asyncio.sleep(5)
            
            # 点击搜索结果
            result = await page.query_selector('a[href*="/detail"]')
            if result:
                await result.click()
                await asyncio.sleep(5)
                
                content = await page.content()
                return self._parse_html_content(content, company_name)
        except:
            pass
        
        return None
    
    def _parse_html_content(self, html, company_name):
        """从 HTML 解析企业数据"""
        data = {"name": company_name}
        
        # 使用正则提取关键信息
        capital = re.search(r'注册资本[：:]?\s*([\d,.]+)\s*(万|亿)?[元人民币]*', html)
        if capital:
            amount = capital.group(1).replace(",", "")
            unit = capital.group(2) or "万"
            data["capital"] = f"{amount}{unit}"
            data["capital_amount"] = float(amount) * (10000 if unit == "万" else 100000000)
        
        legal = re.search(r'法定代表人[：:]\s*([^\s\n<>]{2,20})', html)
        if legal:
            data["legal_representative"] = legal.group(1).strip()
        
        date = re.search(r'成立日期[：:]?\s*(\d{4}[-/年]\d{1,2}[-/月]?\d{0,2}日?)', html)
        if date:
            data["established_date"] = date.group(1)
        
        credit = re.search(r'统一社会信用代码[：:]?\s*([A-Z0-9]{18})', html)
        if credit:
            data["credit_code"] = credit.group(1)
        
        # 解析股东信息
        shareholders = re.findall(r'股东名称[：:]?\s*([^\n<>]+?)(?=\s*持股)', html)
        if shareholders:
            data["shareholders"] = [
                {"name": s.strip(), "ratio": "未知", "type": "未知"}
                for s in shareholders[:5]
            ]
        
        data["fetched_at"] = datetime.now().isoformat()
        data["source"] = "auto_scrape"
        
        return data
    
    def _manual_fallback(self, company_name):
        """手动采集回退方案"""
        return {
            "success": False,
            "error": "需要手动采集",
            "manual_instructions": {
                "company": company_name,
                "platforms": [
                    {
                        "name": "天眼查",
                        "url": f"https://www.tianyancha.com/search?key={quote(company_name)}",
                        "priority": 1
                    },
                    {
                        "name": "企查查",
                        "url": f"https://www.qcc.com/search?key={quote(company_name)}",
                        "priority": 2
                    },
                    {
                        "name": "国家公示系统",
                        "url": "https://www.gsxt.gov.cn/",
                        "priority": 3,
                        "note": "需要精确搜索"
                    }
                ],
                "fields_to_collect": [
                    "公司全称",
                    "法定代表人",
                    "注册资本",
                    "成立日期",
                    "统一社会信用代码",
                    "股东信息（名称、持股比例）"
                ],
                "save_to": str(self.data_dir / f"{company_name}.json")
            },
            "usage_report": self.get_usage_report()
        }
    
    def save_snapshot(self, company_name, data):
        """保存快照"""
        data["fetched_at"] = datetime.now().isoformat()
        
        filepath = self.data_dir / f"{company_name}.json"
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        return filepath


# CLI 接口
async def main():
    import sys
    
    rotator = FreePlatformRotator()
    
    if len(sys.argv) > 1:
        command = sys.argv[1]
        
        if command == "status":
            print(rotator.get_usage_report())
        
        elif command == "scrape" and len(sys.argv) > 2:
            company_name = sys.argv[2]
            print(f"🔍 采集企业: {company_name}")
            
            result = await rotator.scrape_company(company_name)
            
            if result["success"]:
                print(f"✅ 采集成功 (来源: {result['source']})")
                rotator.save_snapshot(company_name, result["data"])
                print(json.dumps(result["data"], indent=2, ensure_ascii=False))
            else:
                print(f"❌ {result['error']}")
                if "manual_instructions" in result:
                    print("\n📋 手动采集指南:")
                    for platform in result["manual_instructions"]["platforms"]:
                        print(f"  {platform['priority']}. {platform['name']}: {platform['url']}")
        
        else:
            print("""
用法:
  python3 scraper_free.py status          # 查看使用统计
  python3 scraper_free.py scrape <公司名>  # 采集企业信息
            """)
    else:
        print(rotator.get_usage_report())


if __name__ == "__main__":
    asyncio.run(main())
