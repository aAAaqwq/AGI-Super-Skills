# coin-vp-scanner 配置
# 量价能 R2 高确定信号扫描器 v3 (基于回测: 到 +1% TP 率 71%)

# ---- 币安 API ----
FAPI_BASE = "https://fapi.binance.com"

# ---- 候选筛选 ----
MIN_QUOTE_VOLUME = 10_000_000   # 24h 成交额下限 (USDT), 过滤流动性不足的小币 (可 --min-vol 调低)
MIN_PRICE        = 0.000001     # 过滤极端低价垃圾币
# 全量扫描: 所有通过流动性筛选的币都深扫 (不做 top-N 截断, 避免漏掉刚启动的币)
EXCLUDE_SUBSTR   = ["USDC", "FDUSD", "DAI", "TUSD", "USDP", "EUR", "GBP",
                    "BUSD", "AEUR", "USD1", "SUSD", "USTC", "WBTC"]  # 非目标币
STABLES          = {"USDT"}     # 附加保护
MAX_EXTENDED_24H = 45           # 24h 涨跌超过 ±45% 视为已过度延伸(提示风险, 仍列出但标记)

# ---- 扫描周期 (极短线 scalp: 持仓 1-15min, 吃 1% 目标) ----
PRIMARY_IV      = "5m"      # 信号 K线周期
PRIMARY_CLOSES  = 90        # 看 90 根 5m K线 (~7.5 小时量能基线)
TREND_IV        = "15m"     # 趋势周期
TREND_CLOSES    = 48
CONTEXT_IV      = "1h"      # 大方向上下文
CONTEXT_CLOSES  = 30

# ---- R2 高确定信号参数 (回测校准, 到TP率≈71%) ----
R2_BODY_PCT   = 0.5    # 最近收盘 K线 实体 ≥0.5% (强势单根)
R2_VOL_RATIO  = 2.0    # 该 K线 量能 ≥2x 基线 (放量确认)
TREND_FILTER  = True   # 信号方向需与 15m 短趋势同向 (加严, 参考到TP率≈69%但更稳)
ALIGN_BONUS   = 0.0
