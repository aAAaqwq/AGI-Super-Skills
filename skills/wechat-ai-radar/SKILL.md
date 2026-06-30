---
name: wechat-ai-radar
description: 微信朋友圈AI雷达 — 自动化采集276+条朋友圈内容，通过AI视觉提取、分类分析、商机发现，生成结构化简报。支持每日定时任务，一键生成热点报告。
triggers:
  - 微信朋友圈分析
  - 朋友圈简报
  - 朋友圈AI报告
  - 微信热点分析
  - 分析朋友圈
  - 生成朋友圈报告
  - 采集朋友圈
  - wechat moments
---

# WeChat AI Radar 技能文档

## 技能概述

**项目路径**: `~/wechat_ai_radar/`

微信朋友圈AI雷达是一个完整的自动化内容采集+分析系统，核心流程：

```
微信朋友圈滚动截图 → AI视觉提取内容 → 存储数据库 → AI分类聚合分析 → 生成结构化简报
```

---

## 核心架构

### 模块说明

| 模块 | 路径 | 功能 |
|------|------|------|
| **config.py** | `~/wechat_ai_radar/config.py` | 全局配置（坐标、API、日志等） |
| **app.py** | `~/wechat_ai_radar/app.py` | 主程序入口，支持多模式运行 |
| **run_300.py** | `~/wechat_ai_radar/run_300.py` | 采集300条帖子完整流程脚本 |
| **automation/** | `automation/scroll_moments.py` | PyAutoGUI模拟滚动截图 |
| **extractor/** | `extractor/moments_extractor.py` | AI视觉从截图提取朋友圈内容 |
| **db/** | `db/database.py` | SQLite数据库读写 |
| **ai/** | `ai/classify.py`, `ai/summarize.py` | AI分类和聚合分析 |
| **reports/** | `reports/daily_report.py` | 日报生成器 |

---

## 关键配置参数

### 朋友圈窗口坐标（已校准）
```python
WECHAT_MOMENTS_FALLBACK_X = 0   # 朋友圈窗口x坐标（屏幕左上角）
WECHAT_MOMENTS_FALLBACK_Y = 0   # 朋友圈窗口y坐标
WECHAT_CONTENT_WIDTH = 550      # 内容区宽度
WECHAT_CONTENT_HEIGHT = 969     # 内容区高度
滚动鼠标目标 = (275, 484)       # 内容区中心
```

### 滚动参数
```python
SCROLL_COUNT = 50              # 默认滚动次数
SCROLL_INTERVAL = 1.0          # 滚动间隔（秒）
SCROLL_AMOUNT = -300           # 每次滚动像素量（负值=向上）
SCROLL_MOUSE_CLICKS = 3        # 每次滚动执行几次scroll调用
```

### AI API配置
```python
AI_API_URL = "https://api.qingyuntop.top/v1"  # 青禾聚合API
AI_API_KEY = config.AI_API_KEY  # 从config读取
AI_MODEL = "gpt-4o-mini"
AI_MAX_TOKENS = 4000
AI_TEMPERATURE = 0.7
AI_REQUEST_DELAY = 1.0         # API请求间隔（秒）
AI_BATCH_SIZE = 10             # 每批处理数量
```

---

## 使用方式

### 方式一：完整采集流程（采集 + 分析 + 简报）

```bash
cd ~/wechat_ai_radar && uv run python run_300.py
```

**流程**：
1. 自动打开/激活微信
2. 执行150次滚动截图（约300条帖子）
3. AI视觉提取内容 → 存入 `moments.db`
4. AI聚合分析
5. 生成简报（Markdown格式）

**目标**：约300条帖子 / 耗时约15-20分钟

---

### 方式二：仅采集截图（不分析）

```bash
cd ~/wechat_ai_radar && uv run python -c "
from automation.open_wechat import WeChatOpener
from automation.scroll_moments import MomentsScroller
import config

opener = WeChatOpener()
opener.activate_wechat()

scroller = MomentsScroller(scroll_count=50, scroll_interval=1.5)
screenshots = scroller.scroll_full(capture=True)
print(f'截图完成: {len(screenshots)} 张')
"
```

---

### 方式三：基于已有数据生成简报

已有 `extracted_*.json` 数据文件时，直接生成简报：

```bash
cd ~/wechat_ai_radar && uv run python reports/generate_daily_report.py
```

**日报结构**（用户指定框架）：
```
# 今日朋友圈热点
## 🔥 热门关键词
## 📈 热门分类（AI/活动/创业/SaaS/出海/促销）
## 💼 商机发现（AI合作/合作需求/创业动态/投资动态）
## 👥 高频人物
## 🧠 AI总结
```

---

### 方式四：app.py 多模式运行

```bash
# 仅滚动截图
uv run python app.py scroll

# OCR文字提取（需要paddleocr）
uv run python app.py ocr

# AI分析已有数据
uv run python app.py analyze

# AI总结
uv run python app.py summarize

# 生成日报
uv run python app.py report

# 启动定时任务（每天21:00自动运行）
uv run python app.py schedule --hour 21 --minute 0
```

---

## 数据文件路径

| 用途 | 路径 |
|------|------|
| 数据库 | `~/wechat_ai_radar/data/moments.db` |
| 截图目录 | `~/wechat_ai_radar/screenshots/` |
| 报告目录 | `~/wechat_ai_radar/reports/` |
| 日志目录 | `~/wechat_ai_radar/logs/` |
| 最新提取数据 | `~/wechat_ai_radar/data/extracted_YYYYMMDD_HHMMSS.json` |

---

## 数据库结构

```sql
-- moments 表
id, content, author, image_path, created_at, hash,
likes, comments, is_analyzed, category, keywords,
people, companies, business_opportunity, sentiment, summary
```

```python
# 读取数据示例
from db.database import Database
from db.storage import Storage

db = Database()
storage = Storage(db)
moments = storage.get_recent(days=7, limit=100)
for m in moments:
    print(f"[{m.author}] {m.content[:50]}")
```

---

## 已封装的便捷脚本

### 1. `reports/generate_daily_report.py`
- 输入：`extracted_*.json` 文件
- 输出：Markdown格式日报 + Word文档
- 框架：热门关键词/分类/商机/人物/AI总结

### 2. `reports/daily_report_to_docx.py`
- 将日报数据转换为Word文档（A4横向，蓝色主题）

### 3. `extract_and_analyze.py`
- 批量处理截图 → AI提取 → 存入数据库

---

## 前置要求

```bash
# 安装依赖
cd ~/wechat_ai_radar && uv sync

# 核心依赖（pyproject.toml）
pyautogui, Pillow, python-dateutil, openai, httpx, APScheduler
```

---

## 已知限制

1. **窗口必须可见**：朋友圈窗口需在屏幕上可见（不能最小化）
2. **坐标依赖屏幕布局**：已校准为 (x=0, y=0) 屏幕左上角布局
3. **Mac专属**：使用PyAutoGUI + macOS特定配置
4. **OCR可选**：paddleocr未安装时跳过OCR，使用AI视觉提取替代

---

## 快捷命令汇总

```bash
# 完整采集+简报
cd ~/wechat_ai_radar && uv run python run_300.py

# 快速生成日报（基于已有JSON）
cd ~/wechat_ai_radar && uv run python reports/generate_daily_report.py

# 生成Word版日报
cd ~/wechat_ai_radar && uv run python reports/daily_report_to_docx.py

# 采集50次滚动截图
cd ~/wechat_ai_radar && uv run python -c "
from automation.open_wechat import WeChatOpener
from automation.scroll_moments import MomentsScroller
opener = WeChatOpener()
opener.activate_wechat()
scroller = MomentsScroller(scroll_count=50, scroll_interval=1.5)
screenshots = scroller.scroll_full(capture=True)
print(f'完成: {len(screenshots)} 张截图')
"
```