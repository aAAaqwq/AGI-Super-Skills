---
name: jiuyangongshe-stock-industry-logic
description: "爬取韭研公社个股产业逻辑与异动解析。输入个股名（如白银有色），自动获取该股异动解析、题材标签、相关文章与产业逻辑内容。"
metadata:
  hermes:
    category: web-scraping
    tags: [jiuyangongshe, 韭研公社, 异动解析, 产业逻辑, 股票研究, scraping]
---

# 韭研公社个股产业逻辑爬取

按个股名爬取韭研公社（jiuyangongshe.com，原韭菜公社）上该股的**产业逻辑 / 异动解析**内容。输入"白银有色"这类个股名，输出该股的题材标签、异动解析全文、相关文章列表。

## 触发条件
- 用户要求"爬取/查询某只股票的产业逻辑、异动解析、题材逻辑"
- 用户给出一只 A 股个股名（或代码），需要韭研公社上的题材/产业链/异动内容
- 用户提到"jiuyanggongshe"（拼写错误，正确为 jiuyangongshe）

## 核心方法（无需登录，SSR 直取）

站内搜索页 `https://www.jiuyangongshe.com/search/<任意>?k=<URL编码个股名>&type=<tab>` 的 SSR HTML 内嵌 `window.__NUXT__` JSON，**无需登录**即可拿到结构化数据。tab 类型：

| type | 含义 | list 内容 |
|---|---|---|
| `1` | 全部 | 含该股标签的全部文章（paginate.totalCount 为总数） |
| `2` | 标题标签 | 标题含该股的文章 |
| `5` | **异动**（核心） | 该股异动解析文章（官方"韭菜团子"发布，标题如"08月24日白银有色股票异动解析"），content 含完整产业逻辑 |
| `8` | 纪要 | 卖方纪要转载 |
| `product` | 红宝书 | 付费产品文章（content 截断） |
| `announcement` | 公告 | 公告相关 |
| `stock` | 股票 | 股票实体信息（stock_id/code/node 板块） |
| `user` | 用户 | 用户搜索结果 |

## 步骤

1. **解析 `window.__NUXT__`**（核心脚本：`scripts/fetch_stock_logic.py`，支持任意个股名，自动做 股票实体 + 异动解析 + 相关文章 三重抓取）：
```bash
python3 scripts/fetch_stock_logic.py "白银有色"
# 批量/谨慎场景: --delay 5（请求间隔秒，默认4）; --max-actions N; --article-dir dir/
```
脚本输出（JSON）：
- `stock`: stock_id / code / node（板块，如 hs_a=沪市A股）
- `actions`: 异动解析列表（title / content / article_id / create_time / integral），默认取最新 15 条（SSR 第一页）
- `articles`: 相关文章列表（全部 tab 第一页 15 条：title / author / create_time / stock_list）
- `pagination`: 各 tab 的 totalCount（异动解析总条数、相关文章总数）

2. **补抓文章详情**（如需全文/评论区）：
```bash
curl -sL -A "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0 Safari/537.36" \
  "https://www.jiuyangongshe.com/a/<article_id>" -o article.html
```
详情页同样内嵌 `window.__NUXT__`，可提取完整 content / stock_list / like_count / comment_count / integral。

3. **异动解析 content 结构**（已知模式）：开头为题材标签行（如"黄金+白银+特种电缆（核聚变）"），随后 1、2、3… 编号要点（产能/业务/催化/产业链卡位）。汇总多期异动解析可还原该股的核心产业逻辑全集。

## 陷阱（实测 2026-08-26）
- **域名拼写**：用户常写 `jiuyanggongshe.com`（多一个 g），正确是 `jiuyangongshe.com`。错误的域名 DNS NXDOMAIN。
- **分页在 SSR 不生效**：`page`/`pageNo`/`pageIndex`/`offset` 参数全部无效，SSR 永远只渲染第一页 15 条。完整分页数据需登录走 API（未登录 302）。**方案：第一页 15 条足够提炼产业逻辑；如要全量，提示需登录。**
- **搜索路径第 1 段任意**：`/search/x?k=名称` 与 `/search/名称?k=名称` 均可，真正生效的是 `k` 参数（个股名 URL 编码）+ `type` 参数。
- **API 全部需登录**：`/api/v1/*`（共 113 端点）未登录统一 302 回首页，无法直接调。SSR 内嵌 NUXT 是唯一公开数据通道。
- **SSR 响应慢且间歇 500**：首页/文章页实测 30-170s、10 次请求 3 次失败。**必须 curl 加 `--max-time 60`，失败重试 2-3 次，间隔 2-5s**。搜索页相对快（1-3s）。
- **NUXT 提取**：`window.__NUXT__=(function(a,b,...){return {...}});</script>` 形式，用 Node `eval` 提取最稳（脚本已内置）。
- **股票可能搜不到**：`list` 为空 / `checkStock=-1` / `stock_id` 字段与 k 不同 → 个股名不在站内（新股/未收录/北交所部分）。如实返回"未收录"，不编造。
- **红宝书（product）content 截断**：付费内容只有摘要，`user_read_limit=1` 表示需订阅，勿伪造全文。
- **异动解析文章可含多只股票标签**：一篇"X股异动解析"可打多只股票标签（如搜"英维克"命中的第一条标题可能是"08月25日金富科技股票异动解析"，因该文同时标签英维克）。**判断依据是 content 内容而非标题**——过滤/汇总时以 content 是否真讲该股为准，标题仅作参考。
- **`--article-dir` 详情页抓取较慢**（每篇 30-170s），默认只抓前 3 篇，失败已容错不中断主流程。
- **反爬防护（已内置）**：多 UA 轮换（7 个常见浏览器 UA）+ 全局限速（默认 4s/请求，`--delay` 可调）。单股调用 3 请求天然安全；批量 >50 股务必 `--delay 5` 以上。注意：站点 API 有动态加密（DYNAMIC_CRYPTO_ENABLED=true）但只作用于登录态，SSR 公开页面目前无验证码/滑块。

## 验证
- `stock` 返回 `code`（如 sh601212）与个股名对应；
- `actions[0].title` 匹配 `<日期><个股名>股票异动解析` 格式；
- `pagination.totalCount` > 0 表示站内有该股数据。

## 支持文件
- `scripts/fetch_stock_logic.py` — 主脚本：个股名 → 股票实体 + 异动解析 + 相关文章（JSON 输出，含 NUXT 提取与重试）
- `scripts/extract_nuxt.js` — Node 提取器：HTML → NUXT JSON（fetch_stock_logic.py 自动调用）
