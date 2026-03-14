---
name: xhs-content-creator
description: "Generate Xiaohongshu (小红书/RED) content optimized for the platform's CES algorithm. Use when: (1) creating xiaohongshu/小红书 posts, (2) writing Chinese social media content for RED, (3) generating content with xiaohongshu SEO optimization, (4) planning xiaohongshu content calendars. Supports diary-style, tutorial, review, and list formats with proper AI content labeling."
---

# 小红书内容创作 Skill

## 核心算法规则（CES评分）
- 关注(8分) > 转发/评论(4分) > 点赞/收藏(1分)
- 初始曝光池 100-500，2小时内点击率≥8% + 互动率≥5% 才进下一级
- **必须标注 #AI生成内容**（2026年1月起强制，否则限流）

## 内容格式要求
- 标题：20字以内，前13字含核心关键词（搜索权重40%）
- 正文：300-600字，短句为主，每段2-3句
- 封面：3:4竖图
- 标签：5-8个，混合热门+长尾

## 写作风格模板

### 日记体（推荐，互动率最高）
- 第一人称，有情绪起伏
- 具体细节（时间、数字、场景）
- 结尾留悬念或提问引导评论
- 参考：小云AI求生记风格

### 教程体
- 标题含"教程/方法/步骤"
- 分步骤，每步配图
- 结尾"关注我获取更多"

### 测评体
- 真实使用体验
- 优缺点对比
- 适合人群推荐

## 输出格式

生成内容时按以下 JSON 结构输出：

```json
{
  "title": "标题（20字内，前13字含关键词）",
  "content": "正文（300-600字）",
  "tags": ["#标签1", "#标签2", "#AI生成内容"],
  "cover_prompt": "封面图描述（用于AI生成）",
  "best_time": "建议发布时间",
  "cta": "引导互动的结尾语"
}
```

## 发布时间建议
- 早高峰：7:00-9:00
- 午休：12:00-13:30
- 晚高峰：17:30-21:00
- 最佳：周二/四/六 晚19:00-20:00

## 安全规则
- 每天最多2篇，间隔≥2小时
- 必须标注 #AI生成内容
- 不发违规内容（医疗建议、金融推荐、政治敏感）
- 建议人工审核后再发布
