# 知乎 DOM 选择器速查

> 更新日期：2026-02-28  
> 基于 Chrome Browser Relay 实测，知乎可能随时更新 DOM

## 专栏文章编辑器（zhuanlan.zhihu.com/write）

> ⚠️ 知乎文章编辑器基于 **Draft.js**，非 ProseMirror

```
标题输入框：  textarea[placeholder*="请输入标题"]  或  ref=e206（快照获取）
正文编辑器：  .notranslate.public-DraftEditor-content[contenteditable="true"]
              或直接：document.querySelector('[contenteditable="true"]')
发布按钮：    button（文字含"发布"，disabled 状态填内容后解除）
草稿保存：    button（文字含"草稿备份"）
```

## 想法编辑器（zhihu.com 首页）

```
触发区域（点击展开）：  .Sticky .PublishThought input  或顶栏占位文字
内容编辑区：           .PublishThought-editor [contenteditable="true"]
                       或 .DraftEditor-editorContainer [contenteditable]
图片上传：             .PublishThought-picture input[type="file"]
话题标签：             .PublishThought-topic
发布按钮：             .PublishThought-submit  或 button:contains("发布")
```

## 通用 JS Snippets

### 设置 Draft.js 编辑器内容（知乎文章正文）
```javascript
// Draft.js 不能直接赋值 innerHTML，必须用 execCommand
const el = document.querySelector('[contenteditable="true"]');
el.focus();
document.execCommand('selectAll');
document.execCommand('insertText', false, '段落一\n\n段落二\n\n段落三');
```

### 设置 Draft.js / DraftEditor 内容（想法）
```javascript
// Draft.js 不能直接设置 innerHTML，需要模拟键盘输入
const el = document.querySelector('[contenteditable="true"]');
el.focus();
document.execCommand('selectAll');
document.execCommand('insertText', false, '你的想法内容');
```

### 点击发布按钮（通用 fallback）
```javascript
const btns = [...document.querySelectorAll('button')];
const publish = btns.find(b => /发布/.test(b.textContent) && !b.disabled);
publish?.click();
```

### 等待页面跳转（文章发布成功判断）
```javascript
// 发布成功后 URL 变为 zhuanlan.zhihu.com/p/<id>
window.location.href.includes('/p/')
```

## 常见问题

| 问题 | 原因 | 解法 |
|------|------|------|
| 点发布没反应 | 标题/正文为空验证 | 确保两者均已填写 |
| 内容被清空 | React/Vue 状态未同步 | 用 execCommand 代替直接赋值 |
| 弹出验证码 | 账号风控 | 手动完成验证后继续 |
| 图片上传失败 | 文件路径不在白名单 | 先复制到 /tmp/openclaw/uploads/ |
