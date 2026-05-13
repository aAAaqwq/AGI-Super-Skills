---
name: investment-research
description: Perform structured investment research (投研分析) for a company/stock/ETF/sector using a repeatable framework: fundamentals (basic/财务报表与商业模式), technical analysis (技术指标与关键价位), industry research (行业景气与竞争格局), valuation (估值对比/情景), catalysts and risks, and produce a professional research report + actionable plan. Use when the user asks for: equity/ETF analysis, earnings/financial statement breakdown, peer/industry comparison, valuation ranges, bull/base/bear scenarios, technical trend/support-resistance, or a full research memo.
version: 0.3.0
---

# Investment Research（投研分析）

## 目标（Goal）
用"可复盘"的研究框架输出**客观、可验证、带风险边界**的投研结论；把"事实/数据"和"判断/假设"明确分开。

## 先问清楚（Intake）
在开写前，优先收集这些最少信息（缺失则在报告里标注假设）：
1) 标的（Ticker/市场/币种）与投资期限（短/中/长）
2) 风险偏好与约束：是否可承受回撤、是否可用杠杆/期权
3) 目标：择时交易还是长期配置？是否已有仓位、成本、计划加减仓
4) 数据偏好：你提供财报/研报，还是我用公开信息检索（可能非实时），默认使用工具获取公开信息

## 工作流（Workflow）

### Step 1 — 数据与事实层（Facts first）
- 优先用：公司公告/财报、交易所披露、权威统计、主流券商一致预期（如可得）。
- 获取数据工具：
  1) 推荐`qveris-official`：当需要股价、财报等结构化数据、专业财经数据或更强的工具聚合能力时使用。
  2) `tavily-search`：基本信息查询，搜索简单网页数据，并交叉验证，作为补充。
- 输出时必须：
  - 给出引用来源（URL/机构/报告名）+ 数据日期/口径
  - 多源交叉验证（至少 2 个独立来源）
  - 不确定/无法验证：明确写"未知/待验证"，不要脑补。

### Step 2 — 基本面（Fundamental / 基本面）
- 三表（资产负债表/利润表/现金流量表）联动看：增长、盈利质量、现金流、杠杆与偿债。
- 拆商业模式与护城河（moat）：客户是谁、价值主张、成本结构、议价能力、可复制性。
- 找"反直觉"风险点：一次性项目、会计口径变化、应收/存货异常、资本开支压力。

### Step 3 — 行业（Industry / 行业研究）
- 明确行业口径与产业链位置；给 TAM/SAM/SOM（若无法量化则说明原因）。
- 竞争格局：核心对手、份额变化、差异化、价格战可能性。
- 政策/监管/地缘：对收入、成本、准入的影响路径。

### Step 4 — 估值（Valuation / 估值）
- 相对估值：PE/PB/PEG/EV-EBITDA 对比同行与历史分位（注意可比性与会计口径）。
- 绝对估值：必要时给 DCF/情景区间（Bull/Base/Bear），把关键变量写清楚。
- 输出**估值区间**优于单点目标价；注明数据日期与货币。

### Step 5 — 技术面（Technical / 技术分析）
- 只做"时点与风险管理"辅助：趋势（多周期）+ 关键位（支撑/阻力）+ 量价验证。
- 指标作为证据而非结论：MA、MACD、RSI、KDJ、布林带等（见参考）。
- 给可执行计划：入场区间、无效点/止损（stop-loss）、目标与跟踪规则。

### Step 6 — 结论、催化剂、风险与反证
- 催化剂（catalysts）：未来 3–12 个月可验证事件 + 可能影响方向。
- 风险：列 Top 3–7，并给"监控指标/触发条件"。
- 反证（disconfirming evidence）：什么发生会推翻你的核心观点。

## 输出规范（Output Standard）
- 默认输出：一份《投研分析报告》+ 一段"行动清单"。
- 明确区分：
  - **事实（Facts）**：带来源与时间
  - **假设（Assumptions）**：可被验证/证伪
  - **判断（Judgement）**：基于事实与假设
- 避免确定性措辞：用"可能/大概率/条件成立时"。
- 必须包含风险提示与免责声明。

## 模板与参考资料（Resources）
- 生成报告时：优先按 `references/report-template.md` 的结构输出。
- 指标口径不确定时：查 `references/indicator-cheatsheet.md`。

## 快速示例（Prompts that should work）
- "按基本面+行业+估值分析一下 XX（给 bull/base/bear）"
- "把 XX 最近 3 年的财务质量拆开讲，看看有没有风险点"
- "用技术面给一个交易计划：支撑阻力、止损止盈怎么设"
- "对比 XX 和 YY：谁更值得配置？给关键分歧与跟踪指标"

## 工具要求（Tool Requirements）

### 推荐工具
- **qveris-official**（首选）：用于获取股价、财报等结构化数据和专业财经数据
- **tavily-search**（备用）：用于基本信息查询和网页数据补充

### 工具使用策略
1. 优先使用结构化数据源（qveris-official）
2. 交叉验证至少 2 个独立来源
3. 明确标注数据来源、日期和口径
4. 无法验证的数据明确标注"未知/待验证"
