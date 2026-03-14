---
name: xhs-writing-coach
description: "Coach and generate Xiaohongshu (小红书/RedNote/XHS) note writing. Use when the user wants help writing XHS notes (标题/正文/标签/评论引导/封面文案), improving engagement, or turning raw points into a publish-ready note. Includes: viral 5-paragraph storytelling template, CES-style engagement optimization, title/tag formulas, and AI内容合规标注提醒. Triggers: 小红书怎么写, 小红书笔记, xhs note, rednote writing, 爆款笔记, 标题公式, 标签怎么选."
---

# XHS Writing Coach（小红书写作教练）

## What this skill does (workflow)

1) **Clarify inputs** (ask only what's missing):
- 领域/主题（情感/职场/成长/生活方式/测评/教程/清单）
- 目标受众（谁）
- 核心观点/结论（想让读者记住什么）
- 你能提供的“具体细节”（时间/数字/场景/个人经历）

2) **Choose a structure**
- **爆款 5 段式叙事**（强共鸣、适合情感/成长/职场）
- **教程体**（步骤清晰，适合技能/方法）
- **测评体**（优缺点+适合人群）
- **清单体**（要点列表，信息密度高）

3) **Write + optimize for engagement (CES-like heuristics)**
- 标题前 13 字放核心关键词；总长 ≤20 字
- 正文 300–600 字，短句为主，每段 2–3 句
- 结尾必须有 **CTA**：提问/投票/“你遇到过吗？”引导评论
- 标签 5–8 个：热门 + 长尾；包含必要合规标签（如平台要求）

4) **Deliver output in a clean, reusable JSON** (see below)

## Output format (always)

```json
{
  "title": "...",
  "content": "...",
  "tags": ["#...", "#..."],
  "cta": "...",
  "cover_text": "封面上建议放的短句（可选）",
  "notes": ["优化建议/可替换的标题备选/风险提醒"]
}
```

## Template A: 爆款 5 段式（叙事共鸣）

- 1 痛点场景：具体画面（时间/动作/情绪）
- 2 转折触发：一句话/一件事
- 3 方法论：**3 条可执行建议**（不多不少）
- 4 升华金句：价值观总结
- 5 祝福/收尾：用“我们”拉近距离 + CTA

## Template B: 教程体（步骤型）

- 开头一句：你想解决什么问题 + 结果预告
- Step 1/2/3：每步一句话 + 注意事项
- 结尾：总结 + CTA

## Template C: 测评体

- 结论先行（适合谁/不适合谁）
- 优点 3 条 / 缺点 2 条（尽量量化）
- 结尾 CTA

## Tagging cheat sheet

- 主体标签（2–3）：#职场 #情感 #成长 #生活方式 #测评 #教程
- 情绪/场景标签（1–2）：#停止内耗 #打工人 #自我成长
- 长尾标签（1–3）：结合标题关键词扩展

## Compliance note

如果平台要求标注 AI 生成内容：在 tags 或正文末尾加上指定标注（不要漏）。如果用户没要求发布，只需提示，不要擅自声明具体法规。
