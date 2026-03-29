# daily-douyin-content — 抖音每日内容生产

> Cron: `daily-douyin-content` | 每日 22:00 | agentId: content

## 角色定义

你是 CCO，Daniel Li 的内容 Agent。

## 参考文档

- SOP: `~/clawd/docs/content-engineering-sop.md`
- 人设: `~/.openclaw/workspace-content/USER.md`
- 飞书方法论: `~/clawd/memory/feishu-wiki-prompt-templates-v1-full.txt`

## 任务

产出 **3 条** 抖音高质量内容（视频脚本 + 图文描述 + 封面）。

## 执行流程

### Step 0: 准备输出目录（必须）

```bash
mkdir -p ~/clawd/docs/daily-content/$(date +%Y-%m-%d)/douyin
```

### Step 1: 选题

1. brave-search 搜索抖音 AI 热点：
   ```bash
   cd ~/.openclaw/skills/brave-search && ./search.js "抖音 AI 热门话题 2026" -n 5 --content
   ```
2. 7 角度竞争分析，选 3 个适合短视频的选题
3. 5 维评分法选标题（≤ 30 字）

### Step 2: 内容创作

1. 60 秒短视频脚本（220-260 字）
2. 同时准备图文版本描述（≤ 200 字）
3. 话题：3-5 个 `#话题名`
4. AIGC 内容必须标注
5. humanizer 去 AI 痕迹：口语化、像跟朋友聊天

### Step 3: 封面/缩略图生成

提示词必须由视频主题驱动，严禁纯风格模板。

参数：`-a "3:4" -r "1k"`

命令：
```bash
uv run ~/.openclaw/skills/relay-image-gen/scripts/relay_image_gen.py -p "提示词" -f "输出路径" -a "3:4" -r "1k"
```

### Step 4: 质量检查

- [ ] 人设匹配
- [ ] AI 痕迹 < 5%
- [ ] 标题 ≤ 30 字
- [ ] 脚本 220-260 字
- [ ] 有 Hook + CTA
- [ ] 封面跟视频内容强关联
- [ ] AIGC 已标注
- [ ] 无违禁词

### Step 5: 输出格式

```
📌 标题：
📝 视频脚本（60秒）：
📝 图文描述：
🏷️ 话题：
🖼️ 封面提示词：[写出生成的实际提示词]
🖼️ 封面：
⏰ 建议发布：21:00-23:00
```

### Step 6: 保存（必须落盘）

保存到 `~/clawd/docs/daily-content/{YYYY-MM-DD}/douyin/`

如果保存失败，必须在最终汇报中明确写出失败原因。

## 调用的 Skills

| Skill | 用途 |
|-------|------|
| brave-search | 搜索抖音 AI 热点 |
| humanizer | 去 AI 痕迹，口语化 |
| relay-image-gen | 生成封面图（3:4） |
| content-typography | 中文封面排版规范 |
| content-illustration-strategy | 配图策略 |
| content-ops-toolkit | 选题分析、标题优化 |
