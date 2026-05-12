# Binance Square 热度猎杀

> 作者：Your Name
> 版权所有 © 2026 Your Name
> 版本：**v12.0**（CDP Live Session + Multi-Topic + Concurrent）

---

## 概述

从 Binance Square 热门话题排行榜获取话题列表，逐个进入话题页抓取最新帖子，提取社区交易信号、情绪方向和小币提及统计。

**使用场景**：在 Polymarket 交易决策前，扫描 Binance Square 社区情绪，辅助判断短期市场方向。

---

## 核心依赖

| 组件 | 说明 |
|------|------|
| Chrome 浏览器 | 已登录的默认配置文件 |
| Playwright | `pip install playwright && playwright install chromium` |
| CDP 端口 | 9222（原生）或 18800（OpenClaw） |

---

## 工作流程（SOP）

```
Step 1 → 打开 trends 页面 → 解析话题列表（名称 + slug）
Step 2 → 爬取广场页（实时帖子流）
Step 3 → 逐个进入话题页 → 点击"最新内容"Tab → 滚动加载 → 提取帖子
Step 4 → 合并去重 → 分析 → 汇报
```

**关键**：每个话题页有两个 Tab — **热门**（热度排序）和 **最新内容**（实时排序）。脚本默认切换到"最新内容"以获取最新帖子。

### Step 1 — 检查 / 启动 Chrome CDP

```bash
# 检查是否已运行
curl -s --max-time 3 http://localhost:9222/json

# 若无，使用启动脚本（自动检测 + 启动 + 运行 + 清理）
./run_with_chrome.sh --min 60 --topics 10 --per-topic 20
```

**`run_with_chrome.sh` 功能**：
1. 检测 Chrome CDP 是否已在 9222 端口运行
2. 若无，自动启动 Chrome（User Profile + Remote Debugging）
3. 运行 scraper
4. 脚本结束自动关闭 Chrome（加 `--keep-alive` 保留进程）

---

### Step 2 — 运行脚本

```bash
cd ~/clawd/skills/binance-square/scripts
python3 square_scraper_cdp.py --min 60 --topics 10 --per-topic 20 --scrolls 2 --concurrency 5
```

**参数说明**：

| 参数 | 默认 | 说明 |
|------|------|------|
| `--min N` | 60 | 只采集 N 分钟内的帖子 |
| `--topics N` | 10 | 最多爬 N 个话题（0=只爬广场不爬话题） |
| `--per-topic N` | 10 | 每个话题最多爬 N 帖 |
| `--scrolls N` | 2 | 每话题滚动加载次数（内容多则加大） |
| `--concurrency N` | 5 | 并发话题爬取数 |
| `--top N` | 10 | 输出 Top N 小币统计 |
| `--coin-type` | all | all / mainstream / small / meme |

---

### Step 3 — 分析数据

**输出指标**：

| 指标 | 说明 |
|------|------|
| 总帖子数 | 所有话题 + 广场的帖子合计 |
| ≤60min 帖 | 近 1 小时内的帖子（核心信号窗口） |
| 金融帖数 | 含交易关键词（做多/做空/开仓/止损等） |
| 小币种类 | 非主流币提及次数排名前 N |
| Topic 热度 | 各话题金融帖数量排行 |
| Edge 候选 | 同时含金融关键词 + 小币 + 明确方向 |

**信号判定**：
```
信号强度 = 金融帖数 / 总帖数 × 币种分散度
Edge 候选 = 金融帖中提及小币 + 方向明确（看涨/看跌）
```

---

### Step 4 — 汇报格式

```
📊 币安 Square v12.0 CDP | {时间} | ≤{N}min | {coin_type}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
总帖子: {N}  |  满足: {M}  |  仅计入: {K}
金融帖: {F} 满足 + {O} 补充  |  小币: {C}种  |  话题: {T}个

🔥 Topic 讨论区热度
  1.  #话题名            {N}帖  {M}帖

🪙 小币机会 (Top N)
  1.  $KAT      12次 ⚡  摘要...

📌 满足条件帖子 (≤60min) 共{M}帖
  [5min前] 📈 $BTC $ETH  趋势反转信号...
```

---

## 脚本说明

### v12.0 CDP Multi-Topic（生产用）

```bash
python3 square_scraper_cdp.py --min 60 --topics 10 --per-topic 20 --scrolls 2 --concurrency 5
```

**流程**：
1. 连接 Chrome CDP 会话
2. 打开 trends 页面 → 解析所有话题的 slug
3. 依次进入每个话题页 → 滚动 2 轮 → 提取 innerText
4. 纯 Python 正则解析时间戳/币种/互动数
5. 合并去重 → 汇总报告

### v8.0 headless（备用）

```bash
xvfb-run --auto-servernum python3 square_scraper.py --topics 0
```

- 无需 Chrome 打开，纯 headless 模式
- **限制**：内容受限，Topic 页会触发 rate limit

---

## 已知限制

| 问题 | 原因 | 解决方案 |
|------|------|----------|
| CDP 连接失败 | 浏览器未启动 | `./run_with_chrome.sh` 会自动启动 |
| 话题无 slug | trends 页面 HTML 解析失败 | 检查 Chrome 是否已打开 trends 页 |
| Topic 页限流 | 连续高频请求 | 减少 `--topics` 或加长间隔 |
| 内容为空 | 未登录 / session 过期 | 重新在 Chrome 登录 Binance |

---

## 文件结构

```
skills/binance-square/
├── SKILL.md                      ← 本文件
└── scripts/
    ├── run_with_chrome.sh         ← 启动器（自动检测/启动 Chrome + 运行 scraper）
    ├── square_scraper_cdp.py     ← v12.0 CDP Multi-Topic（生产用）
    └── square_scraper.py         ← v8.0 headless（备用）
```

---

## 许可与版权

本工具仅供个人学习研究使用。

版权所有 © 2026 Your Name。保留所有权利。
