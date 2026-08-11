# 5minbtc × Claude Code 监控集成

> 把 5minbtc 从「cron 单次预测」升级为「Claude Code 会话内实时监控」。
> 核心: `scripts/5minbtc-monitor.py` 流式输出事件, 配合 Claude Code 的
> **Monitor 工具**把每行事件转为实时通知, 直到命中明确信号或用户喊停。

## 一、为什么需要这个

原版 5minbtc 是 cron 驱动的: 每根 K 线第 4 分钟跑一次引擎 → LLM 裁决 → 写日志。
在 Claude Code 会话里, 用户想要的是**盯着盘, 直到出现可交易信号**:

| 需求 | cron 原版 | Claude Code 监控版 |
|------|-----------|-------------------|
| 持续盯盘 | 每 5min 硬跑, 无信号门 | 事件流, 方向翻转即通知 |
| 明确信号 | LLM 事后看 | 脚本内置判定, 命中即停 |
| 用户控制 | 手动 cron | 用户一句话 start/stop |
| 采样时机 | 固定第 4 分钟 | 第 2/3 分钟 (更早捕捉) |

## 二、脚本设计 (scripts/5minbtc-monitor.py)

**契约**: 一行一条事件到 stdout; 由 Monitor 工具逐行转发。

| 事件 | 含义 | 处理 |
|------|------|------|
| `START` | 首次采样基线 bias | 记录 |
| `DIR-CHANGE` | bias 在 bull/neutral/bear 间翻转 | 即时汇总 |
| `CLEAR-SIGNAL` | 达到明确信号门槛 | **退出** (exit 0) |
| `ENGINE-ERR` | 引擎调用失败 | 打印后继续, 不崩溃 |
| `MAX-RUNS` / `TIMEOUT` | 达到采样/时长上限 | 退出 (exit 2) |

### 明确信号判定 (默认)
```
bias != neutral  AND  strength ∈ {medium, moderate, strong}  AND  confidence ≥ 50
```
> ⚠️ 实测引擎输出的 strength 是 `weak` / `medium` (SKILL.md 文档写 `moderate`) —
> 判定集合必须同时包含 `medium` 和 `moderate`, 否则 CLEAR-SIGNAL 永不触发。

### 采样时机
每根 5min K 线的**第 2、3 分钟** (progress ~40-70%): half_body 已激活, 又留有足够剩余时间。

### 关键参数
```
--max-runs N    采样次数上限 (默认 20; 0 = 无限, 由用户/会话结束)
--min-conf N    明确信号置信度门槛 (默认 50)
--hours H       时长上限 (默认无)
--settle        每次采样前先 settle 上一根 (配合 --max-runs 2 的短监控用)
--dry-run       单次采样打印当前状态后退出 (验证用)
```

## 三、Claude Code 用法

### 启动 (后台持续监控)
```bash
# 无限持续, 直到用户喊停 (推荐用于会话内盯盘)
Monitor(command: "python3 <SKILL>/scripts/5minbtc-monitor.py --max-runs 0",
        persistent: true)

# 有限次数 (默认 20 次, 约 100 分钟)
Monitor(command: "python3 <SKILL>/scripts/5minbtc-monitor.py")

# 更保守: 需 55 置信度才叫明确信号
Monitor(command: "python3 <SKILL>/scripts/5minbtc-monitor.py --min-conf 55")
```

### 事件响应协议 (Claude 侧)
1. `DIR-CHANGE` → 简短汇总: 新 bias、conf、现价、关键因子变化, **说明方向翻转含义**。
2. `CLEAR-SIGNAL` → 立即拉完整引擎快照确认, 输出: bias/strength/conf、现价、关键多空因子、pred 区间、**反向风险** (如 meanrev 托底)。
3. `ENGINE-ERR` 连续 ≥3 次 → 停监控, 诊断网络/端点 (见 binance-endpoint-flapping.md)。
4. 用户「stop / 结束」→ `TaskStop` 停 Monitor。

### 停止
```bash
TaskStop(task_id: <monitor-id>)
# 或用户直接说「停」/「结束」即触发
```

### 一次「单次判断」 (非持续)
```bash
python3 <SKILL>/5minbtc-engine-v5.7.py     # 拉一次预测
python3 <SKILL>/scripts/5minbtc-monitor.py --dry-run   # 等价, 带事件格式
```

## 四、铁律 (从原 SKILL.md 继承)

1. **不缓存**: 每次采样都重新执行引擎脚本。
2. 每次采样后若 bias 或 conf 有实质变化, 视为新信息, 向用户重新汇总。
3. `CLEAR-SIGNAL` 后必须拉一次完整快照二次确认 (监控事件只是触发, 快照才是证据)。
4. **非投资建议**: 明确信号只是引擎统计输出, 不代表可下注; 输出必须带置信度和反向风险。
5. 兜底: 无限模式 (`--max-runs 0`) 依赖用户喊停或会话结束, 脚本本身不设时限。

## 五、与 cron 原版的取舍

- **用监控版**: 会话内盯盘、等信号、需要方向翻转即时感知。
- **用 cron 原版**: 无人值守、每 5min 固定记录预测 + 新闻 + settle 的完整流水线。
- 两者共享同一引擎, 不冲突; 可同时跑 (cron 写日志, 会话内监控看信号)。

## 六、已知边界

- 引擎 ~3s/次 (4 路并行 HTTP), 采样错峰不会重叠。
- 每根 K 线采 2 次 → 20 次 ≈ 7-8 根 K 线 ≈ ~40 分钟 (`--max-runs` 按采样次数计, 不是 K 线数)。
- 若引擎端点故障 (Binance 双向切换后仍失败), 监控进入 ENGINE-ERR 循环, 需人工诊断。
