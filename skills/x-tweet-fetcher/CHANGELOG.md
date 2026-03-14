# Changelog

所有重要更新记录在此。

---

## [1.6.0] - 2026-03-04

### 新增
- **X Lists 抓取**：`--list <id_or_url>` 抓取 X Lists 推文
  - 支持纯数字 ID 和完整 URL（x.com/i/lists/xxx 或 twitter.com/i/lists/xxx）
  - 通过 Camofox + Nitter，零 API Key
  - 支持翻页（MAX_PAGES=10）和去重
  - 支持 `--text-only` 纯文本和 JSON 输出

---

## [1.5.0] - 2026-02-25

### 新增
- **Nitter Mentions 监控**：基于 Nitter 的实时 X 提及监控
- **version_check.py**：自动版本检查工具

---

## [1.4.0] - 2026-02-24

### 新增
- **小红书支持**：`fetch_china.py` 新增小红书平台，支持 `--proxy` 和 `--cookies`
- **搜狗微信搜索**：`sogou_wechat.py` 新增 `--resolve`（Google/DDG 解析真实 URL）和 `--via-ssh`（SSH 代理）
- **路由器代理**：`--via-router` 24/7 家庭 IP 代理搜索

---

## [1.3.0] - 2026-02-23

### 新增
- **Mentions 监控**：`--monitor @username` 实时监控谁提到了你
  - 基于 Google 搜索（通过 Camofox），零 API key
  - 增量检测 — 首次建基线，后续只报新内容
  - 支持 cron 集成（退出码 0=无新 / 1=有新）
  - 本地缓存去重（~/.x-tweet-fetcher/）

---

## [1.2.1] - 2026-02-21

### 修复
- **时间线排序（Issue #25）**：时间线模式下按 Snowflake ID 降序排列（最新在前），`tweet_id` 字段从 Nitter `/status/{id}` 链接提取，Pinned tweet 标记 `is_pinned: true`

---

## [1.2.0] - 2026-02-20

### 新增
- **国内平台支持**：新增 `fetch_china.py`，支持 4 个中国平台
  - 🔥 **微博** — 帖子、评论、互动数据
  - 🎬 **B站** — 视频信息、UP主、播放量、点赞、弹幕
  - 💻 **CSDN** — 技术文章、代码块、阅读量
  - 📖 **微信公众号** — 全文+图片，纯 HTTP 无需 Camofox
- **共享模块**：提取 `camofox_client.py`，fetch_tweet.py 和 fetch_china.py 共用
- **多输出格式**：JSON / Markdown（带 YAML frontmatter）/ 纯文本
- **自动平台识别**：给 URL 自动判断是微博/B站/CSDN/微信
- **双语 README**：中文默认 + 英文切换

### 架构
- Strategy Pattern：每个平台独立 Parser，社区可轻松扩展

---

## [1.1.0] - 2026-02-20

### 修复
- **评论区链接提取**：修复 Nitter 返回 `- link "https://..."` 格式时链接丢失的问题
- **嵌套评论**：新增 `thread_replies` 字段支持嵌套回复提取

---

## [1.0.0] - 2026-02-14

### 初始发布
- **单条推文**：通过 FxTwitter API 抓取，零依赖零 API Key
- **评论区**：通过 Camofox + Nitter 抓取回复
- **用户时间线**：支持翻页，最多 200 条
- **X Articles**：长文完整提取
- **引用推文**：自动包含
- **双语支持**：中文/英文消息
