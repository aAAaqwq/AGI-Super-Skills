---
name: binance-square
description: |
  币安广场合约投机雷达 v5：以最近24小时专业交易帖为主要证据，回源核验帖子，
  联合币安公共合约行情、4周期K线、布林带、ATR、量能和RR，生成可审计的本地影子报告。
  触发词：币安广场、扫描币安、binance square、合约机会、交易信号雷达、4小时雷达
metadata: {"version":"5.0.0","mode":"shadow","runtime_effects":"read-only-no-send"}
---

# 币安广场合约投机雷达 v5.0（Shadow）

> 当前可真实运行的是只读影子报告：不发 Telegram、不创建定时任务、不下单。

## 必读合同

执行前完整读取：

1. `GRILL_DECISIONS.md`：用户确认的产品、作者、行情、评分、追踪与留存规则。
2. `V4_IMPLEMENTATION_PLAN.md`：里程碑、证据门和已知阻塞。

不得把设计目标描述成已经上线的能力。最终结论必须来自当次生成的 JSON/Markdown 和测试结果。

## 当前已实现

- v5.0 对候选分层做了探索性放宽：`TOP >= 55`、`WATCH >= 40`；缺少 Entry/SL/TP 时按字段完整度部分计分，不再仅因缺字段进入评分硬过滤，但执行就绪状态保持 `UNAVAILABLE`，不能成为可执行 TOP。TP1 RR `1.2` 与主要目标 RR `1.5` 是评分线；主要目标低于 `1.5` 仍硬过滤。
- v5.0 增加 `--scheduled-retry` 入口和最多两次相互独立的 Feed 捕获；重试不得跨次拼接帖子或复用旧快照冒充本轮成功。
- Telegram renderer 改为面向用户的简洁摘要；完整 JSON/Markdown、manifest 与 SQLite 仍是唯一审计事实源，精简消息不能替代证据文件。

- 标准入口默认容量 200；Profile 是专业作者帖主通道，Feed 与经过人工/模型提取的参数信号 URL 作有界补充，按 canonical `post_id` 去重且保留全部来源 observation。
- Feed 使用 `square-feed-coverage/v1`：必须从顶部开始，并记录滚动几何、两相懒加载触发、停止原因和覆盖状态。当前 scope 固定为 `BINANCE_SQUARE_DISCOVER_DOM`，`global_denominator_known=false` 且 `pagination_api_exhaustion_verified=false`；即使达到声明下限并稳定穷尽 DOM 而标 `BOUNDED_COMPLETE`，也只代表该次 DOM surface，不代表内部 feed API 或整个平台。容量、滚动预算、错误或未验证旧快照分别标 `CAPPED/PARTIAL/BLOCKED/LEGACY_UNVERIFIED`。
- Feed 每次成功观察都写不可变快照和 `binance_raw_posts.json` observed latest。`capture_attempt_no`、`capture_attempt_limit` 与表示稳定物理底部事实的 `surface_exhausted` 是 `square-feed-coverage/v1` 的向后兼容可选诊断扩展，旧 v1 证据不会被静默升级。只有严格满足 `BOUNDED_COMPLETE + EXHAUSTED + minimum_target_met + unique>=preferred_minimum` 的 Discover DOM 捕获才推进独立 `binance_raw_posts_eligible.json`。PARTIAL 证据必须保存但不得覆盖既有 eligible 指针；抓取锁忙以非零状态失败，不能复用旧 latest 冒充本轮成功。
- Feed 文本在 CDP 入站时执行 Unicode scalar 规范化：合法 emoji 代理对保持原义，孤立 UTF-16 surrogate 仅替换为 `U+FFFD` 并计入 `malformed_unicode_replacements`。最终 JSON 写入层再次递归兜底；写入失败必须清除临时文件，单个异常字符不得拖垮整批帖子。
- 生产 wrapper 默认最多执行两次相互独立的 Feed 捕获（`--capture-attempt-limit 1` 可回滚为单次），首次 eligible 立即停止；两次都未 eligible 时只选择最新一次合法捕获进入 radar，不跨次拼接帖子，也不读取旧 eligible。`PARTIAL` 与达到 200 条硬上限的 `CAPPED` 都只作带原始覆盖标签的不完整 Feed 补充，`CAPPED` 不得冒充穷尽。每次 observed latest 都必须刷新、与当次 immutable snapshot 逐字节一致并通过 v1 合同；只有 eligible 捕获才额外要求 eligible pointer 逐字节一致。Feed 是 Profile 主通道的补充，合法不完整捕获不再阻断 Profile，但下游仍必须如实保留覆盖状态；malformed、未刷新、错误或指针不一致继续失败关闭。
- 逐帖请求币安公开详情接口，使用稳定 `post_id`、`author_id`、权威正文与精确发布时间。
- Profile + Feed 双通道已接入真实只读 pipeline：Profile 计划只认稳定 `squareUid`，通过匿名公共 GET 从 `timeOffset=-1` 分页；逐条用 `firstReleaseTime` 执行严格24小时窗口，并以可验证 cursor 水位、空页或无 next 作为终止证明。置顶旧帖不会造成提前停止，cursor 停滞/上升、锚点不匹配、schema 漂移、请求失败或页预算耗尽均失败关闭为 `PARTIAL`。
- 历史 fixture 保留 30D `PNL/ROI/VOLUME/WIN_RATE` 四榜解析合同；当前真实 Smart Money 接入只支持官方 Web UI 已观测的 `PNL/ROI`，每榜必须恰好30个唯一排名与 `topTraderId` 才可标记 `COMPLETE`。
- Smart Money 公共只读 API 已接入标准 pipeline：`--smart-money` 在线采集，`--smart-money-fixture` 注入带完整性校验的证据；排行、交易员详情与 Square 身份映射分别计数，不能相互代替。
- 单次生产影子入口 `scripts/run_production_cycle.py` 会按上述独立捕获规则刷新 Feed，再以前台、顺序、`--no-send` 方式运行 Smart Money、官方新闻与雷达；Feed 快照超过10分钟或来自未来时失败关闭。离线测试只验证选择与失败关闭合同，尚无真实双捕获稳定性回执。
- 生产 wrapper 为每个长时间子进程每30秒输出一次可刷新的 `[HEARTBEAT]`，避免调度器把正常静默分析误判为无输出挂死；父进程异常退出时会终止并回收子进程。`run_radar.py` 将 `SIGTERM` 转成可审计异常，使已创建的 attempt 进入 `FAILED`，而不是永久遗留 `RUNNING`。
- `scripts/render_latest_telegram.py --report <committed-report.json>` 只读取已提交报告并复用标准 `render_telegram` 合同输出精简文本；它本身不发送。账号、目标、调度与实际发送仍属于安装环境的外部配置，不随公共 Skill 发布。
- 生产入口默认不再消费旧版可变 `data/signal_check_input.json`；只有显式传入 `--signals-json` 才把它作为有manifest的补充来源。真实 pipeline 在任何 Profile、Smart Money 或帖子详情网络请求之前获取一次 Futures catalog 并完成 Binance server-time 校验，后续行情复用同一 catalog。
- 官方 Binance 公告可用 `--official-news` 纳入严格前24小时来源覆盖；列表缺发布时间时必须回源详情，响应 envelope、文章 code、新到旧排序和窗口穷尽性均受合同约束，限流或解析失败会留下 `FAILED` 来源状态而不是伪造空新闻。
- Smart Money fixture 导入不只校验可重签的 payload hash，还会重新验证固定语义：`30D`、`DESC`、恰好 `PNL+ROI`、每页10行×3页，以及两个 `onlyShow*` filter 均为 `false`；任一不符即拒绝。
- `topTraderId → squareUid` 身份映射 v2 必须来自同一匿名 Binance 响应，并绑定 raw bytes、request manifest、实际 SHA-256 和 `/data/topTraderId`、`/data/squareUid` JSON Pointer。采集器只能生成 `PROPOSED`；只有经独立、显式 review 生成的不可变 `APPROVED` artifact 才能进入活动投影，且支持事件化撤销。
- 显式映射证据或经哈希固定的多映射 catalog 可通过 `--smart-money-square-mapping-evidence` 接入同一 pipeline；报告把 Smart Money 映射/Profile 与独立 seed Profile 分开记分母，seed 覆盖不得冒充60人榜单覆盖。
- 严格最近 24 小时窗口：`[decision_at - 24h, decision_at)`。
- 旧 signal 文件只提供作者原始 Entry/SL/TP 等参数；时间与作者必须回源重验，标记为 `AUTHOR_LEGACY_EXTRACTED`。
- `DERIVATION_POLICY_V1`：作者参数有效时保留 `AUTHOR`；缺参数或入场已错过时，只有完整 Futures 四周期证据、结构、0.4 ATR 止损、RR 1.5/2.0 与禁追价门全部通过，才生成显著标记的 `SYSTEM_REDERIVED`；否则 `REJECTED`。
- 作者原始计划会从发布时间回放到决策时点；期间先触发 SL/TP 即拒绝，同根 K 线同时覆盖 SL/TP 时保守按止损优先。作者止损还必须通过发布前结构和最小 0.4 ATR 距离门。
- 布林带收缩但尚未放量突破时降为 WATCH；只有方向一致且量能确认的突破才允许继续参与 TOP 判定。
- 共识按 symbol/direction、稳定作者ID与内容哈希建立；候选自身、同作者多帖和复制内容簇不增加共识分。
- 未验证作者不冒充 Tier A，作者可信度为 0 分。
- 精确验证 `TRADING / PERPETUAL / USDT` 合约。
- 每次真实运行保存完整 Futures 合约目录证据，不只保存本轮涉及的币种。
- Futures 公共行情：现价、标记价、指数价、资金费率、持仓量、24h量、15m/1h/4h/1d 已收盘 K 线。
- Futures 暂时不可用时，只允许 Spot Proxy 补价格和 OHLC；不得用 Spot 量冒充合约量。
- 指标：BB20、%B、BandWidth、ATR14、Futures volume ratio、多周期趋势。
- 固定 100 分评分、硬门槛、TOP3/WATCH5、同币多空冲突降级。
- 手续费、滑点、资金费率和深度模型默认未配置；只有完整注入成本参数且成本调整后主要目标 RR `>=2` 才可标记执行就绪，不能把名义 RR 报成净 RR。
- 本地不可变 raw/market/report JSON、Markdown、单一 `latest` 目录指针原子替换、SQLite logical run/attempt/manifest。
- 生产 logical run 仍由固定 UTC 四小时 slot 唯一标识；首次 attempt 的 `decision_at` 取 attempt-start UTC，并必须由 Binance server time 在30秒偏差内验证、且位于 slot 后 0–10 分钟。验证失败则 `market_catalog/FAILED`，禁止用本机时钟降级成功。SQLite `production_run_cutoff` 每轮只写一次；唯一一次 +10 分钟 retry 必须精确复用，不能改写 cutoff。帖子资格与已闭合 K 线以它为 cutoff；标量行情是随后抓取的实时验证值，必须单独显示 `captured_at`。
- `job_namespace + production_job_id + scheduled_for_utc` 共同隔离 production/canary 身份，避免不同账本生成相同逻辑运行或 attempt 标识。
- logical run 与 `RUNNING` attempt 在任何输入文件、catalog 或帖子详情采集之前落库；FETCH/分析/报告失败均终结为带阶段的 `FAILED`，retry只能从一个已审计的 FAILED attempt1 分配 attempt2。
- 生产跨轮去重只读取更早且 `SUCCEEDED` 的同 job 时槽；FAILED/RUNNING 不污染基线。回放默认明确显示 `NOT_COMPUTED`。
- v4.1 增量数据合同与追踪持久化继续保留：signal family/revision、PENDING/触发/结果、MFE/MAE/R；当前轮失败后查询自动排除其状态。
- UTC 六时槽、一次 +10 分钟重试、静默恢复与二次失败分类告警已有纯 shadow runner；重试成功仍生成该轮唯一的常规 `HELD/NO_SEND` 报告 intent，但不生成恢复告警；不安装任务、不发送。
- 报告分别记录广场抓取开始/完成、行情最新和报告生成时间；K线请求冻结 `endTime=decision_time_ms-1`，跨周期边界仍保持点时一致。
- 报告固定对账 Feed、Profile、Smart Money、官方新闻、行情目录五类来源；每类都显示 `COMPLETE/PARTIAL/FAILED/NOT_ATTEMPTED`、provenance、采集时间和证据清单，不能用一个来源替代另一个来源的完成度。
- Profile报告必须同时携带Smart Money与seed cohort分母；planned、五类终态、逐作者outcome、稳定身份、顶层状态与source coverage必须对账且唯一。覆盖率分子仅为`COMPLETE+EMPTY`，任何`PARTIAL`都不算完成；全EMPTY表示已穷尽无帖，归一为`COMPLETE`。

## 尚未生产化

- 源项目观测到官方 Web UI 提供 `PNL/ROI`，实现要求两榜均完整 TOP30 才能达到 `2/2 COMPLETE`。`VOLUME/WIN_RATE` 仍只是历史/扩展合同，不得宣称为当前 Smart Money UI 能力；安装者必须用当次证据重新确认。
- Smart Money 排行身份是 `topTraderId`，Square 作者主键是 `squareUid`，两者不相等且不得推断映射。榜单详情覆盖不能替代显式身份映射；没有映射就不能抓取对应 Square 内容、增加作者分或授予 Tier A。
- ROI 榜可能包含“小额本金、高倍收益率”的账户；ROI排名和详情字段只作候选发现证据，不能绕过公开实盘时长、Square内容质量、至少20条已触发信号及60天前向绩效门直接晋级 Tier A。
- 9个 Profile 身份/实盘上下文种子已固化，但最新内容抽样均未通过“同帖完整 Entry + SL + TP”质量门；作者分仍为0，尚无合格 Tier A 信号源。
- 源项目历史 canary 曾验证默认容量、窗口排除和DQ分账路径；该动态回执不随 Skill 发布，旧快照也不能替代M1b人工准确率审计。
- 没有真实 60 天绩效历史；作者表现分不能宣称已验证。
- Square Profile 内容主通道已有默认匿名真实抓取器。没有活动映射时，Smart Money cohort 必须显示 `0/60 mapping` 并保持零请求；独立 seed cohort 仍可按自身已验证 `squareUid` 抓取，但必须单独显示分母。运行环境中的动态映射、seed 和帖子证据不随发布包分发，因此干净安装默认仍是未映射状态。
- 交易成本模型保持既有状态，本轮明确不接入手续费或滑点参数；不得把名义 RR 报告成净 RR。
- 作者60天/长期表现的数据结构和追踪合同存在，但尚未把真实60天 point-in-time 聚合接入生产评分。
- Telegram 只有渲染与 `HELD/NO_SEND` intent，没有发送；没有安装每4小时调度。
- 不具备、也不允许真实下单。

任何账号访问、外部发送、常驻调度或交易权限都必须由当前操作者单独、明确授权；授权不替代数据质量、量化发布和独立复核门。

## 真实只读运行

建议使用顺序生产影子入口；它保证消费的是本轮刚写入且通过一致性检查的不可变 Feed 快照：

```bash
python3 scripts/run_production_cycle.py \
  --leaderboard-seed-evidence <optional-reviewed-seed-evidence.json> \
  --smart-money-square-mapping-catalog <optional-approved-mapping-catalog.json> \
  --job-namespace production \
  --production-job-id binance-square-shadow-v4 \
  --limit 200 \
  --no-send
```

独立 Profile seed 和 Smart Money cohort 会分别显示分母；seed 不会冒充榜单映射。单份人工复核映射可改用 `--smart-money-square-mapping-evidence <mapping.json>`，但它与 catalog 参数互斥。没有证据时保持未映射，不按名称猜测。

分步诊断入口：

在 Skill 根目录执行：

```bash
python3 scripts/run_radar.py \
  --real \
  --smart-money \
  --input-snapshot data/binance_raw_posts.json \
  --signals-json data/signal_check_input.json \
  --leaderboard-seed-evidence <optional-reviewed-seed-evidence.json> \
  --smart-money-square-mapping-evidence <optional-reviewed-mapping.json> \
  --official-news \
  --limit 200 \
  --output-dir data/v4/runs \
  --database data/v4/radar.sqlite \
  --no-send
```

真实模式不传 `--clock` 时，以 attempt-start UTC 作为24小时决策时间，并立即用币安 Futures server time 做30秒内校验；校验接口不可用时该 attempt 失败。logical run 固定到所属4小时 UTC 槽；首次决策时间超过 slot 10 分钟会拒绝运行，防止迟到执行污染错误轮次。`--limit` 范围为 1–200，默认200；高质量参数信号先并入，再用 canonical `post_id` 去重。

`--smart-money` 会在同一只读影子运行中实时采集公共 `PNL/ROI` TOP30及公开交易员详情。若已有不可变证据，使用 `--smart-money-fixture <evidence.json>` 做无网络回放；fixture 模式若请求 Smart Money 却未提供 fixture，会明确失败。

### 验收边界

- 本次仓库同步快照通过当前全量离线合同测试；确切项数以当次 `unittest discover` 输出为准。测试只证明代码路径、数据约束和失败关闭行为可复现。
- 真实运行产生的帖子、交易员详情、行情、SQLite、报告和账号授权回执均不随 Skill 发布，避免将动态数据或操作者环境状态固化进仓库。
- `COMPLETE` 只表示榜单合同覆盖，不表示原子快照、作者可靠、策略有效或未来盈利。
- 每次真实使用仍须在合法四小时UTC时槽的前10分钟内运行 `--real --smart-money --no-send`，并以当次 JSON、Markdown、manifest、SQLite完整性检查和独立复核作为唯一运行回执。

输出：

- `data/v4/runs/<logical_run>/attempt-<n>/raw.json`
- `data/v4/runs/<logical_run>/attempt-<n>/market.json`
- `data/v4/runs/<logical_run>/attempt-<n>/report.json`
- `data/v4/runs/<logical_run>/attempt-<n>/report.md`
- `data/v4/runs/latest`：一次原子切换的目录符号指针
- `data/v4/runs/latest.json`、`latest.md`：指向上述目录的兼容链接
- `data/v4/radar.sqlite`

失败不得改变最后成功的 `latest` 目录指针；JSON 与 Markdown 必须作为同一组切换。每个 attempt 必须终结为 `SUCCEEDED` 或 `FAILED`。

若 attempt 已成功提交、但原子切换 `latest` 时发生本地文件系统故障，使用下列恢复入口。它不会重抓、不会创建新 attempt；只有 raw、market、report JSON 与 Markdown 的 manifest SHA-256 全部匹配时才修复指针：

```bash
python3 scripts/repair_latest.py \
  --logical-run-id <logical_run_id> \
  --output-dir data/v4/runs \
  --database data/v4/radar.sqlite
```

## 离线验收

```bash
python3 scripts/run_radar.py \
  --fixture tests/fixtures/m1b \
  --clock 2026-08-01T13:10:00Z \
  --smart-money-fixture <smart-money-evidence.json> \
  --limit 5 \
  --output-dir /tmp/binance-radar-fixture/runs \
  --database /tmp/binance-radar-fixture/radar.sqlite

PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v
```

Fixture 只证明合同、完整性校验和失败路径可复现，不证明当下交易机会或策略有效。发布回执必须记录当次实际测试项数，不能沿用历史数字。

## 评分合同

| 维度 | 分值 |
|---|---:|
| 作者可信度 | 25 |
| 帖子参数完整性 | 15 |
| 新鲜度 | 10 |
| 多周期趋势一致性 | 20 |
| 市场确认 | 10 |
| 风险收益比 | 15 |
| 新闻/独立作者共识 | 5 |

- `>=55`：TOP 候选；仍须通过硬门与执行就绪检查，否则降级 WATCH/FILTER
- `40–54`：WATCH
- `<40`：FILTER

硬门槛：

- 无活跃合约。
- 信号过期或已失效。
- 价格几何关系无效。
- 主要目标 RR `<1.5`。
- 信号已触发止损、达到主要目标或其他失效条件。

缺 Entry、SL 或 TP1 只允许进入部分完整度评分，并因执行就绪不可用而保持 WATCH/FILTER；不得为了输出机会静默补齐参数。仅允许按 `DERIVATION_POLICY_V1` 生成明确标记、带完整证据的系统再推导计划；任何硬门失败即拒绝。没有合格机会时必须输出 `WAIT`。

## 报告硬约束

- 第一屏显示真实 `scanned_at.utc`、`scanned_at.america_los_angeles` 和 `report_generated_at`。
- 第一屏同时显示广场抓取开始/完成、行情最新与报告生成时间；`latest_fetch_at` 必须不晚于报告生成。
- 显示 discovered/within-window/accepted/quarantine；生产运行必须计算真实 new/duplicate，回放无显式基线时必须显示“未计算”。
- `WINDOW_EXCLUDED` 与 `DQ_QUARANTINE` 必须分开：已取得稳定身份和精确时间但落在24小时外属于正常窗口排除，不得冒充数据质量失败；两者之和仍须与总隔离数对账。
- 显示 Tier A/B 身份来源和排行榜真实覆盖率。
- Profile种子与完整榜单必须分开显示；证据时间必须保留原始采集时点，不能改写成本轮时间。
- TOP 必须包含原帖 URL 与行情 `captured_at`。
- TOP/WATCH 必须显式显示 `AUTHOR` 或 `SYSTEM_REDERIVED` 参数来源。
- 每次真实运行保存所用合约目录、标量行情和 4 周期已收盘 K 线到 `market.json`，并纳入 manifest。
- Spot Proxy、榜单阻塞、集中风险必须出现在首屏风险提示。
- 报告最多 TOP3、WATCH5，不得补位或复用旧信号。
- 零机会写“无合格机会 / 等待”。

## 信号追踪合同

- Entry 区触碰才算触发；发布后 24h 未触发记 `UNTRIGGERED`，不是亏损。
- 默认观察 72h，可按作者明确持仓周期覆盖。
- 同一根 K 线同时覆盖 SL/TP 时保守按 SL。
- TP1 命中后继续观察 TP2。
- 未完整配置手续费、滑点和退出比例时，只能报告 `NOMINAL_R`，不得写 `NET_R`。
- 作者统计使用 60 天与 lifetime 的 70/30 聚合；少于 20 条已触发样本时作者分封顶 20/25。

## 留存

```bash
python3 scripts/cleanup_retention.py --help
```

清理默认 `DRY_RUN`。实际删除必须显式 `--apply`，并提供与数据根完全相同的 `--confirm-delete-root`；聚合对账失败时拒绝清理。

## 文件结构

```text
binance-square/
├── SKILL.md
├── GRILL_DECISIONS.md
├── V4_IMPLEMENTATION_PLAN.md
├── PROVENANCE.md
├── scanner/
│   ├── contracts.py / storage.py
│   ├── square.py / authors.py
│   ├── market.py / indicators.py
│   ├── opportunities.py / scoring.py
│   ├── derivation.py / tracking.py / retention.py
│   ├── discovery.py / runner.py / smart_money.py
│   ├── profile_pipeline.py / binance_news.py
│   ├── reports.py / pipeline.py
├── scripts/
│   ├── binance_scraper.py
│   ├── collect_square_v4.py
│   ├── collect_identity_mapping.py / review_identity_mapping.py
│   ├── build_identity_mapping_catalog.py
│   ├── discover_authors.py
│   ├── run_radar.py
│   ├── run_production_cycle.py
│   ├── render_latest_telegram.py
│   ├── run_shadow_cycle.py
│   ├── repair_latest.py
│   └── cleanup_retention.py
├── migrations/001_v4.sql ... 006_identity_mapping_v2.sql
├── tests/
└── data/                       # 运行时生成；发布包仅带空signal输入
```

## 安全边界

- 仅访问币安公开页面或公开市场 GET API。
- 身份证据端点使用独立匿名 HTTP client；不继承浏览器会话，采集只生成 `PROPOSED`，审批必须离线、显式且生成新 artifact。
- 不读取 Cookie、Token、Local Storage、密码、验证码或交易密钥。
- 不发送消息、不安装调度、不发布、不下单，除非用户在后续明确批准对应生产阶段。
- 每次执行都报告真实限制、失败类型和证据路径。

---

*Binance Square Scanner v4 Shadow*
