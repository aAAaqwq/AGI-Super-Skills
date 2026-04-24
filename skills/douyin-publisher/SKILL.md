---
name: douyin-publisher
description: "抖音图文/视频发布（OpenClaw Browser 自动化）：登录检测→内容校验→上传页导航→填标题/正文→上传封面+素材→暂存离开。"
metadata: {"version":"2.0.0","author":"Daniel Li","domains":["content","publishing","automation","douyin"],"type":"automation"}
---
description: "抖音图文/视频发布（OpenClaw Browser 自动化）：登录检测→内容校验→上传页导航→填标题/正文→上传封面+素材→暂存离开。默认只存草稿，Daniel确认后才发布。触发：'发抖音'、'抖音发布'、'douyin publish'、'抖音图文'、'抖音视频'、'发布短视频'。"
author: Daniel Li
version: 2.0.0
---

# 抖音发布 v2.0 — OpenClaw Browser 自动化

> **核心技术栈：OpenClaw `browser` 工具**（不依赖独立 Playwright 脚本）
> **安全原则：默认只存草稿，只在 Daniel 明确确认后才允许点击发布**

---

## ⚠️ 安全铁律

1. **默认 `mode=draft`** — 每次发布流程终点是「暂存离开」，不是「发布」
2. **发布确认门** — 收到 Daniel 明确回复"可以发/发布/ok"后，才允许切换到发布
3. **每步截图** — 关键节点截图留证，失败时有据可查
4. **3次失败即停** — 任何步骤连续失败3次，截图+报告+转"待 Daniel 接管"
5. **遇到验证码/滑块/频率限制** — 立刻停止，截图，等 Daniel 处理

---

## 📋 发布前合规检查

发布前参考 `references/platform-rules.md` 确认内容合规：
- 社区公约11大类违规内容
- AIGC 标识要求（"内容由AI生成"）
- 账号健康分要求
- 禁止搬运/水印/低质内容

---

## 🔄 完整 Workflow（6步）

```
Step 1: 登录检测 ──→ Step 2: 内容检测 ──→ Step 3: 进入发布页
                                                      │
Step 6: 暂存离开 ←── Step 5: 上传素材 ←── Step 4: 填写内容
     │
     ▼
 确认回传给 Daniel
```

---

## Step 1: 登录检测

**目标：确认浏览器已登录抖音创作者平台，未登录则发送二维码给 Daniel**

### 1.1 打开浏览器

```
browser(action="open", url="https://creator.douyin.com/creator-micro/home", profile="user")
```

> `profile="user"` 使用 Daniel 的本地浏览器（已有登录态概率最高）
> 如果 user profile 不可用，使用默认 profile（OpenClaw 托管浏览器）

### 1.2 等待页面加载 & 检测登录状态

```
browser(action="snapshot")
```

**判断是否已登录：**
- ✅ 已登录：URL 包含 `creator-micro`，页面出现创作者后台内容
- ❌ 未登录：URL 包含 `login`/`passport`，或页面出现「扫码登录」「验证码登录」

### 1.3 未登录处理：发二维码

如果未登录：

```
# 截取二维码区域
browser(action="screenshot", path="/tmp/douyin_qr_login.png")
```

然后发消息给 Daniel：
```
message(action="send", message="⚠️ 抖音未登录，请扫描二维码登录。登录完成后回复"ok"",
        media="/tmp/douyin_qr_login.png")
```

等待 Daniel 回复后，重新检测：

```
browser(action="navigate", url="https://creator.douyin.com/creator-micro/home")
# 等待 5 秒让页面加载
browser(action="snapshot")
# 确认已进入创作者后台
```

### 1.4 成功标志

截图确认并记录：
```
browser(action="screenshot", path="/tmp/douyin_step1_logged_in.png")
```

---

## Step 2: 内容及素材检测

**目标：在动手前确认所有文件就绪、格式正确、内容合规**

### 2.1 检查素材文件

```bash
# 确认文件存在、格式、大小
ls -lh /path/to/images/*.jpg /path/to/cover.png
file /path/to/images/*.jpg
```

**图文要求：**
| 项目 | 要求 |
|------|------|
| 图片数量 | 2-35 张 |
| 格式 | JPG, PNG, WebP（**不支持 GIF**） |
| 单张大小 | ≤50MB |
| 推荐比例 | 3:4（1080×1440）或 4:3 |

**视频要求：**
| 项目 | 要求 |
|------|------|
| 格式 | MP4 (H.264) |
| 分辨率 | ≥720×1280，推荐 1080×1920 |
| 大小 | ≤16GB |
| 时长 | 15秒-60分钟 |

### 2.2 检查文本内容

```bash
# 确认标题和描述文件
cat /path/to/content.md
```

**校验规则：**
- 标题 ≤**20**字（实测图文页标题框限制20字）
- 描述 ≤200 字（含话题标签）
- 话题 3-5 个，格式 `#话题名`（无空格）
- AI 内容已标注"内容由AI生成"

### 2.3 输出检测报告

向 Daniel 确认：

```
📋 内容检测报告
━━━━━━━━━━━━━━
📌 标题：{title}（{len}字）
📝 描述：{desc[:50]}...（{len}字）
🏷️ 话题：{tags}
🖼️ 素材：{count} 张图片 / {video} 视频
📐 格式：{formats}
📦 大小：{total_size}

✅ 全部就绪，开始发布流程
```

---

## Step 3: 进入抖音图文发布页面

**目标：导航到正确的发布页面，处理好可能的弹窗**

### 3.1 导航

**图文发布：**
```
browser(action="navigate", url="https://creator.douyin.com/creator-micro/content/upload?default-tab=3")
```

**视频发布：**
```
browser(action="navigate", url="https://creator.douyin.com/creator-micro/content/upload")
```

### 3.2 等待页面就绪

```
# 等待文件上传控件出现（证明页面已完全加载）
browser(action="snapshot")
```

检查 snapshot 中是否有 `input[type="file"]`。如果没有：
- 等待 5 秒再试
- 如果 30 秒内仍未出现，可能被弹窗遮挡 → 处理弹窗

### 3.3 处理干扰弹窗

抖音经常弹出"上次未发布内容"提示。检测并关闭：

```
browser(action="act", kind="evaluate", fn="""() => {
    const els = document.querySelectorAll('*');
    for (const el of els) {
        const t = el.textContent.trim();
        if ((t === '放弃' || t === '不再提醒' || t === '新建图文')
            && el.offsetParent !== null && el.children.length === 0) {
            el.click();
            return 'dismissed: ' + t;
        }
    }
    return 'no popup';
}""")
```

### 3.4 截图确认

```
browser(action="screenshot", path="/tmp/douyin_step3_publish_page.png")
```

---

## Step 4: 填写标题和正文

**目标：在发布页面填入标题和描述（含话题标签）**

### 4.1 填写标题

找到标题输入区（优先使用 snapshot 中的 ref）：

```
# 方法1：通过 placeholder 定位（推荐）
browser(action="act", kind="fill", ref="{title_input_ref}", text="{标题文字}")

# 方法2：通过 evaluate 直接操作
browser(action="act", kind="evaluate", fn="""() => {
    const sel = 'input[placeholder*="标题"]';
    const el = document.querySelector(sel);
    if (el) {
        el.focus();
        el.select();
        el.value = '';
        // 触发 React 的 onChange
        const nativeInputValueSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
        nativeInputValueSetter.call(el, arguments[0]);
        el.dispatchEvent(new Event('input', { bubbles: true }));
        el.dispatchEvent(new Event('change', { bubbles: true }));
        return 'title filled';
    }
    return 'title input not found';
}""")
```

> **注意**：抖音是 React SPA，直接 `.value = xxx` 不会触发状态更新。必须用 `nativeInputValueSetter` 或 `type` 动作。

### 4.2 填写描述（正文）⚠️ 关键步骤

> **2026-04-17 实战验证结论**：
> 抖音描述区使用 **Slate.js** (`data-slate-editor="true"`)，不是普通 textarea。
> - ❌ `innerText = xxx` → 视觉显示但 Slate 状态不更新，暂存后丢失
> - ❌ `document.execCommand('insertText')` 多次调用 → 文本叠加，无法清空已有内容
> - ❌ `ClipboardEvent('paste')` → 浏览器安全策略阻止，Slate 读不到数据
> - ❌ `new InputEvent('beforeinput')` → Slate `preventDefault()` 后不执行实际插入
> - ❌ `browser act kind=type` → contenteditable div 无 Playwright ref，超时
> - ❌ `browser act kind=fill` → 不支持 contenteditable
> - ✅ **唯一可靠方法**：**从全新页面一次性 `execCommand('insertText')`**，且只能调用一次

**正确流程（必须在全新空白编辑器上执行）：**

```
# Step 1: 聚焦描述区
browser(action="act", kind="evaluate", fn="""() => {
    const desc = document.querySelector('[data-slate-editor="true"]');
    if (!desc) return 'not found';
    desc.focus();
    return 'focused';
}""")

# Step 2: 一次性插入文本（只能执行一次！）
browser(action="act", kind="evaluate", fn="""() => {
    const desc = document.querySelector('[data-slate-editor="true"]');
    if (!desc) return 'not found';
    
    const text = '你的描述文字（建议≤200字，含#话题标签）';
    document.execCommand('insertText', false, text);
    
    // 触发 blur 确保 Slate 最终提交状态
    desc.blur();
    
    return 'inserted: ' + desc.innerText.length + ' chars';
}""")

# Step 3: 验证字数计数器已更新（从 0/N 变为实际字数/N）
browser(action="snapshot")
# 检查描述区域文本中是否显示 "实际字数 / 1000"
```

**验证要点**：
- 描述区字数计数器从 `0 / 1000` 变为 `实际字数 / 1000` → ✅ React 状态已更新
- 如果计数器仍是 `0 / 1000` → ❌ 文本未写入 Slate 状态，暂存后会丢失

**注意事项**：
- 描述中包含 `#` 时抖音可能弹出话题搜索面板，此时需先点击面板外部关闭
- `execCommand('insertText')` 在已有内容的 Slate 编辑器上**无法正确清空**（selectAll+delete 无效）
- 如果描述填错，必须**清空重新上传**（点「清空并重新上传」按钮），重新走整个流程
- 不要尝试多次调用 `execCommand`，每次都会在现有文本基础上追加

### 4.3 话题标签

直接在描述文本中包含 `#话题1 #话题2` 即可，Slate 会自动识别。
**不要**单独追加话题，会导致文本叠加问题。

### 4.4 截图确认

```
browser(action="screenshot", path="/tmp/douyin_step4_content_filled.png")
```

---

## Step 5: 上传封面及素材图片

**目标：上传图片素材到发布页面**

### 5.1 定位文件上传控件

```
# 通过 snapshot 获取 file input 的 ref
browser(action="snapshot")
```

找到 `input[type="file"][accept*="image"]` 的 ref。

### 5.2 上传素材图片

> **2026-04-17 实战验证**：
> - `file://` fetch 被浏览器安全策略阻止
> - `evaluate` 中的 `DataTransfer` + `File` 构造同样被阻止
> - 文件必须放在 `/tmp/openclaw/uploads/` 目录下

**正确方法（已验证）：**

```
# Step 1: 复制文件到 uploads 目录
# cp /path/to/images/*.jpg /tmp/openclaw/uploads/

# Step 2: 点击上传按钮触发 file chooser
browser(action="snapshot")  # 获取上传按钮 ref
browser(action="act", kind="click", ref="{upload_btn_ref}")  # e.g. ref=e8 "上传图文"

# Step 3: 通过 browser upload 上传文件
browser(action="upload", paths=[
    "/tmp/openclaw/uploads/img1.jpg",
    "/tmp/openclaw/uploads/img2.jpg",
    "/tmp/openclaw/uploads/img3.jpg"
])

# Step 4: 等待上传处理完成（页面显示"加载中"→编辑器就绪）
browser(action="act", kind="wait", timeMs=10000)

# Step 5: 验证 — snapshot 应显示"已添加N张图片"和编辑区按钮
browser(action="snapshot")
```

**⚠️ 失败方法（不要使用）：**

**方法 B（已废弃）：通过 evaluate 直接设置 file input**

```
browser(action="act", kind="evaluate", fn="""async () => {
    const input = document.querySelector('input[type="file"][accept*="image"]');
    if (!input) return 'file input not found';

    const files = [
        '/path/to/img1.jpg',
        '/path/to/img2.jpg',
        '/path/to/img3.jpg',
    ];

    // 通过 Playwright 的 setInputFiles（如果可用）
    // 或通过 DataTransfer API
    const dt = new DataTransfer();
    for (const path of files) {
        const resp = await fetch('file://' + path);
        const blob = await resp.blob();
        const file = new File([blob], path.split('/').pop());
        dt.items.add(file);
    }
    input.files = dt.files;
    input.dispatchEvent(new Event('change', { bubbles: true }));
    return 'files set: ' + files.length;
}""")
```

> **注意**：方法 B 在某些浏览器安全策略下可能被阻止。如果方法 B 失败，使用方法 A。

### 5.3 等待上传完成

图片上传后，抖音需要处理（压缩、生成缩略图等）。等待信号：

```
# 等待编辑器按钮出现（表示上传处理完成）
browser(action="act", kind="wait", timeMs=5000)

# 检查是否出现了"暂存离开"/"发布"按钮
browser(action="snapshot")
```

**上传完成标志：**
- 页面底部出现「暂存离开」「发布」按钮
- 图片预览区域显示已上传的图片缩略图
- 无"上传中"或进度条

### 5.4 调整封面

如果需要指定封面（从已上传图片中选择）：

```
# 点击封面设置区域
browser(action="act", kind="click", ref="{cover_area_ref}")

# 等待封面选择弹窗
browser(action="act", kind="wait", timeMs=2000)

# 选择指定图片作为封面（通常点击图片缩略图即可）
browser(action="act", kind="click", ref="{target_image_ref}")

# 确认选择
browser(action="act", kind="click", ref="{confirm_btn_ref}")
```

### 5.5 重试机制

如果上传失败：
- 第1次失败：等待 10 秒后重试
- 第2次失败：等待 30 秒后重试
- 第3次失败：**停止**，截图，报告，转"待 Daniel 接管"

### 5.6 截图确认

```
browser(action="screenshot", path="/tmp/douyin_step5_assets_uploaded.png")
```

---

## Step 6: 暂存离开（默认终点）

**目标：点击「暂存离开」将内容保存到草稿箱**

### 6.1 关闭遮挡弹窗

提交前先处理可能的弹窗（共创中心推广等）：

```
browser(action="act", kind="evaluate", fn="""() => {
    const els = document.querySelectorAll('*');
    for (const el of els) {
        const t = el.textContent.trim();
        // 只关闭"我知道了"类提示，不要误关"确认"类弹窗
        if (t === '我知道了' && el.offsetParent !== null && el.children.length === 0) {
            el.click();
            return 'closed: ' + t;
        }
    }
    return 'no popup';
}""")
```

> ⚠️ **安全原则**：只关闭明确无害的提示弹窗（"我知道了"）。
> **绝对不要**关闭包含"确认""放弃"等有歧义文案的弹窗——先截图发给 Daniel 确认。

### 6.2 找到暂存按钮

```
browser(action="snapshot")
```

在 snapshot 中查找以下任一按钮：
| 文案 | selector |
|------|----------|
| `暂存离开` | 图文页最常见 |
| `存草稿` | 视频页常见 |
| `草稿` | 部分版本 |

### 6.3 点击暂存

```
# 使用 snapshot 中获取的 ref
browser(action="act", kind="click", ref="{draft_button_ref}")
```

### 6.4 处理提交后弹窗

点击后可能出现确认弹窗：

```
browser(action="act", kind="wait", timeMs=3000)

# 检查是否有"暂存"确认按钮
browser(action="act", kind="evaluate", fn="""() => {
    const els = document.querySelectorAll('*');
    for (const el of els) {
        const t = el.textContent.trim();
        if ((t === '暂存' || t === '确认' || t === '我知道了')
            && el.offsetParent !== null && el.children.length === 0) {
            el.click();
            return 'clicked: ' + t;
        }
    }
    return 'no post-submit popup';
}""")
```

### 6.5 等待成功信号

```
browser(action="act", kind="wait", timeMs=5000)
```

**成功标志：**
- URL 跳转到草稿管理页 `content/manage`
- 页面出现"保存成功""草稿已保存"等文字
- 上传页面关闭

### 6.6 重试机制

如果暂存失败：
- 检查是否按钮被禁用 → 可能内容未填完整
- 检查是否有报错弹窗 → 截图发给 Daniel
- 第1次失败：等待 5 秒重试
- 第2次失败：等待 10 秒重试
- 第3次失败：**停止**，截图，报告

### 6.7 最终截图确认

```
browser(action="screenshot", path="/tmp/douyin_step6_draft_saved.png")
```

---

## 📤 确认回传（Step 7: 汇报）

发布流程结束后，向 Daniel 发送标准报告：

```
📋 抖音发布报告
━━━━━━━━━━━━━━
📌 标题：{title}
📝 描述：{desc[:80]}...
🏷️ 话题：{tags}
🖼️ 素材：{count} 张图片 / 视频
📐 封面：{cover_status}
✅ 状态：已存草稿 / 待确认发布 / 待接管
📸 截图：{screenshot_path}
🔗 草稿管理：https://creator.douyin.com/creator-micro/content/manage
```

附上最终截图作为确认凭证。

---

## 🚀 发布流程（仅在 Daniel 确认后执行）

如果 Daniel 确认要发布（而非只存草稿），替换 Step 6：

### 6-Alt: 点击发布

```
# 找到发布按钮
browser(action="snapshot")
# 查找 "button:has-text('发布')" 的 ref

# 点击发布
browser(action="act", kind="click", ref="{publish_button_ref}")
```

发布后等待成功信号（同 6.5），截图确认。

---

## 🔧 错误处理总表

| 失败点 | 重试策略 | 停止条件 |
|--------|---------|---------|
| 登录检测 | 重新打开页面 | 转人工扫码 |
| 二维码登录 | 等待 Daniel | 超时120秒 |
| 文件不存在 | 报告缺失文件 | 立即停止 |
| 格式不支持 | 报告并建议转换 | 立即停止 |
| 页面加载超时 | 刷新重试 | 3次失败 |
| 弹窗干扰 | 关闭提示弹窗 | 误关严重弹窗则停止 |
| 标题填写失败 | 重试 | 3次失败 |
| 描述填写失败 | 重试 | 3次失败 |
| 图片上传失败 | 指数退避重试 | 3次失败 |
| 封面设置失败 | 跳过（非阻塞） | — |
| 暂存按钮未找到 | 检查文案变体 | 3次失败 |
| 暂存后无成功信号 | 检查草稿箱 | 3次失败 |
| 验证码/滑块 | **立即停止** | 等 Daniel 处理 |
| 频率限制 | **立即停止** | 等30分钟 |

---

## 🔗 平台入口速查

| 页面 | URL |
|------|-----|
| 创作者首页 | `https://creator.douyin.com/creator-micro/home` |
| 图文发布 | `https://creator.douyin.com/creator-micro/content/upload?default-tab=3` |
| 视频发布 | `https://creator.douyin.com/creator-micro/content/upload` |
| 草稿管理 | `https://creator.douyin.com/creator-micro/content/manage` |

---

## 📝 发布时间建议

| 时段 | 推荐度 |
|------|--------|
| 7:00-9:00 | ⭐⭐⭐ |
| 11:30-13:00 | ⭐⭐⭐ |
| 17:30-19:00 | ⭐⭐⭐ |
| 20:00-22:00 | ⭐⭐⭐⭐⭐ |
| 22:00-00:00 | ⭐⭐⭐⭐ |

---

## 📁 文件结构

```
douyin-publish/
├── SKILL.md                          ← 本文件（workflow 主文件）
├── references/
│   ├── platform-rules.md             ← 完整平台规则
│   ├── handoff-and-human-trace.md    ← 接管规则与人类痕迹规范
│   └── content-style-guide.md        ← 内容风格指南
└── templates/
    ├── desc-template.md              ← 描述排版模板
    └── video-script-template.md      ← 视频脚本模板
```

---

## 📝 "人类痕迹"最小规范

> 避免"机器人味"

- 描述不要全是同一种句式：允许1句短钩子 + 1-2句解释 + 1句CTA
- emoji **适度**：每2-3句1个
- 话题不要固定模板：1-2精准 + 1-2场景 + 0-1泛
- 避免堆"上热门/涨粉"等低质话题

---

*v2.0.0 (2026-04-17): 全面重构 — 从 Playwright 脚本迁移到 OpenClaw Browser 自动化*
*v2.0.1 (2026-04-17): Step 4 描述填写修复 — Slate.js 只能 execCommand 单次插入；Step 5 上传路径修复*
*v1.0.0 (2026-03-27): 初始版本，Playwright 脚本实现*
