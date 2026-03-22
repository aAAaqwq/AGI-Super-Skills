---
name: jimeng-digital-human
description: 即梦AI数字人视频生成全流程自动化。通过浏览器自动化操控 jimeng.jianying.com 数字人界面，完成角色上传、音色选择、台词填入、视频生成和下载。触发场景：用户需要生成数字人视频、即梦数字人、AI数字人口播视频、数字人视频制作。依赖 jimeng-login skill 处理登录。
---

# 即梦数字人视频生成

## 概述

通过浏览器自动化（profile=openclaw）操控即梦数字人界面，完成从角色上传到视频生成、下载的全流程闭环。支持多镜头批量生成，输出按序命名的视频文件供 video-merge-send skill 合并。

## 前置条件

1. 浏览器已启动：`browser start profile=openclaw`
2. 即梦已登录（未登录时触发 `jimeng-login` skill）
3. 用户提供：人物图片、分镜台词（角色说 + 动作描述）
4. 分镜脚本（由 jimeng-storyboard skill 生成，或用户直接提供）

## 完整流程

### Step 1：导航到数字人页面

```
browser navigate url=https://jimeng.jianying.com/ai-tool/home?type=digitalHuman&workspace=0
```

等待 2 秒页面加载，截图确认：
- 已登录：左下角显示用户头像（非"登录"按钮）
- 未登录：触发 `jimeng-login` skill

### Step 2：选择角色（上传人物图片）

**检查是否有默认角色配置：**
读取 `TOOLS.md` 中的 `jimeng-digital-human` 配置段，检查是否已有默认角色图片路径。

**有默认配置时：** 询问用户"是否使用默认角色（田总形象）？"
- 是 → 直接使用已保存的图片路径
- 否 → 请用户发送新图片

**无默认配置 / 用户发送新图片时：**

1. 点击"角色"按钮（snapshot 中找 `角色` 文本的 clickable 元素）
2. 弹出上传提示框："支持真人 & 动漫"
3. 找到图片上传 input：

```javascript
// 找到角色上传的 file input
() => {
  const inputs = document.querySelectorAll('input.file-input-OfqonL');
  const imageInputs = [];
  inputs.forEach((input, i) => {
    if (input.accept && input.accept.includes('image')) {
      const parent = input.closest('[class*="popover-open"]');
      imageInputs.push({ index: i, hasPopoverParent: !!parent });
    }
  });
  return imageInputs;
}
```

4. 复制用户图片到上传目录并上传：

```bash
mkdir -p /tmp/openclaw/uploads
cp <用户图片路径> /tmp/openclaw/uploads/avatar.png
```

```
browser upload selector=".lv-popover-open input.file-input-OfqonL" paths=["/tmp/openclaw/uploads/avatar.png"]
```

5. 等待 3 秒，截图确认角色区域已显示人物图片（不再是"+ 角色"占位）
6. **用户确认后保存为默认：** 将图片路径写入 `TOOLS.md` 的 `jimeng-digital-human` 配置段

### Step 3：选择音色（配音）

**检查是否有默认音色配置：** 读取 `TOOLS.md` 中的默认音色设置。

**有默认配置时：** 询问用户"是否使用默认音色（豪放男子）？"
- 是 → 直接选择该音色
- 否 → 展示音色列表让用户选择

**选择音色操作：**

1. 点击角色名标签（snapshot 中 `开朗男大` 或当前音色名的 clickable 元素）
2. 弹出音色选择面板（tooltip grid），包含"全部音色"、"我的音色"、"收藏"三个 tab
3. 在 grid 中找到目标音色按钮，格式为 `button "音色名 多情感"`
4. 点击该按钮选中
5. 截图确认角色区域已更新音色名

**若音色不在当前页面：** 用筛选条件（性别/年龄/语言/声音特点）或滚动查找。

**音色参考列表见：** [references/voice-list.md](references/voice-list.md)

### Step 4：填入台词和动作描述

编辑区域包含两个部分：
- **角色说**：角色要说的台词内容
- **动作描述**（可选）：镜头语言和动作，如"镜头推进，他摘下眼镜，对着镜头笑着说"

操作步骤：
1. 点击文本编辑区域（snapshot 中的 `textbox`，包含"角色说"和"动作描述"占位文本）
2. 输入台词内容（角色说部分）
3. 换行后输入动作描述

**注意：** 编辑区是 contenteditable div（ProseMirror），不是标准 input。用 click + type 方式输入：

```
browser act kind=click ref=<textbox_ref>
browser act kind=type text="<台词内容>\n<动作描述>"
```

### Step 5：生成视频

1. 确认底部的生成按钮（橙色上箭头按钮）已激活（非 disabled 状态）
2. 点击生成按钮
3. 页面跳转到生成队列（URL 变为 `/ai-tool/generate?workspace=0`），等待视频渲染完成（通常 1-3 分钟）
4. 渲染期间可定期截图检查进度
5. 生成完成后，视频会显示在生成历史列表顶部

### Step 6：下载视频（关键闭环步骤）

视频生成完成后，通过以下流程下载到本地：

#### 6.1 准备下载目录

```bash
mkdir -p /tmp/openclaw/jimeng-videos
```

#### 6.2 设置下载 URL 拦截器

在点击下载按钮**之前**，先注入 JS 拦截器捕获视频直链：

```javascript
() => {
  window.__downloadUrls = [];

  // 拦截 fetch 请求中的视频 URL
  const origFetch = window.fetch;
  window.fetch = async function(...args) {
    const url = typeof args[0] === 'string' ? args[0] : args[0]?.url;
    if (url && (url.includes('.mp4') || url.includes('video') || url.includes('dreamnia'))) {
      window.__downloadUrls.push(url);
    }
    return origFetch.apply(this, args);
  };

  // 拦截动态创建的 <a> 标签（即梦下载机制）
  const observer = new MutationObserver((mutations) => {
    mutations.forEach(m => {
      m.addedNodes.forEach(n => {
        if (n.tagName === 'A' && n.href && n.download !== undefined) {
          window.__downloadUrls.push(n.href);
        }
      });
    });
  });
  observer.observe(document.body, { childList: true, subtree: true });

  return 'download interceptor ready';
}
```

#### 6.3 打开视频详情弹窗

在生成历史列表中，每个视频条目旁有一个**预览/展开按钮**（通常是缩略图左下的 button 元素）。

1. 做 snapshot（refs=aria），在列表中找到目标视频条目
2. 视频条目的结构特征：
   - 包含 `角色说` + 台词文本
   - 包含 `动作描述` + 描述文本
   - 包含时长信息（如 `9s`、`12s`）
   - 条目下方有一个 `button` 元素（展开按钮）
3. 点击该 button 打开视频详情 dialog

**示例：**
```
# 在 snapshot 中找到类似结构：
# generic → 角色说: "xxx台词" → 动作描述: "xxx" → "12s"
# 下方有 button [ref=eXXXX]
browser act kind=click ref=<button_ref>
```

#### 6.4 点击下载按钮

详情 dialog 打开后：

1. 做 snapshot，找到 `button "下载"` 元素（位于 dialog 右上角区域）
2. 点击下载按钮

```
browser act kind=click ref=<下载按钮_ref>
```

**注意：** 点击下载后会弹出**会员推广弹窗**（"无品牌水印直出"），这是正常现象。按 Escape 关闭即可，不影响下载。非会员下载的视频会带即梦水印。

#### 6.5 获取视频直链并下载

点击下载按钮后，等待 1-2 秒，然后读取拦截器捕获的 URL：

```javascript
() => {
  return {
    downloadUrls: window.__downloadUrls || [],
    count: (window.__downloadUrls || []).length
  };
}
```

返回结果中通常有两个 URL：
- **CDN 直链**（以 `https://v3-dreamnia.jimeng.com/` 开头）→ ✅ 用这个
- **blob URL**（以 `blob:https://jimeng.jianying.com/` 开头）→ ❌ 无法用 curl 下载

用 curl 下载 CDN 直链：

```bash
curl -L -o "/tmp/openclaw/jimeng-videos/<序号>_<标识>.mp4" "<CDN直链URL>"
```

**命名规范：** `<两位序号>_<镜头标识>.mp4`
- 示例：`01_hook.mp4`、`02_pain.mp4`、`03_solution.mp4`、`04_cta.mp4`
- 序号与分镜脚本的镜头序号对应

#### 6.6 验证下载

```bash
ls -la /tmp/openclaw/jimeng-videos/
ffprobe -v quiet -print_format json -show_format /tmp/openclaw/jimeng-videos/<文件名>.mp4
```

确认文件大小合理（通常 5-15MB）且格式正确。

#### 6.7 关闭详情弹窗

```
browser act kind=press key=Escape
```

或点击 dialog 的关闭按钮（`×`），回到生成列表页。

### Step 7：多镜头批量生成与下载

对于多镜头分镜脚本，有两种工作模式：

#### 模式A：逐个生成 + 逐个下载（推荐）

按分镜脚本顺序，对每个镜头重复 Step 4→5→6：

```
for 每个镜头 in 分镜脚本:
  1. 导航到数字人页面（角色和音色已保持选中）
  2. 清空编辑区，填入当前镜头的台词和动作描述
  3. 点击生成，等待完成
  4. 注入下载拦截器
  5. 打开详情 → 点击下载 → curl 保存
  6. 关闭详情，继续下一个镜头
```

#### 模式B：全部生成完毕后批量下载

1. 逐个镜头依次生成（Step 4→5 循环）
2. 全部生成完成后，在生成历史列表中按顺序逐个下载（Step 6 循环）
3. **注意**：生成历史列表按时间倒序排列（最新在最上面），需要从下往上依次下载

**每个镜头生成前，清空编辑区的方法：**

```
browser act kind=click ref=<textbox_ref>
browser act kind=press key=Meta+a
browser act kind=press key=Backspace
```

然后输入新内容。

### Step 8：交付与后续

所有镜头视频下载完成后：

1. **确认文件完整性：**
```bash
ls -la /tmp/openclaw/jimeng-videos/
# 确认文件数量与分镜数一致，文件大小合理
```

2. **通知用户：** 告知所有视频已下载到 `/tmp/openclaw/jimeng-videos/`

3. **衔接 video-merge-send skill：**
```bash
python3 skills/video-merge-send/scripts/merge_videos.py \
  -d /tmp/openclaw/jimeng-videos/ \
  -o /tmp/openclaw/jimeng-videos/final_merged.mp4 \
  --transition fade \
  --transition-duration 0.5
```

4. **发送到飞书：** 使用 feishu-media skill 或 message 工具发送合并后的视频

## 默认配置管理

在 `TOOLS.md` 中维护默认配置：

```markdown
### 即梦数字人 (jimeng-digital-human)

- **默认角色图片**: memory/tianzong-avatar.png
- **默认音色**: 豪放男子
- **生成模式**: 快速模式
- **下载目录**: /tmp/openclaw/jimeng-videos
```

首次使用后询问用户是否保存为默认，后续使用时优先提供默认选项。

## 关键技术细节

| 要素 | 说明 |
|------|------|
| 浏览器 profile | openclaw |
| 数字人页面 URL | `https://jimeng.jianying.com/ai-tool/home?type=digitalHuman&workspace=0` |
| 生成历史页面 URL | `https://jimeng.jianying.com/ai-tool/generate?workspace=0` |
| 图片上传方式 | `browser upload` + `/tmp/openclaw/uploads/` 中转目录 |
| 图片 input 选择器 | `.lv-popover-open input.file-input-OfqonL` 或 `input[accept*="image"]` |
| 音色面板触发 | 点击角色名标签（如"开朗男大"） |
| 文本编辑器类型 | ProseMirror contenteditable（非标准 input） |
| 生成按钮状态 | 有内容后从 disabled 变为 enabled |
| 下载机制 | 点击下载按钮 → 触发 fetch 获取 CDN 直链 → 创建 `<a>` 标签下载 |
| 视频 CDN 域名 | `v3-dreamnia.jimeng.com` |
| 视频格式 | H.264 MP4，960x960，60fps |
| 下载存储目录 | `/tmp/openclaw/jimeng-videos/` |
| 登录依赖 | jimeng-login skill |

## 下载 URL 说明

即梦视频下载时会产生两种 URL：

| URL 类型 | 格式 | 可否 curl |
|---------|------|----------|
| CDN 直链 | `https://v3-dreamnia.jimeng.com/...` | ✅ 可以直接 curl -L -o 下载 |
| Blob URL | `blob:https://jimeng.jianying.com/...` | ❌ 仅浏览器内有效 |

**始终使用 CDN 直链下载。** CDN URL 包含签名参数，有效期较短（通常几小时），需及时下载。

## 完整工作流（端到端）

```
1. jimeng-storyboard skill → 生成分镜脚本
2. jimeng-digital-human skill → 逐镜头生成 + 下载视频
   ├── Step 1: 导航到数字人页面
   ├── Step 2: 选择/上传角色
   ├── Step 3: 选择音色
   ├── Step 4-6: 循环（填台词 → 生成 → 下载）× N个镜头
   └── Step 8: 确认文件完整
3. video-merge-send skill → 合并视频 + 发送飞书
```

## 常见问题

| 问题 | 解决方案 |
|------|---------|
| 角色上传后仍显示"+ 角色" | popover 可能已关闭，重新点击"角色"触发上传 |
| aria-ref 点击超时 | 即梦 SPA 重渲染频繁，重新 snapshot 获取新 ref，或用 JS evaluate |
| 音色列表找不到目标 | 滚动列表或用筛选条件缩小范围 |
| 生成按钮 disabled | 确保已填入角色说内容（动作描述可选） |
| 视频生成超时 | 通常 1-3 分钟，超过 5 分钟截图检查是否有错误提示 |
| 下载按钮弹出会员推广 | 正常现象，按 Escape 关闭，视频仍会下载（带水印） |
| 拦截器没捕获到 URL | 确保在点击下载按钮**之前**注入拦截器 JS |
| CDN URL 下载失败 | URL 可能已过期，重新点击下载按钮获取新 URL |
| blob URL 无法下载 | 这是浏览器内存地址，无法用 curl，使用 CDN 直链 |
| 多镜头生成顺序混乱 | 严格按分镜序号命名文件（01_xx.mp4, 02_xx.mp4...） |
| 下载目录已有旧文件 | 每次新任务前清空 `/tmp/openclaw/jimeng-videos/` |
