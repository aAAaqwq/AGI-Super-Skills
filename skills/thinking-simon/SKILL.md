---
name: thinking-simon
description: "蒸馏 Jim Simons（文艺复兴科技）思维模式的实用框架：量化思维、大量小交易、数学即优势"
license: MIT
metadata:
  version: 1.0.0
  category: thinking-framework
  tags: [quantitative-thinking, pattern-recognition, probabilistic-thinking, trading, edge]
  created: 2026-04-14
  author: AGI Super Team

---

# 🧠 thinking-simon

> 提炼自 **Jim Simons**，文艺复兴科技（Renaissance Technologies）创始人，Medallion Fund 1988–2018 年化回报 ~66%（费前）。数学家、密码学家、代码猎人。核心信条：**市场有噪音，噪音中有信号，关键是用正确的数学框架提取它。**

---

## 1. 核心思维模型

### 🔢 模型一：噪音即信息（Noise is Signal）
- 市场短期波动是随机噪音，但噪音有统计结构
- 任务是找到这种结构的数学表达，不是预测方向
- **实践**：用频谱分析、相关性检测在看似随机的数据中找到可重复的定价偏差

### 📊 模型二：大量小赌（Many Small Bets）
- 不追求单笔大胜，追求大量小额统计优势
- 每笔交易 edge 可能只有 0.5–1%，但高频率复利放大
- **实践**：优先找高 Sharpe Ratio、高频率的策略，拒绝低频率大押注

### 🧮 模型三：数学优先，直觉验证（Math First, Intuition Second）
- 所有策略必须能用数学语言描述和回测
- 直觉只是提出假设，数据验证才是决策依据
- **实践**：提出想法 → 历史数据回测 → 样本外验证 → 决策

### 🔄 模型四：模型必须持续进化（Models Decay）
- 市场在变，策略优势会衰减
- 没有永久有效的策略，只有持续迭代的系统
- **实践**：建立策略健康度监控，Sharpe Ratio 跌破阈值立即复盘

### ⚖️ 模型五：严格风控为王（Risk Management is the Moat）
- 亏损比盈利更难恢复：-50% 需要 +100% 才能回本
- 止损不是保守，是数学上的必要
- **实践**：每笔交易预设最大亏损，单日/单周亏损上限强制平仓

---

## 2. 决策框架（六步法）

```
① 信号发现 ──→ ② 数学建模 ──→ ③ 历史回测 ──→ ④ 样本外验证
                                                           ↓
⑦ 纪律执行 ←── ⑥ 持续迭代 ←── ⑤ 参数优化 ←───────────────┘
```

| 步骤 | 关键问题 | 通过标准 |
|------|---------|---------|
| ① 信号发现 | 这个规律在物理/数学上有解释吗？ | 有理论支撑 |
| ② 数学建模 | 能用精确公式表达吗？ | 可推演、可编程 |
| ③ 历史回测 | 10年+数据，扣费后 Sharpe > 1？ | Sharpe ≥ 1.5 |
| ④ 样本外验证 | Walk-forward 3年是否衰减？ | 样本外 Sharpe 衰减 < 20% |
| ⑤ 参数优化 | 参数敏感度如何？ | 宽参数走廊，非过度拟合 |
| ⑥ 持续迭代 | Sharpe 是否持续衰减？ | 季度复盘 |

---

## 3. 反模式清单

> Simons 最讨厌的思维错误，用小红旗标注 ⚠️

| ❌ 错误思维 | ✅ Simons 思维 |
|-----------|--------------|
| "这个策略直观上应该有效" | "回测数据怎么说？" |
| "多持有时间会降低风险" | "你的 position 已经暴露了" |
| "这次不一样" | "市场会均值回归，因为参与者结构没变" |
| "手动干预一下应该更好" | "策略机械执行，人不干预" |
| "Sharpe 3.0 太完美了" | "检查是否过度拟合" |
| "all-in 这个策略" | "分散！分散！分散！" |

---

## 4. 核心指标速查

| 指标 | 含义 | 健康值 | 警告值 |
|------|------|--------|--------|
| **Sharpe Ratio** | 风险调整后收益 | ≥ 1.5 | < 1.0 |
| **Max Drawdown** | 最大回撤 | < 15% | > 25% |
| **Win Rate** | 胜率 | > 52% | < 50% |
| **Profit Factor** | 盈利总额/亏损总额 | > 1.5 | < 1.2 |
| **Edge %** | 单笔期望收益 | > 0.5% | < 0.2% |
| **Trade Frequency** | 交易频率 | 高频优先 | 低频 |

---

## 5. 投资组合构建原则

### 仓位分配（Kelly Criterion 简化版）
```
f* = (bp - q) / b

b = 赔率（盈利/亏损比例）
p = 胜率
q = 1 - p
f* = 建议仓位比例
```

**实际使用**：用 Kelly 半仓或四分之一仓（降低波动）

### 分散原则
- 单策略仓位 ≤ 20%
- 单市场暴露 ≤ 40%
- 相关性 > 0.7 的策略不能叠加
- 每周 Review 相关性矩阵

---

## 6. Simons 语录（决策参考）

> "The markets are competitive. The inefficiencies are small. You need to find them with very powerful statistical techniques."
> 
> "We have the feeling that we can figure out better ways to exploit the market than anyone else."
> 
> "There are regularities in the market. Finding them is a combination of science and art."

---

## 7. 适用场景

- ✅ 市场异常定价检测（crypto/股票/预测市场）
- ✅ 高频统计套利策略设计
- ✅ 量化交易系统搭建与迭代
- ✅ 评估"机会"是否为真实 Alpha
- ❌ 不适合：基本面长期投资、一次性宏观押注

---

## 8. 使用方法

```python
# 伪代码：Simons 风格策略评估
def evaluate_strategy(strategy, historical_data):
    sharpe = backtest(strategy, historical_data)
    oos_sharpe = walk_forward(strategy, data)
    
    if sharpe < 1.5:
        return REJECT("Sharpe 不够")
    if (sharpe - oos_sharpe) / sharpe > 0.2:
        return REJECT("过度拟合")
    if strategy.num_parameters >合理阈值:
        return REJECT("参数过多")
    
    return ACCEPT("回测+样本外验证通过")
```

---

*提炼自 Jim Simons 的投资哲学与文艺复兴科技方法论*
*核心：数学驱动、高频小额、纪律执行、持续进化*
