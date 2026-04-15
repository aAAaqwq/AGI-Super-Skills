---
name: influencer-analyzer
description: 分析抖音/小红书/B站博主的主页、内容风格、爆款规律。可根据链接、博主名、主题三种方式触发。输出结构化的博主画像和内容风格报告，为内容创作者提供可复制的对标参考。触发词：分析博主、分析网红、对标博主、博主风格、起号分析、博主推荐。
version: 1.1.0
author: ives-cco
tags: [influencer, douyin, xiaohongshu, bilibili, b站, 抖音, 小红书, 起号, 对标, content-creator]
---

# Influencer Analyzer — 博主起号分析器

> 分析抖音/小红书/B站博主的主页风格、内容规律、爆款元素，为内容创作者提供可复制的对标参考。

## 何时用

- 用户说"分析这个博主"并提供链接
- 用户说"帮我找几个对标博主"并说明领域
- 用户说"我想做X领域的账号，参考一下"
- 内容创作前需要学习对标账号的风格
- 需要了解某平台的热门内容趋势

## 三种触发方式

### 方式一：链接分析（最精准）

提供博主主页链接或视频链接：

```
请分析这个博主：
https://www.douyin.com/user/MS4wLjABAAAAxxx
https://www.xiaohongshu.com/user/profile/xxx
https://space.bilibili.com/xxx
```

### 方式二：名字搜索

提供博主名字：

```
请搜索并分析"博主名字"这个抖音博主
帮我找小红书上做AI内容比较火的博主
B站上有哪些做量化交易不错的UP主
```

### 方式三：主题推荐

描述想做的方向：

```
我打算做AI创业方向的内容，帮我推荐几个对标博主
大学生AI学习这个主题，有什么值得参考的博主
```

---

## 输入

```yaml
输入:
  mode: link | search | recommend   # 三种模式
  platform: douyin | xiaohongshu | bilibili | all
  identifier: string                  # 链接/名字/主题
  top_n: 5                          # 推荐模式时返回的数量
```

---

## 输出

```yaml
输出:
  status: ok | error
  platform: string
  blogger:
    name: string
    avatar: string (url)
    followers: string          # "10.2万粉"
    following: string
    likes: string              # 总获赞
    bio: string
    profile_url: string
  content_patterns:
    - category: string         # "AI工具测评"
      frequency: string        # "每周3更"
      style: string            # "短平快/深度/教程"
      avg_duration: string     # "30秒/5分钟"
      hook_style: string       # 开头钩子类型
  recent_top_videos:
    - title: string
      likes: string
      views: string
      date: string
      url: string
  style_analysis:
    visual_style: string        # 画面风格描述
    color_palette: string      # 主色调
    editing_rhythm: string     # 剪辑节奏
    voice_style: string        # 配音/字幕风格
    persona: string            # 博主人设定位
  takeaways:
    - 可复制的元素
    - 爆款规律
    - 差异化点
  recommendations:
    - 针对创作者的差异化建议
```

---

## 工具链

| 工具 | 用途 |
|------|------|
| browser | 抓取主页/视频页面 |
| yt-dlp | 下载视频/提取信息 |
| ffmpeg | 关键帧提取 |
| image | AI分析封面风格 |

---

## 平台特点速查

| 平台 | 主页URL格式 | 关键指标 | 内容形式 |
|------|------------|---------|---------|
| 抖音 | douyin.com/user/XXX | 粉丝/点赞/收藏 | 15-60秒竖视频 |
| 小红书 | xiaohongshu.com/user/profile/XXX | 粉丝/点赞/收藏 | 图文/短视频 |
| B站 | space.bilibili.com/XXX | 粉丝/播放/点赞 | 1-30分钟横视频 |

---

## 工作流程

### Link 模式（URL分析）

```
解析URL → 判断平台 → 打开主页
→ 抓取博主信息（头像/粉丝/简介）
→ 抓取最近10-20个视频/帖子
→ 分析封面风格
→ AI综合分析
→ 输出报告
```

### Search 模式（名字搜索）

```
拼接搜索URL → 搜索结果页
→ 找到目标博主
→ 切换到Link模式继续
```

### Recommend 模式（主题推荐）

```
按平台搜索主题关键词
→ 排序找出粉丝多/点赞高的博主
→ 列出Top N供选择
→ 用户指定后切换到Link模式
```

---

## 关键 Selector（Browser 抓取）

### 抖音
```
博主名:   .author-title .name
粉丝数:   .author-follow .count
简介:     .author-description
视频列表: .video-card .cover
点赞:     .video-card .like-count
```

### 小红书
```
博主名:   .user-info .name
粉丝数:   .user-info .fans
简介:     .user-info .desc
笔记列表: .note-item .cover
点赞:     .note-item .like
```

### B站
```
博主名:   .h-pinoco .name
粉丝数:   .n-num .fans
播放量:   .n-num .view
视频列表: .video-card .cover
```

---

## 封面风格分析维度

| 维度 | 说明 |
|------|------|
| 画面构图 | 远景/特写/第一人称/屏幕录制 |
| 主色调 | 冷色/暖色/高饱和/低饱和 |
| 文字封面 | 有字/无字/大字/小字 |
| 人物出场 | 真人出镜/动画/屏幕/无人物 |
| 情绪调性 | 专业/轻松/焦虑/治愈 |

---

## 分析报告模板

```markdown
# 🎯 博主分析报告

**博主**: [名字]
**平台**: [抖音/小红书/B站]
**链接**: [主页链接]
**粉丝**: [X万]
**总赞**: [X万]

---

## 📊 基础画像

- **内容定位**:
- **目标人群**:
- **博主人设**:
- **更新频率**:

---

## 🎬 最近爆款

| 标题 | 点赞 | 播放/阅读 | 日期 |
|------|------|---------|------|
| ... | ... | ... | ... |

---

## 🖼️ 封面风格分析

- **画面构图**: [描述]
- **主色调**: [描述]
- **文字处理**: [描述]
- **人物出场**: [描述]

---

## 🎙️ 内容风格

- **视频节奏**: [描述]
- **配音/字幕**: [描述]
- **开头钩子**: [描述]
- **互动设计**: [描述]

---

## 💡 可复制元素

1. [元素1]
2. [元素2]
3. [元素3]

---

## 🎯 对创作者的建议

[结合目标账号定位的差异化建议，包括：可复制的元素、需避免的坑、差异化方向]
```

---

## 依赖

```
yt-dlp (pip install yt-dlp)
ffmpeg (视频处理)
OpenClaw browser (抓取页面)
```

---

## 示例对话

**User**: 分析这个抖音博主 https://www.douyin.com/user/MS4wLjABAAAAxxx

**Assistant**: 正在分析博主...
→ 抓取主页数据 ✓
→ 分析最近10个视频 ✓
→ 提取封面风格 ✓
→ AI综合分析 ✓

**输出**: [完整博主分析报告]

---

*Author: Ives·CCO | v1.0.0 | 2026-04-14*
