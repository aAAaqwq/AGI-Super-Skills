# 搜神猎手 (SouShen Hunter)

> "搜索如狩猎，信息即猎物"

高性能 Bing 搜索引擎 Skill for OpenClaw - 无需 API 费用，深度网页元素提取

## ✨ 特性

- 🔍 **Bing 搜索** - 使用 Playwright 底层 API，零 API 费用
- 🎯 **深度提取** - 自动提取页面链接、表单、按钮、脚本
- ⚡ **高性能** - 异步架构，快速响应
- 🛡️ **反检测** - 绕过反爬虫机制
- 🤖 **OpenClaw 集成** - 开箱即用

## 📦 安装

```bash
# 克隆仓库
git clone https://github.com/hexian2001/soushen-hunter.git

# 复制到 OpenClaw skills 目录
cp -r soushen-hunter ~/.openclaw/skills/

# 重启 OpenClaw
```

## 🔧 依赖

```bash
pip install playwright
```

**Chrome 自动检测**

脚本会自动检测以下位置的 Chrome：
- 环境变量 `CHROME_PATH` 或 `CHROME_BIN`
- 系统 PATH 中的 `google-chrome`, `chromium` 等
- 常见安装路径（Linux/macOS/Windows）

手动指定 Chrome 路径：
```bash
export CHROME_PATH=/usr/bin/google-chrome
python scripts/bing_search.py "搜索关键词"
```

## 🚀 使用

### CLI 命令

```bash
# 搜神搜索
./soushen "搜索关键词"
# 或
python soushen "搜索关键词"

# 深度页面分析（自动化全面提取）
./soushen --deep "https://目标网址"
# 或
python soushen --deep "https://目标网址"
```

### Python API

**基础搜索**
```python
from scripts.bing_search import BingSearchAgent
import asyncio

async def main():
    async with BingSearchAgent() as agent:
        results = await agent.search("OpenClaw AI Agent")
        for r in results:
            print(f"{r.title}: {r.url}")

asyncio.run(main())
```

**深度页面分析**
```python
async with BingSearchAgent() as agent:
    elements = await agent.extract_page_elements("https://example.com")
    print(f"找到 {len(elements.links)} 个链接")
    print(f"发现 {len(elements.forms)} 个表单")
    print(f"提取 {len(elements.buttons)} 个按钮")
    print(f"发现 {len(elements.scripts)} 个外部脚本")
```

## 📁 结构

```
soushen-hunter/
├── SKILL.md              # Skill 定义文档
├── README.md             # 本文件
└── scripts/
    └── bing_search.py    # 核心搜索脚本
```

## 🔥 为什么叫"搜神猎手"

> 在古代神话中，猎手们追踪猎物于山林之间
> 在信息时代，我们追寻知识于网络之中

**搜神** - 搜寻信息的神奇能力  
**猎手** - 精准、迅猛、一击必中

## 👤 作者

胤仙（何润培）- 小喵的主人

## 📄 许可

MIT License

---

*由 OpenClaw AI 助手「小喵」协助创建* 🐱
