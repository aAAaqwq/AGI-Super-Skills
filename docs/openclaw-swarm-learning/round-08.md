# 🧠 蜂群学习 Round 8/10 — 物理信息交互军团

**日期**: 2026-04-02 14:32 (Thu)
**角色**: 小a CEO
**主题**: 物理信息交互军团 — 设备、摄像头、屏幕、自动化交互、节点协作

---

## 一、物理信息交互军团全景

### 核心命题

AI Agent 不再局限于文本世界。通过 OpenClaw 的 **Nodes** 架构，Agent 可以：
- 📸 **看** — 摄像头拍照/录像，屏幕截图/录屏
- 🗣️ **说** — TTS 语音合成 + Talk Mode 连续对话
- 👂 **听** — 语音转文字 + 唤醒词检测
- 📍 **感知位置** — GPS 定位
- 🖥️ **控制屏幕** — Canvas UI 推送 + A2UI 动态界面
- 🤖 **远程执行** — 跨设备命令执行 + 脚本分发
- 📱 **读取手机** — 通知、照片、联系人、日历、短信、运动数据
- 🌐 **浏览网页** — headless 浏览器自动化

### 军团编制

| 角色 | 技术能力 | 对应工具/Skill | 当前状态 |
|------|---------|---------------|---------|
| **侦察兵** | 摄像头/屏幕/位置感知 | `nodes camera/ screen/ location` | ⚠️ Mac-Mini 已配对但离线 |
| **通信兵** | 语音合成/识别/唤醒 | `tts` / `talk mode` / `voicewake` | ✅ TTS 可用 |
| **操作员** | 浏览器自动化/表单填写 | `agent-browser` / `browser-use` | ✅ 已安装 |
| **指挥官** | Canvas UI / A2UI 推送 | `canvas present/eval/a2ui` | ⚠️ 节点离线 |
| **执行者** | 远程命令执行 | `nodes run` / `exec host=node` | ⚠️ 节点离线 |
| **信息官** | 手机通知/照片/联系人/日历 | `notifications/ photos/ contacts/ calendar` | ❌ 无移动端节点 |

---

## 二、OpenClaw Nodes 架构深度解析

### 2.1 拓扑模型

```
┌──────────────────────────────────────────────────────────────┐
│                    Gateway (Linux VPS)                        │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐     │
│  │ Agent会话 │  │ Cron调度  │  │ 消息路由  │  │ 工具调用  │     │
│  └─────┬────┘  └─────┬────┘  └─────┬────┘  └─────┬────┘     │
│        └──────────────┴──────────────┴──────────────┘         │
│                            │                                   │
│                    WebSocket Server                           │
│                    (port 18789)                                │
└────────────────────────┬─────────────────────────────────────┘
                         │
            ┌────────────┼────────────┐
            │            │            │
     ┌──────▼──────┐ ┌──▼──────┐ ┌──▼──────────┐
     │ macOS Node  │ │ iOS Node│ │ Android Node│
     │ (Mac Mini)  │ │ (iPhone)│ │ (Android)   │
     │             │ │         │ │             │
     │ canvas      │ │ camera  │ │ camera      │
     │ camera      │ │ canvas  │ │ canvas      │
     │ screen.rec  │ │ talk    │ │ sms.send    │
     │ system.run  │ │ location│ │ contacts    │
     │ talk        │ │ voicewake│ │ calendar    │
     │ voicewake   │ │         │ │ callLog     │
     │ system.notify│ │        │ │ photos      │
     └─────────────┘ └─────────┘ │ motion      │
                                  │ notifications│
                                  │ device.status│
                                  └─────────────┘
```

### 2.2 节点配对流程

```bash
# 1. 生成 QR/Setup Code
openclaw qr --json

# 2. 设备扫码连接

# 3. 网关审批
openclaw devices list
openclaw devices approve <requestId>

# 4. 验证连接
openclaw nodes status
openclaw nodes describe --node <idOrName>
```

### 2.3 当前部署状态

| 节点 | 状态 | 配对 | 连接 | 能力 |
|------|------|------|------|------|
| Mac-Mini (小m) | ⚠️ 离线 | ✅ 已配对 | ❌ 断开 | canvas, camera, screen, system.run, talk |
| Daniel Mac Studio | ❌ 未配对 | - | - | Ollama 已验证 |
| 移动设备 | ❌ 无 | - | - | 无 iOS/Android 节点 |

**关键差距**: 物理信息交互的完整能力链（摄像头+屏幕+位置+通知）需要移动端节点。当前仅有 Mac 节点，且处于离线状态。

---

## 三、六大物理交互能力详解

### 3.1 视觉感知（摄像头 + 屏幕）

#### 摄像头 (camera)

```bash
# 拍照 — 前后摄像头
openclaw nodes camera snap --node Mac-Mini --facing front
openclaw nodes camera snap --node Mac-Mini --facing back

# 录像 — 最多60秒
openclaw nodes camera clip --node Mac-Mini --duration 10s

# 列出可用摄像头
openclaw nodes camera list --node Mac-Mini
```

**Agent 工具调用**:
```json
{ "action": "camera_snap", "node": "Mac-Mini", "facing": "front" }
{ "action": "camera_clip", "node": "Mac-Mini", "duration": "10s" }
```

**限制**: 
- 节点必须在前台（foreground）
- 照片 base64 < 5MB（自动压缩）
- 视频最长 60s
- macOS 默认摄像头关闭，需手动开启

#### 屏幕捕获 (canvas + screen)

```bash
# Canvas 截图
openclaw nodes canvas snapshot --node Mac-Mini --format png

# 屏幕录制（macOS）
openclaw nodes screen record --node Mac-Mini --duration 10s --fps 10

# Canvas 导航 + JS 执行
openclaw nodes canvas navigate --node Mac-Mini --url "https://example.com"
openclaw nodes canvas eval --node Mac-Mini --js "document.title"
```

**Canvas 是一个嵌入式 WebView**：
- 支持本地 HTML/CSS/JS
- 支持 A2UI（Agent-to-UI）协议推送动态界面
- 支持外部 URL 导航
- 支持截图捕获返回给 Agent

#### 应用场景矩阵

| 场景 | 摄像头 | 屏幕 | Agent 决策 |
|------|--------|------|-----------|
| 安防监控 | ✅ 定时拍照 + AI分析 | - | 识别异常→告警 |
| 会议辅助 | ✅ 拍白板/幻灯片 | ✅ 截图 | OCR + 总结 |
| 远程调试 | - | ✅ 录屏 | 看到错误→给出修复建议 |
| 产品演示 | - | ✅ Canvas推送UI | 交互式Demo |
| 环境感知 | ✅ 拍摄环境 | - | AI理解物理环境 |

### 3.2 语音交互（说 + 听）

#### TTS 语音合成

```json
{ "text": "你好，这是语音消息", "channel": "telegram" }
```

直接调用 `tts` 工具，自动转换为语音并发送。

#### Talk Mode — 连续语音对话

```
用户说话 → 语音转文字 → 发送给模型 → 模型回复 → ElevenLabs TTS 播放
                    ↑                                          │
                    └──── 中断检测（用户开口即打断）←──────────────┘
```

**配置**:
```json5
{
  talk: {
    voiceId: "elevenlabs_voice_id",
    modelId: "eleven_v3",
    interruptOnSpeech: true,
    silenceTimeoutMs: 1500
  }
}
```

**语音指令**: Agent 可以在回复中动态切换语音：
```json
{ "voice": "voice_id", "once": true }
```

#### 唤醒词 (VoiceWake)

- 全局唤醒词列表，Gateway 统一管理
- 自动同步到所有已连接节点
- 默认触发词：`openclaw`, `claude`, `computer`

### 3.3 位置感知 (location)

```bash
openclaw nodes location get --node Mac-Mini --accuracy precise
```

**参数**: `coarse | balanced | precise`
**隐私**: 默认关闭，需用户手动开启
**场景**: 
- 自动化地理围栏（到家自动开灯）
- 位置相关提醒（到公司提醒开会）
- 日程智能调度

### 3.4 移动端深度集成（Android 专属）

| 能力 | 命令 | 场景 |
|------|------|------|
| 通知读取 | `notifications.list` | 重要消息过滤 + AI总结 |
| 最新照片 | `photos.latest` | 自动获取照片→AI描述/分类 |
| 联系人搜索 | `contacts.search` | "帮我找张三的电话" |
| 日历事件 | `calendar.events` | 智能日程管理 |
| 通话记录 | `callLog.search` | 回拨提醒 |
| 短信发送 | `sms.send` | 自动回复短信 |
| 步数/运动 | `motion.pedometer` | 健康追踪 |
| 设备状态 | `device.status/health` | 电量/存储/网络状态 |

### 3.5 远程命令执行 (system.run)

```bash
# 在远程节点执行命令
openclaw nodes run --node Mac-Mini -- echo "Hello from remote"

# 带环境变量和工作目录
openclaw nodes run --node Mac-Mini --cwd ~/projects --env KEY=VAL -- python3 script.py

# 系统通知
openclaw nodes notify --node Mac-Mini --title "构建完成" --body "deploy.sh 执行成功"
```

**安全机制**:
- 三级安全策略：`deny | allowlist | full`
- 审批文件：`~/.openclaw/exec-approvals.json`
- 白名单管理：`openclaw approvals allowlist add --node <id> "/usr/bin/uname"`

### 3.6 浏览器自动化（agent-browser + browser-use）

#### agent-browser（Rust 高性能 headless）

```bash
agent-browser open https://example.com
agent-browser snapshot -i           # 获取交互元素
agent-browser click @e1             # 点击
agent-browser fill @e2 "text"       # 填表
agent-browser snapshot -s "#main"   # CSS选择器范围截图
```

#### browser-use（AI 驱动，适合复杂交互）

```python
from browser_use import Agent
agent = Agent(task="打开 polymarket.com 查看市场数据", llm=llm)
result = await agent.run()
# ⚠️ 必须关闭浏览器防止资源泄漏
await agent.browser.close()
```

**选择原则**:
| 场景 | 推荐 | 原因 |
|------|------|------|
| 结构化数据采集 | agent-browser | 快速、省token |
| 复杂动态页面 | browser-use | AI自适应 |
| 表单填写/登录 | agent-browser | 精确控制 |
| 需要智能决策 | browser-use | LLM判断 |

---

## 四、Canvas + A2UI — Agent 的可视化武器

### 4.1 Canvas 架构

```
Agent 决策
    ↓ canvas present/navigate/eval
Gateway → WebSocket → Node (WebView)
    ↓ snapshot
Node → base64 图片 → Agent（看到渲染结果）
```

### 4.2 A2UI 协议（Agent-to-UI）

A2UI 让 Agent 直接在设备上渲染 UI 组件：

```bash
# 推送文本
openclaw nodes canvas a2ui push --node Mac-Mini --text "实时监控面板"

# 推送复杂 JSONL 布局
openclaw nodes canvas a2ui push --node Mac-Mini --jsonl ./dashboard.jsonl

# 重置
openclaw nodes canvas a2ui reset --node Mac-Mini
```

**支持组件**: Text, Column, Row, Button, Image 等基础 UI 元素
**协议版本**: v0.8（beginRendering, surfaceUpdate, dataModelUpdate, deleteSurface）

### 4.3 应用场景

| 场景 | Canvas 角色 | A2UI 角色 |
|------|------------|-----------|
| 实时监控面板 | 展示 Grafana/自定义页面 | 动态推送数据卡片 |
| 远程控制台 | 操作界面 | 按钮交互 |
| 数据可视化 | ECharts/D3 嵌入 | 实时数据更新 |
| 任务看板 | Trello 风格界面 | 拖拽/状态更新 |

---

## 五、军团设计原则

### 原则 1：感知-决策-行动闭环（SDA Loop）

```
感知(Sense) → 摄像头/屏幕/位置/通知/传感器
    ↓
决策(Decide) → Agent 分析 + 规则引擎 + ML 模型
    ↓
行动(Act)    → Canvas 推送 / 语音播报 / 远程执行 / 消息通知
    ↓
反馈(Feedback) → 确认执行结果 → 更新状态 → 进入下一轮
```

**设计铁律**: 每个物理交互流程必须构成完整 SDA 闭环，不能只有"感知"没有"行动"，也不能盲目"行动"没有"感知"。

### 原则 2：最小权限 + 显式同意

- 所有传感器（摄像头/麦克风/位置/通知）**默认关闭**
- 用户必须手动开启每一项权限
- Android/iOS 系统级权限提示不可跳过
- `exec host=node` 有独立审批流程（deny/allowlist/full）

**设计含义**: Agent 不能假设任何物理能力可用。每次调用前必须检查节点状态和权限。

### 原则 3：前台优先 + 优雅降级

- 摄像头、Canvas、屏幕录制**必须节点在前台**
- 后台调用返回 `NODE_BACKGROUND_UNAVAILABLE`
- **降级策略**:
  - 摄像头不可用 → 使用最近照片 (`photos.latest`)
  - Canvas 不可用 → 降级为文字/图片消息
  - 节点离线 → 排队等待或降级为本机执行

### 原则 4：数据最小化 + 本地优先

- 照片自动压缩至 < 5MB base64
- 视频限制 60s
- 位置信息精度可配（coarse/balanced/precise）
- **本地处理优先**: 能在设备端完成的（语音唤醒、照片压缩）不在云端做

### 原则 5：多节点协同拓扑

```
Gateway (Linux VPS)
├── Mac Mini (小m) — Ollama + Canvas + 摄像头 + 执行节点
├── Mac Studio — GPU 推理 + 大模型
├── Android — 移动感知 + 通知 + 位置 + SMS
└── iOS — 移动感知 + 语音对话
```

**原则**: 每类设备发挥其物理优势：
- Mac = 持续在线的计算节点 + 屏幕展示
- Android = 移动感知中心（通知/位置/SMS）
- iOS = 语音交互终端（Talk Mode）

### 原则 6：异步驱动 + 事件触发

- Agent 不应轮询节点状态（浪费资源）
- 使用 Cron + 事件触发模式：
  - 定时拍照 → AI 分析 → 异常时才通知
  - 收到特定通知 → 触发 Agent 处理流程
  - 位置变化 → 触发地理围栏逻辑

### 原则 7：安全纵深防御

| 层 | 防护 |
|----|------|
| 网络 | Tailscale 加密隧道 + WebSocket TLS |
| 认证 | Device Pairing + Gateway Token |
| 授权 | per-node 命令白名单 |
| 执行 | exec-approvals.json + ask mode |
| 数据 | base64 限制 + 自动压缩 |
| 隐私 | 用户显式开启每项传感器 |

---

## 六、当前差距与行动建议

### 差距分析

| 维度 | 当前 | 目标 | 差距 |
|------|------|------|------|
| Mac 节点在线 | ❌ 离线 | ✅ 持续在线 | 需确保小m OpenClaw App 持续运行 |
| 移动端节点 | ❌ 无 | ✅ Android + iOS | 需安装 OpenClaw App 并配对 |
| Canvas 使用 | ❌ 未使用 | ✅ 监控面板 | 需小m在线后推送 |
| 语音对话 | ❌ 未配置 | ✅ Talk Mode | 需 ElevenLabs API Key |
| 摄像头集成 | ❌ 未使用 | ✅ 安防/环境感知 | 需移动端节点 |
| 浏览器自动化 | ✅ 已安装 | ✅ 已可用 | 可立即使用 |

### 优先行动（按 ROI 排序）

1. **P0 — 恢复小m Mac Mini 节点在线**
   - 确保 OpenClaw macOS App 持续运行
   - 验证 `openclaw nodes status` 显示 connected
   - 测试 `canvas present` + `camera snap`

2. **P1 — 配置 Android 节点**
   - 安装 OpenClaw Android App
   - 配对 + 开启通知/位置/摄像头权限
   - 解锁全部移动端能力（SMS/联系人/日历/运动）

3. **P1 — 浏览器自动化实战**
   - `agent-browser` 已安装，可直接用于数据采集
   - 替代部分 `browser-use` Python 调用（更轻量）

4. **P2 — Talk Mode 语音对话**
   - 配置 ElevenLabs API Key
   - 在 macOS/iOS 节点启用 Talk Mode
   - 实现"Hey OpenClaw"唤醒 → 语音指令执行

5. **P2 — Canvas 监控面板**
   - 小m在线后推送实时监控页面
   - A2UI 动态卡片（系统状态/Token消耗/项目进度）

---

## 七、军团编排模式（战术手册）

### 模式 A：安防巡逻

```
Cron (每30分钟)
  → nodes camera snap (前后摄像头)
  → image 分析 (识别异常人物/物体)
  → 异常时: message 告警 + canvas a2ui 推送实时画面
```

### 模式 B：会议助手

```
唤醒词 "openclaw meeting"
  → camera clip (录制会议10s片段)
  → audio 转文字 (会议纪要)
  → tts 播报要点
  → 写入 memory/YYYY-MM-DD.md
```

### 模式 C：移动秘书

```
Android 通知到达
  → notifications.list (读取新通知)
  → AI 分类 (重要/普通/垃圾)
  → 重要: tts 播报摘要 + message 推送
  → 普通: 记录到 memory，不打扰
```

### 模式 D：远程运维

```
告警触发
  → nodes screen record (录制屏幕10s)
  → image 分析错误画面
  → nodes run (执行修复命令)
  → nodes notify (通知修复结果)
```

### 模式 E：智能购物

```
"帮我比价XXX"
  → agent-browser 打开电商平台
  → snapshot 获取商品列表
  → AI 提取价格/规格
  → canvas a2ui 推送比价卡片
  → 用户选择 → agent-browser 下单
```

---

## 八、关键洞察

1. **物理交互是 AI 从"聊天机器人"到"数字员工"的关键跃迁**。纯文本 Agent 的天花板是信息处理；接入物理世界的 Agent 能真正执行任务。

2. **节点架构 = 分布式身体**。Gateway 是大脑，Nodes 是手眼耳。每个设备发挥其物理优势：Mac = 持续在线的计算/展示节点，手机 = 移动感知识别终端。

3. **前台依赖是最大瓶颈**。摄像头/Canvas/屏幕录制都要求节点在前台，这意味着 7×24 运行需要专用设备（Mac Mini 是理想选择）。

4. **Android 节点能力最丰富**（通知/SMS/联系人/日历/运动），iOS 侧重视觉/语音体验。建议优先部署 Android 节点获取最大能力覆盖。

5. **浏览器自动化是"零门槛物理交互"**。不需要额外设备，本机即可运行，适合数据采集和自动化操作。是当前立即可用的高 ROI 能力。

6. **SDA 闭环是设计哲学**。感知→决策→行动→反馈，缺一不可。没有行动的感知是浪费，没有感知的行动是盲目。

---

*蜂群学习 Round 8/10 | 物理信息交互军团 | 2026-04-02*
