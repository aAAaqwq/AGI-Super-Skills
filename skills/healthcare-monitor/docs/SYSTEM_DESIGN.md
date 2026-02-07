# 医疗企业融资监控系统 - 技术设计文档

## 1. 系统概述

### 1.1 目标
实时监控医疗健康行业企业的融资动态，第一时间发现融资信号，为媒体、投资机构提供情报服务。

### 1.2 核心价值
- **时效性**: 比公开披露早 24-72 小时发现融资信号
- **准确性**: 多数据源交叉验证，降低误报率
- **自动化**: 7x24 小时自动监控，无需人工干预

---

## 2. 系统架构

```
┌─────────────────────────────────────────────────────────────┐
│                      数据采集层                              │
├─────────────┬─────────────┬─────────────┬──────────────────┤
│  新闻搜索   │  工商变更   │  投融资DB   │   社交媒体       │
│  Firecrawl  │  天眼查API  │  IT桔子     │   Twitter/微博   │
│  36氪/动脉网│  企查查     │  烯牛数据   │   LinkedIn       │
└──────┬──────┴──────┬──────┴──────┬──────┴────────┬─────────┘
       │             │             │               │
       ▼             ▼             ▼               ▼
┌─────────────────────────────────────────────────────────────┐
│                      数据清洗层                              │
│  - 去重 (URL/标题相似度)                                     │
│  - 过滤噪音 (融资融券、旧闻)                                 │
│  - 时间标准化                                                │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                      信号分析层                              │
│  - 关键词匹配 (融资/投资/轮次)                               │
│  - NLP 实体识别 (金额/投资方/轮次)                           │
│  - 置信度评分                                                │
│  - 交叉验证                                                  │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                      告警推送层                              │
│  - Telegram 实时告警                                         │
│  - 飞书群组推送                                              │
│  - 日报/周报生成                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 3. 数据源详解

### 3.1 新闻搜索 (主要数据源)

#### Firecrawl API
```yaml
优点:
  - 聚合多个搜索引擎结果
  - 支持中文搜索
  - 返回结构化数据
  - 实时性好 (分钟级)

缺点:
  - 有 API 调用限制
  - 需要付费

配置:
  API Key: pass show api/firecrawl
  端点: https://api.firecrawl.dev/v1/search
  限制: 1000 次/月 (免费额度)
```

#### 直接抓取新闻源
```yaml
36氪:
  URL: https://36kr.com/search/articles/{query}
  特点: 创投新闻最全，更新快
  延迟: 1-4 小时

动脉网:
  URL: https://vcbeat.top/search?q={query}
  特点: 医疗健康垂直媒体
  延迟: 2-6 小时

投资界:
  URL: https://www.pedaily.cn/search?q={query}
  特点: PE/VC 专业媒体
  延迟: 1-4 小时
```

### 3.2 工商变更 (高准确性数据源)

#### 天眼查/企查查
```yaml
数据类型:
  - 股东变更 (新增机构股东 = 强融资信号)
  - 注册资本变更 (增资 = 中融资信号)
  - 股权比例变更 (稀释 = 中融资信号)

优点:
  - 官方数据，准确性高
  - 可追溯历史变更

缺点:
  - 延迟 3-15 天 (工商登记滞后)
  - 需要付费 API 或爬虫

实现方式:
  1. 付费 API (推荐): 天眼查开放平台
  2. Playwright 爬虫: 需要处理反爬
  3. 国家企业信用公示系统: 免费但难爬
```

### 3.3 投融资数据库

#### IT桔子
```yaml
URL: https://www.itjuzi.com/
数据: 融资事件、投资方、金额、轮次
延迟: 1-7 天
获取方式: 爬虫或付费 API
```

#### 烯牛数据
```yaml
URL: https://www.xiniudata.com/
数据: 一级市场投融资数据
延迟: 1-3 天
获取方式: 付费订阅
```

### 3.4 社交媒体 (最快但噪音大)

```yaml
Twitter/X:
  - 关注投资人、创始人账号
  - 关键词监控
  - 延迟: 实时

微博:
  - 财经大V、创投媒体
  - 延迟: 实时

LinkedIn:
  - 高管职位变动
  - 公司动态
  - 延迟: 实时
```

---

## 4. 融资信号识别算法

### 4.1 关键词权重体系

```python
# 融资动作关键词 (强信号)
FUNDING_KEYWORDS = {
    "完成融资": 25,
    "宣布融资": 25,
    "获得投资": 20,
    "融资": 15,
    "投资": 10,
    "获投": 20,
}

# 融资轮次关键词 (强信号)
ROUND_KEYWORDS = {
    "种子轮": 20,
    "天使轮": 20,
    "Pre-A": 20,
    "A轮": 20,
    "B轮": 20,
    "C轮": 20,
    "D轮": 20,
    "E轮": 20,
    "战略投资": 15,
    "股权融资": 15,
}

# 投资机构关键词 (中信号)
INVESTOR_KEYWORDS = {
    "红杉": 15,
    "高瓴": 15,
    "IDG": 15,
    "经纬": 15,
    "软银": 15,
    "腾讯投资": 15,
    "资本": 10,
    "基金": 10,
    "创投": 10,
    "VC": 10,
    "PE": 10,
}

# 噪音关键词 (需排除)
NOISE_KEYWORDS = [
    "融资融券",
    "融资余额",
    "融资买入",
    "融资净买入",
    "融资净偿还",
    "两融",
]
```

### 4.2 置信度计算公式

```python
def calculate_confidence(text: str, title: str) -> int:
    """
    计算融资信号置信度 (0-100)
    """
    confidence = 0
    combined_text = f"{title} {text}"
    
    # 1. 检查噪音关键词 (直接排除)
    for noise in NOISE_KEYWORDS:
        if noise in combined_text:
            return 0  # 融资融券等噪音，直接返回0
    
    # 2. 融资动作关键词
    for keyword, weight in FUNDING_KEYWORDS.items():
        if keyword in combined_text:
            confidence += weight
    
    # 3. 融资轮次关键词
    for keyword, weight in ROUND_KEYWORDS.items():
        if keyword in combined_text:
            confidence += weight
            break  # 只计算一次
    
    # 4. 投资机构关键词
    investor_count = 0
    for keyword, weight in INVESTOR_KEYWORDS.items():
        if keyword in combined_text:
            confidence += weight
            investor_count += 1
            if investor_count >= 3:  # 最多计算3个
                break
    
    # 5. 金额识别加分
    if re.search(r'\d+(?:\.\d+)?\s*(?:亿|万|美元|人民币)', combined_text):
        confidence += 15
    
    # 6. 时间新鲜度加分
    if any(word in combined_text for word in ["今日", "刚刚", "最新", "宣布"]):
        confidence += 10
    
    # 上限 95%
    return min(confidence, 95)
```

### 4.3 信息提取规则

```python
# 融资轮次提取
ROUND_PATTERN = r"(种子轮|天使轮|Pre-[A-Z]|[A-Z]\+?轮|战略投资|股权融资)"

# 融资金额提取
AMOUNT_PATTERNS = [
    r"(\d+(?:\.\d+)?)\s*(亿美元)",
    r"(\d+(?:\.\d+)?)\s*(亿人民币|亿元|亿)",
    r"(\d+(?:\.\d+)?)\s*(万美元)",
    r"(\d+(?:\.\d+)?)\s*(万人民币|万元|万)",
    r"\$(\d+(?:\.\d+)?)\s*(billion|million|B|M)",
]

# 投资方提取
INVESTOR_PATTERN = r"([\u4e00-\u9fa5]+(?:资本|投资|基金|创投))"
```

---

## 5. 数据准确性保障

### 5.1 噪音过滤

```python
def filter_noise(news_item: dict) -> bool:
    """
    过滤噪音新闻
    返回 True 表示是有效新闻，False 表示是噪音
    """
    title = news_item.get("title", "")
    
    # 1. 排除融资融券新闻
    if any(noise in title for noise in ["融资融券", "融资余额", "两融"]):
        return False
    
    # 2. 排除股票行情新闻
    if any(word in title for word in ["涨停", "跌停", "股价", "市值"]):
        return False
    
    # 3. 排除过旧新闻 (标题中包含年份且不是当年)
    current_year = datetime.now().year
    year_match = re.search(r"20(\d{2})年", title)
    if year_match:
        news_year = 2000 + int(year_match.group(1))
        if news_year < current_year - 1:
            return False
    
    return True
```

### 5.2 多源交叉验证

```python
def cross_validate(company: str, signals: list) -> dict:
    """
    多数据源交叉验证
    """
    sources = set(s["source"] for s in signals)
    
    # 多源验证加分
    if len(sources) >= 3:
        confidence_boost = 20
    elif len(sources) >= 2:
        confidence_boost = 10
    else:
        confidence_boost = 0
    
    # 检查信息一致性
    amounts = [s.get("amount") for s in signals if s.get("amount")]
    rounds = [s.get("round") for s in signals if s.get("round")]
    
    consistency_score = 0
    if len(set(amounts)) == 1 and len(amounts) > 1:
        consistency_score += 15  # 金额一致
    if len(set(rounds)) == 1 and len(rounds) > 1:
        consistency_score += 15  # 轮次一致
    
    return {
        "sources_count": len(sources),
        "confidence_boost": confidence_boost + consistency_score,
        "is_verified": len(sources) >= 2
    }
```

### 5.3 时效性判断

```python
def assess_freshness(news_item: dict) -> str:
    """
    评估新闻时效性
    """
    title = news_item.get("title", "")
    snippet = news_item.get("snippet", "")
    text = f"{title} {snippet}"
    
    # 实时信号
    if any(word in text for word in ["刚刚", "今日", "今天", "最新消息"]):
        return "realtime"  # 实时
    
    # 近期信号
    if any(word in text for word in ["近日", "日前", "本周", "昨日"]):
        return "recent"  # 近期 (1-7天)
    
    # 检查具体日期
    date_match = re.search(r"(\d{1,2})月(\d{1,2})日", text)
    if date_match:
        month, day = int(date_match.group(1)), int(date_match.group(2))
        news_date = datetime(datetime.now().year, month, day)
        days_ago = (datetime.now() - news_date).days
        
        if days_ago <= 3:
            return "recent"
        elif days_ago <= 30:
            return "monthly"
        else:
            return "old"
    
    return "unknown"
```

---

## 6. 实时性优化

### 6.1 检测频率策略

```yaml
高优先级企业 (未上市/近期活跃):
  检测频率: 每 2 小时
  数据源: Firecrawl + 社交媒体
  
中优先级企业 (已上市/稳定期):
  检测频率: 每 6 小时
  数据源: Firecrawl + 新闻源

低优先级企业 (大型成熟企业):
  检测频率: 每 24 小时
  数据源: 新闻源
```

### 6.2 增量检测

```python
def incremental_check(company: str, last_check: datetime) -> list:
    """
    增量检测 - 只获取上次检测后的新数据
    """
    # 1. 搜索时添加时间限制
    query = f"{company} 融资 after:{last_check.strftime('%Y-%m-%d')}"
    
    # 2. 对比已知 URL，排除重复
    known_urls = load_known_urls(company)
    new_results = []
    
    for result in search_results:
        if result["url"] not in known_urls:
            new_results.append(result)
            save_url(company, result["url"])
    
    return new_results
```

### 6.3 实时推送策略

```yaml
高置信度 (>80%):
  推送方式: 立即推送 Telegram
  内容: 完整分析报告
  
中置信度 (50-80%):
  推送方式: 汇总到日报
  内容: 简要信息
  
低置信度 (<50%):
  推送方式: 仅记录日志
  内容: 无
```

---

## 7. 监控企业列表

### 7.1 当前监控 (10家)

| 企业 | 类别 | 优先级 | 状态 |
|------|------|--------|------|
| 迈瑞医疗 | 医疗器械 | 中 | 已上市 |
| 联影医疗 | 医疗器械 | 中 | 已上市 |
| 百济神州 | 创新药 | 中 | 已上市 |
| 信达生物 | 创新药 | 中 | 已上市 |
| 推想科技 | 医疗AI | 高 | 未上市 |
| 数坤科技 | 医疗AI | 高 | 未上市 |
| 微医集团 | 互联网医疗 | 高 | IPO中 |
| 丁香园 | 互联网医疗 | 高 | IPO中 |
| 华大基因 | 基因检测 | 中 | 已上市 |
| 燃石医学 | 基因检测 | 高 | 已上市 |

### 7.2 建议新增

```yaml
医疗AI (高优先级):
  - 深睿医疗
  - 汇医慧影
  - 医渡云
  - 鹰瞳科技

创新药 (高优先级):
  - 君实生物
  - 再鼎医药
  - 和黄医药
  - 康方生物

医疗器械 (中优先级):
  - 微创医疗
  - 先瑞达医疗
  - 心脉医疗
  - 启明医疗

基因检测 (中优先级):
  - 贝瑞基因
  - 泛生子
  - 诺禾致源
  - 世和基因
```

---

## 8. API 配置

### 8.1 Firecrawl
```bash
# 获取 API Key
pass show api/firecrawl

# 测试
curl -X POST "https://api.firecrawl.dev/v1/search" \
  -H "Authorization: Bearer $(pass show api/firecrawl)" \
  -H "Content-Type: application/json" \
  -d '{"query": "信达生物 融资", "limit": 5}'
```

### 8.2 天眼查 (待配置)
```bash
# 需要申请开放平台 API
# https://open.tianyancha.com/

# 配置
pass insert api/tianyancha
```

---

## 9. 运行命令

```bash
# 检查单个企业
python3 ~/clawd/skills/healthcare-monitor/scripts/funding_detector.py --company "信达生物"

# 执行完整检查
python3 ~/clawd/skills/healthcare-monitor/scripts/funding_detector.py --check

# 检查并推送
python3 ~/clawd/skills/healthcare-monitor/scripts/funding_detector.py --check --push
```

---

## 10. 待优化项

### 10.1 短期 (1-2周)
- [ ] 排除"融资融券"噪音
- [ ] 添加更多监控企业
- [ ] 优化置信度算法

### 10.2 中期 (1-2月)
- [ ] 接入天眼查 API (工商变更)
- [ ] 添加社交媒体监控
- [ ] 实现增量检测

### 10.3 长期 (3-6月)
- [ ] 训练专用 NLP 模型
- [ ] 构建投资方知识图谱
- [ ] 预测融资概率

---

*文档版本: v1.0*
*更新时间: 2026-02-06*
*作者: 小a*
