# 5minbtc 新闻数据源 (2026-07-05 清理后)

## 当前在用 (1个)
| 源 | 类型 | 延迟 | 状态 |
|----|------|------|------|
| CoinDesk RSS | RSS | ~14min | 唯一稳定源 |

## 已移除源 (验证失效, 2026-07-05 清理)
- Cointelegraph RSS - 144min+ 延迟 / TG 脚本不存在
- TreeNews TG - 脚本不存在 (`scripts/telegram-treenews.py` missing)
- TheBlock RSS - SSL 封锁
- BitcoinMagazine RSS - 连接重置
- NewsData.io API - 无 API key
- CryptoCompare API - 无 API key
- Binance Blog RSS - 未在 scan_all 调用 (与 Binance 平台新闻重叠)
- alternative.me FGI - 引擎 `_fetch_fng()` 已独立获取, 引擎自带

## 评估中 (待调研)
- CryptoPanic API (免费层) - 待实测延迟
- The Block RSS 新端点
- 中文: PANews, Foresight News, 巴比特, 吴说区块链
