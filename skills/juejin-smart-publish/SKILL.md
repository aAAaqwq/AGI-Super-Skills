---
name: juejin-smart-publish
description: "掘金技术社区智能发布：Markdown编辑器全功能支持。覆盖标题(15-35字)、分类(必选)、标签(1-5个)、封面上传、摘要填写、GFM排版。Playwright自动化+API双通道发布。触发：'发掘金'、'掘金发布'、'juejin publish'、'掘金文章'、'技术博客发布'。"
---

# 掘金智能发布

## 平台入口

- **新建文章**: https://juejin.cn/editor/drafts/new
- **草稿箱**: https://juejin.cn/editor/drafts
- **登录方式**: 手机号验证码 / GitHub OAuth / 微信扫码

## 排版规则

### 文章规范

| 项 | 规则 |
|----|------|
| 编辑器 | Markdown（完整 GFM 支持） |
| 标题 | 15-35字最佳，≤50字，含核心关键词 |
| 正文 | 1,500-5,000字（技术深度文章） |
| 代码块 | 必须指定语言标识 (\`\`\`python) |
| 图片 | 拖拽/URL/剪贴板，建议≥800px |
| 表格 | GFM 表格语法 |
| 分割线 | `---` 分隔大章节 |
| 目录 | 长文章自动生成 |

### 分类（必选1个）

后端 / 前端 / Android / iOS / 人工智能 / 开发工具 / 代码人生 / 阅读

### 标签

| 项 | 规则 |
|----|------|
| 数量 | 1-5个（建议2-4个） |
| 来源 | 搜索已有 或 输入新标签按Enter |
| 策略 | 1-2热门标签(流量) + 1-2精准标签(匹配) |

### 封面 & 摘要

| 项 | 规则 |
|----|------|
| 封面 | 可选，推荐宽屏 JPG/PNG/GIF ≤5MB |
| 摘要 | 50-150字，不填则取正文前N字 |
| 摘要策略 | 含关键词，突出文章价值 |

## 内容适配模板

技术文章标准结构：

```markdown
# {标题：动词开头或数字开头}

> {一句话摘要/导言}

## 背景 / 为什么

{痛点描述，1-2段}

## 方案 / 怎么做

{核心内容，代码+图+表}

### Step 1: ...
### Step 2: ...

## 效果 / 结果

{数据对比，before/after}

## 总结

{关键收获，1-3个要点}

---

**参考链接**:
- [link1](url)
- [link2](url)
```

标题公式：
- 数字型：「5个让你写出优雅代码的Python技巧」
- 实战型：「从0到1搭建AI Agent系统——完整指南」
- 问题型：「为什么你的SQL查询这么慢？」
- 经验型：「踩了3个月的坑，我总结出这套CI/CD方案」

## 发布流程

### Playwright 自动化

```
1. 打开 juejin.cn/editor/drafts/new（检查登录态）
2. 填写标题 → input[placeholder*="标题"]
3. 在 Markdown 编辑区写入正文
4. 点击「发布」按钮打开设置面板
5. 选择分类（必选）
6. 搜索+添加标签（1-5个）
7. 上传封面（可选）
8. 填写摘要（可选）
9. 点击「确认并发布」或「保存草稿」
```

### API 通道（需认证Token）

```bash
# 保存草稿
POST /content_api/v1/article/draft/create
# Body: { title, markdown_content, category_id, tag_ids[], cover_image }

# 发布文章
POST /content_api/v1/article/publish
# Body: { draft_id }

# 上传图片
POST /content_api/v1/upload_pic
```

### 脚本用法

```bash
# Markdown 文件发布（草稿模式）
python scripts/publish.py \
  --title "文章标题" \
  --content-file article.md \
  --category "人工智能" \
  --tags "AI,Agent,OpenClaw" \
  --mode draft

# 带封面和摘要
python scripts/publish.py \
  --title "标题" \
  --content-file article.md \
  --category "前端" \
  --tags "React,TypeScript" \
  --cover cover.png \
  --abstract "50-150字摘要" \
  --mode draft

# API模式（需cookie-file）
python scripts/publish.py \
  --title "标题" \
  --content-file article.md \
  --category "后端" \
  --tags "Python,FastAPI" \
  --mode draft \
  --api --cookie-file cookies.json
```

## UI 选择器参考（Vue.js SPA，类名含hash）

| 元素 | 定位策略 | 说明 |
|------|----------|------|
| 标题输入 | `input[placeholder*="标题"]` | 标题框 |
| 编辑区 | `[class*="editor"] [contenteditable]` / `.CodeMirror` | Markdown编辑器 |
| 预览区 | `[class*="preview"]` | 右侧实时预览 |
| 发布按钮 | `button:has-text("发布")` | 打开发布面板 |
| 分类下拉 | `[class*="category"]` | 分类选择 |
| 标签输入 | `[class*="tag"] input` | 标签搜索 |
| 封面上传 | `[class*="cover"] input[type="file"]` | 封面图 |
| 摘要输入 | `[class*="abstract"] textarea` | 摘要 |
| 确认发布 | `button:has-text("确认并发布")` | 最终发布 |
| 保存草稿 | `button:has-text("保存草稿")` / 自动保存 | 草稿 |

> **注意**：掘金编辑器有自动保存草稿功能，内容输入后几秒即存。

## Markdown 快捷键

| 快捷键 | 功能 |
|--------|------|
| Ctrl/Cmd + B | 加粗 |
| Ctrl/Cmd + H | 标题 |
| Ctrl/Cmd + K | 链接 |
| Ctrl/Cmd + Shift + C | 代码块 |
| Ctrl/Cmd + Shift + I | 图片 |
| Ctrl/Cmd + Z | 撤销 |

## 发布时间建议

| 时段 | 推荐度 | 说明 |
|------|--------|------|
| 8:00-9:00 | ⭐⭐⭐ | 早通勤阅读 |
| 12:00-13:00 | ⭐⭐⭐⭐ | 午休学习 |
| 20:00-22:00 | ⭐⭐⭐⭐⭐ | 晚间深度阅读黄金档 |
| 周末 | ⭐⭐⭐ | 长文适合周末 |

## 错误处理

| 错误 | 处理 |
|------|------|
| 登录过期 | 提示手动登录，`--headless false` |
| 分类未选 | 自动选择"后端"（默认） |
| 标签搜索无结果 | 输入后按Enter创建新标签 |
| 图片上传失败 | 重试3次，回退到URL引用 |
| Markdown渲染异常 | 检查语法，移除不支持的扩展 |
| 发布频率限制 | 建议每天≤3篇，间隔≥30分钟 |

## SEO 优化要点

- 标题含核心关键词（前15字最重要）
- 正文前100字包含关键词
- 标签选择热门+精准组合
- 摘要包含核心关键词
- 内链自己的其他文章
- 参与官方活动增加曝光权重

## 发布前检查清单

- [ ] 标题 15-35字，含关键词
- [ ] 分类已选（必选项）
- [ ] 标签 2-4个，热门+精准
- [ ] 代码块均有语言标识
- [ ] 图片清晰 ≥800px
- [ ] 正文无错别字/格式错误
- [ ] 摘要 50-150字（不填会自动截取）
- [ ] 非搬运内容，声明原创

## 文件结构

```
juejin-smart-publish/
├── SKILL.md
├── scripts/
│   └── publish.py          # Playwright + API 双通道发布
├── references/
│   └── api-spec.md         # 掘金 API 文档
└── templates/
    ├── tech-tutorial.md     # 技术教程模板
    ├── project-showcase.md  # 开源项目展示模板
    └── experience-share.md  # 经验分享模板
```
