# Binance Square 合约投机雷达 v4.0｜实现规划与关键路径

> 本文件包含源项目实施历史和设计门。仓库同步只发布可复现代码、迁移和测试；历史动态证据、账号状态和报告不构成当前提交的运行时验证凭证。

> 规划日期：2026-07-31（America/Los_Angeles）/ 2026-08-01（UTC）
> 状态：v4.2 只读影子实现已形成；Feed有界覆盖、真实Profile分页与identity mapping/v2已接入，发布门仍未通过
> 产品合同：`GRILL_DECISIONS.md` 的 26 项已确认决策
> 运行基线：v3.1；继续保留并兼容，不原地覆盖历史数据
> 安全边界：只生成研究雷达，不连接交易账户、不自动下单、不输出仓位或杠杆

## 2026-08-02 优化状态增量

本节是当前事实优先的状态覆盖；下文 WBS 保留为完整目标与历史决策记录。

- 当前全量离线测试覆盖顺序生产影子入口、Feed不可变快照与有界停止证据、真实Profile分页、显式job namespace和dedup基线隔离、完整Futures合约目录、官方新闻失败关闭、Smart Money双ID mapping/v2与catalog、五类来源血缘和严格TOP报告schema。确切测试项数以发布回执为准。
- 2026-08-03真实预检后，生产CLI默认不再消费旧版可变signal文件；Futures catalog/server-time门已前移到任何Profile、Smart Money和详情网络请求之前。Feed observed latest与coverage-eligible指针已经分离，锁忙改为失败；生产wrapper也已强制本轮observed/immutable/eligible三者逐字节一致，否则在radar前失败。Profile报告现强制分母、五状态、逐作者outcome、身份唯一性、顶层汇总状态与source coverage对账，完成覆盖率只计`COMPLETE+EMPTY`，全EMPTY按已完成处理。下一合法UTC canary仍是运行发布门。
- 量化门保留发布后到决策时点的SL/TP保守回放、发布前结构 + ATR止损合理性、独立作者/内容簇共识和布林收缩突破确认。本轮帖子覆盖改造明确不新增手续费、滑点、资金费率或深度接口。
- 成本模型未配置时强制 `WATCH`，不再允许名义RR直接成为可执行TOP。
- 组件级只读观测已看到 Smart Money `PNL/ROI` 60个唯一交易员详情；当前Feed surface仅4条并正确标为`PARTIAL`。9个独立seed Profile已取得9/9分页终止证明和12条严格24h帖子。这些都不是合法UTC时槽内的完整生产canary。
- 两份同响应双ID证据已独立批准并进入本地catalog，`topTraderId → squareUid` 为2/60；其余58条保持未映射。默认真实Profile抓取器已经接入，60天point-in-time作者表现仍缺失。完整发布门继续阻塞，详见 `OPTIMIZATION_VERIFICATION.md`。

## 一、结果与成功标准

目标是把现有“广场信息流抓取原型”升级为可审计、可回放、每4小时运行一次的合约投机雷达。完整交付必须同时满足：

1. 每个机会可追溯到稳定作者 ID、原帖版本、计划运行时间和所用 K 线。
2. 每轮严格分析计划运行时点之前的滚动24小时，而不是只分析 `new_posts`。
3. 合约行情优先，现货降级必须显式标记 `SPOT_PROXY`。
4. 评分、硬门槛、多空冲突和结果追踪均为确定性、版本化、可离线回放。
5. 每个 UTC 固定轮次只有一个逻辑运行，失败10分钟后只重试一次。
6. 每轮都有“机会 / 无机会 / 故障”三者之一的明确结果，不把系统故障写成无机会。
7. 未通过影子验证前不得称为“已验证交易策略”，更不得自动下单。

明确不做：

- 不把展示名、粉丝数或 `LIVE` 文本当作作者主键。
- 不用当前时间替代帖子发布时间。
- 不因 Binance 托管普通作者帖子就视为官方核实。
- 不在数据链未合格前先做评分、Telegram 自动推送或调度上线。
- 不用回测或前向结果承诺收益。

## 二、基线证据

截至本规划形成时：

- 最新抓取有199条唯一有效 URL；198/199 有原始时间文本。
- 作者字段只有10/199非空，且全部错误为 `LIVE`。
- 45/199 帖子的正文恰好1200字符，说明被硬截断，不能称为完整正文。
- 当前样例包含 `Jul 29/Jul 30`，现有抓取结果不等于严格最近24小时。
- v3.1 只抓广场主页，没有排行榜、作者 Profile 和独立新闻通道。
- 行情脚本只使用现货 API、5根1h K线；没有合约存在性、15m/4h/1d、BB、ATR或来源标记。
- 11条信号输入只得到9个币种结果，因为当前代码按 symbol 过早去重，会丢失同币多作者和多空冲突证据。
- 去重状态只保留500个 URL/正文前缀；按当前约6轮/天、每轮约199条估算，不足一天覆盖。
- 历史快照、原子写、文件锁和错误不覆盖成功结果可复用；当前没有已验证启用的四小时调度任务。
- 目录内没有自动化测试、依赖清单或 schema migration。

因此 P0 结论是：**先修复“帖子—作者—发布时间”稳定身份链，再做排行榜、评分和调度。**

### 2026-08-01 M1b 受控证据增量

- 用户批准后，通过已登录 Chrome CDP 进行单次只读采集；未读取 Cookie、Token、Local Storage、密码或验证码。
- 已确认目标作者稳定 `squareUid`、Profile 路由别名、3个排行榜徽章、公开实盘标签和官方 `top-traders` 小程序深链。
- 用户随后提供官方 Smart Money Web 入口 `https://www.binance.com/zh-CN/smart-money`；公开页已确认“币安合约聪明钱”与“顶级交易员”页签。
- 初次侦察时只有旧小程序 `30D PNL` 入口证据，四榜覆盖 `0/4 PARTIAL_SEED_DISCOVERY`；这是历史状态。后续公共只读接口已验证当前 Web UI 实际支持 `PNL/ROI`，并各取得完整TOP30，现口径为 `2/2 COMPLETE`。
- 已固化9个 Square Profile-backed 身份/实盘上下文种子；它们仍不是榜单前9名。Smart Money 的60个 `topTraderId` 也不能推断成 Square `squareUid`。
- 最新主页内容启发式抽样中，9个 Profile 的同帖完整 Entry+SL+TP 均为0；所有种子保持作者分0，不得静默晋级 Tier A。
- 本次只解决“入口与种子身份未知”这一子阻塞，仍未满足 M1b 的3次、2个UTC slot、100个唯一帖子与覆盖率门。
- 后续只读采集累计得到5次成功 Feed 快照、04/08 两个 UTC slot 和547个唯一 URL。最新101条详情回源中，66条在严格24小时内，35条因精确发布时间落在窗口外被排除；详情解析 DQ 失败为0。
- 窗口外是资格排除，不是身份/时间解析失败。实现将总隔离拆为 `window_excluded_source_records` 与 `dq_quarantined_source_records`；口径版本化后才能重评 M1b，不能用新分母追认旧门已通过。
- M1b 仍为 `REVISE`：缺具名人工 Square author ID 准确率台账、detail-backed 跨 slot 复核与完整 capture manifest。M2 的 Smart Money `PNL/ROI TOP30` 采集子门已关闭为2/2，但 Square 身份/Profile内容映射仍阻塞作者候选池晋级。

### 2026-08-01 Smart Money 接入增量

- 源项目运行曾产生不可变 Smart Money 证据，但动态响应、运行数据库和操作者环境回执不随公共 Skill 发布；安装者必须自行重新采集并保存当次哈希。
- 证据封装时间 `13:08:02.218117Z`；榜单数据更新时间 `09:59:59Z`；排行 `OBSERVED_WINDOW=13:06:40.786480Z → 13:06:46.944740Z`，不是原子快照。
- PNL/ROI各30行、unique `topTraderId`=60，公开交易员详情60/60；本地动态证据已批准2/60显式映射，发布包默认不携带这些动态artifact，Tier A eligible仍为0。
- ROI小额高倍排名不能独立满足Tier A准入；内容质量、交易时长、至少20条已触发信号以及60天前向结果门保持不变。
- Fixture导入执行语义级兼容门：固定 `30D`、`DESC`、`PNL+ROI`、10行×3页及两个 `onlyShow* = false` filter；payload hash正确但合同语义被改写时仍拒绝。
- 身份映射证据门要求真实文件、文件实际 SHA-256，以及schema对 `topTraderId`/`squareUid` 双ID的显式绑定，不能用声明路径或自行填写hash代替证据。

## 三、目标架构

采用适合当前单机规模的最小架构：不可变 JSON 原始证据 + Python 标准库 SQLite WAL 状态层。首版不需要 Spark、数据湖服务、Pandas 或 TA-Lib。

```text
Binance Square Feed ─┐
Author Profiles ─────┼─> Bronze：不可变原始响应 + manifest + SHA-256（60天）
30D Leaderboards ────┤                         │
Futures / Spot API ──┘                         ▼
                                  Silver：身份、帖子、事件时间、行情、候选
                                                  │
                                                  ▼
                                  Gold：评分机会、追踪结果、作者聚合、报告
                                                  │
                                                  ▼
                                  Delivery Outbox → Telegram（最后启用）
```

建议目录：

```text
binance-square-scanner/
├── scanner/
│   ├── contracts.py       # 版本化 DTO、枚举、字段校验
│   ├── storage.py         # SQLite、迁移、manifest、运行锁
│   ├── cdp.py             # CDP 传输层
│   ├── square.py          # Feed/Profile/Leaderboard 解析
│   ├── authors.py         # 作者注册、证据、Tier
│   ├── market.py          # Futures 优先、Spot Proxy
│   ├── indicators.py      # BB/ATR/成交量/多周期纯函数
│   ├── opportunities.py   # 参数有效性、硬门槛、冲突裁决
│   ├── scoring.py         # 100分模型
│   ├── tracking.py        # 24h触发、72h追踪、R/MFE/MAE
│   ├── reports.py         # 本地完整报告与 Telegram 精简报告
│   └── pipeline.py        # 阶段状态机、checkpoint、outbox
├── scripts/
│   ├── run_radar.py
│   ├── discover_authors.py
│   └── cleanup_retention.py
├── tests/
│   ├── fixtures/
│   ├── test_contracts.py
│   ├── test_square.py
│   ├── test_authors.py
│   ├── test_market.py
│   ├── test_indicators.py
│   ├── test_opportunities.py
│   ├── test_tracking.py
│   ├── test_retention.py
│   └── test_pipeline.py
└── data/v4/
    ├── bronze/{posts,profiles,leaderboards,market}/date=YYYY-MM-DD/
    ├── quarantine/
    ├── radar.sqlite
    ├── reports/
    └── retention_manifests/
```

现有三个 v3 脚本保留为兼容 CLI；新逻辑逐步迁入 `scanner/`，v3 数据只读兼容至少一个迁移窗口。

## 四、必须先冻结的数据合同

核心主键和时间口径：

- `logical_run_id`：生产轮次由 `production_job_id + scheduled_for_utc` 唯一确定；`pipeline_version` 是轮次属性，不能参与生产唯一键。版本切换、崩溃恢复和10分钟重试都不能为同一 UTC slot 创建第二个生产轮次。
- `attempt_id`：一次实际尝试；数据库约束 `attempt_no IN (1,2)` 且 `(logical_run_id, attempt_no)` 唯一，即同一轮最多首次 + 10分钟后重试。
- 离线回放使用独立 `replay_namespace + source_logical_run_id + pipeline_version`，永不写生产 outbox，也不占用生产 slot。
- `post_id`：从 canonical post URL 提取的稳定帖子 ID。
- `author_id`：从稳定 Profile URL/ID 提取；展示名仅作为可变 alias。
- `signal_family_id`：同一帖子/币种/方向跨轮的信号族；后续轮次只更新状态，不能重复计作独立样本。
- `decision_at`：首次 attempt 的 attempt-start UTC，经 Binance server time 30秒偏差门验证后，固化为帖子资格与已闭合 K 线截止时间；必须落在 `scheduled_for_utc` 后 0–10 分钟。server-time验证失败必须终结为`market_catalog/FAILED`，不得用本机时间降级成功。`production_run_cutoff` 每run只写一次；唯一一次 +10 分钟 retry 必须精确复用，而不是把 retry 执行时间写成新 decision。现价、标记价、持仓量等标量是截止后逐币抓取的实时验证值，必须保留独立 `captured_at`，报告只能在其后生成；历史回放不得拿这些未来实时标量冒充点时证据。
- 严格24h：`published_at_utc >= scheduled_for_utc - 24h AND published_at_utc < scheduled_for_utc`。
- `time_precision`：记录发布时间证据精度；只有能确定落在窗口内的记录才可晋级。与24h边界相交的不确定时间必须隔离。
- `text_authority`：优先使用帖子详情页结构化正文/页面正文；Feed 卡片只能标记为摘要。每次编辑按 `content_hash + observed_at` 保存版本，不能用后抓到的正文覆盖历史决策证据。

最小表集：

| 域 | 表 | 目的 |
|---|---|---|
| 运行 | `logical_run`, `run_attempt`, `stage_checkpoint` | 幂等、重试、阶段恢复 |
| 原始 | `bronze_manifest` | 文件路径、SHA-256、来源、schema、事件时间范围 |
| 作者 | `author`, `author_alias`, `author_snapshot`, `leaderboard_observation` | 稳定身份、历史标签、排行榜证据 |
| 帖子 | `post`, `post_version`, `post_observation`, `post_quarantine` | 跨通道去重、编辑版本、异常隔离 |
| 行情 | `instrument`, `ticker_snapshot`, `candle` | 合约存在性、价格和四周期原始证据 |
| 信号 | `signal_candidate`, `signal_outcome` | 参数、来源、触发和结果 |
| 机会 | `opportunity`, `opportunity_evidence` | 分项评分、硬门槛、证据血缘 |
| 聚合 | `author_metric_daily`, `author_tier_history` | 60天滚动 + 长期累计 |
| 交付 | `report`, `delivery_outbox` | 报告哈希、发送尝试和防重复 |

持久化价格与金额使用 Decimal 语义或字符串，不用二进制 float 作为审计真值。所有接口带 `schema_version`、`source_system`、`created_at`、`updated_at`；Gold 结果带 `dq_score` 和 `quality_flags`。

### Spot Proxy 权限范围

- 有效合约交易对的存在性必须来自 point-in-time 合约目录；现货 API 不能证明某合约存在。
- 合约 API 临时失败时，现货可代理当前价格，以及明确标注为现货来源的15m/1h/4h/1d OHLC价格结构和BB/ATR计算。
- 现货成交量不能冒充合约成交量；资金费率、标记价格、持仓量、清算和合约深度不得由现货替代。缺失的合约专属字段记为 `UNKNOWN`，相应分项不得拿满。
- `SPOT_PROXY` 候选仍须满足有效合约、时效、结构、SL和RR硬门槛；总分达到75时可以进入TOP3，但报告必须在币种首行显式标注代理来源和缺失证据。

### Grill 决策到执行合同的补充映射

| 决策 | 必须落库的字段/规则 | 必须通过的测试 |
|---|---|---|
| #3 来源分级 | `source_class=BINANCE_OFFICIAL/SQUARE_UGC`、`market_confirmation_ids` | UGC不能因托管在Binance而自动拿官方分；缺市场确认不得提高对应分项 |
| #5/#6 作者门槛 | `public_live`、`leaderboard_tags`、`trading_days`、`analysis_completeness` | Tier A要求实盘/榜单 + ≥365天 + 持续详细分析；B为90–364天；C<90天；粉丝点赞单独不能晋级 |
| #9 参数优先级 | `parameter_source=AUTHOR/SYSTEM_REDERIVED`、`invalidation_reason`、`original_signal_status` | 原参数有效则沿用；二次入场必须标系统推导；SL/主TP已触发或4h破坏必须过滤 |
| #11 输出上限 | `rank_bucket=TOP/WATCH/FILTER` | TOP最多3，WATCH最多5；不足时不得补数 |
| #18 失败恢复 | `attempt_no`、`failed_stage`、`recovered_silently`、`alert_sent_at` | 首败10分钟重试；重试成功保留常规报告 intent、但不发恢复告警；第二次失败才按阶段告警 |
| #21 作者合成分 | `score_60d`、`score_lifetime`、`score_final` | `score_final = 0.7×score_60d + 0.3×score_lifetime`，使用point-in-time快照 |
| #22 观察期 | `tier_status=EXTERNAL_VERIFIED_PROBATION`、`triggered_count` | 未满20条已触发信号时作者分最高20/25；达到20条后才允许正式晋降级 |
| #24 Tier A简短信号 | `post_completeness`、`independent_market_validation` | 简短信号不能拿满内容分，且只有独立多周期/BB/量价/ATR/RR验证通过才可候选 |

## 五、WBS、依赖 DAG 与主风险链

量级 `S/M/L` 表示相对工作量，不是日期承诺。

| ID | 交付物 | 依赖 | 量级/风险 | 验收门 | 回退点 |
|---|---|---|---|---|---|
| M0 | v4 schema、DTO、生产/回放命名空间、run ledger、离线 fixtures、v3兼容读取 | 无 | M/中 | 旧3份快照可读；同一 `production_job_id + scheduled_for_utc` 在版本切换/重试/恢复下始终只有一轮且最多2次attempt；SQLite完整性通过 | 继续运行v3，只写v4旁路数据 |
| M1a | 作者/时间/全文的离线解析合同、隔离原因与fixture测试 | M0 | M/高 | `LIVE`被拒绝；Feed摘要不得冒充全文；不确定ID/时间进入带原因quarantine；固定时钟24h边界通过 | 不晋级Silver，只保存Bronze |
| M1b | 经人工批准的只读页面侦察、种子Profile ID、详情页正文/时间权威来源及固定fixture | M0 + 人工批准 | M/极高 | 至少3次真实采集、覆盖≥2个UTC slot和≥100个唯一帖子；作者ID人工审计准确率≥98%；精确/安全可判定时间覆盖≥99%；accepted source-record≥90%，quarantine≤10%且100%有原因 | 撤销selector版本，保留证据，不推进M2 |
| M2 | 30D各榜TOP30解析、稳定ID合并与每日候选池 | M1a + M1b | L/极高 | 每个可用榜单的已渲染TOP30记录采集覆盖100%；按稳定ID合并；字段缺失可诊断；展示名变化不产生新作者 | 禁用发现，仅使用已验证种子 |
| M3 | Tier A/B Profile直抓、作者注册、跨通道去重、严格24h | M2 | L/高 | 计划抓取的Tier A/B Profile覆盖≥95%；各通道accepted source-record≥90%、quarantine≤10%且有原因；窗口外/不确定帖子不能进Gold；source-record=accepted observations+quarantined records逐通道对账 | `feed-only` 影子模式 |
| M4 | Futures行情、point-in-time合约目录、15m/1h/4h/1d、BB/ATR/成交量 | M0 | L/中 | 合约优先；Spot Proxy按权限范围降级；四周期闭合状态完整；指标黄金样例通过；原始K线可追溯 | 旧现货检查只作观察，不进TOP3 |
| M5 | 参数有效性、100分模型、硬门槛、同币冲突、TOP3/观察池 | M3 + M4 | L/高 | 分项和=总分；合约/失效/RR硬否决；多空分差<10降观察；高相关只披露不重排 | `shadow_score=true`，不发送 |
| M5R | 结果标签合同：Entry成交、费用、滑点、TP1/TP2退出、超时退出与R定义 | M4 + M5 | M/高 | 固定样例可重算；条件已触发指标与所有已发布信号的无条件指标同时输出；不得只保留可执行成功样本 | 只输出名义点位，不称净R |
| M6 | 24h/72h结果追踪、作者60天/长期统计、Tier历史 | M5R | L/高 | 同根K线按SL先；未触发不算亏但计入可执行率；净R/MFE/MAE幂等；作者评分point-in-time且排除自身结果 | 只记录候选，不更新Tier |
| M7 | 60天留存、聚合对账、清理manifest、恢复演练 | M6 | S–M/中 | 第60天保留、第61天清理；清理前后长期聚合一致；dry-run与恢复通过 | 禁用清理，不删除任何证据 |
| M8 | 完整本地报告、Telegram模板、delivery outbox | M5 + M6 + M7 | M/高 | 每轮明确机会/无机会/故障；报告含抓取时间与证据路径；同一run只有一个outbox记录 | `--no-send` 本地模式 |
| M9 | 完整编排、一次10分钟重试、UTC六时点调度与故障告警 | M8 + 影子发布门 | M/高 | 假时钟验证6个slot；只重试一次；失败不覆盖成功；连续轮次无错轮提交 | 禁用任务并恢复手工运行 |

当前依赖 DAG 与主风险链：

```text
M0 → M1a ───────┐
                 ├→ M2 → M3 ─┐
M0 → M1b(批准) ─┘             │
                              ├→ M5 → M5R → M6 → M7 → M8 → M9
M0 → M4 ──────────────────────┘
```

这是依赖关系和当前主风险链，不是经过工期与资源估算证明的唯一关键路径。作者链与行情链都可能在 `M5` 汇合前成为关键链；每个 Wave 开始时需记录实际量级、负责人、最早/最晚完成时间与 slack 后再更新关键路径。最大外部风险 `M1b` 应在 M0 后经人工批准尽早并行，避免到作者解析完成后才暴露页面字段阻塞。

## 六、执行波次与所有权

| 波次 | 主责 | 可并行工作 | 不能提前做 |
|---|---|---|---|
| Wave 0 | PE/架构 | M0合同、SQLite migration、脱敏fixtures、run ledger | 不改评分规则 |
| Wave 1A | 数据/抓取 | M1a离线合同；获批后M1b页面侦察；随后M2→M3 | 不按展示名建库；未批准不得抓真实页面 |
| Wave 1B | 量化工程 | M4 行情与指标纯函数 | 不静默把现货当合约 |
| Wave 2 | PE + CQO | M5 评分、冲突、TOP3 | 两条数据链未过门不得开工 |
| Wave 3 | CQO + 数据 | M5R结果标签合同、M6追踪与作者统计、M7留存 | 不用未来作者表现回填历史分数 |
| Wave 4 | PE/运营 | M8报告/outbox、M9调度 | 不先接Telegram再补幂等 |
| Gate | Governor/人工 | 证据复核、canary、启用审批 | 不自动部署、不自动交易 |

共享写入点 `contracts.py`、SQLite migration 和 `pipeline.py` 必须单一所有者串行合并；作者流和行情流只通过已冻结 DTO 交互。

## 七、量化验证关键路径

### 7.1 可证伪假设

候选主假设：在相同发布覆盖率和可执行率护栏下，`≥75` 分模型相较“仅通过硬门槛后按 RR + 时效排序”的基线，所有已发布信号的无条件平均净 R 和已触发子集的条件平均净 R均改善，其中预注册主指标至少提高 `0.10R`；同时 `75+` 应优于 `65–74`。

这是假设，不是收益承诺。手续费、滑点、Entry 成交规则和 TP1 后退出规则冻结前，不得称为“净R”。

### 7.2 数据切分

1. 最早60%：开发集，只定义子分规则、缺失值和标签。
2. 随后20%：校准集，冻结分数到成功概率映射、成本和门槛解释。
3. 最后20%：冻结测试集，与前段保留96小时 purge gap，只验收一次，不在测试集调参。
4. 发布前：至少60天前向影子，且达到功效计算与300条已触发信号两者中的较大值；最多观察120天，样本不足结论为“不确定”。

在 M5R 中必须事前冻结：Entry区的成交判定、maker/taker费用、滑点、TP1部分退出比例、TP2/SL剩余退出、72h超时退出价格和 `1R` 分母。冻结前只能报告名义点位结果，不能报告净R。

### 7.3 无泄漏控制

- 只使用 `decision_at` 之前已经闭合的K线。
- 帖子编辑、排行榜、作者战绩采用 point-in-time 快照，禁止用未来数据回填。
- 作者60天/长期分数必须排除正在评估的本条信号结果。
- 保留退市和失效合约，避免幸存者偏差。
- 同帖按 canonical ID 去重；复制帖聚类，不能把转发当独立共识。
- 同币同方向跨轮更新归并为 `signal_family_id`，不能重复计样本。
- 65/75门槛不在冻结测试集上优化；分群/次要指标采用多重比较控制。
- TOP3高相关仍按用户决策保留，但统计推断按UTC日/周区块处理，不能当作三个独立市场事件。

### 7.4 发布门

同时满足才可从影子模式升级为用户可见自动报告：

- 进入Silver记录的作者ID与精确发布时间结构完整率100%；原始数据总体时间覆盖≥99%。
- 作者ID人工审计准确率≥98%；合约行情完整率≥99.5%。
- 开放K线泄漏、重复计数和非确定性回放问题均为0。
- 冻结测试与前向影子中，主指标相对基线提升的95%置信区间下界>0，点估计≥0.10R。
- 前向执行率、发布覆盖率和无机会轮次率达到校准阶段预注册下限；不能只凭“已触发信号”子集通过。条件与无条件结果都按UTC日/周聚类给出。
- `75+` 优于 `65–74`；若输出概率校准，ECE≤0.10。
- ≥99%计划轮次有明确“机会/无机会/故障”状态。
- Profile、排行榜、合约API和Telegram分别完成一次受控canary。

任何泄漏、结果错序、身份错配超门或回放不一致立即停止晋级。发布后数据门失守，或连续两个完整滚动窗口 ECE>0.15 时，回退为“仅观察/等待”，保留采集和审计证据。

## 八、测试矩阵

### 单元/契约

- URL、Profile ID、相对/绝对时间和24h边界解析。
- BB(20,2)、%B、BandWidth、ATR、成交量和RR黄金向量。
- Long/Short Entry区、SL、TP1/TP2、失效条件。
- 100分分项、75/65门槛、硬否决、多空10分差。
- 同根K线SL/TP保守顺序、未触发、MFE/MAE和R。

### 集成/回放

- 使用固定时钟和离线Feed/Profile/榜单/API fixtures完成整轮 `--no-send`。
- 同一逻辑轮次重跑不重复写Silver/Gold。
- 不同通道发现同一帖子时，只增加observation，不复制帖子。
- v3历史快照可兼容读取；v4结果不覆盖v3文件。

### 故障注入

- 抓取后失败、行情后失败、报告后失败。
- 发送成功但本地提交前崩溃：记录Telegram可能只能达到 at-least-once，不能宣称 exactly-once。
- Chrome不可用、单通道失败、Futures失败/Spot Proxy、零帖子、锁冲突。
- 60天清理dry-run、聚合对账失败、暂存恢复。

建议实施后的验收入口：

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -q
python3 scripts/run_radar.py \
  --fixture tests/fixtures/m1b \
  --clock 2026-08-01T13:10:00Z \
  --smart-money-fixture <smart-money-evidence.json> \
  --no-send \
  --output-dir /tmp/binance-radar-acceptance/runs \
  --database /tmp/binance-radar-acceptance/radar.sqlite
python3 scripts/cleanup_retention.py \
  --manifest <retention-manifest.json> \
  --root <retention-root> \
  --as-of 2026-08-01T13:10:00Z
sqlite3 /tmp/binance-radar-acceptance/radar.sqlite \
  'PRAGMA integrity_check; PRAGMA foreign_key_check;'
```

`cleanup_retention.py` 不接受 `--dry-run`；省略 `--apply` 即为默认 `DRY_RUN`。只有真实删除时才同时提供 `--apply` 与精确匹配的 `--confirm-delete-root`。

## 九、风险登记册

| 风险 | 等级 | 影响 | 控制/回退 |
|---|---|---|---|
| 作者ID错误或按展示名合并 | P0 | Tier和长期绩效永久污染 | 稳定Profile ID；人工抽样；异常隔离 |
| 相对/缺年时间不可重放 | P0 | 24h窗口与泄漏失真 | 固定时钟解析；不确定记录进quarantine |
| 正文1200字符截断/UI污染 | P0 | 参数和依据不可审计 | 保存版本化全文；选择器fixture测试 |
| `new_posts`替代滚动24h | P0 | 漏有效旧帖、共识和冲突 | 分离摄取去重与报告窗口 |
| 行情按symbol过早去重 | P0 | 丢同币多作者/多空证据 | 帖子级候选，币种聚合只在冲突层发生 |
| Futures失败静默用Spot | P0 | 指标与结果被污染 | `SPOT_PROXY`强制来源字段和降级门 |
| 共享latest文件串轮 | P0 | 错轮评分、错轮提交 | `run_id + immutable snapshot + checkpoint` |
| 先上线Telegram/调度 | P0 | 重复、漏报、半成品外发 | outbox、shadow、canary、人工启用门 |
| 60天清理破坏长期统计 | P1 | 作者等级无法复核 | 先聚合对账、两阶段清理、manifest恢复 |
| DOM/排行榜动态变化 | P1 | 抓取覆盖突然下降 | selector版本、fixtures、覆盖率告警、单通道降级 |
| Telegram无幂等键 | P1 | 极小崩溃窗口可能重复 | run_id可见、outbox、承认at-least-once |
| 指标/阈值过拟合 | P1 | 回测好、前向失效 | 时间切分、purge、冻结测试、60天影子 |

## 十、第一实施批次

在不登录、不抓真实页面、不发送Telegram的前提下，先交付 M0–M1a：

1. `scanner/contracts.py`：核心 DTO、枚举和24h窗口函数。
2. `scanner/storage.py` + `migrations/001_v4.sql`：run ledger、manifest、作者/帖子最小表。
3. `tests/fixtures/`：由现有3份快照生成脱敏兼容fixture，并预留Profile/榜单fixture格式。
4. `tests/test_contracts.py`：固定时钟、ID、Decimal、schema版本、严格窗口。
5. `tests/test_square.py`：`LIVE`拒绝、无ID/无精确时间隔离、全文不截断。
6. `scripts/run_radar.py --fixture <fixture-dir> --no-send`：离线回放入口；需要 Smart Money 时额外提供 `--smart-money-fixture <evidence.json>`。

第一批次退出条件：

- 旧3份快照均能回放且不改原文件。
- 同一 `production_job_id + scheduled_for_utc` 在版本切换、两次attempt与崩溃恢复下仍只有一个生产逻辑轮次；离线回放只能进入replay namespace。
- 按来源记录/observation口径满足 `accepted observations + quarantined source records = bronze source records`；唯一帖子数另行统计，不混用口径。
- `LIVE` 作者为0；任何不确定作者/时间不得进入Silver。
- SQLite完整性、外键和离线测试全部通过。

随后进入 M1b：经人工批准执行受控、只读、已登录页面证据采集，确认种子作者稳定 Profile ID、详情页正文/时间权威来源、排行榜入口和真实字段。M1b 达到非空样本与覆盖率门后才能进入 M2。

## 十一、人类批准门

以下动作不属于本规划自动授权范围，实施到对应阶段时需单独确认：

- 使用已登录浏览器采集真实 Profile/排行榜页面证据。
- 启用定时任务或常驻后台进程。
- 启用 Telegram 真实自动发送和故障告警。
- 连接任何交易账户、API Key 或执行交易；本项目默认永不执行。

## 十二、Swarm 综合记录

- 数据工程审计：主张不可变Bronze + SQLite Silver/Gold，作者ID、事件时间和运行账本为P0。
- PE工程审计：主张保留v3兼容入口、按小模块拆分，作者主链与行情支线在M5汇合。
- CQO实验审计：主张时间切分、point-in-time、purge、冻结测试和至少60天前向影子。
- Governor首轮审查：结论 `REVISE`；指出生产轮次唯一键、M1真实证据、quarantine空门、决策可追踪性、双汇合链、Spot Proxy和结果标签合同七项问题。
- CEO修订：生产轮次改为slot唯一；拆分M1a/M1b；加入真实样本/accepted/quarantine/Profile覆盖门；补充Grill映射、Spot Proxy权限和M5R；将“唯一关键路径”更正为依赖DAG与双主风险链；不在本规划中启用任何外部动作。

## 十三、2026-08-01 执行状态

### 已关闭的代码/合同门

- M0/M1a：v4.1增量合同、001→002迁移、不可变产物、生产/回放命名空间、attempt原子分配、成功后切latest。
- M1b局部：最终真实canary为103个canonical候选、62窗口内、41窗口排除、DQ 0；13币公共Futures链路成功。人工作者ID准确率台账仍未关闭。
- M2代码：历史四榜严格TOP30解析合同保留；当前真实 Smart Money Web UI 只支持并完成 `PNL/ROI 2/2`。Square身份/Profile内容未映射，因此M2的作者池晋级与M3仍未关闭。
- M3代码：Profile计划/五状态、Profile+Feed observation去重与fixture通过；真实Profile执行0/9，因此里程碑整体未关闭。
- M4/M5：四周期、BB/ATR/量能/RR、点时K线`endTime`冻结、SYSTEM_REDERIVED与复制安全共识已接标准pipeline。
- M6局部：signal family/revision/evaluation持久化与纯追踪通过；真实60天结果样本尚未形成。
- M7代码：60天清理、聚合对账与dry-run合同通过；真实60天历史门未关闭。
- M8/M9代码：报告、UTC六slot、单次+10分钟重试、静默恢复、分类alert intent通过；真实outbox写入、Telegram canary和常驻调度保持关闭。
- 发布恢复：raw/market/report/Markdown 均纳入 manifest；若 attempt 已提交 `SUCCEEDED` 但 `latest` 指针切换失败，可由 `scripts/repair_latest.py` 校验全部 SHA-256 后幂等修复，不新建 attempt、不重抓。
- 审计时序：manifest 在文件落盘后取钟，attempt finish 在报告与 manifest 完成后取钟；不再复用 attempt start 时间冒充完成时间。
- 失败审计：logical run 与 RUNNING attempt 在 catalog/detail 等外部采集之前分配；早期 FETCH 失败也必须落为 FAILED attempt1，只有显式 scheduled retry 可复用首次 decision 并分配 attempt2。
- 冻结cutoff：`003_production_cutoff.sql`为每个生产logical run持久化唯一decision；attempt2传入不同值时在分配前拒绝。Binance server-time不可用不再降级为成功报告。

### 验收凭证与发布边界

- `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -q`：169 tests，PASS。
- 源项目历史 JSON、Markdown 和 SQLite 回执未收入公共包；仓库收录不构成运行时验证。
- 时序：slot=`2026-08-01T12:00:00Z`，冻结decision=`12:00:13.877380Z`；Square、market、report、manifest、attempt finish严格按完成顺序记录；全部K线close time早于decision。
- 产物：raw/market/report JSON/report Markdown/seed evidence五类manifest的文件存在且SHA-256全匹配。
- 报告结论：WAIT；不发送、不安装调度、不交易。
- 源项目 Smart Money 加固后 fixture canary 曾通过文件hash与数据库完整性检查；公共包只保留复现代码与测试，必须由当前commit重新生成回执。
- Smart Money接入完成时已错过 `12:00Z + 10m` 生产门，未伪造 real production canary；下一合法时槽为 `16:00Z`。fixture canary不证明策略有效。

### 仍在关键路径上的外部门

1. 为 Smart Money `topTraderId` 建立有来源的 Square `squareUid` 映射；不得把当前2/2排行覆盖误报为作者身份覆盖。
2. 执行9个种子及未来Tier A/B作者的真实Square Profile内容主通道，达到≥95%计划覆盖和内容质量门。
3. 先以HELD outbox完成受控Telegram canary，再单独批准真实发送；不得直接从内存intent跳到常驻推送。
4. 完成受控UTC调度canary后才安装后台任务；失败阶段映射和恢复状态需要落库。
5. 累积至少60天且满足预注册样本量；在此之前不得把WAIT或单次系统推导解释为策略有效性结论。
