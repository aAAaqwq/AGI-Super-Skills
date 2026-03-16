# content-distributor

多平台内容分发 Skill — Markdown 一篇文章，自动转换为各平台适配格式并发布。

## 功能

### 1. Markdown → 多平台格式转换
- **微信公众号**: CSS 全内联 HTML（公众号编辑器不支持 `<style>` 标签）
- **知乎/CSDN/掘金/简书**: 标准 Markdown（编辑器原生支持）
- **小红书**: 纯文本 + emoji 排版（无 Markdown 支持）
- **今日头条/百家号**: 富文本 HTML（CSS 内联）
- **Twitter/X**: 自动拆分为 Thread（每条 ≤280 字符）

### 2. 排版模板
4 套预设模板，适配不同内容类型：

| 模板 | 风格 | 适合场景 |
|------|------|----------|
| `tech` | 科技紫，Catppuccin 代码高亮 | 技术博客、AI/编程 |
| `minimal` | 黑白简约，GitHub 风格 | 随笔、观点文 |
| `business` | 商务蓝，数据框 | 行业报告、市场分析 |
| `dark-tech` | 暗色 GitHub，绿色强调 | 深度技术、Hacker 风格 |

### 3. 发布方式
- **微信公众号**: 官方 API（自动上传素材、创建草稿/发布）
- **其他平台**: 生成 Playwright 操作指令，由 Agent 通过 browser 工具执行

### 4. 登录态管理
- 复用 auth-manager skill 的 browser profile
- 各平台 Cookie 持久化
- 登录过期自动检测

## 使用方法

### 格式转换

```bash
# 转为公众号 HTML
tsx scripts/convert.ts article.md --template tech --platform wechat

# 转为小红书纯文本
tsx scripts/convert.ts article.md --platform xhs

# 全平台转换
tsx scripts/convert.ts article.md --all --output ./dist

# 指定模板
tsx scripts/convert.ts article.md --template business --platform toutiao
```

### 发布

```bash
# 微信公众号发布 (创建草稿)
tsx scripts/publish.ts article.md --platforms wechat --template tech

# 知乎 + 掘金 (生成操作计划)
tsx scripts/publish.ts article.md --platforms zhihu,juejin --dry-run

# 全平台发布
tsx scripts/publish.ts article.md --all --tags "AI,技术" --cover cover.png
```

### Agent 调用

Agent 可以直接调用 convert/publish 函数：

```typescript
import { convert } from './scripts/convert.js';

const results = convert({
  input: 'article.md',
  template: 'tech',
  platform: 'wechat',
});
// results[0].content → CSS 内联的 HTML
```

## 环境变量

| 变量 | 说明 | 必须 |
|------|------|------|
| `WECHAT_APPID` | 微信公众号 AppID | 微信发布时 |
| `WECHAT_APPSECRET` | 微信公众号 AppSecret | 微信发布时 |

## 平台优先级

| 优先级 | 平台 | 发布方式 |
|--------|------|----------|
| P0 | 微信公众号 | 官方 API |
| P0 | 知乎 | Playwright |
| P1 | CSDN | Playwright / API |
| P1 | 掘金 | Playwright |
| P1 | 简书 | Playwright |
| P2 | 小红书 | Playwright |
| P2 | 今日头条 | Playwright |
| P2 | 百家号 | Playwright |
| P3 | B站专栏 | Playwright |
| P3 | Twitter/X | Playwright |

## 文件结构

```
content-distributor/
├── SKILL.md              # 本文件
├── package.json
├── scripts/
│   ├── convert.ts        # Markdown → 多平台格式转换器
│   ├── publish.ts        # 多平台发布编排器
│   ├── demo.ts           # 验证 demo
│   └── platforms/
│       ├── wechat.ts     # 微信公众号 API 发布器
│       └── browser-publish.ts  # Playwright 浏览器发布器
├── templates/
│   ├── tech.css          # 科技风
│   ├── minimal.css       # 简约风
│   ├── business.css      # 商务风
│   └── dark-tech.css     # 深色科技风
└── output/               # 转换输出目录
```

## 依赖

- `markdown-it` — Markdown 解析
- `juice` — CSS 内联（公众号必须）
- `tsx` — TypeScript 直接运行

## 注意事项

1. **微信公众号图片**: 文章内图片必须上传到公众号素材库，外链会被屏蔽
2. **小红书限制**: 无 Markdown/HTML 支持，只能纯文本 + emoji
3. **知乎**: 编辑器支持 Markdown，但部分高级语法（如表格）可能需要手动调整
4. **代码块**: 公众号不支持代码高亮 class，通过 CSS 内联模拟
5. **模板选择**: 公众号/今日头条/百家号使用 CSS 模板；知乎/CSDN/掘金直接用 Markdown 无模板效果
