#!/usr/bin/env python3
"""
企业信息采集器 - 简化版
支持多种数据源，优先使用可用的
"""

import json
import os
import re
import asyncio
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

# 尝试导入 playwright
try:
    from playwright.async_api import async_playwright
    HAS_PLAYWRIGHT = True
except ImportError:
    HAS_PLAYWRIGHT = False
    print("⚠️ Playwright 未安装，部分功能不可用")


class CompanyScraper:
    """企业信息采集器"""
    
    def __init__(self):
        self.data_dir = Path(__file__).parent.parent / "data" / "snapshots"
        self.data_dir.mkdir(parents=True, exist_ok=True)
    
    async def search_company(self, name):
        """搜索企业，返回详情页URL"""
        if not HAS_PLAYWRIGHT:
            return self._manual_search_instructions(name)
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            )
            page = await context.new_page()
            
            # 尝试企查查
            try:
                url = f"https://www.qcc.com/search?key={quote(name)}"
                await page.goto(url, wait_until="domcontentloaded", timeout=20000)
                await asyncio.sleep(2)
                
                link = await page.query_selector("a[href*='/firm/']")
                if link:
                    href = await link.get_attribute("href")
                    await browser.close()
                    return {"source": "qichacha", "url": href}
            except:
                pass
            
            await browser.close()
            return None
    
    def _manual_search_instructions(self, name):
        """返回手动搜索指令"""
        return {
            "status": "manual_required",
            "instructions": f"""
## 手动采集指令

由于反爬限制，请手动采集 **{name}** 的信息：

### 方法一：天眼查
1. 访问 https://www.tianyancha.com/search?key={quote(name)}
2. 点击第一个搜索结果
3. 复制以下信息：
   - 公司全称
   - 法定代表人
   - 注册资本
   - 成立日期
   - 股东信息

### 方法二：企查查
1. 访问 https://www.qcc.com/search?key={quote(name)}
2. 同上

### 方法三：国家企业信用信息公示系统
1. 访问 https://www.gsxt.gov.cn/
2. 搜索企业名称
3. 这是官方数据源，最准确

采集后请将数据保存到：
~/clawd/skills/healthcare-monitor/data/snapshots/{name}.json
"""
        }
    
    def parse_company_data(self, raw_text):
        """从原始文本解析企业数据"""
        data = {}
        
        # 法人
        legal = re.search(r'法定代表人[：:]\s*([^\s\n]{2,20})', raw_text)
        if legal:
            data["legal_representative"] = legal.group(1).strip()
        
        # 注册资本
        capital = re.search(r'注册资本[：:]?\s*([\d,.]+)\s*(万|亿)?[元人民币]*', raw_text)
        if capital:
            amount = capital.group(1).replace(",", "")
            unit = capital.group(2) or "万"
            data["capital"] = f"{amount}{unit}"
            data["capital_amount"] = float(amount) * (10000 if unit == "万" else 100000000)
        
        # 成立日期
        date = re.search(r'成立日期[：:]?\s*(\d{4}[-/年]\d{1,2}[-/月]?\d{0,2}日?)', raw_text)
        if date:
            data["established_date"] = date.group(1)
        
        # 经营状态
        if "存续" in raw_text:
            data["status"] = "存续"
        elif "注销" in raw_text:
            data["status"] = "注销"
        elif "吊销" in raw_text:
            data["status"] = "吊销"
        
        # 统一社会信用代码
        credit = re.search(r'统一社会信用代码[：:]?\s*([A-Z0-9]{18})', raw_text)
        if credit:
            data["credit_code"] = credit.group(1)
        
        return data
    
    def save_snapshot(self, company_name, data):
        """保存企业快照"""
        data["fetched_at"] = datetime.now().isoformat()
        
        filepath = self.data_dir / f"{company_name}.json"
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        return filepath
    
    def load_snapshot(self, company_name):
        """加载企业快照"""
        filepath = self.data_dir / f"{company_name}.json"
        if filepath.exists():
            with open(filepath, "r", encoding="utf-8") as f:
                return json.load(f)
        return None
    
    def compare_snapshots(self, old_data, new_data):
        """对比两个快照，返回变更"""
        changes = []
        
        # 注册资本变更
        old_capital = old_data.get("capital_amount", 0)
        new_capital = new_data.get("capital_amount", 0)
        if old_capital and new_capital and old_capital != new_capital:
            changes.append({
                "type": "capital_change",
                "old": old_data.get("capital"),
                "new": new_data.get("capital"),
                "old_amount": old_capital,
                "new_amount": new_capital,
                "change_pct": (new_capital - old_capital) / old_capital * 100
            })
        
        # 法人变更
        old_legal = old_data.get("legal_representative")
        new_legal = new_data.get("legal_representative")
        if old_legal and new_legal and old_legal != new_legal:
            changes.append({
                "type": "legal_representative_change",
                "old": old_legal,
                "new": new_legal
            })
        
        # 状态变更
        old_status = old_data.get("status")
        new_status = new_data.get("status")
        if old_status and new_status and old_status != new_status:
            changes.append({
                "type": "status_change",
                "old": old_status,
                "new": new_status
            })
        
        return changes


def create_sample_data():
    """创建示例数据用于测试"""
    scraper = CompanyScraper()
    
    # 推想医疗的示例数据 (基于公开信息)
    sample_data = {
        "name": "推想医疗科技股份有限公司",
        "short_name": "推想医疗",
        "legal_representative": "陈宽",
        "capital": "5000万",
        "capital_amount": 50000000,
        "established_date": "2016-01-29",
        "status": "存续",
        "credit_code": "91110108MA004JXL9P",
        "address": "北京市海淀区",
        "scope": "技术开发、技术咨询、技术服务、技术转让；软件开发；计算机系统服务",
        "shareholders": [
            {"name": "陈宽", "ratio": "15.00%", "type": "自然人"},
            {"name": "北京推想科技有限公司", "ratio": "10.00%", "type": "企业法人"},
        ],
        "source": "sample_data",
        "note": "这是示例数据，用于测试系统功能"
    }
    
    filepath = scraper.save_snapshot("推想医疗", sample_data)
    print(f"✅ 示例数据已保存: {filepath}")
    
    return sample_data


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "sample":
        create_sample_data()
    else:
        scraper = CompanyScraper()
        result = scraper._manual_search_instructions("推想医疗")
        print(result["instructions"])
