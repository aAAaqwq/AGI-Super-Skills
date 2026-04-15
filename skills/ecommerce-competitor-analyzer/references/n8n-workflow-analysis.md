# n8n 工作流参考

**来源**：Amazon 竞品分析 n8n 工作流 (v81)
**工作流 ID**：N2Z4oEsWYFAFWDX3
**位置**：你的 n8n 工作流 URL（私有）
**配置文件**：`工作流配置.json`

---

## 概述

本文档记录了从 n8n 工作流实现中的关键模式、决策和经验，这些内容与 skill 实现相关。

---

## 工作流架构

### 节点流程 (v81)

```
Google Sheets 触发器
    ↓
Google Sheets (读取 ASINs)
    ↓
过滤器 (跳过已分析的)
    ↓
Olostep API (抓取100条评论)
    ↓
Set (解析数据)
    ↓
Google Gemini (AI 分析)
    ↓
Code (提取结构化数据) ← **v81 关键修复**
    ↓
Google Sheets (写入结果)
```

### 关键节点

| 节点 | 用途 | 关键设置 |
|------|---------|------------------|
| **Filter** | 跳过已分析的 ASIN | 检查"分析结果"列是否为空 |
| **Olostep API** | 抓取产品页面 | `comments_number: 100` |
| **Google Gemini** | AI 分析 | 模型：`gemini-3-flash-preview` |
| **Code - Extract** | 解析 AI 响应 | 使用 `$input.all()` 进行批处理 |

---

## 关键修复与经验

### 问题 1：批处理不工作 (v79 → v81)

**症状**：工作流只处理了一个 ASIN，尽管从 Google Sheets 读取了多个。

**根本原因**："Code - 提取结构化数据"节点使用了 `$input.item.json` 而不是 `$input.all()`，导致所有项目合并成一个。

**证据**（执行 #368）：
```
Google Sheets: 3 个项目 ✅
Filter: 3 个项目 ✅
Olostep API: 3 个项目 ✅
Google Gemini: 3 个项目 ✅
Code - Extract: 1 个项目 ❌ (被合并！)
```

**解决方案** (v81)：
```javascript
// 之前（错误）
const item = $input.item.json;
// 只处理第一个项目

// 之后（正确）
const items = $input.all();
const results = items.map((item, index) => {
  // 独立处理每个项目
  return { json: { /* 提取的数据 */ } };
});
return results;  // 返回所有结果
```

**关键模式**：在 n8n Code 节点中进行批处理时，始终使用 `$input.all()` + `.map()`。

---

### 问题 2：表达式格式错误 (v71 → v72)

**症状**：工作流验证失败，提示"Invalid expression"错误。

**根本原因**：n8n 表达式必须使用 `{{ }}` 包裹，不能直接使用 JavaScript。

**解决方案**：
```javascript
// 之前（错误）
{{ $('Set - 解析数据').item.json.markdownContent }}

// 之后（正确）
{{ $('Set - 解析数据').item.json.markdownContent }}
```

**关键模式**：HTTP 节点中的所有 n8n 表达式必须使用双花括号。

---

## Skill 实现的代码模式

### 1. 批处理模式

```javascript
// 来自 n8n "Code - 提取结构化数据"节点 (v81)
const items = $input.all();

const results = items.map((item, index) => {
  try {
    // 从当前项目提取数据
    const aiResponse = item.json.content?.parts?.[0]?.text || '';

    // 获取该索引的上游数据
    const upstreamData = $('Set - 解析数据').all();
    const asin = upstreamData[index].json.asin;

    // 返回结构化结果
    return {
      json: {
        asin: asin,
        extractedTitle: extractTitle(aiResponse),
        extractedPrice: extractPrice(aiResponse),
        extractedRating: extractRating(aiResponse)
      }
    };
  } catch (error) {
    // 错误隔离：单个失败不会停止批处理
    return {
      json: {
        asin: 'unknown',
        error: 'Processing failed'
      }
    };
  }
});

return results;
```

### 2. 正则提取模式

```javascript
// 标题提取（多种备用模式）
const titlePatterns = [
  /产品标题[：:]+([^\n]+)/,
  /Title[：:]+([^\n]+)/
];

let title = '未知';  // 默认值
for (const pattern of titlePatterns) {
  const match = aiResponse.match(pattern);
  if (match) {
    title = match[1].trim();
    break;
  }
}

// 价格提取
const pricePatterns = [
  /价格[：:]+[^0-9]*([0-9]+\.?[0-9]*)/,
  /Price[：:]+[^0-9]*([0-9]+\.?[0-9]*)/
];

// 评分提取
const ratingPatterns = [
  /评分[：:]+[^0-9]*([0-9]+\.?[0-9]*)/,
  /Rating[：:]+[^0-9]*([0-9]+\.?[0-9]*)/
];
```

### 3. 错误隔离模式

```javascript
// 带错误隔离的处理
const items = $input.all();
const results = items.map((item, index) => {
  try {
    // 处理逻辑
    const data = processData(item);
    return { success: true, data };
  } catch (error) {
    // 返回错误结果而不是抛出异常
    return { success: false, error: error.message };
  }
});

// 继续处理所有结果（成功 + 失败）
return results;
```

---

## Olostep API 配置

### 请求格式

```javascript
{
  "url": "https://www.amazon.com/dp/B0C4YT8S6H",
  "wait_time": 10,
  "screenshot": false,
  "extract_dynamic_content": true,
  "comments_number": 100  // 关键：100条评论用于深度分析
}
```

### 响应格式

```javascript
{
  "task_id": "string",
  "markdown_content": "完整的页面内容（markdown格式）",
  "html_content": "完整的页面 HTML"
}
```

### 关键设置

| 参数 | 值 | 说明 |
|-----------|-------|-------|
| `comments_number` | 100 | 设置为 100 以进行深度评论分析 |
| `wait_time` | 10 | 允许页面完全加载 |
| `extract_dynamic_content` | true | 捕获 JS 渲染的内容 |

---

## Gemini AI 配置

### 模型

- **模型**：`gemini-3-flash-preview`
- **原因**：快速且性价比高的分析任务

### 提示词结构

提示词结构包含：
1. **角色**：专家级 Amazon 运营总监 + 品牌策略师
2. **目标**：4 维度的深度产品分析
3. **输出**：结构化分析 + 提取的字段

### 4 维度分析框架

1. **文案构建逻辑与词频分析** (The Brain)
   - 构建策略（痛点/场景/规格驱动）
   - Top 10 关键词提取

2. **视觉资产设计思路** (The Face)
   - 设计方法论
   - 视觉流程分解
   - 色彩心理学

3. **评论定量与定性分析** (The Voice)
   - 定量概述
   - 优势聚类
   - 负面评论深入分析
   - Top 3 洞察

4. **市场维态与盲区扫描** (The Pulse)
   - 价格趋势
   - Q&A 分析
   - 盲区识别

---

## Google Sheets 集成

### 表格结构

| 列 | 用途 |
|--------|---------|
| A (ASIN) | 产品标识符（输入） |
| B (分析结果) | 完整的 AI 分析（输出） |
| C (标题) | 提取的标题（输出） |
| D (价格) | 提取的价格（输出） |
| E (评分) | 提取的评分（输出） |

### 过滤逻辑

```javascript
// 如果已分析则跳过
const isAnalyzed = $input.item.json.分析结果 !== '';
return isAnalyzed === false;
```

---

## 版本历史

| 版本 | 日期 | 关键变更 |
|---------|------|-------------|
| v81 | 2026-01-28 | 修复批处理（Code 节点） |
| v80 | 2026-01-28 | 添加100条评论抓取 |
| v79 | 2026-01-28 | 批处理尝试 |
| v73-v78 | 2026-01-28 | 结构化数据提取 |
| v71-v72 | 2026-01-28 | 表达式格式修复 |

---

## Skill 实现检查清单

- [x] 使用 `$input.all()` + `.map()` 进行批处理
- [x] 实现错误隔离（单个失败 ≠ 批处理失败）
- [x] 使用 n8n 的确切 Gemini 提示词（无修改）
- [x] 使用正则备用模式提取标题/价格/评分
- [x] Olostep API 抓取100条评论
- [x] Google Sheets 双输出（表格 + markdown）
- [x] 支持 ASIN 和 URL 输入格式
