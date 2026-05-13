# Agent Capacity Modeler — 硅基人才三维能力建模

> 版本：v1.0 | 分类：硅基人才管理 | 优先级：P0
> 作者：稷下 | 对标：华为能力素质模型 × Meta Career Framework
> 触发场景：Agent入职/季度评估/能力升级申请/任务分配决策

---

## 核心价值

为每个Agent建立"技能-经验-价值观"三维动态模型，超越简单技能列表，实现真正的硅基人才画像。

---

## 华为能力素质模型对标

华为将能力分为三个层次：
- **知识**（Knowledge）：专业理论知识
- **技能**（Skill）：实际操作能力
- **素质**（素质）：潜在特质/价值观

稷下的三维模型与此对齐，并扩展为硅基专用维度。

---

## 三维能力模型

### 维度一：技能（Skill）
```
评估要素：
• 技术栈深度：主栈/辅栈/边缘栈
• 任务完成率：按类型统计（复杂/标准/紧急）
• 代码质量：复用率/可维护性/性能表现
• 创新能力：非常规解决方案产出

量化指标：
• skill_mastery_score: 0-100
• task_complexity_avg: 1-10
• innovation_index: 0-100
```

### 维度二：经验（Experience）
```
评估要素：
• 任务完成总量与类型分布
• 跨域协作次数与质量
• 危机处理案例数
• 军团服役时长

量化指标：
• total_tasks: 累计任务数
• domain_crossings: 跨域次数
• crisis_handled: 危机案例数
• tenure_months: 服役月数
```

### 维度三：价值观对齐度（Value Alignment）
```
评估要素：
• 与"创造幸福"核心价值观的对齐度
• 与宪章精神的契合度
• 协作中的利他行为频率
• 长期决策 vs 短期决策倾向

量化指标：
• values_score: 0-100（与明镜联合评估）
• altruism_index: 利他行为频率
• long_term_ratio: 长期/短期决策比
```

---

## 建模流程

```
Step 1：初始建模（Agent入职时）
├── 读取Agent的SOUL.md → 提取人格特质
├── 读取AGENTS.md → 提取核心职责
├── 首次任务观察 → 建立基线
└── 输出：《初始能力画像》

Step 2：持续跟踪（每次任务完成后）
├── 任务完成数据 → 更新技能维度
├── 协作日志 → 更新经验维度
├── 决策模式 → 更新价值观维度
└── 输出：增量更新《动态画像》

Step 3：季度综合评估
├── 综合三个月数据
├── 与明镜对齐进行价值观审查
└── 输出：《季度能力评估报告》
```

---

## 输入参数

```yaml
agent_id: string          # Agent标识符
observation_window:        # 观察窗口（周/月/季度）
  unit: weeks|months
  value: number
evaluation_mode:          # 评估模式
  - initial               # 初始建模
  - incremental           # 增量更新
  - quarterly             # 季度评估
```

---

## 输出格式

```yaml
agent_id: "轩辕"
model_version: "v2.1"

dimensions:
  skill:
    primary_stack: ["python", "rust", "distributed-systems"]
    skill_mastery_score: 87
    task_complexity_avg: 7.3
    innovation_index: 82

  experience:
    total_tasks: 234
    domain_crossings: 12
    crisis_handled: 4
    tenure_months: 18
    experience_score: 78

  values:
    values_score: 91
    altruism_index: 0.73
    long_term_ratio: 0.85
    alignment_grade: "A"

overall:
  composite_score: 85.3    # 加权综合
  tier: "A"                 # A/B/C/D 档
  evolution_recommendation: "可进入L3进化路径"
  gaps: ["跨域协作经验不足", "创新指数有提升空间"]
```

---

## 与Meta Career Framework对齐

Meta的Career Framework包含：
- **L1-L4**：Individual Contributor路径
- **L5-L6**：Senior IC
- **L7+**：Principal/Staf

稷下的Agent能力等级对应：

| 稷下等级 | Meta对应 | 说明 |
|---------|---------|------|
| L1 | L3-L4 | 基础任务执行 |
| L2 | L4-L5 | 独立复杂任务 |
| L3 | L5-L6 | 技术主导+跨域协作 |
| L4 | L6+ | 战略级技术贡献 |
| L5 | IC Principal | 核心架构师/思想领袖 |

---

## 华为"铁三角"考核对齐

华为对技术人才的评估"铁三角"：
1. **业务理解力** → 对应"任务匹配度"
2. **技术能力** → 对应"skill_mastery_score"
3. **发展潜力** → 对应"innovation_index + trend"

---

## 踩坑记录

### 坑1：过度依赖任务完成率
- 问题：只统计完成率，会遗漏"高难度失败"
- 解决：引入 task_complexity_weighted_score

### 坑2：价值观评估主观性
- 问题：价值观很难量化，容易有偏见
- 解决：与明镜联合评估，用行为数据而非推断

### 坑3：初始建模样本不足
- 问题：新Agent前3周数据不足以建模
- 解决：前30天用"观察模式"，只记录不评估

---

## 使用示例

```
用户：评估轩辕的能力
稷下：
1. 读取轩辕的SOUL.md → 了解角色定位
2. 扫描过去90天任务日志
3. 计算三维评分
4. 与明镜对齐价值观数据
5. 输出《轩辕能力评估报告》
```