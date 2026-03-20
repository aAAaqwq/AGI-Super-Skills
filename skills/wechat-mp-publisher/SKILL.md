---
name: wechat-mp-publisher
description: "微信公众号智能发布全流程：Markdown→微信HTML转换、UEditor排版(15px/#3f3f3f/1.75倍行距)、封面图(900×500头条/200×200次条)、摘要(≤120字)、草稿/群发两种模式。支持API发布和Playwright浏览器发布。触发：'公众号发布'、'微信推文'、'公众号文章'、'wechat mp publish'、'群发'。"
trigger: 
  - "公众号发布"
  - "微信推文"
  - "公众号文章"
  - "wechat mp publish"
  - "群发"
---

# 微信公众号智能发布

## ⚠️ 重要：发布前确认流程

**在点击保存草稿/群发之前，必须执行以下步骤：**

1. **截图确认**：所有内容（标题、摘要、正文、封面）填写完毕后，**必须**使用 `browser(action="screenshot")` 截图当前编辑页面
2. **发送到群**：将截图发到群里（telegram 群: -1003890797239）供 Daniel 确认
3. **等待确认**：**不要自动发布**，必须等待用户在群里确认「可以发布」或类似明确指令
4. **执行发布**：收到确认后，才点击「保存草稿」或「群发」按钮

> 🚫 **警告**：未收到确认前禁止点击发布按钮！

## 排版规则

| 项 | 规则 |
|----|------|
| 标题 | ≤64字，建议13-22字，少用emoji |
| 摘要 | ≤120字，不填取正文前54字 |
| 正文 | ≤20,000字，建议1500-3000字 |
| 字号 | 正文15px，标题18-22px |
| 颜色 | 正文#3f3f3f(非纯黑)，引用#8c8c8c |
| 行距 | 1.75倍，段间距15px |
| 页边距 | 15-20px |
| 首图 | 900×500px(头条)，核心内容居中 |
| 次图 | 200×200px |
| 配图 | 宽640px适配手机，每300-500字配一图 |
| emoji | ⚠️ 少用，部分客户端异常 |

## 内容适配模板

将任意内容转化为公众号格式时：

1. **标题**：13-22字最优，套路选择：
   - 数字冲击：`7个AI工具让你效率翻倍`
   - 悬念钩子：`最后一个太强了！`
   - 对比反差：`10小时→10分钟`

2. **排版HTML样式**：
   ```html
   <section style="font-size:15px;color:#3f3f3f;line-height:1.75;letter-spacing:1px;padding:0 15px;">
     <h2 style="font-size:20px;font-weight:bold;color:#1a1a1a;margin:30px 0 15px;">标题</h2>
     <p style="margin-bottom:15px;">正文段落</p>
     <blockquote style="border-left:3px solid #07c160;background:#f7f7f7;padding:10px 15px;color:#666;font-size:14px;">
       引用块
     </blockquote>
     <p style="color:#888;font-size:12px;text-align:center;">图片说明</p>
   </section>
   ```

3. **Markdown→微信**：使用 mdnice.com 转换或脚本内置转换器

4. **文末标准模板**：
   ```
   ---
   👆 点击关注，每周更新
   💬 评论区聊聊你的看法
   👇 觉得有用？转发给朋友
   ```

## 发布流程

### 完整工作流（含截图确认）

```
1. 接收任务 → 2. 填写内容 → 3. 截图确认 → 4. 等待Daniel确认 → 5. 发布
```

#### 步骤1：填写内容
使用 Browser 自动化或 API 方式填写所有内容（见下方两种方式）

#### 步骤2：截图确认 ⚠️
- **必须**执行 `browser(action="screenshot")` 截取当前编辑页面
- 将截图发送到 Telegram 群（-1003890797239）
- 截图应包含：标题、摘要、正文预览、封面图

#### 步骤3：等待确认
- **不要自动发布**
- 在群里明确等待用户确认（如「确认发布请回复『可以』」）
- 只有收到 Daniel 的明确确认后才能继续

#### 步骤4：执行发布
收到确认后：
- 草稿模式：点击「保存草稿」
- 发布模式：点击「群发」

---

### 方式A: Browser 自动化（默认）

```bash
python scripts/publish.py \
  --title "文章标题" \
  --content /path/to/article.md \
  --cover /path/to/cover.jpg \
  --digest "文章摘要120字以内" \
  --screenshots /tmp/wechat_screenshots
```

**Browser 模式特点：**
- 需要微信扫码登录（首次）
- cookies 自动保存到 `~/.openclaw/skills/wechat-mp-smart-publish/cookies.json`
- 截图目录可选，用于调试

### 方式B: API 发布（需服务号access_token）

```bash
python scripts/api_publish.py \
  --title "文章标题" \
  --content /path/to/article.html \
  --cover /path/to/cover.jpg \
  --digest "摘要"
```

**API 模式特点：**
- 需要 AppID + AppSecret
- 封面图需提前上传为永久素材
- 支持草稿模式和发布模式

**API 端点：**
- 获取Token：`GET /cgi-bin/token`
- 上传素材：`POST /cgi-bin/material/add_material`
- 新建草稿：`POST /cgi-bin/draft/add`
- 发布：`POST /cgi-bin/freepublish/submit`

### 草稿模式（默认安全）

所有发布默认 `--mode draft`，在公众号后台草稿箱确认后再群发。

### 群发模式

`--mode publish` 直接群发。**警告**：订阅号每天仅1次群发机会，服务号每月4次。

### ⚠️ 确认发布示例消息

发送到群里确认时，建议使用以下格式：

```
📝 文章预览

标题：xxx
摘要：xxx
封面：[截图]

请确认是否发布？回复「可以」或「再改改」
```

## 错误处理

| 错误 | 处理 |
|------|------|
| 登录过期 | 提示重新扫码，保存新cookie |
| 标题超64字 | 截断并警告 |
| 封面尺寸错误 | 自动调整为900×500 |
| 图片不显示 | 检查是否上传到微信素材库(外链不可用) |
| 排版错乱 | 使用行内style，不依赖class |
| API频率限制 | 等待60秒重试，最多3次 |
| 敏感词拦截 | 返回具体敏感词位置，提示修改 |
| **未收到确认就发布** | 🚫 **严重错误**！必须重新执行完整确认流程 |

## 发布前检查清单

- [ ] 标题 ≤64字
- [ ] 摘要 ≤120字
- [ ] 首图 900×500px
- [ ] 排版：15px字号、#3f3f3f色、1.75倍行距
- [ ] 图片已全部上传（外链不可用）
- [ ] 无敏感词/违禁词
- [ ] 手机端预览正常
- [ ] **已截图发送到群里等待确认**
- [ ] **已收到 Daniel 明确确认后才能发布**

## 文件结构

```
wechat-mp-publisher/
├── SKILL.md                    # 本文件
├── scripts/
│   ├── publish.py              # Playwright 浏览器发布（默认）
│   └── api_publish.py          # API 发布（需access_token）
├── references/
│   └── platform-rules.md        # 完整平台规则
└── templates/
    ├── tech-article.html        # 技术文排版模板
    └── general-article.html     # 通用文排版模板
```
