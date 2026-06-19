# A股量化投资分析 Skill

> **定位**: Agent可直接加载的A股投资分析技能
> **触发词**: 分析A股 | 精选个股 | 今日主线 | 复盘 | 盘前情报 | A股日报
> **数据引擎**: AKShare + 多源新闻API + Python
> **更新**: 2026-06-19

---

## 概述

此Skill实现了三层分析体系：
1. **情报采集层** — 7路并发多源新闻采集，自动匹配板块和个股
2. **盘面阅读层** — 美股映射 + 大盘多空判断 + 实时主线(>9%题材分析)
3. **个股精选层** — 产业逻辑 + 形态8分类 + 盘口分析 + 题材排名 + 综合评分

## 触发条件

当用户消息包含以下关键词时自动加载：
- `分析A股` `A股分析` `今日A股`
- `精选个股` `选股`
- `今日主线` `主线分析` `热点题材`
- `盘前` `盘前情报` `早报`
- `复盘` `A股复盘` `今日复盘`
- `龙虎榜` `涨停` `连板`
- `a-share` `stock analysis`

## 项目路径

```
~/.openclaw/workspace/projects/a-share/
├── SKILL.md                     # 本文件
├── config.json                  # 全局配置
├── config/
│   ├── sector_keywords.json    # 板块关键词映射
│   ├── us_mapping.json         # 美股→A股映射
│   └── finance_keywords.json   # 财经过滤词
├── plugins/
│   ├── base.py                 # NewsSourcePlugin 基类
│   ├── orz_hot.py             # S1: orz.ai热点API
│   ├── cls_flash.py           # S2: 财联社电报
│   ├── eastmoney_news.py      # S3: 东财要闻
│   ├── web_search_source.py   # S4: web_search关键词
│   ├── rss_source.py          # S5: RSS订阅
│   ├── wallstreetcn.py        # S6: 华尔街见闻
│   └── jiucaigongshe.py       # S7: 韭菜公社
├── plugins/
│   └── news_collector.py       # 模块一: 7源并发情报采集(+去重+匹配)
├── engines/
│   ├── module2_market.py       # 模块二: 大盘+主线+美股映射
│   └── module3_stocks.py       # 模块三: 个股精选+评分
├── orchestrator.py              # 总编排(三模块串联)
├── reporter.py                  # Markdown日报生成器
├── daily_run.sh                 # 一键执行脚本
├── test_data_layer.py           # 数据层单元测试
├── test_news_plugins.py         # 新闻源单元测试
├── reports/                     # 输出报告(reports/YYYY-MM-DD.md)
└── reference-notes.md           # GitHub调研笔记(5仓库/564行)
```

## 环境检查与安装

使用此Skill前，先确认环境：

```bash
# 检查依赖
python3 -c "import akshare, pandas, numpy, aiohttp; print('OK')" 2>/dev/null || \
pip3 install akshare pandas numpy aiohttp feedparser openpyxl tabulate requests
```

如果 `pip3 install` 失败，先确保 pip 可用：`python3 -m ensurepip --upgrade`

## Agent 执行协议

### 快速分析模式（用户说"分析A股"/"今日主线"）

```
Step 1: 确认环境 → ./venv/bin/python3 -c "import akshare; print('OK')"
Step 2: 运行盘面 → ./venv/bin/python3 engines/module2_market.py
Step 3: 运行选股 → ./venv/bin/python3 engines/module3_stocks.py  
Step 4: 按报告模板格式化输出
```

### 完整日报模式（用户说"A股日报"/"完整分析"）

```
Step 1: 运行总编排 → ./venv/bin/python3 reporter.py
  （内部：情报采集 → 盘面分析 → 个股精选 → 生成Markdown + JSON）
Step 2: 读取报告 → cat reports/$(date +%Y-%m-%d).md
Step 3: 按完整报告模板格式化输出
```

### 盘前快报模式（用户说"盘前情报"）

```
Step 1: 并发拉取新闻 → ./venv/bin/python3 -c "
from plugins.cls_flash import fetch_cls_telegraph
from plugins.orz_hot import fetch_douyin_hot
print(f'财联社: {len(fetch_cls_telegraph())}条')
print(f'orz热点: {len(fetch_douyin_hot())}条')
"
Step 2: 美股映射检查 → ./venv/bin/python3 engines/module2_market.py
Step 3: 输出情报汇总表格
```

### 一键执行

```bash
cd ~/.openclaw/workspace/projects/a-share && bash daily_run.sh
# 或
cd ~/.openclaw/workspace/projects/a-share && ./venv/bin/python3 reporter.py

---

## 模块一：情报处理

### 数据源优先级

| 编号 | 数据源 | 方式 | 刷新 | 场景 |
|------|--------|------|------|------|
| S1 | orz热点API | HTTP GET `orz.ai/api/v1/dailynews?platform=douyin` | 30min | 盘前/盘中 |
| S2 | 财联社API | HTTP GET `cls.cn/v1/roll/get_roll_list` | 实时 | 全时段 |
| S3 | 东财要闻 | AKShare `stock_info_global_em()` | 分钟 | 盘前 |
| S4 | web_search | OpenClaw内置 | 按需 | 深度研究 |
| S5 | RSS订阅 | 中国新闻网财经feed | 小时 | 盘前 |
| S6 | 华尔街见闻 | web_fetch wallstreetcn.com | 分钟 | 盘前 |
| S7 | 韭菜公社 | web_fetch jiucaigongshe.com | 按需 | 个股深研 |

### 新闻→板块匹配逻辑

```
新闻标题/正文 → 提取关键词 → 查 sector_keywords.json 映射表 → 匹配板块名 → 
AKShare查板块成分股 → 输出 EventSignal
```

**板块关键词映射示例** (维护在 `config/sector_keywords.json`):
```json
{
  "人工智能": ["AI", "大模型", "ChatGPT", "人工智能", "AGI", "智能体", "AIGC", "DeepSeek", "GPT"],
  "半导体": ["芯片", "光刻", "EDA", "先进封装", "HBM", "存储", "晶圆", "台积电", "英伟达", "GPU"],
  "新能源车": ["电动车", "新能源汽车", "特斯拉", "比亚迪", "固态电池", "4680", "锂电"],
  "机器人": ["人形机器人", "机器人", "具身智能", "Optimus", "Figure", "宇树"],
  "低空经济": ["低空经济", "eVTOL", "无人机", "飞行汽车", "空中交通"],
  "光伏": ["光伏", "硅片", "组件", "钙钛矿", "TopCon", "HJT", "BC电池"],
  "量子计算": ["量子计算", "量子通信", "量子芯片", "量子比特"],
  "核电": ["核电", "核聚变", "SMR", "小型模块化", "第四代核电"],
  "创新药": ["创新药", "GLP-1", "减肥药", "ADC", "细胞治疗", "基因编辑"],
  "数据要素": ["数据要素", "数据资产", "数据确权", "数据交易", "数据局"],
  "消费电子": ["消费电子", "MR", "VisionPro", "AR眼镜", "折叠屏"],
  "商业航天": ["卫星", "商业航天", "SpaceX", "星链", "G60", "千帆"],
  "数字货币": ["数字货币", "区块链", "比特币", "加密货币", "Web3", "DeFi"],
  "军工": ["军工", "国防", "导弹", "战斗机", "航母", "军贸"],
  "地产": ["地产", "房地产", "楼市", "房贷", "限购", "城中村"]
}
```

---

## 模块二：实时盘面

### 美股映射

| 美股标的 | A股映射板块 |
|---------|-----------|
| SOX(费城半导体) | 半导体、芯片、光刻机 |
| ARKK(创新ETF) | AI、机器人、自动驾驶 |
| XBI(生物科技) | 创新药、CXO、医疗器械 |
| TAN(太阳能) | 光伏、储能 |
| LIT(锂电池) | 锂电池、新能源车 |
| URA(铀矿) | 核电 |
| NVDA涨跌 | AI算力、CPO、服务器 |
| TSLA涨跌 | 新能源车、汽车零部件、机器人 |

### 大盘指标计算

```python
# 涨跌家数比
ratio = up_count / down_count

# 风格判断
if ratio > 3:       style = "强势多头"
elif ratio > 1.5:   style = "偏多震荡"  
elif ratio > 0.67:  style = "震荡平衡"
elif ratio > 0.33:  style = "偏空震荡"
else:               style = "空头市场"
```

### 主线判断标准

- `>9%涨幅个股数 >= 15只` 且集中在1-2个题材 → 🔥 强主线
- `>9%涨幅个股数 8-14只` → ⭐ 中等主线
- `>9%涨幅个股数 < 8只` → 题材轮动/无主线
- 涨停数 >= 80 → 情绪高涨（适合接力）
- 涨停数 < 30 → 情绪冰点（适合首板/低吸）

---

## 模块三：异动个股分析

### 8形态检测规则

| 形态 | 检测条件 |
|------|---------|
| **突破平台** | 今日最高 > 30日最高价 AND 量 > 20日均量×1.5 |
| **趋势新高** | 收盘价 = 历史最高收盘价 |
| **新高附近** | (历史最高 - 现价) / 历史最高 < 5% |
| **N连板** | 连续N日涨停(N≥2) |
| **老龙二波** | 历史3连板+回调>15%+再次涨停 |
| **分歧转一致** | 开盘跌>3%最终涨停 |
| **反包板** | T日涨停→T+1上影→T+2涨停 |
| **放量首板** | 20日涨幅<15%+涨停+量>5日均量×3 |

### 盘口力度

- 外盘/内盘 > 1.5 → 💪 强
- 外盘/内盘 1.0-1.5 → 😐 中
- 外盘/内盘 < 1.0 → 👎 弱

### 产业逻辑评级

- ✅ 逻辑正: 主营占比>30%与概念直接相关
- ⚠️ 部分相关: 有相关业务但占比<30%
- ❌ 蹭概念: 无实质业务，仅有概念标签

### 综合评分(满分100)

| 维度 | 满分 | 规则 |
|------|------|------|
| 题材强度 | 30 | 命中前10板块数×8, 上限30 |
| 形态 | 25 | 趋势新高25/突破平台22/放量首板20/分歧转一致18/连板16/反包15/新高附近12/二波10 |
| 盘口 | 20 | 龙虎榜净买10分 + 内外盘比10分 |
| 逻辑 | 15 | 逻辑正15/部分相关8/蹭概念0 |
| 事件 | 10 | 有新闻事件匹配+10 |

---

## 报告输出模板

### 精简版（"分析A股"/"今日主线"）

```markdown
# 🐉 A股速览 | YYYY-MM-DD

## 📊 大盘
涨跌比 X:Y | 成交 XXXX亿 | 涨停X 跌停Y | 风格: XX

## 🔥 主线TOP3
1. **题材A** (X只>9%) — 驱动: X事件
2. **题材B** (X只>9%) — 驱动: Y事件

## 🎯 精选
### XXXX (code) ⭐92分
事件→逻辑→形态→盘口→题材命中
```

### 完整版（"A股日报"/"完整分析"）

```markdown
# 🐉 天枢A股精选 | YYYY-MM-DD (周X)

## 📡 情报汇总 (XX条有效)
| 时间 | 来源 | 事件 | 板块影响 | 强度 |
|------|------|------|---------|------|

## 🌐 美股映射
| 美股板块 | 涨跌 | A股映射 | 信号 |
|---------|------|---------|------|

## 📊 大盘环境
| 指标 | 数值 | 判断 |
|------|------|------|
| 涨跌比 | X:Y | XX |
| 成交额 | XXXX亿 | 放量/缩量 |
| 涨停/跌停 | X/Y | — |
| 市场风格 | XX | — |

## 🔥 今日主线(>9%题材分布)
| 排名 | 题材 | 涨停数 | 驱动事件 | 持续性 |
|------|------|--------|---------|--------|

## 🎯 精选个股
### 1. XXXX ⭐92分
| 维度 | 详情 |
|------|------|
| 事件 | X |
| 逻辑 | X |
| 形态 | X |
| 盘口 | 龙虎榜X万, 外内比X |
| 题材 | 命中X个前10板块 |

## ⚠️ 风险提示
```

---

## 一键执行脚本

```bash
#!/bin/bash
# daily_run.sh
cd ~/.openclaw/workspace/projects/a-share

echo "=== 🐉 天枢A股分析 $(date '+%Y-%m-%d') ==="

echo "[1/4] 情报采集..."
python3 -c "
from plugins.orz_hot import fetch_douyin_hot
from plugins.cls_flash import fetch_cls_telegraph
items = fetch_douyin_hot() + fetch_cls_telegraph()
print(f'采集到 {len(items)} 条情报')
"

echo "[2/4] 大盘+主线..."
python3 engines/module2_market.py

echo "[3/4] 个股精选..."
python3 engines/module3_stocks.py

echo "[4/4] 生成报告..."
python3 orchestrator.py

echo "✅ 完成！报告: reports/$(date +%Y-%m-%d).md"
```

---

## 数据源API速查（AKShare核心函数）

| 函数 | 说明 |
|------|------|
| `ak.stock_zh_a_spot_em()` | 全A实时行情 |
| `ak.stock_zt_pool_em(date)` | 涨停池 |
| `ak.stock_zt_pool_dtgc_em(date)` | 跌停池 |
| `ak.stock_board_industry_name_em()` | 行业板块排名 |
| `ak.stock_board_concept_name_em()` | 概念板块排名 |
| `ak.stock_board_concept_cons_em(symbol)` | 板块成分股 |
| `ak.stock_lhb_detail_em(date)` | 龙虎榜明细 |
| `ak.stock_zh_a_hist(symbol, period, start, end)` | 历史K线 |
| `ak.stock_individual_info_em(symbol)` | 个股F10信息 |
| `ak.stock_individual_fund_flow(stock, market)` | 个股资金流向 |
| `ak.stock_hsgt_north_net_flow_in_em()` | 北向资金 |
| `ak.index_global_spot_em()` | 全球指数 |

## 外部API速查

| API | URL | 说明 |
|-----|-----|------|
| orz热点 | `https://orz.ai/api/v1/dailynews?platform=douyin` | 抖音热榜 |
| orz热点 | `https://orz.ai/api/v1/dailynews?platform=jinritoutiao` | 头条热榜 |
| orz热点 | `https://orz.ai/api/v1/dailynews?platform=weibo` | 微博热搜 |
| 财联社 | `https://www.cls.cn/v1/roll/get_roll_list?app=CailianpressWeb&os=web&rn=50` | 实时电报 |

## 参考项目

| 项目 | 借鉴点 |
|------|--------|
| `AigcExpert/daily_stock_analysis` (685 commits) | LLM分析架构、报告格式、多数据源模式 |
| `tel9980/ai_news` | DeepSeek新闻→板块影响评分 |
| `orz-ai/hot_news` | 多平台热榜API |
| `frosenwind/capitalfarmer` | 东方财富API Python封装 |
| `pigfamily/Ashare` | 新浪+腾讯备用行情源 |

---

## 扩展指南

新增数据源步骤：
1. 继承 `NewsSourcePlugin` 基类
2. 实现 `fetch()` 方法，返回 `List[NewsItem]`
3. 在 `config.json` 的 `news_sources` 中添加
4. 无需修改其他代码

新增分析模块步骤：
1. 在 `engines/` 下创建新文件
2. 暴露 `analyze()` 函数
3. 在 `orchestrator.py` 中注册
