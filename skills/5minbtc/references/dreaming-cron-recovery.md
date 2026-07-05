# Dreaming Cron 故障恢复指南

> 最后更新: 2026-06-13

## 已知故障模式

### 模式1: 数据源不可用导致 Dreaming 失败

**现象**: Dreaming cron 输出以 `RuntimeError: Connection error` 结尾
**根因**: 引擎 `5minbtc-engine-v5.7.py` 无法获取 K线数据 (历史故障: Binance API 451 区域封禁)
**影响**: Dreaming 无法初始化因子计算和预测，整个分析报告为空

**恢复步骤**:
1. 修复数据源（将引擎从 Binance 迁移到 CoinGecko/Bybit 等可用源）
2. 手动执行一次引擎验证: `python3 /home/aa/.hermes/profiles/cqo/skills/5minbtc/5minbtc-engine-v5.7.py`
3. 确认输出包含有效 K线数据后，强制运行一次 cron:
   ```
   cronjob(action='run', job_id='3016e27ddefa')
   ```
4. 验证输出: 检查 cron output 目录下的最新文件

**注意**: cron job 不会自动重试 — 一旦失败不会自动恢复。必须手动修复后重新触发。

### 模式2: Engine 文件修改后未更新 cron 引用

**现象**: 引擎实际运行内容与预期不符
**根因**: cron job 的 `name` 字段标签过时
**修复**: `cronjob(action='update', job_id='3016e27ddefa', name='5minbtc vX.Y')`

### 模式3: 引擎路径硬编码指向错误路径

**现象**: 文件未找到或 import 错误
**根因**: SKILL_DIR 硬编码指向 workspace 而非 skill 目录
**修复**: 使用 `os.path.dirname(os.path.abspath(__file__))` 替代绝对路径

### 模式4: CoinGecko API 限流/超时

**现象**: 手动替代数据源(fallback)也失败 — curl 返回 exit 28 (timeout)
**根因**: CoinGecko free tier 对频繁请求有限流; 中国大陆 IP 可能被限
**影响**: 手工预测推演不可用, 只能在有缓存的历史数据上工作
**恢复步骤**:
1. 切换至备用 API: `api.coingecko.com/api/v3/simple/price` (轻量) 通常可用
2. 若 lightweight price API 也超时, 使用 Bybit public API:
   ```bash
   curl -s "https://api.bybit.com/v5/market/klines?category=spot&symbol=BTCUSDT&interval=5&limit=100"
   ```
3. 或 OKX public API:
   ```bash
   curl -s "https://www.okx.com/api/v5/market/candles?instId=BTC-USDT&bar=5m&limit=100"
   ```
4. 验证后更新引擎的数据源接入代码
5. 2026-06-13 实际诊断: CoinGecko OHLC endpoint 超时但 simple/price 可能可用 — 建议用 Bybit/OKX 作为主要 fallback

**修复**: 引擎需要实现多数据源 fallback 链: Binance(workaround) → Bybit → OKX → CoinGecko

## Dreaming Cron 配置参考

| 属性 | 值 |
|------|-----|
| Job ID | `3016e27ddefa` |
| 调度 | 每天 04:30 CST (UTC+8) |
| 技能 | `5minbtc` |
| 引擎路径 | `/home/aa/.hermes/profiles/cqo/skills/5minbtc/5minbtc-engine-v5.7.py` |
| 输出目录 | `~/cron/output/3016e27ddefa/` |
| 最后成功 | 2026-06-11 (CPI分析报告) |
| 最后失败 | 2026-06-13 — Binance 451 (engine 故障) + CoinGecko 超时 (hand-fallback 故障) |
| 双重故障状态 | 两个数据源均不可用 — 引擎+手工都无法运作 |

## 验证命令

```bash
# 验证数据源可用性
curl -s -o /dev/null -w "%{http_code}" "https://data-api.binance.vision/api/v3/klines?symbol=BTCUSDT&interval=5m&limit=5"

# 手动运行引擎
python3 /home/aa/.hermes/profiles/cqo/skills/5minbtc/5minbtc-engine-v5.7.py

# 检查最新 cron 输出
ls -lt ~/.hermes/profiles/cqo/cron/output/3016e27ddefa/ | head -5
```
