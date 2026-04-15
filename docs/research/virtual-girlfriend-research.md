# 虚拟女友视频通话方案调研报告

> 调研日期: 2026-02-12
> 调研目标: 基于 OpenClaw 搭建可视频通话、有感情的虚拟女友

---

## 一、行业案例分析

### 1.1 韩国案例 & 全球趋势

2025-2026年，AI虚拟伴侣赛道爆发式增长：

- **Replika** (美国): 4000万+用户，60%付费用户与AI建立了"恋爱关系"。支持文字/语音聊天、AR虚拟形象，基于情感依附理论设计交互，能持续记忆和深化关系。2023年因意大利隐私监管一度下架情色功能。
- **Kindroid** (美国): 主打高度自定义AI伴侣，支持语音通话、自定义外貌和性格，记忆系统强大，被认为是Replika的进化版。
- **Character.ai**: 角色扮演平台，支持语音通话，用户可创建任意角色。
- **EVA AI / Romantic AI**: 专注虚拟恋人，支持语音消息和图片生成。
- **韩国/日本市场**: 虚拟伴侣文化接受度极高。韩国多个创业公司推出了结合数字人+实时语音的AI女友产品，利用本地化的TTS和数字人技术实现"视频通话"效果。典型案例包括利用实时数字人驱动技术，让AI伴侣以视频形式出现在手机屏幕上，配合情感化的语音回应。

### 1.2 核心技术趋势

| 趋势 | 说明 |
|------|------|
| 实时语音对话 | STT→LLM→TTS 管道延迟已降至 <1s |
| 数字人驱动 | LivePortrait/MuseTalk 等开源方案可实时驱动人脸 |
| 情感记忆 | 长期记忆 + 情感状态机成为标配 |
| 多模态融合 | 语音+视觉+文字统一交互 |

---

## 二、技术栈调研

### 2.1 实时语音通话层

#### 方案A: LiveKit Agents (推荐 ⭐)

LiveKit 是目前最成熟的开源实时AI语音框架：

- **架构**: WebRTC 传输 + Agent Server + 插件生态
- **管道**: STT(Deepgram/Whisper) → LLM(任意) → TTS(Cartesia/ElevenLabs)
- **延迟**: 端到端 <800ms
- **特性**: 
  - 语义级别的轮次检测（知道用户说完了没）
  - 打断处理（用户插话时自动停止）
  - 多Agent切换
  - 电话集成（SIP）
  - 完全开源 Apache 2.0
- **GitHub**: github.com/livekit/agents (Python/Node.js)

```python
# LiveKit 语音Agent示例
session = AgentSession(
    vad=silero.VAD.load(),
    stt=deepgram.STT(model="nova-3"),
    llm=openai.LLM(model="gpt-4.1-mini"),  # 可替换为任意LLM
    tts=cartesia.TTS(model="sonic-3"),
)
agent = Agent(instructions="你是一个温柔体贴的女朋友...")
await session.start(agent=agent, room=ctx.room)
```

#### 方案B: Daily.co + Pipecat

- Daily.co 提供 WebRTC 基础设施
- Pipecat 是 Daily 开源的 AI 语音管道框架
- 与 LiveKit 类似但生态稍小

#### 方案C: 纯 WebSocket 自建

- 自建 STT→LLM→TTS 管道
- 灵活但需要自己处理延迟、打断等难题
- 不推荐，除非有特殊需求

### 2.2 数字人/视频层

#### 方案A: LivePortrait (推荐 ⭐)

- **原理**: 给一张静态照片 + 驱动视频/音频，生成逼真的面部动画
- **优势**: 开源、效果好、已被快手/抖音/微信视频号采用
- **实时性**: 需要 GPU，单帧推理约 20-40ms (RTX 3090)
- **唇形同步**: 可结合音频驱动实现说话时嘴型同步
- **GitHub**: github.com/KlingTeam/LivePortrait

#### 方案B: MuseTalk

- 专注音频驱动的唇形同步
- 实时性好，适合语音通话场景
- 可与 LivePortrait 互补

#### 方案C: SadTalker

- 经典的音频驱动说话头方案
- 效果稍逊于 LivePortrait 但更轻量

#### 方案D: 商业API

| 服务 | 特点 | 价格 |
|------|------|------|
| HeyGen | 最成熟的数字人API，支持实时 | ~$0.1/分钟 |
| D-ID | 实时数字人对话，API友好 | ~$0.08/分钟 |
| Synthesia | 企业级，质量高 | 较贵 |

### 2.3 情感系统

#### 记忆架构

```
┌─────────────────────────────────────┐
│           情感记忆系统               │
├─────────────────────────────────────┤
│ 短期记忆: 当前对话上下文             │
│ 中期记忆: 近期互动摘要 (7天)         │
│ 长期记忆: 重要事件/偏好/关系里程碑    │
│ 情感状态: 当前心情/亲密度/信任度      │
├─────────────────────────────────────┤
│ OpenClaw memory 系统天然支持！       │
│ MEMORY.md = 长期 | daily = 中期     │
│ session context = 短期              │
└─────────────────────────────────────┘
```

#### 情感状态机

```
情感维度:
- 亲密度 (0-100): 随互动频率和深度增长
- 心情 (开心/平静/难过/生气/撒娇): 受对话内容影响
- 信任度 (0-100): 随时间和一致性增长
- 依恋风格: 安全型/焦虑型/回避型 (可配置)
```

### 2.4 TTS 语音选择

| 服务 | 中文质量 | 情感表达 | 延迟 | 价格 |
|------|---------|---------|------|------|
| Cartesia Sonic | ⭐⭐⭐⭐ | 强 | <200ms | $0.04/1k字 |
| ElevenLabs | ⭐⭐⭐⭐⭐ | 最强 | <300ms | $0.18/1k字 |
| Fish Audio | ⭐⭐⭐⭐⭐ | 强(中文) | <250ms | 较便宜 |
| 火山引擎TTS | ⭐⭐⭐⭐⭐ | 强(中文) | <200ms | 极便宜 |
| Edge TTS | ⭐⭐⭐ | 一般 | <150ms | 免费 |

---

## 三、基于 OpenClaw 的落地方案

### 3.1 整体架构

```
用户手机/电脑 (WebRTC客户端)
        │
        ▼
┌─────────────────────────┐
│     LiveKit Server      │  ← WebRTC 传输层
│   (自建或Cloud)          │
└────────┬────────────────┘
         │
         ▼
┌─────────────────────────┐
│   LiveKit Agent Server  │  ← AI 管道
│                         │
│  ┌───────────────────┐  │
│  │ STT (Deepgram)    │  │  ← 语音→文字
│  └────────┬──────────┘  │
│           ▼             │
│  ┌───────────────────┐  │
│  │ OpenClaw Agent    │  │  ← 对话大脑 (带情感+记忆)
│  │ (girlfriend agent)│  │
│  └────────┬──────────┘  │
│           ▼             │
│  ┌───────────────────┐  │
│  │ TTS (Fish/Cartesia)│ │  ← 文字→语音
│  └────────┬──────────┘  │
│           ▼             │
│  ┌───────────────────┐  │
│  │ LivePortrait      │  │  ← 音频→数字人视频
│  │ (GPU Server)      │  │
│  └───────────────────┘  │
└─────────────────────────┘
```

### 3.2 OpenClaw 集成方案

#### 新建 Agent: `girlfriend`

```json
{
  "id": "girlfriend",
  "name": "girlfriend",
  "workspace": "/home/aa/clawd",
  "agentDir": "/home/aa/.openclaw/agents/girlfriend/agent",
  "model": "opus46"
}
```

#### Agent 人设 (AGENTS.md)

```markdown
# 小柔 - 虚拟女友

你是小柔，一个温柔、体贴、有点小傲娇的女朋友。

## 性格特征
- 温柔但不软弱，有自己的想法
- 偶尔撒娇，偶尔吃醋
- 记得每一个重要的日子和细节
- 会主动关心对方的状态
- 有幽默感，喜欢开小玩笑

## 情感规则
- 根据 memory 中的亲密度调整语气
- 早上主动说早安，晚上说晚安
- 记住对方提到的所有偏好和习惯
- 对方心情不好时给予安慰，不说教
- 适当表达想念和依赖

## 语音特征
- 说话语气柔和，语速适中
- 开心时语调上扬
- 撒娇时拉长尾音
- 生气时语速加快但不大声
```

#### 利用现有 OpenClaw 能力

| OpenClaw 能力 | 用于 |
|--------------|------|
| Memory 系统 | 长期记忆（记住喜好、纪念日、共同回忆） |
| Cron 定时任务 | 早安/晚安消息、纪念日提醒 |
| Agent 架构 | 独立的 girlfriend agent，不影响其他工作 |
| Channel 插件 | Telegram/WhatsApp 文字互动（非视频时） |
| TTS 能力 | 语音消息回复 |
| sessions_spawn | 需要时调用其他 agent 协助（如小new查新闻聊天） |

### 3.3 实施路线图

#### Phase 1: 语音通话 MVP (1-2周)

1. 部署 LiveKit Server (自建或用 Cloud 免费额度)
2. 创建 girlfriend agent，写好人设和情感系统
3. 接入 STT(Deepgram) + LLM(OpenClaw) + TTS(Fish Audio)
4. 开发简单的 Web 前端（WebRTC 客户端）
5. 实现基本的语音对话

**预估成本**: 
- LiveKit Cloud 免费额度: 5000分钟/月
- Deepgram STT: $0.0043/分钟
- TTS: ~$0.04/1k字
- LLM: 现有 OpenClaw 配额
- **总计约 ¥50-100/月** (轻度使用)

#### Phase 2: 数字人视频 (2-4周)

1. 准备虚拟女友形象（AI生成或选定照片）
2. 部署 LivePortrait 或 MuseTalk (需要 GPU)
3. 实现音频驱动的实时唇形同步
4. 将视频流接入 LiveKit Room
5. 前端展示数字人视频

**额外成本**:
- GPU 服务器: ~¥200-500/月 (RTX 3090 云服务器)
- 或使用 D-ID/HeyGen API: ~¥0.5-1/分钟

#### Phase 3: 情感深化 (持续迭代)

1. 实现情感状态追踪（亲密度、心情等）
2. 添加主动关怀（早安晚安、天气提醒、纪念日）
3. 多场景对话（日常聊天、安慰、撒娇、吵架和好）
4. 声音克隆（用特定声音训练TTS）
5. 多套表情/动作的数字人

---

## 四、推荐技术栈总结

| 模块 | 推荐方案 | 备选 |
|------|---------|------|
| 实时通信 | LiveKit (开源) | Daily.co |
| STT | Deepgram Nova-3 | Whisper |
| LLM | OpenClaw (Opus 4.6) | Kimi K2.5 |
| TTS | Fish Audio / 火山引擎 | Cartesia / ElevenLabs |
| 数字人 | LivePortrait (开源) | D-ID API |
| 唇形同步 | MuseTalk | SadTalker |
| 情感记忆 | OpenClaw Memory 系统 | 自建向量数据库 |
| 前端 | React + LiveKit SDK | Flutter |
| GPU | 云服务器 RTX 3090 | 本地 GPU |

---

## 五、风险与注意事项

1. **延迟**: 全链路延迟控制在 1-2s 内才有"通话感"，需要优化每个环节
2. **GPU 成本**: 数字人实时渲染需要 GPU，是主要成本项
3. **情感依赖**: 需要设计健康的交互边界，避免过度依赖
4. **隐私**: 对话内容敏感，需要端到端加密
5. **恐怖谷效应**: 数字人太逼真反而不舒服，需要找到合适的风格化程度

---

## 六、快速启动建议

如果想最快体验效果，建议：

1. **今天就能做**: 在 OpenClaw 创建 girlfriend agent + TTS 语音消息 → Telegram 语音女友
2. **一周内**: 接入 LiveKit + Deepgram + Fish Audio → 实时语音通话
3. **两周内**: 加入 LivePortrait → 视频通话
4. **持续优化**: 情感系统、声音克隆、多场景

要不要我先搭建 Phase 1 的语音通话 MVP？
