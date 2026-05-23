# R08: 期权与波动率理论深度蒸馏

> 蒸馏范围：R26-30 | 期权Greeks进阶 → 波动率曲面 → Variance Swap → 隐含分布 → 加密期权策略

---

## 1. Greeks进阶

### Delta对冲的离散化误差
- **连续对冲假设**：Black-Scholes假设无限频率再平衡，现实中每日/每小时再平衡
- **离散化误差**：Δt越大，对冲误差越大，误差方差 ∝ Γ²σ⁴Δt
- **最优再平衡频率**：交易成本 vs 对冲误差的权衡 — Whalley & Wilmott (1993) 渐近分析：对冲带宽 ∝ (Γ²σ²S²/κ)^(1/3)，κ=交易成本率
- **加密实践**：Deribit期权Delta对冲需考虑现货T+0、合约杠杆，高频再平衡成本较低

### Gamma-Theta权衡（核心关系）
```
BS框架：Θ + ½σ²S²Γ + rSΔ = rV（持有成本等式）
简化：Θ ≈ -½σ²S²Γ（平值附近）
```
- **Gamma Scalping**：做多Gamma → 每次价格波动赚 ½Γ(ΔS)²，但每天付|Θ|
- **盈亏平衡波动**：实现波动率 > 隐含波动率时Gamma多头盈利
- **加密特殊性**：BTC实现波动率经常超过隐含（周末跳空），Gamma多头在周五尾盘建仓有统计优势

### 高阶Greeks
| Greek | 定义 | 加密实战意义 |
|-------|------|-------------|
| **Vanna** | ∂Δ/∂σ = ∂Vega/∂S | 波动率变化时Delta偏移，影响对冲稳定性 |
| **Volga (Vomma)** | ∂Vega/∂σ | 波动率凸性暴露，long volga = 做多波动率波动率 |
| **Charm** | ∂Δ/∂t | 到期日附近Delta漂移加速，影响对冲频率决策 |
| **Color** | ∂Γ/∂t | Gamma的时间衰减速率，短期期权Gamma衰减极快 |
| **Speed** | ∂Γ/∂S | Gamma随标的变化，衡量对冲再平衡紧迫性 |

---

## 2. 波动率曲面建模

### 局部波动率（Dupire 2024框架）
- **Dupire公式**：σ²_loc(K,T) = [2∂C/∂T] / [K²∂²C/∂K²]
- **核心思想**：从市场期权价格反推局部波动率函数 σ(S,t)
- **优点**：完美拟合所有观察到的期权价格
- **致命缺陷**：产生"负波动率斜率动态" — 当现货上涨时模型预测波动率下降，与实证相悖
- **实战定位**：用于奇异期权定价的基准模型，不用于交易

### 随机波动率模型
**Heston模型**（最广泛使用）：
```
dS = μS dt + √v S dW₁
dv = κ(θ-v) dt + ξ√v dW₂    (CIR过程)
Corr(dW₁, dW₂) = ρ           (杠杆效应)
```
- 5参数(κ,θ,ξ,ρ,v₀)，半解析解（特征函数+FFT）
- ρ<0 产生volatility skew（下跌时波动率上升）
- ξ 控制vol-of-vol（波动率的波动率）
- **加密应用**：BTC的ρ约-0.3~-0.5（弱于股票的-0.7），ξ约0.8~1.2（远高于股票的0.3）

**SABR模型**（利率市场标准，可适配加密）：
```
dF = σ F^β dW₁
dσ = α σ dW₂
```
- Hagan近似公式直接给出IV → 快速校准
- β=1时为lognormal SABR，适合BTC（对数正态特征）
- **实战**：Deribit期权做市商常用SABR族进行快速报价

### 加密波动率曲面特殊性
1. **极端Skew**：BTC期权25Δ RR (Risk Reversal) 可达±15 vol points（标普约±5）
2. **周末效应**：周五→周一跳空，周末IV系统性低估 → 周五尾盘做多Gamma统计盈利
3. **ETF上市后变化**：2024.1 BTC ETF上市后，短期IV下降约5-8个点，skew变平
4. **期限结构倒挂**：恐惧事件时短期IV > 长期IV，与VIX类似但幅度更大

---

## 3. Variance Swap与波动率交易

### VIX计算原理
```
σ² = (2/T) Σᵢ [ΔKᵢ/Kᵢ²] e^(RT) Q(Kᵢ)  — 对所有OTM期权求和
```
- 本质是所有OTM期权价格的加权平均，权重 1/K²
- **模型无关**：不依赖任何波动率模型假设

### 方差互换定价（Log Contract复制）
- **核心公式**：Var Swap = E[log²(R)] = 2/T ∫₀ᵀ (1/S_t) dS_t - 2/T log(S_T/S_₀) 的风险中性期望
- **复制组合**：持有连续K的OTM strip，权重 2/(TK²) dK
- **离散实现**：选取有限strike的期权近似，误差 ∝ (ΔK)²
- **方差互换 vs 波动率互换**：
  - 方差互换：可直接用期权strip复制，流动性好
  - 波动率互换：需要凸性调整 E[σ] < √(E[σ²])，无法静态复制

### 加密波动率指数
- **BVIV (Binance)**：基于Binance期权，计算类似VIX
- **DVOL (Deribit)**：基于Deribit期权数据的波动率指数
- **实战应用**：DVOL-RV spread作为波动率交易信号（DVOL > 历史RV → 卖波动率）

---

## 4. 隐含分布提取（Breeden-Litzenberger）

### 核心公式
```
f(K) = e^(rT) ∂²C/∂K²  — 风险中性概率密度
```
- 从期权价格二阶导数提取隐含PDF
- **数值实现**：插值IV → 构建光滑IV曲面 → 数值二阶导
- **关键挑战**：稀疏strike → 插值不稳定 → 需要正则化（Tikhonov/B-spline平滑）

### 模型无关尾部风险
- **Left tail mass**：P(S_T < K) = e^(rT) ∂P(K)/∂K（从put导数）
- **Conditional Value at Risk**：从隐含PDF直接积分计算
- **加密实战**：Deribit BTC期权提取隐含分布：
  - 观察到左尾肥于右尾（崩盘恐惧）
  - ETF上市后左尾概率下降但未消失
  - 隐含分布的偏度变化领先于现货价格

---

## 5. 加密期权实战策略

### 波动率卖出策略（统计表现）
| 策略 | 构造 | 典型胜率 | 加密实证 |
|------|------|---------|---------|
| **Iron Condor** | 卖OTM call+put + 买更OTM保护 | 70-80% | 月度IC在BTC上月均收益2-5% IV，尾部风险需严格止损 |
| **Short Strangle** | 卖OTM call + 卖OTM put | 65-75% | BTC周度strangle历史回测：盈利期数>70%，但亏损期数单次可吃掉5-8次盈利 |
| **Calendar Spread** | 买远月卖近月同strike | 60-65% | 利用期限结构contango，近月IV衰减更快 |

### 波动率套利（IV-RV Spread）
- **核心逻辑**：长期看，IV > RV（波动率风险溢价，VRP）
- **BTC VRP**：历史均值约3-5个vol points，但时而转负（如2024.3突破行情）
- **交易方法**：卖出方差互换（或近似用short straddle）+ Delta对冲
- **加密优势**：高VRP + 做市商较少 = 更大的结构性套利机会

### 期权+现货组合
- **Covered Call**：持有BTC + 卖虚值call → 增强收益，放弃上行
- **Protective Put**：持有BTC + 买虚值put → 尾部保险，成本约年化5-10% IV
- **Collar**：持有BTC + 卖call + 买put → 零成本保险，限制上下行

---

## 关键参考文献
- Dupire (1994) "Pricing with a Smile" — 局部波动率奠基
- Heston (1993) "A Closed-Form Solution for Options with Stochastic Volatility"
- Hagan et al. (2002) "Managing Smile Risk" — SABR模型
- Breeden & Litzenberger (1978) "Prices of State-Contingent Claims Implicit in Option Prices"
- Carr & Madan (2001) "Optimal Positioning in Market Completeness" — Variance Swap理论
- Demeterfi et al. (1999) "More Than You Ever Wanted to Know About Volatility Swaps"
- Alexander & Imeraj (2023) "Crypto Options and Volatility" — 加密期权实证
