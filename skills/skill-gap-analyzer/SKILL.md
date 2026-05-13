# Skill Gap Analyzer — 战略蓝图与能力矩阵缺口分析

> 版本：v1.0 | 分类：硅基人才管理 | 优先级：P0
> 作者：稷下 | 对标：华为战略解码 × 麦肯锡能力矩阵
> 触发场景：季度战略对齐 / 新战略发布 / Agent能力升级申请

---

## 核心价值

将军团战略蓝图与现有Agent能力矩阵进行对比，自动识别"能力鸿沟"，并发起招聘（硅基/碳基猎取）或培训（进化路径）需求。

---

## 华为战略解码流程对齐

华为战略规划（SP）→ 年度经营计划（BP）→ 关键岗位能力需求

稷下的三步对齐：
1. **战略解码** → 从昆仑/天枢获取战略优先级
2. **能力需求映射** → 将战略优先级转化为具体能力需求
3. **缺口识别** → 对比现有能力 vs 需求，找出鸿沟

---

## 分析框架

### Step 1：战略能力需求提取

```python
def extract_capability_requirements(strategic_priorities):
    """
    输入：战略优先级列表
    输出：能力需求列表
    """
    requirements = []
    for priority in strategic_priorities:
        # 从战略优先级提取所需能力
        # 例如："国际化扩张" → 需要"跨文化协作"+"多语言处理"
        capability = map_priority_to_capability(priority)
        urgency = assess_urgency(priority)
        requirements.append({
            "capability": capability,
            "urgency": urgency,  # P0/P1/P2
            "depth_needed": assess_depth(priority)
        })
    return requirements
```

### Step 2：现有能力矩阵构建

读取每个Agent的`agent-capacity-modeler`输出，建立现有能力矩阵：

```
能力矩阵格式：
| Agent | 核心能力1 | 核心能力2 | 核心能力3 | 综合评分 |
|-------|---------|---------|---------|---------|
| 轩辕  | 95      | 88      | 72      | 85       |
| 天工  | 82      | 91      | 78      | 83.7     |
| ...   | ...     | ...     | ...     | ...      |
```

### Step 3：缺口计算

```python
def calculate_gaps(requirements, capability_matrix):
    gaps = []
    for req in requirements:
        current_level = get_current_capability(req['capability'])
        needed_level = req['depth_needed']
        gap = needed_level - current_level
        if gap > 0.2:  # 超过20%差距才视为显著缺口
            gaps.append({
                "capability": req['capability'],
                "gap_size": gap,
                "urgency": req['urgency'],
                "recommended_action": recommend_action(gap)
            })
    return sort_by_urgency(gaps)
```

---

## 华为"关键岗位"识别逻辑

华为对关键岗位的定义：
- **战略重要性**：对公司业务成败影响巨大
- **稀缺性**：市场上符合要求的人才极少
- **替代难度**：培养周期长，外部获取成本高

稷下对能力缺口的优先级判定：
```
关键岗位 = 战略重要性(高) × 稀缺性(高) × 替代难度(高)
→ P0 优先级，触发立即猎取
```

---

## 输出格式

```yaml
analysis_date: "2026-05-03"
strategic_period: "2026-Q2"

requirements_analysis:
  total_capabilities_required: 15
  P0_critical: 3
  P1_high: 7
  P2_standard: 5

gap_summary:
  total_gaps: 4
  critical_gaps:
    - capability: "跨文化协作"
      gap_size: 0.45
      affected_strategies: ["国际化扩张", "跨大陆协作"]
      recommended_action: "招聘碳基国际合作专家"
    - capability: "量化策略创新"
      gap_size: 0.35
      affected_strategies: ["金融造血"]
      recommended_action: "Agent进化计划 + 外部专家接触"

  medium_gaps:
    - ...

  minor_gaps:
    - ...

recruitment_recommendations:
  silicon_hire:
    - capability: "跨文化协作模拟"
      target_agent: "麒麟"
      evolution_path: "增加跨境电商项目参与度"
  carbon_hire:
    - capability: "量化策略架构"
      target_profile: "头部量化基金PM级别"
      urgency: "P0"
      offer_type: "合伙人级"

training_recommendations:
  - agent: "鲲鹏"
    gap: "国际化增长"
    training_path: "参与轩辕跨境技术项目"
```

---

## 与麦肯锡能力规划方法论对齐

麦肯锡能力规划框架：
1. **能力扫描** → 评估现有能力水平
2. **差距分析** → 识别关键缺口
3. **优先级排序** → 基于战略重要性排序
4. **行动计划** → 招聘/培训/外部合作

稷下完全对齐此框架，并扩展为硅基/碳基双通道。

---

## 踩坑记录

### 坑1：战略优先级表述模糊
- 问题：昆仑/天枢的战略描述可能不够具体，难以提取能力需求
- 解决：稷下主动与昆仑/天枢进行"战略解码会议"，将战略翻译为可量化能力需求

### 坑2：能力评估数据延迟
- 问题：能力矩阵数据可能有1-2周延迟
- 解决：标注数据时间戳，对高优先级缺口进行实时复核

### 坑3：缺口行动建议过于笼统
- 问题："招聘P0人才"这类建议不够可执行
- 解决：为每个缺口配套具体的猎取方案或培训计划

---

## 使用示例

```
用户：分析Q2战略的能力缺口
稷下：
1. 与天枢对齐Q2战略优先级
2. 提取15项关键能力需求
3. 构建现有Agent能力矩阵
4. 计算4个显著缺口
5. 输出《Q2能力缺口与行动建议报告》
6. 同步给昆仑（战略决策参考）
7. 同步给猎头行动（碳基招聘启动）
```