# Binance Square Scanner｜授权与启用回执

> 记录时间：2026-08-01（America/Los_Angeles / UTC）  
> 用户原话：`全部授权`

## 已授权范围

- 复用用户已登录的 Binance Chrome 会话做受控只读页面检查和 CDP 采集。
- 访问 Binance 公开页面与公开 GET 行情/帖子详情接口。
- 在证据门通过后启用本地每 4 小时采集调度、一次失败重试与本地影子报告。
- 在发布门和受控 canary 通过后启用 Telegram 报告与故障告警。
- 需要时连接专门的 paper-trading 测试环境，但必须先冻结 M5R 成交、费用、滑点、退出与 R 定义，并再次记录具体环境和启用回执。

## 授权不等于已经启用

- 当前已执行：只读 Chrome/CDP 采集、公开详情回源、公开 Futures 行情、本地 `--no-send` 影子报告。
- 当前未执行：常驻调度、Telegram 真实发送、交易所测试账户连接、真实下单。
- Smart Money 已真实完成当前官方可观测的 `PNL/ROI TOP30`，覆盖为 `2/2 COMPLETE`；旧 `0/4` 仅是接入前历史口径。60个 `topTraderId` 到 Square `squareUid` 的显式身份映射仍为 `0/60`，Square作者主通道与量化发布门未通过，因此外发和常驻调度继续保持关闭。
- `quant-trader` 研究合同与本项目安全边界禁止真实交易。即使用户提供广泛授权，也不能把研究雷达升级成自动下单系统；若未来改变目标，必须另立受监管、账户隔离和逐笔批准的项目。

## 数据与账户边界

- 禁止读取 Cookie、Token、Local Storage、密码或验证码。
- 禁止把 Square UGC 当作 Binance 已核实新闻。
- 禁止把 Profile 种子当作排行榜名次，或在内容质量门未通过时给作者加分。
- Smart Money/Square 身份映射必须有真实证据文件、文件实际 SHA-256 与schema双ID绑定；Smart Money fixture 即使payload hash有效，也必须重新通过固定的榜单语义合同。
- 所有对外发送、调度启用和测试账户连接都必须保留可回退配置、canary 证据与独立 Governor 复核。
