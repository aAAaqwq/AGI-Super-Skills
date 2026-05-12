# Data Sources Skill v2

获取实时市场数据的统一接口。所有数据源均无需browser依赖（Elon除外）。

## 快速使用

```bash
# 获取所有数据
bash ~/.openclaw/workspace-CQO/scripts/data_sources_v2.sh all

# 获取单项数据
bash ~/.openclaw/workspace-CQO/scripts/data_sources_v2.sh btc
bash ~/.openclaw/workspace-CQO/scripts/data_sources_v2.sh oil
bash ~/.openclaw/workspace-CQO/scripts/data_sources_v2.sh fed
bash ~/.openclaw/workspace-CQO/scripts/data_sources_v2.sh gold
```

## 数据源列表

### 加密货币 (Binance实时)
| 品种 | 命令 | API端点 |
|------|------|---------|
| BTC | `btc` | `api.binance.com/api/v3/ticker/price?symbol=BTCUSDT` |
| ETH | `eth` | `api.binance.com/api/v3/ticker/price?symbol=ETHUSDT` |
| SOL | `sol` | `api.binance.com/api/v3/ticker/price?symbol=SOLUSDT` |
| 黄金 | `gold` | `api.binance.com/api/v3/ticker/price?symbol=PAXGUSDT` |

### 大宗商品 (FRED, 延迟1-2天)
| 品种 | 命令 | 说明 |
|------|------|------|
| WTI原油 | `oil` | FRED DCOILWTICO |
| BRENT原油 | `oil` | FRED DCOILBRENTEU |

### 宏观数据 (FRED)
| 数据 | 命令 | 说明 |
|------|------|------|
| Fed利率 | `fed` | FRED FEDFUNDS, 月度更新 |

### 社交媒体
| 数据 | 命令 | 获取方式 |
|------|------|----------|
| Elon推文 | `elon` | **需browser** (见下方) |

## Elon推文获取

### 方法1: 内置browser (推荐)
```
browser(action='navigate', profile='openclaw', targetUrl='https://xtracker.polymarket.com/user/elonmusk')
browser(action='snapshot', compact=true)
```
从snapshot提取 "X Total Posts" 数字。

### 方法2: fbu (备选)
```bash
export PATH="$HOME/.cargo/bin:$PATH"
export DISPLAY=:1
timeout 30 fast-browser-use snapshot \
  --url "https://xtracker.polymarket.com/user/elonmusk" \
  --headless true
```
⚠️ fbu可能无法获取完整页面内容。

### 方法3: xtracker API (无计数)
```bash
curl -s 'https://xtracker.polymarket.com/api/users/elonmusk' | jq '.data.trackings[0].title'
```
返回市场标题，但**没有currentCount**。

**推荐**: 用内置browser获取。

## 示例输出

```
=== 2026-03-06 23:10:07 ===
--- 加密货币 (Binance实时) ---
BTC: $68,369.86
ETH: $1,975.45
SOL: $84.26
--- 大宗商品 ---
GOLD (PAXG): $5,157.71/oz
OIL WTI: $71.13 (2026-03-02)
OIL BRENT: $77.24
--- 宏观数据 (FRED) ---
FED RATE: 3.64% (2026-02-01)
--- 社交媒体 ---
ELON POSTS: 需要browser访问xtracker获取
```

## 注意事项

1. **每次调用前自动清代理**
2. **超时10秒**
3. **FRED数据有1-2天延迟**
4. **Elon推文需browser** (xtracker API不提供计数)

## 脚本位置
`~/.openclaw/workspace-CQO/scripts/data_sources_v2.sh`

---
*创建: 2026-03-06 | 更新: v2*
