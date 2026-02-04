#!/usr/bin/env python3
"""
融资信号分析器
使用规则 + LLM 判断是否为融资事件
"""

import json
import re
from datetime import datetime
from pathlib import Path


class FundingAnalyzer:
    """融资信号分析器"""
    
    def __init__(self):
        self.config = self._load_config()
        self.signals = self.config.get("funding_signals", {})
    
    def _load_config(self):
        """加载配置"""
        config_path = Path(__file__).parent.parent / "config" / "settings.json"
        with open(config_path, "r", encoding="utf-8") as f:
            return json.load(f)
    
    def analyze(self, company_name, changes, current_data):
        """
        分析变更是否为融资信号
        
        Args:
            company_name: 公司名称
            changes: 变更列表
            current_data: 当前公司数据
        
        Returns:
            {
                "is_funding": bool,
                "confidence": int (0-100),
                "round_estimate": str,
                "amount_estimate": str,
                "investors": list,
                "signals": list,
                "analysis": str
            }
        """
        
        result = {
            "is_funding": False,
            "confidence": 0,
            "round_estimate": None,
            "amount_estimate": None,
            "investors": [],
            "signals": [],
            "analysis": ""
        }
        
        # 1. 规则分析
        score = 0
        signals = []
        
        for change in changes:
            change_type = change.get("type")
            
            # 注册资本变更
            if change_type == "capital_change":
                old_capital = self._parse_capital(change.get("old", "0"))
                new_capital = self._parse_capital(change.get("new", "0"))
                
                if old_capital > 0:
                    increase_pct = (new_capital - old_capital) / old_capital * 100
                    
                    if increase_pct >= 10:
                        score += self.signals["strong"]["capital_increase_over_10pct"]
                        signals.append({
                            "type": "capital_increase",
                            "description": f"注册资本增加 {increase_pct:.1f}%",
                            "weight": self.signals["strong"]["capital_increase_over_10pct"]
                        })
                    else:
                        score += self.signals["weak"]["capital_increase_only"]
                        signals.append({
                            "type": "capital_increase_small",
                            "description": f"注册资本小幅增加 {increase_pct:.1f}%",
                            "weight": self.signals["weak"]["capital_increase_only"]
                        })
            
            # 新增股东
            elif change_type == "new_shareholders":
                new_shareholders = change.get("shareholders", [])
                
                for shareholder in new_shareholders:
                    if self._is_institutional(shareholder):
                        score += self.signals["strong"]["new_institutional_shareholder"]
                        signals.append({
                            "type": "new_institutional_shareholder",
                            "description": f"新增机构股东: {shareholder}",
                            "weight": self.signals["strong"]["new_institutional_shareholder"]
                        })
                        result["investors"].append(shareholder)
                    else:
                        score += self.signals["medium"]["new_individual_shareholder"]
                        signals.append({
                            "type": "new_individual_shareholder",
                            "description": f"新增自然人股东: {shareholder}",
                            "weight": self.signals["medium"]["new_individual_shareholder"]
                        })
        
        # 2. 计算置信度
        result["confidence"] = min(score, 100)
        result["signals"] = signals
        
        # 3. 判断是否为融资
        threshold = self.config["alert_threshold"]["confidence"]
        result["is_funding"] = result["confidence"] >= threshold
        
        # 4. 推断融资轮次
        if result["is_funding"]:
            result["round_estimate"] = self._estimate_round(current_data, changes)
            result["amount_estimate"] = self._estimate_amount(changes)
        
        # 5. 生成分析文本
        result["analysis"] = self._generate_analysis(company_name, result)
        
        return result
    
    def _parse_capital(self, capital_str):
        """解析注册资本"""
        if not capital_str:
            return 0
        
        match = re.search(r'([\d.]+)', str(capital_str))
        if not match:
            return 0
        
        amount = float(match.group(1))
        
        if '亿' in str(capital_str):
            amount *= 100000000
        elif '万' in str(capital_str):
            amount *= 10000
        
        return int(amount)
    
    def _is_institutional(self, name):
        """判断是否为机构股东"""
        keywords = [
            '投资', '资本', '基金', '创投', '创业投资',
            'Capital', 'Venture', 'Investment', 'Fund',
            '合伙企业', '有限合伙', 'LP', 'GP',
            '控股', '集团', '资产管理'
        ]
        return any(kw in name for kw in keywords)
    
    def _estimate_round(self, current_data, changes):
        """推断融资轮次"""
        # 基于公司成立年限
        established = current_data.get("established_date", "")
        if established:
            try:
                est_year = int(established[:4])
                current_year = datetime.now().year
                age = current_year - est_year
                
                if age <= 2:
                    return "种子轮/天使轮"
                elif age <= 4:
                    return "A轮"
                elif age <= 6:
                    return "B轮"
                else:
                    return "C轮+"
            except:
                pass
        
        # 基于注册资本增幅
        for change in changes:
            if change.get("type") == "capital_change":
                old = self._parse_capital(change.get("old", "0"))
                new = self._parse_capital(change.get("new", "0"))
                if old > 0:
                    increase_pct = (new - old) / old * 100
                    if increase_pct >= 30:
                        return "A轮"
                    elif increase_pct >= 15:
                        return "B轮"
                    else:
                        return "C轮+"
        
        return "未知轮次"
    
    def _estimate_amount(self, changes):
        """推断融资金额"""
        for change in changes:
            if change.get("type") == "capital_change":
                old = self._parse_capital(change.get("old", "0"))
                new = self._parse_capital(change.get("new", "0"))
                increase = new - old
                
                if increase > 0:
                    # 注册资本增加通常是融资金额的 10-30%
                    min_amount = increase * 3
                    max_amount = increase * 10
                    
                    return f"{self._format_amount(min_amount)} - {self._format_amount(max_amount)}"
        
        return "未知"
    
    def _format_amount(self, amount):
        """格式化金额"""
        if amount >= 100000000:
            return f"{amount / 100000000:.1f}亿"
        elif amount >= 10000:
            return f"{amount / 10000:.0f}万"
        else:
            return f"{amount:.0f}元"
    
    def _generate_analysis(self, company_name, result):
        """生成分析文本"""
        if not result["is_funding"]:
            return f"{company_name} 的变更不符合融资特征"
        
        lines = [
            f"**{company_name}** 疑似完成融资",
            "",
            f"**置信度**: {result['confidence']}%",
            f"**预估轮次**: {result['round_estimate']}",
            f"**预估金额**: {result['amount_estimate']}",
        ]
        
        if result["investors"]:
            lines.append(f"**投资方**: {', '.join(result['investors'])}")
        
        lines.append("")
        lines.append("**信号分析**:")
        for signal in result["signals"]:
            lines.append(f"- {signal['description']} (+{signal['weight']})")
        
        return "\n".join(lines)


def analyze_with_llm(company_name, changes, current_data):
    """
    使用 LLM 进行深度分析
    
    这个函数需要通过 OpenClaw 调用 LLM
    """
    
    prompt = f"""
分析以下企业工商变更是否为融资事件:

企业: {company_name}

变更记录:
{json.dumps(changes, ensure_ascii=False, indent=2)}

当前企业信息:
{json.dumps(current_data, ensure_ascii=False, indent=2)}

请分析:
1. 这是否为融资事件? (是/否)
2. 如果是，预估融资轮次
3. 预估融资金额
4. 可能的投资方
5. 分析依据

请以 JSON 格式返回结果。
"""
    
    return {
        "prompt": prompt,
        "instructions": "使用 OpenClaw LLM 执行此 prompt"
    }
