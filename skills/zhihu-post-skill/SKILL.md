---
name: zhihu-post
description: 在知乎发布内容（专栏文章、想法/动态）。使用 Chrome Browser Relay 控制用户的 Chrome 浏览器完成发布。触发词：知乎发帖、发知乎、知乎文章、知乎想法、zhihu post、发布到知乎、帮我发知乎。
---

# 知乎发帖技能

## 内容类型

| 类型 | URL | 适用场景 |
|------|-----|----------|
| 专栏文章 | https://zhuanlan.zhihu.com/write | 长文、深度内容 |
| 想法（动态） | https://www.zhihu.com/ | 短内容、随感、≤1000字 |

## 前置条件

用户需在 **Windows Chrome** 中完成以下操作：
1. 打开目标 URL（文章或首页）
2. 确保已登录知乎
3. 点击 OpenClaw Browser Relay 工具栏图标 attach tab（badge 亮起）

## 发布专栏文章流程

### Step 1：确认 tab 连接
```
browser(action=tabs, profile="chrome")
```
确认知乎编辑器页面在列表中。

### Step 2：获取页面快照
```
browser(action=snapshot, profile="chrome", interactive=True)
```

### Step 3：填写标题

知乎文章标题 input selector：
```
input[placeholder*="标题"]
```
或用 aria ref 点击标题区域，用 `browser(action=act, request={kind:type, ref:<ref>, text:"..."})` 填入。

也可用 JS：
```javascript
const titleInput = document.querySelector('textarea[placeholder], input[placeholder*="标题"]');
titleInput.value = "你的标题";
titleInput.dispatchEvent(new Event('input', {bubbles: true}));
```

### Step 4：填写正文

知乎文章编辑器是 **Draft.js**，selector：
```
.notranslate.public-DraftEditor-content[contenteditable="true"]
```

⚠️ Draft.js **不能直接赋值 innerHTML**，必须用 `execCommand`：
```javascript
const el = document.querySelector('[contenteditable="true"]');
el.focus();
document.execCommand('selectAll');
document.execCommand('insertText', false, '你的正文内容（纯文本）');
```

如需多段落，插入 `\n\n` 分隔段落。如需加粗/标题等富文本格式，点击工具栏对应按钮后再执行 insertText。

### Step 5：发布

快照找到「发布」按钮 ref，点击：
```
browser(action=act, profile="chrome", request={kind:click, ref:<发布按钮ref>})
```

或 JS：
```javascript
// 找包含"发布"文字的按钮
[...document.querySelectorAll('button')].find(b => b.textContent.includes('发布文章'))?.click()
```

### Step 6：确认发布成功

页面跳转到文章详情页（URL 含 `zhuanlan.zhihu.com/p/`）即为成功。

---

## 发布想法（动态）流程

想法是知乎首页的短内容框，限制约 1000 字。

### Step 1：打开想法输入框

在 https://www.zhihu.com/ 快照后，点击「写想法」或顶部输入框触发编辑器展开。

### Step 2：填写内容

想法编辑器 selector（contenteditable div）：
```javascript
const editor = document.querySelector('.PublishThought-editor .DraftEditor-contentWrapper [contenteditable="true"]');
// 或尝试：
const editor = document.querySelector('[contenteditable="true"][data-contents]');
editor.focus();
```

用 `browser(action=act, request={kind:type, ref:<ref>, text:"..."})` 输入，或 JS 设置。

### Step 3：发布

点击「发布」按钮（通常右下角）。

---

## 注意事项

- **首次使用前**先手动在 Chrome 登录知乎，避免发布时弹出验证码
- 内容含图片时：先将图片复制到 `/tmp/openclaw/uploads/`，再用 `browser(action=upload)` 上传
- 知乎对新账号有发布频率限制，连续发布间隔 ≥ 3 分钟
- 发布完成后截图 `browser(action=screenshot)` 留存证据

## 参考文件

- `references/dom-selectors.md` — 知乎各页面 DOM 结构速查
