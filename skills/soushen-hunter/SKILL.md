---
name: soushen-hunter
description: |
  高性能 Bing 搜索引擎 Skill - "搜神猎手"
  使用 Playwright 底层 API 进行深度网页搜索和元素提取
  
  功能：
  1. Bing 搜索执行 - 返回结构化搜索结果（标题、链接、摘要、来源）
  2. 深度页面分析 - 提取页面的所有关键元素（链接、表单、按钮、脚本、元数据）
  
  触发条件：
  - 用户需要进行 Bing 网络搜索时
  - 需要提取网页结构信息（链接、表单等）时
  - 需要无 API 成本的搜索解决方案时
  
  使用方法：
  - 基础搜索：python scripts/bing_search.py "搜索关键词"
  - 深度分析：python scripts/bing_search.py "关键词" --deep <目标URL>
---

# 搜神猎手 (SouShen Hunter) - Bing 搜索 Skill

高性能 Bing 搜索引擎，基于 Playwright 实现深度网页信息提取。

## 核心功能

### 1. Bing 搜索
执行 Bing 搜索并返回结构化结果：
- 标题、URL、摘要、来源网站
- 自动过滤广告和无关内容
- 支持中文和英文搜索

### 2. 深度页面分析
对指定 URL 进行深度扫描，提取：
- **所有链接**：文本、href、类型
- **表单信息**：action、method、输入字段
- **按钮元素**：文本、类型、动作
- **外部脚本**：JS 文件 URL 列表
- **页面元数据**：meta tags、Open Graph 等

## 使用方法

### 基础搜索
```bash
python scripts/bing_search.py "OpenClaw AI Agent"
```

### 深度页面分析
```bash
python scripts/bing_search.py "placeholder" --deep https://example.com
```

### Python API
```python
from bing_search import BingSearchAgent, SearchResult

async with BingSearchAgent(headless=True) as agent:
    # 搜索
    results = await agent.search("关键词", num_results=10)
    
    # 深度分析
    elements = await agent.extract_page_elements("https://example.com")
```

## 依赖要求

- Python 3.8+
- playwright (`pip install playwright`)
- Chrome/Chromium 浏览器

## 配置说明

脚本默认查找以下 Chrome 路径：
- `~/.local/bin/chrome-for-testing-dir/chrome`
- `/usr/bin/google-chrome`
- `/usr/bin/chromium`

可通过修改脚本中的 `CHROME_PATHS` 列表自定义路径。

## 反检测特性

- 禁用自动化控制标记 (`--disable-blink-features=AutomationControlled`)
- 模拟真实用户代理
- 设置合理视口大小
- 随机化部分行为模式
