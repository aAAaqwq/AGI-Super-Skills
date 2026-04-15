# 跨境电商竞品分析Skill

<div align="center">

**一款强大的多平台电商竞品分析 Claude Code Skill**

**Created By Buluslan**

**想了解更多最新AI行业动态，AI+电商/广告的行业实践方法，人与AI如何协作共生的思考，请关注公众号：【新西楼】**

![qrcode_for_gh_e3b954bd3859_258](https://github.com/user-attachments/assets/d8f068d9-c4f8-46c7-914c-fbcab5d52f2a)


[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Claude Code](https://img.shields.io/badge/Claude_Code-Skill-blue)](https://claude.ai/code)

</div>

## 概述

这是一个 [Claude Code Skill](https://claude.ai/code)，可以自动分析多个电商平台（Amazon、Temu、Shopee等）的竞品数据，并生成全面的 AI 分析报告。

### 核心功能

- **多平台支持**：Amazon（已启用）、Temu 和 Shopee（计划中）
- **批量处理**：单次请求分析多个产品
- **AI 驱动分析**：四维度分析框架：
  - 文案策略与关键词分析
  - 视觉资产设计方法论
  - 客户评论情感分析
  - 市场定位与竞争情报
- **双格式输出**：
  - Google Sheets（结构化数据）
  - Markdown 报告（详细分析）
- **错误隔离**：单个产品失败不会中断批量处理

## 什么是 Claude Code Skill？

**技能**是 Claude Code AI 的"使用手册"。它通过提供结构化的提示词、脚本和配置，让 Claude 能够执行专业任务。

使用本技能，你只需要说：
> "分析这些 Amazon 产品：B0C4YT8S6H, B08N5WRQ1Y, B0CLFH7CCV"

Claude 就会：
1. 从 Amazon 提取产品数据
2. 生成 AI 驱动的分析报告，主要包括：
- 基础信息：商品标题、价格、评分情况等。
- 内容分析：listing文案的方法论总结，高频卖点和内容亮点，TOP10高频关键词分析。
- 视觉分析：主图和A+的设计方法论总结，视觉动线拆解。
- 评论分析：统计评论数量和星级分布，并详细分析最新的评论内容，分别总结3条产品优势和缺陷，输出改进建议。
- 其他分析：包括asin排名和市场动态，Q&A中的高频问题分析，以及整体的分析总结。
4. 将结果输出到 Google Sheets 和 Markdown 文件

## 系统要求

### 必需的 API 密钥

| 服务 | 用途 | 费用 |
|---------|---------|------|
| **Olostep API** | 网页数据抓取 | 1000 次免费请求/月，之后 $0.002/次 |
| **Google Gemini API** | AI 分析 | ~$0.001/产品 |

### 可选的 API 密钥

| 服务 | 用途 |
|---------|---------|
| **Google Sheets API** | 将结果导出到 Google Sheets |

## 安装

### 步骤 1：安装技能

```bash
# 使用 npx skills（推荐）
npx skills add buluslan/ecommerce-competitor-analyzer

# 或手动克隆
git clone https://github.com/buluslan/ecommerce-competitor-analyzer.git
cp -r ecommerce-competitor-analyzer ~/.claude/skills/main-mode-skills/ecommerce-competitor-analyzer.skill
```

### 步骤 2：配置环境变量

```bash
# 复制示例环境文件
cd ~/.claude/skills/main-mode-skills/ecommerce-competitor-analyzer.skill
cp .env.example .env

# 编辑 .env 并添加你的 API 密钥
nano .env
```

添加你的 API 密钥：
```bash
OLOSTEP_API_KEY=your_olostep_api_key_here
GEMINI_API_KEY=your_gemini_api_key_here
GOOGLE_SHEETS_ID=your_google_sheets_id_here
```

### 步骤 3：验证安装

```bash
# 列出已安装的技能
~/.claude/list-skills.sh
```

## 使用方法

### 基础用法（单个产品）

在 Claude Code 中，只需说：

```
分析这个 Amazon 产品：B0C4YT8S6H
```

Claude 会：
1. 从 Amazon 提取产品数据
2. 生成全面的分析报告
3. 保存到 Google Sheets（1行）+ Markdown 文件

### 批量分析（多个产品）

```
分析这些 Amazon 产品：
B0C4YT8S6H
B08N5WRQ1Y
B0CLFH7CCV
```

或使用 URL：

```
分析这些产品：
https://amazon.com/dp/B0C4YT8S6H
https://amazon.com/dp/B08N5WRQ1Y
```

### 输出格式

#### 格式 1：Google Sheets（结构化数据）

| ASIN | 产品标题 | 价格 | 评分 | 文案分析 | 视觉分析 | 评论分析 | 市场分析 |
|------|--------------|-------|--------|---------------------|-----------------|-----------------|-----------------|
| B0C4YT8S6H | Samsung Galaxy Tab A9+ | $159.99 | 4.4 | [300字摘要] | [300字摘要] | [300字摘要] | [300字摘要] |

#### 格式 2：Markdown 报告（详细分析）

```markdown
# Amazon 竞品分析报告

## 产品 1：B0C4YT8S6H

### 基本信息
- 标题：Samsung Galaxy Tab A9+ Plus 11" 64GB Android Tablet
- 价格：$159.99
- 评分：4.4/5

### 文案策略与关键词分析
[完整分析内容...]

### 视觉资产设计方法论
[完整分析内容...]

### 客户评论分析
[完整分析内容...]

### 市场定位与竞争情报
[完整分析内容...]
```

## 配置

### Google Sheets 设置（可选）

如果要将结果导出到 Google Sheets：

1. **创建 Google Cloud 项目**
   - 访问 [Google Cloud Console](https://console.cloud.google.com/)
   - 创建新项目

2. **启用 Google Sheets API**
   - 导航到"API 和服务" > "库"
   - 搜索"Google Sheets API"
   - 点击"启用"

3. **创建 OAuth2 凭证**
   - 导航到"API 和服务" > "凭据"
   - 点击"创建凭据" > "OAuth 客户端 ID"
   - 应用类型："桌面应用"
   - 下载 JSON 凭证文件

4. **配置技能**
   - 复制 JSON 文件内容
   - 粘贴到 `.env` 中的 `GOOGLE_SHEETS_CREDENTIALS`
   - 添加你的 Google Sheets ID 作为 `GOOGLE_SHEETS_ID`

### 高级设置

编辑 `platforms.yaml` 进行高级配置：

```yaml
settings:
  max_batch_size: 20        # 每批最大产品数
  concurrency_limit: 5      # 并发处理数
  scraping_timeout: 120000  # 2分钟
  analysis_timeout: 60000   # 1分钟
```

## 项目结构

```
ecommerce-competitor-analyzer.skill/
├── SKILL.md                                # AI 指令手册
├── platforms.yaml                          # 平台配置
├── .env.example                            # 配置模板
├── scripts/                                # 核心脚本
│   ├── detect-platform.js                 # 平台检测
│   ├── scrape-amazon.js                   # Amazon 爬虫
│   └── batch-processor.js                 # 批处理引擎
├── prompts/                                # AI 提示词模板
│   ├── analysis-prompt-base.md            # 基础分析框架
│   ├── analysis-prompt-amazon.md          # Amazon 专用提示词
│   └── analysis-prompt-cross-platform.md  # 跨平台对比
└── references/                             # 文档
    ├── n8n-workflow-analysis.md           # n8n 工作流参考
    └── platform-differences.md            # 平台对比
```

## API 密钥获取指南

### 1. Olostep API

1. 访问 [https://olostep.com/](https://olostep.com/)
2. 注册免费账户
3. 导航到 Dashboard > API Keys
4. 复制你的 API 密钥
5. 添加到 `.env`：`OLOSTEP_API_KEY=your_key_here`

**费用**：1000 次免费请求/月，之后 $0.002/次

### 2. Google Gemini API

1. 访问 [https://aistudio.google.com/app/apikey](https://aistudio.google.com/app/apikey)
2. 点击"创建 API 密钥"
3. 复制密钥
4. 添加到 `.env`：`GEMINI_API_KEY=your_key_here`

**费用**：~$0.001/产品分析

### 3. Google Sheets API（可选）

参见上面的"Google Sheets 设置"部分。

## 故障排除

### 问题："Olostep API key not found"

**解决方案**：确保你已从 `.env.example` 创建了 `.env` 文件并添加了你的 API 密钥。

### 问题："Google Sheets authentication failed"

**解决方案**：确保 `.env` 中的 `GOOGLE_SHEETS_CREDENTIALS` 包含有效的 JSON（单行）。

### 问题："Batch processing timeout"

**解决方案**：增加 `.env` 中的 `SCRAPER_TIMEOUT` 或减少批量大小。

### 问题："部分产品失败但其他成功"

**解决方案**：这是预期行为。技能使用错误隔离机制 - 单个失败不会中断整批处理。检查输出报告中的失败项。

## 开发

### 运行测试

```bash
# 测试平台检测
node scripts/detect-platform.js https://amazon.com/dp/B0C4YT8S6H

# 测试爬虫
node scripts/scrape-amazon.js B0C4YT8S6H
```

### 添加新平台

1. 在 `platforms.yaml` 中添加平台配置
2. 在 `scripts/` 中创建爬虫脚本
3. 在 `prompts/` 中创建分析提示词
4. 更新 `scripts/detect-platform.js`

## 贡献

欢迎贡献！请：

1. Fork 仓库
2. 创建功能分支
3. 进行更改
4. 提交 Pull Request

### 贡献方向

- [ ] 添加 Temu 平台支持
- [ ] 添加 Shopee 平台支持
- [ ] 改进错误处理
- [ ] 添加更多 AI 分析维度
- [ ] 创建 Excel 导出格式
- [ ] 添加 PDF 报告生成

## 许可证

本项目基于 MIT 许可证 - 详见 [LICENSE](LICENSE) 文件。

## 致谢

- 基于 n8n 工作流 v81 逻辑构建
- 使用 Olostep API 进行网页抓取
- 使用 Google Gemini API 进行 AI 分析
- 宝玉的 Skills 框架

## 支持

- **问题反馈**：[GitHub Issues](https://github.com/buluslan/ecommerce-competitor-analyzer/issues)
- **讨论交流**：[GitHub Discussions](https://github.com/buluslan/ecommerce-competitor-analyzer/discussions)
- **联系Builder，请备注【github】**：

<img width="717" height="714" alt="wechat_2025-10-17_173400_583" src="https://github.com/user-attachments/assets/7c406098-dcd9-4684-84bd-f0ed4213e95f" />


## 路线图

- [x] Amazon 平台支持
- [ ] Temu 平台支持
- [ ] Shopee 平台支持
- [ ] 跨平台对比
- [ ] 历史价格追踪
- [ ] 评论情感可视化
- [ ] 竞品价格提醒
- [ ] 自动每日分析

---

<div align="center">

**专为跨境电商从业者打造 ❤️**

[⬆ 返回顶部](#跨境电商竞品分析Skill)

</div>
