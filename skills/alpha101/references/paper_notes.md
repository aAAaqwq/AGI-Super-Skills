# 101 Formulaic Alphas — 论文笔记

> Kakushadze, Z. (2015). "101 Formulaic Alphas". arXiv:1601.00991

## 核心发现

1. **低相关组合**: 101个alpha平均两两相关仅15.9%，适合组合
2. **收益∝波动率**: R ~ σ^0.76，高波动alpha收益更高
3. **换手率无解释力**: 换手率对alpha收益和相关性无显著影响
4. **持仓期0.6-6.4天**: 短线因子为主

## 因子数据需求

### 基础输入
| 变量 | 定义 |
|------|------|
| open | 日开盘价 |
| close | 日收盘价 |
| high | 日最高价 |
| low | 日最低价 |
| volume | 日成交量 |
| vwap | 日成交量加权均价 |
| returns | 日收益率 (close-to-close) |
| cap | 市值 |
| adv{d} | 过去d天平均成交额 |

### 行业分类（部分因子需要）
- GICS (Global Industry Classification Standard)
- BICS, NAICS, SIC 等均可

## 函数定义

| 函数 | 定义 |
|------|------|
| rank(x) | 截面排名归一化[0,1] |
| delay(x,d) | x在d天前的值 |
| delta(x,d) | x - delay(x,d) |
| correlation(x,y,d) | d天滚动相关 |
| covariance(x,y,d) | d天滚动协方差 |
| scale(x,a) | sum(\|x\|)=a |
| sign(x) | 符号函数 |
| signedpower(x,a) | x^a |
| decay_linear(x,d) | 线性衰减WMA |
| ts_min/ts_max(x,d) | 滚动min/max |
| ts_argmin/ts_argmax(x,d) | min/max位置 |
| ts_rank(x,d) | 时间序列排名 |
| sum/stddev(x,d) | 滚动统计 |
| product(x,d) | 滚动连乘 |
| IndNeutralize(x,IndClass) | 行业中性化 |

## 部分因子解析

### 简单因子（适合入门）
- **#41**: sqrt(high*low) - vwap → 均价偏离
- **#101**: (close-open)/(high-low) → 日内动量
- **#54**: 价格位置反转
- **#12**: sign(Δvolume) * (-Δclose) → 量价背离

### 高IC因子（论文暗示）
- **#1**: 条件波动率 + Ts_ArgMax
- **#7**: 条件ts_rank（成交量触发）
- **#20**: 开盘缺口三重排名
- **#55**: 价格位置与成交量相关性

### 需行业数据的因子（#48, #56, #58-100中部分）
这些因子使用IndNeutralize，加密市场可用sector/板块分类替代。
