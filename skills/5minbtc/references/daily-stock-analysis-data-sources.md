# daily_stock_analysis 数据源参考

> 参考仓库: `ZhuLinsen/daily_stock_analysis` (A股/港股/美股多市场分析)
> 本地参考: `~/clawd/repos/daily_stock_analysis/_src/data_provider/`
> 最后同步: 2026-06-21

## 评估结论

| 维度 | 结论 |
|------|------|
| **对5minbtc新闻源价值** | ⭐⭐⭐ 中等 — `finnhub_fetcher.py` + `tushare_fetcher.py` 含加密货币/A股新闻分类逻辑可借鉴，但项目本身是股票分析不是加密货币 |
| **直接可用数据源** | `finnhub_fetcher.py`（美股新闻+部分crypto news endpoint） |
| **架构借鉴价值** | ⭐⭐⭐⭐ 高 — `base.py`（147KB）的多源fallback框架非常成熟 |
| **可直接抄的代码** | 多源fallback重试/超时/缓存模式 |

---

## data_provider/ 17个 fetcher 清单

| 文件 | 大小 | 用途 | 对5minbtc价值 |
|------|------|------|--------------|
| `base.py` | 147KB | **统一接口 + fallback框架** | ⭐⭐⭐⭐ 架构模式 |
| `akshare_fetcher.py` | 94KB | **A股综合（新闻/公告/资金流）** | ⭐⭐⭐ 中文新闻分类思路 |
| `tushare_fetcher.py` | 51KB | **A股专业（新闻/公告/财务）** | ⭐⭐⭐ 新闻事件分类 |
| `efinance_fetcher.py` | 52KB | 东财（A股） | ⭐⭐ A股数据 |
| `longbridge_fetcher.py` | 36KB | **港股/美股** | ⭐⭐⭐ 长桥新闻API |
| `yfinance_fetcher.py` | 35KB | yfinance（美股/全球） | ⭐⭐ 美股新闻 |
| `fundamental_adapter.py` | 21KB | 基本面数据适配器 | ⭐ 参考设计 |
| `realtime_types.py` | 17KB | 实时数据schema | ⭐ 类型定义参考 |
| `baostock_fetcher.py` | 14KB | baostock（A股历史） | ⭐ A股历史 |
| `pytdx_fetcher.py` | 18KB | 通达信（A股） | ⭐ A股实时 |
| `tencent_fetcher.py` | 7KB | 腾讯财经 | ⭐ A股实时 |
| `yfinance_fundamental_adapter.py` | 16KB | yfinance基本面 | ⭐ |
| `alphavantage_fetcher.py` | 7KB | Alpha Vantage | ⭐ |
| `tickflow_fetcher.py` | 12KB | tick级数据流 | ⭐⭐ 微结构思路 |
| `finnhub_fetcher.py` | 5KB | **Finnhub（美股新闻+数据）** | ⭐⭐⭐⭐ **含crypto news endpoint** |
| `us_index_mapping.py` | 3KB | 美股指数映射 | — |
| `__init__.py` | 0KB | 包初始化 | — |

## 重点 fetcher 字段说明（待深入研究时用）

### finnhub_fetcher.py ⭐⭐⭐⭐
- **crypto news endpoint**: `/news?category=crypto`
- 返回字段: `id, category, datetime, headline, image, related, source, summary, url`
- 包含 `category=crypto` 过滤 — 可直接用于BTC新闻源增强
- 当前5minbtc新闻源主要是CoinDesk/Cointelegraph/TreeNews RSS，Finnhub可作为**机构级第四源**

### tushare_fetcher.py ⭐⭐⭐
- 新闻分类逻辑: `新闻类别`字段（财经/政策/公司/国际等）
- 紧急度标记: 部分新闻带`urgent`字段
- **借鉴价值**: 当前5minbtc news_risk判断粗糙（仅NORMAL/BLACK_SWAN/CRITICAL），可学习更细粒度分类

### akshare_fetcher.py ⭐⭐⭐
- 公告/资讯抓取模式（A股）— 对加密货币无直接价值
- 但其**多源fallback重试逻辑**值得借鉴

### base.py ⭐⭐⭐⭐
- **统一 DataFetcher 基类** — 抽象所有数据源接口
- 内置 fallback 链、超时、重试、缓存
- 字段标准化层（不同数据源→统一schema）
- 是整个项目的架构核心

---

## GitHub 仓库下载流程（受限网络环境）

**核心问题**: 在中国大陆网络环境下，`git clone`/`gh repo clone`/codeload zip 均可能因TLS握手超时失败。

**解决路径（按推荐顺序）**:

### 方案A: `wget` GitHub Tarball API ⭐⭐⭐⭐⭐ 最稳

```bash
# 单文件下载（适合所有平台，无需认证）
wget --tries=30 --timeout=120 --read-timeout=120 -c \
  -O /tmp/repo.tgz \
  "https://api.github.com/repos/{owner}/{repo}/tarball"

# 解压
tar -xzf /tmp/repo.tgz
mv {owner}-{repo}-*/ _src/
```

**关键优势**:
- 不需要 git 协议（避免 smart-http 拦截）
- API 域名 `api.github.com` 通常比 `codeload.github.com` 稳定
- 支持断点续传（`-c`）
- 失败自动重试（`--tries=30`）

### 方案B: `curl` zip 直连

```bash
curl -fL --retry 3 --connect-timeout 15 --max-time 240 \
  -o repo.zip \
  "https://codeload.github.com/{owner}/{repo}/zip/refs/heads/main"
```

**注意**: codeload 在受限网络下经常 TLS 截断，且不会重传已经收到的字节

### 方案C: gh CLI（如果有 auth）

```bash
gh repo clone {owner}/{repo} -- --depth=1
```

**注意**: 走 git protocol，受限网络下可能同样失败

### 方案D: gitee 镜像

```bash
git clone --depth=1 https://gitee.com/mirrors/{repo}
```

**注意**: 很多 GitHub 项目没有 gitee 镜像，且 `gitee.com/mirrors/{name}` 路径可能要求 auth

---

## 失败模式诊断

| 错误 | 根因 | 解决 |
|------|------|------|
| `GnuTLS recv error (-110)` | TLS连接被中间设备重置（GFW） | 换 `wget` tarball方案 |
| `Could not resolve host: ghproxy.com` | DNS污染/镜像失效 | 换 `api.github.com` 直连 |
| `Could not read Username for gitee.com` | 仓库不是公开镜像 | 换 GitHub 直接下载 |
| `Operation timed out after XXXms` | TCP慢/被掐 | 加大 `--timeout=120 --read-timeout=120` |
| `unexpected end of file` (tar) | tarball下载到一半被掐 | 加 `-c` 断点续传，或降低并发 |

---

## 实际案例 (2026-06-21)

`ZhuLinsen/daily_stock_analysis` clone 过程：
- ❌ `git clone --depth=1` × 3 次超时（90s+）
- ❌ `gh repo clone` × 2 次失败（gitee镜像不存在）
- ❌ `codeload.github.com/zip` 被截断（仅196KB）
- ❌ `curl` 同上截断到 0 字节
- ✅ `wget .../tarball` 成功下载 13.1MB（32KB/s × 6.5min），但 `src/` 因 EOF 截断
- ✅ 解压得到 414/337+ 文件，**`data_provider/` 完整**（17个 fetcher）

**关键观察**: wget 报"已保存"但实际是 EOF 截断。判断标准：用 `tar -tzf` 能完整列出所有文件才算成功。

---

## 后续可执行动作（未完成）

1. [ ] 重 wget 续传 tarball 拿 `src/` 业务层（**非阻塞**——本任务目标只看数据源）
2. [ ] 深入读 `finnhub_fetcher.py` — 看 crypto news endpoint 真实字段
3. [ ] 深入读 `base.py` — 评估多源fallback架构是否能借鉴到 5minbtc news_risk
4. [ ] 评估是否把 Finnhub 加入 5minbtc 新闻源（需要Finnhub API key）