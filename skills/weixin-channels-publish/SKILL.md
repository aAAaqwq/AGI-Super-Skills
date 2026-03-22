---
name: weixin-channels-publish
description: 微信视频号助手网页版视频发布全流程。通过浏览器自动化操控 channels.weixin.qq.com 完成登录检测、扫码登录、上传视频、填写描述和短标题、截图确认后发布或保存草稿。触发场景：用户需要发布视频到视频号、视频号发布、视频号上传视频、发视频号。
---

# 微信视频号助手 — 视频发布

## 概述

通过浏览器自动化（profile=openclaw）操控视频号助手网页版（channels.weixin.qq.com），完成从登录到视频发布的全流程闭环。

## 前置条件

1. 浏览器已启动：`browser start profile=openclaw`
2. 待发布的视频文件已准备好（通常由 video-merge-send skill 合并输出）
3. 视频描述文案（可由 AI 根据分镜脚本自动生成）

## 完整流程

### Step 1：导航到视频号助手

```
browser navigate url=https://channels.weixin.qq.com
```

等待页面加载完成（2-3秒）。

### Step 2：登录检测

根据 URL 和页面内容判断登录状态：

**判断方法：**
- **未登录**：URL 跳转到 `channels.weixin.qq.com/login.html`，页面显示二维码
- **已登录**：URL 为 `channels.weixin.qq.com/platform/post/list` 或其他非 login 页面，左侧有导航菜单

```javascript
() => {
  return {
    url: window.location.href,
    isLoginPage: window.location.pathname.includes('login'),
    title: document.title
  };
}
```

**已登录** → 跳到 Step 4

**未登录** → 继续 Step 3

### Step 3：扫码登录

#### 3.1 截取二维码

登录页面的二维码位于一个 **iframe** 中。

**方法A：直接截图整个页面**（推荐，最简单）

```
browser screenshot profile=openclaw
```

截图会包含右侧的二维码区域，用户可以直接用微信扫码。

**方法B：定位二维码 iframe 并截图**

```javascript
// 二维码在 iframe 内，结构：
// iframe → generic → img (二维码图片)
// snapshot 中 ref 前缀 f8 表示 iframe 内的元素
// 二维码图片 ref 类似 f8e7
```

#### 3.2 发送二维码截图给用户

```
message action=send channel=feishu message="📱 请用微信扫码登录视频号助手" filePath=<截图路径>
```

发送截图后告知用户：
> "请打开微信 → 扫一扫 → 扫描屏幕上的二维码，然后在手机上确认登录。"

#### 3.3 等待登录完成

轮询检测登录状态（每 5 秒检查一次，最多等待 2 分钟）：

```javascript
() => {
  return {
    url: window.location.href,
    isLoginPage: window.location.pathname.includes('login'),
    title: document.title
  };
}
```

**登录成功标志**：
- URL 不再包含 `login`
- 页面跳转到管理后台（通常是 `/platform/post/list`）

**二维码过期处理**：
- 如果 iframe 中出现"二维码已过期，点击刷新"文本（snapshot 中 `ref=f8e16`）
- 点击刷新链接，重新截图发送

```
browser act kind=click ref=f8e16  # "二维码已过期，点击刷新"
```

#### 3.4 登录态持久化

登录成功后，cookie 自动保存在：
```
~/.openclaw/browser/openclaw/user-data
```
下次打开浏览器自动保持登录。

### Step 4：导航到发表视频页面

登录后导航到"发表视频"页面。有两种方式：

**方式A：直接 URL 导航**（推荐）

```
browser navigate url=https://channels.weixin.qq.com/platform/post/create
```

**方式B：通过菜单导航**

1. snapshot 找到左侧菜单
2. 点击"内容管理"展开子菜单
3. 点击"视频"进入视频列表
4. 点击"发表视频"按钮

```
# 依次查找并点击：
# 1. "内容管理" 菜单项
# 2. "视频" 子菜单
# 3. "发表视频" 按钮
```

### Step 5：上传视频文件

发表视频页面会有一个**上传区域**（通常是拖拽区 + 点击上传按钮）。

#### 5.1 查找上传入口

做 snapshot 找到上传相关元素：
- 通常有"选择文件"或"点击上传"按钮
- 或者一个 `input[type="file"]` 隐藏元素

```javascript
// 查找文件上传 input
() => {
  const inputs = document.querySelectorAll('input[type="file"]');
  const results = [];
  inputs.forEach((input, i) => {
    results.push({
      index: i,
      accept: input.accept,
      id: input.id,
      className: input.className,
      parentClass: input.parentElement?.className
    });
  });
  return results;
}
```

#### 5.2 上传视频

```
browser upload selector="input[type='file']" paths=["<视频文件路径>"]
```

或使用 snapshot 中找到的具体选择器。

**视频文件路径**通常为：
- 单镜头：`/tmp/openclaw/jimeng-videos/01_xxx.mp4`
- 合并后：`/tmp/openclaw/jimeng-videos/final_merged.mp4`

#### 5.3 等待上传完成

视频上传需要时间，取决于文件大小。

轮询检查上传进度（每 5 秒截图/snapshot 一次）：
- 上传中：显示进度条或百分比
- 上传完成：进度消失，显示视频预览缩略图

```javascript
() => {
  // 检查是否有上传进度元素
  const progress = document.querySelector('[class*="progress"]');
  const percent = document.querySelector('[class*="percent"]');
  return {
    hasProgress: !!progress,
    progressText: progress?.textContent || '',
    percentText: percent?.textContent || ''
  };
}
```

### Step 6：填写视频信息

#### 6.1 添加描述（正文描述）

找到描述输入区域并填写爆火文案。

```
# snapshot 找到描述文本框（通常是 textarea 或 contenteditable div）
browser act kind=click ref=<描述输入框_ref>
browser act kind=type text="<描述文案>"
```

**描述文案生成规则：**

根据视频内容（分镜脚本的主题）自动生成爆款描述：

1. **Hook 开头**：用提问或痛点吸引注意
2. **核心价值**：一句话说清视频讲了什么
3. **话题标签**：加 3-5 个相关话题 `#标签`
4. **行动号召**：引导点赞/关注/收藏

**示例模板：**
```
🔥 [痛点问题]？看完这条视频你就懂了！

[一句话核心价值]

💡 关键要点：
1. [要点1]
2. [要点2]
3. [要点3]

👇 觉得有用就点赞收藏，关注我学更多干货！

#企业数字化 #创业干货 #门店经营 #中小企业 #田泽湘
```

#### 6.2 填写短标题（6-16个字符）

找到短标题输入框并填写。短标题显示在视频封面上，要求 **6-16个字符**。

```
# snapshot 找到短标题输入框
browser act kind=click ref=<短标题输入框_ref>
browser act kind=type text="<短标题>"
```

**短标题生成规则：**
- 6-16个字符（中文算1个字符）
- 简短有力，概括视频核心
- 带数字更吸引点击
- 示例：`3万搞定门店数字化`、`利润翻倍的3个秘诀`、`老板必学的获客公式`

#### 6.3 其他可选设置

根据页面情况，可能还有：
- **封面选择**：默认自动截取，或可上传自定义封面
- **位置**：可选添加定位
- **合集**：可选加入已有合集
- **定时发布**：可设置发布时间
- **谁可以看**：公开/私密/部分可见

一般保持默认即可，除非用户特别指定。

### Step 7：截图确认

发布前截图整个页面，发送给用户确认：

```
browser screenshot profile=openclaw
message action=send channel=feishu message="📋 视频已准备好，请确认以下信息后告诉我：\n1️⃣ 立即发布\n2️⃣ 保存草稿\n3️⃣ 修改内容\n\n描述：[已填写的描述]\n短标题：[已填写的短标题]" filePath=<截图路径>
```

等待用户回复指令。

### Step 8：执行发布 / 保存草稿

根据用户指令执行：

#### 发布

```
# snapshot 找到"发表"按钮
browser act kind=click ref=<发表按钮_ref>
```

发布后可能出现确认弹窗，点击确认。

截图确认发布成功：
```
browser screenshot profile=openclaw
message action=send channel=feishu message="✅ 视频已成功发布到视频号！" filePath=<截图路径>
```

#### 保存草稿

```
# snapshot 找到"存草稿"按钮
browser act kind=click ref=<存草稿按钮_ref>
```

## 默认配置

在 `TOOLS.md` 中维护：

```markdown
### 视频号助手 (weixin-channels-publish)

- **默认话题标签**: #企业数字化 #创业干货 #门店经营 #中小企业 #田泽湘
- **默认描述模板**: 爆款描述（hook+价值+标签+CTA）
- **短标题风格**: 数字+痛点，6-16字
```

## 关键技术细节

| 要素 | 说明 |
|------|------|
| 浏览器 profile | openclaw |
| 登录页 URL | `https://channels.weixin.qq.com/login.html` |
| 后台首页 URL | `https://channels.weixin.qq.com/platform/post/list` |
| 发表视频 URL | `https://channels.weixin.qq.com/platform/post/create` |
| 二维码位置 | 登录页右侧 iframe 内（`img` 元素） |
| 登录方式 | 微信扫码（无账号密码登录选项） |
| 登录态存储 | `~/.openclaw/browser/openclaw/user-data`（cookie 自动持久化） |
| 视频上传限制 | 最大 4GB，时长 1 秒 ~ 60 分钟 |
| 支持格式 | mp4, mov, avi, wmv, flv, mkv, webm |
| 短标题要求 | 6-16 个字符 |
| 描述长度限制 | 最多 1000 字 |

## 完整工作流（端到端）

```
1. jimeng-storyboard skill    → 生成分镜脚本
2. jimeng-digital-human skill → 逐镜头生成 + 下载视频
3. video-merge-send skill     → 合并视频片段
4. weixin-channels-publish    → 发布到视频号 ← 本 skill
   ├── Step 1-3: 登录检测/扫码
   ├── Step 4: 导航到发表页
   ├── Step 5: 上传合并视频
   ├── Step 6: 填写描述+短标题
   ├── Step 7: 截图确认
   └── Step 8: 发布/草稿
```

## 常见问题

| 问题 | 解决方案 |
|------|---------|
| 二维码过期 | 点击"二维码已过期，点击刷新"链接，重新截图发给用户 |
| 扫码后未跳转 | 确认手机端已点确认，等待 5-10 秒后刷新页面 |
| 上传进度卡住 | 检查文件大小是否超限（4GB），网络是否稳定 |
| 找不到上传按钮 | 重新 snapshot，视频号助手可能改版，用 JS 搜索 `input[type="file"]` |
| 短标题字数不符 | 严格控制 6-16 字符，中文算 1 个字符 |
| 发布按钮灰色/disabled | 检查必填项是否都已填写（描述、短标题、视频上传完成） |
| 登录后又跳回登录页 | cookie 可能过期，需重新扫码登录 |
| 描述含敏感词被拦截 | 避免使用"最"、"第一"、"保证赚"等绝对化用语 |

## 注意事项

1. **合规先行**：描述中避免夸大承诺和绝对化用语（"最好"、"保证"、"100%"）
2. **发布前必须用户确认**：永远不要自动点击发布，必须截图让用户确认
3. **草稿优先**：如果用户犹豫，默认保存草稿而非发布
4. **每个 snapshot 都要重新获取 ref**：视频号助手 SPA 页面会频繁重渲染
