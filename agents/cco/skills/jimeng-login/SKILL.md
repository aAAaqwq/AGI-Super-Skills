---
name: jimeng-login
description: 即梦AI平台(jimeng.jianying.com)浏览器登录。当需要操作即梦数字人、视频生成等功能前检测到未登录时触发。处理协议同意、抖音OAuth扫码、登录态持久化。
---

# 即梦登录

## 前置条件

- OpenClaw 浏览器已启动（profile=openclaw）
- 即梦页面已打开或即将打开

## 登录检测

判断即梦是否已登录：
- **未登录**：左侧栏底部显示"登录"按钮
- **已登录**：左侧栏底部显示用户头像和"开会员"入口

检测方式：对即梦页面做 snapshot，查找 `menuitem "登录"` 元素。存在则未登录。

## 登录流程

### 1. 同意协议弹框

点击"登录"按钮后弹出"同意协议后前往登录"对话框。

**关键坑点**：aria-ref 点击"同意"按钮经常超时。用 JS 点击：

```javascript
// snapshot 中按钮 ref 可能超时，改用 evaluate
() => {
  const all = document.querySelectorAll('[role="dialog"] button');
  const results = [];
  all.forEach(el => results.push({ tag: el.tagName, text: el.textContent, class: el.className }));
  return results;
}
```

找到 class 包含 `agree-button` 的按钮后：

```javascript
() => {
  const btn = document.querySelector('[class*="agree-button"]');
  if (btn) { btn.click(); return 'clicked'; }
  return 'not found';
}
```

### 2. 抖音 OAuth 扫码

同意协议后，即梦会**弹出新标签页**跳转到 `open.douyin.com` 的抖音授权页面（不是页内弹窗）。

操作步骤：
1. 调用 `browser tabs` 查找 title 包含"抖音授权"的标签页
2. 对该标签页截图，获取二维码图片
3. 用 `message` 工具将截图发送给用户（`media` 参数传本地图片路径）
4. 提示用户打开抖音APP → 左上角扫一扫 → 扫码授权

**注意**：多次点击登录会产生多个抖音授权标签页，只需取最新的一个。

### 3. 等待用户扫码确认

用户扫码后，抖音授权标签页会自动关闭/跳转，即梦主页面刷新为已登录状态。

验证方式：对即梦主页面截图，确认左下角不再显示"登录"，而是用户头像。

### 4. 登录态持久化

登录态自动保存在 Chrome user-data 目录：
```
~/.openclaw/browser/openclaw/user-data
```

下次 `browser start profile=openclaw` 启动时自动保持登录。

可选：导出 cookies 备份到 `memory/jimeng-cookies-backup.json`：

```javascript
() => { return document.cookie; }
```

## 常见问题

| 问题 | 解决方案 |
|------|---------|
| "同意"按钮 aria-ref 点击超时 | 用 JS evaluate 通过 class 选择器点击 |
| 登录后页面没变化 | 刷新即梦主页面（navigate 回原 URL） |
| open_id cross app 错误 | 发送图片用 `message` 工具而非直接调飞书 API |
| 多个抖音授权标签页 | 用 `browser tabs` 列出，只操作最新的，关闭多余的 |
| 二维码过期 | 关闭抖音授权标签页，重新点击即梦登录按钮 |
