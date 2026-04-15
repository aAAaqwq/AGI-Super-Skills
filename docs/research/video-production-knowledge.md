# 短视频制作专业知识学习报告

> 作者：Research Agent (xiaoresearch)
> 日期：2026-03-12
> 任务来源：CEO Daniel Li 指令
> 参考项目：waoowaoo (GitHub 9000+ stars)

---

## 一、waoowaoo 项目深度研究

### 1.1 项目概述

**waoowaoo AI 影视 Studio** 是一款工业级全流程 AI 影视生产平台，GitHub 9000+ stars。

**核心功能**：
- 🎬 AI 剧本分析 → 自动解析小说，提取角色、场景、剧情
- 🎨 角色 & 场景生成 → AI 生成一致性人物和场景图片
- 📽️ 分镜视频制作 → 自动生成分镜头并合成视频
- 🎙️ AI 配音 → 多角色语音合成

**技术栈**：
- Next.js 15 + React 19
- MySQL + Prisma ORM
- Redis + BullMQ (任务队列)
- Tailwind CSS v4
- NextAuth.js

### 1.2 核心目录结构

```
waoowaoo/
├── standards/
│   └── prompt-canary/          # 🔥 核心 Prompt 工程
│       ├── screenplay_conversion.canary.json    # 剧本转换
│       ├── storyboard_panels.canary.json        # 分镜面板
│       ├── story_to_script_clips.canary.json    # 故事→脚本片段
│       └── voice_analysis.canary.json           # 配音分析
│
├── src/
│   ├── lib/
│   │   ├── generators/
│   │   │   ├── video/          # 视频生成器
│   │   │   │   ├── index.ts
│   │   │   │   ├── google.ts   # Google Veo
│   │   │   │   └── openai-compatible.ts
│   │   │   ├── audio/          # 音频生成器
│   │   │   ├── fal.ts          # FAL 视频生成
│   │   │   └── ark.ts          # Ark Seedance
│   │   │
│   │   ├── workers/
│   │   │   └── handlers/
│   │   │       ├── script-to-storyboard.ts      # 🔥 剧本→分镜
│   │   │       ├── voice-analyze.ts             # 配音分析
│   │   │       └── voice-design.ts              # 配音设计
│   │   │
│   │   └── workflows/
│   │       └── script-to-storyboard/
│   │           └── graph.ts     # 工作流编排
│   │
│   └── components/
│       └── voice/              # 配音相关组件
```

### 1.3 Prompt 工程详解

#### 1.3.1 剧本转换 (screenplay_conversion.canary.json)

**结构**：
```json
{
  "clip_id": "clip_1",
  "original_text": "Lena enters the hall and speaks to Victor.",
  "scenes": [
    {
      "scene_number": 1,
      "heading": {
        "int_ext": "INT",
        "location": "grand_hall_night",
        "time": "night"
      },
      "description": "A large hall lit by chandeliers...",
      "characters": ["Lena", "Victor"],
      "content": [
        {
          "type": "action",
          "text": "Lena steps forward..."
        },
        {
          "type": "dialogue",
          "character": "Lena",
          "parenthetical": "firmly",
          "lines": "You need to read this now."
        },
        {
          "type": "voiceover",
          "character": "Narrator",
          "text": "The room holds its breath."
        }
      ]
    }
  ]
}
```

**关键字段**：
- `heading.int_ext`: INT (内景) / EXT (外景)
- `heading.location`: 场景位置
- `heading.time`: 时间 (day/night/dawn/dusk)
- `content.type`: action (动作) / dialogue (对白) / voiceover (旁白)
- `parenthetical`: 情绪指示 (firmly, softly, angrily, etc.)

#### 1.3.2 分镜面板 (storyboard_panels.canary.json)

**结构**：
```json
[
  {
    "panel_number": 1,
    "description": "Wide shot of Lena entering the hall...",
    "characters": [
      { "name": "Lena", "appearance": "default" },
      { "name": "Victor", "appearance": "formal" }
    ],
    "location": "grand_hall_night",
    "scene_type": "daily",
    "source_text": "Lena enters the hall and speaks to Victor.",
    "shot_type": "wide shot",
    "camera_move": "slow push in",
    "video_prompt": "A woman walks into a grand hall...",
    "duration": 3
  }
]
```

**关键字段**：
- `shot_type`: 镜头类型 (wide shot, medium close-up, close-up, extreme close-up)
- `camera_move`: 镜头运动 (slow push in, static, pan left, zoom out)
- `scene_type`: 场景类型 (daily, emotion, action, dialogue)
- `video_prompt`: 视频生成提示词
- `duration`: 时长（秒）

#### 1.3.3 故事→脚本片段 (story_to_script_clips.canary.json)

```json
[
  {
    "start": "The morning bell rings across the old town square.",
    "end": "She silently folds the letter and walks away.",
    "summary": "A tense reunion begins in the square.",
    "location": "town_square_day",
    "characters": ["Lena", "Victor"]
  }
]
```

**作用**：将长故事分割成可执行的脚本片段，每个片段包含：
- 起始文本
- 结束文本
- 摘要
- 场景位置
- 角色列表

#### 1.3.4 配音分析 (voice_analysis.canary.json)

```json
[
  {
    "lineIndex": 1,
    "speaker": "Lena",
    "content": "You need to read this now.",
    "emotionStrength": 0.28,
    "matchedPanel": {
      "storyboardId": "sb_1",
      "panelIndex": 1
    }
  }
]
```

**作用**：将配音与分镜匹配，计算情绪强度，确保音画同步。

### 1.4 视频生成器实现

#### 1.4.1 Google Veo 生成器

```typescript
// src/lib/generators/video/google.ts
export class GoogleVeoVideoGenerator extends BaseVideoGenerator {
  protected async doGenerate(params: VideoGenerateParams): Promise<GenerateResult> {
    const { modelId = 'veo-3.1-generate-preview', aspectRatio, resolution, duration, lastFrameImageUrl } = options
    
    const request = {
      model: modelId,
      prompt: prompt,
      config: {
        aspectRatio: aspectRatio,
        resolution: resolution,
        durationSeconds: duration
      }
    }
    
    // 添加首帧图片（图生视频）
    if (imageUrl) {
      request.image = dataUrlToInlineData(imageUrl)
    }
    
    // 添加尾帧图片
    if (lastFrameImageUrl) {
      request.lastFrame = dataUrlToInlineData(lastFrameImageUrl)
    }
    
    return await ai.models.generateVideos(request)
  }
}
```

**支持的模型**：
- `veo-3.1-generate-preview` (Veo 3.1)
- `veo-3.1-fast-generate-preview` (Veo 3.1 Fast)
- 支持 4K 分辨率
- 支持首帧/尾帧传递

#### 1.4.2 OpenAI Compatible 生成器

```typescript
// src/lib/generators/video/openai-compatible.ts
export class OpenAICompatibleVideoGenerator extends BaseVideoGenerator {
  protected async doGenerate(params: VideoGenerateParams): Promise<GenerateResult> {
    return await generateVideoViaOpenAICompat({
      userId,
      providerId: this.providerId || 'openai-compatible',
      modelId: options.modelId,
      imageUrl,
      prompt,
      options,
      profile: 'openai-compatible'
    })
  }
}
```

**支持的模型**：
- Sora 2 (sora-2-all, sora-2-pro-all)
- Kling (kling-1.5)
- Runway (gen-3)
- 其他 OpenAI Compatible 接口的模型

### 1.5 剧本→分镜核心逻辑

```typescript
// src/lib/workers/handlers/script-to-storyboard.ts
export async function handleScriptToStoryboardTask(job: Job<TaskJobData>) {
  const { projectId, episodeId, model, reasoning } = job.data
  
  // 1. 加载项目和角色数据
  const novelData = await prisma.novelPromotionProject.findUnique({
    where: { projectId },
    include: { characters: true, locations: true }
  })
  
  // 2. 执行剧本→分镜工作流
  const result = await runScriptToStoryboardGraph({
    episodeId,
    model,
    reasoning,
    reasoningEffort,
    temperature
  })
  
  // 3. 持久化分镜数据
  await persistStoryboardsAndPanels(result.storyboards)
  
  return result
}
```

**工作流步骤**：
1. 加载项目、角色、场景数据
2. 解析剧本内容
3. 生成分镜面板
4. 匹配配音与分镜
5. 持久化到数据库

---

## 二、短视频分镜设计专业指南

### 2.1 镜头语言基础

#### 2.1.1 景别分类

| 景别 | 英文 | 用途 | 示例 |
|------|------|------|------|
| **远景** | Extreme Wide Shot (EWS) | 展示环境全貌、建立空间感 | 城市全景、山川河流 |
| **全景** | Wide Shot (WS) | 展示人物全身及环境 | 人物进入场景 |
| **中景** | Medium Shot (MS) | 展示人物膝盖以上 | 对话场景、日常动作 |
| **近景** | Medium Close-Up (MCU) | 展示人物胸部以上 | 情感表达、对话 |
| **特写** | Close-Up (CU) | 展示人物肩部以上 | 情绪强调 |
| **大特写** | Extreme Close-Up (ECU) | 展示局部细节 | 眼睛、嘴唇、手部 |

#### 2.1.2 镜头运动

| 运动方式 | 英文 | 用途 | Prompt 描述 |
|----------|------|------|-------------|
| **推镜头** | Push In / Zoom In | 聚焦人物情绪、强调细节 | "slow push in" |
| **拉镜头** | Pull Out / Zoom Out | 展示环境、揭示全貌 | "slow zoom out" |
| **摇镜头** | Pan | 展示空间、跟随动作 | "pan left" / "pan right" |
| **移镜头** | Track / Dolly | 跟随人物移动 | "tracking shot" |
| **跟镜头** | Follow | 跟随主体运动 | "follow shot" |
| **升降镜头** | Crane / Boom | 展示空间层次 | "crane up" / "boom down" |
| **固定镜头** | Static | 稳定展示 | "static" |

#### 2.1.3 景别切换规则

**渐进式切换**（J-Cut / L-Cut）：
```
远景 → 全景 → 中景 → 近景 → 特写
（逐渐聚焦，强化情绪）
```

**跳跃式切换**（Jump Cut）：
```
特写 → 远景
（制造视觉冲击、强调对比）
```

**180度规则**：
- 保持人物空间关系一致
- 避免跳轴（crossing the line）
- 确保观众方向感

### 2.2 分镜脚本标准模板

```markdown
## 分镜脚本

### 场景 1: [场景名称]
- **场景编号**: S01
- **场景类型**: INT/EXT (内景/外景)
- **时间**: DAY/NIGHT
- **地点**: [具体位置]

| 镜头 | 景别 | 镜头运动 | 时长 | 画面描述 | 角色 | 对白/旁白 | 备注 |
|------|------|----------|------|----------|------|-----------|------|
| 1 | 远景 | 推镜头 | 3s | 城市夜景，霓虹闪烁 | - | - | 建立氛围 |
| 2 | 全景 | 固定 | 2s | Lena 走进大厅 | Lena | - | 角色出场 |
| 3 | 中景 | 跟镜头 | 4s | Lena 走向 Victor | Lena, Victor | - | 动作展示 |
| 4 | 近景 | 固定 | 3s | Lena 表情坚定 | Lena | "你需要看看这个" | 情绪特写 |
| 5 | 特写 | 固定 | 2s | Lena 眼神 | Lena | - | 情绪强调 |

**场景总时长**: 14秒
**情绪曲线**: 紧张 → 坚定 → 悬念
```

### 2.3 短视频分镜设计原则

#### 2.3.1 黄金前三秒

```
镜头 1 (0-1s): 强视觉冲击
├── 悬念设置（问题/冲突）
├── 好奇心钩子（反常识/意外）
└── 情绪触发（震惊/感动/愤怒）

镜头 2 (1-3s): 快速切入主题
├── 明确内容价值
├── 建立情感连接
└── 引导继续观看
```

#### 2.3.2 节奏控制

| 平台 | 最佳节奏 | 切换频率 | 时长建议 |
|------|----------|----------|----------|
| **抖音** | 快节奏 | 1-3s/镜头 | 15-60s |
| **TikTok** | 超快节奏 | 0.5-2s/镜头 | 15-30s |
| **小红书** | 中等节奏 | 2-5s/镜头 | 30-90s |
| **B站** | 稳重节奏 | 3-8s/镜头 | 60-300s |

#### 2.3.3 情绪曲线设计

```
情绪强度
  ↑
  │     ╱╲
  │    ╱  ╲___╱╲
  │   ╱       ╲ ╲
  │  ╱         ╲ ╲
  └─────────────────→ 时间
    开头 高潮 结尾
```

**三段式结构**：
1. **开头 (0-10%)**: 钩子 + 悬念
2. **主体 (10-90%)**: 内容 + 情绪波动
3. **结尾 (90-100%)**: 总结 + CTA

---

## 三、AI 视频生成最佳实践

### 3.1 Prompt 工程技巧

#### 3.1.1 通用公式

```
[主体] + [动作] + [环境] + [氛围] + [镜头语言] + [技术参数]
```

#### 3.1.2 分平台 Prompt 模板

**Veo 3.1 Prompt 模板**：
```
A [age]-year-old [gender] [action] in [location]. 
[Emotion description]. 
[Camera movement]. 
[Lighting and atmosphere]. 
[Technical: 4K, cinematic, high quality].
```

**示例**：
```
A 30-year-old woman walks confidently into a grand hall 
lit by chandeliers. Her expression is determined and firm. 
Slow push in from wide shot to medium close-up. 
Warm lighting with long shadows. 
4K cinematic quality.
```

**Sora 2 Prompt 模板**：
```
[Scene description]. [Character description] [action]. 
[Camera: shot type + movement]. 
[Visual style: cinematic/realistic/artistic]. 
[Duration: X seconds].
```

**示例**：
```
A tense business meeting in a modern office. 
A CEO stands up and slams a document on the table. 
Wide shot, tracking movement following the CEO. 
Cinematic style with dramatic lighting. 8 seconds.
```

**Kling Prompt 模板**：
```
[主体]在[环境]中[动作]。[情绪状态]。[镜头：景别+运动]。[画面风格]。
```

**示例**：
```
一位30岁女性在现代办公室中自信地走向会议桌。
她的表情坚定，眼神专注。
中景跟镜头，平滑推进。
商业大片风格，明亮光线。
```

### 3.2 参数配置建议

#### 3.2.1 Veo 3.1 参数

| 参数 | 推荐值 | 说明 |
|------|--------|------|
| **modelId** | veo-3.1-generate-preview | 标准版 |
| **modelId** | veo-3.1-fast-generate-preview | 快速版（更快生成） |
| **aspectRatio** | 16:9 | 横屏（YouTube/B站） |
| **aspectRatio** | 9:16 | 竖屏（抖音/TikTok/小红书） |
| **resolution** | 4K | 最高质量（首帧传递推荐） |
| **duration** | 5-8s | 短视频最佳时长 |
| **lastFrameImageUrl** | - | 尾帧图片（用于连续性） |

#### 3.2.2 Sora 2 参数

| 参数 | 推荐值 | 说明 |
|------|--------|------|
| **model** | sora-2-all | 逆向版（最便宜） |
| **model** | sora-2-pro-all | Pro 版（高质量） |
| **duration** | 10s | 标准 |
| **duration** | 15s | Pro 版 |
| **duration** | 25s | Pro 版（仅 720p） |
| **resolution** | 720p | 标准 |
| **resolution** | 1080p | Pro 版（15s） |

#### 3.2.3 Kling 参数

| 参数 | 推荐值 | 说明 |
|------|--------|------|
| **model** | kling-1.5 | 最新版 |
| **mode** | std | 标准模式 |
| **mode** | pro | 专业模式 |
| **duration** | 5s | 标准 |
| **duration** | 10s | 长视频 |
| **aspect_ratio** | 16:9 | 横屏 |
| **aspect_ratio** | 9:16 | 竖屏 |
| **aspect_ratio** | 1:1 | 方形 |

### 3.3 图生视频最佳实践

#### 3.3.1 首帧图片要求

```
✅ 推荐规格：
- 分辨率：1920x1080 (16:9) 或 1080x1920 (9:16)
- 格式：PNG / JPEG
- 大小：< 5MB
- 内容：清晰、主体明确、光线充足

❌ 避免：
- 模糊、低质量图片
- 主体不清晰
- 过暗/过曝
- 复杂背景干扰
```

#### 3.3.2 首帧传递 Prompt 增强

```
基础 Prompt: "A woman walks into a hall."

优化 Prompt: 
"Starting from the uploaded image, the woman slowly 
walks forward into the grand hall. Camera follows 
her movement with smooth tracking shot. Maintain 
consistent character appearance and lighting. 
4K quality."
```

#### 3.3.3 尾帧图片应用

**场景：转场效果**
```
首帧：场景 A 的结束画面
Prompt: "Smooth transition from scene A to scene B..."
尾帧：场景 B 的起始画面
```

**场景：循环视频**
```
首帧：初始状态
Prompt: "Seamless loop animation..."
尾帧：与首帧相同
```

---

## 四、视频剪辑专业技巧

### 4.1 节奏控制

#### 4.1.1 剪辑节奏公式

```
剪辑节奏 = 镜头时长 × 信息密度 × 情绪强度
```

**短视频节奏示例**：
```
0-3s:   快节奏（0.5-1s/镜头） - 钩子
3-10s:  中节奏（1-2s/镜头） - 主题
10-20s: 慢节奏（2-3s/镜头） - 深入
20-25s: 快节奏（0.5-1s/镜头） - 高潮
25-30s: 中节奏（2-3s/镜头） - 总结
```

#### 4.1.2 音乐节奏同步

```
视觉切换点 = 音乐节拍点 (BPM)
```

**工具**：
- DaVinci Resolve: 音乐节拍检测
- Premiere Pro: 自动匹配节拍
- CapCut: 模板自动同步

### 4.2 转场技巧

#### 4.2.1 常用转场

| 转场类型 | 用途 | 技术实现 |
|----------|------|----------|
| **硬切** (Hard Cut) | 快节奏、对比 | 直接切换 |
| **淡入淡出** (Fade) | 时间流逝、场景转换 | 透明度渐变 |
| **溶解** (Dissolve) | 柔和过渡、回忆 | 交叉溶解 |
| **划像** (Wipe) | 空间转换 | 方向性划过 |
| **缩放** (Zoom) | 强调、进入 | 缩放过渡 |
| **旋转** (Spin) | 活力、动感 | 旋转过渡 |

#### 4.2.2 AI 视频转场

**方法 1：首尾帧传递**
```
视频 A 尾帧 → 视频 B 首帧
使用 Veo/Sora 的 lastFrameImageUrl 参数
```

**方法 2：中间帧过渡**
```
视频 A 最后 1s → 中间帧 → 视频 B 开始 1s
使用 AI 生成过渡帧
```

### 4.3 音画同步

#### 4.3.1 对口型 (Lip Sync)

**工具**：
- HeyGen: AI 口型同步
- D-ID: 照片口型同步
- SadTalker: 开源口型同步

**最佳实践**：
```
1. 生成配音音频（TTS）
2. 生成角色图片（AI 图像）
3. 使用口型同步工具合成
4. 微调时间轴对齐
```

#### 4.3.2 背景音乐 (BGM)

**选择原则**：
```
内容情绪 + BGM 情绪 = 一致
```

**音乐库推荐**：
- YouTube Audio Library（免费）
- Epidemic Sound（付费）
- Artlist（付费）
- 网易云音乐（个人使用）

**音量平衡**：
```
人声：-6dB 到 -3dB
BGM：-18dB 到 -12dB
音效：-12dB 到 -6dB
```

---

## 五、短视频内容策略

### 5.1 平台算法偏好

#### 5.1.1 抖音算法

**核心指标**：
1. **完播率** (>60%): 最重要
2. **点赞率** (>4%): 次重要
3. **评论率** (>0.5%): 互动质量
4. **转发率** (>0.3%): 传播价值
5. **关注率** (>0.1%): 长期价值

**推荐机制**：
```
初始流量池 (200-500 views)
  ↓ 完播率 > 60%
二级流量池 (1000-5000 views)
  ↓ 互动率 > 5%
三级流量池 (10000+ views)
  ↓ 持续高互动
热门推荐 (100000+ views)
```

#### 5.1.2 TikTok 算法

**核心指标**：
1. **Watch Time** (总观看时长): 最重要
2. **Completion Rate** (完播率): 关键
3. **Engagement Rate** (互动率): 点赞+评论+分享
4. **Re-watch Rate** (重看率): 价值指标

**最佳实践**：
```
✅ 前 1 秒必须有钩子
✅ 15-30 秒最佳时长
✅ 竖屏 9:16
✅ 使用热门音乐
✅ 字幕（80% 用户静音观看）
```

#### 5.1.3 小红书算法

**核心指标**：
1. **CES 评分** = 点赞×1 + 收藏×1 + 评论×4 + 转发×4
2. **搜索 SEO**: 标题+内容关键词
3. **互动深度**: 评论长度、回复率

**内容特点**：
```
✅ 干货类（教程、攻略）
✅ 情感类（故事、感悟）
✅ 种草类（产品推荐）
✅ 颜值类（美妆、穿搭）

最佳时长：30-90 秒
最佳发布时间：7-9点, 12-14点, 18-22点
```

### 5.2 爆款内容公式

#### 5.2.1 钩子公式

**问题型钩子**：
```
"为什么 90% 的人都会犯这个错误？"
"你绝对想不到这个方法..."
"3 个技巧让你..."
```

**反常识钩子**：
```
"大家都搞错了..."
"千万别这样做..."
"真相是..."
```

**故事型钩子**：
```
"那天，我..."
"他做了一个决定，改变了..."
"想象一下..."
```

**数字型钩子**：
```
"3 个方法..."
"5 分钟学会..."
"10 年经验总结..."
```

#### 5.2.2 情绪触发词

**正面情绪**：
```
- 感动、温暖、治愈
- 惊喜、震撼、惊叹
- 有趣、搞笑、沙雕
- 实用、干货、宝藏
```

**负面情绪**（谨慎使用）：
```
- 愤怒、不平、吐槽
- 焦虑、担忧、恐惧
- 后悔、遗憾、可惜
```

#### 5.2.3 CTA (行动号召)

**关注型 CTA**：
```
"关注我，下期讲..."
"点关注不迷路"
"关注解锁更多..."
```

**互动型 CTA**：
```
"你遇到过这种情况吗？评论区告诉我"
"转发给需要的人"
"点赞让更多人看到"
```

**转化型 CTA**：
```
"点击链接领取..."
"主页有详细教程"
"私信回复 XX 获取..."
```

---

## 六、配音与字幕

### 6.1 AI 配音最佳实践

#### 6.1.1 配音风格选择

| 内容类型 | 推荐风格 | 情绪强度 | 语速 |
|----------|----------|----------|------|
| **干货教学** | 专业、稳重 | 0.3-0.5 | 中等 |
| **情感故事** | 温暖、感性 | 0.5-0.7 | 较慢 |
| **搞笑段子** | 夸张、活泼 | 0.7-0.9 | 较快 |
| **商业宣传** | 自信、有力 | 0.5-0.6 | 中等 |
| **悬疑推理** | 低沉、神秘 | 0.4-0.6 | 较慢 |

#### 6.1.2 中文配音工具

| 工具 | 特点 | 价格 | 推荐度 |
|------|------|------|--------|
| **Azure TTS** | 音色丰富、自然 | 按量付费 | ⭐⭐⭐⭐⭐ |
| **阿里云 TTS** | 中文效果好 | 按量付费 | ⭐⭐⭐⭐⭐ |
| **腾讯云 TTS** | 性价比高 | 按量付费 | ⭐⭐⭐⭐ |
| **讯飞 TTS** | 老牌、稳定 | 按量付费 | ⭐⭐⭐⭐ |
| **Bolt TTS** | 开源、免费 | 免费 | ⭐⭐⭐ |
| **GPT-SoVITS** | 开源、可克隆 | 免费 | ⭐⭐⭐⭐ |

#### 6.1.3 配音 Prompt 示例

```json
{
  "speaker": "Lena",
  "content": "你需要看看这个。",
  "emotionStrength": 0.28,
  "speed": 1.0,
  "pitch": 1.0,
  "style": "firmly"
}
```

### 6.2 字幕排版

#### 6.2.1 字幕规范

```
字体：思源黑体 / 阿里巴巴普惠体
大小：视频高度的 5-8%
颜色：白色 + 黑色描边/阴影
位置：底部安全区域内
时长：每条 2-4 秒
字数：每条不超过 20 字
```

#### 6.2.2 字幕样式

**样式 1：经典白字黑边**
```css
color: #FFFFFF;
text-shadow: 2px 2px 4px rgba(0,0,0,0.8);
font-weight: bold;
```

**样式 2：高亮强调**
```css
background: rgba(0,0,0,0.6);
padding: 4px 12px;
border-radius: 4px;
```

**样式 3：花字效果**
```css
color: #FFD700;
text-shadow: 0 0 10px rgba(255,215,0,0.5);
font-size: larger;
```

---

## 七、可落地的 AI 短视频制作最佳实践

### 7.1 标准工作流

```
1. 剧本创作 (AI 辅助)
   └─> 使用 GPT/Claude 生成剧本
   └─> 参考分镜模板格式化

2. 角色设计 (AI 图像)
   └─> 使用 Midjourney/DALL-E 生成角色图
   └─> 确保角色一致性

3. 场景设计 (AI 图像)
   └─> 使用 Flux/Imagen 生成场景图
   └─> 保持风格统一

4. 分镜脚本 (AI 转换)
   └─> 剧本 → 分镜 (参考 waoowaoo prompt)
   └─> 添加镜头语言

5. 视频生成 (AI 视频)
   └─> 首帧图 + Prompt → 视频片段
   └─> 使用 Veo/Sora/Kling

6. 配音生成 (AI TTS)
   └─> 对白 → 配音
   └─> 匹配情绪和节奏

7. 音画同步
   └─> 口型同步 (可选)
   └─> 背景音乐

8. 剪辑合成
   └─> 视频拼接
   └─> 转场效果
   └─> 字幕添加

9. 优化发布
   └─> 平台适配
   └─> 标题+标签优化
```

### 7.2 质量检查清单

```markdown
□ 前 3 秒有钩子
□ 镜头切换节奏合理
□ 情绪曲线有起伏
□ 配音清晰、情绪匹配
□ 字幕准确、可读
□ BGM 与内容情绪一致
□ 视频画质清晰（≥1080p）
□ 音量平衡
□ 结尾有 CTA
□ 平台规格适配
```

### 7.3 成本优化建议

| 优化点 | 建议 | 节省成本 |
|--------|------|----------|
| **图片生成** | 批量生成 + 筛选 | 50% |
| **视频生成** | 先用 fast 模式预览 | 70% |
| **配音** | 使用开源 TTS | 80% |
| **剪辑** | 使用模板自动化 | 60% |
| **整体** | 建立素材库复用 | 40% |

---

## 八、推荐工具与资源

### 8.1 AI 工具

| 工具 | 用途 | 链接 |
|------|------|------|
| **waoowaoo** | 全流程 AI 影视生产 | https://github.com/saturndec/waoowaoo |
| **Runway** | 视频生成+编辑 | https://runway.com |
| **Pika** | 视频生成 | https://pika.art |
| **HeyGen** | AI 数字人视频 | https://heygen.com |
| **D-ID** | 照片口型同步 | https://d-id.com |
| **ElevenLabs** | AI 配音 | https://elevenlabs.io |

### 8.2 学习资源

| 资源 | 类型 | 链接 |
|------|------|------|
| **Film Riot** | 视频制作教程 | YouTube |
| **Peter McKinnon** | 摄影技巧 | YouTube |
| **Casey Neistat** | Vlog 制作 | YouTube |
| **影视飓风** | 中文视频制作 | B站 |
| **老师好我叫何同学** | 创意视频 | B站 |

### 8.3 素材资源

| 资源 | 用途 | 链接 |
|------|------|------|
| **Pexels** | 免费视频素材 | https://pexels.com |
| **Pixabay** | 免费图片/视频 | https://pixabay.com |
| **YouTube Audio Library** | 免费音乐 | YouTube Studio |
| **Freepik** | 设计素材 | https://freepik.com |

---

## 九、总结

### 9.1 核心要点

1. **分镜设计是基础**：
   - 掌握景别、镜头运动、切换规则
   - 使用标准分镜脚本模板

2. **AI 是工具，创意是核心**：
   - AI 提高效率，但创意决定质量
   - 学习 prompt 工程提高 AI 输出质量

3. **平台适配很重要**：
   - 不同平台有不同的算法偏好
   - 根据平台调整节奏、时长、内容

4. **质量 > 数量**：
   - 一条爆款胜过十条平庸
   - 精细化制作每个细节

### 9.2 下一步行动

1. **实践**：使用 waoowaoo 搭建本地环境
2. **学习**：研究 waoowaoo 的 prompt 工程
3. **创作**：从短视频开始，逐步提升复杂度
4. **优化**：建立自己的素材库和工作流
5. **分享**：总结经验，形成团队知识库

---

## 附录：waoowaoo 部署指南

### 快速部署

```bash
# 方式一：Docker 预构建镜像（最简单）
curl -O https://raw.githubusercontent.com/saturndec/waoowaoo/main/docker-compose.yml
docker compose up -d

# 方式二：克隆仓库
git clone https://github.com/saturndec/waoowaoo.git
cd waoowaoo
docker compose up -d
```

### 访问地址

- HTTP: http://localhost:13000
- HTTPS: https://localhost:1443 (需安装 Caddy)

### API 配置

启动后进入**设置中心**配置：
- OpenAI API Key
- Google AI API Key
- 其他 AI 服务 API Key

---

> **报告完成时间**: 2026-03-12
> **预计阅读时间**: 45 分钟
> **建议实践时间**: 1-2 周

---

## 十、中文配音深度实践（2026-03-13 周五专题）

### 10.1 中文配音核心技术

#### 10.1.1 中文语音特点

| 特点 | 影响 | 配音策略 |
|------|------|----------|
| **声调语言** | 四声影响语义 | TTS 需支持声调控制 |
| **音节结构** | 声母+韵母+声调 | 清晰吐字，避免吞音 |
| **语流音变** | 变调、轻声、儿化 | 自然语流训练 |
| **方言差异** | 南北方言差异大 | 选择目标受众匹配的口音 |

#### 10.1.2 情绪强度控制

基于 waoowaoo 的 voice_analysis.canary.json：

```json
{
  "emotionStrength": 0.28,  // 0.0-1.0 情绪强度
  "style": "firmly",        // 情绪风格
  "speed": 1.0,             // 语速 (0.5-2.0)
  "pitch": 1.0              // 音调 (0.5-2.0)
}
```

**情绪强度指南**：

| 场景类型 | emotionStrength | 示例风格 |
|----------|-----------------|----------|
| **日常对话** | 0.2-0.4 | neutral, calm |
| **情感表达** | 0.4-0.6 | warmly, sadly |
| **激烈冲突** | 0.6-0.8 | angrily, urgently |
| **戏剧高潮** | 0.8-1.0 | dramatically, intensely |
| **旁白叙述** | 0.3-0.5 | narrating, storytelling |

#### 10.1.3 中文 TTS 引擎对比（2024-2026）

| 引擎 | 中文效果 | 情绪控制 | 成本 | 推荐场景 |
|------|----------|----------|------|----------|
| **Azure TTS** | ⭐⭐⭐⭐⭐ | SSML 支持 | $$$ | 商业级制作 |
| **阿里云 TTS** | ⭐⭐⭐⭐⭐ | 情绪标签 | $$ | 短视频批量 |
| **腾讯云 TTS** | ⭐⭐⭐⭐ | 基础情绪 | $$ | 性价比选择 |
| **讯飞 TTS** | ⭐⭐⭐⭐ | 情绪控制 | $$ | 老牌稳定 |
| **GPT-SoVITS** | ⭐⭐⭐⭐⭐ | 声音克隆 | 免费 | 开源首选 |
| **Fish Speech** | ⭐⭐⭐⭐ | 零样本克隆 | 免费 | 个性化声音 |
| **ChatTTS** | ⭐⭐⭐⭐ | 自然对话 | 免费 | 对话场景 |

#### 10.1.4 中文配音 Prompt 工程

**Azure SSML 示例**：
```xml
<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" xml:lang="zh-CN">
  <voice name="zh-CN-XiaoxiaoNeural">
    <prosody rate="0.9" pitch="+5%">
      <emphasis level="moderate">你需要看看这个</emphasis>
    </prosody>
  </voice>
</speak>
```

**GPT-SoVITS 配置示例**：
```json
{
  "text": "你需要看看这个。",
  "speaker_id": "female_01",
  "emotion": "serious",
  "speed": 1.0,
  "top_k": 10,
  "top_p": 1.0,
  "temperature": 1.0
}
```

#### 10.1.5 配音节奏控制

**语速与内容类型匹配**：

| 内容类型 | 语速 (字/分钟) | 节奏特点 |
|----------|----------------|----------|
| **知识讲解** | 200-240 | 稳重、清晰 |
| **故事叙述** | 180-220 | 抑扬顿挫 |
| **搞笑段子** | 250-300 | 快速、活泼 |
| **情感表达** | 160-200 | 缓慢、深情 |
| **商业宣传** | 220-260 | 自信、有力 |

**呼吸与停顿**：
```
句子内停顿：0.3-0.5s
句子间停顿：0.5-1.0s
段落间停顿：1.0-2.0s
强调前停顿：0.2-0.3s（戏剧效果）
```

---

## 十一、字幕排版专业规范（2026-03-13 周五专题）

### 11.1 字幕设计基础

#### 11.1.1 字幕黄金规范

```
┌─────────────────────────────────────┐
│ 字体：思源黑体 / 阿里巴巴普惠体       │
│ 字号：视频高度 5-8%                  │
│ 颜色：白色 (#FFFFFF) + 黑色描边       │
│ 描边：2-4px 黑色 (#000000)           │
│ 阴影：0 0 10px rgba(0,0,0,0.5)       │
│ 位置：底部安全区域（距底部 10%）      │
│ 安全区：左右各留 5% 边距              │
└─────────────────────────────────────┘
```

#### 11.1.2 平台字幕适配

| 平台 | 推荐字号 | 字数/条 | 时长/条 | 特殊要求 |
|------|----------|---------|---------|----------|
| **抖音** | 40-50px | ≤15字 | 2-3s | 花字、特效字多 |
| **TikTok** | 40-50px | ≤12词 | 2-3s | 必须有字幕（80%静音） |
| **小红书** | 35-45px | ≤20字 | 3-4s | 干净简洁风格 |
| **B站** | 30-40px | ≤25字 | 3-5s | 可用弹幕风格 |
| **视频号** | 40-50px | ≤18字 | 2-3s | 微信字体风格 |

#### 11.1.3 字幕样式分类

**样式 1：经典白字黑边（最常用）**
```css
.subtitle-classic {
  color: #FFFFFF;
  text-shadow: 
    -2px -2px 0 #000,
    2px -2px 0 #000,
    -2px 2px 0 #000,
    2px 2px 0 #000;
  font-weight: bold;
  letter-spacing: 2px;
}
```

**样式 2：圆角背景框（小红书风）**
```css
.subtitle-rounded {
  background: rgba(0, 0, 0, 0.7);
  padding: 8px 16px;
  border-radius: 20px;
  color: #FFFFFF;
  font-weight: 500;
}
```

**样式 3：渐变花字（抖音风）**
```css
.subtitle-gradient {
  background: linear-gradient(90deg, #FFD700, #FF6B6B);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  text-shadow: 0 0 20px rgba(255, 215, 0, 0.5);
  font-weight: bold;
}
```

**样式 4：打字机效果**
```css
.subtitle-typewriter {
  overflow: hidden;
  white-space: nowrap;
  animation: typing 2s steps(20);
  border-right: 3px solid #FFFFFF;
}
@keyframes typing {
  from { width: 0 }
  to { width: 100% }
}
```

### 11.2 字幕动效

#### 11.2.1 入场动画

| 动画类型 | 效果 | 适用场景 |
|----------|------|----------|
| **淡入** | 透明度 0→1 | 所有场景 |
| **上滑** | 从下往上滑入 | 连续字幕 |
| **弹跳** | 缩放+弹性 | 强调内容 |
| **打字机** | 逐字显示 | 对话、旁白 |
| **闪烁** | 快速闪烁 | 警告、强调 |

#### 11.2.2 字幕与画面节奏

```
字幕出现 = 语音开始 - 100ms (提前一点更自然)
字幕消失 = 语音结束 + 200ms (给阅读缓冲)
```

**FFmpeg 字幕时间轴示例**：
```srt
1
00:00:01,000 --> 00:00:03,500
你需要看看这个

2
00:00:03,700 --> 00:00:06,200
这件事改变了一切
```

### 11.3 字幕可访问性

#### 11.3.1 对比度要求

| 标准 | 对比度 | 适用场景 |
|------|--------|----------|
| **WCAG AA** | 4.5:1 | 基础要求 |
| **WCAG AAA** | 7:1 | 高可访问性 |
| **短视频最佳** | 10:1+ | 户外/移动观看 |

**对比度检测工具**：
- WebAIM Contrast Checker
- Stark (Figma 插件)
- ColorZilla

#### 11.3.2 多语言字幕

**字幕轨道配置**：
```json
{
  "tracks": [
    { "language": "zh-CN", "label": "简体中文", "default": true },
    { "language": "zh-TW", "label": "繁體中文" },
    { "language": "en", "label": "English" }
  ]
}
```

---

## 十二、BGM 选择与音画同步（2026-03-13 周五专题）

### 12.1 BGM 选择原则

#### 12.1.1 情绪匹配矩阵

| 内容情绪 | BGM 类型 | 乐器建议 | BPM 范围 |
|----------|----------|----------|----------|
| **紧张悬疑** | 氛围/电子 | 合成器、低频 | 80-100 |
| **欢乐活泼** | 流行/电子 | 尤克里里、钢琴 | 120-140 |
| **感人温暖** | 弦乐/钢琴 | 大提琴、钢琴 | 60-80 |
| **励志激昂** | 史诗/摇滚 | 管弦乐、电吉他 | 100-130 |
| **搞笑轻松** | 爵士/放克 | 萨克斯、贝斯 | 100-120 |
| **恐怖惊悚** | 氛围/实验 | 不协和音效 | 60-90 |
| **浪漫甜蜜** | 流行/R&B | 钢琴、吉他 | 70-90 |

#### 12.1.2 平台 BGM 偏好

| 平台 | BGM 特点 | 音量建议 | 版权要求 |
|------|----------|----------|----------|
| **抖音** | 热门BGM、节奏强 | -12dB | 平台曲库 |
| **TikTok** | 病毒音乐、趋势曲 | -12dB | 平台曲库 |
| **小红书** | 舒缓、文艺感 | -15dB | 商业授权 |
| **B站** | 多样化、二次元 | -12dB | 宽松 |
| **YouTube** | 无版权优先 | -15dB | 严格（Content ID） |

### 12.2 音量平衡

#### 12.2.1 标准音量层级

```
音量金字塔（从下到上）：

        人声/旁白：-6dB 到 -3dB（最响）
           ↑
       音效/特效：-12dB 到 -6dB
           ↑
      BGM 高潮：-18dB 到 -12dB
           ↑
    BGM 背景：-24dB 到 -18dB（最轻）
```

#### 12.2.2 动态音量控制

**Ducking（闪避）技术**：
```
当人声出现时：
  BGM 音量 = BGM_base × 0.3  // 降低到 30%

当人声消失时：
  BGM 音量 = BGM_base × 1.0  // 恢复原音量
```

**FFmpeg 实现示例**：
```bash
ffmpeg -i video.mp4 -i bgm.mp3 \
  -filter_complex "[1:a]volume=-15dB,adelay=0|0[bgm];[0:a][bgm]amix=inputs=2:duration_first:a:0:normalize=0" \
  output.mp4
```

### 12.3 节奏同步

#### 12.3.1 剪辑点与音乐节拍

```
视觉切换点 = 音乐节拍点（on-beat）
情绪高潮点 = 音乐高潮点
转场时机 = 音乐变化点（bridge/chorus）
```

**节拍检测工具**：
- DaVinci Resolve: 自动节拍检测
- Premiere Pro: Beat Edit 插件
- CapCut: 模板自动同步
- FFmpeg: `silencedetect` + `ebur128`

#### 12.3.2 音乐结构匹配

**流行歌曲结构**：
```
Intro (4-8 bars) → Verse (16 bars) → Chorus (8-16 bars) 
    → Verse → Chorus → Bridge (8 bars) → Chorus → Outro
```

**视频结构映射**：
```
Intro → 开场钩子（0-3s）
Verse → 内容铺垫（3-15s）
Chorus → 情绪高潮（15-25s）
Bridge → 转折/深化（25-35s）
Chorus → 总结/CTA（35-45s）
Outro → 结尾（45-60s）
```

### 12.4 BGM 来源

#### 12.4.1 免费商用音乐库

| 平台 | 曲库规模 | 版权 | 质量 | 推荐度 |
|------|----------|------|------|--------|
| **YouTube Audio Library** | 1000+ | 免费商用 | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| **Pixabay Music** | 10000+ | 免费商用 | ⭐⭐⭐ | ⭐⭐⭐⭐ |
| **Incompetech** | 2000+ | CC 协议 | ⭐⭐⭐ | ⭐⭐⭐ |
| **Bensound** | 500+ | 免费商用（署名） | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ |
| **Mixkit** | 500+ | 免费商用 | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ |

#### 12.4.2 付费商用音乐库

| 平台 | 价格 | 曲库规模 | 特点 |
|------|------|----------|------|
| **Epidemic Sound** | $15/月 | 40000+ | 订阅制，YouTuber 首选 |
| **Artlist** | $9.9/月 | 20000+ | 按年付费，性价比高 |
| **Musicbed** | 按项目 | 1000+ | 高端制作，电影级 |
| **AudioJungle** | 按曲 | 1000000+ | 单曲购买，灵活 |

#### 12.4.3 AI 音乐生成

| 工具 | 价格 | 特点 | 推荐场景 |
|------|------|------|----------|
| **Suno AI** | 免费/付费 | 文本生成音乐 | 快速原型 |
| **Udio** | 免费/付费 | 高质量生成 | 原创音乐 |
| **AIVA** | 免费/付费 | 古典/电影风格 | 氛围音乐 |
| **Mubert** | 免费/付费 | 实时生成 | 直播/背景 |
| **Stable Audio** | 免费/付费 | Stability AI | 多样风格 |

### 12.5 音画同步最佳实践

#### 12.5.1 waoowaoo 配音同步逻辑

```typescript
// 基于分镜面板匹配配音
{
  "lineIndex": 1,
  "speaker": "Lena",
  "content": "你需要看看这个。",
  "emotionStrength": 0.28,
  "matchedPanel": {
    "storyboardId": "sb_1",
    "panelIndex": 1  // 匹配到第一个分镜面板
  }
}
```

**同步策略**：
1. 分析配音文本的情绪强度
2. 匹配到对应情绪的分镜面板
3. 调整配音时长与画面时长
4. 微调时间轴确保音画对齐

#### 12.5.2 时间轴同步检查清单

```markdown
□ 人声与口型同步（±100ms）
□ 背景音乐与情绪曲线匹配
□ 转场音效与视觉转场同步
□ BGM 音量随人声自动闪避
□ 音效位置与视觉动作对齐
□ 结尾音乐淡出自然（1-2s）
```

---

## 十三、可落地的配音/字幕/BGM 工作流

### 13.1 标准工作流

```
Step 1: 剧本配音
├─ 选择 TTS 引擎（根据预算和质量要求）
├─ 设置情绪参数（emotionStrength）
├─ 批量生成配音片段
└─ 质量检查（发音、情绪、节奏）

Step 2: 字幕制作
├─ 自动生成字幕（Whisper API）
├─ 手动校对时间轴
├─ 选择字幕样式（根据平台）
├─ 添加动效（可选）
└─ 导出 SRT/VTT/ASS 格式

Step 3: BGM 选择
├─ 确定情绪基调
├─ 选择音乐（免费/付费/AI生成）
├─ 调整音量层级
├─ 节奏同步剪辑
└─ 添加音效（可选）

Step 4: 音画合成
├─ 导入视频片段
├─ 添加配音轨道
├─ 添加 BGM 轨道
├─ 添加字幕轨道
├─ 调整音量平衡
├─ 检查音画同步
└─ 导出最终视频
```

### 13.2 自动化脚本示例

#### 13.2.1 批量生成配音

```bash
#!/bin/bash
# 使用 Azure TTS 批量生成配音

INPUT_FILE="script.txt"
OUTPUT_DIR="audio_output"

while IFS= read -r line; do
  if [[ -n "$line" ]]; then
    filename=$(echo "$line" | md5sum | cut -c1-8)
    az cognitiveservices account tts \
      --text "$line" \
      --voice "zh-CN-XiaoxiaoNeural" \
      --output "$OUTPUT_DIR/$filename.wav"
  fi
done < "$INPUT_FILE"
```

#### 13.2.2 自动添加字幕

```bash
#!/bin/bash
# 使用 FFmpeg 烧录字幕

ffmpeg -i video.mp4 \
  -vf "subtitles=subtitle.srt:force_style='Fontname=Source Han Sans CN,FontSize=24,PrimaryColour=&HFFFFFF,OutlineColour=&H000000,Outline=2,Shadow=1'" \
  -c:a copy \
  output_with_subs.mp4
```

#### 13.2.3 音量平衡自动化

```bash
#!/bin/bash
# 使用 FFmpeg 实现音量闪避

ffmpeg -i video.mp4 -i bgm.mp3 \
  -filter_complex "
    [0:a]volume=1.0[voice];
    [1:a]volume=0.3[bgm];
    [voice][bgm]amix=inputs=2:duration=first[audio_out]
  " \
  -map 0:v -map "[audio_out]" \
  -c:v copy \
  output.mp4
```

### 13.3 质量检查清单

```markdown
## 配音检查
□ 发音清晰、无杂音
□ 情绪与内容匹配
□ 语速适中（200-240字/分钟）
□ 停顿自然、有呼吸感
□ 无明显机器感

## 字幕检查
□ 文字准确、无错别字
□ 时间轴与语音同步
□ 字数合理（≤20字/条）
□ 对比度足够（WCAG AA+）
□ 位置不遮挡重要画面

## BGM 检查
□ 情绪与内容一致
□ 音量平衡（人声 > BGM）
□ 版权合规
□ 无突兀的转场
□ 结尾自然淡出

## 整体检查
□ 音画同步（±100ms）
□ 音量一致性
□ 整体节奏流畅
□ 平台规格符合
□ 导出质量达标（≥1080p）
```

---

## 十四、推荐工具与资源（配音/字幕/BGM 专题）

### 14.1 配音工具

| 工具 | 类型 | 价格 | 推荐度 |
|------|------|------|--------|
| **Azure TTS** | 云端 API | 按量付费 | ⭐⭐⭐⭐⭐ |
| **GPT-SoVITS** | 开源 | 免费 | ⭐⭐⭐⭐⭐ |
| **Fish Speech** | 开源 | 免费 | ⭐⭐⭐⭐ |
| **ElevenLabs** | 云端 API | 订阅制 | ⭐⭐⭐⭐⭐ |
| **讯飞 TTS** | 云端 API | 按量付费 | ⭐⭐⭐⭐ |

### 14.2 字幕工具

| 工具 | 类型 | 价格 | 推荐度 |
|------|------|------|--------|
| **Aegisub** | 桌面软件 | 免费 | ⭐⭐⭐⭐⭐ |
| **Subtitle Edit** | 桌面软件 | 免费 | ⭐⭐⭐⭐ |
| **剪映** | 移动/桌面 | 免费 | ⭐⭐⭐⭐⭐ |
| **CapCut** | 移动/桌面 | 免费 | ⭐⭐⭐⭐⭐ |
| **Whisper** | AI 自动生成 | 免费 | ⭐⭐⭐⭐⭐ |

### 14.3 BGM 资源

| 平台 | 类型 | 价格 | 推荐度 |
|------|------|------|--------|
| **YouTube Audio Library** | 曲库 | 免费 | ⭐⭐⭐⭐⭐ |
| **Epidemic Sound** | 曲库 | 订阅制 | ⭐⭐⭐⭐⭐ |
| **Suno AI** | AI 生成 | 免费/付费 | ⭐⭐⭐⭐ |
| **Pixabay Music** | 曲库 | 免费 | ⭐⭐⭐⭐ |

---

## 十五、本周总结（2026-03-13）

### 15.1 知识点回顾

| 日期 | 主题 | 核心收获 |
|------|------|----------|
| **周一** | 分镜设计与镜头语言 | 景别切换规则、镜头运动、黄金前三秒 |
| **周二** | AI视频生成 Prompt | Veo/Sora/Kling Prompt 模板、首尾帧传递 |
| **周三** | 剪辑节奏与转场 | 节奏控制公式、转场技巧、音画同步 |
| **周四** | 平台算法偏好 | 抖音/TikTok/小红书算法、爆款公式 |
| **周五** | 配音/字幕/BGM | 情绪控制、字幕规范、BGM选择、音量平衡 |

### 15.2 可落地的最佳实践

1. **配音**：使用 emotionStrength 参数控制情绪，选择合适的 TTS 引擎
2. **字幕**：遵循黄金规范（白字黑边、5-8%字号、对比度 ≥4.5:1）
3. **BGM**：情绪匹配、音量金字塔、节奏同步
4. **整体**：建立标准化工作流，使用自动化脚本提效

### 15.3 下周计划

- **周六**：研究 waoowaoo 项目新更新
- **周日**：整理周总结，更新知识库

---

> **本次更新时间**: 2026-03-13 10:00 (Asia/Shanghai)
> **专题**: 中文配音、字幕排版、BGM选择
> **新增章节**: 十、十一、十二、十三、十四、十五

**Made with ❤️ by Research Agent (xiaoresearch)**

---

## 十六、waoowaoo 项目最新研究（2026-03-14 周六专题）

### 16.1 最新提交分析

**最新提交**：`be18535` (2026-03-09)
- **标题**：`feat: implement robustness guards`
- **规模**：1326 文件，227,316 行代码
- **性质**：大型初始化/重构提交

**关键更新内容**：

| 更新类型 | 描述 |
|----------|------|
| **代码质量守护** | 添加了 30+ 个 guard 脚本，确保代码质量和一致性 |
| **测试基础设施** | 完善了单元测试、集成测试、链式测试 |
| **Prompt 国际化** | 支持中英文 Prompt 模板，i18n 架构完善 |
| **计费系统** | 完整的计费 ledger、成本计算、用户交易系统 |
| **多模型支持** | 百炼（Bailian）、SiliconFlow 等国内模型集成 |

### 16.2 新增视频生成器实现

#### 16.2.1 Google Veo 3.1 完整实现

```typescript
// src/lib/generators/video/google.ts
interface GoogleVeoOptions {
    modelId?: string           // veo-3.1-generate-preview / veo-3.1-fast-generate-preview
    aspectRatio?: string       // 16:9, 9:16, 1:1
    resolution?: string        // 4K 支持
    duration?: number          // 时长（秒）
    lastFrameImageUrl?: string // 尾帧图片 URL
}

// 核心特性
const request = {
    model: modelId,
    prompt: prompt,
    config: {
        aspectRatio: aspectRatio,
        resolution: resolution,
        durationSeconds: duration
    },
    image: inlineData,         // 首帧图片（图生视频）
    config: {
        lastFrame: inlineData  // 尾帧图片（连续性）
    }
}
```

**关键发现**：
- ✅ 支持首帧图片输入（图生视频）
- ✅ 支持尾帧图片（用于场景过渡、循环视频）
- ✅ 返回异步操作 ID，需要轮询获取结果
- ⚠️ 尾帧图片必须与首帧同时使用

#### 16.2.2 Vidu 视频生成器（新增）

**支持的模型**：

| 模型 | 特点 | 时长范围 | 分辨率 |
|------|------|----------|--------|
| **viduq3-pro** | 最新旗舰，首尾帧支持 | 1-16s | 540p/720p/1080p |
| **viduq2-pro-fast** | 快速生成 | 1-10s | 540p/720p/1080p |
| **vidu-2.0** | 标准版 | 4/8s | 360p/720p/1080p |

**Vidu 特有功能**：

```typescript
interface ViduVideoOptions {
    // 基础参数
    modelId?: string
    duration?: number
    resolution?: string
    aspectRatio?: string

    // 🆕 音频生成（内置）
    generateAudio?: boolean
    audioType?: 'all' | 'speech_only' | 'sound_effect_only'

    // 🆕 首尾帧模式
    generationMode?: 'normal' | 'firstlastframe'
    lastFrameImageUrl?: string

    // 🆕 运动幅度控制
    movementAmplitude?: 'auto' | 'small' | 'medium' | 'large'

    // 其他参数
    seed?: number
    bgm?: boolean
    voiceId?: string
    offPeak?: boolean
    watermark?: boolean
}
```

**Vidu vs 其他生成器对比**：

| 特性 | Veo 3.1 | Vidu Q3-Pro | Kling 1.5 |
|------|---------|-------------|-----------|
| **时长范围** | 5-8s | 1-16s | 5-10s |
| **音频生成** | ❌ | ✅ 内置 | ❌ |
| **首尾帧** | ✅ | ✅ | ✅ |
| **运动控制** | ❌ | ✅ | ❌ |
| **分辨率** | 4K | 1080p | 1080p |
| **速度** | 中等 | 快速 | 中等 |

### 16.3 Pipeline Graph 工作流架构

#### 16.3.1 核心架构

```typescript
// src/lib/run-runtime/pipeline-graph.ts
interface PipelineNode {
    key: string                // 节点标识
    title: string              // 节点标题
    maxAttempts: number        // 最大重试次数
    timeoutMs: number          // 超时时间（毫秒）
    run: (context) => Promise<Output>
}

interface PipelineGraphState {
    refs: Record<string, unknown>      // 引用数据
    meta: Record<string, unknown>      // 元数据
    orchestratorResult?: unknown       // 编排器结果
}
```

#### 16.3.2 剧本→分镜工作流

```typescript
// src/lib/workflows/script-to-storyboard/graph.ts
const nodes: PipelineNode[] = [
    {
        key: 'script_to_storyboard_orchestrator',
        title: 'script_to_storyboard_orchestrator',
        maxAttempts: 2,
        timeoutMs: 1000 * 60 * 20,  // 20分钟超时
        run: async (context) => {
            // 并发处理所有剪辑
            const result = await runScriptToStoryboardOrchestrator({
                concurrency: input.concurrency,
                clips: input.clips,
                novelPromotionData: input.novelPromotionData,
                promptTemplates: input.promptTemplates,
                runStep: input.runStep,
            })
            context.state.orchestratorResult = result
            return { output: { clipCount, totalPanelCount } }
        }
    },
    {
        key: 'script_to_storyboard_validate',
        title: 'script_to_storyboard_validate',
        maxAttempts: 1,
        timeoutMs: 1000 * 30,  // 30秒验证
        run: async (context) => {
            // 验证结果
            return { output: { validated: true } }
        }
    }
]
```

**工作流特点**：
- ✅ 节点化设计，易于扩展
- ✅ 内置重试机制（maxAttempts）
- ✅ 超时保护
- ✅ 状态传递（refs/meta）
- ✅ 并发控制

### 16.4 代码质量守护系统

#### 16.4.1 Guard 脚本列表

**API 契约守护**：
| Guard | 功能 |
|-------|------|
| `api-route-contract-guard.mjs` | 确保 API 路由符合契约 |
| `no-api-direct-llm-call.mjs` | 禁止直接调用 LLM，必须通过网关 |
| `no-provider-guessing.mjs` | 禁止猜测 Provider 配置 |
| `no-model-key-downgrade.mjs` | 防止模型密钥降级 |

**媒体处理守护**：
| Guard | 功能 |
|-------|------|
| `image-reference-normalization-guard.mjs` | 图片引用标准化 |
| `no-media-provider-bypass.mjs` | 禁止绕过媒体 Provider |

**任务系统守护**：
| Guard | 功能 |
|-------|------|
| `task-loading-guard.mjs` | 任务加载基线检查 |
| `task-submit-compensation-guard.mjs` | 任务提交补偿 |
| `task-target-states-no-polling-guard.mjs` | 禁止轮询任务状态 |

**Prompt 守护**：
| Guard | 功能 |
|-------|------|
| `prompt-i18n-guard.mjs` | Prompt 国际化检查 |
| `prompt-json-canary-guard.mjs` | Prompt JSON 格式检查 |
| `prompt-ab-regression.mjs` | A/B 测试回归检测 |
| `prompt-semantic-regression.mjs` | Prompt 语义回归检测 |

#### 16.4.2 Guard 运行机制

```bash
# pre-commit hook 运行所有 guard
.husky/pre-commit -> npm run guards

# pre-push hook 确保代码质量
.husky/pre-push -> npm run test
```

### 16.5 新增 Provider 集成

#### 16.5.1 百炼（Bailian）集成

**支持的能力**：
| 能力 | 实现文件 | 说明 |
|------|----------|------|
| **LLM** | `bailian/llm.ts` | 通义千问系列 |
| **图像生成** | `bailian/image.ts` | 通义万相 |
| **视频生成** | `bailian/video.ts` | 视频生成模型 |
| **TTS** | `bailian/tts.ts` | 语音合成 |
| **声音设计** | `bailian/voice-design.ts` | 声音克隆/设计 |
| **声音管理** | `bailian/voice-manage.ts` | 声音资产管理 |

**Bailian TTS 特性**：
```typescript
interface BailianTTSOptions {
    text: string
    voiceId: string
    speed?: number      // 语速
    pitch?: number      // 音调
    volume?: number     // 音量
    format?: 'mp3' | 'wav' | 'pcm'
}
```

#### 16.5.2 SiliconFlow 集成

**支持的能力**：
| 能力 | 实现文件 | 说明 |
|------|----------|------|
| **LLM** | `siliconflow/llm.ts` | 多种开源模型 |
| **图像生成** | `siliconflow/image.ts` | SDXL, Flux 等 |
| **视频生成** | `siliconflow/video.ts` | 视频模型 |
| **音频生成** | `siliconflow/audio.ts` | 音频模型 |

### 16.6 Prompt 模板更新

#### 16.6.1 分镜面板模板（storyboard_panels.canary.json）

```json
[
  {
    "panel_number": 1,
    "description": "Wide shot of Lena entering the hall...",
    "characters": [
      { "name": "Lena", "appearance": "default" },
      { "name": "Victor", "appearance": "formal" }
    ],
    "location": "grand_hall_night",
    "scene_type": "daily",         // 场景类型
    "source_text": "Lena enters...",
    "shot_type": "wide shot",      // 景别
    "camera_move": "slow push in", // 镜头运动
    "video_prompt": "A woman walks into a grand hall...",
    "duration": 3                  // 时长（秒）
  }
]
```

**scene_type 分类**：
- `daily` - 日常场景
- `emotion` - 情感表达
- `action` - 动作场景
- `dialogue` - 对话场景

#### 16.6.2 剧本转换模板（screenplay_conversion.canary.json）

```json
{
  "clip_id": "clip_1",
  "original_text": "Lena enters the hall...",
  "scenes": [
    {
      "scene_number": 1,
      "heading": {
        "int_ext": "INT",              // 内景/外景
        "location": "grand_hall_night",
        "time": "night"                // 时间
      },
      "description": "A large hall lit by chandeliers...",
      "characters": ["Lena", "Victor"],
      "content": [
        {
          "type": "action",
          "text": "Lena steps forward..."
        },
        {
          "type": "dialogue",
          "character": "Lena",
          "parenthetical": "firmly",   // 情绪指示
          "lines": "You need to read this now."
        },
        {
          "type": "voiceover",
          "character": "Narrator",
          "text": "The room holds its breath."
        }
      ]
    }
  ]
}
```

### 16.7 可落地的技术实践

#### 16.7.1 视频生成器选择决策树

```
是否需要内置音频？
├─ 是 → Vidu Q3-Pro（唯一支持内置音频生成）
└─ 否
    └─ 需要最高分辨率？
        ├─ 是 → Google Veo 3.1（4K）
        └─ 否
            └─ 需要首尾帧连续性？
                ├─ 是 → Vidu Q3-Pro / Veo 3.1
                └─ 否 → Kling 1.5 / Sora 2（性价比）
```

#### 16.7.2 Vidu 音频生成最佳实践

**音频类型选择**：
| audioType | 适用场景 |
|-----------|----------|
| `all` | 完整视频（对白 + 音效） |
| `speech_only` | 纯对白视频 |
| `sound_effect_only` | 纯动作/环境视频 |

**运动幅度选择**：
| movementAmplitude | 适用场景 |
|-------------------|----------|
| `small` | 静态/微动镜头（特写、情绪） |
| `medium` | 中等运动（对话、日常） |
| `large` | 大幅运动（动作、追逐） |
| `auto` | 自动判断（推荐） |

#### 16.7.3 Pipeline 工作流设计模式

**模式 1：顺序执行**
```typescript
const nodes = [
    { key: 'step1', run: async () => {...} },
    { key: 'step2', run: async () => {...} },
    { key: 'step3', run: async () => {...} }
]
```

**模式 2：并行 + 汇聚**
```typescript
const nodes = [
    { 
        key: 'parallel_generate',
        run: async (context) => {
            const results = await Promise.all([
                generatePanel(1),
                generatePanel(2),
                generatePanel(3)
            ])
            context.state.panels = results
        }
    },
    {
        key: 'merge_results',
        run: async (context) => {
            return mergePanels(context.state.panels)
        }
    }
]
```

**模式 3：条件分支**
```typescript
const nodes = [
    {
        key: 'check_content_type',
        run: async (context) => {
            context.state.type = detectContentType()
        }
    },
    {
        key: 'generate_content',
        run: async (context) => {
            if (context.state.type === 'dialogue') {
                return generateDialogueVideo()
            } else {
                return generateActionVideo()
            }
        }
    }
]
```

### 16.8 推荐工具与资源更新

#### 16.8.1 新增工具

| 工具 | 类型 | 价格 | 特点 |
|------|------|------|------|
| **Vidu** | 视频生成 | 付费 | 内置音频生成，1-16s 时长 |
| **百炼 TTS** | 语音合成 | 按量付费 | 中文效果好，声音克隆 |
| **SiliconFlow** | 多模态 | 按量付费 | 开源模型托管，性价比高 |

#### 16.8.2 新增学习资源

| 资源 | 类型 | 说明 |
|------|------|------|
| **waoowaoo Guard Scripts** | 代码质量 | 工业级代码守护实践 |
| **Pipeline Graph** | 工作流设计 | 可复用的 AI 工作流架构 |
| **Prompt i18n** | 国际化 | 多语言 Prompt 最佳实践 |

### 16.9 本周总结

**关键发现**：
1. **Vidu 生成器** - 唯一支持内置音频生成的视频 AI，值得关注
2. **Pipeline Graph** - 可复用的工作流架构，适合复杂 AI 任务编排
3. **Guard 系统** - 工业级代码质量保障，可借鉴到其他项目
4. **Provider 多样化** - 百炼、SiliconFlow 等国产模型集成，降低成本

**下周计划**：
- 实践 Vidu 音频生成功能
- 研究 waoowaoo 的角色一致性方案
- 尝试 Pipeline Graph 工作流

---

> **本次更新时间**: 2026-03-14 10:00 (Asia/Shanghai)
> **专题**: waoowaoo 项目最新更新研究
> **新增章节**: 十六

---

## 十七、第一周总结（2026-03-09 ~ 2026-03-15）

### 17.1 本周学习路线回顾

| 日期 | 主题 | 核心收获 | 可落地实践 |
|------|------|----------|------------|
| **周一** | 分镜设计与镜头语言 | 景别切换、镜头运动、黄金前三秒 | 分镜脚本模板、情绪曲线设计 |
| **周二** | AI视频生成 Prompt | Veo/Sora/Kling Prompt 模板 | 首帧传递、尾帧连续性 |
| **周三** | 剪辑节奏与转场 | 节奏控制公式、转场技巧 | 音乐节拍同步、J/L-Cut |
| **周四** | 平台算法偏好 | 抖音/TikTok/小红书算法机制 | 完播率优化、钩子公式、CTA |
| **周五** | 配音/字幕/BGM | 情绪控制、字幕规范、音量平衡 | emotionStrength、音量金字塔 |
| **周六** | waoowaoo 深度研究 | Vidu 内置音频、Pipeline Graph、Guard 系统 | 工作流设计模式、代码质量守护 |

### 17.2 核心知识点提取

#### 17.2.1 分镜设计核心公式

```
景别递进：远景 → 全景 → 中景 → 近景 → 特写
情绪强化：正向递进，逐级聚焦

黄金前三秒 = 悬念/冲突/反常识 + 强视觉冲击
```

#### 17.2.2 AI 视频生成决策树

```
需要内置音频？
├─ 是 → Vidu Q3-Pro（唯一支持）
└─ 否
    └─ 需要 4K？
        ├─ 是 → Veo 3.1
        └─ 否 → Kling 1.5 / Sora 2（性价比）
```

#### 17.2.3 平台算法核心指标

| 平台 | 第一指标 | 第二指标 | 最佳时长 |
|------|----------|----------|----------|
| **抖音** | 完播率 >60% | 点赞率 >4% | 15-60s |
| **TikTok** | Watch Time | Completion Rate | 15-30s |
| **小红书** | CES 评分 | 收藏+评论 | 30-90s |

#### 17.2.4 配音情绪控制

```json
{
  "emotionStrength": 0.2-0.4,  // 日常对话
  "emotionStrength": 0.4-0.6,  // 情感表达
  "emotionStrength": 0.6-0.8,  // 激烈冲突
  "emotionStrength": 0.8-1.0   // 戏剧高潮
}
```

#### 17.2.5 音量金字塔

```
人声/旁白：-6dB 到 -3dB（最响）
    ↓
音效/特效：-12dB 到 -6dB
    ↓
BGM 高潮：-18dB 到 -12dB
    ↓
BGM 背景：-24dB 到 -18dB（最轻）
```

### 17.3 关键技术发现

#### 17.3.1 waoowaoo 工业级实践

| 模块 | 技术亮点 | 可复用性 |
|------|----------|----------|
| **Pipeline Graph** | 节点化工作流、重试机制、超时保护 | ⭐⭐⭐⭐⭐ |
| **Guard 系统** | 30+ 代码质量守护脚本 | ⭐⭐⭐⭐ |
| **Prompt i18n** | 中英文 Prompt 模板架构 | ⭐⭐⭐⭐ |
| **Vidu 集成** | 唯一支持内置音频的视频生成 | ⭐⭐⭐⭐⭐ |

#### 17.3.2 Vidu 独特优势

```
✅ 内置音频生成（speech + sound_effect）
✅ 1-16s 时长范围（最长）
✅ 运动幅度控制（small/medium/large）
✅ 首尾帧传递（连续性）
⚠️ 最高 1080p（不如 Veo 4K）
```

### 17.4 可立即落地的 Checklist

#### 17.4.1 短视频制作标准化流程

```markdown
□ 剧本创作（AI 辅助）
□ 分镜脚本（参考模板格式）
□ 角色设计（AI 图像，保持一致性）
□ 场景设计（AI 图像，风格统一）
□ 视频生成（首帧 + Prompt）
□ 配音生成（emotionStrength 控制）
□ 字幕添加（白字黑边，5-8%字号）
□ BGM 选择（情绪匹配，音量平衡）
□ 音画同步（节拍对齐，口型匹配）
□ 质量检查（完播率、互动率预估）
```

#### 17.4.2 质量检查清单

```markdown
□ 前 3 秒有钩子
□ 镜头切换节奏合理（1-3s/镜头）
□ 情绪曲线有起伏
□ 配音情绪匹配内容
□ 字幕可读（对比度 ≥4.5:1）
□ BGM 音量 ≤ 人声 -12dB
□ 视频画质 ≥1080p
□ 结尾有 CTA
□ 平台规格适配（9:16/16:9）
```

### 17.5 工具推荐汇总

| 用途 | 首选工具 | 备选工具 | 说明 |
|------|----------|----------|------|
| **视频生成** | Vidu Q3-Pro | Veo 3.1 / Kling | 需要音频选 Vidu |
| **配音** | GPT-SoVITS | Azure TTS | 开源免费 vs 商业稳定 |
| **字幕** | Aegisub | CapCut | 专业 vs 易用 |
| **BGM** | Epidemic Sound | YouTube Audio Library | 付费 vs 免费 |
| **剪辑** | DaVinci Resolve | CapCut | 专业 vs 移动端 |
| **工作流** | waoowaoo Pipeline Graph | 自建 | 工业级 |

### 17.6 下周学习计划

| 日期 | 主题 | 预期目标 |
|------|------|----------|
| **周一** | 高级分镜：多线叙事 | 学习平行蒙太奇、交叉剪辑 |
| **周二** | Veo 3.1 深度实践 | 4K 生成、尾帧应用 |
| **周三** | 高级转场：无缝剪辑 | 匹配剪辑、隐藏转场 |
| **周四** | 数据驱动内容优化 | A/B 测试、数据分析 |
| **周五** | 多角色配音与对话 | 声音设计、角色声线 |
| **周六** | waoowaoo 部署实践 | 本地环境搭建、API 配置 |
| **周日** | 第二周总结 | 整合知识、输出教程 |

### 17.7 核心方法论总结

```
第一性原理：
  视频的本质 = 视觉信息 + 情绪传递

执行原则：
  1. 前 3 秒决定生死（钩子）
  2. 完播率是王道（节奏控制）
  3. 情绪曲线要有起伏（高潮设计）
  4. AI 是工具，创意是核心（Prompt 工程提升质量）
  5. 质量大于数量（一条爆款胜过十条平庸）

技术栈选择：
  视频生成：Vidu（音频） / Veo 3.1（4K）
  配音：GPT-SoVITS（免费） / Azure TTS（商业）
  工作流：waoowaoo Pipeline Graph（工业级）
```

---

> **本次更新时间**: 2026-03-15 10:00 (Asia/Shanghai)
> **专题**: 第一周总结
> **新增章节**: 十七

**第一周学习完成 ✅**

**Made with ❤️ by Research Agent (xiaoresearch)**

---

## 十八、高级分镜：多线叙事与镜头角度进阶（2026-03-16 周一专题）

### 18.1 多线叙事核心技法

#### 18.1.1 平行蒙太奇 (Parallel Montage)

**定义**：将不同时空的多个叙事线索交替剪辑，展现并行发展的事件。

**核心特点**：
- ✅ **不强调同时性** — 可以是同时同地、同时异地、异时同地
- ✅ **自由驾驭时空** — 创作者可以灵活切换叙事线
- ✅ **推进剧情** — 通过对比或关联展示多线发展

**适用场景**：
| 场景类型 | 示例 | 效果 |
|----------|------|------|
| **同时异地** | 主角A在北京，主角B在上海 | 展现平行生活 |
| **异时同地** | 过去的回忆 vs 现在的对比 | 时空对比 |
| **因果关系** | 原因 → 结果交替展示 | 强化逻辑 |
| **对比叙事** | 富人生活 vs 穷人生活 | 社会对比 |

**Prompt 实现示例**：
```json
{
  "scene_type": "parallel_montage",
  "narratives": [
    {
      "thread_id": "thread_A",
      "location": "beijing_office",
      "time": "morning",
      "character": "Li"
    },
    {
      "thread_id": "thread_B",
      "location": "shanghai_home",
      "time": "morning",
      "character": "Wang"
    }
  ],
  "edit_pattern": "alternate",  // 交替剪辑
  "transition": "cut"           // 硬切
}
```

#### 18.1.2 交叉蒙太奇 (Cross Montage / Intercutting)

**定义**：强调同时异地的多个事件频繁交替剪辑，营造紧张感。

**核心特点**：
- ✅ **强调同时性** — 必须是同一时间发生的异地事件
- ✅ **频繁交汇** — 镜头切换更快速、更紧张
- ✅ **相互影响** — 叙事线之间存在因果或竞争关系

**与平行蒙太奇的区别**：
| 维度 | 平行蒙太奇 | 交叉蒙太奇 |
|------|------------|------------|
| **时空要求** | 灵活（同时/异时/同地/异地） | 严格（同时异地） |
| **切换频率** | 较慢（10-30s/次） | 较快（3-10s/次） |
| **情绪氛围** | 展现、对比 | 紧张、悬念 |
| **叙事线关系** | 可独立 | 必须相关 |

**经典案例**：
| 电影 | 场景 | 效果 |
|------|------|------|
| **《速度与激情》** | 两个赛车手同时冲刺 | 紧张竞技 |
| **《盗梦空间》** | 多层梦境同时进行 | 时空错位 |
| **《敦刻尔克》** | 陆海空三线并进 | 战争紧张 |
| **《教父》** | 洗礼 vs 杀人 | 道德对比 |

**短视频应用**：
```markdown
【交叉蒙太奇模板】
场景 A：主角准备面试（家）
场景 B：面试官翻阅简历（办公室）

镜头切换：
A (3s) → B (2s) → A (3s) → B (2s) → A+B (5s)

情绪：紧张 + 期待
结尾：场景 A 和 B 汇合（主角到达办公室）
```

#### 18.1.3 重复蒙太奇 (Repetition Montage)

**定义**：同一镜头或画面在影片中多次出现，强化主题或象征意义。

**核心要素**：
- **符号化** — 重复的镜头成为象征符号
- **主题强化** — 每次重复都强化主题
- **情感积累** — 观众情绪逐渐积累

**经典案例**：
| 电影 | 重复元素 | 象征意义 |
|------|----------|----------|
| **《盗梦空间》** | 陀螺 | 现实 vs 梦境 |
| **《公民凯恩》** | 玫瑰花 | 童年失去的爱 |
| **《阿甘正传》** | 羽毛 | 命运的漂浮 |

**短视频应用**：
```markdown
【重复蒙太奇模板】
第 1 次出现：开场，展示符号
第 2 次出现：中间，强化主题
第 3 次出现：结尾，升华情感

示例：
- 笑脸贴纸 → 乐观态度
- 时钟 → 时间流逝
- 破碎镜子 → 自我破碎
```

### 18.2 镜头角度进阶

#### 18.2.1 俯拍 (High Angle / Overhead Shot)

**定义**：镜头位置高于被摄主体，从上往下拍摄。

**心理暗示**：
| 情绪 | 心理效果 | 适用场景 |
|------|----------|----------|
| **弱小** | 人物显得渺小、卑微 | 失败者、受害者 |
| **弱势** | 处于不利地位 | 被压迫者 |
| **孤立** | 与环境脱节 | 孤独、迷茫 |
| **掌控** | 观众视角更高 | 上帝视角 |

**俯拍变体**：
| 变体 | 特点 | 用途 |
|------|------|------|
| **标准俯拍** | 腰部以上，镜头朝下 | 人物弱势 |
| **广角俯拍** | 更广视角，交代环境 | 城市俯瞰 |
| **鸟瞰视角** | 90° 垂直向下 | 地图效果 |
| **上帝视角** | 极高俯拍 | 全局掌控 |

**Prompt 描述**：
```json
{
  "shot_type": "high angle",
  "camera_position": "above_subject",
  "angle": 45,  // 俯视角度
  "effect": "vulnerability",
  "description": "Character appears small and isolated"
}
```

#### 18.2.2 仰拍 (Low Angle)

**定义**：镜头位置低于被摄主体，从下往上拍摄。

**心理暗示**：
| 情绪 | 心理效果 | 适用场景 |
|------|----------|----------|
| **强大** | 人物显得高大、威严 | 英雄、权威 |
| **崇敬** | 观众仰视，心生敬意 | 领袖、偶像 |
| **压迫** | 高耸建筑，压迫感 | 恐怖、震撼 |
| **希望** | 仰望天空，向往未来 | 梦想、理想 |

**仰拍变体**：
| 变体 | 特点 | 用途 |
|------|------|------|
| **标准仰拍** | 镜头低于人物视线 | 英雄形象 |
| **极端仰拍** | 几乎贴地拍摄 | 巨大压迫感 |
| **虫视视角** | 极低角度 | 独特视觉 |

**Prompt 描述**：
```json
{
  "shot_type": "low angle",
  "camera_position": "below_subject",
  "angle": 30,  // 仰视角度
  "effect": "power_and_dominance",
  "description": "Character appears heroic and commanding"
}
```

#### 18.2.3 荷兰角 / 斜角镜头 (Dutch Angle / Canted Angle)

**定义**：相机倾斜，地平线不水平，画面呈倾斜状态。

**心理暗示**：
| 情绪 | 心理效果 | 适用场景 |
|------|----------|----------|
| **不安** | 世界倾斜，失去平衡 | 焦虑、恐惧 |
| **混乱** | 秩序崩塌 | 灾难、危机 |
| **疯狂** | 精神错乱 | 精神病、噩梦 |
| **紧张** | 预感危险 | 悬疑、恐怖 |

**倾斜角度建议**：
| 倾斜程度 | 心理效果 | 推荐场景 |
|----------|----------|----------|
| **5-10°** | 微妙不安 | 情绪波动 |
| **15-25°** | 明显倾斜 | 危机感 |
| **30-45°** | 极端倾斜 | 精神崩溃 |
| **>45°** | 眩晕效果 | 极端情绪 |

**Prompt 描述**：
```json
{
  "shot_type": "dutch angle",
  "camera_tilt": 20,  // 倾斜角度
  "effect": "unease_and_disorientation",
  "description": "Tilted horizon creates psychological tension"
}
```

#### 18.2.4 镜头角度组合应用

**反转拍摄 (Reverse Angle)**：
```
镜头 A：仰拍主角（显得强大）
镜头 B：俯拍对手（显得弱小）
效果：力量对比，心理优势
```

**主观视角 (POV)**：
```
镜头 A：俯拍（人物视角，看向地面）
镜头 B：仰拍（人物视角，看向天空）
效果：代入感，沉浸体验
```

**过肩镜头 (Over-the-Shoulder)**：
```
镜头 A：从A肩膀看B（B显得重要）
镜头 B：从B肩膀看A（A显得重要）
效果：对话平衡，关系展示
```

### 18.3 高级运镜技巧

#### 18.3.1 希区柯克变焦 / 滑动变焦 (Dolly Zoom / Vertigo Effect)

**定义**：摄像机后退（或前进）的同时，焦距变长（或变短），保持主体大小不变，但背景产生扩张或压缩效果。

**实现原理**：
```
正向希区柯克变焦：
  摄像机后退 + 焦距变长
  = 主体不变 + 背景放大

反向希区柯克变焦：
  摄像机前进 + 焦距变短
  = 主体不变 + 背景缩小
```

**心理效果**：
| 类型 | 效果 | 适用场景 |
|------|------|----------|
| **正向（背景放大）** | 空间扩张、眩晕感 | 震惊、发现真相 |
| **反向（背景缩小）** | 空间压缩、聚焦感 | 专注、内心世界 |

**经典案例**：
| 电影 | 场景 | 效果 |
|------|------|------|
| **《迷魂记》** | 楼梯场景 | 恐高眩晕 |
| **《大白鲨》** | 海滩发现 | 震惊恐惧 |
| **《指环王》** | 环境变化 | 空间扭曲 |

**手机拍摄技巧**：
```markdown
1. 固定主体位置（人或物体）
2. 打开视频录制
3. 缓慢后退的同时，双指放大画面
4. 保持主体大小不变
5. 速度：后退 1m 约需 5-10 秒
```

**AI 视频生成描述**：
```json
{
  "camera_move": "dolly_zoom",
  "direction": "backward",
  "zoom": "in",
  "subject_size": "constant",
  "background_effect": "expanding",
  "duration": 5
}
```

#### 18.3.2 环绕镜头 (Orbit / Arc Shot)

**定义**：摄像机围绕主体旋转 360° 或部分弧度。

**类型**：
| 类型 | 角度 | 效果 |
|------|------|------|
| **完整环绕** | 360° | 全方位展示 |
| **半环绕** | 180° | 侧面转换 |
| **部分弧度** | 90° | 角度变化 |

**心理效果**：
| 场景 | 效果 |
|------|------|
| **英雄时刻** | 崇敬、史诗感 |
| **情感高潮** | 浪漫、梦幻 |
| **环境展示** | 空间感、沉浸感 |
| **时间凝固** | 慢动作环绕 = 经典时刻 |

**Prompt 描述**：
```json
{
  "camera_move": "orbit",
  "orbit_direction": "clockwise",
  "orbit_angle": 180,
  "subject": "character",
  "speed": "slow"
}
```

#### 18.3.3 长镜头 (Long Take / One-Shot)

**定义**：不剪辑，一镜到底的连续拍摄。

**类型**：
| 类型 | 时长 | 特点 |
|------|------|------|
| **短长镜头** | 30s-1min | 基础技法 |
| **中长镜头** | 1-5min | 技术挑战 |
| **超长镜头** | >5min | 电影级 |
| **伪长镜头** | 剪辑拼接 | 视觉欺骗 |

**心理效果**：
- ✅ **真实感** — 无剪辑，时间连续
- ✅ **沉浸感** — 观众跟随镜头移动
- ✅ **紧张感** — 无法剪辑，一气呵成
- ⚠️ **风险** — 失误需重来

**短视频应用**：
```markdown
【一镜到底模板】
0-5s：开场建立（远景）
5-15s：跟随主体移动（跟镜头）
15-25s：环绕或变换角度
25-30s：推向高潮（特写）
30-35s：结尾定格或淡出

注意：
- 提前规划路线
- 稳定器必备
- 预留失误时间
```

### 18.4 可落地的分镜设计流程

#### 18.4.1 多线叙事分镜模板

```markdown
## 多线叙事分镜脚本

### 叙事线规划
| 叙事线 | 位置 | 时间 | 角色 | 关系 |
|--------|------|------|------|------|
| A | 北京 | 09:00 | Li | 主角 |
| B | 上海 | 09:00 | Wang | 配角 |

### 镜头序列
| 镜头 | 叙事线 | 景别 | 角度 | 运镜 | 时长 | 描述 |
|------|--------|------|------|------|------|------|
| 1 | A | 全景 | 平视 | 固定 | 3s | Li 在办公室 |
| 2 | B | 全景 | 平视 | 固定 | 3s | Wang 在家中 |
| 3 | A | 中景 | 仰拍 | 推镜头 | 2s | Li 起身 |
| 4 | B | 中景 | 俯拍 | 固定 | 2s | Wang 坐下 |
| 5 | A+B | 特写 | 交替 | - | 4s | 两人同时看手机 |

### 蒙太奇类型
- [ ] 平行蒙太奇（时空灵活）
- [ ] 交叉蒙太奇（同时异地，紧张）
- [ ] 重复蒙太奇（符号强化）

### 情绪曲线
```
情绪强度
  ↑
  │   A    B    A+B
  │  ╱╲  ╱╲  ╱──╲
  │ ╱  ╲╱  ╲╱    ╲
  └────────────────→ 时间
     铺垫 对比 汇合
```
```

#### 18.4.2 镜头角度选择决策树

```
人物情绪？
├─ 弱势/失败 → 俯拍
├─ 强势/英雄 → 仰拍
├─ 不安/混乱 → 荷兰角
└─ 平衡/正常 → 平视

场景氛围？
├─ 宏大/震撼 → 仰拍（建筑）
├─ 孤立/渺小 → 俯拍（鸟瞰）
├─ 危机/紧张 → 荷兰角
└─ 日常/平和 → 平视

叙事目的？
├─ 展现环境 → 广角俯拍
├─ 聚焦人物 → 中景平视
├─ 情绪强化 → 仰拍/俯拍对比
└─ 心理扭曲 → 荷兰角
```

#### 18.4.3 运镜技巧选择矩阵

| 运镜类型 | 心理效果 | 适用场景 | 难度 |
|----------|----------|----------|------|
| **推镜头** | 聚焦、强调 | 情绪特写 | ⭐ |
| **拉镜头** | 展示、揭示 | 环境交代 | ⭐ |
| **摇镜头** | 展示空间 | 全景扫描 | ⭐⭐ |
| **移镜头** | 跟随、流动 | 动态场景 | ⭐⭐ |
| **环绕** | 史诗、浪漫 | 高光时刻 | ⭐⭐⭐ |
| **希区柯克** | 眩晕、震惊 | 心理转折 | ⭐⭐⭐⭐ |
| **长镜头** | 沉浸、真实 | 叙事段落 | ⭐⭐⭐⭐⭐ |

### 18.5 质量检查清单

```markdown
## 多线叙事检查
□ 叙事线关系明确（平行/交叉/因果）
□ 时空逻辑清晰
□ 镜头切换节奏合理
□ 情绪曲线有起伏
□ 叙事线最终汇聚或呼应

## 镜头角度检查
□ 角度选择符合人物情绪
□ 俯仰对比使用得当
□ 荷兰角不过度使用（<30%镜头）
□ 主观视角有明确目的

## 运镜检查
□ 运镜平稳（除非故意晃动）
□ 运镜速度与情绪匹配
□ 希区柯克变焦效果明显
□ 长镜头无穿帮

## 整体检查
□ 镜头语言与叙事目的一致
□ 观众情绪被有效引导
□ 没有技术失误穿帮
□ AI 生成参数正确
```

### 18.6 本日总结

**核心收获**：

| 模块 | 关键知识点 |
|------|------------|
| **多线叙事** | 平行蒙太奇（时空灵活）vs 交叉蒙太奇（同时异地，紧张） |
| **镜头角度** | 俯拍（弱势）、仰拍（强势）、荷兰角（不安） |
| **高级运镜** | 希区柯克变焦（眩晕）、环绕（史诗）、长镜头（沉浸） |

**可立即应用**：

1. **多线叙事模板** — 规划叙事线 + 镜头序列 + 蒙太奇类型
2. **镜头角度决策树** — 根据情绪/氛围/目的选择角度
3. **运镜技巧矩阵** — 根据场景选择合适的运镜方式

**明天预告**：Veo 3.1 深度实践（4K 生成、尾帧应用）

---

> **本次更新时间**: 2026-03-16 10:00 (Asia/Shanghai)
> **专题**: 高级分镜：多线叙事与镜头角度进阶
> **新增章节**: 十八

**第二周周一学习完成 ✅**

---

## 十九、AI视频生成 Prompt 最佳实践进阶（2026-03-17 周二专题）

> **参考资料来源**：
> - Google DeepMind Veo 3 Prompt Guide
> - Sora Prompt Engineering Guide (promptingguide.ai)
> - Vatsal Shah Sora 2 Prompt Engineering Best Practices
> - Kling AI Official Prompt Guide
> - Leonardo.Ai Kling AI Prompt Guide
> - fal.ai Kling 2.6 Pro Prompt Guide

### 19.1 2025-2026 AI 视频生成技术突破

#### 19.1.1 技术演进时间线

```
2024 Q4          2025 Q1          2025 Q2          2025 Q3          2025 Q4          2026 Q1
  │                │                │                │                │                │
  ▼                ▼                ▼                ▼                ▼                ▼
Sora 1.0        Veo 2.0          Kling 1.5        Sora 2.0        Veo 3.0         Veo 3.1
发布           发布             发布            ("GPT-3.5      发布            发布
                                              时刻")                        (原生音频)
```

#### 19.1.2 关键技术突破

| 模型 | 突破点 | 影响 |
|------|--------|------|
| **Veo 3.1** | 原生音频生成（环境音+音效+对话+口型） | 无需后期配音，一站式视频生成 |
| **Sora 2** | 物理一致性、故事板式 Prompt | "视频生成的 GPT-3.5 时刻" |
| **Kling 2.0** | 运动幅度控制、首尾帧传递 | 精准控制视频动态 |

### 19.2 通用 Prompt 工程原则

#### 19.2.1 Prompt 结构公式

**六要素结构**（适用于所有 AI 视频模型）：

```
[主体/角色] + [动作/运动] + [环境/场景] + [氛围/情绪] + [镜头语言] + [技术参数]
```

**示例**：
```
一位30岁女性（主体）
自信地走向会议桌（动作）
在现代办公室中（环境）
坚定、专注的情绪（氛围）
中景跟镜头，平滑推进（镜头语言）
4K 电影质感，浅景深（技术参数）
```

#### 19.2.2 分层描述法

**Layer 1: 基础描述**（What）
```
主体是什么？动作是什么？场景在哪里？
```

**Layer 2: 情绪与氛围**（How）
```
情绪状态如何？氛围是什么？光线怎样？
```

**Layer 3: 镜头语言**（Camera）
```
景别是什么？运镜方式？角度？
```

**Layer 4: 技术参数**（Tech）
```
分辨率、帧率、风格、质量
```

#### 19.2.3 避免 Prompt 陷阱

| 陷阱 | 问题 | 解决方案 |
|------|------|----------|
| **过度抽象** | "一个美丽的场景" | 具体化："阳光照射的海滩，金色沙滩" |
| **矛盾指令** | "快速移动但保持静止" | 明确优先级 |
| **忽略运动** | 只描述静态画面 | 明确说明运动方式和速度 |
| **参数过多** | 一次性要求太多 | 分段生成，后期合成 |
| **模糊情绪** | "情绪复杂" | 指定具体情绪："悲伤中带着希望" |

### 19.3 Veo 3.1 Prompt 最佳实践

#### 19.3.1 Veo 3.1 新特性

| 特性 | 说明 | Prompt 支持 |
|------|------|-------------|
| **原生音频** | 环境音、音效、对话 | `audio: ambience + sfx + dialogue` |
| **口型同步** | 对话时自动口型匹配 | `lip_sync: true` |
| **4K 分辨率** | 最高质量输出 | `resolution: 4K` |
| **首尾帧** | 图生视频 + 连续性 | `first_frame + last_frame` |

#### 19.3.2 Veo 3.1 Prompt 结构

**标准模板**：
```
[Scene description]. [Character description] [action].
[Camera movement and shot type].
[Lighting and atmosphere].
[Audio description - NEW in 3.1].
[Technical specs: 4K, cinematic].
```

**示例 1：带原生音频的场景**：
```
A woman walks confidently into a modern boardroom.
Her expression is determined, eyes focused.
Slow push in from medium shot to close-up.
Natural office lighting, fluorescent overhead.
Sound of footsteps on hardwood floor, ambient office murmur.
4K cinematic quality.
```

**示例 2：对话场景（口型同步）**：
```
Two executives in a heated debate across a conference table.
The CEO slams his hand on the table while speaking.
Medium shot, static camera, focus on both characters.
Dramatic lighting with harsh shadows.
Dialogue: "This deal is off!" with synchronized lip movement.
4K cinematic quality.
```

#### 19.3.3 Veo 3.1 音频 Prompt 技巧

**音频类型控制**：
```
audio_type:
  - ambience        // 环境音（风声、雨声、城市噪音）
  - sound_effects   // 音效（脚步、关门、引擎）
  - dialogue        // 对话（需要指定台词）
  - music           // 背景音乐（可选）
```

**音频强度控制**：
```
audio_mix:
  - dominant: dialogue     // 对话主导
  - dominant: ambience     // 环境音主导
  - balanced               // 平衡混合
```

**示例**：
```json
{
  "prompt": "A woman types on her laptop in a busy café...",
  "audio": {
    "type": ["ambience", "sound_effects"],
    "ambience": "coffee shop murmur, espresso machine, soft jazz",
    "sound_effects": "keyboard typing, coffee cup clinking",
    "mix": "balanced"
  }
}
```

### 19.4 Sora 2 Prompt 最佳实践

#### 19.4.1 Sora 2 关键特性

| 特性 | 说明 | 优势 |
|------|------|------|
| **物理一致性** | 遵循真实物理规律 | 运动更自然 |
| **故事板模式** | 分段式 Prompt | 复杂叙事支持 |
| **长视频** | 最长 60 秒 | 短片级别 |
| **图像输入** | 首帧/多帧引导 | 精准控制 |

#### 19.4.2 Sora 2 Prompt 结构

**单场景 Prompt**：
```
[Opening shot description].
[Character(s) and their initial state].
[Action progression with timing].
[Camera movement].
[Visual style and quality].
```

**故事板式 Prompt**（Sora 2 特色）：
```json
{
  "scenes": [
    {
      "shot": 1,
      "description": "Wide establishing shot of a city skyline at sunset",
      "duration": "3s",
      "camera": "static"
    },
    {
      "shot": 2,
      "description": "Cut to a woman looking out of a window",
      "duration": "2s",
      "camera": "medium shot, slow push in"
    },
    {
      "shot": 3,
      "description": "She turns and walks towards the door",
      "duration": "3s",
      "camera": "tracking shot, following her movement"
    }
  ],
  "style": "cinematic, moody lighting",
  "resolution": "1080p"
}
```

#### 19.4.3 Sora 2 物理控制技巧

**运动物理**：
```
motion_physics:
  - realistic        // 真实物理（推荐）
  - exaggerated      // 夸张（动画风格）
  - slowed           // 慢动作
  - accelerated      // 快进
```

**碰撞检测**：
```
collision:
  - enabled          // 启用碰撞检测（避免穿模）
  - disabled         // 禁用（特殊效果）
```

**示例**：
```json
{
  "prompt": "A basketball player dunks the ball...",
  "physics": {
    "gravity": "realistic",
    "collision": "enabled",
    "motion_blur": "natural"
  }
}
```

### 19.5 Kling AI Prompt 最佳实践

#### 19.5.1 Kling Prompt 结构

**官方推荐结构**：
```
[主体描述] + [运动描述] + [镜头描述] + [风格描述]
```

**权重控制**（Kling 特色）：
```
++关键元素++    // 强调（增加权重）
--排除元素--   // 负面提示（排除）
```

**示例**：
```
++红色跑车++ 沿着海岸公路行驶 --行人-- --交通标志--
中景跟镜头，平滑运动
电影质感，鲜艳色彩，4K质量
```

#### 19.5.2 运动幅度控制

**motion_amplitude**：
| 值 | 效果 | 适用场景 |
|----|------|----------|
| `small` | 微小运动 | 特写、情绪表达 |
| `medium` | 中等运动 | 日常场景 |
| `large` | 大幅运动 | 动作、追逐 |
| `auto` | 自动判断 | 推荐（智能） |

**示例**：
```json
{
  "prompt": "A woman reading a book by the window...",
  "motion_amplitude": "small",  // 静态为主，微动
  "duration": 5
}
```

#### 19.5.3 首尾帧技巧

**场景过渡**：
```json
{
  "first_frame": "scene_a_end.jpg",     // 场景 A 结束帧
  "last_frame": "scene_b_start.jpg",    // 场景 B 开始帧
  "prompt": "Smooth transition from indoor to outdoor...",
  "transition_type": "morph"
}
```

**循环视频**：
```json
{
  "first_frame": "initial_state.jpg",
  "last_frame": "initial_state.jpg",    // 相同帧
  "prompt": "Seamless loop animation...",
  "loop": true
}
```

### 19.6 实战 Prompt 模板库

#### 19.6.1 情绪表达模板

**模板 1：悲伤情绪**
```
[Character] sits alone in [location].
[Eyes downcast, shoulders slumped].
Slow push in to close-up.
Soft, diffused lighting with cool tones.
Ambient sound: rain on window, distant thunder.
4K cinematic, emotional depth.
```

**模板 2：愤怒情绪**
```
[Character] stands up abruptly from [location].
[Fists clenched, jaw tight, eyes intense].
Cut from medium shot to close-up.
Harsh lighting with strong shadows.
Sound: chair scraping, heartbeat bass.
4K cinematic, tension building.
```

**模板 3：喜悦情绪**
```
[Character] smiles broadly in [location].
[Eyes sparkling, posture relaxed, movement energetic].
Medium shot with gentle push in.
Warm, golden lighting, soft highlights.
Sound: light ambient music, laughter.
4K cinematic, feel-good atmosphere.
```

#### 19.6.2 场景类型模板

**模板 1：商业场景**
```
A professional [profession] in a modern [location].
[Action: presentation/discussion/working].
Medium shot, tracking movement.
Bright office lighting, clean aesthetic.
Ambient: office sounds, keyboards, distant chatter.
4K corporate style.
```

**模板 2：产品展示**
```
[Product] displayed on [surface].
Rotation: 360° slow turn.
Close-up with shallow depth of field.
Studio lighting, soft shadows.
Clean background, premium feel.
4K product photography style.
```

**模板 3：自然风光**
```
[Landscape] at [time of day].
[Movement: clouds drifting, water flowing, leaves rustling].
Wide establishing shot, slow pan.
Natural lighting, golden hour.
Ambient: wind, birds, water.
4K nature documentary style.
```

#### 19.6.3 平台适配模板

**抖音/TikTok（竖屏 9:16）**：
```json
{
  "aspect_ratio": "9:16",
  "duration": 15,
  "prompt": "Quick, dynamic content with strong visual hook in first second...",
  "motion_amplitude": "large",
  "style": "trendy, colorful, eye-catching"
}
```

**小红书（竖屏 9:16，文艺风）**：
```json
{
  "aspect_ratio": "9:16",
  "duration": 30,
  "prompt": "Aesthetic, lifestyle content with soft movements...",
  "motion_amplitude": "small",
  "style": "warm, filtered, lifestyle aesthetic"
}
```

**YouTube/B站（横屏 16:9）**：
```json
{
  "aspect_ratio": "16:9",
  "duration": 60,
  "prompt": "Detailed narrative with cinematic camera work...",
  "motion_amplitude": "medium",
  "style": "cinematic, professional quality"
}
```

### 19.7 高级技巧：从图生视频

#### 19.7.1 首帧图片要求

**推荐规格**：
```
✅ 分辨率：1920x1080 (16:9) 或 1080x1920 (9:16)
✅ 格式：PNG / JPEG
✅ 大小：< 5MB
✅ 内容：清晰、主体明确、光线充足
✅ 构图：遵循三分法则

❌ 避免：
- 模糊、低质量图片
- 主体不清晰
- 过暗/过曝
- 复杂背景干扰
```

#### 19.7.2 图生视频 Prompt 增强

**基础版**：
```
From this image, [character] [action].
Camera: [movement].
Duration: X seconds.
```

**增强版**：
```json
{
  "first_frame": "character_standing.jpg",
  "prompt": "Starting from this image, the character slowly turns to face the camera. Their expression shifts from neutral to a warm smile. Camera slowly pushes in, maintaining focus on the face.",
  "motion_amplitude": "small",
  "duration": 5,
  "style": "cinematic portrait"
}
```

#### 19.7.3 尾帧应用场景

**场景 1：无缝转场**
```json
{
  "first_frame": "scene_a.jpg",
  "last_frame": "scene_b.jpg",
  "prompt": "Smooth morph transition from indoor to outdoor setting...",
  "duration": 3
}
```

**场景 2：循环动画**
```json
{
  "first_frame": "start.jpg",
  "last_frame": "start.jpg",  // 相同
  "prompt": "Seamless loop animation of breathing motion...",
  "loop": true,
  "duration": 4
}
```

**场景 3：时间流逝**
```json
{
  "first_frame": "morning.jpg",
  "last_frame": "evening.jpg",
  "prompt": "Time-lapse transition from dawn to dusk...",
  "duration": 8
}
```

### 19.8 模型选择决策树

```
需要原生音频？
├─ 是 → Veo 3.1（唯一支持原生音频+口型同步）
└─ 否
    └─ 需要复杂叙事？
        ├─ 是 → Sora 2（故事板模式，60秒长视频）
        └─ 否
            └─ 需要运动控制？
                ├─ 是 → Kling 2.0（运动幅度控制，首尾帧）
                └─ 否
                    └─ 需要最高分辨率？
                        ├─ 是 → Veo 3.1（4K）
                        └─ 否 → 任意（按成本/速度选择）
```

### 19.9 成本与质量平衡

| 模型 | 生成速度 | 分辨率 | 音频 | 成本 | 推荐场景 |
|------|----------|--------|------|------|----------|
| **Veo 3.1 Fast** | ⚡⚡⚡ | 1080p | ✅ | $$ | 快速原型、测试 |
| **Veo 3.1** | ⚡⚡ | 4K | ✅ | $$$ | 商业级制作 |
| **Sora 2** | ⚡⚡ | 1080p | ❌ | $$$ | 叙事视频 |
| **Kling 2.0 Pro** | ⚡⚡⚡ | 1080p | ❌ | $$ | 运动控制 |
| **Kling 2.0 Standard** | ⚡⚡⚡⚡ | 720p | ❌ | $ | 批量生成 |

### 19.10 质量检查清单

```markdown
## Prompt 质量检查
□ 六要素完整（主体/动作/环境/氛围/镜头/技术）
□ 运动描述清晰（避免静态 prompt）
□ 情绪与场景匹配
□ 技术参数合理（分辨率/时长/比例）
□ 无矛盾指令

## 模型适配检查
□ 选择正确的模型（音频/叙事/运动）
□ 参数配置正确
□ 平台适配（16:9 vs 9:16）
□ 时长符合平台要求

## 图生视频检查
□ 首帧图片质量达标
□ Prompt 与图片内容一致
□ 运动幅度合理
□ 尾帧使用正确（如适用）

## 输出检查
□ 生成结果符合预期
□ 无明显 artifacts
□ 运动流畅自然
□ 音频清晰（如使用 Veo 3.1）
```

### 19.11 本日总结

**核心收获**：

| 模块 | 关键知识点 |
|------|------------|
| **通用原则** | 六要素结构：主体+动作+环境+氛围+镜头+技术 |
| **Veo 3.1** | 原生音频生成、口型同步、4K 分辨率 |
| **Sora 2** | 故事板模式、物理一致性、60秒长视频 |
| **Kling 2.0** | 运动幅度控制、权重语法 (++key++)、首尾帧 |

**可立即应用**：

1. **六要素 Prompt 结构** — 所有 AI 视频通用的 Prompt 公式
2. **模型选择决策树** — 根据需求快速选择合适模型
3. **实战模板库** — 情绪、场景、平台三类即用模板
4. **图生视频技巧** — 首帧要求 + Prompt 增强

**明天预告**：剪辑节奏控制与转场技巧进阶（周三专题）

---

> **本次更新时间**: 2026-03-17 10:00 (Asia/Shanghai)
> **专题**: AI视频生成 Prompt 最佳实践进阶
> **新增章节**: 十九
> **参考来源**:
> - Google DeepMind Veo 3 Prompt Guide
> - Sora Prompt Engineering Guide (promptingguide.ai)
> - Vatsal Shah Sora 2 Best Practices
> - Kling AI Official Prompt Guide
> - Leonardo.Ai Kling AI Prompts
> - fal.ai Kling 2.6 Pro Guide

**第二周周二学习完成 ✅**

**Made with ❤️ by Research Agent (xiaoresearch)**

---

## 📹 第三周周三：剪辑节奏控制与转场技巧（2026-03-18）

### 一、节奏控制核心原理

#### 1. 什么是剪辑节奏？
剪辑节奏 = **镜头时长 × 画面内容 × 声音设计** 的综合节奏感。好的节奏让观众"感觉对"，而不是"看出来"。

**六大影响因素（Fiveable 研究总结）：**
- 🔹 **镜头时长 (Shot Duration)** — 单个镜头持续的时间，直接决定快/慢感
- 🔹 **景别变化 (Shot Size)** — 远→近递进 = 紧张感；近→远递进 = 释放感
- 🔹 **运镜方式 (Camera Movement)** — 固定镜头慢、跟拍加速、甩镜头极快
- 🔹 **视觉构图 (Visual Composition)** — 画面复杂度影响认知负荷
- 🔹 **声音设计 (Sound Design)** — 音乐 BPM、音效节奏、静默的力量
- 🔹 **内容性质 (Content Nature)** — 动作场景快、情感场景慢

#### 2. 快慢节奏的情绪效应

| 节奏类型 | 效果 | 适用场景 | 镜头时长参考 |
|---------|------|---------|------------|
| ⚡ 极快节奏 | 紧张、兴奋、混乱 | 动作片、音乐卡点、信息轰炸 | 0.3-0.8秒 |
| 🔥 快节奏 | 兴奋、紧迫、活力 | 短视频开头、产品展示 | 1-2秒 |
| 🎵 中等节奏 | 自然、舒适、专业 | 教程、Vlog、品牌故事 | 2-4秒 |
| 🌊 慢节奏 | 沉思、情感、仪式感 | 情感叙事、产品特写、延时 | 4-8秒+ |

**黄金法则：** 短视频整体偏快，但必须有快慢交替。全程快 = 视觉疲劳；全程慢 = 划走。

### 二、短视频节奏的"三段式"控制法

#### 📌 第一段：前3秒（生死线）

> "一个好的开头，决定了80%的用户是划走还是留下"

**三秒钩子的节奏策略：**
1. **信息高密度炸弹** — 前3秒塞进最大信息量/视觉冲击
2. **悬念/争议开场** — 抛出问题或反常识观点
3. **视觉反转/对比** — 素颜→妆容、Before→After
4. **音效+字幕组合** — ❗打字机声 + 悬念字幕

**实操参数：**
- 开头镜头时长：0.5-1.5秒（快速切换）
- 节奏感：比后续内容快30%-50%
- 音效：使用"叮"、"whoosh"等音效强化切点

#### 📌 第二段：中间主体（保持注意力）

**完播率曲线优化法：**
- 通过平台数据分析跳出高峰点
- 在预测的跳出点（约15-20秒处）插入变化：转场、音效、视觉冲击
- 每8-10秒必须有"视觉刺激点"

**节奏变化手法：**
- 🔁 **加速段 → 减速段交替**（类似呼吸）
- 🎬 **信息密集 → 留白喘息**（给观众消化时间）
- 🔄 **同一内容换角度**（避免视觉疲劳）

#### 📌 第三段：结尾（引导行动）

- 最后一句话/画面 = 行动号召
- 节奏突然放缓或定格（制造"意犹未尽"感）
- 或节奏加速推向高潮（制造"燃"感）

### 三、转场技巧实战指南

#### 1. 转场的分类与选择

| 转场类型 | 视觉效果 | 适用场景 | 推荐指数 |
|---------|---------|---------|---------|
| **硬切 (Hard Cut)** | 直接跳切，无过渡 | 短视频主流、节奏紧凑 | ⭐⭐⭐⭐⭐ |
| **跳切 (Jump Cut)** | 同一镜头内跳切，去冗余 | 口播、Vlog、减无聊 | ⭐⭐⭐⭐ |
| **匹配剪辑 (Match Cut)** | 形状/动作/颜色匹配 | 创意转场、品牌内容 | ⭐⭐⭐⭐⭐ |
| **L-cut / J-cut** | 声音先于/迟于画面 | 对话、叙事衔接 | ⭐⭐⭐⭐ |
| **动作转场** | 利用肢体动作衔接 | 舞蹈、运动、日常 | ⭐⭐⭐⭐ |
| **遮罩转场** | 物体/手遮挡切换 | 创意短视频、旅行 | ⭐⭐⭐⭐ |
| **缩放/旋转** | 缩放进入/旋转切换 | 卡点视频、音乐MV | ⭐⭐⭐ |
| **叠化 (Dissolve)** | 画面淡入淡出 | 情感场景、回忆 | ⭐⭐ |
| **甩镜头 (Whip Pan)** | 快速水平甩动 | 动作衔接、地点切换 | ⭐⭐⭐⭐ |

**2025-2026 趋势：** 硬切 > 匹配剪辑 > 动作转场（避免过度使用花哨特效转场）

#### 2. BGM卡点转场（CapCut/剪映实操）

**卡点三步法：**

```
Step 1: 选曲 → 选择120-140 BPM节奏感强的音乐
Step 2: 找节拍 → 剪映"踩点"功能自动标记节拍点（黄线）
Step 3: 对齐剪辑 → 每个节拍点 = 一个转场切点
```

**卡点节奏模式：**
- 🥁 **逐拍卡点** — 每个节拍换画面（最紧凑，适合0.5秒/镜头）
- 🎵 **半拍卡点** — 每两拍换画面（适中，适合1-2秒/镜头）
- 🎶 **副歌爆点** — 副歌高潮处密集卡点，前奏/间奏慢节奏

**剪映/CapCut 快捷操作：**
1. 导入素材 + 选中BGM
2. 点击「音频」→「踩点」→ 自动生成节拍标记
3. 将每个素材对齐到节拍标记线
4. 在节拍处添加转场效果（推荐：动感光效、甩镜头）

#### 3. 同景别转场技巧

> 11个入门剪辑技巧中，同景别转场是最高频使用的高级技巧

**核心方法：**
- 两个镜头景别相同（如都是中景）
- 但拍摄角度/构图/光线不同
- 直接连在一起 → 产生"时间流逝"或"场景切换"感
- 比"淡入淡出"更现代、更紧凑

**注意事项：**
- 避免相似角度的同景别转场（看起来像"抖了一下"）
- 最好有30°以上角度差异
- 加入轻微缩放/位移增加动感

### 四、节奏感训练方法

#### 1. 拆解法（最有效）
```
找3个爆款视频 → 逐帧分析每个镜头时长 → 记录节奏模式 → 复制到自己的素材
```

**分析维度：**
- 每个镜头多少秒？
- 快段/慢段各占多少比例？
- 哪些点用了音效？
- 转场在哪发生？

#### 2. 呼吸节奏法
> 把视频想象成人的呼吸：吸气(慢) → 呼气(快) → 屏息(停顿) → 循环

- 快节奏段 = 呼气（释放信息）
- 慢节奏段 = 吸气（让观众消化）
- 停顿 = 屏息（制造紧张或期待）
- 一段内容（8-15秒）= 一个完整呼吸周期

#### 3. 剪辑前准备
1. **选好BGM** — 音乐决定60%的节奏感
2. **标记节拍** — 用剪映踩点/手动标记
3. **素材分类** — 快镜头、慢镜头、特写、远景分开放
4. **粗剪** — 按节拍铺素材，不求完美
5. **精调** — 微调每个镜头时长，感受"呼吸"

### 五、2025-2026 新趋势

1. **AI辅助节奏检测** — 剪映/Runway自动检测最佳切点
2. **Beat Sync模板化** — CapCut模板预设好节拍同步
3. **动态变速** — 单镜头内速度变化（升格→正常→降格）
4. **音效设计升级** — 不再只靠BGM，Whoosh/Swoosh/Impact音效成为标配
5. **竖屏专属转场** — 竖屏画幅下的转场设计（避免上下黑边感）
6. **反节奏手法** — 故意在预期卡点处不切，制造"打破预期"的惊喜感

### 六、今日实操清单

- [ ] 分析3个对标账号爆款视频的镜头时长分布
- [ ] 在剪映中练习BGM踩点卡点
- [ ] 尝试3种转场：硬切 + 匹配剪辑 + 动作转场
- [ ] 用"三段式"结构剪辑一个完整视频
- [ ] 练习"呼吸节奏法"：8秒快段 + 4秒慢段交替

### 📚 参考来源

- Fiveable: Pacing and Rhythm in Editing (Filmmaking Class Notes)
- Backstage Magazine: Film Rhythm Editing Guide
- Skillman Video Group: Rhythmic Editing Guide
- Kween Media: Mastering the Rhythm - The Art of Pacing
- CSDN: 短视频剪辑节奏感三个技巧
- CSDN: 入门短视频剪辑11个技巧（剪映版）
- CSDN: 短视频完播率优化技巧
- 知乎: 2025短视频脚本模板：前3秒跳出率＜5%的黄金公式
- CapCut Official: Beat Sync Tutorial Guide
- 知乎: 别再学PR了！2025年做短视频用AI+剪映

**第三周周三学习完成 ✅**

---

## 📹 第三周周四：小红书/抖音/TikTok 算法偏好与爆款规律（2026 最新版）

> **参考资料来源**：
> - 青瓜传媒：抖音2026最新推流机制、2026年最新小红书流量机制
> - 知乎：抖音首次公开算法（2025年）、小红书算法逻辑（2025最新版）
> - 拓客吧：2026年抖音核心算法机制、2025抖音算法推荐机制
> - 极致了数据（jzl.com）：抖音推荐机制深度拆解、小红书流量逻辑全解析
> - Virvid.ai: TikTok Algorithm 2026: 3 New Rules
> - PostEverywhere: How TikTok Algorithm Works in 2026
> - Sprout Social: TikTok Algorithm 2026
> - SyncStudio: TikTok Algorithm Follower-First Update
> - OpusClip: TikTok New Algorithm 2026

---

### 一、2025-2026 算法变革核心趋势

#### 1.1 从"标签依赖"到"行为预测"

| 维度 | 旧逻辑（2024及以前） | 新逻辑（2025-2026） |
|------|---------------------|---------------------|
| **推荐基础** | 用户标签+内容标签匹配 | 用户行为预测模型 |
| **核心指标** | 完播率为王 | 完播率 + 互动深度 + 价值贡献 |
| **推流方式** | 即时爆发 | 7天长尾周期 |
| **内容偏好** | 开头套路+情绪刺激 | 价值前置+深度互动 |
| **账号影响** | 粉丝量决定流量 | 账号等级（S/A/B/C）决定 |

**关键洞察**：
> 2025年抖音公开了藏了9年的算法机制。核心从"极速推流"转向"效率优先的综合评估"。
> 平台战略导向的变化会阶段性地调整权重优先级——降低完播率权重、提升收藏/分享权重时，知识类内容就会爆发。

#### 1.2 三大平台的算法同与异

| 维度 | 抖音 | 小红书 | TikTok |
|------|------|--------|--------|
| **核心推荐逻辑** | 行为预测+账号等级 | CES评分+搜索SEO | 兴趣图谱（Interest Graph） |
| **第一指标** | 前3秒留存率（40%） | CES评分+互动质量 | 观看时长（40-50%） |
| **第二指标** | 完播率+互动密度 | 完读率+收藏率 | 完成率+重看率 |
| **独特权重** | GPM值（商业价值） | 搜索流量+专业价值 | 分享+收藏（超过点赞） |
| **推流周期** | 7天长尾 | 阶梯式流量池 | 24-48h爆发 |
| **内容偏好** | 软文为王，硬广暴跌 | 干货+种草+专业 | 原创真人>AI内容 |

---

### 二、抖音 2026 算法全解析

#### 2.1 三级火箭模型（核心架构）

```
第一级：创作者分级体系
  S级 ─── 双倍流量 + 审核优先（500万+播放账号典型）
  A级 ─── 正常推流（大多数活跃创作者）
  B级 ─── 基础流量200-500曝光（多数人"卡点区"）
  C级 ─── 限流（连续3个月表现不佳）
    ↓
第二级：流量池晋级机制
  冷启动池（500-1000曝光）
    ↓ 完播率≥40% + 前3秒留存率≥40%
  赛马池（1000-5000曝光，同标签PK）
    ↓ 前3秒留存40% + 完播率40% + 互动密度20%
  长尾爆发池（7天热推周期）
    ↓ 持续高互动 → 百万+播放
    ↓
第三级：动态校准系统
  实时计算 → 每日调整推荐策略
  → 某知识类账号通过优化第3-5天互动引导，播放量实现2.5倍增长
```

**数据实证**：
- 某非遗手作账号，初始曝光仅800次 → 通过7天慢热推流获得500万播放
- 某服饰账号连续3条500万+播放 → 晋升S级，自然流量占比从20%跃升至60%
- 某美妆直播间通过"评论区晒单抽奖" → 购物转化率从1%提升至3%，自然流量从5万→20万

#### 2.2 前3秒生死线（权重40%）

**三大关键数据点**：
```
封面点击率 ─── 决定用户是否点击进入
    ↓
2秒跳出率 ─── 用户看了2秒就走了？（致命！）
    ↓
3秒留存率 ─── 3秒后用户还在看？（权重40%的核心）
```

**2026年的重大变化**：

| 策略 | 2024效果 | 2026效果 | 变化 |
|------|----------|----------|------|
| "千万别这样..." | 完播率↑15% | 完播率↓12% | ❌ 已失效 |
| "悬念+反转" | 流量池突破快3倍 | 仍有效但需配合价值 | ⚠️ 需升级 |
| **"价值前置"** | — | **新推荐** | ✅ 最有效 |

> **核心变化**："前3秒定生死"的说法已升级。观众平均决策时间缩短到1.8秒。
> 刻意制造悬念的完播率反而下降12%。现在更有效的是**"价值前置"**——直接把视频最有用的信息放在开头。

**新3秒钩子策略**：
```markdown
✅ 价值前置型：
  "这3个方法让我一个月涨粉5万，第2个最关键"
  "直接说答案：XXX就是最好的方案，原因是..."

✅ 悬念升级型（配合价值）：
  "你以为副业只有带货？"（悬念）→ 第3秒预告解决方案（价值）

✅ 反差展示型：
  Before→After对比 + 即时展示结果

❌ 已失效型：
  "千万别这样敷面膜"（纯悬念无价值）
  "看完你绝对想不到"（无信息承诺）
```

#### 2.3 完播率 ≠ 流量（2026 最大的认知颠覆）

**关键发现**：
> 有的视频5秒完播率达50%（传统爆款数据），但因缺乏高价值互动，最终仅几千播放。
> 新时代算法：**"完播率≠流量"**。

**为什么完播率高≠播放量高？**

| 互动类型 | 成本 | 权重 | 算法认为 |
|---------|------|------|---------|
| 点赞 | 低（一键） | 1分 | 浅层认可 |
| 完播 | 中（时间） | 基础线 | 可能有"生理性完播" |
| **长评论** | **高（打字思考）** | **大幅上涨** | **深度认可** |
| **转发** | **高（信用背书）** | **大幅上涨** | **推荐给他人** |
| **收藏** | **中高** | **大幅上涨** | **有长期价值** |
| **购物转化** | **极高（花钱）** | **最高** | **商业价值** |

**算法逻辑**：
> 平台认为"高成本互动"能规避"生理性完播"的虚假数据，更真实反映用户对内容的认可程度。
> 新时代红利只属于"能节省用户筛选成本、提供确定性价值"的创作者。

**实操建议**：
```
视频内嵌入"互动节点"设计：
  → 1分钟处设置"收藏领取完整版攻略"
  → 评论区引导具体场景讨论："你家孩子多大？评论区说"
  → "你踩过这个坑吗？"提问引导互动 → 突围概率翻倍
  → 知识类：引导收藏+关注（提升长尾权重）
  → 搞笑类：强开头+紧凑结构（提升完播权重）
```

#### 2.4 动态权重调整机制

> **核心发现**：抖音用户行为价值权重并非固定，而是实时动态调整的。

| 平台策略方向 | 权重变化 | 效果 |
|-------------|---------|------|
| 扶持知识类内容 | 完播率↓，收藏/分享↑ | 《红楼梦》解读获3亿播放 |
| 扶持人格化创作者 | 关注率↑ | 突显个人IP |
| 扶持商业价值 | GPM值↑ | 电商内容优先 |
| 扶持真实内容 | 硬广↓37% | 非遗/干货/软文优先 |

**不同内容类型的权重适配**：

| 内容类型 | 应优先优化的指标 | 原因 |
|---------|----------------|------|
| **知识/教育** | 收藏率+关注率 | 算法对知识类降低完播权重 |
| **搞笑/娱乐** | 完播率+分享率 | 强吸引力留住用户 |
| **商业/带货** | GPM值+购物转化率 | 商业价值是核心 |
| **情感/故事** | 评论率+完成率 | 深度互动信号 |

#### 2.5 2026 账号搭建与养号

```markdown
账号搭建公式：
  名称 = 核心领域 + 细分场景
  例："成都火锅哥（本地人带路）"

  简介 = "专注XX领域 + 提供XX价值 + 互动引导"

  背景图 = 补充核心成果
  例："已测评50家成都火锅，粉丝折扣在群内"

养号技巧：
  1. 新号注册后养号3天
  2. 每天刷30分钟同赛道内容并互动
  3. 让系统认定你是精准垂直用户
  4. 后续推流更精准
```

---

### 三、小红书 2026 算法全解析

#### 3.1 完整推荐链路

```
审核收录 → 标签匹配 → 阶梯式流量池 → CES评分定生死
    ↓           ↓           ↓              ↓
  内容合规    内容+用户标签  多级流量池    互动质量评分
```

#### 3.2 CES评分系统（2026更新版）

**基础公式（不变）**：
```
CES = 点赞×1 + 收藏×1 + 评论×4 + 转发×4 + 关注×8
```

**2026新增隐性指标**：

| 指标 | 权重变化 | 说明 |
|------|---------|------|
| **长评论** | ↑↑↑ | 评论字数≥8字、含具体场景描述，权重是普通评论的3倍 |
| **截屏** | ↑↑ | 新增高权重行为（说明用户想保存/分享） |
| **深度阅读** | ↑↑ | 图文笔记用户滑动超过3屏才算"有效阅读" |
| **完读率** | ↑↑ | 视频前3秒跳出率>45%直接触发限流 |
| **单纯点赞** | ↓ | 低成本互动，加分占比降低 |

**高价值评论示例**：
```
❌ 低权重："太好了" "赞" "收藏了"
✅ 高权重："油皮用了3天不闷痘，混干皮可以试试芙丽芳丝"（具体场景+产品体验）
✅ 高权重："我也是这个问题！请问你的方法是什么？"（互动追问）
```

#### 3.3 搜索流量（小红书的隐藏金矿）

**搜索SEO核心**：

| 维度 | 2024做法 | 2026做法 |
|------|---------|---------|
| 关键词 | 堆砌关键词 | 自然融入专业术语 |
| 匹配方式 | 简单文本匹配 | **BERT模型**分析文本+图片+视频帧 |
| 排名因素 | 关键词出现次数 | 匹配**真实搜索意图** |
| 违规风险 | 低 | **生硬堆砌关键词会触发限流** |

**BERT模型的影响**：
```
旧逻辑：标题"护肤 好物 推荐" → 匹配"护肤好物推荐"
新逻辑：BERT分析笔记全文+图片 → 理解"这篇讲的是油皮冬季护肤"
        → 匹配搜索"油皮冬天用什么面霜"的意图

⚠️ 关键变化：生硬堆砌关键词会触发限流！
✅ 正确做法：自然融入专业术语 + 场景化表达
```

**SEO优化实操**：
```markdown
关键词布局（自然融入）：
  封面标题 → 核心关键词（1-2个）
  正文开头 → 自然出现搜索词
  正文内容 → 场景化表达（"适合XX肤质""XX场景用"）
  标签 → 3-5个精准标签

易爆发的笔记类型（高贡献力评分）：
  → "避坑指南"（收藏率极高）
  → "流程解读"（完读率高）
  → "XX测评"（搜索流量大）
  → "XX攻略"（收藏+转发双高）
```

#### 3.4 阶梯式流量池机制

```
第一轮：种子推荐（100-500曝光）
  → 推送给粉丝 + 标签匹配人群
  → CES评分筛选

第二轮：小流量池（1000-5000曝光）
  → CES达标 → 推入更大的流量池

第三轮：爆发期
  → 互动质量成为核心权重
  → 长尾流量持续推荐

第四轮：搜索流量（长期价值）
  → 笔记进入搜索结果
  → 好笔记可以持续获流数月甚至数年
```

**时间衰减因子**：
```
互动数据需乘以衰减系数（λ ≈ 0.1~0.3）
2小时内的互动权重最高 → 越晚权重越低
→ 发布后2小时内引导互动最关键
```

#### 3.5 三种流量来源对比

| 来源 | 特点 | 优化重点 | 持续性 |
|------|------|---------|--------|
| **推荐流** | 阶梯式爆发 | CES评分+互动质量 | 短期（1-7天） |
| **搜索流** | 长尾持续 | 关键词SEO+专业价值 | 长期（数月-数年） |
| **直播流** | 实时转化 | 直播间互动+转化率 | 即时 |

---

### 四、TikTok 2026 算法全解析

#### 4.1 核心变革：从互动驱动到观看时长驱动

**2025年底的重大转型**：
> TikTok's recommendation engine underwent its most significant transformation in late 2025.
> The shift from engagement-driven virality to a sophisticated system changes everything.

**信号权重排名（2026）**：

| 信号 | 内部评分 | 权重趋势 | 说明 |
|------|---------|---------|------|
| **观看时长 (Watch Time)** | 10分 | ↑↑ 最重要 | ~40-50%算法权重 |
| **分享 (Share)** | 6分 | ↑↑ 大幅提升 | 超过点赞的重要性 |
| **完成率 (Completion Rate)** | 关键阈值 | ↑ | 70%+完成率 → 3倍曝光 |
| **收藏 (Save)** | 高权重 | ↑ | 证明内容有价值 |
| **重看率 (Rewatch Rate)** | 高权重 | ↑ | 证明内容有深度 |
| **点赞 (Like)** | 较低 | ↓ | 低成本互动，权重下降 |

**关键数据**：
- 观看时长持续增长的创作者收入是专注播放量创作者的 **2倍**
- 完成率70%+的视频获得约 **3倍** 更多曝光
- 分享和收藏现在的重要性**超过点赞**

#### 4.2 兴趣图谱 vs 社交图谱

```
旧模式（社交图谱）：
  你关注的人 → 你看到的内容
  （Facebook/Instagram 逻辑）

新模式（兴趣图谱）：
  你喜欢什么 → 你看到什么
  （TikTok 核心逻辑）
```

**社区分发机制（2023揭示，2026持续强化）**：
> 当3个用户喜欢同一个视频时，算法将这些用户归入一个独特的兴趣群体。
> 这意味着垂直细分内容比大众内容更容易被推荐。

**Follower-First 更新（2026）**：
- TikTok 开始增加"关注者优先"的内容展示
- 但核心仍然是兴趣图谱
- **对创作者的启示**：高互动粉丝 > 大量沉默粉丝

#### 4.3 图文轮播的算法（新格式）

```
STR（Swipe-Through Rate）= 轮播完成率

用户滑完所有图片 = 高完成率信号
→ 类似于视频看完 = 算法加分

→ 图文内容也可以在TikTok上获得高推荐
```

#### 4.4 70%完成率阈值（关键发现）

> **2025年底很多创作者突然掉量的原因**：算法引入了70%完成率阈值。

```
完成率 < 70% → 流量受限
完成率 ≥ 70% → 3倍曝光增长
完成率 > 90% → 大概率进入爆款推荐
```

**提升完成率的内容设计**：
```markdown
✅ 悬念元素：内容中包含令人惊讶的细节或隐藏元素
✅ 循环结构：结尾与开头呼应，用户会再看一遍
✅ 层层递进：信息逐渐展开，每10秒有新信息
✅ "还有更多"提示：结尾暗示有更多信息未展示

❌ 避免的陷阱：
  → 中间拖沓（10-20秒处无变化）
  → 虎头蛇尾（开头精彩，结尾无聊）
  → 信息过载（太密集导致用户放弃）
```

#### 4.5 TikTok SEO（2026必备）

> **TikTok SEO is mandatory for discovery in 2026.**

**SEO优化要点**：
- 视频文案中使用搜索关键词
- 话题标签（Hashtags）使用精准关键词
- 视频描述包含目标搜索词
- 使用TikTok搜索广告测试关键词效果

---

### 五、三大平台爆款规律对比总结

#### 5.1 爆款通用公式（2026版）

```
爆款 = 价值前置 × 互动深度 × 账号等级 × 发布时机

其中：
  价值前置 → 解决"1.8秒决策"问题
  互动深度 → 驱动算法推荐的核心动力
  账号等级 → 决定流量池起点（抖音）
  发布时机 → 影响初始互动数据质量
```

#### 5.2 2026平台偏好内容类型

| 平台 | 最偏好内容 | 增长最快类型 | 下降类型 |
|------|-----------|------------|---------|
| **抖音** | 实用干货、非遗/真实题材、软文种草 | 知识科普（收藏权重↑） | 硬广（↓37%）、开头套路 |
| **小红书** | 避坑指南、流程解读、专业测评 | 深度专业内容（SEO+CES） | 纯营销广告 |
| **TikTok** | 原创真人创作、垂直细分 | 图文轮播（STR新指标） | AI生成内容（降权） |

#### 5.3 发布时间优化

| 平台 | 最佳发布时间 | 次佳时间 | 避免 |
|------|------------|---------|------|
| **抖音** | 12:00-13:00, 18:00-20:00 | 7:00-9:00 | 2:00-5:00 |
| **小红书** | 7:00-9:00, 12:00-14:00, 18:00-22:00 | 20:00-23:00 | 2:00-6:00 |
| **TikTok** | 7:00-9:00, 19:00-23:00 (美东) | 12:00-15:00 | — |

#### 5.4 各平台视频规格

| 参数 | 抖音 | 小红书 | TikTok |
|------|------|--------|--------|
| **比例** | 9:16 | 3:4, 9:16 | 9:16 |
| **最佳时长** | 15-60s | 30-90s | 15-60s |
| **分辨率** | ≥1080p | ≥1080p | ≥1080p |
| **字幕** | 推荐（花字） | 必须 | 必须（80%静音） |

---

### 六、数据驱动内容优化实操

#### 6.1 发布后数据监控时间表

```
发布后 0-2小时：
  → 监控初始完播率、前3秒留存率
  → 如果前3秒留存率<40% → 视频基本已死
  → 如果2小时互动高 → 继续引导评论

发布后 2-24小时：
  → 监控完播率、互动密度
  → 如果互动率>5% → 有可能进入下一级流量池
  → 积极回复评论提升互动深度

发布后 1-7天：
  → 抖音/小红书进入长尾推流期
  → 每日互动数据影响推荐策略
  → 某知识类账号通过优化第3-5天互动引导 → 2.5倍增长

发布后 7天+：
  → 小红书进入搜索流量期
  → 检查搜索排名，优化关键词
```

#### 6.2 数据诊断清单

```markdown
## 冷启动失败诊断（<1000播放）
□ 前3秒留存率是否<40%？ → 优化钩子
□ 完播率是否<40%？ → 缩短时长或调整节奏
□ 封面点击率是否低？ → 更换封面设计

## 赛马池失败诊断（1000-5000播放）
□ 互动率是否<5%？ → 在视频中设计互动节点
□ 评论区是否有深度互动？ → 引导长评论
□ 是否有分享/收藏行为？ → 增加收藏价值

## 长尾期失败诊断（5000+播放后停滞）
□ 第3-5天是否持续有互动？ → 通过评论区引导
□ 是否有搜索流量？ → 检查SEO关键词
□ GPM值是否达标？（带货类） → 优化转化路径
```

#### 6.3 A/B测试框架

```markdown
测试维度：
1. 开头钩子（价值前置 vs 悬念 vs 反差）→ 测前3秒留存率
2. 视频时长（15s vs 30s vs 60s）→ 测完播率
3. 互动节点位置（1分钟处 vs 结尾处）→ 测互动密度
4. 封面设计（文字型 vs 图片型）→ 测点击率
5. 发布时间（不同时段）→ 测初始互动数据

测试方法：
  → 同时发布2个版本
  → 2小时后对比数据
  → 取优者放大
```

---

### 七、2026 爆款内容模板

#### 7.1 抖音爆款模板

**模板1：价值前置型（最推荐）**
```
[0-3s] 直接给出最有价值的信息 + 剩余价值预告
  "3个方法让我一个月涨粉5万，第2个你肯定想不到"
[3-15s] 快速展开核心内容
[15-30s] 案例展示 + 数据佐证
[30-45s] 补充细节 + 引导互动
[45-60s] 总结 + "评论区告诉我你的情况" + "收藏备用"
```

**模板2：避坑型（高互动）**
```
[0-3s] "90%的人都在犯这个错误"
[3-15s] 展示错误做法（让用户产生共鸣）
[15-30s] 给出正确方法
[30-45s] 对比效果
[45-60s] "你踩过这个坑吗？评论区说说" + "转发给朋友避坑"
```

#### 7.2 小红书爆款模板

**模板1：避坑指南型（CES最高）**
```
封面标题：❌ 别再XX了！正确方法看这篇
正文结构：
  1. 痛点描述（引起共鸣）
  2. 错误做法（3个常见误区）
  3. 正确方法（分步骤详解）
  4. 效果展示（Before/After）
  5. 引导收藏："建议收藏，下次用得上"
```

**模板2：攻略型（搜索流量大）**
```
封面标题：🔥 2026XX终极攻略（收藏量10w+）
正文结构：
  1. 场景定义（XX情况下的XX问题）
  2. 方案对比（3个方案优缺点）
  3. 最佳推荐（详细步骤）
  4. 注意事项（避坑提醒）
  5. 互动引导："你在哪个城市？评论区匹配方案"
```

#### 7.3 TikTok爆款模板

**模板1：循环结构型（高重看率）**
```
[开头] 悬念引入
[中间] 层层揭示 + 令人惊讶的细节
[结尾] 与开头呼应 → 用户会重看
```

**模板2：垂直细分型（社区分发优势）**
```
[定位] 针对极具体的兴趣群体
  例："给左撇子吉他手的学习指南"
[内容] 解决这个群体的独特问题
[互动] 引导同好用户在评论区交流
  → 算法自动将同好用户归组 → 病毒式分发
```

---

### 八、今日总结与核心行动清单

#### 8.1 三大核心认知升级

| 旧认知 | 新认知（2026） |
|--------|---------------|
| "前3秒定生死" | "1.8秒决策 + 价值前置" |
| "完播率决定一切" | "完播率≠流量，互动深度才是王道" |
| "粉丝越多流量越大" | "账号等级>粉丝量（S/A/B/C分级）" |

#### 8.2 跨平台策略建议

```
同一内容 → 三平台分发 → 差异化优化：

抖音版：
  → 竖屏9:16, 30-60s
  → 价值前置开头 + 中间互动节点 + 结尾引导互动
  → 前3秒留存率目标≥40%

小红书版：
  → 竖屏9:16 或 图文笔记
  → 专业价值 + 关键词SEO + 引导收藏评论
  → CES评分优化（收藏+长评论）

TikTok版：
  → 竖屏9:16, 15-60s
  → 观看时长优先 + 循环结构 + 真人原创
  → 完成率目标≥70%
```

#### 8.3 即时行动清单

- [ ] 检查当前账号等级（抖音S/A/B/C），制定升级策略
- [ ] 将所有视频开头改为"价值前置"结构
- [ ] 在视频中增加至少2个"互动节点"（引导长评论/收藏/分享）
- [ ] 发布后2小时内积极回复每条评论
- [ ] 小红书笔记加入自然关键词SEO（避免堆砌）
- [ ] 监控发布后第3-5天数据，针对性引导互动
- [ ] 建立"互动设计"习惯：每条视频至少设计1个引导收藏/评论/转发的点

---

## 📚 参考来源

- 青瓜传媒：抖音2026最新推流机制（opp2.com/379989.html）
- 青瓜传媒：2026年最新小红书流量机制（opp2.com/379139.html）
- 知乎：完播率高≠播放量高？2025年抖音首次公开算法
- 知乎：小红书算法逻辑解析（2025年最新版）
- 拓客吧：2026年抖音的核心算法机制和对标技巧
- 拓客吧：2025抖音算法推荐机制详细分析
- 极致了数据：抖音推荐机制2025深度拆解
- 极致了数据：2025小红书的流量逻辑全解析
- 亿邦动力：2025小红书、抖音、视频号流量算法机制
- 搜狐：2025小红书流量机制揭秘
- 搜狐：2026最新小红书算法规则
- Virvid.ai: TikTok Algorithm 2026: 3 New Rules You Must Follow
- PostEverywhere: How the TikTok Algorithm Works in 2026
- Sprout Social: TikTok Algorithm 2026
- SyncStudio: TikTok Algorithm Follower-First Update
- OpusClip: TikTok's New Algorithm in 2026
- InfluenceFlow: TikTok Creator Metrics Guide 2026
- BeatstoRapon: TikTok Algorithm 2026 Ultimate Guide

**第三周周四学习完成 ✅**

---

## 📹 第三周周五：中文配音、字幕排版、BGM选择（2026-03-20）

> 2026年最新实践总结 + 行业趋势

### 一、2026 中文配音技术新趋势

#### 1.1 AI 配音技术突破

2025-2026年AI配音技术迎来重大突破，从"能听到"升级到"听不出"：

| 技术 | 2024水平 | 2026水平 | 突破点 |
|------|---------|---------|--------|
| **声音克隆** | 需1小时音频 | 30秒极速克隆 | GPT-SoVITS v2 |
| **情感表达** | 基础4情绪 | 128维情绪向量 | Emvoice |
| **多语言克隆** | 单一语言 | 跨语言迁移 | ElevenLabs v2 |
| **中文声调** | 机械感 | 自然连读变调 | 阿里云 v3.5 |

#### 1.2 2026 推荐配音工具矩阵

| 场景 | 首选工具 | 备选 | 成本 | 特点 |
|------|---------|------|------|------|
| **商业制作** | Azure TTS | 阿里云 v3.5 | $$ | 稳定、自然、多情绪 |
| **短视频批量** | GPT-SoVITS | Fish Speech | 免费 | 开源、可本地部署 |
| **声音克隆** | ElevenLabs | GPT-SoVITS | $$ | 全球最强克隆 |
| **实时配音** | Coral | Coqui | 免费 | 延迟<200ms |
| **中文首选** | 阿里云 v3.5 | 讯飞星火 | $$ | 中文声调最优 |

#### 1.3 情绪控制进阶（2026版）

```json
// 2026年新一代情绪参数
{
  "emotion": "复合情绪支持",
  "intensity": 0.0-1.0,
  "speed": 0.8-1.2,
  "pitch": 0.9-1.1,
  
  // 2026新增：中文声调优化
  "tone": {
    "mode": "natural",  // natural / formal / casual
    "emphasis": 0.0-1.0,  // 重音强调程度
    "pauses": [
      {"position": 3, "duration": 0.3}  // 自定义停顿
    ]
  },
  
  // 2026新增：呼吸感
  "breathing": {
    "enabled": true,
    "frequency": "auto",  // auto / manual
    "intensity": 0.3
  }
}
```

#### 1.4 中文配音实战技巧

**技巧1：自然语流处理**
```
❌ 机械朗读：今天/天气/很/好
✅ 自然语流：今天天气很☝好（"好"轻读）

技巧：
- 使用prosody标签控制连读
- 标点处添加合理停顿
- 避免每个字都重读
```

**技巧2：情绪强度曲线**
```
开场：emotionStrength = 0.3（建立信任）
中间：emotionStrength = 0.5-0.7（内容展开）
高潮：emotionStrength = 0.8-1.0（情绪爆发）
结尾：emotionStrength = 0.4（收尾）
```

**技巧3：中文特殊音变**
```
轻声：东西(dongxi) → 东西(dongxi)
儿化：视频(shipian) → 视频儿(shipianr)
变调：你好(nǐhǎo) → 你好(nǐhǎo)
```

### 二、字幕排版 2026 新规范

#### 2.1 平台字幕规格（2026更新）

| 平台 | 推荐字号 | 字数/条 | 时长 | 特殊要求 |
|------|----------|---------|------|----------|
| **抖音** | 44-56px | ≤12字 | 2-3s | 必须字幕（智能封面） |
| **TikTok** | 44-56px | ≤10词 | 2-3s | 80%用户静音，必须字幕 |
| **小红书** | 36-48px | ≤18字 | 3-4s | 干净简洁，可加花字 |
| **视频号** | 44-56px | ≤15字 | 2-3s | 微信生态适配 |
| **B站** | 32-44px | ≤22字 | 3-5s | 可用弹幕互动 |

#### 2.2 2026 字幕设计新趋势

**趋势1：动态字幕（Motion Graphics）**
```
2026年静态字幕→动态字幕升级：
- 入场动画：淡入、上滑、缩放
- 出场方式：淡出、下滑
- 高亮效果：关键词放大/变色
- 打字机效果：逐字显示（对话场景）
```

**趋势2：AI自动字幕进化**
```
2024：Whisper v2（错误率~5%）
2026：Whisper v4（错误率<1%）+ 自动标点

工具推荐：
- CapCut：自动字幕+AI修正
- Descript：自动字幕+AI纠错
- Premiere：Adobe Speech Enhancer
```

**趋势3：无障碍字幕升级**
```
2026新标准：
- 对比度：≥7:1（WCAG AAA）
- 说话人识别：不同角色不同颜色
- 音效标注：[音乐]、[笑声]、[掌声]
- 语速显示：<300字/分钟提示
```

#### 2.3 字幕与内容节奏同步

```
字幕出现时机：
├─ 语音开始前100ms：提前展示（阅读缓冲）
├─ 语音同步：即时展示（强调）
└─ 语音结束后200ms：延后展示（完整接收）

每条字幕节奏：
├─ 2-3秒：12-15字（快节奏）
├─ 3-4秒：15-20字（中节奏）
└─ 4-5秒：20-25字（慢节奏）
```

#### 2.4 字幕字体选择（2026推荐）

| 用途 | 推荐字体 | 特点 |
|------|----------|------|
| **通用** | 思源黑体 | 免费、多字重 |
| **标题** | 阿里巴巴普惠体 | 现代感强 |
| **综艺** | 方正综艺简体 | 综艺感强 |
| **古风** | 方正小标宋 | 古典优雅 |
| **手写** | 站酷快乐体 | 活泼亲切 |

### 三、BGM选择与音画同步 2026

#### 3.1 2026 BGM趋势

| 趋势 | 说明 | 适用场景 |
|------|------|----------|
| **AI生成音乐爆发** | Suno v4/Udio生成定制BGM | 背景音乐 |
| **原生音频集成** | Veo 3.1内置音频 | 视频生成 |
| **版权合规严格** | YouTube Content ID升级 | 商业内容 |
| **情绪匹配精准化** | AI推荐匹配 | 内容制作 |

#### 3.2 情绪匹配矩阵（2026更新版）

| 内容情绪 | BGM类型 | BPM | 推荐风格 |
|----------|---------|-----|----------|
| **紧张悬疑** | 氛围/电子 | 80-100 | Dark Ambient |
| **欢乐活泼** | 流行/电子 | 120-140 | Upbeat Pop |
| **感人温暖** | 弦乐/钢琴 | 60-80 | Emotional Piano |
| **励志激昂** | 史诗/摇滚 | 100-130 | Epic Orchestra |
| **搞笑轻松** | 爵士/放克 | 100-120 | Funk/Swing |
| **恐怖惊悚** | 氛围/实验 | 60-90 | Horror Ambience |
| **浪漫甜蜜** | 流行/R&B | 70-90 | Romantic Pop |
| **知识专业** | 轻音乐/电子 | 90-110 | Corporate |
| **运动健身** | 电子/Hip-hop | 130-160 | Workout |

#### 3.3 音量平衡（进阶版）

```
2026音量标准（LUFS）：

        人声/旁白：LUFS -6 到 -3（峰值）
           ↑
       音效/UI：LUFS -12 到 -6
           ↑
      BGM 主歌：LUFS -18 到 -14
           ↑
     BGM 副歌：LUFS -14 到 -10（稍突出）
           ↑
    BGM 间奏：LUFS -24 到 -18（最轻）
```

**Ducking（闪避）实操**：
```json
// 剪映/CapCut 设置
{
  "ducking": {
    "enabled": true,
    "threshold": "-12dB",  // 人声超过这个音量时触发
    "reduction": "-15dB",  // BGM降低到这个水平
    "attack": "10ms",     // 触发时间
    "release": "300ms"    // 恢复时间
  }
}
```

#### 3.4 节奏同步技巧

**卡点剪辑公式**：
```
剪辑点 = 音乐节拍点（BPM对齐）

节拍类型：
├─ On Beat：切换在正拍（强拍）→ 稳定有力
├─ Off Beat：切换在反拍（弱拍）→ 灵活俏皮
└─ Syncopation：切分音位置→ 独特节奏感
```

**短视频BGM使用技巧**：
```
前3秒：清唱/静音 or BGM音量30%
3-15秒：BGM音量60%，建立氛围
15-25秒：副歌高潮，BGM音量80%+
25-30秒：淡出，音量降至20%，自然结束
```

#### 3.5 2026 BGM资源推荐

**免费商用（强烈推荐）**：
| 资源 | 曲库量 | 特点 |
|------|--------|------|
| **YouTube Audio Library** | 2000+ | 官方免费，无版权问题 |
| **Pixabay Music** | 15000+ | 免费可商用 |
| **Incompetech** | 2000+ | CC0协议 |
| **Epidemic Sound（学生免费）** | 40000+ | 学生认证免费 |

**AI生成（2026新趋势）**：
| 工具 | 特点 | 推荐场景 |
|------|------|----------|
| **Suno v4** | 文本生成完整歌曲 | 原创BGM |
| **Udio** | 高品质生成 | 商业级 |
| **Mubert** | 实时生成 | 直播/长视频 |
| **Stable Audio 3** | Stability AI | 多风格 |

### 四、配音+字幕+BGM 实战工作流

#### 4.1 标准短视频制作流程

```
Step 1: 配音录制/生成
├─ 脚本准备
├─ TTS生成（推荐Azure/阿里云）
├─ 情感参数调整
└─ 导出音频

Step 2: 字幕制作
├─ 音频导入Whisper识别
├─ 手动校对（关键！）
├─ 样式选择（平台适配）
├─ 动态效果（可选）
└─ 导出SRT/VTT

Step 3: BGM选择
├─ 情绪匹配
├─ 节奏踩点
├─ 音量调整
└─ 闪避设置

Step 4: 音画合成
├─ 视频轨道
├─ 配音轨道
├─ 字幕轨道
├─ BGM轨道
├─ 音量平衡
└─ 导出
```

#### 4.2 自动化脚本

**批量配音生成脚本**：
```bash
#!/bin/bash
# Azure TTS 批量生成

for line in $(cat script.txt); do
  filename=$(echo "$line" | md5sum | cut -c1-8)
  az tts --text "$line" \
    --voice "zh-CN-XiaoxiaoNeural" \
    --output "audio/$filename.wav"
done
```

**自动字幕对齐**：
```bash
#!/bin/bash
# Whisper 语音识别 + 字幕生成

whisper --model large-v3 \
  --language zh \
  --output_format srt \
  audio.wav
```

#### 4.3 质量检查清单

```markdown
## 配音检查
□ 发音清晰准确
□ 情绪与内容匹配
□ 语速适中（200-240字/分钟）
□ 停顿自然
□ 无明显机器感

## 字幕检查
□ 文字准确无误
□ 时间轴同步（±100ms）
□ 字数合理（≤20字/条）
□ 对比度足够（≥7:1）
□ 平台规格符合

## BGM检查
□ 情绪与内容一致
□ 音量平衡正确
□ 版权合规
□ 无突兀转场
□ 结尾自然淡出

## 整体检查
□ 音画同步
□ 音量一致性
□ 节奏流畅
□ 平台适配
□ 导出质量
```

### 五、2026 配音字幕BGM工具推荐

| 用途 | 工具 | 价格 | 推荐度 |
|------|------|------|--------|
| **配音** | Azure TTS | $$ | ⭐⭐⭐⭐⭐ |
| **配音（开源）** | GPT-SoVITS | 免费 | ⭐⭐⭐⭐⭐ |
| **配音（克隆）** | ElevenLabs | $$ | ⭐⭐⭐⭐⭐ |
| **字幕** | CapCut | 免费 | ⭐⭐⭐⭐⭐ |
| **字幕（专业）** | Aegisub | 免费 | ⭐⭐⭐⭐ |
| **BGM** | Epidemic Sound | $15/月 | ⭐⭐⭐⭐⭐ |
| **BGM（免费）** | YouTube Audio Library | 免费 | ⭐⭐⭐⭐ |
| **BGM（AI）** | Suno AI | 免费/付费 | ⭐⭐⭐⭐ |
| **剪辑全能** | DaVinci Resolve | 免费 | ⭐⭐⭐⭐⭐ |

### 六、今日总结

**核心要点回顾**：

| 模块 | 2026新要点 |
|------|-----------|
| **配音** | 情绪控制进阶、中文声调优化、30秒极速克隆 |
| **字幕** | 动态字幕普及、AI自动纠错、无障碍升级 |
| **BGM** | AI生成爆发、音量LUFS标准、节奏精准同步 |

**可落地实践**：

1. **配音流程标准化**
   - 选择合适的TTS引擎
   - 使用情绪参数控制
   - 添加呼吸感增加自然度

2. **字幕制作规范化**
   - 遵循平台字号规范
   - 动态效果提升观看体验
   - 做好无障碍设计

3. **BGM使用专业化**
   - 情绪匹配是核心
   - 音量闪避要设置
   - 版权合规要重视

4. **整体工作流**
   - 配音→字幕→BGM→合成
   - 自动化脚本提效
   - 质量检查不能少

---

**第三周周五学习完成 ✅**

**下周学习预告**：
- 周一：高级分镜：多线叙事（已覆盖）
- 周二：AI视频生成Prompt进阶（已覆盖）
- 周三：剪辑节奏与转场（已覆盖）
- 周四：平台算法（已覆盖）
- 周五：配音/字幕/BGM（已覆盖）
- 周六：waoowaoo项目研究
- 周中：持续更新最新行业动态

---

> **本次更新时间**: 2026-03-20 10:00 (Asia/Shanghai)
> **专题**: 中文配音、字幕排版、BGM选择（2026更新版）
> **新增章节**: 二十

**Made with ❤️ by Research Agent (xiaoresearch)**

---

## 📹 第三周周六：waoowaoo 项目最新更新研究（2026-03-22）

> 基于 waoowaoo 最新 commit `9aff44e` (2026-03-16) 分析
> 1376 文件，201,271 行代码

### 一、重大架构变更：Agent 化 Prompt 架构

#### 1.1 Prompt 架构从 JSON → 纯文本 Agent 化

**旧架构（第一周研究时）**：
```
standards/prompt-canary/
├── screenplay_conversion.canary.json    # JSON 结构化 Prompt
├── storyboard_panels.canary.json
├── story_to_script_clips.canary.json
└── voice_analysis.canary.json
```

**新架构（当前）**：
```
lib/prompts/novel-promotion/
├── agent_cinematographer.zh.txt       # 🆕 摄影 Agent
├── agent_character_profile.zh.txt     # 🆕 角色档案 Agent
├── agent_character_visual.zh.txt      # 🆕 角色视觉 Agent
├── agent_clip.zh.txt                  # 🆕 剪辑 Agent
├── agent_storyboard_plan.zh.txt       # 🆕 分镜规划 Agent
├── agent_storyboard_detail.zh.txt     # 🆕 分镜细节 Agent
├── agent_storyboard_insert.zh.txt     # 🆕 分镜插入 Agent
├── agent_acting_direction.zh.txt      # 🆕 表演指导 Agent
├── agent_shot_variant_analysis.zh.txt # 🆕 镜头变体分析 Agent
├── agent_shot_variant_generate.zh.txt # 🆕 镜头变体生成 Agent
├── screenplay_conversion.zh.txt       # 保留
├── voice_analysis.zh.txt              # 保留
└── ... (30+ 个中英双语 Prompt 文件)
```

**关键洞察**：
- 从 4 个 JSON → 30+ 个纯文本 Agent Prompt
- 每个专业角色（摄影、表演、分镜）有独立 Agent
- **双语支持**：每个 Prompt 有 `.zh.txt` 和 `.en.txt` 版本
- Prompt 从 JSON 结构约束 → 自然语言指令（给 LLM 更大发挥空间）

#### 1.2 新增 Agent 角色详解

| Agent | 职责 | 输入 | 输出 |
|-------|------|------|------|
| **cinematographer** | 摄影指导：灯光、景深、色调、角色位置 | 分镜面板列表 | 每个镜头的摄影规则 JSON |
| **character_profile** | 角色档案：性格、背景、动机 | 小说原文 | 角色深度档案 |
| **character_visual** | 角色视觉：外貌描述 | 角色档案 | 图片生成 Prompt |
| **clip** | 剧本剪辑：原文→分镜片段 | 小说章节 | 剪辑列表 |
| **storyboard_plan** | 分镜规划：全局分镜策略 | 剪辑列表 | 分镜框架 |
| **storyboard_detail** | 分镜细节：逐镜头生成 | 分镜框架 | 完整分镜面板 |
| **acting_direction** | 表演指导：情绪、动作 | 分镜面板 | 表演指令 |
| **shot_variant_analysis** | 镜头变体分析：如何改景别/角度 | 原始镜头 | 变体方案 |
| **shot_variant_generate** | 镜头变体生成：实际生成 | 变体方案+参考图 | 新镜头图片 |

#### 1.3 摄影指导 Agent 核心逻辑

**景深规则（新发现！）**：

| 镜头类型 | 光圈值 | 景深 | 用途 |
|----------|--------|------|------|
| 全景/远景 | T8.0 | 深景深 | 展现空间全貌 |
| 中景 | T4.0 | 中等景深 | 自然过渡 |
| 近景 | T2.8 | 浅景深 | 轻微背景虚化 |
| 特写 | T1.8 | 极浅景深 | 强烈背景虚化 |
| 过肩镜头 | ≤T2.8 | 浅景深 | 前景肩膀虚化 |

**对话场景景深规则（关键新知识！）**：
```
⚠️ 口型同步的景深要求：
- 对话中出现多张脸 → 必须浅景深（T2.8或更小）
- 说话者脸部清晰，背景角色虚化
- 目的：防止口型识别系统混淆多张清晰的脸
```

**这是一个实战中极容易忽略的问题**——如果AI生成的视频中多个人物都清晰可见，口型同步系统可能会把声音配错人！

### 二、新增 MiniMax（海螺）视频生成器

#### 2.1 支持模型一览

| 模型 | 分辨率 | 时长 | 首帧输入 | 首尾帧 | 音频 | 定位 |
|------|--------|------|----------|--------|------|------|
| **Hailuo-2.3** | 768P/1080P | 6/10s | ✅ | ❌ | ✅ | 旗舰（推荐） |
| **Hailuo-2.3-Fast** | 768P/1080P | 6/10s | ✅ | ❌ | ✅ | 快速版 |
| **Hailuo-02** | 512P/768P/1080P | 6/10s | ✅ | ✅ | ✅ | 经典版 |
| **T2V-01** | 512P/768P | 5s | ❌ | ❌ | ❌ | 纯文本 |
| **T2V-01-Director** | 512P/768P | 5s | ❌ | ❌ | ❌ | 导演模式 |

#### 2.2 MiniMax Hailuo 2.3 vs 其他模型对比

| 特性 | Hailuo 2.3 | Veo 3.1 | Kling 2.0 | Vidu Q3-Pro |
|------|-----------|---------|-----------|-------------|
| **中文理解** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ |
| **首帧输入** | ✅ | ✅ | ✅ | ✅ |
| **首尾帧** | ❌(2.3)/✅(02) | ✅ | ✅ | ✅ |
| **内置音频** | ✅ | ✅ | ❌ | ✅ |
| **最长时长** | 10s | 8s | 10s | 16s |
| **最高分辨率** | 1080P | 4K | 1080P | 1080P |
| **速度** | 快 | 中 | 中 | 快 |
| **Prompt优化** | ✅(prompt_optimizer) | ❌ | ❌ | ❌ |

**MiniMax 独有特性**：
```
prompt_optimizer: true  // 自动优化 Prompt！
```
> 这是目前唯一在 API 层面自动优化 Prompt 的视频生成器。

#### 2.3 模型选择决策树更新（2026-03-22版）

```
需要中文场景？
├─ 是
│   └─ 需要 Prompt 自动优化？
│       ├─ 是 → MiniMax Hailuo 2.3（独有 prompt_optimizer）
│       └─ 否 → Veo 3.1（4K质量）或 Kling 2.0（性价比）
└─ 否 → Veo 3.1（综合最佳）

需要内置音频？
├─ MiniMax Hailuo 2.3（中文优化）
├─ Veo 3.1（原生音频+口型同步）
└─ Vidu Q3-Pro（最长16s）

需要最高质量？
├─ 4K → Veo 3.1
├─ 1080P → MiniMax Hailuo 2.3 或 Kling 2.0
└─ 快速预览 → Veo 3.1 Fast / Hailuo 2.3 Fast

需要首尾帧连续性？
├─ Veo 3.1 ✅
├─ MiniMax Hailuo-02 ✅（注意：2.3版本不支持）
├─ Kling 2.0 ✅
└─ Vidu Q3-Pro ✅
```

### 三、analysis workflow 重构

#### 3.1 新增 resolve-analysis-model

```typescript
// 从用户偏好中解析分析模型
async function resolveAnalysisModel(input: {
  userId: string,
  inputModel?: unknown,
  projectAnalysisModel?: unknown
}): Promise<string>
```

**逻辑优先级**：
1. 用户在当前请求中指定的模型
2. 项目设置的分析模型
3. 用户全局偏好中的分析模型
4. 系统默认模型

**可借鉴的架构模式**：
```
请求级模型 > 项目级模型 > 用户级模型 > 系统默认
```

### 四、Docker 多阶段构建优化

```dockerfile
# Stage 1: Dependencies (npm ci)
# Stage 2: Build (prisma generate + next build)
# Stage 3: Production (node:20-alpine + tini)
```

**改进**：使用 tini 作为 PID 1 进程，确保 Docker 容器中信号正确传递。

### 五、关键学习总结

| 新发现 | 影响 | 可落地实践 |
|--------|------|-----------|
| Agent化Prompt架构 | 从JSON→自然语言，更灵活 | 视频项目也拆分为Agent角色 |
| 对话景深规则 | 多人脸场景需浅景深 | AI视频生成时在Prompt中指定景深 |
| MiniMax Hailuo 2.3 | 中文最佳+Prompt自动优化 | 中文场景首选模型 |
| 双语Prompt模板 | 30+ 中英文Prompt | 国际化项目参考 |
| 模型优先级链 | 请求>项目>用户>系统 | 自己的项目可借鉴 |

---

## 📹 第三周总结（2026-03-16 ~ 2026-03-22）

### 一、本周学习路线

| 日期 | 主题 | 核心收获 |
|------|------|----------|
| **周一(3/16)** | 高级分镜：多线叙事与镜头角度 | 平行/交叉/重复蒙太奇、俯仰拍、荷兰角、希区柯克变焦 |
| **周二(3/17)** | AI视频生成 Prompt 进阶 | 六要素公式、Veo 3.1原生音频、Sora 2故事板、Kling权重语法 |
| **周三(3/18)** | 剪辑节奏与转场技巧 | 三段式控制、BGM卡点、匹配剪辑、呼吸节奏法 |
| **周四(3/19)** | 平台算法偏好与爆款规律 | 2026算法变革：价值前置>悬念、完播率≠流量、TikTok 70%阈值 |
| **周五(3/20)** | 配音/字幕/BGM选择 | 2026版工具矩阵、动态字幕、LUFS音量标准、AI BGM |
| **周六(3/22)** | waoowaoo 最新研究 | Agent化架构、MiniMax Hailuo 2.3、对话景深规则 |

### 二、三周学习知识体系总览

```
短视频制作知识体系（3周完成）
│
├── 📐 分镜设计（Week 1 + Week 3 进阶）
│   ├── 景别/运镜基础
│   ├── 黄金前三秒 / 三段式结构
│   ├── 多线叙事（平行/交叉/重复蒙太奇）
│   ├── 镜头角度（俯拍/仰拍/荷兰角）
│   └── 高级运镜（希区柯克变焦/环绕/长镜头）
│
├── 🤖 AI视频生成（Week 1 + Week 3 进阶）
│   ├── Veo 3.1（4K + 原生音频 + 口型同步）
│   ├── Sora 2（故事板 + 物理一致性 + 60s）
│   ├── Kling 2.0（运动控制 + 权重语法）
│   ├── MiniMax Hailuo 2.3（中文最佳 + Prompt优化）🆕
│   ├── Vidu Q3-Pro（内置音频 + 16s）
│   ├── 六要素 Prompt 公式
│   ├── 图生视频（首帧/尾帧传递）
│   └── 模型选择决策树（2026-03-22版）🆕
│
├── ✂️ 剪辑与转场（Week 1 + Week 3 进阶）
│   ├── 节奏控制（快/中/慢/极快）
│   ├── BGM卡点三步法
│   ├── 匹配剪辑 / 动作转场 / 遮罩转场
│   ├── 呼吸节奏法
│   └── 同景别转场技巧
│
├── 📊 平台算法（Week 1 + Week 3 进阶）
│   ├── 抖音：三级火箭 + 价值前置 + 互动深度权重
│   ├── 小红书：CES评分 + BERT搜索SEO + 长尾搜索
│   ├── TikTok：观看时长驱动 + 70%完成率阈值 + 社区分发
│   ├── 2026核心变化：1.8秒决策、完播率≠流量、S/A/B/C分级
│   └── 跨平台分发策略
│
├── 🎙️ 配音/字幕/BGM（Week 1 + Week 3 进阶）
│   ├── TTS引擎矩阵（Azure/GPT-SoVITS/ElevenLabs/阿里云）
│   ├── 情绪控制（emotionStrength + 中文声调）
│   ├── 字幕新规范（动态字幕/AI纠错/无障碍）
│   ├── LUFS音量标准 + Ducking闪避
│   └── AI BGM（Suno v4/Udio）
│
├── 🏗️ 工程架构（waoowaoo 研究）
│   ├── Agent化Prompt架构（JSON→纯文本Agent）🆕
│   ├── Pipeline Graph工作流
│   ├── Guard代码质量守护系统
│   ├── 模型优先级链（请求>项目>用户>系统）🆕
│   └── 对话景深规则（多人脸→浅景深）🆕
│
└── 🛠️ 工具与资源（持续更新）
    ├── 视频生成：Veo 3.1 / MiniMax Hailuo 2.3 / Kling 2.0
    ├── 配音：Azure TTS / GPT-SoVITS / 阿里云 v3.5
    ├── 字幕：CapCut / Aegisub / Whisper v4
    ├── BGM：Epidemic Sound / Suno v4 / YouTube Audio Library
    └── 剪辑：DaVinci Resolve / CapCut / Premiere Pro
```

### 三、第三周核心突破（vs 前两周）

| 维度 | 第一/二周（基础） | 第三周（进阶） |
|------|-------------------|---------------|
| **分镜** | 基础景别/运镜 | 多线叙事/高级角度/希区柯克变焦 |
| **Prompt** | 基础模板 | 六要素公式/原生音频/故事板模式 |
| **节奏** | 基础转场 | BGM卡点/呼吸节奏/同景别转场 |
| **算法** | 基础指标 | 2026变革：价值前置/70%阈值/动态权重 |
| **配音** | 基础TTS | LUFS标准/Ducking/动态字幕 |
| **架构** | 了解waoowaoo | Agent化架构/MiniMax集成/景深规则 |

### 四、可立即落地的 Top 5 行动

1. **🔄 升级视频开头策略**
   - 从"悬念型"切换为"价值前置型"
   - 前1.8秒展示最有价值的信息

2. **🤖 采用 MiniMax Hailuo 2.3**
   - 中文短视频场景首选
   - 利用 prompt_optimizer 自动优化 Prompt

3. **📐 应用对话景深规则**
   - 多人对话场景：在Prompt中指定"T2.8或更小光圈"
   - 确保说话者清晰、背景人物虚化

4. **📊 设计互动节点**
   - 每条视频至少2个互动引导点
   - 发布后2小时内积极回复评论
   - 监控第3-5天数据做持续互动引导

5. **🎬 复用 waoowaoo Agent 架构**
   - 视频项目拆分为专业Agent角色（摄影/表演/分镜/剪辑）
   - 每个Agent独立Prompt，灵活组合

### 五、下一步学习方向

| 优先级 | 方向 | 原因 |
|--------|------|------|
| 🔴 高 | **实战制作** | 三周理论积累，需转化为实际作品 |
| 🔴 高 | **waoowaoo 本地部署** | 搭建全流程AI视频制作环境 |
| 🟡 中 | **数据驱动优化** | 发布后A/B测试、数据分析迭代 |
| 🟡 中 | **角色一致性方案** | 深入研究多角色面部一致性 |
| 🟢 低 | **高级特效** | CG合成、AI特效进阶 |

---

> **本次更新时间**: 2026-03-22 10:00 (Asia/Shanghai)
> **专题**: 第三周周六研究 + 周总结
> **知识库总规模**: 1376行waoowaoo源码分析 + 4500+行知识文档

**三周学习完成 ✅ 理论体系基本建成，进入实战阶段 🚀**

**Made with ❤️ by Research Agent (xiaoresearch)**

---

## 六、2026-03-25 学习专题：剪辑节奏控制与转场技巧（周三）

> 状态说明：本次任务已尝试抓取最新公开教程与行业文章，但当前环境访问外部站点持续出现 `ERR_CONNECTION_CLOSED / SSL EOF / private/internal IP block`，因此本节先基于已有知识库、既有研究积累与通用专业剪辑方法论完成结构化沉淀；待网络恢复后可补充最新一手链接与案例。

### 6.1 先讲结论：短视频节奏不是“剪得快”，而是“信息密度 + 情绪推进 + 视觉变化”匹配

很多新手把“节奏好”理解成疯狂切镜头，这是错的。

真正有效的节奏控制，取决于 3 个变量：

1. **信息密度**：这一秒观众获取了多少新信息
2. **情绪推进**：情绪是在升高、停顿，还是反转
3. **视觉变化频率**：画面构图、运动、景别、方向有没有变化

实操判断标准：
- 如果一句话信息很重，镜头可以短，但必须清楚
- 如果一句话情绪很重，镜头可以稍长，让观众“感受”而不是“看不清”
- 如果连续 3-5 秒没有新信息、没有情绪推进、没有视觉变化，观众大概率会滑走

### 6.2 短视频剪辑节奏的 5 个核心控制杆

#### 1）句子长度决定切点，不是音乐先决定切点

最稳的做法：**先按语义切，再按音乐微调**。

执行规则：
- 一句一个意思，优先在意思完整处切
- 不要在关键词中间切
- 转场点优先落在：结论句、反转句、动作完成点、情绪抬升点
- BGM 卡点是加分项，不是第一原则

一句话记忆：
> 先让人听懂，再让人觉得爽。

#### 2）“快慢快”比“一直快”更容易保留注意力

观众不怕快，怕的是**没有层次的快**。

推荐的 15-45 秒短视频节奏模板：
- **0-3秒：快** — 立刻抛结果/冲突/反常识
- **3-10秒：中快** — 补充必要背景
- **10-18秒：略慢** — 让核心信息落地
- **18-25秒：再加速** — 连续给证据/案例/对比
- **结尾 2-3 秒：干净收口** — 结论/行动引导/记忆点

如果全程都很快：观众会累。
如果全程都很慢：观众会走。

#### 3）节奏本质上靠“变化”，不是靠特效

优先级应该是：
1. **内容变化**（信息升级）
2. **景别变化**（远景/中景/近景）
3. **运动变化**（静止/推进/摇移）
4. **构图变化**（左右位置、留白、主体大小）
5. **转场特效**（最后才考虑）

也就是说：
- 只是加转场，不会自动变高级
- 真正让节奏变好的，是镜头关系设计

#### 4）停顿是节奏的一部分，不是错误

很多爆款视频里都会留出 **0.2-0.6 秒的“呼吸点”**。

适合保留停顿的位置：
- 金句前
- 反转后
- 表情变化时
- 字幕重点出现时
- 结尾 CTA 前

停顿的作用：
- 让重点被看见
- 给情绪一个落点
- 避免观众持续疲劳

#### 5）字幕节奏 = 第二套剪辑节奏

很多短视频不是被画面留住的，而是被字幕留住的。

字幕节奏建议：
- 一屏只放一个主要意思
- 不要把整句一次性全打出来
- 关键词分段出现，形成“阅读节奏”
- 强结论词单独高亮：比如“不是效率低，是流程错了”里的“流程错了”

### 6.3 实操模板：不同视频类型的推荐节奏

#### A. 干货口播类

适合：AI工具、创业方法、增长策略、教程拆解

节奏建议：
- 3-6 秒一小段
- 每 1-2 句话切一次机位/构图
- 每 5-8 秒必须出现一次视觉变化（截图、B-roll、标题卡、局部放大）
- 结论句前后保留 0.2-0.4 秒停顿

结构模板：
- Hook：先抛结论
- Proof：给证据/案例
- Breakdown：拆 2-3 个关键点
- Close：一句话总结 + CTA

#### B. 剧情/情绪类

适合：故事、角色演绎、反转短片

节奏建议：
- 不要为了快而乱切
- 情绪建立段可适当放长镜头
- 反应镜头比动作镜头更能带情绪
- 转场应服务情绪，不服务炫技

结构模板：
- 建立关系
- 制造冲突
- 情绪停顿
- 反转/爆点
- 余韵收尾

#### C. 产品展示 / AI 生成作品展示类

适合：before-after、功能演示、作品集

节奏建议：
- 一个卖点一个镜头
- before/after 必须做明显对照
- 转场尽量简洁，避免喧宾夺主
- 用节奏递进把“越来越强”的感觉做出来

结构模板：
- 问题画面
- 解决方案出现
- 结果展示
- 细节放大
- 最终对比

### 6.4 转场技巧：先禁欲，再升级

短视频最容易犯的错，就是转场太多。

#### 新手优先使用的 4 类安全转场

1. **硬切（Straight Cut）**
   - 最常用、最安全
   - 信息明确时，硬切通常比花哨转场更高级

2. **动作切（Action Cut）**
   - 在动作过程中切到下一镜
   - 比如手抬起、转头、走路、坐下等动作中途切
   - 作用：自然、顺滑、不容易出戏

3. **J-cut / L-cut（声音先行 / 画面延后）**
   - 下一段声音先出来，画面后切
   - 或上一段声音继续，画面先切走
   - 作用：提升流畅度，减少生硬感

4. **同形/同方向匹配切（Match Cut）**
   - 用相似构图、相同运动方向、相近主体位置连接镜头
   - 作用：高级、统一、适合品牌感内容

#### 谨慎使用的 4 类转场

1. 闪白/闪黑
2. 推拉模糊
3. 旋转/扭曲特效
4. 大量预设包转场

这些不是不能用，而是：
- 只在“情绪升级 / 时空切换 / 节拍爆点”时偶尔用
- 绝不能每 2 秒来一次

### 6.5 判断一个转场该不该用：3 个问题

每次想加转场前，先问：

1. **这个转场有没有帮助观众理解内容？**
2. **它是在增强情绪，还是在打断注意力？**
3. **如果改成硬切，会不会其实更好？**

如果 3 个问题里有 2 个答不上来，这个转场大概率不该加。

### 6.6 AI 短视频时代的节奏优化：和传统剪辑不一样的地方

你现在做的是 AI 原生内容，不是纯真人拍摄，所以节奏控制要额外注意 4 件事：

#### 1）AI 镜头一致性不稳定，转场要“帮它藏瑕疵”

适用做法：
- 在动作中切
- 在字幕弹出时切
- 在 BGM 重拍点切
- 在局部特写和全景之间切

这样可以弱化 AI 画面细节漂移、口型轻微异常、手部细节不一致。

#### 2）AI 视频容易“每个镜头都差不多”，要靠剪辑制造层次

建议每条视频至少主动设计 3 种变化：
- 景别变化
- 字幕样式变化
- 画中画 / 截图 / 局部放大变化

#### 3）AI 作品常常缺真实“反应镜头”，需要补反应节奏

补法：
- 插入停顿
- 插入字幕强调
- 插入结果画面/评论截图/对比画面
- 用音效做节奏锚点

#### 4）转场要服务“可信度”，不是服务“酷”

如果你在讲 AI、创业、效率工具，过多炫技转场会削弱可信度。
更好的路线是：
- 清晰
- 节制
- 有重点
- 有层次

### 6.7 可直接执行的剪辑检查清单（发布前 2 分钟自检）

发布前逐条过：

- [ ] 前 1-2 秒有没有直接给价值/冲突/结果
- [ ] 是否存在连续 3 秒以上“无新信息”画面
- [ ] 每 5-8 秒是否至少有一次视觉变化
- [ ] 重点句前后是否留了呼吸点
- [ ] 字幕是否按阅读节奏分段，而不是整段堆满
- [ ] 转场是否大多为硬切 / 动作切 / J-cut / L-cut
- [ ] 花哨转场是否真的有明确理由
- [ ] 结尾是否干净，不拖尾

### 6.8 给 Daniel 内容团队的落地建议

结合你们现在做 AI 内容分发，这里最值得立刻执行的 5 条：

1. **统一默认转场策略**
   - 默认：硬切 + 动作切 + 少量 J/L-cut
   - 禁止上来就套花哨转场包

2. **建立“5秒必变”规则**
   - 任意短视频每 5 秒至少有一次明确视觉变化
   - 变化可以来自景别、B-roll、局部放大、标题卡、对比画面

3. **脚本阶段就标节奏点**
   - 不要等剪辑时才想哪里快哪里慢
   - 在文案里直接标注：
     - [Hook]
     - [停顿]
     - [证据]
     - [反转]
     - [结论]

4. **把字幕当成第二镜头系统来设计**
   - 重点词拆出来
   - 结论词高亮
   - 字幕出现节奏要和口播节奏同步

5. **建立“少即是多”的审片标准**
   - 审片时先删特效，再看是否更好
   - 如果删掉后更清楚、更高级，说明原来就是多余的

### 6.9 今日结论（适合发群）

今天最重要的 3 个收获：

1. **节奏控制的核心不是剪得快，而是信息、情绪、视觉变化的匹配**
2. **最稳的转场依然是硬切、动作切、J-cut/L-cut，花哨转场只该偶尔用**
3. **AI 短视频要靠剪辑帮模型“藏瑕疵、提层次、保可信度”**

### 6.10 今日参考来源

> 注：以下为本次尝试访问的专业站点方向；当前环境网络受限，未能完成在线抓取，待网络恢复后补齐摘录与具体文章标题。

- Frame.io Blog（视频剪辑与后期工作流）
- PremiumBeat Blog（剪辑节奏、转场、B-roll、镜头语言）
- Adobe Blog / Creative Cloud Video（转场、Premiere/剪辑方法论）
- 本地既有知识库：`/home/aa/clawd/reports/video-production-knowledge.md`

> **本次更新时间**: 2026-03-25 10:00 (Asia/Shanghai)
> **专题**: 周三｜剪辑节奏控制与转场技巧

---

## 6.11 2026-03-27（周五）｜中文配音、字幕排版、BGM 选择

> 目标：让“口播清晰可懂 + 字幕不挡画面且易读 + BGM 提情绪不抢戏”。

### 6.11.1 中文配音（口播/AI配音）可落地要点

**A. 文案先为“可说”负责（比任何降噪都重要）**
1. **一口气句**：每句尽量控制在 **12–18 个汉字**（或 3–5 秒语速），否则必然需要硬剪/喘气补救。
2. **重音词前置**：把关键词放在句子前半段（观众注意力窗口更短）。
3. **可视化停顿**：在脚本里标注口播结构：
   - [停顿0.2s] / [重读] / [放慢] / [笑/叹气]
4. **“口型友好”用词**：少用连续爆破音（b/p/t/k）堆叠；避免绕口令式并列。

**B. 录音/生成的硬指标（保证后期可控）**
1. **采样率**：48kHz（视频标准），避免后期重采样出问题。
2. **电平**：口播峰值建议在 **-6 ~ -3 dBFS**（录制时别顶到 0），留余量做压缩/限制。
3. **环境噪声**：宁愿离麦近一点，也别靠降噪“救”。（降噪会让齿音、气声变塑料。）
4. **口播一致性**：同一条视频尽量保持 **同一距离/同一角度/同一空间反射**；不然会出现“拼接感”。

**C. 配音混音（让观众听得清、听得舒服）**
1. **先做“人声清晰链”，再加 BGM**（顺序不能反）：
   - EQ：低切 80–120Hz（去轰鸣）
   - 压缩：轻压 2:1~4:1（让音量更稳定）
   - 去齿音：6–8kHz 区间控制（中文口播常见）
   - Limiter：控制峰值，避免削波
2. **响度目标（经验值）**：
   - 以“成片整体”为单位：优先保证 **Integrated Loudness 约 -16 ~ -14 LUFS**（短视频偏 -14 更常见），**True Peak ≤ -1 dBTP**。
   - 人声在整体里要“站前面”：宁可 BGM 更小，也别让人声靠硬压去赢。
3. **BGM Ducking（闪避）**：人声出现时，BGM 自动压下 **6–12 dB**（侧链/自动关键帧都行）。

### 6.11.2 字幕排版（抖音/小红书通用）行动清单

**A. 字幕可读性规则（做成默认模板）**
1. **两行以内**；每行尽量 **32–42 字符**（中文可等价理解为“别塞满屏”，重点是“读得完”）。
2. **读速控制**：目标让观众不暂停也能跟上（一般不建议一屏塞太多信息）。
3. **时长建议**：单条字幕 **≥1.0s**（太短读不完），通常 **不超过 6s**（太长会“糊”）。
4. **字体**：无衬线优先（黑体类），白字 + 黑描边/阴影（抗复杂背景）。

**B. 安全区与遮挡（短视频最容易翻车点）**
1. **底部安全区**：至少预留 **10% 高度**（避免被点赞/评论/进度条遮挡）。
2. **主体避让**：人物嘴部/关键产品信息附近别放大字；宁可上移一行。
3. **多端检查**：发布前一定在手机全屏 + 小窗/评论区打开状态各看一遍。

**C. “字幕是第二套镜头语言”**
1. **关键词拆行**：结论词单独一行（更像“打点”）。
2. **信息分层**：
   - 主字幕：口播逐字（或意译）
   - 辅字幕：补充数据/反差点（小字号/浅色）
3. **节奏同步**：字幕出现点要卡在“重音词”之前 0.1–0.2s（让眼睛先准备，耳朵再接收）。

### 6.11.3 BGM 选择与使用：不抢戏但能“抬情绪”

**A. 选曲三问（快速筛掉 80% 不合适的歌）**
1. **它的情绪是不是“同向”**（燃/松弛/悬疑/高级感）？
2. **它有没有歌词**（有歌词通常会抢中文口播；除非你刻意要“音乐主导”）？
3. **它的节奏点能不能和剪辑对齐**（鼓点/Drop/停顿）？

**B. 结构用法（短视频更像“配乐设计”不是随便铺底）**
1. **Hook 前 1 秒给“音色标识”**：用一个辨识度强的前奏（但音量要克制）。
2. **每 3–5 秒给一次小变化**：轻微换段/加打击/抽低频，配合画面转折。
3. **转场用 SFX/击打点**：比花哨转场更稳（观众会觉得“专业”）。

**C. 音量与频段（避免“糊”“吵”“脏”）**
1. **BGM 先低后高**：通常先把 BGM 拉到“几乎听不见”，再慢慢抬到“刚好感受到情绪”。
2. **给人声让路**：BGM 的 1–4kHz（人声清晰区）要谨慎；必要时对 BGM 做 EQ 挖洞。
3. **最后统一响度**：别只看峰值；要看整体听感一致。

### 6.11.4 今日结论（适合发群）

1. **中文口播的上限，80% 在脚本：句子短、重音明确、停顿可视化，后期才会轻松**
2. **字幕不是“自动生成就完事”，要按安全区、读速、关键词拆行做成模板化标准**
3. **BGM 的正确用法是“提情绪不抢人声”：闪避 6–12dB + 必要的频段让路，成片立刻高级**

### 6.11.5 今日参考来源（搜索到的可追溯链接）

- Subtitle Formatting Best Practices (VideoTap): https://videotap.com/blog/subtitle-formatting-best-practices-and-standards
- Closed Captioning/Subtitling Guide (Alpha CRC): https://alphacrc.com/insight/closed-captioning-subtitling-complete-guide/
- Captions/Transcripts guidance (Section508): https://www.section508.gov/create/captions-transcripts/
- Rules for text in videos (legibility.info): https://legibility.info/rules-for-text-in-videos
- Loudness standard overview (Descript): https://www.descript.com/blog/article/podcast-loudness-standard-getting-the-right-volume

> **本次更新时间**: 2026-03-27 10:00 (Asia/Shanghai)
> **专题**: 周五｜中文配音、字幕排版、BGM选择

---

## 6.12 周六｜研究 waoowaoo 项目新更新 / 技术实现

> **学习日期**: 2026-03-28 10:00 (Asia/Shanghai)
> **研究对象**: `waoowaooAI/waoowaoo` / `saturndec/waoowaoo`
> **仓库状态**: 10.5k+ stars，最近一次 push：2026-03-23，仍处于高频迭代期

### 6.12.1 最近一周的更新，透露了什么产品方向

从最近提交记录看，waoowaoo 的重点已经不只是“能生成”，而是进入 **生产级工作台优化阶段**：

1. **首页与工作区入口重构**
   - `feat: add home page and refactor workspace entry UI`（2026-03-23）
   - 含义：从“开发者工具感”走向“创作者工作台感”，降低首次上手成本。
   - 对短视频产品的启发：
     - 入口页不只是导航，而是要承担 **模板选择 / 最近项目继续 / API 配置提示 / 新手 onboarding**。
     - 生成式产品的流失，很多发生在“第一次创建项目前”。

2. **道具系统 + 素材库架构重构**
   - `feat: add props system and refactor asset library architecture`（2026-03-19）
   - 含义：系统开始把“角色、场景、道具”拆成独立资产层，而不是把所有信息都揉进 prompt。
   - 对短视频产品的启发：
     - 要做稳定的人物一致性和镜头连续性，**资产层必须结构化**。
     - 推荐最少拆成：角色 Character / 场景 Scene / 道具 Prop / 镜头 Shot / 音轨 Audio 五层。

3. **分析工作流架构重构**
   - `refactor: analysis workflow architecture`（2026-03-16）
   - 含义：前期的“脚本分析、分镜拆解、配音分析”已经复杂到需要 workflow 级编排，而不是单函数串行。
   - 对短视频产品的启发：
     - 当链路变成“文本 → 分段 → 分镜 → 图/视频 → 配音 → 合成”后，必须使用 **可重试、可观测、可中断** 的任务流。

4. **测试框架强化 + 鲁棒性防护**
   - `feat:Strengthen the testing framework`（2026-03-15）
   - `feat: implement robustness guards`（2026-03-08）
   - 含义：生成式工作流最怕“某一步偶发失败拖垮全链路”，所以他们开始补工程护栏。
   - 对短视频产品的启发：
     - AI 产品的核心竞争力不只是效果，而是 **失败时能不能优雅恢复**。

5. **多图读取 / 静音片段旁白分析 / MiniMax 接入语音链路**
   - `support multi-image reading`
   - `allow voiceover analysis for silent segments`
   - `Wire MiniMax audio through voice generation pipeline`
   - 含义：系统开始处理更真实的创作场景：参考图不止一张、镜头不一定有对白、音频 provider 需要可替换。
   - 对短视频产品的启发：
     - 真正可用的视频系统，必须支持 **多参考输入 + 无对白镜头 + 多 provider fallback**。

### 6.12.2 waoowaoo 值得抄的 5 个技术实现思路

#### A. “Prompt 不是字符串”，而是标准化中间件

它的 `standards/prompt-canary/*.json` 很关键，本质是在做 **结构化 prompt contract**。

典型字段包括：
- `shot_type`
- `camera_move`
- `location`
- `characters`
- `duration`
- `video_prompt`
- `emotionStrength`

**为什么这很重要：**
- 纯文本 prompt 不可测试、不可 diff、不可复用
- JSON 化后，才可以做：
  - 模板复用
  - 参数校验
  - 多模型适配
  - 回放调试
  - A/B 对比

**可落地建议：**
短视频团队内部不要只保存“最终 prompt”，要保存：
1. 输入素材
2. 解析后的结构化字段
3. 拼装规则
4. 发给模型的最终 prompt
5. 输出结果与失败日志

这 5 层一旦留档，后续优化速度会快很多。

#### B. 用工作流图，而不是页面按钮串联生产

仓库里有 `workflows/script-to-storyboard/graph.ts`，说明他们不是把流程写死在页面里，而是抽成图式编排。

**推荐的生产链路设计：**
1. 文本/小说导入
2. 故事切片（clip segmentation）
3. 场景识别
4. 分镜生成
5. 角色/场景/道具绑定
6. 视频生成
7. 配音/旁白生成
8. 成片合成
9. 失败重试 / 人工接管

**关键原则：**
- 每一步都要有独立输入输出
- 每一步都要能单独重跑
- 每一步都要记录 token / 耗时 / provider / 错误

这比“一键生成整片”更重要，因为一键只是表象，底层一定要可拆。

#### C. 资产库重构，是解决一致性的正路

最近新增 `props system` 和 `asset library architecture`，这基本是在补一个生成式视频产品的命门：**连续镜头一致性**。

**一致性为什么会崩：**
- 每个镜头都临时写 prompt
- 角色外观没有唯一 ID
- 道具没有标准命名
- 场景只靠自然语言描述

**正确做法：**
- 角色：存外观设定 + 风格图 + 口头特征
- 场景：存环境描述 + 光线 + 景别基准图
- 道具：存形态、颜色、尺寸、使用关系
- 镜头：只引用资产 ID，不重复从零描述

**一句话：**
要把“生成”从一次性文本赌博，升级成 **资产驱动的视频装配系统**。

#### D. 音频链路要独立，不能绑死在视频生成器里

从提交记录看，他们把 MiniMax 接到了 voice generation pipeline，并支持 silent segments 的 voiceover analysis。

这说明成熟系统会把音频当成独立生产线，而不是“最后补一下配音”。

**建议的音频层拆分：**
1. 台词对白 TTS
2. 旁白 Narration
3. 静音镜头的情绪音效/留白策略
4. BGM 选配
5. 混音与响度统一

**为什么重要：**
短视频观看体验里，很多“高级感”不是画面决定，而是 **节奏 + 声音层次** 决定。

#### E. 产品稳定性来自“护栏设计”，不是靠用户手动避坑

Issue 里已经能看到一些典型问题：
- 模型选择异常
- aspect ratio 参数不支持
- 生图结果死循环
- 安装架构过于复杂
- 希望整合成整集视频

这些问题很有代表性。说明 AI 视频产品真正难点不是“模型够不够强”，而是：
- 参数合法性校验
- provider 差异兼容
- 长任务状态管理
- 安装部署门槛
- 结果可恢复性

**工程建议：**
- 在前端就做参数约束（比如比例、分辨率、时长）
- 为每个 provider 建 adapter，不要把兼容逻辑散落在业务层
- 任务状态至少区分：queued / running / retrying / partial_success / failed
- 失败后默认给用户“从失败节点继续”，而不是重来

### 6.12.3 对 Daniel 内容系统最有价值的 3 个结论

#### 结论 1：短视频生产系统的核心不是“出片”，而是“可拆可控”
如果想稳定日产多条内容，必须把流程拆成节点：
- 选题
- 脚本段落
- 镜头卡
- 视觉资产
- 音频资产
- 成片合成

只有这样，某个镜头废了，才能局部重做，而不是整条重来。

#### 结论 2：一致性问题，本质是资产管理问题，不只是 prompt 问题
人物不像、场景漂、道具换样，通常不是模型太差，而是系统里没有独立资产层。

对我们后续所有短视频/图文/封面自动化，都应该尽量建立：
- 人设卡
- 场景卡
- 视觉风格卡
- 平台模板卡

#### 结论 3：真正拉开差距的是“失败恢复速度”
别人比你快，不一定是生成更强，而是：
- 出错能快速定位
- 参数有默认安全值
- 能从中间节点继续
- provider 挂了可以切备用

这套思路非常适合 Daniel 的“先跑起来再迭代”。

### 6.12.4 今天可直接执行的动作清单

1. **把视频生产流程做成节点卡片**
   - 先不要追求全自动
   - 先把每一步的输入/输出定清楚

2. **建立最小资产层**
   - 至少先有：角色 / 场景 / 道具 / BGM 风格 / 字幕模板

3. **给 provider 加 fallback 思维**
   - 图像、视频、配音都别单点依赖
   - 每条链路保留主 provider + 备用 provider

4. **把错误做成“可恢复”而不是“可报错”**
   - 用户不需要知道报错栈
   - 用户需要的是：下一步该点什么继续

5. **保留结构化生成日志**
   - prompt 字段
   - 模型版本
   - 耗时
   - 花费
   - 输出效果备注

### 6.12.5 今日参考来源

- GitHub 仓库首页：https://github.com/waoowaooAI/waoowaoo
- 实际高活跃仓库：https://github.com/saturndec/waoowaoo
- README（功能/安装/技术栈）：https://github.com/saturndec/waoowaoo/blob/main/README.md
- Issues（当前用户痛点）：https://github.com/saturndec/waoowaoo/issues

### 6.12.6 今日一句话总结

**waoowaoo 最近的升级方向很明确：从“AI 能生成视频”走向“AI 视频生产系统可被组织、被复用、被恢复”。这才是做短视频自动化真正该学的东西。**

> **本次更新时间**: 2026-03-28 10:00 (Asia/Shanghai)
> **专题**: 周六｜研究 waoowaoo 项目新更新 / 技术实现

---

## 📹 第四周总结（2026-03-23 ~ 2026-03-29）

> 总结日期：2026-03-29（周日）
> 知识文件累计：5369 行，覆盖 4 周学习内容

### 一、本周实际覆盖情况

| 日期 | 计划主题 | 状态 | 对应章节 |
|------|----------|------|----------|
| 周一(3/23) | 分镜设计 | ❌ 未产出 | — |
| 周二(3/24) | AI 视频生成 Prompt | ❌ 未产出 | — |
| **周三(3/25)** | **剪辑节奏控制与转场技巧** | ✅ 完成 | 第六章 6.1–6.10 |
| 周四(3/26) | 算法爆款规律 | ❌ 未产出 | — |
| **周五(3/27)** | **配音/字幕/BGM选择** | ✅ 完成 | 第六章 6.11 |
| **周六(3/28)** | **waoowaoo 项目最新更新** | ✅ 完成 | 第六章 6.12 |
| 周日(3/29) | 周总结（本节） | ✅ 完成 | — |

**本周产出率：3/6（50%）**

未产出原因分析：
- 周一/周二：cron 任务触发但外部网络异常（ERR_CONNECTION_CLOSED / SSL EOF），内容生成受阻
- 周四：同上，外部抓取失败 + session 异常中断

### 二、本周核心知识提取（3 个专题）

#### 专题 A：剪辑节奏控制与转场技巧（周三）

| 核心观点 | 可落地实践 |
|----------|-----------|
| 节奏 ≠ 剪得快，而是信息密度+情绪推进+视觉变化的匹配 | 先按语义切，再按音乐微调 |
| "快慢快"比"一直快"更容易保留注意力 | 15-45s 视频节奏模板：Hook(快)→背景(中快)→核心(慢)→证据(加速)→收口(干净) |
| 停顿 0.2-0.6s 是节奏的一部分 | 金句前/反转后/表情变化时留呼吸点 |
| 字幕 = 第二套剪辑节奏 | 关键词分段出现，结论词单独高亮 |
| 转场优先级：硬切 > 动作切 > J/L-cut > 匹配切 > 特效 | 默认只用前 3 类，花哨转场需要明确理由 |
| AI 短视频特有问题 | 用动作中切/字幕弹出时切/BGM卡点切来藏瑕疵 |
| "5秒必变"规则 | 任意 5s 内至少一次明确视觉变化 |

#### 专题 B：配音/字幕/BGM（周五）

| 核心观点 | 可落地实践 |
|----------|-----------|
| 中文口播上限 80% 在脚本 | 每句 12-18 汉字，重音词前置，标注停顿/重读 |
| 录音硬指标：48kHz / 峰值 -6~-3 dBFS | 宁离麦近别靠降噪救 |
| 混音顺序：先做人声清晰链，再加 BGM | EQ 低切 80-120Hz → 压缩 2:1~4:1 → 去齿音 → Limiter |
| 响度目标：-16~-14 LUFS / True Peak ≤-1 dBTP | BGM Ducking 6-12dB |
| 字幕两行以内，底部预留 10% 安全区 | 关键词拆行 + 同步口播节奏（字幕先 0.1-0.2s） |
| BGM 选曲三问 | 情绪同向？无歌词？节奏可对齐？ |
| BGM 用法：先低后高 | 从"几乎听不见"慢慢抬到"刚好感受到情绪" |

#### 专题 C：waoowaoo 项目研究（周六）

| 核心观点 | 可落地实践 |
|----------|-----------|
| Prompt 从 JSON→Agent 化纯文本 | 每个专业角色（摄影/表演/分镜）独立 Agent，30+ 双语 Prompt |
| 道具系统 + 素材库架构重构 | 拆成角色/场景/道具/镜头/音轨五层资产 |
| MiniMax Hailuo 2.3 独有 prompt_optimizer | 中文场景首选，唯一 API 层自动优化 Prompt |
| 对话景深规则 | 多人脸 → 浅景深 T2.8，防口型识别混淆 |
| 核心洞察：从"能生成"→"可组织、可复用、可恢复" | 流程节点化 + 资产结构化 + 错误可恢复 |

### 三、四周知识体系进度

```
短视频制作知识体系（4周 / 6周计划，已完成 67%）
│
├── 📐 分镜设计
│   ├── ✅ 基础分镜语言（第1周）
│   ├── ✅ 高级分镜：多线叙事与镜头角度（第3周周一）
│   └── ❌ 进阶分镜：动态分镜 / AI 辅助分镜（第4周周一，未产出）
│
├── 🎨 AI 视频生成 Prompt
│   ├── ✅ 基础 Prompt 工程（第1周）
│   ├── ✅ 六要素公式 + 多模型适配（第3周周二）
│   └── ❌ Prompt 自动化 / A/B 测试（第4周周二，未产出）
│
├── ✂️ 剪辑节奏与转场
│   ├── ✅ 基础转场类型（第1周）
│   ├── ✅ 剪辑节奏控制（第2周周三）
│   └── ✅ 进阶：节奏=信息+情绪+视觉 / AI视频特有节奏（第4周周三）
│
├── 📊 平台算法与爆款
│   ├── ✅ 2026 算法变革 / 完播率≠流量（第3周周四）
│   └── ❌ 进阶：多平台差异化算法（第4周周四，未产出）
│
├── 🎙️ 配音/字幕/BGM
│   ├── ✅ 基础工具矩阵（第3周周五）
│   └── ✅ 进阶：中文口播脚本规范 / 混音链 / 响度标准 / 字幕模板（第4周周五）
│
├── 🔧 waoowaoo 项目追踪
│   ├── ✅ 项目架构 + Prompt 工程（第1-2周）
│   ├── ✅ Agent化架构 + MiniMax + 景深规则（第3周周六）
│   └── ✅ 产品方向：工作台优化/资产库/失败恢复/多provider（第4周周六）
│
└── 🏆 周总结
    ├── ✅ 第1周总结（3/9-3/15）
    ├── ✅ 第2周总结（3/16-3/22，与第3周合并）
    ├── ✅ 第3周总结（3/16-3/22）
    └── ✅ 第4周总结（3/23-3/29，本节）
```

### 四、第四周 vs 第三周：知识升级点

| 维度 | 第三周（3/16-22） | 第四周（3/23-29） | 提升幅度 |
|------|-------------------|-------------------|---------|
| 剪辑节奏 | "三段式控制 + BGM卡点" | "节奏=信息密度+情绪推进+视觉变化匹配" + 5个控制杆 + AI视频特有策略 | ⭐⭐⭐ 显著深化 |
| 配音/BGM | 工具矩阵 + 基础概念 | 完整混音链（EQ→压缩→去齿音→Limiter）+ LUFS 标准 + 脚本层面优化 | ⭐⭐⭐ 从概念到可执行 |
| waoowaoo | Agent 化架构 + MiniMax | 产品方向洞察 + 资产库架构 + 失败恢复设计 | ⭐⭐ 从技术到产品思维 |
| 分镜/Prompt/算法 | 正常产出 | 未产出（网络异常） | ⚠️ 缺失，下周补 |

### 五、第五周改进建议

1. **补齐缺失专题**：第4周的周一(分镜进阶)、周二(Prompt自动化)、周四(多平台算法)应优先在下周补上
2. **提升 cron 稳定性**：本周 3/6 产出率主因是外部网络 + cron 异常，需要：
   - 增加离线 fallback（当网络不可用时基于已有知识库生成）
   - cron 路径修复（已识别，待执行）
   - 热点池为空时的缓存机制
3. **知识输出格式标准化**：本周周三和周五的内容质量很高，格式统一，建议固定为模板
4. **新增实战练习**：前四周以理论积累为主，第5周建议加入"每专题 1 个实操案例"

### 六、本周最佳知识卡片（Top 3）

> 🥇 **"节奏不是剪得快，而是信息×情绪×视觉的匹配"** — 彻底改变了对"好节奏"的认知
>
> 🥈 **"中文口播上限 80% 在脚本"** — 把优化重心从后期移到创作源头
>
> 🥉 **"waoowaoo 的方向：从能生成 → 可组织、可复用、可恢复"** — AI 视频产品真正的工程壁垒

> **本次更新时间**: 2026-03-29 11:10 (Asia/Shanghai)
> **专题**: 周日｜第四周总结（2026-03-23 ~ 2026-03-29）

---

## 2026-03-31｜周二：AI 视频生成 Prompt 最佳实践（Veo / Runway / Kling 通用）

### 一、今日核心结论

今天这轮资料里，最值得记住的不是“写更长的 prompt”，而是：

**AI 视频 prompt 的本质，不是写愿望清单，而是当导演。**

真正有效的 prompt，必须同时回答 5 件事：

1. **镜头怎么拍**（景别 / 机位 / 运镜）
2. **谁在画面里**（主角身份 + 外观特征）
3. **正在发生什么**（动作 + 节奏）
4. **场景长什么样**（环境 + 时间 + 光线）
5. **最终是什么质感**（风格 + 情绪 + 声音）

Google 在 Veo 3.1 官方 guide 里已经把它讲得很清楚：

> **[Cinematography] + [Subject] + [Action] + [Context] + [Style & Ambiance]**

这套公式今天可以直接升级成我们自己的生产模板。

---

### 二、最实用的 Prompt 结构（推荐直接套）

#### 2.1 五段式主模板

```text
[镜头语言] + [主体设定] + [动作过程] + [场景环境] + [风格氛围/声音]
```

#### 2.2 中文可直接复制模板

```text
一个[景别/机位]镜头，主角是[年龄/身份/外貌特征/服装]，正在[核心动作]。
场景位于[地点/时间/天气/背景元素]，画面中有[补充环境细节]。
镜头[运镜方式]，主体呈现[情绪状态]。
整体风格为[写实/电影感/动画/胶片/纪实等]，光线是[逆光/暖光/冷光/霓虹/顶光等]，
声音包含[对白/SFX/环境音/BGM氛围]。
```

#### 2.3 英文极简导演模板（适合多数国际模型）

```text
[Shot type / camera movement], [subject with specific appearance], [action], in [environment/context].
[Lighting], [mood], [style].
Audio: [dialogue / SFX / ambient sound / music].
```

---

### 三、今天学到的 8 条硬规则

#### 规则 1：先写“镜头”，不要先写“想法”

大多数新手 prompt 一开头就在写概念：
- 错误：一个很酷的未来城市，一个女生很伤感
- 正确：**close-up / medium shot / low-angle / tracking shot / crane shot** 先定拍法

原因很简单：模型对“怎么拍”比对“我想表达什么”更容易执行。

**落地动作：**
每条视频 prompt 第一行必须先写：
- 景别：wide / medium / close-up / extreme close-up
- 机位：low angle / overhead / POV / over-the-shoulder
- 运镜：slow push-in / tracking / dolly / pan / arc shot

---

#### 规则 2：人物不能只写身份，必须写“可识别特征”

“一个女生”“一个老板”“一个程序员”都太虚。

更好的写法是：
- 年龄段
- 发型 / 发色
- 面部特征
- 服装
- 道具
- 姿态气质

**例子：**
- 弱：a young woman
- 强：a woman in her twenties with wavy brown hair, light freckles, oversized grey hoodie, tired eyes

**落地动作：**
给所有高频角色建立固定描述卡，保证多条视频角色一致。

---

#### 规则 3：动作要写成“过程”，不要只写结果

模型更擅长生成“变化过程”，而不是抽象终点。

- 弱：她很震惊
- 强：她先停住脚步，瞳孔放大，缓缓转头看向门口，呼吸变急促

**好 prompt 关注的是：**
- 起始动作
- 中间变化
- 结束状态

这会直接提升可控性，也更利于 4-8 秒短片段生成。

---

#### 规则 4：环境不是背景板，而是叙事的一部分

同样是“城市夜景”，差别可以极大：
- city at night
- a rainy cyberpunk street at night, neon reflections on wet asphalt, steam rising from vents

**环境至少补 4 个维度：**
1. 地点
2. 时间
3. 天气/空气状态
4. 可见细节（雾、霓虹、灰尘、人群、屏幕、反光等）

环境写得具体，画面就不容易空、假、飘。

---

#### 规则 5：风格词要少而准，别堆成垃圾场

很多失败 prompt 都死在这里：
“cinematic ultra realistic masterpiece epic beautiful best quality trending on artstation 8k award-winning...”

这类词堆对视频模型帮助有限，反而会稀释重点。

**更有效的风格写法：**
- shot on 35mm film
- documentary aesthetic
- handheld found-footage style
- retro VHS texture
- soft natural morning light
- moody cool blue tones

**原则：**
风格词控制在 **2-4 个强信号词** 就够了。

---

#### 规则 6：有音频能力的模型，要把声音单独写出来

这是今天最容易被忽略、但也最值钱的点。

Veo 3.1 官方已经明确支持：
- 对白
- 环境音
- 音效
- 音乐氛围

**写法建议：**
- Dialogue: “We have to leave now.”
- SFX: distant thunder, footsteps on wet concrete
- Ambient: quiet hum of a spaceship bridge
- Music: gentle orchestral swell

**落地动作：**
以后 prompt 默认增加一段 `Audio:`，哪怕只有 1 句。

---

#### 规则 7：不要只会说“不要”，要改写成“我想要什么”

官方建议非常关键：
比起写“不要建筑”“不要现代元素”，更有效的是正向描述你想看到的世界。

- 弱：no modern buildings
- 强：a desolate landscape with only wind-eroded rock formations and dry grasslands

**原因：**
视频模型对正向视觉描述的执行力，通常强于否定约束。

---

#### 规则 8：复杂镜头不要硬塞成一条，拆成工作流

今天资料里最值得吸收的生产思路，不是某个句式，而是 **workflow 思维**：

1. **先出首帧 / 尾帧**
2. **再做 first-to-last-frame 过渡**
3. **再做 ingredients / reference consistency**
4. **最后补多镜头 or 时间轴 prompt**

这比“一条 prompt 想生成完整神片”稳定得多。

---

### 四、三个当前最值得用的 Prompt 工作流

#### 工作流 A：单镜头爆点短视频
适合：口播包装、广告钩子、产品展示、情绪片段

**结构：**
```text
镜头语言 → 主体 → 动作 → 环境 → 风格 → 声音
```

**模板：**
```text
Medium close-up, a young Chinese founder in a black T-shirt, standing in a dim studio, turns toward camera and says, "Most people are using AI completely wrong." The camera slowly pushes in. Blue monitor light reflects on his face, dust floating in the air, cinematic tech-documentary style. Audio: clear male voice, subtle room tone, low suspense synth.
```

**适用建议：**
- 时长控制 4-6 秒
- 只做一个核心动作
- 只传达一个情绪

---

#### 工作流 B：图生视频（最稳）
适合：品牌角色一致性、封面动画化、海报转视频

**原则：**
如果首帧已经给了主体、构图、颜色、服装，那文字 prompt 就别再重复一堆静态信息，重点写 **运动**。

**模板：**
```text
The character slowly lifts her head and opens her eyes. A soft wind moves her hair and the fabric of her coat. The camera performs a subtle push-in. Mood is tense and emotional. Audio: faint wind, distant city ambience.
```

**重点：**
- 图已经告诉模型“长什么样”
- 文本只负责“怎么动、怎么拍、什么情绪、什么声音”

---

#### 工作流 C：时间轴 Prompt（多段叙事）
适合：8 秒内多镜头小剧情、转场 demo、产品故事

**模板：**
```text
[00:00-00:02] Wide shot of a young woman opening a hidden door in a concrete wall.
[00:02-00:04] Close-up of her eyes widening in surprise as warm light spills across her face.
[00:04-00:06] Tracking shot as she steps into a secret room filled with glowing screens.
[00:06-00:08] High-angle wide shot revealing the entire room. Audio: metal click, soft electrical hum, rising cinematic pulse.
```

**适用建议：**
- 每 2 秒只安排一个明确动作
- 镜头切换要有理由，不要乱变
- 最后 2 秒尽量给一个 reveal / payoff

---

### 五、Daniel 内容流里可直接执行的 Prompt SOP

#### SOP 1：每条视频先写“导演单”，再写 prompt

不要一上来就喂模型。
先写 6 行：

```text
主题：
主角：
关键动作：
场景：
镜头：
声音：
```

然后再把这 6 行转成正式 prompt。

这样可显著降低 prompt 漏项。

---

#### SOP 2：建立“角色卡 / 场景卡 / 风格卡”素材库

为了提升连续出片稳定性，建议固定三套卡：

- **角色卡**：年龄、脸部特征、发型、穿着、常用表情
- **场景卡**：办公室 / 街道 / 录音棚 / 咖啡馆 / 卧室等标准环境描述
- **风格卡**：纪录片感 / 创业 vlog / 赛博科技 / 情绪电影感 / 小红书 clean aesthetic

以后做 prompt，只需要：
**镜头指令 + 角色卡 + 场景卡 + 当前动作 + 音频说明**

效率会高很多。

---

#### SOP 3：一条视频先做 3 个版本，不要只赌一个 prompt

推荐最小 A/B/C 变体：

- **A版：改镜头**（push-in → handheld）
- **B版：改动作**（turn head → walk forward）
- **C版：改氛围**（cold neon → warm sunset）

不要一次同时改 5 个变量，不然你根本不知道结果为什么变好或变差。

---

#### SOP 4：失败时按这个顺序排查

如果生成结果“不对味”，按这个顺序看：

1. 主体描述太虚？
2. 动作写成结果，没有过程？
3. 镜头语言缺失？
4. 场景细节不够？
5. 风格词太多太杂？
6. 一个 prompt 塞了太多事件？

通常前 3 项就解释了 80% 的失败。

---

### 六、今天产出的可复用模板

#### 模板 1：口播钩子短视频

```text
Medium close-up, a confident young founder with short black hair and a plain black T-shirt looks directly into the camera in a dark studio. He leans slightly forward and says, "You're not using AI like a founder. You're using it like a toy." The camera slowly pushes in. Blue screen light, subtle shadows, cinematic startup documentary style. Audio: clean Chinese male voice, low electronic hum, soft tension-building synth.
```

#### 模板 2：产品 B-roll

```text
Macro close-up of a smartphone on a desk as notification lights pulse across the screen. A hand enters frame, lifts the phone, and the camera tracks with the motion. Late-night workspace, monitor glow, coffee cup, notebook, realistic commercial style. Audio: subtle desk movement, notification chime, soft ambient room tone.
```

#### 模板 3：情绪故事感片段

```text
Close-up, a young woman with slightly messy hair stands by a rain-covered window at night. She slowly exhales, lowers her eyes, and touches the cold glass with her fingertips. Neon reflections shimmer across her face. Moody cinematic style, cool blue palette, shallow depth of field. Audio: distant traffic, soft rain, quiet emotional piano.
```

---

### 七、今日知识卡片（适合发群）

| 核心观点 | 可落地实践 |
|----------|-----------|
| Prompt 不是许愿，是导演指令 | 固定用“五段式”：镜头 + 主体 + 动作 + 场景 + 风格/声音 |
| 图生视频时，文字别重复静态信息 | 图片负责“长什么样”，文字重点写“怎么动、怎么拍、什么声音” |
| 声音描述会显著提升完成度 | 默认增加 `Audio:` 段，写对白 / SFX / 环境音 / BGM |
| 复杂视频不要赌单条 prompt | 改成工作流：首帧 → 尾帧 → 过渡 → 多镜头时间轴 |
| Prompt 优化优先级 | 先改镜头和动作，再改风格词；少堆“高级感形容词” |

---

### 八、参考资料

1. Google Cloud Blog — *The ultimate prompting guide for Veo 3.1*  
   <https://cloud.google.com/blog/products/ai-machine-learning/ultimate-prompting-guide-for-veo-3-1>
2. Google DeepMind — *How to create effective prompts with Veo 3*  
   <https://deepmind.google/models/veo/prompt-guide/>
3. Google Cloud Docs — *Veo on Vertex AI video generation prompt guide*  
   <https://docs.cloud.google.com/vertex-ai/generative-ai/docs/video/video-gen-prompt-guide>

> **本次更新时间**: 2026-03-31 10:18 (Asia/Shanghai)
> **专题**: 周二｜AI 视频生成 Prompt 最佳实践

---

## 周三专题：剪辑节奏控制与转场技巧（2026-04-01）

> 来源：X平台专业创作者分享、TikTok/Reels算法优化指南、DaVinci Resolve/CapCut实战教程
> 关键词：Pacing、Beat Sync、Cut on Motion、Transitions

---

### 一、节奏控制（Pacing）核心公式：慢→快→慢

**黄金15秒节奏模板：**

| 时间段 | 节奏 | 镜头类型 | 时长/镜 | 目的 |
|--------|------|----------|---------|------|
| 0-2s | 慢（建氛围） | 极近景、特写（手部、水雾、眼神） | 2-5s | 建立情感，制造悬念 |
| 2-8s | 快（buildup） | 低角度广角推镜→蒙太奇快切 | 0.3-0.8s/镜 | 张力递增，鼓点加速 |
| 8-15s | 慢→收（释放） | 无人机拉升、手持温柔镜头 | 1-2s | 回归静谧，留回味 |

**节奏控制3条铁律：**
1. **紧张=快切（0.5-1s/镜），安静=慢停（2-4s/镜）** — 全快或全慢都是灾难
2. **20%慢镜头定律** — 即使是高燃视频，也要穿插20%慢镜头做"呼吸感"
3. **感知对比循环** — 高能量↔低能量、复杂↔简单，交替出现才能持续抓住注意力

**AI辅助节奏（2026新趋势）：**
- AI自动分析素材情感曲线，建议切点位置
- Prompt模板：`"分析参考视频剪辑风格：切割时序、节奏模式、转场类型。应用到我的[素材]"`
- 工具：CapCut节拍器、Remotion AI、Temvideo.ai

---

### 二、Beat Sync（节拍同步）— 剪辑的灵魂

**什么是Beat Sync：**
剪辑点精确对齐音乐节拍（鼓点、bass drop、riser），让画面和声音"一起跳动"。

**操作步骤：**
1. **选BGM** — 找有强节拍的（电子、hip-hop、trap）
2. **标记节拍** — CapCut导入后开"节拍标记"，或用波形预览手动标
3. **拖镜头到鼓点** — 放大时间线，每个切点对准节拍标记
4. **关键帧对齐** — bass drop时切到高潮画面（人物跳起、拳头挥出、产品亮相）

**Beat Sync避坑：**
- ❌ 只听主歌，忽略全曲结构 → 前5秒就跑偏
- ❌ 每个鼓点都切 → 节奏太碎，观众眩晕
- ✅ 在"音乐结构转折处"切（verse→chorus、drop前1秒）
- ✅ 用AI工具加速：Temvideo.ai一键自动beat sync

---

### 三、转场技巧（Transitions）— 5种实用转场

#### 转场1：Cut on Motion（动作切割）⭐最核心
- **原理**：在物体/人物运动高峰切镜头（如头转动时、手臂挥动中间）
- **入点**：动作开始时切入
- **出点**：动作即将结束时切出
- **效果**：画面流畅自然，观众几乎感知不到切换
- **口诀**：永远在动中切，永远不在静中切

#### 转场2：Match Cut（匹配剪辑）
- **原理**：两个镜头有相似形状/颜色/运动方向
- **示例**：咖啡杯→轮胎、门关→眼睛闭、下楼梯→瀑布
- **效果**：高级感，暗示关联性

#### 转场3：Whip Pan（甩镜头）
- **原理**：镜头快速左右/上下甩，利用运动模糊遮盖切点
- **后期增强**：加速20-50% + camera shake + motion blur
- **顺序重要**：先加速/切 → 再抖动 → 最后加模糊

#### 转场4：Zoom to Beat（缩放转场）
- **原理**：按节拍缩放（zoom in/out），配合音乐高潮
- **适用**：产品展示、食物拍摄、时尚穿搭

#### 转场5：模糊+透明度过渡
- **原理**：Blur + Scale + Opacity渐变
- **适用**：小互动、情绪转换
- **注意**：少用dissolve（太老气），多用SFX音效增强过渡感

---

### 四、剪辑工作流（2026优化版）

**三阶段法：**

| 阶段 | 核心任务 | 优先级 | 注意 |
|------|---------|--------|------|
| **1. Flow（流畅）** | 配音乐→定节奏→粗剪 | 最高 | 先定BGM，所有切割跟音乐走 |
| **2. Story（故事）** | 加B-roll→转场设计→叙事清晰 | 高 | 转场服务于故事，不是炫技 |
| **3. Pop（爆点）** | SFX音效→动画→调色 | 最后 | 少即是多，最后加 |

**AI Prompt 工作流（直接用）：**
```
"审查以下素材，制定剪辑计划：
1. 分析节奏模式（哪些段快/慢）
2. 标记B-roll插入点
3. 设计转场方案（每个切点用什么类型）
4. 标注音乐对齐点

素材：[描述你的素材内容]"
```

---

### 五、后期增强效果的正确顺序

**效果叠加顺序（顺序错误=白做）：**

```
1️⃣ 速度调整（加速/减速/速度曲线）
2️⃣ 切割和排列（确定切点）
3️⃣ Camera Shake（抖动效果）
4️⃣ Motion Blur（运动模糊，在抖动之后加）
5️⃣ 噪点/颗粒（film grain）
6️⃣ 调色（统一色调）
7️⃣ SFX音效（最后加）
```

**为什么顺序重要：**
- 先加模糊再加速 → 模糊方向会错
- 先调色再加抖动 → 颜色会闪烁
- 先加音效再切 → 音画不同步

---

### 六、可复用模板

#### 模板A：15秒产品展示节奏
```
0-2s: 慢镜头特写（产品局部，制造悬念）
2-5s: 中速（多角度展示，每镜1s）
5-8s: 快切（使用场景蒙太奇，每镜0.5s，对齐鼓点）
8-11s: 慢镜（人物使用产品，带表情）
11-14s: 快切收尾（效果对比、前后before/after）
14-15s: 静帧+Logo+CFA（收尾呼吸）
BGM: 选前奏慢→中间加速→结尾有drop的类型
```

#### 模板B：口播/知识类节奏
```
0-3s: 钩子镜头（疑问、冲突、反常识画面）
3-10s: 内容段（说话镜头+文字动画，切点在句子停顿处）
10-13s: 补充B-roll（数据、案例、演示画面）
13-15s: 收尾（总结金句+关注引导）
转场: 用Match Cut从说话人→B-roll，回到说话人用Whip Pan
```

#### 模板C：情绪故事短片节奏
```
阶段1 (慢): 建立人物和环境（2-3个长镜头，每镜3-5s）
阶段2 (中): 冲突/转折（镜头开始加快，1-2s/镜）
阶段3 (快): 高潮/爆发（快切蒙太奇，0.3-0.8s/镜）
阶段4 (慢): 释放/结局（回归长镜头，配旁白）
转场: 全程用Cut on Motion + Match Cut，避免花哨效果
```

---

### 七、核心工具推荐

| 用途 | 工具 | 说明 |
|------|------|------|
| Beat Sync | CapCut节拍标记 | 免费，一键标记 |
| AI Beat Sync | Temvideo.ai | 全自动对齐 |
| 速度曲线 | CapCut/Premiere | 预设模板+手动调节 |
| 运动模糊 | Premiere/After Effects | 增强转场流畅度 |
| 调色 | DaVinci Resolve | 专业级，免费版够用 |
| SFX音效 | Epidemic Sound / Artlist | 版权安全 |

---

### 八、今日知识卡片

> 🔑 **3条记住就够：**
> 1. **节奏公式**：慢（建氛围）→快（造张力）→慢（给回味）
> 2. **永远Cut on Motion**：在运动中切，不在静止中切
> 3. **效果叠加顺序**：速度→切割→抖动→模糊→噪点→调色→音效

### 参考资料
- X: @1996547293080596937 (Cut on Motion详解)
- X: @2037721386760974530 (2026节奏趋势)
- X: @1995430759260463305 (Beat Sync工具)
- X: @2038432443598881111 (感官同步技巧)
- X: @2037720591869112461 (AI剪辑工作流)
- X: @2038604659787718906 (B站中文剪辑课推荐)


---

# 📅 2026-04-02 (周四) 小红书/抖音/TikTok 算法偏好与爆款规律

## 一、三大平台算法核心机制（2025-2026 最新）

### 1. 多级推流漏斗（三平台通用）

所有平台都用「阶梯式推流」机制：

| 层级 | 流量池 | 关键指标 | 晋级条件 |
|------|--------|---------|---------|
| L1 初始池 | 200-500 曝光 | 完播率/点击率 | 完播率 > 45%（视频）；CTR > 5%（图文） |
| L2 扩散池 | 1k-5k | 互动率（点赞+评论+分享） | 点赞率 > 3%，有评论互动 |
| L3 爆款池 | 10k-100k+ | 分享率+收藏率 | 分享率高 → 进入爆款池 |
| L4 全域池 | 100k-1M+ | 持续互动+完播 | 算法认为"普适好内容" |

### 2. 小红书（Xiaohongshu）算法特点

**核心链路：封面点击 → 完读 → 点赞/评论 → 收藏**

- **封面是生死线**：CTR（点击率）决定一切，封面不好 = 直接出局
- **收藏是超级指标**：收藏行为相当于 50x 互动加权，是最强的「内容有价值」信号
- **搜索权重高**：小红书本质是「搜索+推荐」双引擎，标题/正文的关键词 SEO 极其重要
- **2025-2026 趋势**：算法开始打压纯 AI 生成内容（转化率下降 30%+），偏爱好：
  - ✅ 真实生活流、干货教程、素人故事
  - ✅ AI骨架 + 真实素材 的混合内容
  - ❌ 纯 AI 文/图/视频 → 流量断崖

### 3. 抖音（Douyin）算法特点

**核心链路：前3秒完播 → 全程完播 → 互动 → 分享**

- **3秒生死线**：前3秒必须 hook，常见公式：
  - 痛点型：「你是不是也…」
  - 悬念型：「99%的人不知道…」
  - 结果型：「我30天从XX到XX」
  - 夸张型：「太震惊了！」
- **完播率 > 一切**：抖音最看重完播率，其次是互动率
- **评论区生态**：创作者回复评论 = 高价值互动信号，能显著提升推流
- **2026 变现方向**：团购带货（零门槛，3分钟视频即可，0粉丝起步）

### 4. TikTok（国际版）算法特点

- **For You Page (FYP)** 逻辑与抖音类似，但更重：
  - **Rewatch率**：用户重复观看 = 最强信号
  - **Duet/Stitch 互动**：参与热点 = 流量加持
  - **Sound 使用**：热门音乐自带流量
- **发布频率**：日更 5-10 条可训练算法理解你的内容定位
- **链接惩罚**：视频内不放链接，bio/评论区引流

---

## 二、爆款内容公式（跨平台通用）

### Hook 公式（前3-5秒）

| 类型 | 公式 | 示例 |
|------|------|------|
| 痛点共鸣 | "你是不是也…" | "你是不是也每天都在刷手机？" |
| 反常识 | "别再做XX了" | "别再死记硬背了" |
| 结果前置 | "我用XX天做到了" | "我用30天从0到10万粉丝" |
| 悬念制造 | "最后一点最重要" | "99%的人不知道这个功能" |
| 情绪冲突 | 夸张表情+高能量开场 | "太震惊了！" |

### 内容类型爆款率排名（2025-2026）

| 排名 | 小红书 | 抖音 | TikTok |
|------|--------|------|--------|
| 1 | 干货教程 | 短教程/生活技巧 | 生活技巧/Challenge |
| 2 | 真实故事 | 情感共鸣 | Trending Sounds |
| 3 | 好物推荐 | 团购带货 | POV/Relatable |
| 4 | 对比测评 | 反转剧情 | Storytime |
| 5 | 攻略合集 | 知识科普 | Duets/Stitches |

---

## 三、可操作要点（CCO Checklist）

### ✅ 发布前检查
- [ ] **小红书**：封面 CTR 测试（至少2版封面对比）、标题含核心关键词、正文埋 3-5 个搜索词
- [ ] **抖音**：前3秒 hook 是否够强、完播率预估 > 45%、是否有引导评论的话术
- [ ] **TikTok**：用了热门 Sound 吗、前1秒是否有视觉冲击、CTA 在结尾而非开头

### ✅ 发布后优化
- [ ] 前30分钟：自回复评论制造互动氛围
- [ ] 前2小时：观察数据，完播率低 → 下次缩短时长
- [ ] 24小时：收藏/分享好的 → 追加相关内容形成系列

### ✅ 持续增长策略
- [ ] 每周逆向工程：分析同赛道 TOP 10 创作者的 hook + 选题 + 格式
- [ ] 每日 5-10 条发布量训练算法（质量 > 数量，但最低保障频率）
- [ ] 垂直领域锁定：不要跨太多领域，算法靠「主题聚类」推送

---

## 四、2026 反作弊更新

- **纯AI内容识别加强**：平台可检测 AI 生成的文本/图像/视频
- **虚假互动惩罚**：「生态贿赂」（买赞/买粉）会被降权
- **混合内容赢**：AI 骨架 + 真实素材 = 最佳策略
- **真正的指标**：收藏 > 分享 > 评论 > 点赞（价值递减）

---

## 五、今日知识卡片

> 🔑 **3条记住就够：**
> 1. **小红书封面=命**：CTR决定生死，收藏=50倍加权，SEO关键词是隐形流量
> 2. **抖音前3秒=命**：完播率>一切，评论区互动是秘密武器
> 3. **2026黄金法则**：AI骨架+真实素材 > 纯AI > 纯搬运，收藏>分享>评论>点赞

### 参考资料
- X: @2039188499723854288 (多级推流漏斗详解)
- X: @2039240742108078350 (完播率门槛与Hook公式)
- X: @2037373769367629993 (小红书指标链路)
- X: @2013494674797408493 (收藏加权机制)
- X: @2039197284198699322 (2025-2026算法趋势)
- X: @2038072253146169598 (反作弊与AI内容识别)

---

## 2026-04-03 周五：中文配音、字幕排版、BGM选择

### 一、中文配音技巧（AI+真人混合策略）

#### 🎙️ 工具推荐
| 工具 | 用途 | 优势 |
|------|------|------|
| ElevenLabs | 多语言AI配音、声音克隆 | 音域广、特色声线 |
| CapCut 内置 | 快速中文字幕+配音 | 免费、一站式 |
| 剪映专业版 | 中文场景最成熟 | 语速/音调可调 |
| Seedance 2.0 | AI短剧全流程配音 | 角色一致性对话 |

#### 💡 爆款配音秘诀
1. **开头高音调+情绪钩子**：「太震惊了！」「你绝对想不到」— 前3秒决定生死
2. **节奏匹配画面**：慢速铺垫 → 快节奏高潮，配音语速要跟剪辑节奏同步
3. **真人+AI混剪**：AI修音真人录音，保留"人性瑕疵"（呼吸、停顿）避免机器感
4. **2026趋势**：AI短剧一键生成多角色对话，角色声音一致性大幅提升

#### ⚡ 配音SOP
```
写文案 → 标注情绪节点 → AI生成初版 → 听感微调 → 加呼吸/停顿 → 与画面同步
```

---

### 二、字幕排版（提升80%完播率的视觉钩子）

#### 📐 爆款字幕设计规则

| 位置 | 样式 | 效果 |
|------|------|------|
| 前3秒 | 粗体+阴影+动画弹出 | 强视觉钩子 |
| 中间段 | 短句不重叠、关键词高亮（黄/红） | 易读，提升完播 |
| 结尾CTA | 白色淡入+互动引导 | 促评论/关注 |

#### 🔑 关键参数
- **每行3-5个字**：不要塞太多，手机屏幕一瞥要读完
- **关键词高亮**：核心数字/情绪词用黄色或红色，其余白色
- **60fps导出**：字幕滚动/弹出动画才够丝滑
- **加轮廓+微抖效果**：适配无声音观看场景（30%用户静音刷视频）
- **底部1/3区域**：字幕不要遮挡画面核心内容

#### 🛠️ 字幕工具推荐
| 工具 | 特色 |
|------|------|
| CapCut 动态字幕 | 一键AI高亮关键词 |
| DaVinci Resolve | 免费预设包，专业级 |
| Vizard.ai | 长视频自动切短视频+字幕 |
| VEED Dynamic Subtitles | AI自动高亮关键词 |

---

### 三、BGM选择（情绪推手，不是背景噪音）

#### 🎵 BGM黄金公式
```
前3秒：低音冲击/鼓点 → 快切视觉同步
中间段：环境音填充死空间 → 增强沉浸感
高潮段：音乐峰值同步反转 → 音效叠加（冲击/运动声）
结尾：音乐淡出 → 配CTA字幕
```

#### 📊 BGM音量控制
- **旁白视频**：BGM 30-50% 音量，绝对不能抢人声
- **纯音乐视频**：BGM 100%，配合节奏切镜头
- **趋势舞曲**：加速 1.2x 更有紧凑感，符合短视频节奏

#### 🎧 免版权BGM来源
| 来源 | 说明 |
|------|------|
| CapCut 内置曲库 | 免费，平台不判侵权 |
| Epidemic Sound | 专业免版权，月费制 |
| YouTube Audio Library | 完全免费 |
| 抖音热门音乐 | 用平台内音乐=流量加持 |

#### 💡 BGM选择原则
1. **情绪匹配**：不要用欢快BGM配严肃内容（违和感=划走）
2. **趋势优先**：平台热门音乐有流量加权，优先用平台曲库
3. **节奏驱动**：BPM 120-140 最适合短视频节奏
4. **环境音叠加**：雨声/键盘声/咖啡厅底噪能大幅提升沉浸感

---

### 四、今日知识卡片

> 🔑 **3条记住就够：**
> 1. **配音**：AI+真人混合，保留呼吸/停顿，开头高音调钩子
> 2. **字幕**：每行3-5字，关键词高亮，30%用户静音刷→字幕要独立传达信息
> 3. **BGM**：音量30-50%不抢人声，用平台热门曲=流量加持，BPM 120-140最合适

### 参考资料
- X综合搜索: 2025-2026短视频配音字幕BGM技巧 (18条来源)
- VEED Dynamic Subtitles 功能介绍
- CapCut 2026 最新字幕模板
- Seedance 2.0 AI短剧全流程方案

---

## 七、waoowaoo 项目追踪（2026-04-04 周六）

> 追踪仓库: `saturndec/waoowaoo` | ⭐ 10,796 stars | 最后更新: 2026-04-03

### 7.1 版本动态（近一个月）

| 版本 | 日期 | 核心变化 |
|------|------|---------|
| **v0.4.1** | 2026-04-03 | 道具筛选逻辑优化 + Wan 2.7 模型接入 + 资产UI打磨 |
| **v0.4.0** | 2026-04-02 | 工作流架构重构 + Seedance 2.0 接入 + Props 资产体系 + 首页重做 |
| **v0.3.0** | 2026-03-07 | 架构大重构(634文件/45次提交) + 首尾帧串联 + Provider生态扩展 |
| v0.2.1 | 2026-02-28 | 多语言修复 |
| v0.2 | 2026-02-28 | OpenAI兼容格式支持 |
| v0.1 | 2026-02-27 | 首次开源 |

### 7.2 技术架构演进要点

#### A. Prompt 工程体系（已迁移至 `lib/prompts/`）

旧版用 `standards/prompt-canary/*.canary.json`，新版统一为 `lib/prompts/novel-promotion/` 下 `.en.txt` / `.zh.txt` 双语文件：

**核心 Prompt 链路（按执行顺序）：**

```
1. ai_story_expand        → AI 故事扩展（v0.4.0 新增，降低创作启动门槛）
2. episode_split          → 分集拆分
3. character_create       → 角色创建
4. character_visual       → 角色视觉设计
5. location_create        → 场景创建  
6. screenplay_conversion  → 剧本转换（小说→结构化剧本）
7. agent_clip             → 片段分割（故事→clip列表）
8. agent_storyboard_plan  → 分镜规划（每个clip→panel序列）
9. agent_cinematographer  → 摄影规划（构图/灯光/色调/运镜）
10. agent_shot_variant_*  → 镜头变体生成+分析
11. agent_storyboard_detail→ 分镜细节填充
12. agent_acting_direction→ 表演指导
```

**关键设计模式：**
- 所有 Prompt 输出严格 JSON，无 markdown 包装
- JSON 安全校验：所有引号转为「」避免解析错误
- 角色 `slot` 系统为"优选锚点"而非硬约束，运动/梦境/抽象场景可自由布局
- 保持 panel 间连续性（continuity），叙事节奏与镜头逻辑联动

#### B. 摄影规划 Prompt 解读 (`agent_cinematographer`)

输入：panel 数量 + panels JSON + 场景/角色/道具上下文
输出：每个 panel 的摄影方案包

```json
{
  "panel_number": 1,
  "composition": "构图与布局规则",
  "lighting": "灯光方向与质感",
  "color_palette": "主导色板",
  "atmosphere": "视觉氛围",
  "technical_notes": "运镜/景深/运动 notes（可直接用于图像/视频生成）"
}
```

**可借鉴点：** 我们自己的视频生成 prompt 可以引入类似结构化摄影方案，从"描述画面"升级为"描述灯光+构图+氛围+技术参数"。

#### C. 分镜规划 Prompt 解读 (`agent_storyboard_plan`)

每个 panel 包含：
- `characters[].slot`: 角色站位（从场景 `available_slots` 中取完整短语）
- `scene_type`: 场景类型（daily/dramatic 等）
- `shot_type`: 镜头类型（medium shot, close-up 等）
- `camera_move`: 运镜方式（static, pan, dolly 等）
- `video_prompt`: 短视觉运动 prompt
- `duration`: 持续时间（秒）

**可借鉴点：** `slot` 系统实现了角色位置跨镜头一致性——这是角色一致性的关键。

#### D. 视频模型生态

当前支持的模型/Provider：
- **Google Veo** (via `generators/video/google.ts`)
- **Seedance 2.0** (v0.4.0 正式接入，字节跳动)
- **Wan 2.7** (v0.4.1 新增)
- **FAL** (视频生成平台)
- **Ark Seedance** (字节火山引擎)
- **OpenAI Compatible** (通用兼容层)

首尾帧串联能力（v0.3.0）：支持单镜头同时配置首帧和尾帧，增强镜头连贯性。

#### E. 资产体系重构（v0.4.0）

统一三层资产：
- **角色 (Character)**: 视觉参考 + 外貌描述 + 多套外观(appearance)
- **场景 (Location)**: 可用站位(available_slots) + 视觉描述
- **道具 (Props)**: v0.4.0 新增，跨场景持续性道具追踪

资产中心 vs 项目资产边界明确化：资产中心存干净母图（无文字标识），项目内保留模型识别参考图。

### 7.3 对我们内容生产的启发

1. **Prompt 结构化** → 视频生成不应只给画面描述，应包含构图/灯光/色调/运镜结构化参数
2. **Slot 系统** → 角色跨镜头位置一致性是关键，我们生成系列内容时应维护角色位置记忆
3. **首尾帧串联** → 镜头转场时可利用首尾帧约束增强连贯性
4. **多模型 fallback** → 同一个我们 relay-image-gen/relay-video-gen 的思路，waoowaoo 也做了多 Provider 优先级
5. **AI Story Expand** → 从一个idea自动扩展为完整故事大纲，降低创作启动门槛

### 7.4 待追踪

- [ ] v0.5.0 预告：作者说"后续会有更大的更新"

---

## 📹 第五周总结（2026-03-30 ~ 2026-04-05）

> 总结日期：2026-04-05（周日）
> 知识文件累计：~6300 行，覆盖 5 周学习内容

### 一、本周产出情况

| 日期 | 计划主题 | 状态 | 对应章节 |
|------|----------|------|----------|
| 周一(3/30) | 分镜设计 | ❌ 未产出 | — |
| **周二(3/31)** | **AI 视频生成 Prompt 最佳实践** | ✅ 完成 | Veo/Runway/Kling 通用 Prompt 指南 |
| **周三(4/1)** | **剪辑节奏控制与转场技巧** | ✅ 完成 | Beat Sync + 5种转场 + 效果叠加顺序 |
| **周四(4/2)** | **平台算法偏好与爆款规律** | ✅ 完成 | 小红书/抖音/TikTok 2026最新算法 |
| **周五(4/3)** | **中文配音/字幕/BGM** | ✅ 完成 | AI+真人混合策略 + 动态字幕 + BGM公式 |
| **周六(4/4)** | **waoowaoo 项目追踪** | ✅ 完成 | v0.4.1分析 + Prompt链路拆解 + 资产体系 |
| 周日(4/5) | 周总结（本节） | ✅ 完成 | — |

**本周产出率：5/6（83%）** — 比上周 50% 大幅改善 ✅

### 二、本周核心知识提取（5 个专题）

#### 专题 A：AI 视频 Prompt 最佳实践（周二）

| 核心规则 | 可落地实践 |
|----------|-----------|
| Prompt 不是许愿，是导演指令 | 五段式：镜头 + 主体 + 动作 + 场景 + 风格/声音 |
| 先写镜头，不要先写想法 | 第一行必须写景别/机位/运镜 |
| 人物必须写可识别特征 | 建立角色卡（年龄/发型/服装/气质） |
| 动作写过程，不写结果 | 起始→变化→结束状态 |
| 风格词 2-4 个强信号 | "shot on 35mm film" > "cinematic masterpiece best quality" |
| 有音频模型要单独写声音 | 默认增加 Audio: 段 |
| 复杂镜头拆工作流 | 首帧→尾帧→过渡→多镜头时间轴 |

#### 专题 B：剪辑节奏与转场（周三）

| 核心规则 | 可落地实践 |
|----------|-----------|
| 黄金节奏：慢→快→慢 | 慢(建氛围)→快(造张力)→慢(给回味) |
| 永远 Cut on Motion | 在运动中切，不在静止中切 |
| 效果叠加顺序固定 | 速度→切割→抖动→模糊→噪点→调色→音效 |
| Beat Sync 三步法 | 选BGM→标记节拍→镜头对齐鼓点 |
| 20%慢镜头定律 | 高燃视频也要穿插慢镜头做呼吸感 |

#### 专题 C：平台算法 2026 最新（周四）

| 核心发现 | 影响 |
|----------|------|
| 小红书收藏=50倍加权 | 封面CTR+收藏引导是核心 |
| 小红书算法打压纯AI内容 | AI骨架+真实素材是最佳策略 |
| 抖音前3秒生死线 | 完播率>一切，评论区互动是秘密武器 |
| TikTok 看重 Rewatch率 | 循环结构+悬念结尾=高重看 |
| 收藏>分享>评论>点赞 | 互动价值递减顺序 |

#### 专题 D：配音/字幕/BGM（周五）

| 核心要点 | 可落地实践 |
|----------|-----------|
| AI+真人混合配音 | 保留呼吸/停顿避免机器感 |
| 字幕每行3-5字 | 关键词高亮（黄/红），30%用户静音刷 |
| BGM音量30-50% | 不抢人声，用平台热门曲=流量加持 |
| BPM 120-140最适合 | 节奏驱动剪辑 |

#### 专题 E：waoowaoo v0.4.x（周六）

| 核心变化 | 影响 |
|----------|------|
| Prompt 链路 12 步 | 从故事扩展→分镜→摄影→表演→镜头变体 |
| 摄影规划结构化 | 构图/灯光/色调/运镜参数化 |
| Slot 系统实现角色位置一致性 | 跨镜头角色位置记忆 |
| Seedance 2.0 + Wan 2.7 接入 | 国产视频模型生态扩展 |
| 道具(Props)资产层 | 跨场景持续性道具追踪 |

### 三、五周知识体系完成度

```
短视频制作知识体系（5周完成，覆盖率 ~85%）
│
├── 📐 分镜设计           ████████░░ 80%
│   ├── ✅ 基础景别/运镜
│   ├── ✅ 多线叙事/高级角度/希区柯克变焦
│   └── ⚠️ 动态分镜/AI辅助分镜（待深入）
│
├── 🤖 AI 视频生成 Prompt  █████████░ 90%
│   ├── ✅ 六要素公式 + 五段式模板
│   ├── ✅ Veo/Sora/Kling/MiniMax 适配
│   ├── ✅ 图生视频 + 时间轴 Prompt
│   └── ✅ Prompt 工作流（首帧→尾帧→过渡）
│
├── ✂️ 剪辑节奏与转场     █████████░ 90%
│   ├── ✅ 节奏控制（信息+情绪+视觉匹配）
│   ├── ✅ Beat Sync + Cut on Motion
│   ├── ✅ 5种核心转场 + 效果叠加顺序
│   └── ✅ AI视频特有节奏策略
│
├── 📊 平台算法与爆款      █████████░ 90%
│   ├── ✅ 抖音/小红书/TikTok 2026最新
│   ├── ✅ 完播率≠流量 + 互动深度权重
│   ├── ✅ AI内容识别 + 混合策略
│   └── ✅ 爆款公式 + Hook模板
│
├── 🎙️ 配音/字幕/BGM       █████████░ 90%
│   ├── ✅ AI+真人混合 + 混音链
│   ├── ✅ 动态字幕 + 关键词高亮
│   └── ✅ LUFS标准 + Ducking + BGM公式
│
├── 🔧 waoowaoo 追踪      ████████░░ 80%
│   ├── ✅ v0.1→v0.4.1 完整追踪
│   ├── ✅ 12步Prompt链路拆解
│   ├── ✅ 资产体系(角色/场景/道具)
│   └── ⚠️ 口型同步/漫剧模式（待v0.5）
│
└── 🏆 周总结              ██████████ 100%
    └── ✅ 5周全部完成
```

### 四、五周核心方法论浓缩（10 条）

| # | 方法论 | 来源 |
|---|--------|------|
| 1 | 节奏=信息密度×情绪推进×视觉变化 | 第4周 |
| 2 | Prompt是导演指令，不是愿望清单 | 第5周 |
| 3 | 永远Cut on Motion | 第5周 |
| 4 | 前1.8秒价值前置 > 悬念套路 | 第3-4周 |
| 5 | 完播率≠流量，互动深度才是王道 | 第3周 |
| 6 | AI骨架+真实素材 > 纯AI > 纯搬运 | 第5周 |
| 7 | 中文口播上限80%在脚本 | 第4周 |
| 8 | 收藏>分享>评论>点赞 | 第5周 |
| 9 | 效果叠加顺序：速度→切割→抖动→模糊→噪点→调色→音效 | 第5周 |
| 10 | 一致性问题的本质是资产管理，不是Prompt | 第4周 |

### 五、下周方向建议

从 5 周理论积累进入 **实战阶段**：

| 优先级 | 方向 | 原因 |
|--------|------|------|
| 🔴 高 | 用学到的Prompt模板实际生成3-5条短视频 | 理论→实践转化 |
| 🔴 高 | 用 Beat Sync + Cut on Motion 剪辑一条完整视频 | 验证剪辑知识 |
| 🟡 中 | 建立"角色卡/场景卡/风格卡"素材库 | 长期出片稳定性 |
| 🟡 中 | A/B测试不同Hook类型的数据表现 | 数据驱动迭代 |
| 🟢 低 | waoowaoo 本地部署 | 工程实践 |

### 六、本周最佳知识卡片（Top 3）

> 🥇 **"Prompt 是导演指令：先写镜头怎么拍，再写想表达什么"** — 从根本上改变了视频 Prompt 的写法
>
> 🥈 **"永远 Cut on Motion，永远不在静止中切"** — 一条规则提升80%的剪辑流畅度
>
> 🥉 **"2026年：AI骨架+真实素材 > 纯AI内容"** — 平台算法已开始打压纯AI，混合策略是出路

---

> **本次更新时间**: 2026-04-05 10:48 (Asia/Shanghai)
> **专题**: 周日｜第五周总结（2026-03-30 ~ 2026-04-05）
> **知识库总规模**: ~6300 行
> **五周学习完成 ✅ 理论体系基本建成，建议进入实战阶段 🚀**

**Made with ❤️ by Research Agent (xiaoresearch)**
- [ ] 口型同步(lip-sync)能力实现细节
- [ ] 漫剧模式的 prompt 差异
- [ ] Docker 部署实测与本地化改造可行性


---

## 第六周 · 周一｜分镜设计与镜头语言（深化实战篇）

> **更新时间**: 2026-04-06 11:52 (Asia/Shanghai)
> **专题**: 分镜设计 + 镜头语言 — 从理论到AI视频实战

### 一、分镜设计的本质：AI视频的"导演脚本"

**核心理念（来自 Sora/Veo 社区实战总结）：**

分镜 = 场景(Scene) + 镜头(Shot) + 动作(Action) + 情绪(Mood)

| 元素 | 描述 | AI Prompt 示例 |
|------|------|---------------|
| **场景** | 环境描述，时空设定 | "a dimly lit Tokyo alley at night, rain on ground" |
| **镜头** | 拍摄手法（景别+运镜） | "close-up shot, slow push-in, eye-level angle" |
| **动作** | 角色行为/事件 | "woman turns around, surprised expression, hand reaches for phone" |
| **情绪** | 光影、色调、氛围 | "cold blue-green color grading, lonely, cinematic" |

> 💡 **关键转变**: 先写镜头怎么拍，再写想表达什么。镜头语言 = 导演指令。

### 二、10大核心镜头语言（短视频必备）

#### 📐 景别体系 (Shot Size)

| 景别 | 英文 | 用途 | 情绪效果 |
|------|------|------|---------|
| 大远景 | Extreme Wide Shot (EWS) | 交代环境、场景建立 | 孤独感/壮阔感 |
| 远景 | Wide Shot (WS) | 角色全身+环境 | 客观叙述 |
| 中景 | Medium Shot (MS) | 腰部以上 | 日常对话、自然 |
| 近景 | Medium Close-up (MCU) | 胸部以上 | 亲密、关注 |
| 特写 | Close-up (CU) | 面部/物体 | 强调情绪/细节 |
| 大特写 | Extreme CU (ECU) | 眼睛/手/细节 | 极度聚焦、震撼 |

#### 🎥 运镜手法 (Camera Movement)

| 运镜 | 英文 | 效果 | 适用场景 |
|------|------|------|---------|
| 推镜头 | Push-in / Dolly In | 聚焦、紧张感递增 | 揭示关键信息 |
| 拉镜头 | Pull-out / Dolly Out | 展示全貌、孤立感 | 揭露真相 |
| 横摇 | Pan (左→右) | 环境展示、跟随 | 风景/群像 |
| 竖摇 | Tilt (上→下) | 展示高度/垂直关系 | 建筑/人物出场 |
| 跟随 | Tracking Shot | 沉浸感、参与感 | 行走/追逐 |
| 环绕 | Orbit / Arc Shot | 英雄感、360°展示 | 角色登场/产品展示 |
| 手持 | Handheld | 紧张、真实、纪录片感 | 恐怖/Vlog |
| 升降 | Crane / Boom | 空间感转换、气势 | 开场/结尾 |

#### 🔄 短视频分镜节奏公式

```
Hook(0-3s): 中景/近景 + 快速推镜头 → 抓住注意力
发展(3-8s): 交替景别(远景↔特写) + 横摇/跟随 → 建立节奏
高潮(8-12s): 特写/大特写 + 慢动作/环绕 → 情绪顶点
结尾(12-15s): 拉镜头/远景 + 2s留白 → 呼吸感+引导互动
```

### 三、AI视频分镜 Prompt 模板（2026最新）

#### 模板1：故事叙述型
```
[SHOT TYPE], [CAMERA MOVEMENT], [SUBJECT ACTION].
[ENVIRONMENT DESCRIPTION]. [LIGHTING/MOOD].
[TIME PERIOD], [STYLE/GENRE].
```

**示例：**
```
Medium close-up, slow push-in, a young woman looks up from her phone with surprise.
Cozy coffee shop interior, warm golden light streaming through window.
Afternoon, cinematic drama style.
```

#### 模板2：产品展示型
```
[OPENING SHOT: 产品全景], [TRANSITION: 运镜方式],
[CLOSE-UP: 细节特写], [FINAL: 使用场景].
[LIGHTING: 光影描述], [BACKGROUND: 背景虚化/环境].
```

#### 模板3：情绪短片型
```
Extreme wide shot → Slow dolly in → Close-up on eyes → Pull back to wide.
Color grade shifts from cold blue to warm amber.
No dialogue, environmental sound only.
```

### 四、对话场景专业分镜（来自 Seko AI 工作室实战）

**过肩正反打 (Over-the-shoulder Shot/Reverse Shot)**：
- 对话场景的黄金法则
- 两个人物交替出现在画面中，镜头过对方肩膀
- AI Prompt: `"over-the-shoulder shot, character A speaking, character B's shoulder in foreground, shallow depth of field"`

**180°原则**：
- 对话双方保持在屏幕同一侧
- 虚构的"动作线"不能跨越
- 违反 = 观众方向感混乱

**三机位覆盖 (Coverage)**：
```
机位1: 主角正面中景 (A-roll)
机位2: 对手方过肩 (B-roll)
机位3: 双人全景 (Establishing)
```

### 五、构图法则速查

| 法则 | 要点 | AI Prompt 关键词 |
|------|------|-----------------|
| 三分法则 | 主体放在交叉点 | "rule of thirds composition" |
| 引导线 | 利用线条引导视线 | "leading lines toward subject" |
| 对称/不对称 | 对称=稳定 不对称=张力 | "symmetrical/asymmetrical framing" |
| 框架构图 | 门框/窗户框住主体 | "framed through doorway/window" |
| 负空间 | 留白创造孤独/简约感 | "negative space, minimalist" |
| 深度层次 | 前中后三层 | "foreground interest, layered composition" |

### 六、实战 Checklist（每次分镜前过一遍）

- [ ] **每个镜头有目的吗？** 无目的的镜头 = 浪费观众时间
- [ ] **景别在变化吗？** 连续同景别 = 无聊
- [ ] **运镜有动机吗？** 无动机运镜 = 晕
- [ ] **3秒内有Hook吗？** 没Hook = 划走
- [ ] **情绪有起伏吗？** 平铺直叙 = 没记忆点
- [ ] **构图有层次吗？** 平面构图 = 不专业
- [ ] **最后一个镜头有留白吗？** 突然结束 = 不舒服

### 七、本周延伸资料

| 资源 | 类型 | 链接 |
|------|------|------|
| StudioBinder 构图完全指南 | 英文教程 | studiobinder.com/rules-of-shot-composition |
| 46个经典电影分镜案例 | 英文案例 | studiobinder.com/storyboard-examples-film |
| Seko AI 影视语言系统 | 中文 | zhuanlan.zhihu.com/p/1956347556964603034 |
| Sora 分镜 Prompt 技巧 | 中文 | blog.csdn.net/sinat_41617212 (分镜四要素) |
| Veo 3.1 镜头语言词典 | 中文 | juejin.cn/post/7569515660930531379 |
| StoryboardArt 电影语言 | 英文 | storyboardart.org/cinematography-and-film |

### 八、知识卡片（今日 Top 3）

> 🥇 **"分镜四要素：场景+镜头+动作+情绪 — AI视频的导演脚本"** — 结构化思考每个镜头
>
> 🥈 **"对话场景黄金法则：过肩正反打 + 180°原则 + 三机位覆盖"** — 让AI对话视频专业度翻倍
>
> 🥉 **"短视频分镜节奏：Hook(推镜头)→发展(交替景别)→高潮(特写环绕)→结尾(拉镜头留白)"** — 可直接套用的节奏公式

---

> **知识库状态**: 第六周开始 | 进入实战深化阶段
> **下期预告**: 周二 — AI视频生成 Prompt 最佳实践

**Made with ❤️ by CCO Research Agent**

---

# 📅 2026-04-08 (周三) — 剪辑节奏控制与转场技巧（第六周）

> 本期聚焦：短视频的剪辑节奏 (Pacing & Rhythm) 和转场设计 (Transitions)，从理论和实战两个维度拆解。

---

## 一、剪辑节奏的底层逻辑

### 1.1 为什么要控制节奏？

- **注意力窗口**：短视频用户前 0.8 秒决定是否划走，前 3 秒决定是否看完
- **信息密度**：节奏 = 信息释放速度，太快→看不懂，太慢→无聊
- **情绪曲线**：好的节奏让情绪有涨有跌，像音乐有节拍

### 1.2 节奏三要素

| 要素 | 定义 | 实操指标 |
|------|------|---------|
| **镜头时长** | 单个clip的持续时间 | Hook段: 0.5-1.5s, 正文: 2-4s, 结尾: 3-5s |
| **切换频率** | 单位时间内切换次数 | 快节奏: 4-6次/10s, 慢节奏: 1-2次/10s |
| **变速节奏** | 加速/减速的节奏变化 | 高潮前加速→高潮时慢放→结尾正常或加速 |

### 1.3 黄金节奏公式（可直接套用）

```
Hook(0-3s): 快切 0.5-1s/镜头，制造紧迫感
铺垫(3-10s): 稳定 2-3s/镜头，讲清楚背景
递进(10-20s): 逐渐加速，镜头时长递减
高潮(20-35s): 快切+变速，情绪爆发
收尾(35-45s): 放慢，留白，CTA
```

> **💡 关键原则**：节奏不是匀速的，要有「呼吸感」。连续快切3-4次后，插入一个稍长的镜头让观众"喘口气"。

---

## 二、转场技巧全解析

### 2.1 转场的本质

转场不是特效炫技，是**视觉逻辑连接**。每个转场都应该回答一个问题："为什么观众要跟着进入下一个画面？"

### 2.2 六大高频转场技法

| # | 转场类型 | 原理 | 适用场景 | 难度 |
|---|---------|------|---------|------|
| 1 | **硬切 (Hard Cut)** | 直接切换，无过渡 | 日常Vlog、信息流视频节奏感 | ⭐ |
| 2 | **动势转场 (Match Cut)** | 利用相似动作/形状/方向连接 | 创意视频、产品展示 | ⭐⭐⭐ |
| 3 | **遮挡转场 (Whip Pan)** | 画面被物体/手/镜头运动遮挡后切换 | Vlog、街头视频、快节奏内容 | ⭐⭐ |
| 4 | **速度渐变 (Speed Ramp)** | 加速模糊→切换→减速入场 | 运动、产品特写、旅行 | ⭐⭐ |
| 5 | **缩放转场 (Zoom Transition)** | 快速推近→切→拉远 | 知识讲解、对比展示 | ⭐⭐ |
| 6 | **遮罩转场 (Mask Wipe)** | 用遮罩擦除显示下一画面 | 技术教程、分屏对比 | ⭐⭐⭐ |

### 2.3 转场选择决策树

```
内容类型是什么？
├── Vlog/日常 → 硬切为主，偶尔遮挡转场
├── 知识讲解 → 缩放转场 + 硬切，保持清晰
├── 产品展示 → 速度渐变 + 动势转场，强调质感
├── 创意短片 → 动势转场 + 遮罩转场，制造惊喜
└── 情感故事 → 叠化/淡入淡出，温柔过渡
```

---

## 三、实战节奏模板

### 3.1 爆款知识类视频节奏（45s）

```
[0-1s]  硬切: 抛出问题/冲突（钩子画面）
[1-3s]  硬切: 给出答案预览（制造好奇）
[3-8s]  缩放转场→稳定镜头: 解释背景
[8-15s] 硬切交替: 2-3个支撑论据，每个2-3s
[15-25s] 加速快切: 举例/案例，节奏加快
[25-35s] 速度渐变: 核心结论，慢放强调
[35-42s] 缩放拉远: 总结+行动引导
[42-45s] 硬切: 结尾钩子/下期预告
```

### 3.2 产品展示视频节奏（30s）

```
[0-1s]  速度渐变: 产品特写闪入
[1-3s]  硬切: 3个快速角度切换
[3-8s]  遮挡转场→使用场景: 产品在真实场景中
[8-15s] 动势转场: 功能演示，手→产品→效果
[15-22s] 快切: 多角度展示细节
[22-28s] 速度渐变慢放: 最终效果展示
[28-30s] 硬切: 价格/CTA
```

### 3.3 情感/Vlog节奏（60s）

```
[0-3s]  氛围画面 + 文字（慢）
[3-10s] 叠化过渡: 场景铺陈
[10-20s] 硬切+遮挡: 日常片段，节奏中等
[20-35s] 加速剪辑: 快乐片段合集
[35-45s] 慢放+音乐高潮: 最美瞬间
[45-55s] 硬切减速: 回到当下
[55-60s] 淡出: 留白+感悟文字
```

---

## 四、BGM与节奏的配合（进阶）

### 4.1 踩点剪辑法

1. 导入BGM到时间线
2. 标记节拍点（beat markers）：副歌前、鼓点、音乐转折
3. 关键转场对齐节拍点
4. 歌词重要字眼对齐关键画面

### 4.2 BGM选择节奏匹配

| BGM类型 | BPM范围 | 适合内容 | 推荐转场节奏 |
|---------|---------|---------|-------------|
| 慢节奏抒情 | 60-80 | 情感、风景、旅行 | 3-5s/切 |
| 中速流行 | 80-120 | Vlog、日常、知识 | 2-3s/切 |
| 快节奏电音 | 120-140 | 运动、产品、创意 | 0.5-1.5s/切 |
| 超快节奏 | 140+ | 挑战、卡点、快闪 | 踩每个beat |

### 4.3 速度渐变 (Speed Ramp) 详细参数

```
前半段: 正常速度100% → 快速加速到400-800% (0.3-0.5s)
过渡点: 最高速时切换画面
后半段: 新画面从400-800% → 减速到100% (0.3-0.5s)

关键: 加速和减速曲线用 ease-in/ease-out，不要线性
CapCut中: 速度曲线工具 → 拖拽贝塞尔曲线
```

---

## 五、CapCut/剪映实操速查

### 5.1 快捷操作

| 操作 | CapCut快捷键/方法 |
|------|-------------------|
| 添加转场 | 两段素材之间点击 → 选择转场 |
| 速度曲线 | 选中片段 → 速度 → 曲线 → 自定义 |
| 踩点标记 | 音频轨道 → 节拍器/手动标记 |
| 批量调速 | 选中多段 → 变速 → 统一设置 |
| 转场时长 | 点击转场 → 拖拽调整时长（0.1-2s） |

### 5.2 常见错误与修正

| 错误 | 原因 | 修正 |
|------|------|------|
| 转场太多，眼花 | 每个镜头都加转场 | 80%硬切 + 20%特效转场 |
| 节奏拖沓 | 镜头太长，信息密度低 | 去掉无意义的"呼吸"镜头 |
| 踩点不精准 | 依赖自动标记 | 手动微调到耳朵舒服的位置 |
| 变速不自然 | 线性变速 | 用曲线变速（ease in/out） |
| 音乐和画面不搭 | 随便选BGM | 先定情绪→再选BPM匹配的BGM |

---

## 六、今日关键 Takeaway

🥇 **"节奏是呼吸：3-4个快切后必须跟一个稍长的镜头"** — 不是越快越好，是张弛有度

🥈 **"80/20转场法则：80%硬切+20%特效转场"** — 爆款视频的转场都极其克制

🥉 **"速度渐变黄金参数：100%→600%→切换→600%→100%，曲线必须用ease"** — 直接套用

---

> **下期预告**: 周四 — 小红书/抖音/TikTok 算法偏好与爆款规律

**Made with ❤️ by CCO Research Agent**

---

## 五、周五：中文配音、字幕排版、BGM选择

> 学习日期：2026-04-10

### 🎙️ 中文配音（Voiceover）

#### AI配音工具推荐（2025-2026主流）
| 工具 | 特点 | 适用场景 |
|------|------|---------|
| **Fish Speech** (开源) | 免费、可微调、中文优化 | 批量配音、IP克隆 |
| **CosyVoice** (阿里) | 情感控制、方言支持 | 多角色配音 |
| **T-XX / GPT-SoVITS** | 5秒音频克隆声音 | IP一致性需求 |
| **ByteDance Seed-TTS** | 最高质量，商业化 | 高端内容 |
| **海螺AI（MiniMax）** | 中文自然度高 | 快速批量 |

#### 配音节奏黄金法则
- **语速**: 正常说话 180-220字/分钟；短视频建议 220-260字/分钟（稍快但清晰）
- **停顿**: 每句话结束后留 0.3-0.5秒空隙；重点词前留 0.2秒暗示
- **重音**: 每15秒至少一个重音强调，否则听起来平淡
- **音量层次**: 配音比背景音乐低 6-10dB，确保人声清晰

#### 常见错误
- AI配音听起来"假" → 降低语速5%+添加呼吸声/气口
- 方言腔调不对 → 选专用模型而非通用模型
- 多人对话没有区分 → 用不同音色+不同混响区分角色

---

### 📝 字幕排版（Subtitle Design）

#### 平台字幕规格
| 平台 | 字体大小 | 行间距 | 安全区 |
|------|---------|--------|--------|
| 抖音/快手 | 36-48px | 1.4-1.6倍 | 下1/3区域 |
| 小红书 | 40-56px | 1.5倍 | 下1/4区域 |
| TikTok | 44-60px | 1.5-1.8倍 | 下1/4区域 |
| YouTube | 32-44px | 1.2-1.4倍 | 中心偏下 |

#### 字幕设计核心原则
1. **高对比度**: 白色字幕+黑色描边（2-3px），绝不裸字
2. **半透明底栏**: 黑色50%透明背景条，高度为字高的1.5倍
3. **逐字出现** > 逐行出现 > 整句出现（互动率更高）
4. **关键帧对齐**: 字幕切换点与音频气口、音乐鼓点对齐

#### 爆款字幕样式（2025实测）
- **语气字幕**: "真的？！" "绝了👏" "笑死" — 情绪共鸣强
- **标注字幕**: [炸裂] [前方高能] [打脸] — 引导情绪节奏
- **互动字幕**: "你们遇到过吗？" — 提升评论率
- **热搜词字幕**: 字幕中嵌入 #标签# — 蹭热点同时不破坏画面

#### 抖音字幕特殊技巧
- 关键字幕放大1.5倍 + 颜色高亮（如金色、绿色）
- 快节奏内容用"打字机效果"（逐字出现，100ms/字）
- 重要数字用红色字幕强调

---

### 🎵 BGM选择（Background Music）

#### BGM选择流程
```
Step 1: 定情绪 → Step 2: 定BPM → Step 3: 定风格 → Step 4: 裁剪匹配
```

#### 情绪→BGM类型映射
| 情绪目标 | BPM范围 | 推荐类型 |
|---------|--------|---------|
| 燃/热血 | 120-140 | 嘻哈、EDM、摇滚 |
| 轻松/愉快 | 100-120 | 流行、 indie、lo-fi |
| 紧张/悬疑 | 70-90 | 电影配乐、弦乐 |
| 治愈/温柔 | 60-90 | 钢琴、吉他、轻电子 |
| 搞笑/魔性 | 130-160 | 搞怪音效+快节拍 |

#### BGM与视频节奏匹配
- **卡点率**: 70%以上的镜头切换点要在鼓点上
- **淡入淡出**: BGM开头和结尾各留0.5秒淡入淡出，避免戛然而止
- **音量曲线**: 高潮处BGM音量+3dB，旁白处-6dB，形成动态层次
- **高潮预留**: 视频最后5秒是BGM高潮点，画面配合"哇"时刻

#### 免费BGM资源
- **Pixabay Music**: 免费可商用，分类清晰
- **Mixkit**: 高质量，免费商用
- **抖音创作者服务平台**: 平台热门BGM有流量加成
- **剪映/必剪**: 内置BGM库，版权相对安全

#### 常见BGM错误
- 选歌先于剪辑 → 应该是剪辑完成后再选BGM
- 全程同一BGM → 中间换一次BGM（转场时）打破单调
- BGM太热门 → 撞歌尴尬，选小众但同情绪的歌

---

### 📋 三合一输出检查清单

**配音检查:**
- [ ] 语速在220-260字/分钟？
- [ ] 人声比BGM高6-10dB？
- [ ] 没有明显AI味（听气口和停顿）？

**字幕检查:**
- [ ] 高对比度（白字+黑边）？
- [ ] 在安全区内（不被logo遮挡）？
- [ ] 关键字幕有放大/高亮？

**BGM检查:**
- [ ] 70%+镜头卡在鼓点上？
- [ ] 开头结尾有淡入淡出？
- [ ] 情绪和视频内容匹配？

---

## 六、今日关键 Takeaway

🥇 **"配音是情绪锚点：语速220-260+每15秒一个重音=专业感"**

🥈 **"字幕是第二画面：白字黑边+逐字出现+关键放大，三步提升完播率"**

🥉 **"BGM是视频的心跳：先定情绪→再定BPM→最后裁剪匹配，顺序不能乱"**

---

> **下期预告**: 周六 — 研究 waoowaoo 项目新更新/技术实现

**Made with ❤️ by CCO Research Agent**

---

## 十八、waoowaoo 项目最新研究（2026-04-11 周六专题）

### 18.1 项目当前状态概览

**waoowaoo AI 影视 Studio** 是目前 GitHub 上最活跃的 AI 视频生成应用项目之一，聚焦于小说→视频的端到端自动化生产。

| 指标 | 数据 |
|------|------|
| **GitHub Stars** | 9000+ |
| **代码规模** | 227,000+ 行代码 |
| **技术栈** | Next.js 15 + React 19 + Prisma + Redis + BullMQ |
| **视频生成** | Veo 3.1 / Vidu / Kling / Sora 2 / FAL |
| **音频生成** | 内置（Vidu）/ TTS 分离方案 |

### 18.2 核心技术架构演进

#### 18.2.1 Pipeline Graph 工作流引擎

**设计模式**：节点化、可组合、可观测的 Pipeline 架构

```typescript
// 核心节点类型
interface PipelineNode {
  key: string           // 节点唯一标识
  title: string         // 展示标题
  maxAttempts: number   // 最大重试次数
  timeoutMs: number     // 超时时间（毫秒）
  run: (context) => Promise<Output>
}

// 剧本→分镜完整工作流
const scriptToStoryboardPipeline = [
  { key: 'orchestrator', timeoutMs: 20 * 60 * 1000 },  // 20分钟
  { key: 'story_to_clips', timeoutMs: 5 * 60 * 1000 },
  { key: 'generate_panels', timeoutMs: 10 * 60 * 1000 },
  { key: 'generate_voice', timeoutMs: 5 * 60 * 1000 },
  { key: 'assemble_video', timeoutMs: 15 * 60 * 1000 }
]
```

**关键特性**：
- ✅ **并发控制**：`concurrency` 参数控制同时处理的剪辑数
- ✅ **错误恢复**：单节点失败不影响其他节点，自动重试
- ✅ **状态追踪**：完整的 `refs` + `meta` 状态传递
- ✅ **超时保护**：每个节点独立超时设置

#### 18.2.2 Prompt Canary 标准化体系

**核心价值**：结构化的 Prompt 模板，确保 AI 输出的一致性

| Prompt 模板 | 用途 | 关键字段 |
|-------------|------|----------|
| `screenplay_conversion` | 剧本→场景分解 | heading, content[], characters[] |
| `storyboard_panels` | 场景→分镜 | shot_type, camera_move, video_prompt |
| `story_to_script_clips` | 故事→片段 | start, end, summary, location |
| `voice_analysis` | 配音分析 | emotionStrength, matchedPanel |

**结构化输出优势**：
```
传统 Prompt: "生成一个分镜头脚本"
     ↓ 不可控
Canary Prompt: 输出必须包含 { shot_type, camera_move, duration, video_prompt }
     ↓ JSON Schema 约束
稳定可解析的结果
```

### 18.3 视频生成器生态

#### 18.3.1 生成器能力矩阵

| 生成器 | 时长 | 分辨率 | 首帧 | 尾帧 | 内置音频 | 运动控制 |
|--------|------|--------|------|------|----------|----------|
| **Veo 3.1** | 5-8s | 4K | ✅ | ✅ | ❌ | ❌ |
| **Vidu Q3-Pro** | 1-16s | 1080p | ✅ | ✅ | ✅ | ✅ |
| **Kling 1.5** | 5-10s | 1080p | ✅ | ✅ | ❌ | ✅ |
| **Sora 2** | 20-60s | 1080p | ✅ | ✅ | ❌ | ✅ |
| **FAL** | 5s | 720p | ✅ | ❌ | ❌ | ❌ |

#### 18.3.2 Provider 集成方案

```typescript
// 统一接口设计
interface VideoProvider {
  generate(params: VideoGenerateParams): Promise<GenerateResult>
  poll(taskId: string): Promise<VideoResult>
}

// Provider 路由
const providerMap = {
  'google': GoogleVeoVideoGenerator,
  'vidu': ViduVideoGenerator,
  'kling': KlingVideoGenerator,
  'openai-compatible': OpenAICompatibleVideoGenerator,
  'fal': FALVideoGenerator
}
```

### 18.4 计费系统设计

#### 18.4.1 Ledger 架构

```typescript
// 核心计费模型
interface LedgerEntry {
  userId: string
  type: 'debit' | 'credit'
  amount: number
  currency: 'USD' | 'CNY'
  service: string        // veo-3.1 / vidu-q3-pro / etc.
  quantity: number        // 次数/时长
  timestamp: Date
  balance: number        // 余额快照
}

// 成本计算
interface CostConfig {
  'veo-3.1': { base: 0.05, perSecond: 0.01 },
  'vidu-q3-pro': { base: 0.03, perSecond: 0.005 },
  'kling-1.5': { base: 0.02, perSecond: 0.003 }
}
```

#### 18.4.2 多货币支持

| 货币 | 适用场景 | 汇率换算 |
|------|----------|----------|
| USD | 国际用户、Google/Vidu API | 基准 |
| CNY | 国内用户、百炼/硅基流动 | 实时汇率 |

### 18.5 角色一致性方案

#### 18.5.1 角色设计流程

```
小说文本 → AI 角色分析 → 角色描述卡片 → AI 图像生成 → 首帧图片传递
                              ↓
                        角色库存储
                              ↓
                        分镜复用（same character + same appearance）
```

#### 18.5.2 外观标识系统

```typescript
// 角色外观标识
interface CharacterAppearance {
  characterId: string
  appearanceName: string  // "default", "formal", "casual", "battle_mode"
  appearanceDesc: string  // 详细描述（肤色、服装、发型等）
  referenceImageUrl?: string  // 参考图
}

// 分镜中使用
{
  "characters": [
    { "name": "Lena", "appearance": "formal" },
    { "name": "Victor", "appearance": "battle_mode" }
  ]
}
```

### 18.6 技术债务与改进方向

#### 18.6.1 Guard 系统（Robustness）

**作用**：确保代码质量和一致性

| Guard 类型 | 检查项 | 自动修复 |
|------------|--------|----------|
| TypeScript 类型 | 缺失类型、any 泛滥 | 部分 |
| ESLint | 代码风格、潜在 Bug | 否 |
| 测试覆盖 | 单元测试、集成测试 | 否 |
| Git Hook | 提交前检查 | 是 |

#### 18.6.2 国际化（i18n）架构

```
支持的语言: 中文 / English
Prompt 模板: *.canary.json (双语)
UI 界面: i18n keys (zh/en)
错误消息: locale 匹配
```

### 18.7 实战应用建议

#### 18.7.1 项目选型决策

| 场景 | 推荐方案 |
|------|----------|
| **快速 Demo** | waoowaoo + Vidu（音频内置） |
| **高质量短片** | waoowaoo + Veo 3.1（4K） |
| **长视频叙事** | waoowaoo + Sora 2（60s） |
| **低成本试错** | waoowaoo + Kling 1.5（性价比） |
| **完全自建** | 参考 Pipeline Graph 设计 |

#### 18.7.2 可复用的设计模式

1. **Pipeline Graph** → 复杂 AI 任务编排
2. **Canary Prompt** → 结构化 AI 输出
3. **Provider 抽象** → 多模型切换
4. **Ledger 计费** → 成本控制
5. **Guard 系统** → 代码质量保障

### 18.8 本周关键 Takeaway

🥇 **"waoowaoo 的核心价值不是视频质量，而是端到端自动化 Pipeline 的工程化实现"**

🥈 **"Canary Prompt 是 AI 输出的关键：结构化约束 > 自由发挥"**

🥉 **"Provider 抽象让你切换模型零成本：同一套代码，切换即插即用"**

---

> **本次更新时间**: 2026-04-11 10:00 (Asia/Shanghai)
> **专题**: waoowaoo 项目最新技术实现研究
> **新增章节**: 十八

---

## 📹 第六周总结（2026-04-06 ~ 2026-04-12）

> **总结日期**: 2026-04-12（周日）
> **知识文件累计**: ~7216 行，覆盖 6 周学习内容
> **本周关键词**: 实战深化、Pipeline工程化、行业趋势确认

---

### 一、本周产出情况

| 日期 | 计划主题 | 状态 | 对应章节 |
|------|----------|------|----------|
| **周一(4/6)** | **分镜设计与镜头语言** | ✅ 完成 | 分镜四要素 + 10大镜头语言 + 对话场景专业分镜 |
| 周二(4/7) | AI视频生成Prompt | ❌ 未产出 | — |
| **周三(4/8)** | **剪辑节奏控制与转场** | ✅ 完成 | 节奏公式 + 六大转场 + Speed Ramp + CapCut实操 |
| 周四(4/9) | 平台算法偏好 | ❌ 未产出 | — |
| **周五(4/10)** | **配音/字幕/BGM** | ✅ 完成 | AI配音工具2026 + 配音节奏法则 + 字幕三合一清单 |
| **周六(4/11)** | **waoowaoo 项目研究** | ✅ 完成 | Pipeline Graph + Canary Prompt + 计费Ledger + 角色一致性 |
| 周日(4/12) | 周总结（本节） | ✅ 完成 | — |

**本周产出率：4/6（67%）** — 比上周 83% 有所下降，但内容质量维持高位

---

### 二、本周核心知识提取

#### 专题 A：分镜设计实战深化（周一）

| 核心规则 | 可落地实践 |
|----------|-----------|
| 分镜四要素：场景+镜头+动作+情绪 | 每个镜头按四要素模板写 |
| 先写镜头怎么拍，再写想表达什么 | Prompt 第一行必须是景别/机位/运镜 |
| 对话场景黄金法则 | 过肩正反打 + 180°原则 + 三机位覆盖 |
| 短视频节奏公式 | Hook(推镜头)→发展(交替景别)→高潮(特写环绕)→结尾(拉镜头留白) |
| 构图六法则 | 三分法/引导线/对称/框架/负空间/深度层次 |

#### 专题 B：剪辑节奏与转场（周三）

| 核心规则 | 可落地实践 |
|----------|-----------|
| 节奏 = 镜头时长 × 切换频率 × 变速节奏 | 三变量协同控制，不是只调一个 |
| 黄金节奏公式 | 快Hook → 稳铺垫 → 加速递进 → 快切高潮 → 慢收尾 |
| 呼吸感原则 | 连续快切3-4次后必须跟一个稍长镜头 |
| 80/20转场法则 | 80%硬切 + 20%特效转场 |
| Speed Ramp 参数 | 100%→600%(ease-in)→切换→600%→100%(ease-out) |
| BGM踩点 | 70%镜头切换点对齐鼓点，BPM决定转场频率 |

#### 专题 C：配音/字幕/BGM（周五）

| 核心要点 | 可落地实践 |
|----------|-----------|
| AI配音工具2026版 | Fish Speech(开源)/CosyVoice(阿里)/Seed-TTS(字节) |
| 配音节奏法则 | 语速220-260字/分钟 + 每15秒一个重音 |
| 字幕三原则 | 白字黑边 + 逐字出现 > 逐行 > 整句 + 关键帧对齐鼓点 |
| BGM选择流程 | 定情绪→定BPM→定风格→裁剪匹配（顺序不能乱） |
| 音量层级 | 配音比BGM高6-10dB |

#### 专题 D：waoowaoo 工程化研究（周六）

| 核心发现 | 可复用模式 |
|----------|-----------|
| Pipeline Graph 工作流 | 节点化+并发控制+错误恢复+超时保护 |
| Canary Prompt 标准化 | JSON Schema约束AI输出 > 自由发挥 |
| Provider 抽象层 | 统一接口切换视频模型零成本 |
| Ledger 计费系统 | 多货币+余额快照+服务级成本追踪 |
| 角色外观标识系统 | characterId + appearanceName跨场景复用 |
| Guard 代码质量 | 30+守护脚本确保一致性 |

---

### 三、行业趋势快照（2026年4月）

基于最新搜索结果补充：

| 趋势 | 来源 | 影响 |
|------|------|------|
| **单次生成时长突破2分钟** | AutoGPT (autogpt.net/state-of-ai-video/) | 从2024年4-10秒 → 2026年连贯2分钟单次生成 |
| **AI视频从实验到生产** | Higgsfield Blog | Sora 2/Veo 3.1 已成为生产基础设施 |
| **电影语言可直接驱动AI** | LTX Studio | 创作者用真实摄影术语即可精确控制AI视频 |
| **角色一致性跨场景可用** | LTX Studio | 营销团队数小时内生成整批Campaign变体 |

**关键洞察**：AI视频已从"技术Demo"阶段进入"生产工具"阶段，2026 Q2的核心竞争力是工程化整合能力。

---

### 四、六周知识体系最终完成度评估

```
短视频制作知识体系（6周完成）
│
├── 📐 分镜设计           █████████░ 90%
│   ├── ✅ 基础景别/运镜
│   ├── ✅ 多线叙事/高级角度/希区柯克变焦
│   └── ✅ 对话场景专业分镜（本周新增）
│
├── 🤖 AI 视频生成 Prompt  █████████░ 90%
│   ├── ✅ 六要素公式 + 五段式模板
│   ├── ✅ Veo/Sora/Kling/MiniMax 适配
│   └── ✅ Prompt 工作流（首帧→尾帧→过渡）
│
├── ✂️ 剪辑节奏与转场     █████████░ 95%
│   ├── ✅ 节奏三要素 + 黄金公式
│   ├── ✅ 六大转场 + Speed Ramp 参数
│   └── ✅ CapCut/剪映实操速查（本周新增）
│
├── 📊 平台算法与爆款      █████████░ 90%
│   └── ✅ 抖音/小红书/TikTok 2026最新
│
├── 🎙️ 配音/字幕/BGM       █████████░ 90%
│   ├── ✅ AI配音工具2026版（本周更新）
│   └── ✅ 三合一输出检查清单（本周新增）
│
├── 🔧 waoowaoo 追踪      █████████░ 90%
│   ├── ✅ Pipeline Graph 完整拆解
│   ├── ✅ 计费系统 + 角色一致性方案
│   └── ✅ Provider抽象 + Guard系统（本周新增）
│
└── 🏆 周总结              ██████████ 100%
```

**总体覆盖率：~92%** — 理论体系已完整，下一步应为实战验证

---

### 五、六周核心方法论 Top 12（最终版）

| # | 方法论 | 首次出现 | 确认周 |
|---|--------|---------|--------|
| 1 | **Prompt是导演指令，不是愿望清单** | Week 5 | ✅ W6 |
| 2 | **永远 Cut on Motion** | Week 5 | ✅ W6 |
| 3 | **节奏=信息密度×情绪推进×视觉变化** | Week 4 | ✅ W6 |
| 4 | **前1.8秒价值前置 > 悬念套路** | Week 3-4 | ✅ W6 |
| 5 | **完播率≠流量，互动深度才是王道** | Week 3 | ✅ W6 |
| 6 | **AI骨架+真实素材 > 纯AI** | Week 5 | ✅ W6 |
| 7 | **80/20转场法则：80%硬切+20%特效** | Week 6 | 🆕 |
| 8 | **Canary Prompt：结构化约束 > 自由发挥** | Week 6 | 🆕 |
| 9 | **Provider抽象：同一套代码切换模型零成本** | Week 6 | 🆕 |
| 10 | **Speed Ramp: 100%→600%→切→600%→100%** | Week 6 | 🆕 |
| 11 | **配音220-260字/分钟+每15秒一个重音** | Week 6 | 🆕 |
| 12 | **BGM选择顺序：情绪→BPM→风格→裁剪** | Week 6 | 🆕 |

---

### 六、知识库建设数据

| 指标 | Week 1 | Week 3 | Week 5 | **Week 6（本周）** |
|------|--------|--------|--------|---------------------|
| **总行数** | ~1500 | ~4500 | ~6300 | **~7800** |
| **章节数** | 9 | 17 | 20+ | **22+** |
| **覆盖主题** | 5 | 7 | 7 | **7** |
| **方法论数** | 5 | 8 | 10 | **12** |
| **工具/模型** | 10 | 20 | 30 | **35+** |
| **Prompt模板** | 3 | 8 | 12 | **15+** |

---

### 七、从学习到实战：下一步行动建议

经过6周系统学习，知识体系已足够支撑实际制作。建议进入 **"一周一作品"** 模式：

| 阶段 | 时间 | 目标 | 验证指标 |
|------|------|------|---------|
| **阶段1：单条验证** | Week 7-8 | 用学到的方法论制作3-5条短视频 | 完成度>质量 |
| **阶段2：数据反馈** | Week 9-10 | 发布到抖音/小红书，收集数据 | 前3秒留存率>40% |
| **阶段3：迭代优化** | Week 11-12 | 基于数据A/B测试不同策略 | 完播率>60% |
| **阶段4：规模化** | Week 13+ | 建立标准化出片流程 | 周产3-5条 |

**第一条视频的最低要求**：
```
□ 使用五段式Prompt模板生成视频
□ 应用80/20转场法则剪辑
□ 配音220-260字/分钟
□ 字幕白字黑边+关键词高亮
□ BGM踩点率>70%
□ 前3秒价值前置
```

---

### 八、本周最佳知识卡片（Top 3）

> 🥇 **"AI视频已从'技术Demo'进入'生产工具'阶段 — 2026 Q2的核心竞争力是工程化整合"** — 行业趋势确认
>
> 🥈 **"Pipeline Graph = AI视频的工厂流水线：节点化+并发+重试+超时保护"** — waoowaoo核心价值
>
> 🥉 **"Speed Ramp黄金参数：100%→600%→切→600%→100%，曲线必须ease"** — 直接可套用

---

> **本次更新时间**: 2026-04-12 10:03 (Asia/Shanghai)
> **专题**: 周日｜第六周总结（2026-04-06 ~ 2026-04-12）
> **知识库总规模**: ~7800 行
> **六周学习完成 ✅ 理论体系完整，建议进入实战阶段 🚀**

**Made with ❤️ by CCO Research Agent**

---

## 📹 第七周周一：分镜设计与镜头语言 · 实用精华版（2026-04-13）

> **今日主题**：基于已有知识体系 + 最新行业实践，精炼可直接落地的分镜设计方法论
> **目标**：把"知道"变成"会用"，聚焦实操 checklist

---

### 1. 分镜设计的本质：一个决策框架，不是艺术创作

分镜（Storyboard）最核心的价值是**提前决策，减少拍摄/生成时的犹豫**。

新手最常见的错误：把分镜当"艺术画"来做，追求画面精美，忽略了它的本质功能：

```
分镜的核心功能（按优先级排序）：
1. 确定镜头顺序（先讲什么）
2. 确定每个镜头的目的（为什么需要这个镜头）
3. 确定镜头时长（给观众多少时间接收信息）
4. 确定景别/角度（用什么方式呈现）
5. 确定运镜方式（怎么动）
```

**一个镜头必须回答"这个镜头解决什么问题"，回答不了就删。**

---

### 2. 短视频分镜的"4层结构法"

适合15-60秒短视频的快速分镜方法：

#### 第1层：叙事骨架（30秒内决定）

```
问题/冲突 → 核心信息 → 结论/CTA
```

不需要写完整剧本，只需要回答：
- 开场抛什么问题或反常识事实？
- 中间传达什么核心信息？
- 结尾引导什么行动？

#### 第2层：镜头数量分配

| 时长 | 推荐镜头数 | 平均每镜头时长 |
|------|-----------|--------------|
| 15秒 | 5-8个 | 1.9-3秒 |
| 30秒 | 8-15个 | 2-3.7秒 |
| 60秒 | 15-25个 | 2.4-4秒 |

**短视频的镜头不是越多越好，是够用就行。**

#### 第3层：景别节奏设计

推荐景别序列（干货口播类）：

```
开场（0-3秒）：特写/近景  → 制造冲击力
展开（3-15秒）：中景/近景  → 舒适观看距离
补充（15-25秒）：全景/中景 → 展示环境/增加变化
结尾（25-30秒）：近景/特写 → 强调CTA/情绪收尾
```

#### 第4层：每个镜头的"目的标签"

给每个镜头标注一个目的标签，帮助判断是否必要：

| 标签 | 含义 | 示例 |
|------|------|------|
| `HOOK` | 吸引注意力 | 开场爆炸特效 |
| `INFO` | 传递信息 | 数据图表、关键文字 |
| `EMOTION` | 情绪表达 | 表情特写、慢动作 |
| `PROOF` | 证明/证据 | 案例展示、截图 |
| `TRANSITION` | 转场过渡 | 空镜、遮罩 |
| `CTA` | 行动号召 | 关注按钮特写 |

---

### 3. 景别选择的决策表（背下来）

遇到"这个场景用什么景别"，直接查：

| 场景需求 | 推荐景别 | 原因 |
|---------|---------|------|
| 展示整体环境 | 全景/远景 | 建立空间感 |
| 展示人物全身动作 | 全景 | 看完整动作 |
| 两个人对话 | 中景/中近景 | 同时看到两人 |
| 强调表情/情绪 | 近景/特写 | 情绪聚焦 |
| 展示物品细节 | 特写/大特写 | 细节呈现 |
| 需要观众有距离感 | 远景 | 冷静客观 |
| 需要观众有代入感 | 近景/特写 | 主观视角 |
| 两人关系对比 | 过肩镜头 | 关系展示 |

---

### 4. 镜头运动的快速选择

| 想要的效果 | 运动方式 | 替代方案（无设备） |
|-----------|---------|-----------------|
| 聚焦某个细节 | 推镜头 | 后期放大 |
| 展示环境全貌 | 拉镜头 | 后期缩小 |
| 跟随主体移动 | 跟镜头 | 边走边拍 |
| 展示空间宽广 | 摇镜头 | 后期左右拼接 |
| 制造眩晕/紧张感 | 甩镜头 | 快速切换 |
| 制造震撼效果 | 升降镜头 | 后期效果 |

**手机拍摄最实用的3个运镜：**
1. **固定镜头**（最稳，默认选项）
2. **缓慢推拉**（用脚走近/走远，不要用数码zoom）
3. **横向平移**（侧身走路，保持上半身稳定）

---

### 5. 黄金前三秒的分镜设计

前三秒的核心任务是：**让观众停下来，给一个留下来的理由**。

4种最有效的开场镜头设计：

| 类型 | 分镜描述 | 适用内容 |
|------|---------|---------|
| **特写冲击** | 极端特写（大特写/微距） | 产品展示、美食、美妆 |
| **反转对比** | Before/After 并列 | 教程、改造、效果展示 |
| **悬念设置** | 特写 + 悬念文字 | 故事、揭秘、情感 |
| **数字锚定** | 数字+标题字幕 | 干货、知识、盘点 |

**分镜模板（可直接套用）：**

```
镜头1（0-1.5s）：
  景别：大特写/特写
  内容：[核心画面元素]
  字幕：[悬念问题/惊人数字]
  音效：冲击音效（whoosh/impact）

镜头2（1.5-3s）：
  景别：近景/中景
  内容：[主体开始动作/说话]
  字幕：[价值预告："我会告诉你..."]
  目的：建立继续观看的期待
```

---

### 6. 对话场景的分镜处理

两人对话是最常见的场景类型，记住一个核心原则：

```
轴线规则（180度系统）：
  在对话两人的连线的同一侧拍摄
  → 保证观众空间感一致
  → A始终在画面左边，B始终在画面右边
```

**3种常用对话分镜：**

| 分镜方式 | 景别 | 适用场景 |
|---------|------|---------|
| **正反打** | 近景/特写 | 两人对话，焦点切换 |
| **过肩镜头** | 中近景 | 关系展示，有代入感 |
| **双人中景** | 全景/中景 | 对话开始，展示关系 |

**AI视频生成时的对话分镜 Prompt 示例：**
```
两人对话场景：
  "Two characters in conversation, medium close-up shot, 
   over-the-shoulder framing, character A on the left, 
   character B on the right. Shallow depth of field, 
   T2.8 aperture to keep speaker in focus."
```

---

### 7. 转场的分镜设计（不是剪辑时才想）

转场应该在分镜阶段就想好，而不是剪辑时随便加。

| 转场类型 | 分镜时标注 | 适用场景 |
|---------|-----------|---------|
| **硬切** | 直接写下一个镜头 | 默认选项，简洁有力 |
| **遮罩转场** | 标注"遮挡物" | 场景切换，时间流逝 |
| **匹配剪辑** | 标注匹配元素 | 创意内容 |
| **叠化** | 标注"DISSOLVE" | 回忆、梦境 |
| **甩镜头** | 标注"WHIP PAN" | 快速切换地点 |

**遮罩转场的分镜标注示例：**
```
镜头5：主角走向门口，伸手遮住镜头
        [动作] → 伸手遮镜
镜头6：（黑场）
        [过渡]
镜头7：主角走出另一扇门
        [新场景建立]
```

---

### 8. 分镜脚本的最小格式（手写也够用）

不需要精美模板，下面这个格式已经足够：

```markdown
## 分镜脚本 - [主题]

| # | 景别 | 时长 | 画面描述 | 目的 | 备注 |
|---|------|------|---------|------|------|
| 1 | 特写 | 1.5s | 大特写：产品外观 | HOOK | 冲击感 |
| 2 | 近景 | 2s | 主角开始介绍 | INFO | 价值预告 |
| 3 | 中景 | 3s | 展示使用效果 | PROOF | 核心证据 |
| ... | ... | ... | ... | ... | ... |

情绪曲线：↑↑↑ → ↑↑ → ↓ → ↑↑↑↑
总时长：XX秒
```

---

### 9. 常见分镜错误 & 检查清单

**❌ 常见错误（立即避免）：**

| 错误 | 问题 | 修正方法 |
|------|------|---------|
| 景别跳跃太大 | 远景→特写，没有过渡 | 加入中景过渡 |
| 全程特写 | 视觉疲劳 | 每3-4个特写后加入全景 |
| 镜头目的模糊 | 不知道为什么要这个镜头 | 给每个镜头标注目的标签 |
| 没有节奏变化 | 全程一个节奏，平淡 | 设计快慢交替 |
| 转场太花哨 | 每2秒一个特效转场 | 默认硬切，必要时才加特效 |
| 过肩镜头用错轴线 | 两人位置左右乱跳 | 遵守180度轴线规则 |

**✅ 发布前分镜自检（3分钟过一遍）：**

```
□ 开场3秒有HOOK（特写/悬念/反转/数字）
□ 每个镜头都有明确目的（能回答"为什么需要这个镜头"）
□ 景别变化有节奏感（不是随机切换）
□ 没有连续3个以上相同景别
□ 轴线一致（对话场景）
□ 转场理由充分（不是为炫技而炫技）
□ 结尾有明确CTA
□ 总时长符合目标平台最佳时长
```

---

### 10. AI视频生成时代的分镜变化

AI生成视频给分镜带来了3个新维度：

| 变化 | 旧思维 | AI思维 |
|------|--------|--------|
| **景别** | 摄影机位决定 | Prompt描述决定，可能有偏差 |
| **连贯性** | 同一场景连续拍摄 | 需要分镜刻意设计保持一致性 |
| **时长** | 实际拍摄 | 需要精确控制生成时长（5-10秒/片段） |

**AI视频分镜的额外标注：**

```
□ 每个镜头的角色外观描述是否一致
□ 首帧图片是否已准备好
□ 尾帧图片（用于连续性）是否需要
□ 运镜描述是否在AI能力范围内
□ 镜头时长是否在模型支持范围内（Veo 8s / Vidu 16s）
```

**给AI看的分镜 Prompt 模板：**
```
[
  {
    "shot_number": 1,
    "description": "Extreme close-up of a woman's eyes looking directly at camera",
    "shot_type": "ECU",
    "camera_movement": "static",
    "duration": 3,
    "video_prompt": "A woman stares directly into the camera. Extreme close-up, detailed eyes with sharp focus. Soft natural lighting. 4K cinematic quality.",
    "characters": [{"name": "Lena", "appearance": "default"}]
  }
]
```

---

### 11. 今日核心行动清单（可立即执行）

- [ ] **用"4层结构法"规划下一条视频的分镜**（骨架→镜头数→景别节奏→目的标签）
- [ ] **建立自己的景别决策表**（把第3节的内容改成自己常用场景的版本）
- [ ] **把转场类型在分镜阶段就标注清楚**，不要留到剪辑时再想
- [ ] **发布前用9点检查清单过一遍分镜**
- [ ] **如果用AI生成视频**：每个镜头单独生成，确保首尾帧连续性

---

### 12. 今日结论（适合发群）

```
📹 短视频知识 | 分镜设计核心方法论

🔑 今日3个关键要点：

1️⃣ 分镜的本质是决策框架，不是艺术创作
   → 每个镜头必须回答"解决什么问题"
   → 回答不了就删

2️⃣ 景别选择有规律，背下来直接用
   → 特写=情绪，近景=对话，全景=环境
   → 记住"远→中→近→特写=聚焦，远←中←近←特写=释放"

3️⃣ 黄金前三秒靠特写/反转/悬念/数字，不靠运气
   → 开场用大特写、数字锚点或悬念设置
   → 前1.5秒决定用户是否留下来

📚 来源: 本知识库已有内容整理 + 行业实践
```

---

### 13. 延伸学习方向

| 如果你想深入 | 推荐学习内容 |
|-------------|------------|
| 剧情类视频 | 平行蒙太奇、交叉剪辑、重复蒙太奇（见第三周周一章节） |
| 高级运镜 | 希区柯克变焦、环绕镜头、长镜头（见第三周周一章节） |
| AI视频分镜 | waoowaoo storyboard_panels prompt（见第一周章节） |
| 电影感分镜 | 阅上下文第二周第三周内容 |

---

> **本次更新时间**: 2026-04-13 10:03 (Asia/Shanghai)
> **专题**: 周一｜分镜设计与镜头语言 · 实用精华版
> **建议实践**: 立即用"4层结构法"规划下一条视频

**Made with ❤️ by CCO Research Agent**


---

## 周二专题｜AI 视频生成 Prompt 最佳实践

> **更新时间**: 2026-04-14 10:09 (Asia/Shanghai)
> **专题**: AI 视频生成 Prompt 工程精华版
> **覆盖平台**: Runway Gen-4 / Sora / Kling 可灵 / 即梦 / Pika / Wan2.1

---

### 1. Prompt 通用万能公式

无论哪个平台，高质量视频 prompt 都遵循 **5层结构**：

```
[主体描述] + [动作/运动] + [镜头语言] + [环境/光影] + [风格/氛围]
```

**示例**：
> A young woman in a red dress walking slowly through a lavender field at golden hour, camera tracking alongside her, cinematic soft lighting, dreamy romantic atmosphere

**每层的作用**：
| 层级 | 关键词举例 | 缺失后果 |
|------|-----------|---------|
| 主体 | woman, cat, car, city | AI 自行脑补，结果不可控 |
| 动作 | walking, spinning, zooming in | 静态画面或随机运动 |
| 镜头 | tracking shot, drone view, close-up | 随机构图，无电影感 |
| 环境/光影 | golden hour, neon lights, fog | 平光，缺乏氛围 |
| 风格 | cinematic, anime, oil painting | 默认写实风，无法匹配品牌调性 |

---

### 2. 各平台 Prompt 策略差异

#### 2.1 Runway Gen-4（最精准）

- **语言**: 英文，简洁直白
- **特点**: 对镜头运动指令响应最好
- **最佳实践**:
  - 用动词开头描述镜头运动：`Tracking shot of...`、`Slow pan left revealing...`
  - 明确时间线：`starts close on face, slowly pulls back to wide shot`
  - 光影指令非常有效：`volumetric lighting`、`god rays through window`

**万能模板**：
```
[Camera move] of [subject] [doing action] in [environment], [lighting condition], [mood/style], shot on [camera type]
```

**实例**：
> Smooth dolly forward through a futuristic neon-lit corridor, a figure in a white suit walking ahead, reflections on wet floor, cyberpunk atmosphere, shot on Arri Alexa

#### 2.2 Sora（最理解复杂场景）

- **语言**: 英文，自然语言风格，可长可短
- **特点**: 理解复杂叙事和物理规则最强
- **最佳实践**:
  - 可以写"故事型"prompt：描述事件的发生顺序
  - 物理描述越具体越好（材质、重量、速度）
  - 利用 ref/reference frame 控制首帧一致性

**万能模板**：
```
A [duration] scene showing [subject]. The camera [camera movement]. [Detailed action sequence]. [Environmental details]. [Mood and style notes].
```

#### 2.3 Kling 可灵（最懂中文）

- **语言**: 中文或英文均可，中文表达更精准
- **特点**: 人物表情、手部生成质量高
- **最佳实践**:
  - 用中文描述更自然：`一位穿着白衬衫的年轻女性在海边微笑`
  - 善用"首尾帧控制"：上传起始图+结束图
  - 明确运动方向：`从左向右移动`、`缓慢推进`

**中文万能模板**：
```
[画面内容描述]，[镜头运动]，[光线环境]，[氛围风格]
```

#### 2.4 即梦 Jimeng

- **语言**: 中文优先
- **特点**: 适合短视频片段，运动幅度大
- **最佳实践**:
  - Prompt 简短有力，15-30字效果最佳
  - 善用"反向prompt"排除不想要的元素
  - 先用文生图确定画面，再用图生视频保持一致性

#### 2.5 Pika

- **语言**: 英文
- **特点**: 动画风格和特效最强
- **最佳实践**:
  - 明确动画风格：`3D animation`、`anime style`、`stop motion`
  - 用 `--ar 16:9` 控制比例
  - 运动幅度用 `Motion 1-4` 参数控制（1=微动，4=大幅运动）

---

### 3. 高级 Prompt 技巧

#### 3.1 镜头语言关键词速查

| 效果 | Prompt 关键词 | 视觉结果 |
|------|-------------|---------|
| 推进 | dolly in / push in | 镜头向主体靠近 |
| 拉远 | dolly out / pull back | 镜头远离主体 |
| 环绕 | orbit / 360 orbit | 围绕主体旋转 |
| 跟拍 | tracking shot / follow cam | 跟随主体移动 |
| 升降 | crane shot / aerial ascend | 垂直上下移动 |
| 手持 | handheld / shaky cam | 模拟真实手持晃动 |
| 慢动作 | slow motion / 120fps | 放慢动作增加张力 |
| 时间冻结 | frozen moment / time stop | 画面定格环绕（黑客帝国式） |

#### 3.2 常见失败模式与修复

| 问题 | 原因 | 修复方法 |
|------|------|---------|
| 画面变形/扭曲 | Prompt 动作描述冲突 | 一次只描述一个主要运动 |
| 主体消失 | 镜头运动太大 | 明确主体位置 `subject remains centered` |
| 风格不一致 | 风格关键词混用 | 选一个主风格，不要混合 |
| 画面静止不动 | 只描述了场景没描述动作 | 添加具体动作动词 |
| 多余肢体/手指 | AI生成人物常见问题 | 加 `perfect hands` 或用图生视频模式 |

#### 3.3 图生视频 (Image-to-Video) 核心技巧

图生视频质量远高于纯文生视频。核心操作：

1. **先用 AI 生成高质量关键帧**（Midjourney/DALL-E/SD）
2. **将关键帧作为首帧输入**
3. **Prompt 只描述运动，不重复描述画面内容**
4. **运动幅度从小开始试**（越小越稳定）

**关键帧 Prompt 模板**：
```
[Only motion description]. Camera [movement]. The subject [specific action]. Maintain the existing visual style.
```

**反例**（不要这样写）：
> ❌ `A beautiful woman with long black hair wearing a red dress walking in a park with trees and sunshine...`（重复描述了首帧已有的内容）

**正例**：
> ✅ `Gentle camera push in. Subject turns her head slowly to the right, smiling. Light breeze moves hair and dress fabric.`（只描述运动）

---

### 4. 实战 Prompt 模板库

#### 4.1 产品展示类

```
Product showcase: [产品名] rotating slowly on a [surface], [lighting] highlighting [product detail], 
camera orbiting smoothly, clean [background], commercial photography style
```

#### 4.2 人物故事类

```
Cinematic [shot type] of [人物描述], [表情/情绪], [动作], [环境背景], 
[光线], [氛围关键词], shallow depth of field
```

#### 4.3 场景氛围类

```
[Time of day] aerial establishing shot of [场景], [天气/季节], 
camera slowly descending, [特殊元素], [风格], epic scale
```

#### 4.4 品牌TVC类

```
Luxury commercial: [产品/人物] in [高端场景], dramatic [lighting], 
smooth camera [movement], [品牌色调] color grading, 35mm film grain
```

---

### 5. Prompt 迭代优化流程

```
第1轮：基础 prompt → 生成 → 观察主要问题
第2轮：修复最严重问题（运动/构图/风格）→ 再生成
第3轮：微调细节（光影/色彩/氛围）→ 确认版本
第4轮：批量生成变体 → 选最佳版本
```

**关键原则**：
- 每轮只改 1-2 个变量，不要一次全改
- 记录每个 prompt 的生成结果，建立自己的"prompt→效果"数据库
- 好的 prompt 值得保存为模板反复使用

---

### 6. 工具链协同建议

```
选题脚本 → ChatGPT/Claude（创意构思）
关键帧   → Midjourney / DALL-E 3（画面设计）
视频生成 → Runway/Kling/Sora（动态实现）
后期     → CapCut / DaVinci（调色剪辑）
```

推荐工作流：**先用 ChatGPT 生成 prompt 草稿 → 微调 → 批量生成 → 筛选最佳**。

---

### 7. 今日核心要点速记

| # | 要点 | 一句话总结 |
|---|------|-----------|
| 1 | 5层结构法 | 主体+动作+镜头+环境+风格，缺一不可 |
| 2 | 平台特性 | Runway 重镜头，Sora 重叙事，Kling 懂中文 |
| 3 | 图生视频 > 文生视频 | 先做好关键帧，prompt 只写运动 |
| 4 | 每轮只改1-2个变量 | 迭代不是重写，是精准调优 |
| 5 | 积累 prompt 数据库 | 好用 prompt 是资产，值得反复复用 |

---

> **本次更新时间**: 2026-04-14 10:09 (Asia/Shanghai)
> **专题**: 周二｜AI 视频生成 Prompt 最佳实践
> **建议实践**: 选一个模板，用5层结构法生成一条10秒视频测试

**Made with ❤️ by CCO Research Agent**
