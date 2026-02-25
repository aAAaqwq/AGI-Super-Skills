---
name: skill-search
description: 从GitHub和SkillsMP等官方网站搜索符合用户描述的优质skill，供用户选择，然后自动克隆并安装相应skill到全局~/.claude/skills/目录。当用户需要搜索或安装新skill时触发此技能。
---

# Skill 搜索与安装助手（v2）

从多个渠道搜索、筛选、安装 Claude Code Skills。**优中择优，高 stars 优先。**

## 搜索策略（按优先级执行）

### 第一层：精选聚合仓库（本地缓存优先）

先从这些顶级仓库搜索，覆盖面最广、质量最高：

| 仓库 | ⭐ Stars | 说明 | 搜索方式 |
|------|---------|------|----------|
| `hesreallyhim/awesome-claude-code` | 24.8K | 官方级精选合集 | clone → find SKILL.md |
| `sickn33/antigravity-awesome-skills` | 14.7K | 900+ Skills 大全 | clone → find SKILL.md |
| `VoltAgent/awesome-agent-skills` | 7.8K | 380+ 社区 skills | clone → find SKILL.md |
| `VoltAgent/awesome-claude-code-subagents` | 11.2K | 100+ 子agent | clone → find SKILL.md |
| `travisvn/awesome-claude-skills` | 7.6K | 精选资源列表 | README 提取链接 |
| `jeremylongshore/claude-code-plugins-plus-skills` | 1.4K | 分类插件+skills | clone → find SKILL.md |
| `heilcheng/awesome-agent-skills` | 2.3K | 多agent工具教程 | README 提取链接 |
| `rohitg00/awesome-claude-code-toolkit` | 545 | 135 agents + 35 skills | clone → find SKILL.md |
| `menkesu/awesome-pm-skills` | 185 | 28个PM技能 | clone → find SKILL.md |
| `ramihassen95/claude-builder-template` | — | TDD/subagent/debug | clone → find SKILL.md |
| `aAAaqwq/AGI-Super-Skills` | — | 自有 skill 仓库（首选） | 直接引用 |
| `VoltAgent/awesome-openclaw-skills` | — | OpenClaw 专属 skills | clone → find SKILL.md |
| `VoltAgent/awesome-claude-code-subagents` | 11.2K | 100+ 子agent（可分配给团队agent） | clone → find SKILL.md |

**缓存机制**：首次搜索时 clone 到 `/tmp/skill-cache/`，后续搜索复用（同一会话内）。

```bash
CACHE="/tmp/skill-cache"
mkdir -p "$CACHE"
# 只在不存在时 clone
[ -d "$CACHE/awesome-claude-code" ] || git clone --depth 1 https://github.com/hesreallyhim/awesome-claude-code.git "$CACHE/awesome-claude-code"
# 搜索
find "$CACHE" -name "SKILL.md" | xargs grep -li "{关键词}" 2>/dev/null
```

### 第二层：网页搜索平台

当聚合仓库未找到时，搜索这些 skill 市场网站：

| 平台 | URL | 搜索方式 |
|------|-----|----------|
| **SkillsMP** | https://skillsmp.com | web_fetch 抓取搜索页 |
| **ClawdHub** | https://clawhub.com | web_fetch 抓取 |
| **SkillKit** | https://skillkit.dev (如存在) | web_fetch |

```bash
# 示例：搜索 SkillsMP
web_fetch("https://skillsmp.com/search?q={关键词}")
```

### 第三层：GitHub 全局搜索

聚合仓库和网站都没有时，GitHub API 兜底：

```bash
# 搜索关键词组合（按效果排序）
"claude skill {关键词}" sort:stars
"SKILL.md {关键词}" sort:stars  
"{关键词} agent skill" sort:stars
```

**筛选规则（严格执行）：**
- ⭐ > 100 优先展示
- ⭐ > 10 次选
- ⭐ < 10 仅在无更好选择时展示
- 必须包含 SKILL.md 文件
- 同类 skill 只展示最高星的 1-2 个

## 结果展示

每个结果包含：

```
📦 {技能名称}
📝 {一句话描述}
⭐ {Stars} | 🔗 {仓库URL}
📂 {SKILL.md 路径}
```

**排序**：⭐ Stars 降序，同分看最近更新时间。

展示 Top 5-10 个结果，让用户选择。

## 安装流程

1. **去重检查**：`ls ~/.claude/skills/ ~/clawd/skills/` 是否已存在
2. **clone + 定位**：`git clone --depth 1` → `find -name SKILL.md`
3. **双路径安装**：
   ```bash
   cp -r {skill_dir} ~/.claude/skills/{name}/     # 全局
   cp -r {skill_dir} ~/clawd/skills/{name}/       # workspace（团队共享）
   ```
4. **清理**：`rm -rf {temp_dir}`
5. **确认**：输出安装路径 + 提示重启生效

## 依赖处理

- Python → 提示 `pip install`
- Node.js → 提示 `npm install`
- 需要 API key → 明确告知

## 搜索技巧

| 用户说 | 搜索关键词 |
|--------|-----------|
| "找个写代码的" | coding, development, code-generation |
| "SEO相关" | seo, content-writing, programmatic-seo |
| "UI设计" | ui-ux, frontend-design, web-design |
| "自动化XX平台" | {platform}-automation |
| "提高编程能力" | tdd, code-review, debugging, subagent, coding-agent |

## 错误处理

- GitHub rate limit → 切换到 web_fetch 搜索
- clone 失败 → 检查网络，重试一次
- SKILL.md 无效 → 跳过，标记 ⚠️
- 无结果 → 建议用 skillforge 自动生成
