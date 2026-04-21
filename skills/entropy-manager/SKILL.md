---
name: entropy-manager
description: Entropy scanner for codebases — detect disorder and suggest cleanup actions
---

# 熵管理 Skill (Entropy Manager)

> **核心信念**：AI 团队每行代码都在增加系统的混乱度。不主动减熵，系统会自然腐败。
> 灵感来源：热力学第二定律 × 软件工程 hygiene × Daniel "秩序规则" 宪章

## 触发条件
- 手动触发：`熵扫描` / `entropy scan` / `减熵` / `清理`
- 定期触发：建议每周一次 cron（`entropy-weekly-scan`）
- 重大变更后：项目上线、大规模重构后

## 熵的 6 大分类

| # | 类别 | 代号 | 说明 | 检测方式 |
|---|------|------|------|----------|
| 1 | **文档熵** | `DOC` | 过时文档、失效链接、空 TODO、错误日期 | 日期检查、TODO 统计、断链检测 |
| 2 | **命名熵** | `NAME` | 非 kebab-case/snake_case 文件、命名不一致 | 文件名模式匹配 |
| 3 | **代码熵** | `CODE` | 死代码、注释掉的块、未使用的 import、console.log 遗留 | AST/grep 扫描 |
| 4 | **配置熵** | `CONF` | 过时配置、未使用的 env var、孤立的 agent 配置 | 配置文件交叉验证 |
| 5 | **文件熵** | `FILE` | 错位文件、tmp 残留、重复文件、空 .gitkeep | 目录结构验证 |
| 6 | **依赖熵** | `DEP` | 未使用依赖、过时版本、安全漏洞 | package.json/requirements.txt 扫描 |

## 严重度分级

| 级别 | 定义 | 示例 | 处理时限 |
|------|------|------|----------|
| 🔴 **Critical** | 安全/功能影响 | 硬编码密钥、破损的入口文件 | 立即 |
| 🟡 **Warning** | 维护性影响 | 死代码>50行、过时 TODO>10个 | 本周 |
| 🟢 **Info** | 美观/一致性 | 命名不统一、空文件 | 下次顺手修 |

## 执行流程

### Phase 1: 扫描诊断
```bash
bash ~/clawd/skills/entropy-manager/scripts/entropy-scan.sh [target_dir]
```
输出：`~/clawd/tmp/entropy-report-YYYY-MM-DD.md`

### Phase 2: 报告生成
扫描结果汇总为：
- 总熵值评分（0-100，100=完美）
- 各分类得分
- Top 10 高熵文件
- 自动可修复项 vs 需人工确认项

### Phase 3: 自动修复（需确认）
对 🟢 级别问题自动修复（需 CEO 确认后执行）：
- 重命名文件到规范格式
- 删除空 .gitkeep（目录有内容时）
- 清理 tmp/ 超过 7 天的文件
- 移除注释代码块（>10行连续注释代码）

### Phase 4: 记录追踪
- 每次扫描结果追加到 `~/clawd/tmp/entropy-history.jsonl`
- 趋势：熵值是否在下降？
- 对比上次：新增了多少熵？

## 报告格式

```markdown
# 熵扫描报告 — YYYY-MM-DD

## 📊 总评分: 72/100 (较上次 +5)

| 分类 | 得分 | 问题数 | Critical | Warning | Info |
|------|------|--------|----------|---------|------|
| DOC  | 65   | 12     | 0        | 4       | 8    |
| NAME | 80   | 5      | 0        | 1       | 4    |
| CODE | 70   | 8      | 1        | 3       | 4    |
| CONF | 85   | 3      | 0        | 1       | 2    |
| FILE | 60   | 10     | 0        | 5       | 5    |
| DEP  | 75   | 4      | 0        | 2       | 2    |

## 🔴 Critical (立即处理)
1. [CODE] ~/clawd/projects/xxx/config.py:5 — 硬编码 API key

## 🟡 Warning (本周处理)
1. [DOC] ~/clawd/MEMORY.md — 3 个 TODO 超过 30 天未更新
2. [FILE] ~/clawd/tmp/ — 15 个文件超过 7 天

## 🟢 Info (下次顺手修)
1. [NAME] ~/clawd/scripts/api_health_check.py → 建议 api-health-check.py

## 📈 趋势
- 上次扫描: 67/100 (YYYY-MM-DD)
- 变化: +5
- 熵增最快: FILE (+8 问题)
- 熵减最快: CODE (-3 问题)
```

## 扫描范围

### 默认范围
```
~/clawd/              # 工作主目录（排除 .git, node_modules, venv）
~/.openclaw/agents/   # Agent 配置
~/.openclaw/skills/   # 全局 Skills
```

### 项目级范围
```bash
entropy-scan.sh ~/clawd/projects/blue-blood-elite/
```

## 与宪章的关系

**秩序规则第 8 条 — 熵管理秩序**：
> 系统自然趋向混乱。AI 团队每行代码都在增加熵值。不主动减熵，等于慢性自杀。
> 每周至少一次全系统熵扫描，Critical 级别问题不过夜。

## 依赖
- bash 4+
- Python 3.11+（用于复杂分析脚本）
- git（用于历史对比）

## 文件结构
```
entropy-manager/
├── SKILL.md              # 本文件
├── scripts/
│   ├── entropy-scan.sh   # 主扫描脚本
│   └── entropy-fix.sh    # 自动修复脚本（需确认）
└── README.md
```
