---
name: weibo-hot-trend
description: 获取微博热搜榜数据，返回热搜标题、热度值和跳转链接。当用户需要查看微博热搜、微博热点、微博热榜时使用此技能。支持自定义获取条数（默认50条）。
---

# 微博热搜榜

## 获取热搜

```bash
# 默认获取50条
node scripts/weibo.js

# 获取前N条
node scripts/weibo.js 20
```

## 数据来源

微博网页端公开接口 `weibo.com/ajax/side/hotSearch`

## 注意事项

- 访问频繁可能触发风控，建议间隔 ≥30 分钟
- 热度单位为万，label_name 为标签（沸、新、热等）
