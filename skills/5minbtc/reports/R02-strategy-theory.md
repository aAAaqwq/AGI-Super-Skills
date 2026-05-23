# R2: 量化交易顶尖策略理论深度蒸馏

> 2026-05-23 | 来源: 28次 web_search + 3次 web_extract

## 一、统计套利 / 配对交易

### OU过程数学核心
$$dX_t = \theta(\mu - X_t)dt + \sigma dW_t$$
- θ: 均值回归速度 | μ: 长期均衡 | σ: 扩散系数
- **半衰期**: $t_{1/2} = \ln 2 / \theta$ — 决定持仓周期

### 参数估计
- **OLS**: 简单但Hurwicz bias（$\hat{b}$向上偏误，低估θ，高估半衰期）
- **MLE**: 渐近有效，转移密度 $X_{t+\Delta t}|X_t \sim N(\mu + (X_t-\mu)e^{-\theta\Delta t}, \frac{\sigma^2}{2\theta}(1-e^{-2\theta\Delta t}))$
- **实践**: 先OLS初始值，再MLE精细化，日频需200+观测

### 协整检验
- **Engle-Granger**: 因变量选择不对称，只能一个协整向量，检验势低
- **Johansen**: 基于VECM，对称，可检测多个协整关系，直接提取对冲权重
  - 迹检验: $LR_{tr} = -T\sum_{i=r+1}^{n}\ln(1-\hat{\lambda}_i)$
  - 最大特征值检验: $LR_{max} = -T\ln(1-\hat{\lambda}_{r+1})$

### 最优阈值 (Leung & Li 2015)
- 基于OU参数的最优停止问题
- θ快→阈值窄（回归快）；σ大→阈值宽（补偿波动）
- 数值解：有限差分法求解Stefan problem

### 失效场景
- 协整关系破裂（2008危机）、制度切换、交易成本吞噬、拥挤交易、gap risk

### 核心文献
1. Avellaneda & Lee (2010) QF 10(7)
2. Leung & Li (2015) IJTAF 18(3)
3. Johansen (1991) Econometrica 59(6)
4. d'Aspremont (2011) QF 11(3)

---

## 二、做市策略

### Avellaneda-Stoikov (2008)
- **预约价格**: $r(s,q,t) = s - q\gamma\sigma^2(T-t)$ — 效用调整mid
- **最优价差**: $\delta^b + \delta^a = \frac{2}{\gamma}\ln(1+\frac{\gamma}{\kappa}) + \gamma\sigma^2(T-t)$
- 到达率: $\Pr(\text{fill at }S\pm\delta) \approx A\exp(-\kappa\delta)$
- 核心洞见: 库存偏移自动倾斜报价，κ大→价差小

### GLF扩展 (2013, 2015)
- 多资产做市（向量库存$\mathbf{q}$，协方差$\Sigma$）
- 近封闭解: $\delta^b \approx \frac{1}{\kappa} + \frac{2q+1}{2}\frac{\gamma\sigma^2(T-t)}{2} + \frac{\epsilon}{\gamma}$
- 跨资产库存耦合: Risk = $\mathbf{q}'\Sigma\mathbf{q}(T-t)$

### Alpha-AS (Schulz 2022)
- RL替换AS固定参数，保留理论框架
- Alpha-AS-1: RL直接输出δ | Alpha-AS-2: RL输出超参(γ,κ)
- Alpha-AS-2在加密市场显著优于原始AS

### 失效场景
- 毒性订单流、极端波动、LOB结构突变、延迟竞争、库存极限

### 核心文献
1. Avellaneda & Stoikov (2008) QF 8(3)
2. Guéant, Lehalle & Fernandez (2013) MFE 7(4)
3. Cartea, Jaimungal & Penalva (2015) Cambridge UP
4. Schulz et al. (2022) PLoS ONE 17(12)

---

## 三、高频信号

### OFI (Cont, Kukanov & Stoikov 2014)
- 订单流不平衡 = best bid事件 - best ask事件
- $\Delta p_n = \alpha + \beta \cdot OFI_n + \epsilon_n$, $R^2$=0.35-0.65
- OFI比纯成交量预测力更强，平方根冲击定律的微观基础

### 价格冲击模型分层
1. 线性(小单): $\Delta p = \lambda Q$
2. 平方根(中单): $\Delta p = \sigma\sqrt{Q/V}$
3. 对数(大单): $\Delta p = k\ln(Q)$

### Kyle's Lambda估计
- 高频回归: $\Delta p_\tau = \alpha + \lambda \cdot \text{sign}(v_\tau)\sqrt{|v_\tau|} + \epsilon$
- LOB快照: $\hat{\lambda} \approx \frac{1}{2}\frac{\text{spread}}{\text{depth at best}}$
- VPIN: volume bucket中估计知情交易概率

### 核心文献
1. Cont, Kukanov & Stoikov (2014) JFE 12(1)
2. Kyle (1985) Econometrica 53(6)
3. Easley, López de Prado & O'Hara (2012) RFS 25(5)
4. Almgren & Chriss (2001) JOR 3(2)

---

## 四、动量策略前沿

### TS动量 vs 截面动量
- **截面动量**(Jegadeesh & Titman 1993): 相对排名博弈，做多top做空bottom
- **TS动量**(Moskowitz, Ooi & Pedersen 2012): 独立判断趋势方向，单资产可实施
  - 信号: $\text{sign}(r_{t-12,t-1})$
  - 波动率缩放: $\frac{40\%}{\sigma_t}$
  - 58个期货合约夏普~1.2

### 动量崩溃与对冲
- **2009年3月**: 截面动量3个月亏73.42%
- **Barroso & Santa-Clara (2015)**: 风险管理动量
  - $w_t^{RM} = \frac{\sigma_{target}}{\sigma_t^{realized}} w_t^{original}$
  - 夏普0.8→1.5，最大回撤-73%→-20%

### BTC动量特殊性
- 高频显现（小时/分钟级，Corbet et al. 2020）
- 散户主导→趋势更强更持久
- 资金费率动量、链上动量、波动率调整动量

### 核心文献
1. Moskowitz, Ooi & Pedersen (2012) JFE
2. Barroso & Santa-Clara (2015) JFE
3. Daniel & Moskowitz (2016) JF
4. Liu, Tsyvinski & Wu (2022) JF

---

## 五、均值回归

### Kalman Filter动态均值回归
- 状态方程: $\beta_t = \beta_{t-1} + w_t$, $w_t \sim N(0,Q)$
- 观测方程: $y_t = x_t\beta_t + v_t$, $v_t \sim N(0,R)$
- 时变对冲比 vs 静态OLS：动态适应regime变化
- 核心: 预测→更新循环，R/Q比控制适应性vs稳定性

### Z-Score陷阱
- 非平稳序列的Z-Score无意义（均值和标准差时变）
- 必须先用OU过程确认均值回归性，再做Z-Score
- 正确做法: 用滚动OU参数计算动态Z-Score
