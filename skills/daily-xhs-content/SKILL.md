---
name: daily-xhs-content
description: Use when running the daily Xiaohongshu content production cron or generating 3 小红书 content drafts with正文 and cover direction for Daniel Li.
author: Daniel Li
---

# daily-xhs-content — 小红书每日内容生产

> Cron: `daily-xhs-content` | 每日 21:00 | agentId: content

## 角色定义

你是 CCO，Daniel Li 的内容 Agent。

## 参考文档

- SOP: `~/clawd/docs/content-engineering-sop.md`
- 人设: `~/.openclaw/workspace-content/USER.md`
- 飞书方法论: `~/clawd/memory/feishu-wiki-prompt-templates-v1-full.txt`

## 任务

产出 **3 篇** 小红书高质量内容（正文 + 封面）。

## 执行流程

### Step 1: 选题

1. 调用 brave-search 搜索 AI 热点：
   ```bash
   cd ~/.openclaw/skills/brave-search && ./search.js "小红书 AI 热点 2026" -n 5 --content
   ```
   关键词：AI工具、AI创业、AI效率、ChatGPT、Claude、Cursor、AI Agent、大学生AI
2. 用 7 角度竞争分析法，选出 3 个差异化选题
3. 按 5 维评分法（点击欲望/信息密度/清晰度/差异化/正文匹配度），每个选题生成 12 个标题选 Top1

### Step 2: 内容创作

1. 小红书正文结构（400-800字，≤1000字）：
   - emoji 开头钩子（第一句决定生死）
   - 2-4 个信息点，短句为主
   - 有个人观点和真实经历（"我"的视角）
   - humanizer 去 AI 痕迹：无赋能/闭环/底层逻辑，有吐槽/不确定性/长短句交替
   - 结尾：💬互动引导 + ⭐收藏引导 + 👋关注引导
2. 标签：5-8 个 `#话题名`

### Step 3: 封面生成（⚠️ 内容驱动，严禁纯风格）

**核心原则：每张封面必须是一个视觉故事，3 秒内传达文章核心观点。**

提示词结构：`[主体场景] + [视觉隐喻/故事] + [色彩情绪] + [风格] + [格式]`

设计流程：
1. 提炼文章核心观点（一句话）
2. 把观点变成视觉隐喻（问：这个观点像什么画面？）
3. 选择色彩情绪（警告=红黑，科技=蓝白，批判=红金，教程=蓝绿，创业=金黑）
4. 补全风格和格式

❌ 严禁："深色底+强调色+抽象几何" 这种通用提示词
✅ 要求：提示词中必须包含文章主题相关的具体物体、场景和隐喻

参数：`-a "3:4" -r "1k"`

命令：
```bash
uv run ~/.openclaw/skills/relay-image-gen/scripts/relay_image_gen.py -p "提示词" -f "输出路径" -a "3:4" -r "1k"
```

### Step 4: 质量检查

- [ ] 人设匹配（直接犀利有观点）
- [ ] AI 痕迹 < 5%
- [ ] 标题 ≤ 20 字
- [ ] 正文 ≥ 100 字
- [ ] 标签 5-8 个
- [ ] 封面跟文章内容强关联（非通用背景）
- [ ] 无违禁词

### Step 5: 输出格式

每篇按此格式：

```
📌 标题：
🏷️ 标签：
📝 正文：
🖼️ 封面提示词：[写出生成的实际提示词]
🖼️ 封面：[已生成/待生成]
⏰ 建议发布：21:00-23:00
```

最后附选题评分表。

### Step 6: 保存

保存到 `~/clawd/docs/daily-content/{YYYY-MM-DD}/xhs/`

```bash
mkdir -p ~/clawd/docs/daily-content/$(date +%Y-%m-%d)/xhs
```

## 调用的 Skills

| Skill | 用途 |
|-------|------|
| brave-search | 搜索 AI 热点 |
| humanizer | 去 AI 痕迹，让文案更像人写的 |
| relay-image-gen | 生成封面图（3:4） |
| content-typography | 中文封面排版规范 |
| content-illustration-strategy | 配图策略（内容驱动） |
| content-ops-toolkit | 选题分析、标题优化方法论 |
