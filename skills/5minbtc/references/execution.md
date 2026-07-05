# 5minbtc 执行步骤 (LLM 工作流)

## 铁律
1. 每次必须重新执行引擎脚本 — 不缓存
2. 每次必须重新搜索3组新闻
3. 先 settle 上一根, 再 log 新预测
4. LLM 可微调引擎的 bias/pred_close/range, 但必须说明理由
5. 输出 15-25 行 (平衡深度和 Telegram 可读性)

## 执行步骤

### Step 1: 并行启动 (5个调用同时发出)
```
并行组:
├── exec: settle-all + 引擎脚本 + 新闻扫描 (合并一条命令)
├── web_search: "Bitcoin BTC breaking news price" count=3 freshness=day
├── web_search: "crypto market macro stocks today" count=3 freshness=day
└── web_search: "比特币 BTC 最新 晚间" count=3 freshness=day
```

### 引擎命令 (绝对路径)
```bash
SKILL_DIR=/home/aa/.hermes/profiles/cqo/skills/5minbtc && \
  python3 $SKILL_DIR/5minbtc-log.py settle-all 2>&1; \
  echo "---ENGINE---"; \
  python3 $SKILL_DIR/5minbtc-engine-v5.7.py 2>&1; \
  echo "---NEWS---"; \
  python3 $SKILL_DIR/5minbtc-news.py 2>&1
```

### Step 2: LLM 完整分析
详见: [output-template.md](output-template.md)

### Step 3: 记录日志
```bash
SKILL_DIR=/home/aa/.hermes/profiles/cqo/skills/5minbtc && \
  python3 $SKILL_DIR/5minbtc-log.py log \
    "<engine.candle.iso>" \
    <final_pred_close> \
    <final_pred_high> \
    <final_pred_low> \
    <confidence> \
    <final_bias> \
    <news_sentiment> \
    <engine.indicators.vol_pct>
```

## 超出设计时间窗口的处理
本 skill 设计预测**单根 5 分钟 K线**。当用户问更宽的时间窗口 (如"20:00-24:00 up or down"), 不能直接套用单根 5min 预测。
- 仍按标准流程跑当前 5min K线完整预测
- 基于当前快照的宏观读数给宽窗口**方向倾向**, 标注"超出引擎置信区间"
- 建议在该窗口起始时间 (如 20:00) 再次触发 5minbtc

## 搜索优化
3 组通用搜索常返回首页/目录页。如果初始结果不具体, 追加 1-2 组上下文定制搜索 (用当前价格方向 + 关键事件)。LLM 分析前发起, 延迟 <30s 但信息价值显著。
