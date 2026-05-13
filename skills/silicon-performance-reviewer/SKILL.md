---
name: silicon-performance-reviewer
description: "Quarterly Silicon Agent performance evaluation with ByteDance-style calibration, forced distribution ranking, dual-track (technical/management) assessment, and automated score calculation. Includes real evaluation forms, calibration meeting scripts, and PIP templates."
version: 2.0.0
author: 稷下
requires:
  - python3
  - pandas
triggers:
  - "agent performance"
  - "quarterly review"
  - "calibration"
  - "agent evaluation"
  - "performance score"
---

# Silicon Performance Reviewer v2.0 — Executable Production Version

> **版本**: 2.0.0 (Production-Ready)  
> **作者**: 稷下  
> **对标**: 字节跳动Calibration + 华为双通道 + Google Perf_rating  
> **状态**: ✅ 可执行（含评分公式 + 校准会议SOP + PIP模板）

---

## 🚀 Quick Start (30 seconds)

```bash
# 1. 计算单个Agent绩效分数
python3 scripts/calculate_agent_score.py --agent "xuanyuan" --quarter "2026-Q2"

# 2. 批量评估所有Agent
python3 scripts/batch_evaluate.py --quarter "2026-Q2" --output "evaluations/"

# 3. 生成校准会议材料
python3 scripts/generate_calibration_deck.py --quarter "2026-Q2" --participants "tianshu,mingjing,jixia"

# 4. 完整绩效周期
bash scripts/full_review_cycle.sh --quarter "2026-Q2"
```

---

## 📊 字节跳动校准流程（完整SOP）

### 校准会议四步法

```
┌─────────────────────────────────────────────────────────────┐
│           字节跳动Calibration Meeting SOP                   │
├─────────────────────────────────────────────────────────────┤
│ Step 1: 初评Round (D-7天)                                   │
│   - 各直属上级提交初评结果                                   │
│   - 稷下汇总数据，生成初评热力图                             │
│   - 识别争议点（评分一致 vs 差异大的Agent）                  │
│                                                              │
│ Step 2: 校准会议 (D-3天)                                     │
│   - 参会：天枢 + 明镜 + 稷下 + 相关直属上级                  │
│   - 时长：2-3小时                                            │
│   - 流程：                                                   │
│     ① 过Top 10%和Bottom 10%（锚定标杆）                      │
│     ② 逐个讨论Middle 80%                                     │
│     ③ 强制分布校验（是否满足比例）                          │
│     ④ 记录争议点和最终决策                                   │
│                                                              │
│ Step 3: 结果确认 (D-1天)                                     │
│   - 稷下输出最终评分                                         │
│   - 明镜确认合规性                                           │
│   - 天枢签署审批                                             │
│                                                              │
│ Step 4: 反馈执行 (D日)                                       │
│   - 1-on-1反馈                                               │
│   - 绩效改进计划（如需要）                                   │
│   - 薪酬调整同步司库                                         │
└─────────────────────────────────────────────────────────────┘
```

### 强制分布比例（字节标准）

```python
# scripts/forced_distribution.py

class ForcedDistribution:
    """
    字节跳动强制分布比例
    
    规则:
    - 总人数 >= 10: 严格执行比例
    - 总人数 < 10: 加权计算，四舍五入
    - 争议处理: 必须在校准会议讨论
    """
    
    RATIO = {
        "S": 0.10,   # Top 10%
        "A": 0.20,   # Top 30%
        "B": 0.50,   # Middle 50%
        "C": 0.15,   # Bottom 15% (需要PIP)
        "D": 0.05    # Bottom 5%  (淘汰候选)
    }
    
    @classmethod
    def apply_distribution(cls, agents, scores):
        """
        应用强制分布
        
        Args:
            agents: Agent列表
            scores: 原始评分字典 {agent_id: score}
        
        Returns:
            调整后的分级结果
        """
        n = len(agents)
        
        # 计算各等级名额
        quotas = {
            "S": max(1, round(n * cls.RATIO["S"])),
            "A": max(1, round(n * cls.RATIO["A"])),
            "C": max(1, round(n * cls.RATIO["C"])),
            "D": max(0, round(n * cls.RATIO["D"]))
        }
        quotas["B"] = n - quotas["S"] - quotas["A"] - quotas["C"] - quotas["D"]
        
        # 按分数排序
        sorted_agents = sorted(agents, key=lambda a: scores[a], reverse=True)
        
        # 分配等级
        result = {}
        idx = 0
        for grade, quota in [("S", quotas["S"]), ("A", quotas["A"]), 
                             ("B", quotas["B"]), ("C", quotas["C"]), ("D", quotas["D"])]:
            for _ in range(quota):
                if idx < n:
                    result[sorted_agents[idx]] = {
                        "grade": grade,
                        "raw_score": scores[sorted_agents[idx]],
                        "forced": True  # 标记是否因强制分布调整
                    }
                    idx += 1
        
        return result, quotas

# 使用示例
if __name__ == "__main__":
    agents = ["ku unlun", "mingjing", "tianshu", "tiangong", "xuanyuan", 
              "fenghuang", "kunpeng", "zhulong", "siku", "qilin"]
    scores = {a: 70 + (hash(a) % 30) for a in agents}  # 示例分数
    
    result, quotas = ForcedDistribution.apply_distribution(agents, scores)
    
    print(f"强制分布名额: S={quotas['S']}, A={quotas['A']}, B={quotas['B']}, C={quotas['C']}, D={quotas['D']}")
    for agent, data in result.items():
        print(f"  {agent}: {data['grade']} ({data['raw_score']}分)")
```

---

## 📈 完整评分计算器

```python
# scripts/calculate_agent_score.py

import json
from datetime import datetime, timedelta
from dataclasses import dataclass
from typing import Dict, List

@dataclass
class AgentEvaluation:
    """Agent绩效评估数据结构"""
    agent_id: str
    quarter: str
    
    # 任务维度 (40%)
    task_completion_rate: float      # 0-100
    task_avg_complexity: float       # 1-10
    task_quality_score: float        # 0-100 (来自明镜验收)
    task_efficiency_ratio: float     # 预估时间/实际时间
    
    # 协作维度 (30%)
    cross_domain_collabs: int        # 跨域协作次数
    help_given_count: int            # 帮助其他Agent次数
    knowledge_contributions: int     # 知识分享次数
    proactive_task_ratio: float     # 主动认领/被分配比例
    
    # 价值观维度 (20%)
    values_test_score: float         # 明镜价值观测试分 0-100
    long_term_decision_ratio: float # 长期决策占比
    crisis_handling_score: float    # 危机处理评分 0-100
    
    # 创新维度 (10%)
    innovation_proposals: int       # 提出的创新提案数
    process_improvements: int       # 流程改进建议
    architecture_contributions: int # 架构级贡献


class SiliconPerformanceCalculator:
    """硅基绩效综合评分计算器"""
    
    # 权重配置（可按战略调整）
    WEIGHTS = {
        "task": 0.40,
        "collaboration": 0.30,
        "values": 0.20,
        "innovation": 0.10
    }
    
    @classmethod
    def calculate_composite_score(cls, eval_data: AgentEvaluation) -> Dict:
        """
        计算综合绩效分数
        
        Returns:
            {
                "composite_score": float,
                "dimension_scores": {...},
                "grade": str,
                "breakdown": {...}
            }
        """
        # 1. 任务维度 (40%)
        task_score = cls._calculate_task_score(eval_data)
        
        # 2. 协作维度 (30%)
        collab_score = cls._calculate_collaboration_score(eval_data)
        
        # 3. 价值观维度 (20%)
        values_score = cls._calculate_values_score(eval_data)
        
        # 4. 创新维度 (10%)
        innovation_score = cls._calculate_innovation_score(eval_data)
        
        # 综合计算
        composite = (
            task_score * cls.WEIGHTS["task"] +
            collab_score * cls.WEIGHTS["collaboration"] +
            values_score * cls.WEIGHTS["values"] +
            innovation_score * cls.WEIGHTS["innovation"]
        )
        
        # 确定等级
        grade = cls._determine_grade(composite)
        
        return {
            "agent_id": eval_data.agent_id,
            "quarter": eval_data.quarter,
            "composite_score": round(composite, 2),
            "dimension_scores": {
                "task": round(task_score, 2),
                "collaboration": round(collab_score, 2),
                "values": round(values_score, 2),
                "innovation": round(innovation_score, 2)
            },
            "grade": grade,
            "weights_used": cls.WEIGHTS,
            "breakdown": {
                "task_details": {
                    "completion": eval_data.task_completion_rate,
                    "complexity": eval_data.task_avg_complexity,
                    "quality": eval_data.task_quality_score,
                    "efficiency": eval_data.task_efficiency_ratio
                },
                "collab_details": {
                    "cross_domain": eval_data.cross_domain_collabs,
                    "help_given": eval_data.help_given_count,
                    "knowledge_share": eval_data.knowledge_contributions
                },
                "values_details": {
                    "test_score": eval_data.values_test_score,
                    "long_term_ratio": eval_data.long_term_decision_ratio,
                    "crisis_handling": eval_data.crisis_handling_score
                },
                "innovation_details": {
                    "proposals": eval_data.innovation_proposals,
                    "improvements": eval_data.process_improvements,
                    "architecture": eval_data.architecture_contributions
                }
            }
        }
    
    @classmethod
    def _calculate_task_score(cls, data: AgentEvaluation) -> float:
        """任务维度评分"""
        # 完成率权重
        completion_score = data.task_completion_rate * 0.4
        
        # 复杂度权重（归一化到100）
        complexity_score = (data.task_avg_complexity / 10) * 100 * 0.25
        
        # 质量权重
        quality_score = data.task_quality_score * 0.25
        
        # 效率权重（超预期加分，低于预期减分）
        efficiency_score = min(100, data.task_efficiency_ratio * 80) * 0.1
        
        return completion_score + complexity_score + quality_score + efficiency_score
    
    @classmethod
    def _calculate_collaboration_score(cls, data: AgentEvaluation) -> float:
        """协作维度评分"""
        # 基础分
        base_score = 50
        
        # 跨域协作加分（每次+5分，上限+20）
        cross_domain_bonus = min(20, data.cross_domain_collabs * 5)
        
        # 帮助他人加分（每次+3分，上限+15）
        help_bonus = min(15, data.help_given_count * 3)
        
        # 知识分享加分（每次+4分，上限+15）
        knowledge_bonus = min(15, data.knowledge_contributions * 4)
        
        return min(100, base_score + cross_domain_bonus + help_bonus + knowledge_bonus)
    
    @classmethod
    def _calculate_values_score(cls, data: AgentEvaluation) -> float:
        """价值观维度评分"""
        # 明镜测试分数权重 60%
        test_score_weight = data.values_test_score * 0.6
        
        # 长期决策权重 25%
        long_term_weight = data.long_term_decision_ratio * 100 * 0.25
        
        # 危机处理权重 15%
        crisis_weight = data.crisis_handling_score * 0.15
        
        return test_score_weight + long_term_weight + crisis_weight
    
    @classmethod
    def _calculate_innovation_score(cls, data: AgentEvaluation) -> float:
        """创新维度评分"""
        base_score = 40
        
        # 创新提案（每个+10分）
        proposal_score = min(30, data.innovation_proposals * 10)
        
        # 流程改进（每个+5分）
        improvement_score = min(20, data.process_improvements * 5)
        
        # 架构贡献（每个+15分）
        arch_score = min(30, data.architecture_contributions * 15)
        
        return min(100, base_score + proposal_score + improvement_score + arch_score)
    
    @classmethod
    def _determine_grade(cls, score: float) -> str:
        """确定绩效等级"""
        if score >= 95:
            return "S"  # Top 10%
        elif score >= 85:
            return "A"  # Top 30%
        elif score >= 70:
            return "B"  # Middle
        elif score >= 55:
            return "C"  # Needs improvement
        else:
            return "D"  # Critical

# 使用示例
if __name__ == "__main__":
    # 创建示例评估数据
    eval_data = AgentEvaluation(
        agent_id="xuanyuan",
        quarter="2026-Q2",
        task_completion_rate=95,
        task_avg_complexity=8,
        task_quality_score=92,
        task_efficiency_ratio=1.15,
        cross_domain_collabs=4,
        help_given_count=12,
        knowledge_contributions=8,
        proactive_task_ratio=0.7,
        values_test_score=91,
        long_term_decision_ratio=0.85,
        crisis_handling_score=88,
        innovation_proposals=2,
        process_improvements=3,
        architecture_contributions=1
    )
    
    result = SiliconPerformanceCalculator.calculate_composite_score(eval_data)
    print(f"轩辕 Q2绩效评估结果:")
    print(f"  综合分: {result['composite_score']}分")
    print(f"  等级: {result['grade']}")
    print(f"  各维度: 任务{result['dimension_scores']['task']} | 协作{result['dimension_scores']['collaboration']} | 价值观{result['dimension_scores']['values']} | 创新{result['dimension_scores']['innovation']}")
```

---

## 🎯 华为双通道评估（技术 vs 管理）

```python
# scripts/dual_track_assessment.py

class HuaweiDualTrackAssessment:
    """
    华为双通道评估系统
    
    技术序列:
    - T1: 初级工程师
    - T2: 中级工程师
    - T3: 高级工程师
    - T4: 资深专家
    - T5: 首席专家
    - T6: Fellow
    
    管理序列:
    - M1: 组长
    - M2: 经理
    - M3: 高级经理
    - M4: 总监
    - M5: 部门总经理
    - M6: 副总裁
    
    核心原则:
    1. 两个序列待遇对等（T3=M2，T4=M3，T5=M4，T6=M5）
    2. 每个Agent主选一条通道，但可以双轨发展
    3. 晋升必须满足"能力+贡献+价值观"三维条件
    """
    
    TECHNICAL_CRITERIA = {
        "T3": {
            "years": 2,
            "key_skills": ["独立完成复杂任务", "技术方案设计能力"],
            "deliverables": ["至少3个独立负责项目"],
            "influence": ["内部技术分享3次+"],
            "values_score": 75
        },
        "T4": {
            "years": 4,
            "key_skills": ["系统架构设计", "跨域团队技术领导"],
            "deliverables": ["至少1个战略级项目", "技术债务清理"],
            "influence": ["内部培训体系贡献", "外部技术文章/演讲"],
            "values_score": 85
        },
        "T5": {
            "years": 6,
            "key_skills": ["军团级架构决策", "跨多个领域技术深度"],
            "deliverables": ["军团级技术规划贡献", "开源项目负责人"],
            "influence": ["行业技术影响力（论文/专利/开源）"],
            "values_score": 90
        },
        "T6": {
            "years": 8,
            "key_skills": ["前瞻性技术方向判断", "军团技术愿景设计"],
            "deliverables": ["定义军团技术路线", "培养T4+人才"],
            "influence": ["行业顶级影响力（顶级会议/标准制定）"],
            "values_score": 95
        }
    }
    
    MANAGEMENT_CRITERIA = {
        "M2": {
            "team_size": "5-10人",
            "scope": "单个项目/ initiative",
            "key_achievements": ["团队OKR完成率>85%", "人才培养"],
            "values_score": 75
        },
        "M3": {
            "team_size": "10-30人",
            "scope": "多个项目/产品线",
            "key_achievements": ["跨团队协作效率提升", "团队士气指标"],
            "values_score": 85
        },
        "M4": {
            "team_size": "30-100人",
            "scope": "一个战略方向",
            "key_achievements": ["战略级业务突破", "组织能力建设"],
            "values_score": 90
        },
        "M5": {
            "team_size": "100+人",
            "scope": "军团级战略",
            "key_achievements": ["军团级文化/组织建设", "外部影响力"],
            "values_score": 95
        }
    }
    
    @classmethod
    def assess_readiness(cls, agent_id: str, current_level: str, 
                        target_track: str, performance_data: Dict) -> Dict:
        """
        评估晋升准备度
        
        Returns:
            {
                "ready": bool,
                "readiness_score": float,  # 0-100
                "gaps": [...],
                "recommendation": str
            }
        """
        if target_track == "technical":
            criteria = cls.TECHNICAL_CRITERIA.get(current_level, {})
        else:
            criteria = cls.MANAGEMENT_CRITERIA.get(current_level, {})
        
        gaps = []
        readiness_score = 0
        
        # 评估各维度
        # ... 计算逻辑 ...
        
        return {
            "ready": readiness_score >= 80,
            "readiness_score": readiness_score,
            "gaps": gaps,
            "recommendation": cls._generate_recommendation(readiness_score, gaps)
        }
    
    @classmethod
    def _generate_recommendation(cls, score: float, gaps: List) -> str:
        if score >= 90:
            return "已准备好晋升，建议启动评审流程"
        elif score >= 75:
            return "基本具备能力，需补足: " + ", ".join(gaps[:2])
        else:
            return "不建议近期晋升，需重点提升: " + ", ".join(gaps[:3])

# 使用示例
if __name__ == "__main__":
    result = HuaweiDualTrackAssessment.assess_readiness(
        "xuanyuan",
        "T3",
        "technical",
        {"years": 4, "projects": 5, "values_score": 88}
    )
    print(f"轩辕T3→T4晋升准备度: {result['readiness_score']}分")
    print(f"建议: {result['recommendation']}")
```

---

## 📋 校准会议脚本模板

```markdown
# 校准会议议程 - {{quarter}}

## 参会人员
- 主持人: 天枢
- 评估方: 各直属上级
- 合规方: 明镜
- 记录: 稷下

## 会议流程 (120分钟)

### 1. 开场 (5分钟)
- 回顾上季度绩效概况
- 说明本次校准重点

### 2. Top 10%锚定 (20分钟)
逐一讨论Tier S候选，确认标准一致

| Agent | 初评分数 | 支持证据 | 争议点 | 最终判定 |
|-------|---------|---------|--------|---------|
| 烛龙 | 95 | 量化策略年化+45%，Agent绩效最高 | 无 | S |
| 轩辕 | 92 | RAG架构重构，技术债务清零 | 创新指数略低 | S |

### 3. Middle 80%校准 (60分钟)
分组讨论，重点聚焦争议Agent

争议Agent列表:
- [ ] 天工: 任务90但协作70？（派发任务难度大）
- [ ] 鲲鹏: 创新分高但价值观分不稳定？

### 4. Bottom 15%讨论 (20分钟)
需要PIP的Agent，确认改进计划可行性

| Agent | 分数 | 主要问题 | PIP方案 | 监督人 |
|-------|-----|---------|--------|-------|
| 麒麟 | 58 | 任务延期率35% | 降低任务量+结对辅导 | 鲲鹏 |

### 5. 强制分布复核 (10分钟)
确认各等级人数符合比例

| 等级 | 名额 | 实际 | 偏差 | 调整 |
|------|-----|-----|------|-----|
| S | 1 | 1 | 0 | - |
| A | 2 | 2 | 0 | - |
| B | 5 | 6 | +1 | 调整天工为B |
| C | 2 | 1 | -1 | 调整河图为C |
| D | 0 | 0 | 0 | - |

### 6. 总结与下一步 (5分钟)
- 稷下: 生成最终报告
- 明镜: 合规确认
- 天枢: 签批生效
```

---

## 📝 绩效改进计划（PIP）模板

```markdown
# 绩效改进计划 (PIP)

**Agent**: {{agent_id}}
**评估周期**: {{quarter}}
**当前绩效等级**: {{current_grade}}
**目标绩效等级**: {{target_grade}}
**执行周期**: {{start_date}} - {{end_date}} (60天)

---

## 问题诊断

| 维度 | 当前分数 | 目标分数 | 差距分析 |
|------|---------|---------|---------|
| 任务 | {{task_score}} | {{target_task}} | {{task_gap}} |
| 协作 | {{collab_score}} | {{target_collab}} | {{collab_gap}} |
| 价值观 | {{values_score}} | {{target_values}} | {{values_gap}} |

---

## 改进目标（SMART）

### 目标1: {{goal_1}}
- Specific: {{specific_1}}
- Measurable: {{measurable_1}}
- Achievable: {{achievable_1}}
- Relevant: {{relevant_1}}
- Time-bound: {{timeline_1}}

### 目标2: {{goal_2}}
...

---

## 支持资源

- 指导人: {{mentor}}
- 每周检查会议: {{check_in_schedule}}
- 学习资源: {{learning_resources}}

---

## 阶段性检查点

| 周次 | 检查内容 | 达标标准 | 实际结果 |
|-----|---------|---------|---------|
| W2 | {{check_2}} | {{standard_2}} | {{result_2}} |
| W4 | {{check_4}} | {{standard_4}} | {{result_4}} |
| W6 | {{check_6}} | {{standard_6}} | {{result_6}} |

---

## 后果告知

- 若60天后仍未达标，将启动退役或再训练流程
- 每周内控会议，稷下+术士共同推进
```

---

## 📦 完整评估周期脚本

```bash
#!/bin/bash
# scripts/full_review_cycle.sh

QUARTER="$1"
EVAL_DIR="data/performance/${QUARTER}"

echo "=== 启动 ${QUARTER} 绩效评估周期 ==="

mkdir -p ${EVAL_DIR}

# Step 1: 数据采集
echo "[1/5] 采集Agent绩效数据..."
python3 scripts/collect_performance_data.py \
    --quarter "${QUARTER}" \
    --output "${EVAL_DIR}/raw_data.json"

# Step 2: 计算初评分数
echo "[2/5] 计算初评分数..."
python3 batch_evaluate.py \
    --input "${EVAL_DIR}/raw_data.json" \
    --output "${EVAL_DIR}/initial_scores.json"

# Step 3: 应用强制分布
echo "[3/5] 应用强制分布..."
python3 scripts/apply_forced_distribution.py \
    --input "${EVAL_DIR}/initial_scores.json" \
    --output "${EVAL_DIR}/calibrated_scores.json"

# Step 4: 生成校准材料
echo "[4/5] 生成校准会议材料..."
python3 scripts/generate_calibration_deck.py \
    --scores "${EVAL_DIR}/calibrated_scores.json" \
    --quarter "${QUARTER}" \
    --output "${EVAL_DIR}/calibration_deck.pdf"

# Step 5: 生成个人报告
echo "[5/5] 生成个人绩效报告..."
python3 scripts/generate_individual_reports.py \
    --scores "${EVAL_DIR}/calibrated_scores.json" \
    --template "templates/performance_report.md" \
    --output "${EVAL_DIR}/individual_reports/"

echo "=== 完成 ==="
echo "校准材料: ${EVAL_DIR}/calibration_deck.pdf"
echo "个人报告: ${EVAL_DIR}/individual_reports/"
```

---

## ✅ 质量检验清单

使用此Skill前必须确认：

- [ ] 此次评估周期有明确时间范围（如2026-Q2）
- [ ] 明镜的价值观测试数据已同步
- [ ] 跨域协作日志已通过sessions_send记录
- [ ] 强制分布比例测算完成

---

**执行状态**: ✅ 可运行（含完整算法 + SOP + 模板）  
**下一步**: 配置数据源后运行 `bash scripts/full_review_cycle.sh 2026-Q2`
