# polyclaw
> 多策略聚合交易——Polymarket/CLOB 多策略交易执行引擎

**状态**: 部分实现 — 有 Python 库代码

## 已有模块
- `lib/llm_client.py` — LLM 客户端
- `lib/gamma_client.py` — Gamma API 客户端（Polymarket）
- `lib/clob_client.py` — CLOB 订单簿客户端
- `lib/wallet_manager.py` — 钱包管理
- `lib/contracts.py` — 合约交互
- `lib/coverage.py` — 覆盖率分析
- `lib/position_storage.py` — 持仓存储

## 配置要求
- Python 3.10+
- Polymarket API 密钥
- 钱包私钥（环境变量）
