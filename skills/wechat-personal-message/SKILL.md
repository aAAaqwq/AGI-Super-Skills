---
name: wechat-personal-message
description: 微信自动化助手 — 激活微信 → 置顶窗口 → 搜索联系人 → Vision OCR识别 → 进入聊天 → 自动发送。全程本地运行，支持 OCR 视觉反馈校验，可被外部工具调用。
triggers:
  - 微信自动发消息
  - 微信OCR识别
  - 微信自动化
  - wechat automation
  - 微信关键词回复
  - 微信发送消息
  - 微信Mac自动化
---

# 微信自动化助手 (WeChat Automator) v4.2

## 功能概述

一套完整的微信自动化工具，基于 macOS 原生能力实现，全程本地运行：

```
激活微信 → 前置置顶窗口 → 搜索联系人 → 截图聊天窗口 → Vision OCR识别 → 关键词匹配 → 自动回复 → 发送消息
```

## 依赖与环境

| 依赖 | 要求 | 安装命令 |
|------|------|---------|
| macOS | 10.15+ | — |
| **pyobjc** | 必须 | `pip3 install pyobjc` |
| **cliclick** | 必须 | `brew install cliclick` |
| Vision Framework | 内置 | macOS 10.15+ 自带 |
| screencapture | 内置 | macOS 系统自带 |

## 权限要求

请按以下步骤开启权限：
1. **辅助功能权限**：`系统设置 → 隐私与安全性 → 辅助功能 → 终端 → 开启`
2. **屏幕录制权限**：`系统设置 → 隐私与安全性 → 屏幕录制 → 终端 → 开启`

---

## 快速开始

### 检查系统环境

```bash
python3 ~/.hermes/skills/openclaw-imports/wechat-personal-message/scripts/wechat_automator.py check
```

### 完整自动化流程（OCR + 自动回复）

```bash
python3 ~/.hermes/skills/openclaw-imports/wechat-personal-message/scripts/wechat_automator.py run -c 张三
```

### 仅发送消息（不 OCR）

```bash
python3 ~/.hermes/skills/openclaw-imports/wechat-personal-message/scripts/wechat_automator.py send -c 张三 -m "晚上8点开会"
```

---

## 核心函数（供外部调用）

### `execute_wechat_automation()`

主执行函数，支持完整自动化流程。

**参数：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `contact_name` | str | ✅ | 联系人名称（备注名或微信号） |
| `keyword_dict` | dict | ❌ | 关键词字典，格式 `{"类别": ["关键词1", "关键词2"]}` |
| `default_reply` | str | ❌ | 默认回复文案 |
| `custom_replies` | dict | ❌ | 自定义回复覆盖，格式 `{"类别": "回复内容"}` |
| `chat_region` | tuple | ❌ | 截图区域 `(x, y, w, h)` |
| `auto_reply` | bool | ❌ | 是否自动回复，默认 True |
| `verbose` | bool | ❌ | 是否输出详细日志，默认 True |

**返回值：** 执行结果字典

**示例：**

```python
from wechat_automator import execute_wechat_automation

result = execute_wechat_automation(
    contact_name="张三",
    keyword_dict={
        "价格": ["多少钱", "价格", "报价"],
        "合作": ["合作", "代理", "加盟"],
        "问候": ["你好", "您好", "在吗"]
    },
    default_reply="感谢您的消息，我会尽快回复您。"
)

print(result["success"])        # True/False
print(result["matched_category"])  # 匹配到的类别
print(result["recognized_texts"]) # OCR 识别的文本列表
print(result["reply_content"])   # 发送的回复内容
```

### `send_text_message()`

快捷函数：仅发送文本消息（不 OCR）。

```python
from wechat_automator import send_text_message

success = send_text_message("张三", "晚上8点开会")
```

### `check_system_ready()`

检查系统环境是否就绪。

```python
from wechat_automator import check_system_ready

status = check_system_ready()
print(status["ready"])  # True/False
```

---

## 技术实现细节

### AppleScript 键盘操作（关键实现）

⚠️ **重要**：macOS AppleScript 的特殊键必须用 `key code` 方式，不能用 `keystroke "return"`：

```python
# ✅ 正确方式：key code
key_code_map = {
    "return": 36,    # 回车
    "enter": 36,     # 回车（同 return）
    "escape": 53,    # ESC
    "tab": 48,       # Tab
    "space": 49,     # 空格
    "backspace": 51, # 退格
    "up": 126,       # 上箭头
    "down": 125,     # 下箭头
    "left": 123,     # 左箭头
    "right": 124,    # 右箭头
}

script = '''
tell application "System Events"
    key code 36  -- return
end tell
'''
```

### 动态窗口坐标计算（关键！）

⚠️ **绝对禁止硬编码坐标**。微信窗口位置不固定，必须先获取窗口实际 rect，再按比例计算输入框坐标：

```python
# 1. 获取微信窗口 rect: (x, y, width, height)
script = '''
tell application "System Events"
    tell process "WeChat"
        get {position, size} of window 1
    end tell
end tell
'''
# 返回格式: {{0, 22}, {1514, 1006}} → (x=0, y=22, w=1514, h=1006)

# 2. 按窗口比例计算输入框位置（约窗口右下区域）
input_x = win_x + int(win_w * 0.75)   # x方向约75%处
input_y = win_y + int(win_h * 0.92)   # y方向约92%处

# 3. 用 process 块内 click 执行点击
script = f'''
tell application "System Events"
    tell process "WeChat"
        click at {{{input_x}, {input_y}}}
    end tell
end tell
'''
```

### OCR 识别（Vision Framework）⚠️ pyobjc API 注意事项

**新版 pyobjc (3.x+) API 与旧版不同，以下是已验证可用的 API：**

```python
from Vision import VNRecognizeTextRequest, VNImageRequestHandler
from AppKit import NSImage

# 1. 加载图片（必须用 alloc().initWithContentsOfFile_）
img = NSImage.alloc().initWithContentsOfFile_(image_path)

# 2. 创建识别请求并设置回调（不能用 setCompletionHandler_）
recognized_texts = []
def completionHandler(request, error):
    if error:
        return
    for observation in request.results() or []:
        text = observation.text()
        if text and text.strip():
            recognized_texts.append(text)

request = VNRecognizeTextRequest.alloc().initWithCompletionHandler_(completionHandler)
request.setRecognitionLanguages_(["zh-Hans", "en-US"])
request.setUsesLanguageCorrection_(True)

# 3. 执行识别
img_data = img.TIFFRepresentation()
handler = VNImageRequestHandler.alloc().initWithData_options_(img_data, {})
handler.performRequests_error_([request], None)
```

**常见错误：**
- `initWithData_` → 应为 `initWithData_options_`
- `initWithContentsOfFile_()` → 应先用 `alloc()` 再调用
- `setCompletionHandler_()` → 应在 `initWithCompletionHandler_` 时传入回调
- `initWithImage_options_` → 不存在，必须用 `initWithData_options_`

### 截图（screencapture）

```bash
# 截取指定区域
screencapture -x -R "x,y,width,height" output.png
```

---

## 执行流程详解

```
1. send_text_message(contact, message)
   ├─ 保存原始剪贴板（最开始保存，避免被 search_contact 污染）
   ├─ activate_wechat()
   ├─ bring_to_front()
   ├─ search_contact(name)  ← 会写入联系人名到剪贴板
   ├─ send_message(message, original_clipboard)  ← 用保存的原始值
   └─ 恢复原始剪贴板

2. search_contact(name)
   ├─ write_to_clipboard(name)
   ├─ Cmd+F 打开搜索框
   ├─ Cmd+V 粘贴联系人名
   ├─ 按 Enter 进入聊天（✅ 用 Enter，不依赖坐标点击！）
   └─ ESC 关闭悬浮资料卡（如果出现）

3. send_message(text)
   ├─ 写入消息到剪贴板
   ├─ 多点位尝试点击输入框（75%, 50%, 居中）
   ├─ OCR 确认输入框就绪
   ├─ Cmd+V 粘贴消息
   ├─ OCR 确认文本已粘贴
   ├─ Enter 发送（微信 Mac 版用 Enter 发送）
   └─ OCR 验证消息出现在聊天中
```

---

## 常见问题

**Q: 消息发到了搜索聊天记录面板而不是聊天窗口？**
A: 这是 v4.0 修复的关键问题。当 OCR 同时检测到"发送人"+"日期"+"搜索聊天记录"+"暂无"时，说明进入了「搜索聊天记录」面板而非真正的聊天窗口。`ocr_check_chat_entered()` 已内置此判断，`send_message()` 也会检测并按 ESC 关闭。但根本原因是：该联系人在微信里没有直接的私聊历史记录，微信只能搜索到群聊里的消息。这种情况无法自动化解决，需要先在微信里手动给该联系人发一条消息建立私聊，之后才可以用自动化发送。

**Q: AI实赣派刘拾柒/AI星辰社朱老师发消息失败？**
A: v4.1 修复了此问题。新逻辑：搜索后点击第一个结果 → 立即尝试发消息（不验证是否真正进入聊天窗口）。即使该联系人没有私聊记录，只要搜索结果列表第一项是该联系人，就会尝试发送。OCR 验证改为发送后验证，如果消息内容出现在屏幕上即认为成功。

**Q: 搜索后 Enter 进入的是公众号文章页而不是聊天窗口？**
A: 这种情况发生在搜索结果第一个是「AI搜索/网络结果」（公众号文章）时。v3.8 修复：当 Enter 未进入聊天时，代码会重新搜索、OCR 识别目标联系人在列表中的实际索引、点击正确坐标后再 Enter。OCR 定位联系人位置（支持部分名称匹配），搜索列表每项约 28 像素高。

**Q: 消息发到了搜索框/悬浮资料卡而不是聊天窗口？**
A: 这是 v3.5 修复的核心问题。搜索后按 Enter 会打开悬浮资料卡。正确流程是：① Cmd+F 搜索 ② Cmd+V 粘贴 ③ ↓ 方向键选中列表项 ④ Enter 进入聊天 ⑤ OCR 验证是否真的是聊天窗口（有输入框UI）。已内置自动修正逻辑。

**Q: 返回 "returnescapereturn" 文字？**
A: 说明 `press_key("return")` 用了 `keystroke` 方式而非 `key code`。已修复，特殊键必须用 key code。

**Q: `get_wechat_window_rect()` 返回 None？**
A: 微信窗口信息可能无法通过 System Events 获取，此时使用默认屏幕尺寸 (1920×1080) 作为 fallback，虽然可能不精准但通常仍可工作。如持续失败，可手动指定 `chat_region` 参数。

**Q: 消息粘贴到输入框了但发送后对方没收到？**
A: 检查是否用了错误的发送键 — 微信 Mac 版必须用 **`Enter（Return）`** 发送消息，单独按 Return 是换行。v3.6 已修复此问题。

**Q: OCR 报错 `VNImageRequestHandler has no attribute initWithData_`？**
A: 这是 pyobjc 版本问题。新版 API 必须是 `initWithData_options_`（带 options 参数），且必须先 `alloc()` 再 `init...`。

**Q: OCR 验证说"仍在搜索预览"但实际右侧已显示聊天内容？**
A: 这是 v3.8 修复的关键问题。微信 Mac 搜索后，即使左侧搜索UI还在，右侧也可能已显示聊天记录（联系人名+时间戳+消息内容）。`ocr_check_chat_entered()` 新增 `has_right_panel_preview` 判断：当检测到搜索UI存在但同时有联系人名、时间戳、多段文字（>10段）时，认为已进入「聊天预览」状态，可以直接发送消息。

**Q: 搜索后点击联系人，但没进入聊天窗口而是弹出了悬浮资料卡？**
A: 这是 v3.3 修复的问题：搜索后按 Return 会直接打开悬浮的资料卡。正确的做法是：① 先按一次 `↓` 方向键选中列表项 ② 再单击/双击联系人区域进入聊天，而不是按 Return。已加入 OCR 验证自动修正逻辑。

**Q: 发送消息后，剪贴板里残留了联系人名称？**
A: 这是 v4.2 修复的关键 bug。`search_contact()` 会把联系人名称写入剪贴板（用于粘贴搜索），如果保存原始剪贴板的时机不对，恢复时就变成了联系人名称。v4.2 修复：`send_text_message()` 在整个流程的**最开始**就保存原始剪贴板，确保恢复的是真正原始的内容。

---

## 版本历史

- **v4.2 (2026-05-22)** — 剪贴板污染修复 + Enter 进入聊天
  - 🐛 修复：剪贴板污染 bug — `send_text_message()` 在 `search_contact()` 之后保存原始剪贴板，但 `search_contact()` 会写入联系人名称到剪贴板，导致恢复时残留联系人名而非原始内容。修复：最开始就保存原始剪贴板。
  - 🐛 修复：搜索后点击「窗口右侧 75% 位置」会点到聊天列表里的其他联系人。修复：改用 **Enter 键** 直接进入聊天，不再依赖坐标点击。
  - ✅ 实测：5位好友批量发送全部成功，OCR 验证确认消息送达，剪贴板恢复正常。

- **v4.1 (2026-05-21)** — 无私聊记录联系人发送逻辑
  - 🐛 修复：搜索后直接点第一个结果 → 发消息，不再验证是否真正进入聊天窗口
  - 🐛 修复：`search_contact()` 移除 OCR 聊天验证，点击第一个结果后直接返回成功
  - 🐛 修复：`cliclick` 坐标浮点数报错 — 所有坐标计算后取 `int()`
  - ⚡ 逻辑变更：搜索后尝试点击窗口右侧聊天区域(65%, 75%) + ESC 关闭悬浮资料卡 → 直接发消息
  - ✅ 实测：`AI实赣派刘拾柒`（无私聊记录）成功发送消息，OCR 确认「这是来自拾柒老师的爱马仕Al...」出现在聊天中

- **v4.0 (2026-05-21)** — 搜索聊天记录面板识别 + 联系人无私聊限制
  - 🐛 修复：`ocr_check_chat_entered()` 新增"搜索聊天记录面板"判断 — 当 OCR 检测到"发送人"+"日期"+"搜索聊天记录"+"暂无"时，认为是搜索聊天记录面板而非真正聊天窗口
  - 🐛 修复：`send_message()` 也会检测并关闭搜索聊天记录面板
  - ⚠️ 重要限制：如联系人没有私聊历史记录，微信搜索后只能进入「搜索聊天记录」面板，无法主动发起私信，必须先手动建立私聊
  - 🐛 修复：`search_contact()` 优先匹配直接联系人（排除"包含"条目），避免点击到群聊里的成员名
  - 🐛 修复：点击位置改为偏左下(55%, 88%)，更接近真实输入框位置

- **v3.8 (2026-05-21)** — 搜索预览状态精确判断 + 点击定位修复
  - 🐛 修复：Enter后OCR验证认为"仍在搜索预览"但实际右侧已显示聊天内容的情况
  - ✨ 新增：`has_right_panel_preview` 判断 — 当搜索UI可见但右侧显示「联系人名+时间戳+消息内容」时，认为已进入聊天预览，可直接发消息
  - 🐛 修复：fallback点击逻辑不再硬编码位置，而是用OCR在搜索列表中找到目标联系人的实际索引，再计算点击坐标
  - 🔑 判断条件：`contact_name in text or text in contact_name` 做部分匹配定位
  - ✨ 搜索列表每项高度约28像素，从窗口顶部(8%)开始计算

- **v3.7 (2026-05-21)** — 搜索结果分类识别 + 智能选择
  - 🐛 修复：搜索结果第一个可能是「AI搜索/网络结果」（公众号文章）而非实际群聊/好友
  - ✨ 新增 `parse_search_results()` — 解析OCR结果，识别「群聊/AI搜索/公众号/好友」类型
  - ✨ 新增 `find_target_result()` — 优先选择「群聊」类型，排除AI搜索和公众号
  - ✨ 新增 `navigate_to_search_result()` — 用方向键移动到目标条目
  - 🔑 搜索结果详情页特征：`"AI搜索", "全部 文章", "账号 文章", "划线 视频", "搜一搜"`
  - 🔑 悬浮资料卡特征：`"微信号", "地区", "朋友圈", "更多", "个性签名"` + 无输入框

- **v3.6 (2026-05-21)** — 关键流程修正
  - 🐛 修复：搜索后**不要按 ↓ 方向键**，否则会跳过好友（第一项）选中群聊（第二项）
  - 🐛 修复：微信 Mac 版发送键是 **`Enter（Return）`**，不是 Cmd+Return
  - ✅ 实测：成功发送消息给朱子函，OCR 确认进入正确好友聊天
  - ✨ 改用 `cliclick` 替代 osascript click，执行更稳定
  - ✨ 新增 `double_click_at坐标()` 和 `cliclick_wait()` 支持双击和等待
  - ✨ 重写 `ocr_check_chat_entered()` — 区分悬浮资料卡和真正聊天窗口
  - 🔑 悬浮资料卡特征：有"微信号/地区/朋友圈"但无输入框
  - 🔑 真正聊天窗口特征：有"输入/发送/图片/表情"等UI元素，或有联系人名+时间戳
  - ✨ `search_contact()` 现在用 Enter 进入聊天（比双击更可靠），失败后自动修正
  - ✨ `send_message()` 多点位扫描输入框 + 每步 OCR 验证
  - ✅ 实测：刘时佶聊天窗口进入成功，OCR 确认显示「这是测试消息」

- **v3.4 (2026-05-21)** — OCR 修复 + Cmd+Return 发送键修复
  - 🐛 修复：pyobjc 新版 OCR API 全部更新（`initWithData_options_`、`initWithCompletionHandler_` 等）
  - 🐛 修复：微信 Mac 版发送键必须是 `Cmd+Return`，单独 `Return` 只换行不发送
  - ✨ 新增：`ocr_guided_send_message()` — 每步 OCR 验证 + 自动修正的发送流程
  - ✨ 新增：`click_input_box_smart()` — 智能扫描窗口底部定位输入框
  - ✨ 新增：`ensure_in_chat_window()` — OCR 验证是否已进入聊天，未进入则自动修正
  - ✨ 新增：`ocr_verify_message_sent()` — 发送后 OCR 验证消息是否出现在聊天中
  - ✨ 新增：OCR 验证流程嵌入 search_contact 和 send_message 每一步
  - ✅ 实测：刘时佶成功收到消息，OCR 确认屏幕显示「这是测试消息」

- **v3.3 (2026-05-21)** — 搜索进入聊天关键修复
  - 🐛 修复：搜索后直接按 Return 打开悬浮资料卡而非进入聊天，增加 ESC 关闭悬浮卡
  - 🔍 调试方法：截图 + vision 分析定位问题；单步日志确定失效步骤
  - 📌 已知问题：搜索后 ↓ 方向键选择逻辑仍不稳定，取决于列表初始焦点

- **v3.2 (2026-05-21)** — 发送流程关键修复
  - 🐛 修复：双击输入框后可能选中了文字，导致粘贴覆盖而非插入。增加第三次点击（偏左50px）重置光标位置
  - 🐛 修复：粘贴后等待时间从 0.3s 增至 0.5s，确保剪贴板内容完全写入
  - ✨ 新增：发送后额外一次点击确认，解除输入框状态
  - ✅ 实测：刘时佶成功收到自动发送的消息

- **v3.1 (2026-05-21)** — 关键 bug 修复
  - 🐛 修复：特殊键（return/escape）必须用 `key code` 而非 `keystroke`，否则会输入文字
  - 🐛 修复：`click_at坐标` 必须在 `tell process "WeChat"` 内执行才有权限
  - 🐛 修复：进入聊天窗口后等待时间从 0.5s 增至 2.0s
  - ✨ 新增：`click_at坐标()` 函数替代无效的旧实现
  - ✅ 实测：发送消息功能完全正常

- **v3.0 (2026-05-21)** — 完全重写
  - ✨ 基于 Vision Framework 重写 OCR 模块
  - ✨ 纯 AppleScript 实现，移除 cliclick 依赖
  - ✨ 新增 `execute_wechat_automation()` 主函数

---

## 维护者

贰拾（二十四）/ 辰景网络技术团队
