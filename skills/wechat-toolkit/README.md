# 📦 微信公众号工具包 (wechat-toolkit)

> OpenClaw Skill — 微信公众号一站式工具包，集成 **搜索 → 下载 → 洗稿 → 发布** 四大功能，覆盖公众号内容创作全流程。
>
> 📦 **跨平台支持**: macOS / Linux / Windows（全部脚本基于 Node.js）

---

## ✨ 功能模块

| 模块 | 功能 | 说明 |
|------|------|------|
| 🔍 **搜索** | 关键词搜索公众号文章 | 基于搜狗微信搜索，支持抓取正文 |
| 📰 **下载** | 下载文章内容/配图/视频 | 输出 Markdown + HTML + 媒体文件 |
| ✍️ **洗稿** | AI 去痕迹 + 原创改写 | 结构重组、语言改写、SEO 优化 |
| 📱 **发布** | 一键发布到公众号草稿箱 | 基于 wenyan-cli，支持主题和视频嵌入 |

---

## 🚀 快速开始

### 环境要求

- **Node.js** ≥ 18
- **Google Chrome**（下载模块需要）
- [OpenClaw](https://github.com/anthropics/openclaw) 运行环境

### 安装

```bash
# 1. 克隆仓库到 OpenClaw skills 目录
git clone git@github.com:Mr-Q526/openclaw-skill-wechat-toolkit.git skills/wechat-toolkit

# 2. 安装搜索模块依赖
npm install -g cheerio

# 3. 安装下载模块依赖
cd skills/wechat-toolkit/scripts/downloader && npm install

# 4. 安装发布模块依赖
npm install -g @wenyan-md/cli
```

---

## 📖 使用方法

### 🔍 搜索文章

```bash
# 基础搜索
node scripts/search/search_wechat.js "关键词"

# 指定数量 + 抓取正文
node scripts/search/search_wechat.js "关键词" -n 5 -c

# 保存结果
node scripts/search/search_wechat.js "关键词" -n 20 -o result.json
```

**参数：**
- `-n, --num`：返回数量（默认 10，最大 50）
- `-o, --output`：输出 JSON 文件路径
- `-r, --resolve-url`：解析微信文章真实链接
- `-c, --fetch-content`：抓取文章正文（自动启用 `-r`）

### 📰 下载文章

```bash
# 设置默认下载路径（首次）
node scripts/downloader/download.js --set-output ~/Downloads/wechat-articles

# 下载文章
node scripts/downloader/download.js "https://mp.weixin.qq.com/s/xxx"

# 跳过图片/视频
node scripts/downloader/download.js "https://mp.weixin.qq.com/s/xxx" --no-image --no-video
```

**输出结构：**
```
<下载目录>/<文章标题>/
├── content/article.html    # 完整 HTML
├── metadata.json            # 元数据
├── images/                  # 配图
└── videos/                  # 视频/音频
```

### ✍️ 洗稿改写

作为 OpenClaw Skill 使用，通过自然语言指令触发：

- *"帮我洗稿这篇文章"*
- *"改写成原创"*
- *"降低查重率"*
- *"去掉 AI 味"*

**改写策略包括：** 结构重组、语言改写、标题优化、开头重写、SEO 优化等。

### 📱 发布到公众号

```bash
# 配置（确保环境变量已设置）
export WECHAT_APP_ID=your_app_id
export WECHAT_APP_SECRET=your_app_secret

# 发布（三种方式任选）
node scripts/publisher/publish.js /path/to/article.md
wenyan publish -f article.md -t lapis -h solarized-light
node scripts/publisher/publish_with_video.js /path/to/article.md  # 含视频时使用
```

> ⚠️ **重要：** 你的 IP 必须添加到微信公众号后台白名单中！

**Markdown 格式要求：**
```markdown
---
title: 文章标题（必填）
cover: /absolute/path/to/cover.jpg（必填，使用绝对路径）
---

# 正文内容...
```

---

## 📁 项目结构

```
wechat-toolkit/
├── SKILL.md                        # OpenClaw Skill 定义
├── README.md                       # 本文件
├── example.md                      # 示例文章
├── references/                     # 参考文档
│   ├── themes.md                   #   主题配置说明
│   └── troubleshooting.md          #   故障排查指南
└── scripts/                        # 脚本目录（全部 Node.js，跨平台）
    ├── search/                     #   搜索模块
    │   └── search_wechat.js
    ├── downloader/                 #   下载模块
    │   └── download.js
    └── publisher/                  #   发布模块
        ├── publish.js              #   基础发布
        └── publish_with_video.js   #   含视频发布
```

---

## 🔧 故障排查

| 问题 | 解决方法 |
|------|----------|
| IP 不在白名单 | `curl ifconfig.me` → 添加到公众号后台 |
| wenyan 未安装 | `npm install -g @wenyan-md/cli` |
| 环境变量未设置 | `export WECHAT_APP_ID=xxx` |
| 缺少 frontmatter | 添加 `title` + `cover` 字段 |
| 40001 token 失效 | 使用 `publish_with_video.js` |

更多排查方法见 [`references/troubleshooting.md`](references/troubleshooting.md)

---

## ⚠️ 免责声明

- 所有工具仅供**个人学习**使用，请遵守相关版权法规
- 搜索功能内置防封禁机制（随机 UA、请求延迟），请勿高频使用

---

## 📄 License

MIT
