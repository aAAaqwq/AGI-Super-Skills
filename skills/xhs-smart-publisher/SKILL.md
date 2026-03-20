---
name: xhs-smart-publisher
description: "小红书智能发布：内容适配→排版→Playwright自动发布/存草稿。覆盖标题公式(≤20字+emoji+数字)、正文排版(空行分段+emoji点缀)、标签策略(热门+长尾3-8个)、封面规格(3:4竖版1080×1440)、CES算法优化。支持图文笔记和轮播。触发：'发小红书'、'小红书发布'、'xhs publish'、'红书笔记'、'小红书草稿'。"
---

# 小红书智能发布

## ⚡ 快速工作流

```
触发词 → 填写内容 → 🔍 截图确认 → ⏳ 等待指令 → ✅ 发布/存草稿
```

**关键：截图确认步骤不可跳过！**

| 步骤 | 操作 | 阻塞? |
|------|------|-------|
| 1 | 填写标题、正文、标签、上传封面 | ❌ |
| 2 | **截图发送到群** | ⚠️ 必须 |
| 3 | **等待用户确认** | ✅ 阻塞 |
| 4 | 收到"发布"→点击发布 | ❌ |
| 4 | 收到"存草稿"→点击暂存 | ❌ |

**用户指令：**
- `发布` / `确认发布` → 执行发布
- `存草稿` / `暂存` → 保存到草稿箱

## 排版规则

| 项 | 规则 |
|----|------|
| 标题 | ≤20字，emoji+关键词+数字，公式：人群+关键词+数字+悬念+emoji |
| 正文 | 300-1000字，双换行分段，每段1-2个emoji开头，前3行放核心 |
| 标签 | #话题名(无空格) 3-8个，精准在前泛话题在后 |
| 封面 | 3:4竖版(1080×1440)，大字+对比色+人物/产品占60%+ |
| 图片 | 1-18张，JPG/PNG，≤20MB/张 |
| 最佳时间 | 工作日18-22点，周末20-23点 |

## 内容适配模板

将任意内容转化为小红书格式时：

1. **标题**：提炼核心卖点，套用公式 `人群定位+关键词+数字+悬念词+emoji`
   - 例：`打工人必看🔥5个效率工具让你准时下班`
2. **正文排版**：
   ```
   emoji 开头金句/痛点（抓注意力）

   emoji 正文第一段（核心信息，≤3行）

   emoji 正文第二段（展开论述）

   emoji 正文第三段（补充/案例）

   emoji 总结/互动引导（提问/投票）

   #精准话题1 #精准话题2 #泛话题3 #泛话题4
   ```
3. **emoji策略**：每段开头1个，正文中关键词旁适度点缀，不超过正文的5%
4. **标签策略**：2个精准话题(搜索量高) + 2-4个泛话题(曝光量大) + 1-2个长尾话题

## 发布流程（Browser工具操作）

### 通用流程

**Step 0: 确认发布内容类型**
- 视频 → 走视频发布流程
- 图文 → 走图文发布流程
- 长文 → 走长文发布流程

---

### 📷 图文发布流程（7步）

**Step 1: 打开发布页面**
```
browser(action="navigate", profile="openclaw", 
       targetUrl="https://creator.xiaohongshu.com/publish/publish?source=official&target=image")
```

**Step 2: 确认发布类型**
- 点击「上传图文」

**Step 3: 上传封面图片**
- 点击上传按钮或 `input[type='file']` 上传封面图
- 等待图片加载完成

**Step 4: 填写标题**
- ⚠️ 定位标题输入框：placeholder="填写标题会有更多赞哦"
- 使用 JavaScript 精确填充（防止UI错位）：
```javascript
// 找到标题输入框并设置值
const titleInput = document.querySelector('input[placeholder*="标题"]');
if(titleInput) {
  titleInput.value = '标题内容（≤20字）';
  titleInput.dispatchEvent(new Event('input', {bubbles: true}));
}
```

**Step 5: 填写正文（⚠️ 最关键一步）**
- **先点击正文编辑器获取焦点**：
  ```
  browser(action="act", kind="click", ref="<正文框ref>")
  ```
- **等待 500ms** 让 Quill 编辑器初始化
- **使用 Clipboard API 粘贴正文**（不要用 fill/type，会失败）：
```javascript
const el = document.querySelector('.ql-editor');
el?.click();
await new Promise(r => setTimeout(r, 300));
const text = `要粘贴的完整正文内容（含换行）`;
const dt = new DataTransfer();
dt.setData('text/plain', text);
el?.dispatchEvent(new ClipboardEvent('paste', {
  clipboardData: dt, bubbles: true, cancelable: true
}));
```
- **验证**：正文框字数统计应显示 `X/1000`（X>0），如果仍显示 `0/1000`，尝试方案B/C/D（见"UI问题与解决方案"）
- ⚠️ 如果使用 browser evaluate，fn 中不能有 await，用 setTimeout 包裹：`new Promise(r=>setTimeout(r,500)).then(()=>{...})`

**Step 6: 检查排版**
- ⚠️ **必须先验证正文已写入**：正文框字数应 > 0
- 截图确认格式
- 确认标题框内只有标题（≤20字），字数 `X/20`
- 确认正文框内有完整正文，字数 `X/1000`
- 如正文 0/1000 → 正文未写入 → 回到 Step 5 尝试其他方案
- 如有排版问题，手动调整

**Step 7: 🔍 截图确认（必须步骤）**
- ⚠️ **在点击发布/保存草稿之前**，必须执行此步骤
- 使用 browser 截图当前页面内容：
  ```
  browser(action="screenshot", target="host")
  ```
- 将截图发送到群中汇报：
  ```
  message(action="send", channel="telegram", target="-1003890797239", 
         message="📝 小红书内容已填写完毕，请确认后回复'发布'或'存草稿'",
         accountId="xiaocode")
  ```
- **必须等待用户确认后才能继续**（不自动发布）

**Step 8: ⏳ 等待用户确认**
- 用户回复以下指令之一：
  - `发布` / `确认发布` → 执行发布
  - `存草稿` / `暂存` → 保存到草稿箱
  - `修改` / `取消` → 停止流程，等待重新触发
- ⚠️ **此步骤是阻塞的**，在收到明确指令前不执行任何操作

**Step 9: ✅ 执行发布/存草稿**

*根据用户确认选择：*

**发布模式：**
- 点击「发布」按钮
- 等待发布成功提示
- 截图确认发布结果
- 发送完成通知到群

**草稿模式：**
- 点击「暂存离开」按钮
- 确认草稿保存成功
- 发送完成通知到群

---

### 📝 长文发布流程（6步）

相比图文，少去上传图片封面步骤

**Step 1: 打开发布页面**
- URL: `https://creator.xiaohongshu.com/publish/publish?source=official`

**Step 2: 确认发布类型**
- 点击「写长文」

**Step 3: 填写标题**
- 同图文 Step 4

**Step 4: 填写正文**
- 同图文 Step 5

**Step 5: 🔍 截图确认（必须步骤）**
- 同图文 Step 7：必须先截图发送到群等待确认

**Step 6: ⏳ 等待用户确认**
- 同图文 Step 8：等待用户回复「发布」或「存草稿」

**Step 7: ✅ 执行发布/存草稿**
- 同图文 Step 9

---

### 🎬 视频发布流程（3步）

**Step 1: 上传视频**
- 点击「上传视频」
- 选择视频文件上传

**Step 2: 🔍 截图确认（必须步骤）**
- 填写标题、描述等内容后
- 执行 `browser(action="screenshot", target="host")` 截图
- 发送到群中等待确认
- ⚠️ 必须等待用户确认后才能发布

**Step 3: ⏳ 等待用户确认**
- 同图文 Step 8

**Step 4: ✅ 执行发布**
- 用户确认后点击「发布」

---

### 自动化脚本用法

```bash
python scripts/xhs_publish.py \
  --title "标题文字" \
  --content "正文内容" \
  --tags "话题1,话题2,话题3" \
  --image "/path/to/cover.jpg" \
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

#### ❌ 问题1：正文框 0/1000 写不进去（已确认 2026-03-19）

**现象**：标题正确（8字），但正文框显示 0/1000，browser 的 fill/type 均无法写入内容。

**根因**：小红书创作者平台使用 **Quill.js 富文本编辑器**（class=`ql-editor`，`contenteditable="true"`）。普通 DOM 操作（设置 innerText/value）不触发 React 状态更新，导致：
- 内容虽然视觉上出现，但 Quill 内部 delta 为空
- 字数统计不变（0/1000）
- 保存草稿后正文丢失

**✅ 解决方案（按优先级排序）**：

**方案A：Clipboard API 模拟粘贴（推荐）**
```javascript
// 先点击正文编辑器获取焦点
document.querySelector('.ql-editor')?.click();
// 等待 300ms 让 Quill 初始化
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
document.querySelector('.ql-editor')?.dispatchEvent(pasteEvent);
```

**方案B：Quill API 直接操作**
```javascript
// 获取 Quill 实例（通过 __quill 属性）
const quill = document.querySelector('.ql-editor')?.__quill;
if (quill) {
  quill.clipboard.dangerouslyPasteHTML(0, '<p>正文段落1</p><p>正文段落2</p>');
}
```

**方案C：executeCommand（兼容方案）**
```javascript
document.querySelector('.ql-editor')?.focus();
document.execCommand('selectAll');
document.execCommand('insertText', false, '正文内容');
```

**方案D：使用 Playwright 的 keyboard.type + clipboard**
```
# 先复制内容到剪贴板
browser(action="evaluate", fn="navigator.clipboard.writeText('正文内容')")
# 点击正文框
browser(action="act", kind="click", ref="正文框ref")
# Ctrl+V 粘贴
browser(action="act", kind="press", key="Control+v")
```

**⚠️ 注意**：方案D在 Linux 无头浏览器中可能不工作（无 X clipboard），优先用方案A。

**验证标准**：粘贴后正文框字数统计应显示 `X/1000`（X>0）。

---

#### ❌ 问题2：标题和正文内容混串

**现象**：标题输入框显示字符计数如 "510/20"，内容被粘贴到了标题位置。

**根因**：编辑器 UI 的 contenteditable 字段定位错误。

**解决**：
  1. **先填标题**：使用 `input[placeholder*="标题"]` 定位
  2. **再点击正文框**：点击 `.ql-editor` 后等待 500ms
  3. **最后填正文**：使用方案A粘贴
  4. 验证标题框字数 ≤ 20，正文框字数 > 0

### 手动修正流程（最终兜底）
1. 打开草稿箱
2. 点击"编辑"进入文章
3. 手动复制正文到正确位置，修正标题
4. 点击发布

## 错误处理

| 错误 | 处理 |
|------|------|
| 登录过期 | 提示用户重新扫码，保存新cookie |
| 滑块验证 | 暂停等待手动完成，设置 `--headless false` |
| 标题超长 | 自动截断到20字并警告 |
| 图片上传失败 | 重试3次，每次间隔5秒 |
| 网络超时 | 重试3次，指数退避(5s/15s/45s) |
| 发布频率限制 | 等待60秒后重试 |
| 内容混入标题 | 保存草稿后手动修正 |

## 发布前检查清单

- [ ] 标题 ≤20字，含emoji和关键词
- [ ] 正文 ≥100字（新规要求）
- [ ] 标签 3-8个，#格式
- [ ] 封面图 3:4竖版
- [ ] 无其他平台水印
- [ ] 非AI搬运内容（原创要求）

## 文件结构

```
xhs-smart-publisher/
├── SKILL.md
├── scripts/
│   └── xhs_publish.py        # Playwright 自动发布脚本
├── references/
│   └── platform-rules.md     # 完整平台规则（从调研文档提取）
└── templates/
    └── content-template.md   # 排版模板示例
```
