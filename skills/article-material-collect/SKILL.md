---
name: article-material-collect
description: 上层编排 Skill，通过 **Brave Search 发现 → 智能选择浏览器截图** 完成结构化素材采集。
  文章素材收集编排Skill。为MediaClaw内容生产提供结构化的多平台素材采集workflow。
  强制使用OpenClaw Browser截图实际文章页面，支持GitHub/Reddit/X/Medium/知乎等。
  用法: (1) content-ops-toolkit素材阶段调用 (2) daily-*-content素材采集 (3) 独立素材收集任务。
  Trigger: "收集素材", "素材收集", "采集素材", "素材", "找素材", "research materials", "material collect".
  Author: Daniel Li
  version: 2.1.0
  dependencies: [brave-search, web-content-capture]
---

# 文章素材收集 v2.1

> MediaClaw 素材收集编排 Skill — OpenClaw Browser + Playwright 双模式

## v1.0 → v2.1 修复历程

| 版本 | 修复内容 |
|------|---------|
| v1.0 | 问题版：Playwright 优先 → 截图搜索页 |
| v2.0 | 修复：OpenClaw Browser 强制优先 → 截图实际文章页 |
| **v2.1** | **当前版**：强化质量门槛、平台登录要求、修复 Reddit/X 截无效图问题 |

## 定位

上层编排 Skill，通过 **Brave Search 发现 → 智能选择浏览器截图** 完成结构化素材采集。

**智能选择原则**：公开页面用 Playwright（更快更稳），需要登录的页面用 OpenClaw Browser。

## 默认配置

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| 公开页面浏览器 | **Playwright headless** | Reddit、DEV、GitHub、Medium |
| 需登录页面浏览器 | **OpenClaw Browser (openclaw profile)** | X/Twitter、知乎（部分） |
| 截图质量门槛 | **≥50KB** | （v2.1 从 20KB 提高到 50KB） |
| 信息源 | DEV, GitHub, Reddit, X, Medium, 知乎 | 可扩展 |
| 保存位置 | `MediaClaw/output/articles/{date}/{topic}/素材/` | 调用方可覆盖 |
| 搜索工具 | Brave Search API | `node ~/.openclaw/skills/brave-search/search.js` |

## 平台登录要求（v2.1 新增）

| 平台 | 需要登录 | 推荐浏览器 | 素材价值 |
|------|---------|-----------|---------|
| **DEV Community** | ❌ 否 | Playwright | ⭐⭐⭐⭐⭐ 推荐替代 X/Reddit |
| **GitHub** | ❌ 否 | Playwright | ⭐⭐⭐⭐⭐ 代码/项目测评必备 |
| **Reddit** | ❌ 否 | Playwright | ⭐⭐⭐⭐ 社区观点，需实际帖子 URL |
| **Medium** | ❌ 否 | Playwright | ⭐⭐⭐⭐ 技术博客 |
| **X/Twitter** | ✅ 是 | OpenClaw Browser（需登录） | ⭐⭐⭐ 大V观点，**未登录则跳过** |
| **知乎** | ✅ 部分 | OpenClaw Browser | ⭐⭐⭐ 中文内容，**未登录则跳过** |
| **Google** | ❌ 否 | Playwright | ⭐ 热度参考，**不截图搜索结果** |

## Workflow（v2.1）

### Phase 1: 确认收集参数

**必须明确以下3项才能开始采集**：

```
1. 主题/关键词 → 用来搜索的query（可以是中英文多个）
2. 文章关联 → 对应哪篇文章（日期+slug），决定保存路径
3. 信息源 → 从哪些平台收集（建议：DEV + GitHub + Reddit + Medium，跳过 X/知乎除非已登录）
```

**输出确认**：
```
素材收集确认（v2.1）：
- 主题：{query}
- 关联文章：{date}/{slug}
- 保存位置：{output_dir}/素材/
- 信息源：{platforms}
- 浏览器策略：公开页面 → Playwright / 需登录 → OpenClaw Browser
```

### Phase 2: 搜索发现（获取实际内容页 URL）

用 Brave Search API 发现**实际内容页 URL**（不是搜索结果页）：

```bash
node ~/.openclaw/skills/brave-search/search.js "Claude Code vs Codex comparison 2026" -n 10 --content
```

**关键原则**：从搜索结果中提取**实际文章/帖子 URL**，按以下优先级：

| 优先级 | 平台类型 | URL 特征 | 说明 |
|--------|---------|---------|------|
| ⭐⭐⭐⭐⭐ | DEV Community 文章 | `dev.to/{user}/{slug}` | 公开内容，质量高，**优先采集** |
| ⭐⭐⭐⭐⭐ | GitHub 项目页面 | `github.com/{user}/{repo}` | 工具/项目测评必备 |
| ⭐⭐⭐⭐ | Reddit 帖子 | `reddit.com/r/{sub}/comments/{id}/` | 从搜索结果提取实际帖子 URL |
| ⭐⭐⭐⭐ | 技术博客（NxCode等） | 独立域名文章页 | 有数据、有观点、可截图 |
| ⭐⭐⭐ | Medium / 知乎 / CSDN | 文章页 URL | 中文内容，需文章页 URL |
| ⭐⭐ | X 大V 推文 | `x.com/{user}/status/{id}` | **需登录**，未登录则跳过 |
| ⭐ | Google 搜索结果页 | `google.com/search?q=` | **仅作热度证明，不截文章** |

**🚨 v2.1 特别注意**：
- **Reddit**：URL 必须是 `/comments/{id}/` 格式，不是 `/search/?q=` 格式
- **X**：必须从搜索结果提取实际推文 URL，未登录则跳过
- **Google**：**严禁截图搜索结果页**，只记录搜索结果数量

### Phase 3: 智能采集（按平台选择浏览器）

#### 公开页面 → Playwright（推荐）

```python
import asyncio
from playwright.async_api import async_playwright

async def collect_material(url: str, output_path: str, wait_s: int = 8) -> dict:
    """采集公开页面素材"""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(
            viewport={"width": 1400, "height": 900},
            user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"
        )
        try:
            await page.goto(url, timeout=25000, wait_until="networkidle")
            await asyncio.sleep(wait_s)
            await page.screenshot(path=output_path, full_page=True)
            size = os.path.getsize(output_path)
            return {"status": "ok", "size": size, "path": output_path}
        except Exception as e:
            return {"status": "error", "error": str(e)}
        finally:
            await browser.close()
```

#### 需要登录 → OpenClaw Browser

```bash
# 检查登录状态
browser(action="status", profile="openclaw")
# 如果 running=true → 已登录，继续
# 如果 running=false → 未登录 → 跳过该平台
```

```bash
# 打开页面
browser(action="open", profile="openclaw", targetUrl="https://...")

# 等待加载（X/知乎需要更长等待）
browser(action="act", targetId="xxx", request={"kind": "wait", "timeMs": 12000})

# 截图
browser(action="screenshot", profile="openclaw", targetId="xxx", type="png")
```

### Phase 4: 质量验证（强制门控）

**每个截图必须通过以下检查**：

```bash
# 1. 文件大小 ≥ 50KB
size=$(stat -c%s "$path")
if [ $size -lt 51200 ]; then
    echo "FAIL: 文件太小 (${size}B < 50KB)，重试"
    # 重试：增加等待时间 +5s
fi

# 2. 非空白图片
python3 -c "
from PIL import Image; import numpy as np
img = np.array(Image.open('$path'))
if img.mean() > 250:
    print('FAIL: blank image')
else:
    print('OK')
"

# 3. 内容相关性（目测检查截图是否包含目标关键词）
```

**重试策略**：
1. 第一次失败 → 等待时间 +5s，重试
2. 第二次失败 → 换浏览器方式（OpenClaw ↔ Playwright）
3. 第三次失败 → 标记为"截图失败"并记录原因

### Phase 5: 保存与索引

**目录结构**：
```
{OUTPUT_DIR}/素材/
├── README.md              ← 素材索引（必须）
├── dev-community/         ← DEV 文章截图
│   └── *.png
├── github/                ← GitHub 项目截图
│   └── *.png
├── reddit/                ← Reddit 帖子截图
│   └── *.png
├── medium/                ← Medium 文章截图
│   └── *.png
├── x/                     ← X 推文截图（仅登录成功时）
│   └── *.png
└── failed/                 ← 截图失败的记录
    └── README.md
```

**素材索引 README.md（必须）**：
```markdown
# 素材索引 — {topic}
## 采集时间: {YYYY-MM-DD HH:MM}
## 采集工具: Playwright (公开页) + OpenClaw Browser (需登录页)

| 平台 | 标题 | URL | 文件 | 大小 | 状态 |
|------|------|-----|------|------|------|
| DEV | Claude Code vs Codex | https://dev.to/... | dev-xxx.png | 240KB | ✅ |
| Reddit | 500+ developers | https://reddit.com/r/... | reddit-xxx.png | 85KB | ✅ |
| X | @user analysis | - | - | - | ❌ 未登录跳过 |
| Google | - | - | - | - | ℹ️ 仅记录数量 |

统计: 有效截图 {n} 张 / 总计划 {n} 张
跳过: {platforms}（原因：{reasons}）
```

---

## 快速调用模板

```
调用 article-material-collect v2.1:
  topic: "Claude vs Codex 对比"
  query_zh: "Claude Code Codex 对比 评测 2026"
  query_en: "Claude Code vs Codex comparison 2026"
  article: "2026-04-16/claude-vs-codex"
  sources: [dev-community, github, reddit, medium]  ← 推荐：跳过 X/知乎除非已登录
  output_dir: ~/clawd/projects/MediaClaw/output/articles/2026-04-16/claude-vs-codex/素材/
```

## 质量标准（v2.1）

- [ ] 素材文件夹包含 README.md 索引
- [ ] 每张截图 ≥ 50KB（非空白）✅ 强化
- [ ] 截图的是**实际文章内容**，不是搜索结果页 ✅ 强化
- [ ] Reddit 截图是帖子页，不是 /search/ 页面 ✅ 新增
- [ ] X 截图有登录态才执行，无登录则跳过并记录 ✅ 新增
- [ ] Google 搜索结果**不截图**，只记录数量 ✅ 新增
- [ ] DEV Community 作为优先信息源 ✅ 新增
- [ ] 文件命名有意义（非 screenshot-1.png）
- [ ] 素材可直接用于文章嵌入（清晰、相关、裁剪得当）

## 铁律（v2.1）

1. **智能选择浏览器** — 公开页面用 Playwright（更快），需登录用 OpenClaw Browser
2. **截取实际内容页** — 禁止截图 Reddit/X/Google 搜索结果页
3. **质量门控** — 每个截图必须 ≥ 50KB + 非空白
4. **跳过而非失败** — X/知乎等平台未登录时，跳过并记录原因（不算失败）
5. **DEV 优先** — DEV Community 是最可靠的公开技术内容源，优先采集
6. **必须索引** — 每次采集必须生成 README.md
7. **先确认再采集** — Phase 1 参数确认后才执行 Phase 2-5
8. **不暴露隐私** — 截图前检查无个人信息泄露

## 已知问题与应对

| 问题 | 原因 | 应对 |
|------|------|------|
| Reddit 截图是搜索页 | v1.0 行为，未更新 URL | v2.1：必须用 /comments/ URL |
| Reddit headless 超时 | Reddit 检测 headless 浏览器 | v2.1：改用 `domcontentloaded` + 真实 UA + 10s 等待 |
| X 截图 22KB（空白） | openclaw profile 未登录 X | v2.1：跳过或用 OpenClaw Browser（需登录态） |
| Nitter 备选不可靠 | Nitter 实例不稳定 | v2.1：仅作备选，主要靠 openclaw browser 登录态 |
| Google 截图没用 | 搜索结果页无实质内容 | v2.1：明确禁止，改为记录数量 |
| 知乎需要登录 | 大部分内容需登录 | v2.1：跳过并记录 |

**实测结果（2026-04-16）**：
| 平台 | 方法 | 结果 | 大小 |
|------|------|------|------|
| Reddit | Playwright (domcontentloaded) | ✅ 通过 | 860KB |
| DEV Community | Playwright (domcontentloaded) | ✅ 极佳 | 1706KB |
| Nitter | Playwright | ❌ 几乎空白 | 6KB |
| X/Twitter | OpenClaw Browser (未登录) | ❌ 空白 | <50KB |

**结论**：Reddit → Playwright（真实UA）；X → OpenClaw Browser（登录态）或跳过；Nitter 不可靠。

---

## 上层调用

content-ops-toolkit 在素材阶段调用本 skill。本 skill 内部调用：
- `brave-search` → 搜索发现
- `web-content-capture` → 底层截图（v2.1 修复版）

---

## 更新日志

- **v2.1.0** (2026-04-16): 修复 Daniel 反馈的素材无效问题
  - 提高质量门槛：20KB → 50KB
  - 添加完整平台登录要求文档
  - 修复 Reddit URL（必须 /comments/ 而非 /search/）
  - 添加 X 未登录跳过机制
  - 明确禁止截图 Google 搜索结果
  - 新增 DEV Community 作为优先信息源
  - 添加跳过机制（平台未登录不算失败）
  - 细化质量验证和重试策略
- **v2.0.0** (2026-04-15): OpenClaw Browser 强制优先，动态等待
- **v1.0.0** (2026-04-14): 初始版本