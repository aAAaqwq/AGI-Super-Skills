# wechat-pipeline · 公众号流水线

> 📝→🎨→📤 写作 → 封面 → 发布 · 三段式自动编排 · 每段断点检查

## 一句话

说"写一篇公众号文章"，AI 自动走完 写文章 → 生成封面 → 推送草稿 全流程，每段等你拍板。

## 三段流水线

```
Stage 1: 内容创作 (wechat-article-writer)
  搜索资料 → 撰写文章 → 生成5个爆款标题 → 排版建议
  🔴 断点：展示文章+标题，等你选

Stage 2: 封面生成 (code-to-image)
  选模板 → 设计HTML → 渲染PNG
  🔴 断点：展示封面图，等你确认

Stage 3: 发布推送 (md2wechat)
  校验 → 渲染HTML → 上传封面 → 门禁审查 → create_draft
  🔴 断点：展示标题/作者/封面/摘要，等你回复"发"
```

## 触发词

`公众号创作` `写公众号文章` `公众号发布` `公众号流水线` `发公众号`

## 核心规则

- ❌ 不跳段、不并行、不自动进下一段
- ❌ 不用 AI 生图做封面（用代码渲染）
- ❌ 不用 test-draft（用 create_draft）
- ✅ 每段等用户确认
- ✅ 封面必须跟文章主题直连
- ✅ 遇错截图存档

## 安装

```bash
clawhub install wechat-pipeline
```

## 依赖

- `wechat-article-writer` skill
- `code-to-image` skill
- `md2wechat` skill + CLI
- `WECHAT_APPID` / `WECHAT_SECRET` 环境变量
