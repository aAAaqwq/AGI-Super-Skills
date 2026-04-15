---
name: douyin-smart-publish
description: "抖音创作者平台智能发布（视频/图文）：内容适配→上传→填描述/#话题→封面→存草稿→截图回传确认。默认只存草稿；只有在 Daniel 明确确认后才允许点击发布。覆盖标题(≤55字)、描述(建议≤200字)、#话题标签(3-5个)、封面设置、定时发布、可见性、合拍/下载开关。Playwright 自动化。触发：'发抖音'、'抖音发布'、'douyin publish'、'抖音图文'、'抖音视频'、'发布短视频'。"
author: Daniel Li
---

# 抖音智能发布

> 📋 **发布前请确认内容合规**：`~/clawd/projects/MediaClaw/references/platforms/douyin.md`（社区公约11大类违规、AIGC标识、账号健康分）

## ⚠️ 默认发布策略

- **默认目标是存草稿，不是直接发布。**
- **只有 Daniel 明确确认后，才允许点“发布”。**
- 在自动化填完内容后，优先截图回传当前页面，确认标题/描述/封面/话题都正确。
- 如果遇到登录验证、滑块、频率限制、上传卡住，不要死磕；保留截图和当前状态，转为“待 Daniel 接管”。

## 平台入口

- **创作者中心**: https://creator.douyin.com
- **内容上传**: https://creator.douyin.com/creator-micro/content/upload
- **图文上传**: https://creator.douyin.com/creator-micro/content/upload?default-tab=3
- **登录方式**: 抖音 APP 扫码 / 手机号验证码

## 发布类型

| 类型 | URL参数 | 说明 |
|------|---------|------|
| 视频 | `default-tab=1`(默认) | 短视频/长视频 |
| 图文 | `default-tab=3` | 图片轮播+描述 |
| 全景视频 | `default-tab=3`(全景) | VR视频 |
| 文章 | `default-tab=4` | 长文(≤8000字+30图) |

## 排版规则

### 视频规范

| 项 | 规则 |
|----|------|
| 时长 | 15秒-60分钟（≥15分钟需粉丝≥1000） |
| 格式 | MP4, WebM（推荐MP4 H.264） |
| 分辨率 | ≥720×1280，推荐1080×1920，最高4K |
| 帧率 | ≤60fps，推荐30fps |
| 大小 | ≤16GB |
| 画幅 | 9:16竖屏(最优) / 16:9横屏 / 3:4 / 4:3 |

### 图文规范

| 项 | 规则 |
|----|------|
| 图片数量 | 2-35张 |
| 格式 | JPG, JPEG, PNG, WebP（**不支持GIF**） |
| 大小 | 单张≤50MB |
| 比例 | 推荐3:4或4:3，不建议超过1:2 |

### 描述/标题规范

| 项 | 规则 |
|----|------|
| 标题 | ≤55字（实测，超出截断显示） |
| 描述 | 建议≤200字（含话题标签） |
| 话题 | #话题名 格式，3-5个，精准在前泛在后 |
| @提及 | @用户名 增加互动 |
| POI定位 | 可添加位置（本地推荐加权） |
| emoji | 适度使用，每2-3句1个 |

### 封面规范

| 项 | 规则 |
|----|------|
| 视频封面 | 从视频帧选取 或 自定义上传(1080×1920) |
| 图文封面 | 从已上传图片中选择 |
| 推荐 | 竖版9:16，清晰大字，对比色 |

### AIGC标注要求（2023.9起）

- AI生成内容必须标注 "内容由AI生成"
- 虚构情节标注 "情景演绎，仅供娱乐"

## 内容适配模板

将内容转化为抖音格式时：

1. **标题/描述**：开头放核心信息(前3秒法则)，加emoji和话题标签
   ```
   核心卖点/痛点句 emoji

   补充说明(1-2句)

   #精准话题1 #精准话题2 #泛话题3
   ```
2. **话题策略**：1-2个精准话题 + 2-3个泛话题，避免无关话题(判标题党)
3. **描述字数**：控制在100-200字，简洁有力
4. **互动引导**：结尾加提问或CTA

## 发布流程

### 关键安全门：截图确认 → 再发布

- 自动化填完以后，**先截图**（作为确认凭证）。
- 默认只执行 **存草稿**。
- 只有收到 Daniel 明确确认，才允许切换到 `--mode publish`。

> 需要接管/风控/停手规则：见 `references/handoff-and-human-trace.md`

### 2026-03-27 实战验证结论（已跑通）

这份 skill 已经在真实抖音创作者后台完成过一次完整图文草稿测试，链路如下：

1. 复用 `storage_state` 登录态进入创作者后台
2. 成功上传 3 张图片
3. 成功填写标题
4. 成功填写描述
5. 成功点击草稿按钮并存入草稿箱

这次实战得到的**关键经验**：

- **先授权，再发布**：未登录时页面里可能根本没有上传控件，不能把“上传失败”误判成 selector 问题。
- **登录判断不能只看 URL**：即使 URL 已在 `creator-micro/*` 下，页面仍可能是扫码登录态；要同时检查页面文案/二维码区。
- **当前抖音图文页的草稿按钮文案可能不是 `存草稿`，而是 `暂存离开`**。
- **图文页存在真实 `input[type=file]`**，在授权成功后可直接上传；之前 `count=0` 的根因是登录页，不是上传能力缺失。

推荐排查顺序：
1. 先确认是否真的登录成功
2. 再确认 `input[type=file]` 是否存在
3. 再确认底部按钮文案是 `发布 / 暂存离开` 还是其他变体
4. 最后才改 selector


### 视频发布

```
1. 打开 creator.douyin.com/creator-micro/content/upload
2. 上传视频文件 (拖拽或点击)
3. 等待上传+转码完成
4. 选择/上传封面
5. 填写描述 + #话题 + @提及
6. 设置：可见性(公开/好友/私密)、合拍、下载
7. 可选：定时发布(最远10天)、POI定位
8. 点击 [发布] 或 [存草稿]
```

### 图文发布

```
1. 打开 creator.douyin.com/creator-micro/content/upload?default-tab=3
2. 上传图片 (2-35张，拖拽排序)
3. 选择封面图
4. 填写描述 + #话题
5. 设置发布选项
6. [发布] 或 [存草稿]
```

### 脚本用法

```bash
# 0) 冒烟检查（不上传，只打开页面+截图+输出关键信号）
python scripts/publish.py doctor --no-headless \
  --screenshot /tmp/douyin_doctor.png

# 1) 从 daily-content 产物直接发布到草稿箱（推荐，SOP直连）
#   - 支持 md/txt 两种格式：
#     /home/aa/clawd/docs/daily-content/YYYY-MM-DD/douyin/douyin-content-YYYY-MM-DD.md
#     /home/aa/clawd/docs/daily-content/YYYY-MM-DD/douyin/douyin-3posts-YYYY-MM-DD.txt
#   - pick=1/2/3 选择第几条
#   - 默认 mode=draft（只存草稿）
python scripts/publish.py daily \
  --source "/home/aa/clawd/docs/daily-content/2026-03-24/douyin/douyin-content-2026-03-24.md" \
  --pick 1 \
  --type image \
  --files "/path/to/img1.jpg,/path/to/img2.jpg" \
  --mode draft

# 2) 视频发布（草稿模式）
python scripts/publish.py video \
  --file "/path/to/video.mp4" \
  --title "可选标题（≤55字）" \
  --desc "描述文字 #话题1 #话题2" \
  --cover "/path/to/cover.jpg" \
  --mode draft

# 3) 图文发布
python scripts/publish.py image \
  --files "/path/to/img1.jpg,/path/to/img2.jpg" \
  --title "可选标题（≤55字）" \
  --desc "图文描述 #话题1" \
  --mode draft

# 4) 定时发布（⚠️仅在 Daniel 明确确认后使用 publish）
python scripts/publish.py daily \
  --source "/home/aa/clawd/docs/daily-content/2026-03-25/douyin/douyin-3posts-2026-03-25.txt" \
  --pick 2 \
  --type video \
  --file "/path/to/video.mp4" \
  --schedule "2026-03-27 21:30" \
  --mode publish
```

## UI 选择器参考（React SPA，类名含hash）

| 元素 | 定位策略 | 说明 |
|------|----------|------|
| 上传区域 | `input[type="file"]` / `button:has-text("上传视频")` | 文件上传；**先确认已登录**，未登录时可能为 0 |
| 描述输入 | `[class*="desc"] [contenteditable]` / `textarea` / `[placeholder*="添加作品描述"]` | 描述编辑区 |
| 话题输入 | 描述区中输入 `#` 触发话题搜索 | 话题弹窗选择 |
| 封面选择 | `[class*="cover"]` / 封面编辑弹窗 | 视频帧或自定义 |
| 发布按钮 | `button:has-text("发布")` | 发布确认 |
| 草稿按钮 | `button:has-text("存草稿")` / `button:has-text("暂存离开")` | **当前实测图文页常见为 `暂存离开`** |
| 定时开关 | `[class*="schedule"]` / 时间选择器 | 定时发布 |
| 可见性 | `[class*="permission"]` / radio按钮 | 公开/好友/私密 |
| 图片排序 | 拖拽操作 | 调整图片顺序 |

> **注意**：抖音使用React + CSS Modules，class名含hash前缀，优先用文本匹配(`has-text`)或`placeholder`定位。

## 发布时间建议

| 时段 | 推荐度 | 说明 |
|------|--------|------|
| 7:00-9:00 | ⭐⭐⭐ | 早通勤 |
| 11:30-13:00 | ⭐⭐⭐ | 午休 |
| 17:30-19:00 | ⭐⭐⭐ | 下班通勤 |
| 20:00-22:00 | ⭐⭐⭐⭐⭐ | 晚间黄金档 |
| 22:00-00:00 | ⭐⭐⭐⭐ | 睡前 |

## 错误处理

| 错误 | 处理 |
|------|------|
| 登录过期 | 提示扫码，`--headless false` |
| 滑块验证 | 暂停等待手动完成 |
| 上传超时 | 重试3次，指数退避(10s/30s/90s) |
| 转码失败 | 检查格式/分辨率，降级重传 |
| 描述过长 | 截断到200字并警告 |
| 频率限制 | 建议每天≤3条，间隔≥30分钟 |

## 算法要点

- 发布后2小时内"赛马机制"决定推荐量
- **完播率** > 点赞率 > 评论率 > 转发率
- 前3秒决定用户是否继续观看
- 话题标签影响推荐池分配
- 竖屏内容推荐权重更高

## 发布前检查清单

- [ ] 描述 ≤200字，含3-5个话题标签
- [ ] 视频：MP4/WebM格式，≤16GB，≤60分钟
- [ ] 图文：2-35张，JPG/PNG/WebP，每张≤50MB
- [ ] 封面清晰，竖版9:16最优
- [ ] 无其他平台水印
- [ ] AI内容已标注（如适用）
- [ ] 非搬运内容
- [ ] 已截图回传确认
- [ ] 若使用 `daily` 模式：已核对 `pick` 对应的是正确那条内容

## 文件结构

```
douyin-smart-publish/
├── SKILL.md
├── scripts/
│   └── publish.py          # Playwright 自动发布脚本
├── references/
│   └── platform-rules.md   # 完整平台规则
└── templates/
    └── desc-template.md    # 描述/话题排版模板
```
