# 加密货币交易学习系统

使用 1 USDT 作为学习成本，系统化学习加密货币交易。

## 快速开始

### 1. 安装

```bash
cd ~/clawd/crypto-learning

# 创建快捷命令（可选）
echo 'alias crypto="~/clawd/crypto-learning/crypto"' >> ~/.bashrc
source ~/.bashrc
```

### 2. 第一步：准备

```bash
# 查看准备清单
crypto checklist
```

完成以下任务：
- [ ] 注册交易所（Binance/OKX/Bybit）
- [ ] 设置 2FA 安全验证
- [ ] 入金 1 USDT
- [ ] 创建交易账户

### 3. 开始学习

```bash
# 查看今日任务
crypto daily

# 查看学习进度
crypto progress show

# 学习 K 线知识
crypto learn show kline_basics

# 测试理解
crypto learn quiz kline_basics
```

### 4. 模拟交易

在学习阶段，使用交易所的模拟账户（如果有）进行模拟交易：

```bash
# 记录模拟交易
crypto trade add --symbol BTC/USDT --action buy \
  --price 50000 --amount 0.00002 \
  --stop-loss 49000 --take-profit 52000 \
  --notes "模拟交易：突破阻力位"

# 查看交易记录
crypto trade list

# 交易统计
crypto trade summary
```

## 学习路径

### 阶段 1：准备阶段（Day 1-2）
- [ ] 注册交易所
- [ ] 设置 2FA
- [ ] 入金 1 USDT
- [ ] 创建账户

### 阶段 2：基础学习（Day 3-5）
- [ ] 学习 K 线基础
- [ ] 学习订单类型
- [ ] 模拟交易练习
- [ ] 小额实盘测试（0.1 USDT）

### 阶段 3：技术分析（Day 6-10）
- [ ] 学习支撑位/阻力位
- [ ] 学习趋势分析
- [ ] 学习技术指标
- [ ] 实践技术分析

### 阶段 4：风险管理（Day 11-15）
- [ ] 学习仓位管理
- [ ] 学习止损止盈
- [ ] 制定交易计划
- [ ] 执行交易计划

### 阶段 5：实盘实践（Day 16+）
- [ ] 第一笔交易
- [ ] 记录每笔交易
- [ ] 复盘交易
- [ ] 优化策略

## 命令参考

### 学习管理
```bash
crypto progress show              # 查看学习进度
crypto progress complete 1 register_exchange
                                 # 标记任务完成
```

### 知识学习
```bash
crypto learn list                 # 列出所有学习卡片
crypto learn show kline_basics    # 显示学习卡片
crypto learn quiz kline_basics    # 测试理解
```

### 交易记录
```bash
crypto trade add [选项]          # 添加交易记录
crypto trade list                # 列出所有交易
crypto trade summary             # 交易统计
```

### 日常管理
```bash
crypto daily                    # 每日学习任务
crypto review                   # 交易复盘
```

## 可用的学习卡片

### 技术分析
- `kline_basics` - K 线基础知识
- `support_resistance` - 支撑位和阻力位

### 交易基础
- `order_types` - 订单类型
- `trading_plan` - 交易计划

### 风险管理
- `risk_management` - 风险管理

## 使用示例

### 完整的学习流程

```bash
# 1. 每天开始
crypto daily

# 2. 学习新知识
crypto learn show support_resistance

# 3. 测试理解
crypto learn quiz support_resistance

# 4. 实践（模拟或小额）
crypto trade add --symbol BTC/USDT --action buy \
  --price 98000 --amount 0.0000102 \
  --stop-loss 95000 --take-profit 105000 \
  --notes "突破阻力位买入"

# 5. 每天结束
crypto review
crypto progress complete 2 learn_kline
```

### 完整的交易流程

```bash
# 1. 分析市场（使用学习卡片）
crypto learn show support_resistance

# 2. 制定交易计划（手动或使用模板）
# - 入场条件：突破阻力位
# - 仓位：0.5 USDT
# - 止损：支撑位下方 3%
# - 止盈：风险回报比 1:2

# 3. 执行交易
crypto trade add --symbol BTC/USDT --action buy \
  --price 98000 --amount 0.0000102 \
  --stop-loss 95000 --take-profit 105000 \
  --notes "突破阻力位，风险回报比 1:2"

# 4. 监控（在交易所）
# 等待止盈或止损触发

# 5. 记录结果
crypto trade add --symbol BTC/USDT --action sell \
  --price 103000 --amount 0.0000102 \
  --profit 0.0506 \
  --notes "止盈触发，收益 +5.06 USDT"

# 6. 复盘
crypto review
```

## 风险提醒

⚠️ **重要：这只是为了学习，不要追求盈利！**

- 只投入你能承受损失的金额（1 USDT）
- 永远设置止损
- 不要使用杠杆
- 记录每一笔交易
- 定期复盘和改进

## 数据文件

所有数据存储在 `~/clawd/crypto-learning/`：

- `progress.json` - 学习进度
- `trades.json` - 交易记录

定期备份这些文件！

## 学习目标

**这个系统的目标不是赚钱，而是：**

1. ✅ 掌握基础知识和术语
2. ✅ 学会制定交易计划
3. ✅ 建立风险管理的习惯
4. ✅ 积累交易经验
5. ✅ 形成自己的交易系统

**如果能保住这 1 USDT，就是成功！**

## 常见问题

### Q: 1 USDT 太少，怎么操作？
A: 可以选择：
- 使用 USDT-M 永续合约（最小 0.001 USDT 开仓）
- 选择交易量大的币种（如 BTC、ETH、DOGE）
- 模拟交易练习（不使用真实资金）

### Q: 我应该先学习什么？
A: 建议顺序：
1. K 线基础（kline_basics）
2. 订单类型（order_types）
3. 风险管理（risk_management）
4. 支撑阻力（support_resistance）
5. 交易计划（trading_plan）

### Q: 模拟交易有用吗？
A: 非常有用！模拟交易可以：
- 不用真金白银练习
- 测试你的交易系统
- 建立信心和纪律
- 等准备好后再用真金

### Q: 多长时间能学会？
A: 这取决于你的投入：
- 每天 1-2 小时：约 2-4 周完成所有阶段
- 每周几次：约 2-3 个月完成所有阶段

记住：学习是持续的，没有终点！

## 下一步

```bash
# 开始你的学习之旅
cd ~/clawd/crypto-learning

# 查看准备清单
./crypto checklist

# 查看今日任务
./crypto daily
```

**祝学习顺利！记住：保护本金，学习第一！** 🎯
