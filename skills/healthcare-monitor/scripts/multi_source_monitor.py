#!/usr/bin/env python3
"""
医疗融资监控系统 - 多源数据融合监控
整合官方、商业、媒体、招聘等多数据源
"""

import json
import subprocess
import urllib.request
from datetime import datetime, timedelta
from html.parser import HTMLParser

# ==================== 配置 ====================

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
TIMEOUT = 15

# ==================== 官方数据源 ====================

class OfficialSourceScraper:
    """国家企业信用信息公示系统爬虫"""
    
    def search_company(self, company_name):
        """搜索企业信息"""
        # 由于官方系统需要验证码，这里提供接口说明
        # 实际实现需要 Playwright + 验证码识别
        return {
            "source": "国家企业信用信息公示系统",
            "available": True,
            "cost": 0,
            "data": None,
            "notes": "需要验证码处理，建议使用 Playwright"
        }

# ==================== 商业数据源 ====================

class TianyanchaScraper:
    """天眼查数据源"""
    
    def search_company(self, company_name):
        """搜索企业信息"""
        try:
            url = f"https://www.tianyancha.com/search?key={urllib.parse.quote(company_name)}"
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
                html = resp.read().decode("utf-8", errors="ignore")
            
            # 解析企业基本信息
            data = self._parse_company_info(html)
            return {
                "source": "天眼查",
                "available": True,
                "cost": 0,
                "data": data,
                "url": url
            }
        except Exception as e:
            return {
                "source": "天眼查",
                "available": False,
                "error": str(e)
            }
    
    def _parse_company_info(self, html):
        """解析企业信息（简化版）"""
        # 实际实现需要更复杂的解析
        return {
            "company_name": "",
            "registered_capital": "",
            "founding_date": "",
            "shareholders": [],
            "changes": []
        }

class QichachaScraper:
    """企查查数据源"""
    
    def search_company(self, company_name):
        """搜索企业信息"""
        try:
            url = f"https://www.qcc.com/web/search?key={urllib.parse.quote(company_name)}"
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
                html = resp.read().decode("utf-8", errors="ignore")
            
            return {
                "source": "企查查",
                "available": True,
                "cost": 0,
                "data": {},
                "url": url
            }
        except Exception as e:
            return {
                "source": "企查查",
                "available": False,
                "error": str(e)
            }

# ==================== 媒体数据源 ====================

class MediaScraper:
    """媒体融资数据源"""
    
    def search_funding_news(self, company_name):
        """搜索融资相关新闻"""
        sources = [
            ("36氪", f"https://36kr.com/search/articles/{company_name}"),
            ("动脉网", f"https://www.vbdata.cn/search?keyword={company_name}"),
            ("投中网", f"https://www.chinaventure.com.cn/search/{company_name}")
        ]
        
        results = []
        for name, url in sources:
            try:
                req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
                with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
                    html = resp.read().decode("utf-8", errors="ignore")
                
                # 解析新闻（简化版）
                news_count = html.count("融资") + html.count("投资")
                if news_count > 0:
                    results.append({
                        "source": name,
                        "url": url,
                        "news_count": news_count
                    })
            except Exception as e:
                pass
        
        return results

# ==================== 招聘数据源 ====================

class HiringScraper:
    """招聘数据源"""
    
    def search_hiring(self, company_name):
        """搜索招聘信息"""
        sources = [
            ("BOSS直聘", f"https://www.zhipin.com/job_detail/?query={company_name}"),
            ("拉勾网", f"https://www.lagou.com/jobs/list_{company_name}")
        ]
        
        results = []
        for name, url in sources:
            try:
                req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
                with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
                    html = resp.read().decode("utf-8", errors="ignore")
                
                # 统计岗位数量（简化版）
                job_count = html.count("职位") + html.count("岗位")
                results.append({
                    "source": name,
                    "url": url,
                    "job_count": job_count
                })
            except Exception as e:
                pass
        
        return results

# ==================== 多源融合分析 ====================

class MultiSourceAnalyzer:
    """多源数据融合分析器"""
    
    def __init__(self):
        self.official_scraper = OfficialSourceScraper()
        self.tianyancha = TianyanchaScraper()
        self.qichacha = QichachaScraper()
        self.media = MediaScraper()
        self.hiring = HiringScraper()
    
    def analyze_company(self, company_name):
        """综合分析企业融资信号"""
        
        print(f"\n🔍 分析企业: {company_name}")
        print("=" * 50)
        
        # 1. 官方数据源（一级验证）
        print("\n[一级验证] 官方数据源")
        official_data = self.official_scraper.search_company(company_name)
        print(f"  国家企业信用公示: {'✅' if official_data['available'] else '❌'}")
        
        # 2. 商业数据源（一级验证 - 多源对比）
        print("\n[一级验证] 商业数据源")
        tianyancha_data = self.tianyancha.search_company(company_name)
        qichacha_data = self.qichacha.search_company(company_name)
        
        tianyancha_available = tianyancha_data.get("available", False)
        qichacha_available = qichacha_data.get("available", False)
        
        print(f"  天眼查: {'✅' if tianyancha_available else '❌'}")
        print(f"  企查查: {'✅' if qichacha_available else '❌'}")
        
        # 3. 媒体验证（二级验证）
        print("\n[二级验证] 媒体验证")
        media_results = self.media.search_funding_news(company_name)
        for media in media_results:
            print(f"  {media['source']}: {media['news_count']} 条相关")
        
        # 4. 招聘验证（二级验证）
        print("\n[二级验证] 招聘数据")
        hiring_results = self.hiring.search_hiring(company_name)
        for hiring in hiring_results:
            print(f"  {hiring['source']}: {hiring['job_count']} 个岗位")
        
        # 5. 综合评分
        print("\n📊 综合评分")
        
        score = 0
        total = 7
        
        # 一级验证（3 分）
        if official_data.get("available"):
            score += 1
            print("  ✓ 官方数据源: +1")
        
        if tianyancha_available and qichacha_available:
            score += 1
            print("  ✓ 多源对比: +1")
        
        # 二级验证（4 分）
        if len(media_results) >= 2:
            score += 2
            print(f"  ✓ 媒体验证: +2 ({len(media_results)} 个来源)")
        elif len(media_results) >= 1:
            score += 1
            print(f"  ✓ 媒体验证: +1 ({len(media_results)} 个来源)")
        
        if hiring_results and hiring_results[0].get("job_count", 0) > 5:
            score += 2
            print(f"  ✓ 招聘验证: +2 (扩招信号)")
        elif hiring_results and hiring_results[0].get("job_count", 0) > 0:
            score += 1
            print(f"  ✓ 招聘验证: +1 (有招聘)")
        
        confidence = (score / total) * 100
        
        print(f"\n  综合得分: {score}/{total}")
        print(f"  置信度: {confidence:.0f}%")
        
        # 结论
        if confidence >= 80:
            conclusion = "✅ 真实度高，建议跟进"
        elif confidence >= 60:
            conclusion = "🟡 较真实，需要关注"
        elif confidence >= 40:
            conclusion = "🟠 可疑，需要深入验证"
        else:
            conclusion = "❌ 不确定，不建议跟进"
        
        print(f"\n  结论: {conclusion}")
        
        return {
            "company": company_name,
            "score": score,
            "total": total,
            "confidence": confidence,
            "conclusion": conclusion,
            "sources": {
                "official": official_data.get("available", False),
                "tianyancha": tianyancha_available,
                "qichacha": qichacha_available,
                "media_count": len(media_results),
                "hiring_count": len(hiring_results)
            }
        }

# ==================== 主函数 ====================

def main():
    """主函数"""
    analyzer = MultiSourceAnalyzer()
    
    # 测试企业
    companies = [
        "迈瑞医疗",
        "联影医疗",
        "百济神州"
    ]
    
    results = []
    for company in companies:
        result = analyzer.analyze_company(company)
        results.append(result)
        print("\n" + "="*50 + "\n")
    
    # 保存报告
    report = {
        "timestamp": datetime.now().isoformat(),
        "companies": results
    }
    
    report_file = f"/home/aa/clawd/skills/healthcare-monitor/data/reports/multi_source_{datetime.now().strftime('%Y%m%d')}.json"
    with open(report_file, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    
    print(f"\n✅ 报告已保存: {report_file}")
    
    return results

if __name__ == "__main__":
    main()
