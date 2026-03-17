# AGENTS.md - Workspace

## Every Session
1. Read `SOUL.md` — who you are
2. Read `USER.md` — who you're helping
3. Read `memory/YYYY-MM-DD.md` (today + yesterday)
4. **Main session only**: Also read `MEMORY.md`

## Memory
- **Daily**: `memory/YYYY-MM-DD.md` — raw logs
- **Long-term**: `MEMORY.md` — curated (main session only, never leak to groups)
- **Write it down** — "mental notes" don't survive restarts

## Safety
- Don't exfiltrate private data
- `trash` > `rm`
- Ask before external actions (emails, tweets, public posts)

## Group Chats
- Respond when mentioned or can add real value
- Stay silent (`HEARTBEAT_OK`) for casual banter
- Don't dominate; quality > quantity

## Heartbeats
- Use productively: check emails, calendar, weather (rotate 2-4x/day)
- Track in `memory/heartbeat-state.json`
- Stay quiet 23:00-08:00 unless urgent
- Periodically review daily files → update MEMORY.md

## 知识库 / Memory Router（强制）

- 回答配置/流程/历史/怎么做/项目状态类问题前，**必须先检索 QMD**：
  - `qmd query "<问题>"` — 默认混合搜索（BM25 + 向量 + rerank）
  - 精确定位用 `qmd search "<关键词>"` 或 `qmd query -c <collection> "<问题>"`
  - 查看文件用 `qmd get path/file.md:行号 -l 30`
  - 批量取文件用 `qmd multi-get "pattern"`
  - 浏览索引内容用 `qmd ls <collection>`
- Collections: `clawd-memory`, `daily-memory`, `team`, `openclaw-config`, `projects`, `skills`, `reports`
- 涉及待办/决策/人/日期 → 还要查 `~/clawd/memory/YYYY-MM-DD.md` 与 `~/clawd/MEMORY.md`
- 输出至少引用 1-3 个来源（文件路径或 qmd:// URI）
- Skill 详情: `~/clawd/skills/memory-router/SKILL.md`

## Heartbeat vs Cron
- **Heartbeat**: batch checks, needs conversation context, timing can drift
- **Cron**: exact timing, isolated session, one-shot reminders

## 短视频制作完整流程

### 创作类型分类
1. **剧情类** - 有完整故事线的短视频
2. **教程类** - 教学、分享技巧
3. **产品展示类** - 产品介绍、功能演示
4. **错位玩法类** ⭐ NEW - 视觉错觉、创意拍摄
5. **抽象视频类** - 荒诞感、反转、脑洞

### 错位玩法创作流程

**第一步：选择错位类型**
- 视角错位（Forced Perspective）
- 时间错位（Time Shift）
- 空间错位（Space Warp）
- 大小错位（Scale Illusion）
- 逻辑错位（抽象/荒诞）

**第二步：使用策划模板**
```markdown
【错位视频策划卡】
类型：[选择类型]
场景：地点/时间/光线
道具：清单
人物：人数/服装/动作
机位：角度/距离/焦距
剪辑：转场/特效/音乐
预期效果：
```

**第三步：拍摄执行**
- 按照机位设置清单执行
- 使用道具清单准备
- 多拍几条备用

**第四步：剪辑制作**
- 找到最佳转场点
- 硬切或叠化（0.5秒内）
- 调整颜色和曝光
- 添加音效和音乐

**第五步：AI辅助**（可选）
- `relay-video-gen`：生成抽象转场素材
- `relay-image-gen`：生成背景图片
- AI剪辑工具：自动识别转场点

### 快速上手模板
1. **手掌托物** - 难度⭐
2. **鞋子踩人** - 难度⭐⭐
3. **饮料瓶吸入** - 难度⭐⭐
4. **无限楼梯** - 难度⭐⭐⭐
5. **手机人物互动** - 难度⭐⭐⭐

### 详细资料
- 完整技巧文档：`~/clawd/content/research/short-video-misalignment-techniques.md`
- 包含：类型分类、爆款案例、拍摄SOP、抽象视频指南、10个创意模板
