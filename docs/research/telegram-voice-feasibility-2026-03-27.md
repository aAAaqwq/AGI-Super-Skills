# Telegram 语音交互（Voice Interaction）与 OpenClaw 可行性报告

日期：2026-03-27

## 一、现状分析（OpenClaw + Telegram）

### 1. Telegram Bot API 对语音消息的支持

Telegram Bot API 原生支持：

- **接收语音消息**：用户发送 voice note 后，Bot 会收到 `message.voice.file_id`
- **下载语音文件**：通过 `getFile` 获取 `file_path`，再从 `https://api.telegram.org/file/bot<TOKEN>/<file_path>` 下载
- **发送语音消息**：通过 `sendVoice` 发送 voice message（语音气泡）
- **发送普通音频**：通过 `sendAudio` 发送音频文件（不是语音气泡）

Telegram 语音消息常见格式是 OGG/Opus；但 `sendVoice` 也可兼容部分 MP3 / M4A。

### 2. OpenClaw 当前对 Telegram 语音的真实支持情况

基于本地源码 `~/clawd/openclaw-src/` 与上游 docs：

#### 2.1 入站语音：**已支持**

OpenClaw Telegram 处理链已能识别并下载入站语音：

- `src/telegram/bot-handlers.ts`
  - 检测 `msg.voice?.file_id`
- `src/telegram/bot/delivery.resolve-media.ts`
  - 通过 `ctx.getFile()` 和 Telegram file URL 下载音频
- `src/media-understanding/audio-preflight.ts`
  - 可在 group `requireMention: true` 场景下，先转写语音再做 mention 检测
- `src/media-understanding/transcribe-audio.ts`
  - 暴露运行时 STT 接口 `transcribeAudioFile(...)`

这说明：

**OpenClaw 已经支持 Telegram 语音消息接收、下载、接入转写链路。**

#### 2.2 入站语音转写（STT）：**已支持，且是框架级能力**

OpenClaw 官方/上游文档 `docs/nodes/audio.md` 明确写到：

- 启用 `tools.media.audio` 后，OpenClaw 会：
  1. 找到首个音频附件
  2. 下载音频
  3. 按顺序尝试 provider / CLI 转写
  4. 成功后把 transcript 注入 `Body` 和 `{{Transcript}}`
- group 中 `requireMention: true` 时，会先做 audio preflight transcription，再判断是否提及机器人
- 支持 provider / CLI fallback

支持的 STT 路线包括：

- 本地 CLI：
  - `sherpa-onnx-offline`
  - `whisper-cli`（whisper.cpp）
  - `whisper`（Python Whisper CLI）
- Provider：
  - OpenAI
  - Groq
  - Deepgram
  - Google

文档默认推荐/示例中出现：

- `gpt-4o-mini-transcribe`
- `gpt-4o-transcribe`
- Deepgram `nova-3`

所以结论很明确：

**OpenClaw 当前已经具备“Telegram 语音消息 → STT → 注入 agent 输入”的现成能力，不需要从零开发。**

#### 2.3 出站语音（TTS）：**已支持**

OpenClaw 现有 `tts` 工具真实存在：

- `src/agents/tools/tts-tool.ts`
- 描述：`Convert text to speech. Audio is delivered automatically...`

并且 TTS 核心实现 `src/tts/tts.ts` 已对 Telegram 做了专门适配：

- 若 channel 是 `telegram`：
  - OpenAI 输出格式用 `opus`
  - ElevenLabs 输出格式用 `opus_48000_64`
  - 标记 `voiceCompatible: true`
- `tts-tool.ts` 会在成功时输出 `[[audio_as_voice]]`，让下游按语音气泡发送

Telegram 发送侧也已支持：

- `src/telegram/send.ts`
  - 音频媒体会根据 `asVoice` 决定走 `sendVoice` 或 `sendAudio`
- `src/telegram/voice.ts`
  - 判断媒体是否兼容 Telegram voice
- `src/media/audio.ts`
  - 明确支持 `.oga/.ogg/.opus/.mp3/.m4a` 和相应 MIME 作为 voice-compatible
- 测试 `src/telegram/send.test.ts`
  - 已覆盖 `sendVoice` / `sendAudio` 路由逻辑

所以结论：

**OpenClaw 当前已经支持“文本 → TTS → Telegram 语音气泡发送”。**

### 3. OpenClaw 本地 docs（~/clawd/docs）检查结果

`~/clawd/docs/` 目录里，和 Telegram 相关的主要是业务文档，例如：

- `docs/one-company/telegram-setup-guide.md`
- `docs/one-company/telegram-organization.md`
- `docs/SYSTEM_SUMMARY.md`

这些文档主要描述群组、agent、消息路由与组织方式，**没有专门成体系地描述 voice/TTS 实现方案**。

也就是说：

- 业务文档里：**语音方案基本未系统落地说明**
- 真正的语音支持说明在上游 OpenClaw docs / source 中更完整

### 4. OpenClaw 官方文档检查结果

已通过上游本地 docs 与浏览器访问 `docs.openclaw.ai/nodes/audio` 交叉验证，内容一致，核心结论：

- 官方已明确支持 **Audio / Voice Notes**
- 官方已明确支持 `tools.media.audio`
- 官方已明确支持 group mention 场景下的 **audio preflight transcription**
- 插件文档 `docs/tools/plugin.md` 明确支持：
  - `api.runtime.stt.transcribeAudioFile(...)`
  - 使用 `tools.media.audio` 配置和 provider fallback
- 同时插件文档也说明 TTS 走 core `messages.tts` 配置

结论：

**官方文档层面，OpenClaw 已具备 STT + TTS 的正式支持，不属于“需要自研底层框架”的阶段。**

---

## 二、STT 方案

### 方案 A：OpenAI Whisper / OpenAI Transcribe（推荐云方案）

#### 可选模型

- `gpt-4o-mini-transcribe`（推荐默认）
- `gpt-4o-transcribe`（更高准确率）
- 传统 `whisper-1` 也可，但 OpenClaw 上游当前 docs 已更多转向新模型

#### 优点

- 接入 OpenClaw 最顺滑
- 官方已有 `tools.media.audio.models` 配置能力
- 不需要单独写 skill 就能用在 Telegram 入站音频
- 质量、稳定性、语言覆盖较好

#### 缺点

- 有 API 成本
- 依赖外部网络与配额

#### 建议配置示例

```json5
{
  tools: {
    media: {
      audio: {
        enabled: true,
        models: [
          { provider: "openai", model: "gpt-4o-mini-transcribe", language: "zh" }
        ]
      }
    }
  }
}
```

### 方案 B：本地 Whisper CLI（推荐离线/低成本方案）

OpenClaw 已支持本地 CLI fallback：

- `whisper`（Python CLI）
- `whisper-cli`（whisper.cpp）

本地 skill 也已存在：

- `openai-whisper-api`（云 API）
- `openai-whisper`（本地 Whisper CLI）

#### 优点

- 可离线运行
- 成本低
- 可做本地兜底 fallback

#### 缺点

- 部署复杂度更高
- 中文效果视模型与机器性能而定
- 首次模型下载慢
- CPU 推理延迟通常比云方案大

#### 建议配置思路

主方案云端，失败再回退本地：

```json5
{
  tools: {
    media: {
      audio: {
        enabled: true,
        models: [
          { provider: "openai", model: "gpt-4o-mini-transcribe", language: "zh" },
          {
            type: "cli",
            command: "whisper",
            args: ["--model", "base", "{{MediaPath}}"],
            timeoutSeconds: 45
          }
        ]
      }
    }
  }
}
```

### 方案 C：Deepgram（备选）

OpenClaw 官方 docs 有专门的 Deepgram 文档，说明其可作为 inbound audio transcription provider。

#### 优点

- 专门 STT 服务
- 英文和实时生态成熟

#### 缺点

- 对中文与混合语言体验需单独验证
- 对当前目标来说，不如 OpenAI 方案统一

### STT 推荐结论

**推荐优先级：**

1. **OpenAI `gpt-4o-mini-transcribe`** 作为主路
2. **本地 whisper / whisper.cpp** 作为 fallback
3. Deepgram 作为备选

---

## 三、TTS 方案

### 方案 A：OpenClaw 内建 TTS tool + OpenAI TTS（推荐）

OpenClaw 当前 `tts` tool 已可直接用于 Telegram，并已做 voice-compatible 输出适配。

#### 已知能力

- tool 名：`tts`
- 调用时可带 `channel: "telegram"`
- 对 Telegram 会优先产出 **Opus** 音频
- tool 成功后会自动附带 `[[audio_as_voice]]`
- Telegram 发送链会用 `sendVoice`

#### 优点

- 不需要自己处理编码细节
- OpenClaw 已经内建 Telegram 适配
- 代码与文档都表明这条路最顺

#### 缺点

- 依赖 OpenAI API key（若选 OpenAI provider）

#### 推荐配置

```json5
{
  messages: {
    tts: {
      auto: "off",
      provider: "openai",
      openai: {
        model: "gpt-4o-mini-tts",
        voice: "alloy"
      }
    }
  }
}
```

适合在 agent 中按需调用 `tts` tool，而不是默认每条都语音回复。

### 方案 B：OpenClaw 内建 TTS tool + edge-tts（推荐低成本方案）

源码显示：

- 默认 provider 若无 API key，会偏向 `edge`
- 使用 `node-edge-tts`
- 能输出 mp3 / opus / ogg / wav 等格式（取决于配置）

#### 优点

- 成本低
- 接入简单
- 适合作为默认 TTS 或开发调试环境

#### 缺点

- 声音表现力通常不如 OpenAI / ElevenLabs
- 某些 voice / 格式稳定性需要实测
- 若输出格式不兼容，可能退化成 `sendAudio` 而非 `sendVoice`

#### 实务建议

如果走 edge-tts，建议明确设置 Telegram 兼容输出格式，并实测最终文件扩展名/MIME 是否被 OpenClaw 判定为 voice-compatible。

### 方案 C：ElevenLabs（高质量备选）

OpenClaw 源码显示已支持 ElevenLabs，并对 Telegram 设置：

- `opus_48000_64`
- `voiceCompatible: true`

#### 优点

- 音色质量高
- 适合品牌化人格语音

#### 缺点

- 成本更高
- 需要额外 key 和 voice 管理

### TTS 推荐结论

**推荐优先级：**

1. **OpenClaw 内建 `tts` tool + OpenAI TTS**
2. **OpenClaw 内建 `tts` tool + edge-tts**（低成本/开发环境）
3. **ElevenLabs**（追求音色质量时）

---

## 四、OpenClaw `tts` tool 当前能力评估

### 已具备能力

- 文本转语音
- 按 channel 选择输出格式
- Telegram 专门适配 voice-bubble 输出
- OpenAI / ElevenLabs / Edge 三种 provider
- 自动生成临时音频文件并传给消息系统

### 当前边界

- `tts` tool 解决的是 **出站语音**，不是入站转写
- 入站语音转写走的是 `tools.media.audio` / runtime STT 能力，不是 `tts`
- 如果要做“语音对话体验”（收到语音 -> 转写 -> 回答 -> 再语音返回），需要把 **STT 与 TTS 流程在 agent 或插件层串起来**

---

## 五、是否需要开发 skill？

### 短答案

**不是必须，但建议开发一个轻量 skill / workflow 封装。**

### 原因

底层能力已经有：

- Telegram 收语音：有
- 下载语音：有
- STT：有
- TTS：有
- Telegram 发 voice bubble：有

所以：

**不需要开发底层框架；只需要开发“体验层封装”。**

### 不开发 skill 也能做的事

- 开启 `tools.media.audio`
- 配置 `messages.tts`
- 在 agent prompt / workflow 里规定：
  - 如果用户输入是语音，则优先简洁回复
  - 必要时调用 `tts` tool 语音回复

### 为什么仍建议做一个 skill

因为实际产品化时，需要统一处理：

- 何时对语音消息启用语音回复
- 何时只文字回复
- 语音过长时是否先摘要
- 中文 voice 风格和 persona
- 错误回退（TTS 失败则发文字）
- 群聊/私聊策略不同

### 建议 skill 设计

例如：`telegram-voice-reply`

职责：

1. 判断入站消息是否为 voice
2. 从 `{{Transcript}}` 或 STT 结果取文本
3. 生成简洁口语化回答
4. 调用 `tts` tool（`channel: telegram`）
5. 若失败则回退文字
6. 可选：同时发送 transcript 确认文本

结论：

**建议开发 skill，但只是 orchestration skill，不是底层能力开发。**

---

## 六、实现难度评估（1-5星）

### 1. 仅启用“语音输入转文字”

**难度：⭐☆☆☆☆（1/5）**

原因：

- OpenClaw 已原生支持
- 主要是配置 `tools.media.audio`
- Telegram 入站下载链已具备

### 2. 启用“文字转语音回复”

**难度：⭐⭐☆☆☆（2/5）**

原因：

- `tts` tool 已存在
- Telegram voice bubble 发送已存在
- 主要是 TTS provider 配置与回复策略控制

### 3. 做成完整“语音对话模式”

**难度：⭐⭐⭐☆☆（3/5）**

原因：

- 底层能力已齐
- 但还需要 orchestration：
  - 入站 voice 检测
  - transcript/summary 策略
  - TTS 回复开关
  - 文本/语音双轨回退
  - 群聊/私聊差异策略

### 4. 做成产品级稳定体验

**难度：⭐⭐⭐⭐☆（4/5）**

原因：

- 需要优化延迟、成本、人格音色、一致性
- 需要处理超长语音、转写错误、失败回退、日志与监控
- 需要补齐业务文档与 skill 封装

---

## 七、推荐方案 + 所需工作

### 推荐方案

**推荐采用：**

- **入站 STT**：OpenClaw `tools.media.audio` + OpenAI `gpt-4o-mini-transcribe`
- **fallback STT**：本地 `whisper` / `whisper.cpp`
- **出站 TTS**：OpenClaw `tts` tool + OpenAI `gpt-4o-mini-tts`
- **体验封装**：新增一个轻量 `telegram-voice-reply` skill 或 workflow

这是当前性价比最高、开发量最小、最贴近 OpenClaw 现有能力的方案。

### 推荐交互流程

1. 用户在 Telegram 发送 voice note
2. OpenClaw 下载音频
3. `tools.media.audio` 进行转写
4. Agent 获得 transcript
5. Agent 生成简洁口语答复
6. 调用 `tts(text=..., channel="telegram")`
7. OpenClaw 输出 Opus 音频
8. Telegram 通过 `sendVoice` 发送语音气泡
9. 若 TTS 失败，则回退为文本消息

### 所需工作清单

#### Phase 1：最小可用版本（MVP）

1. 配置 `tools.media.audio.enabled: true`
2. 配置 `tools.media.audio.models` 为 OpenAI transcribe
3. 配置 `messages.tts` 为 OpenAI 或 edge
4. 在 Telegram 私聊中测试：
   - 语音输入转文字
   - `tts` 工具发语音
   - `sendVoice` 是否真走语音气泡

#### Phase 2：语音回复策略

5. 增加规则：仅当用户输入是 voice 时，优先语音回复
6. 控制 TTS 回复长度，避免过长
7. TTS 失败时自动退回文字
8. 可选开启 `tools.media.audio.echoTranscript`

#### Phase 3：封装 skill

9. 新建 `telegram-voice-reply` skill：
   - 检测 voice 输入
   - 提炼 transcript
   - 输出短口语
   - 调 `tts`
10. 增加私聊/群聊差异策略：
   - 私聊：可默认语音回复
   - 群聊：默认文字，按需语音

#### Phase 4：产品化优化

11. 加入 fallback provider / local whisper
12. 增加监控：转写耗时、TTS 耗时、失败率
13. 优化中文 voice persona
14. 补齐 `~/clawd/docs/` 本地业务文档

---

## 八、最终结论

**结论一句话：可行，而且大部分已经做好了。**

更准确地说：

1. **Telegram Bot API 层面**：原生支持接收 voice、下载文件、发送 voice message
2. **OpenClaw 当前能力**：
   - 入站语音接收：已支持
   - 入站语音 STT：已支持
   - 出站 TTS：已支持
   - Telegram 语音气泡发送：已支持
3. **是否要开发 skill**：
   - **不需要开发底层能力**
   - **建议开发一个 orchestration skill** 来把语音对话体验做顺

### 最推荐实施路径

- 先直接启用配置验证现有能力
- 再做 `telegram-voice-reply` skill 封装体验
- 主方案用 OpenAI，fallback 用本地 whisper / edge-tts

---

## 参考证据（关键来源）

### 本地源码

- `~/clawd/openclaw-src/src/telegram/bot-handlers.ts`
- `~/clawd/openclaw-src/src/telegram/bot/delivery.resolve-media.ts`
- `~/clawd/openclaw-src/src/media-understanding/audio-preflight.ts`
- `~/clawd/openclaw-src/src/media-understanding/transcribe-audio.ts`
- `~/clawd/openclaw-src/src/agents/tools/tts-tool.ts`
- `~/clawd/openclaw-src/src/tts/tts.ts`
- `~/clawd/openclaw-src/src/telegram/send.ts`
- `~/clawd/openclaw-src/src/telegram/voice.ts`
- `~/clawd/openclaw-src/src/media/audio.ts`

### 本地上游文档

- `~/clawd/openclaw-src/docs/nodes/audio.md`
- `~/clawd/openclaw-src/docs/providers/deepgram.md`
- `~/clawd/openclaw-src/docs/tools/plugin.md`

### 本地业务 docs

- `~/clawd/docs/one-company/telegram-setup-guide.md`
- `~/clawd/docs/SYSTEM_SUMMARY.md`

### 官方 docs / 外部参考

- `https://docs.openclaw.ai/nodes/audio`
- `https://docs.openclaw.ai/tools/plugin`
- `https://docs.openclaw.ai/providers/deepgram`
- `https://core.telegram.org/bots/api`
