---
name: code-material-gen
description: |
  代码生成配图素材。用 HTML/CSS + Playwright 渲染高质量中文配图。
  不依赖任何AI图片API，100%代码生成，字体可控、像素精确、零成本。
  Trigger: "代码生成素材", "配图生成", "素材生成", "code material", "render material".
metadata:
  version: 1.0.0
  author: CCO Ives
  domains: [content, design, automation]
  type: production
---

# code-material-gen — 代码生成配图素材

> HTML/CSS + Playwright 渲染，全中文手写字体，像素精确，零成本

## 定位

当素材需要**全中文、手写字体、字迹清晰、可复现**时使用。替代API生图方案（longform-visual-notes），不消耗任何API额度。

## 与其他skill的关系

| Skill | 关系 |
|-------|------|
| longform-visual-notes | 互补：API生图 vs 代码生成 |
| content-cover-gen | 互补：封面场景可用code-material-gen |
| daily-gzh-content | 素材生成阶段调用 |
| daily-xhs-content | 小红书素材（比例改3:4） |

## 快速使用

```bash
python3 ~/clawd/skills/code-material-gen/scripts/generate.py \
  --type list \
  --title "三个核心建议" \
  --items "建议一:先用Excel写规则" "建议二:手动执行30天" "建议三:追求稳定性" \
  --font MaShanZheng \
  --palette ink \
  --size 1536x1024 \
  --output /path/to/output.png
```

## 素材类型

| type | 用途 | items格式 |
|------|------|----------|
| `timeline` | 时间线/阶段图 | `"阶段一:描述" "阶段二:描述"` |
| `compare` | 对比表格（表头第一项） | `"指标\|A\|B" "胜率\|59%\|61%"` |
| `list` | 要点列表/编号卡片 | `"标题:描述"` |
| `quote` | 金句/引用卡片 | `"金句文字" "作者"` |
| `cover` | 文章封面 | `"副标题" "标签1,标签2"` |
| `chart` | 数据展示（同list） | 同list |

## 手写字体

| 字体 | 风格 | 推荐场景 |
|------|------|---------|
| `MaShanZheng` | 马善政楷体 | ✅ **推荐**，清晰有力，正文首选 |
| `ZCOOLKuaiLe` | 站酷快乐体 | 圆润活泼，适合轻松内容 |
| `LiuJianMaoCao` | 刘建毛草 | 草书风格，仅适合大标题 |
| `ZhiMangXing` | 芝麻行书 | 行书风格，适合金句卡片 |

## 配色方案

| palette | 风格 | 适用 |
|---------|------|------|
| `tech` | 深色科技（深蓝底+亮蓝） | AI/科技/数据主题 |
| `warm` | 暖色纸张（米色底+橙红） | 经验分享/生活类 |
| `ink` | 水墨风（白底+红黑） | ✅ **推荐**，文化感强 |
| `minimal` | 极简白（白底+蓝） | 通用/商务 |

## 尺寸建议

| 平台 | 推荐 | 参数 |
|------|------|------|
| 公众号/抖音 | 16:9 | `1536x1024` |
| 小红书 | 3:4 | `1024x1365` |
| 封面 | 16:9 | `1920x1080` |

## 输出规范

- ✅ **全中文**，无任何英文
- ✅ **手写字体**，清晰可读
- ✅ **零成本**，不消耗API
- ✅ **可复现**，同样参数永远输出一样
- ✅ **<1秒/张**，批量生成极快

## 依赖

- Python 3 + Playwright（`pip install playwright`）
- 中文字体文件在 `~/.fonts/chinese-handwriting/`
- 无需网络，无需API key

## 更新日志

- **v1.0.0** (2026-04-18): 初始版本
  - 5种素材类型（timeline/compare/list/quote/cover）
  - 4种手写字体（马善政/站酷快乐/刘建毛草/芝麻行书）
  - 4种配色方案（tech/warm/ink/minimal）
