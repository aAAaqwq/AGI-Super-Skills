---
name: douyin-smart-publisher
description: "抖音智能发布：内容适配→排版→Browser自动发布/存草稿。覆盖标题公式(≤55字+悬念+emoji)、正文排版(分段+emoji点缀)、话题标签策略、封面规格(9:16竖版1080×1920)、视频时长限制。支持图文和视频发布。触发：'发抖音'、'抖音发布'、'douyin publish'、'抖音视频'。"
---

# 抖音智能发布

## 排版规则

| 项 | 规则 |
|----|------|
| 标题 | ≤55字，悬念+关键词+emoji，公式：悬念/痛点+关键词+行动指引+emoji |
| 正文 | 0-500字（视频描述），建议50-200字，前3行放核心 |
| 话题 | #话题名 3-5个，精准话题在前 |
| 封面 | 9:16竖版(1080×1920)，大字+高对比+关键帧 |
| 视频 | 15秒-10分钟，最佳1-3分钟 |
| 最佳时间 | 工作日12-13点、18-21点，周末全天 |

## 内容适配模板

将任意内容转化为抖音格式时：

1. **标题**：提炼核心卖点，套用公式 `悬念/痛点+关键词+行动指引+emoji`
   - 例：`🔥打工人必看！5个效率工具让你准时下班`
   - 例：`👀不会还有人不知道这个神器吧？`

2. **正文排版**（视频描述）：
   ```
   第一行：核心钩子（最吸睛）

   第二行：补充说明/痛点共鸣

   第三行：行动指引/引导评论

   #话题1 #话题2 #话题3
   ```
3. **emoji策略**：标题2-3个，正文每段1个
4. **话题策略**：1-2个精准话题 + 1-2个泛话题 + 1个热度话题

## 发布流程（Browser工具操作）

### 通用流程

**Step 0: 确认发布内容类型**
- 视频 → 走视频发布流程
- 图文 → 走图文发布流程

---

### 🎬 视频发布流程（9步）

**Step 1: 打开发布页面**
```
browser(action="navigate", profile="openclaw", 
       targetUrl="https://creator.douyin.com/creator-micro/content/upload")
```

**Step 2: 等待页面加载**
- 等待创作者平台完全加载
- 检查是否已登录（未登录需扫码）

**Step 3: 上传视频文件**
- 点击上传按钮或使用 `input[type='file']` 上传视频
- 等待视频上传和转码完成（进度条）

**Step 4: 填写标题**
- ⚠️ 定位标题输入框：查找包含"标题"或"描述"的输入框
- 使用 JavaScript 精确填充：
```javascript
// 找到标题输入框并设置值
const titleInput = document.querySelector('input[placeholder*="标题"], textarea[placeholder*="标题"]');
if(titleInput) {
  titleInput.value = '视频标题（≤55字）';
  titleInput.dispatchEvent(new Event('input', {bubbles: true}));
}
```

**Step 5: 填写正文（视频描述）**
- 点击描述输入框获取焦点
- 使用 Clipboard API 粘贴正文：
```javascript
const descInput = document.querySelector('.ql-editor, textarea, [contenteditable="true"]');
if(descInput) {
  descInput.click();
  await new Promise(r => setTimeout(r, 300));
  const text = '要粘贴的正文内容';
  const dt = new DataTransfer();
  dt.setData('text/plain', text);
  descInput.dispatchEvent(new ClipboardEvent('paste', {clipboardData: dt, bubbles: true}));
}
```

**Step 6: 添加话题标签**
- 在正文中添加 #话题名
- 或找到标签输入框添加

**Step 7: 设置封面（可选）**
- 选择视频关键帧作为封面
- 或上传自定义封面图

**Step 8: 截图预览**
- ⚠️ **关键步骤**：截图当前填写内容的页面
- 发送到群中等待 Daniel 确认
- 汇报进度

**Step 9: 等待确认后发布**
- 用户确认后点击「发布」按钮
- 或点击「保存到草稿箱」

---

### 📷 图文发布流程（7步）

**Step 1: 打开发布页面**
```
browser(action="navigate", profile="openclaw", 
       targetUrl="https://creator.douyin.com/creator-micro/content/upload")
```

**Step 2: 选择图文模式**
- 点击「图文」发布选项

**Step 3: 上传图片**
- 点击上传按钮选择图片（9:16竖版最佳）
- 支持1-20张图片

**Step 4: 填写标题**
- 同视频发布 Step 4

**Step 5: 填写正文**
- 同视频发布 Step 5

**Step 6: 添加话题**
- 同视频发布 Step 6

**Step 7: 截图预览 & 等待确认**
- 同视频发布 Step 8-9

---

### 自动化脚本用法

```bash
python scripts/douyin_publish.py \
  --title "标题文字" \
  --content "正文内容" \
  --tags "话题1,话题2,话题3" \
  --video "/path/to/video.mp4" \
  --mode draft \
  --auto-login
```

**参数说明：**
- `--auto-login`: 自动连接 openclaw 浏览器获取登录态
- `--mode draft`: 保存到草稿箱（默认）
- `--mode publish`: 直接发布

## 浏览器自动化注意事项

### 已登录态获取
使用 openclaw 浏览器 profile="openclaw"，通过 CDP 连接 (http://127.0.0.1:18800) 自动复用登录态。

### UI 问题与解决方案

#### ❌ 问题1：正文框写不进去

**根因**：抖音创作者平台可能使用富文本编辑器。

**✅ 解决方案：Clipboard API 模拟粘贴**
```javascript
// 先点击正文编辑器获取焦点
document.querySelector('[contenteditable="true"], textarea')?.click();
await new Promise(r => setTimeout(r, 300));
// 使用 Clipboard API 粘贴
const text = '要粘贴的正文内容';
const clipboardData = new DataTransfer();
clipboardData.setData('text/plain', text);
const pasteEvent = new ClipboardEvent('paste', {
  clipboardData: clipboardData,
  bubbles: true,
  cancelable: true
});
document.querySelector('[contenteditable="true"]')?.dispatchEvent(pasteEvent);
```

#### ❌ 问题2：视频上传失败

**可能原因**：
- 视频格式不支持（推荐MP4）
- 视频过大（压缩后再上传）
- 网络不稳定

**解决**：压缩视频或分段上传

#### ❌ 问题3：登录过期

**解决**：提示用户重新扫码登录

### 手动修正流程（最终兜底）
1. 打开草稿箱
2. 点击"编辑"进入内容
3. 手动修正内容
4. 点击发布

## 错误处理

| 错误 | 处理 |
|------|------|
| 登录过期 | 提示用户重新扫码，保存新cookie |
| 滑块验证 | 暂停等待手动完成，设置 `--headless false` |
| 标题超长 | 自动截断到55字并警告 |
| 视频上传失败 | 重试3次，检查视频格式和大小 |
| 网络超时 | 重试3次，指数退避(5s/15s/45s) |
| 发布频率限制 | 等待60秒后重试 |

## 发布前检查清单

- [ ] 标题 ≤55字，含emoji和悬念词
- [ ] 正文/描述 0-500字
- [ ] 话题 3-5个，#格式
- [ ] 封面 9:16竖版(1080×1920)
- [ ] 视频 15秒-10分钟
- [ ] 无其他平台水印
- [ ] 非AI搬运内容（原创要求）

## 关键页面URL

| 功能 | URL |
|------|-----|
| 抖音创作者平台首页 | https://creator.douyin.com |
| 内容管理 | https://creator.douyin.com/creator-micro/content |
| 图文/视频发布 | https://creator.douyin.com/creator-micro/content/upload |
| 草稿箱 | https://creator.douyin.com/creator-micro/content/draft |

## 文件结构

```
douyin-smart-publisher/
├── SKILL.md
├── scripts/
│   └── douyin_publish.py        # Playwright 自动发布脚本
├── references/
│   └── platform-rules.md       # 完整平台规则（从调研文档提取）
└── templates/
    └── content-template.md      # 排版模板示例
```
