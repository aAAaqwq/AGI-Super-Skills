# R10: 风险管理前沿深度蒸馏

> 蒸馏范围：R36-40 | CVaR → EVT极值理论 → 下行风险 → Regime Detection → 压力测试

---

## 1. CVaR与尾部风险建模

### VaR vs CVaR (Expected Shortfall)

**VaR_α(P&L)** = inf{l : P(L > l) ≤ 1-α} — 损失分布的α分位数
**CVaR_α** = E[L | L > VaR_α] — 超过VaR的条件期望损失

关键差异：
- VaR只告诉"最多亏多少"(在置信水平内) — 不关心尾部形状
- CVaR告诉"如果突破VaR，平均亏多少" — 捕捉尾部信息
- **CVaR是一致性风险度量**(满足次可加性)，VaR不是
- Basel III已从VaR转向ES(CVaR)作为银行监管标准

### Rockafellar-Uryasev线性规划方法

**核心突破**：CVaR可以通过线性规划直接优化

```
min_{x,ζ} F_α(x,ζ) = ζ + (1/(1-α)) · E[max(L(x) - ζ, 0)]
```
- ζ = VaR候选值，x = 组合权重
- **线性化**：引入辅助变量 u_i ≥ 0, u_i ≥ L_i - ζ
- 离散场景下变为标准线性规划 → 可嵌入组合优化
- **实用价值**：不需要知道分布的具体形式，只需场景样本

### 加密市场CVaR特征
- BTC日度95% CVaR约5-8%(传统股票市场约2-3%)
- 99% CVaR可达15-25%(2020.3.12单日-40%)
- CVaR/VaR比值(尾部厚度指标)：BTC约1.5-2.0，标普约1.2-1.4

---

## 2. 极值理论(EVT)

### POT (Peaks Over Threshold)方法

**核心定理(Balkema-de Haan-Pickands)**：
对于足够高的阈值u，超出量的分布收敛于广义Pareto分布(GPD)：

```
P(X-u ≤ y | X > u) ≈ G(y; ξ, β) = 1 - (1 + ξy/β)^(-1/ξ)    for y > 0
```
- ξ = shape parameter (尾部厚度)
  - ξ < 0: 薄尾(有上界)
  - ξ = 0: 指数尾部(正态类)
  - ξ > 0: 肥尾(Pareto类) — **金融市场典型**
- β = scale parameter

**阈值u的选择**：
- 经验法则：u ≈ 90-95%分位数
- 精确方法：平均超出量图(Mean Excess Plot) — 在超过u后应为线性

### Hill估计器

用于估计shape parameter ξ：
```
ξ_Hill = (1/k) Σ_{i=1}^{k} [log(X_(i)) - log(X_(k+1))]
```
- X_(i) = 第i个顺序统计量(降序)
- k = 使用的尾部观测数
- **k的选择**：k太小→方差大，k太大→偏差大 → 平衡点约为n^0.6

### 加密市场EVT参数估计

**BTC日度收益率EVT估计**：
- ξ ≈ 0.25-0.45 (显著肥尾，高于标普的0.15-0.25)
- 右尾略薄于左尾(崩盘恐惧不对称性)
- 极端事件(>10σ)出现频率远高于正态预测 — EVT比正态更准确

**实战应用**：
1. **极端VaR/CVaR计算**：用GPD拟合尾部 → 外推计算99.9% VaR
2. **压力损失估计**：基于EVT估计单日最大可能损失
3. **尾部风险定价**：期权隐含分布 vs EVT拟合分布的差异

---

## 3. 下行风险(DSR)进阶

### Sortino Ratio

```
Sortino = (R_p - R_f) / σ_d
σ_d = √(E[min(R_p - MAR, 0)²])  — 下行半标准差
```
- MAR = Minimum Acceptable Return (通常取0或无风险利率)
- **vs Sharpe**：Sharpe惩罚所有波动(包括上行)，Sortino只惩罚下行
- **适用场景**：非对称收益分布(如期权策略、趋势跟踪)

### Omega函数

```
Ω(r) = ∫_r^∞ [1 - F(x)] dx / ∫_{-∞}^r F(x) dx
```
- r = 收益率阈值
- **Omega > 1**：获得超过r的概率加权收益高于低于r的损失
- **Omega是完整的分布描述** — 比任何单一统计量包含更多信息
- **优化应用**：最大化Omega(r) → 不需要假设分布形态
- **加密实战**：BTC策略的Omega(0)在牛市区间可达3-5，熊市可降至0.5

### MAR设定方法
1. **零值MAR**：最简单，确保正期望
2. **无风险利率**：与Sharpe等价
3. **目标收益率**：基于资金成本/机会成本
4. **动态MAR**：随市场regime调整(牛市更高/熊市更低)

---

## 4. Regime Detection

### Hidden Markov Model (HMM)

**模型设定**：
```
隐状态 S_t ∈ {1,...,K} (K=2-4个regime)
P(S_t = j | S_{t-1} = i) = p_ij (转移概率矩阵)
观测 r_t | S_t = j ~ N(μ_j, σ_j²) (regime-dependent分布)
```
- **估计方法**：Baum-Welch算法(EM)估计参数，Viterbi解码最可能状态路径
- **BTC典型regime**：
  - Regime 1 (低波动牛市)：μ>0, σ~2-3%
  - Regime 2 (高波动熊市)：μ<0, σ~5-8%
  - Regime 3 (震荡)：μ≈0, σ~3-4%

### Markov Switching模型 (Hamilton 1989)

- HMM在计量经济学的经典实现
- **扩展**：允许regime-dependent的AR系数 → 不同regime下动量/反转强度不同
- **滤波**：实时估计当前处于各regime的概率 P(S_t=j | r_1,...,r_t)
- **实战**：用滤波概率作为策略的条件开关

### Change-Point Detection (PELT算法)

**PELT (Pruned Exact Linear Time)** — Killick et al. (2012)：
- 精确检测时间序列的结构断点
- 时间复杂度O(n)（剪枝加速）
- **vs HMM**：不需要预设regime数量和参数
- **应用**：检测BTC波动率regime切换点，用于：
  1. 自适应止损调整
  2. 仓位大小动态调整
  3. 策略参数切换触发器

### 加密市场Regime特征
- **切换频率**：BTC平均每30-60天切换一次regime（传统市场约90-180天）
- **可预测性**：基于链上指标(活跃地址、交易所净流入)可提前1-3天预警regime切换
- **ETF影响**：2024年后BTC regime与美股regime相关性增加

---

## 5. 压力测试与极端场景

### 历史场景回放

| 事件 | BTC跌幅 | 持续时间 | 特征 |
|------|--------|---------|------|
| **2020.3.12** (COVID) | -40% | 1天 | 流动性枯竭，spread扩大10x |
| **2021.5.19** (中国禁矿) | -35% | 3天 | 政策冲击，矿工抛售 |
| **2022.11.9** (FTX崩盘) | -25% | 2天 | 交易所信任危机 |
| **2024.8.5** (日圆套利平仓) | -18% | 1天 | 宏观跨市场传染 |

### 反向压力测试(Reverse Stress Testing)
1. **定义**：从"什么会让策略崩溃"倒推
2. **方法**：
   - 识别策略的关键风险因子暴露
   - 找到使策略亏损超过阈值的因子变动组合
   - 评估该组合发生的概率(结合EVT)
3. **加密示例**：
   - 资金费率策略：交易所同时暂停提币 + funding rate极端
   - 做市策略：连续闪崩 + 流动性蒸发 + 交易所宕机

### 蒙特卡洛压力测试
- **相关矩阵扰动**：将正常相关矩阵乘以扰动因子，模拟极端相关性变化
  - 正常BTC-SPX相关性~0.3 → 压力下可升至0.7+
  - 相关性趋同(correlation breakdown)是最致命的压力效应
- **肥尾注入**：用t分布(自由度3-5)替代正态 → 生成极端场景
- **条件场景**：在特定宏观事件(如美联储紧急降息)条件下模拟

### 加密特有风险因子
1. **交易所风险**：交易所暂停/倒闭(FTX教训) → 分散托管
2. **链上风险**：DeFi协议被黑/预言机操纵 → 审计+限额
3. **监管风险**：主要国家禁止/限制 → 地理分散
4. **技术风险**：网络拥堵/分叉 → 多链备份
5. **稳定币风险**：USDT/USDC脱锚 → 多稳定币分散

---

## 关键参考文献
- Rockafellar & Uryasev (2000) "Optimization of Conditional Value-at-Risk"
- Balkema & de Haan (1974) / Pickands (1975) — POT定理
- Hill (1975) — Hill估计器
- Hamilton (1989) "A New Approach to the Economic Analysis of Nonstationary Time Series"
- Killick, Fearnhead & Eckley (2012) "Optimal Detection of Changepoints With a Linear Computational Cost"
- Sortino & Price (1994) "Performance Measurement in a Downside Risk Framework"
- Acerbi & Tasche (2002) "On the Coherence of Expected Shortfall"
- Basel III FRTB (Fundamental Review of the Trading Book)
