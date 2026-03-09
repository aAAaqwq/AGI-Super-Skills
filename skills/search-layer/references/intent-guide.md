# Intent Classification Guide

搜索意图分类的详细指南。Agent 在执行搜索前，先根据此指南判断用户查询的意图类型，然后选择对应的搜索策略。

## 七种意图类型

### 1. Factual（事实查询）

**识别信号**：
- "什么是 X"、"X 的定义"、"X 是什么意思"
- "What is X"、"Define X"、"X meaning"
- 问句结构，期望一个明确答案

**搜索策略**：
- Mode: `answer`（Tavily AI answer 优先）
- Freshness: 不限
- 查询扩展: 加 "definition"、"explained"、"overview"
- 结果偏好: 权威文档 > 百科 > 社区解答

**权重配置**：`--intent factual`
```
keyword_match: 0.4, freshness: 0.1, authority: 0.5
```

---

### 2. Status（状态/进展查询）

**识别信号**：
- "X 最新进展"、"X 现在怎样了"、"X 的状态"
- "X latest"、"X update"、"What's new with X"
- 含时间暗示词：最新、最近、目前、现在、进展

**搜索策略**：
- Mode: `deep`
- Freshness: `pw`（过去一周）或 `pm`（过去一月）
- 查询扩展: 加当前年份（动态）、"latest"、"update"、"release"
- 结果偏好: 最新 > 权威 > 完整

**权重配置**：`--intent status`
```
keyword_match: 0.3, freshness: 0.5, authority: 0.2
```

---

### 3. Comparison（对比查询）

**识别信号**：
- "X vs Y"、"X 和 Y 的区别"、"X 还是 Y"
- "X compared to Y"、"X or Y"、"difference between X and Y"
- 两个或多个实体的并列

**搜索策略**：
- Mode: `deep`
- Freshness: `py`（过去一年，确保不过时）
- 查询分解: 生成 3 个子查询
  1. "X vs Y" / "X compared to Y"
  2. "X advantages features" / "X 优势"
  3. "Y advantages features" / "Y 优势"
- 结果偏好: 同时包含两者的文章 > 单方面评测

**权重配置**：`--intent comparison`
```
keyword_match: 0.4, freshness: 0.2, authority: 0.4
```

---

### 4. Tutorial（教程/操作指南）

**识别信号**：
- "怎么做 X"、"如何 X"、"X 教程"、"X 入门"
- "How to X"、"X tutorial"、"X guide"、"getting started with X"
- 动作导向的问句

**搜索策略**：
- Mode: `answer`
- Freshness: `py`（过去一年，避免过时教程）
- 查询扩展: 加 "tutorial"、"guide"、"step by step"、"example"
- Domain boost: `dev.to, freecodecamp.org, realpython.com, baeldung.com`
- 结果偏好: 步骤清晰的教程 > 概念解释

**权重配置**：`--intent tutorial`
```
keyword_match: 0.4, freshness: 0.1, authority: 0.5
```

---

### 5. Exploratory（探索性查询）

**识别信号**：
- "关于 X 的一切"、"深入了解 X"、"X 生态"
- "Everything about X"、"X ecosystem"、"X deep dive"
- 开放式、无明确边界的查询

**搜索策略**：
- Mode: `deep`
- Freshness: 不限
- 查询分解: 生成 2-3 个角度
  1. "X overview architecture"
  2. "X ecosystem community"
  3. "X use cases applications"
- 结果偏好: 覆盖面广 > 单点深入

**权重配置**：`--intent exploratory`
```
keyword_match: 0.3, freshness: 0.2, authority: 0.5
```

---

### 6. News（新闻查询）

**识别信号**：
- "X 新闻"、"X 最近发生了什么"、"本周 X"
- "X news"、"X this week"、"latest X announcements"
- 明确的新闻/时事导向

**搜索策略**：
- Mode: `deep`
- Freshness: `pd`（24h）或 `pw`（一周）
- 查询扩展: 加 "news"、"announcement"、"release"、当前日期
- 结果偏好: 最新 > 一切

**权重配置**：`--intent news`
```
keyword_match: 0.3, freshness: 0.6, authority: 0.1
```

---

### 7. Resource（资源定位）

**识别信号**：
- "X 官网"、"X GitHub"、"X 文档"、"X 下载"
- "X official site"、"X documentation"、"X repo"
- 寻找特定资源/链接

**搜索策略**：
- Mode: `fast`
- Freshness: 不限
- 查询扩展: 加 "official"、"github"、"documentation" 等具体资源类型
- 结果偏好: 精确匹配 > 相关内容

**权重配置**：`--intent resource`
```
keyword_match: 0.5, freshness: 0.1, authority: 0.4
```

## 意图判断流程

```
1. 扫描查询中的信号词（见各类型的"识别信号"）
2. 如果匹配多个类型，按优先级选择：Resource > News > Status > Comparison > Tutorial > Factual > Exploratory
   - 例："Deno 最新版本下载" 同时匹配 Status 和 Resource → 选 Resource
   - 例："Bun vs Deno 最新对比" 同时匹配 Comparison 和 Status → 选 Comparison（但加 freshness）
3. 如果无法判断，默认 exploratory
4. 中文查询同时生成英文变体（技术类查询）
```

## 查询扩展规则

### 技术同义词（自动扩展）
- k8s → Kubernetes
- JS → JavaScript
- TS → TypeScript
- React → React.js / ReactJS
- Vue → Vue.js / VueJS
- Go → Golang
- Postgres → PostgreSQL
- Mongo → MongoDB
- tf → TensorFlow
- torch → PyTorch

### 语言适配
- 中文技术查询 → 同时搜英文版本
- 例："Rust 异步编程" → 额外搜 "Rust async programming"
