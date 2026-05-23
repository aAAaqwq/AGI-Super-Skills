# R5: 机器学习量化交易最前沿

> 2026-05-23 | 来源: 18次 web_search | 聚焦BTC 5min预测场景

## 一、GBDT因子挖掘 (LightGBM)

### BTC 5min适配度: ★★★★★
表格型数据(OHLCV+衍生因子)最优选择，秒级训练。

### 关键实践
- **时序交叉验证**: 严禁`train_test_split(shuffle=True)`，必须用`TimeSeriesSplit`或Purged K-Fold
- Purge窗口≥12根K线(1h)
- **Point-in-Time对齐**: 因子在t仅用≤t-1数据，标签用未来收益
- **SHAP**: 因子筛选(≈0剔除) + 因子监控(随时间变化=regime shift预警)
- **Optuna**: TPESampler, n_trials=200

### BTC 5min关键超参
- `num_leaves`: 31-63 | `max_depth`: 5-8 | `learning_rate`: 0.01-0.05
- `min_child_samples`: 50-200 | `early_stopping_rounds=50`

### 失败模式
- 过拟合高频噪声 → 增大min_child_samples, 减小num_leaves
- 因子共线性 → SHAP + PCA/因子正交化
- Regime变化因子失效 → 分层训练/条件因子模型

### 核心文献
1. Ke et al. (2017) LightGBM NeurIPS
2. López de Prado (2018) *Advances in Financial ML* — Purged K-Fold

---

## 二、深度学习时序预测

### BTC 5min适配度: ★★★★☆
多步预测和多模态融合有不可替代优势，建议与GBDT混合架构。

### 前沿Transformer (2023-2025)
1. **PatchTST** (ICLR 2023): 时序分Patch降低复杂度O(L²)→O((L/P)²)
2. **TimesNet** (ICLR 2023): FFT→2D张量→2D卷积捕捉多周期
3. **iTransformer** (ICLR 2024)🏆: 反转！变量为Token，注意力建模变量间相关性
4. **TFT** (2021): 多Horizon + 分位数预测 + 可解释注意力

### BTC 5min关键超参 (iTransformer)
- seq_len=96(8h), pred_len=12(1h), d_model=64, n_heads=4
- dropout=0.2, RevIN=True, loss=MSE+Huber

### 金融时序vs自然语言差异
| 维度 | NLP | 金融 |
|------|-----|------|
| 平稳性 | 稳定 | 高度非平稳 |
| 信噪比 | 高 | 极低 |
| 分布偏移 | 缓慢 | 剧烈(黑天鹅) |
| 多周期 | 层次结构 | 多周期叠加 |

应对: RevIN + 滚动标准化 + 对比学习预训练 + 在线微调

### 核心文献
1. Nie et al. (2023) PatchTST ICLR
2. Liu et al. (2024) iTransformer ICLR
3. Lim et al. (2021) TFT Int.J.Forecasting
4. Kim et al. (2022) RevIN ICLR

---

## 三、强化学习做市与交易

### BTC 5min适配度: ★★★☆☆
高度实验性，仓位管理潜力巨大。

### 算法选择
- 方向决策 → **PPO**（离散买/卖/平）
- 仓位管理 → **SAC**（连续比例，推荐首选）
- 做市 → **SAC** 或 **TD3**

### 奖励函数设计（核心！）
- **P&L-Based**: 直接但忽略风险
- **Sharpe-Based**: 考虑风险但稀疏奖励
- **Differential Sharpe** (Moody & Saffell 2001)🌟: 在线递推，即时反馈+风险调整
  - $dS = (B_t \cdot \Delta A - 0.5 A_t \cdot \Delta B) / (B_t - A_t^2)^{1.5}$

### 状态空间设计
- 市场数据(归一化OHLCV) + 技术指标 + 持仓状态 + 市场状态(spread/OB imbalance/费率) + 外部信号(贝叶斯概率/ML置信度)

### RL过拟合: Sim2Real Gap
- 缓解: 市场模拟器增强 + 域随机化 + 模拟→纸盘→实盘渐进
- **FinRL框架**: AI4Finance开源，集成PPO/SAC/DDPG

### 核心文献
1. Haarnoja et al. (2018) SAC ICML
2. Moody & Saffell (2001) Differential Sharpe NeurIPS
3. Liu et al. (2020) FinRL IJCAI

---

## 四、AutoML与自动特征工程

### BTC 5min适配度: ★★★★☆
自动化因子挖掘显著提升Alpha发现效率，需强过滤机制。

### 遗传规划 (gplearn)
- 函数集: add/sub/mul/div/sqrt/log/rank/delay/delta/ts_mean/ts_std
- `parsimony_coefficient=0.01-0.1`（复杂度惩罚，关键防过拟合）
- 2024-2025前沿: AlphaForge(多目标优化) → AlphaCFG(语法引导) → FactorMiner(自进化Agent)

### Featuretools时序特征
- Deep Feature Synthesis + cutoff_time确保PiT + 多窗口[12,48,96,288]

### 联邦学习跨交易所
- FedAvg/FedProx + 差分隐私 → 数据不出本地，只传模型梯度
- 当前实验阶段，跨交易所合规需求推动落地

---

## 五、混合架构: 与贝叶斯引擎v3.5.1集成

```
贝叶斯概率引擎(P=0.77) → LightGBM因子筛选(Top 20) → SAC仓位管理 → 执行风控层
```

### 实施优先级
- **P0**: LightGBM + Optuna + SHAP
- **P1**: iTransformer/TFT深度模型
- **P2**: SAC仓位管理RL + gplearn自动因子
- **P3**: 联邦学习(研究)

### 技术栈
- 因子: LightGBM 4.x + Optuna 3.x + SHAP 0.45+
- 深度学习: PyTorch 2.x + Time-Series-Library (thuml)
- RL: FinRL + Stable-Baselines3
- AutoML: gplearn + Featuretools
- 部署: ONNX Runtime
