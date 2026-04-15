# 第3轮：视频生成专属技巧

> 学习时间：2026-03-21 06:20 - 07:00
> 主题：视频生成专属技巧（运镜、时间、节奏）

---

## 3.1 视频生成模型概述

### 主流视频生成模型

| 模型 | 提供商 | 特点 | 适用场景 |
|------|--------|------|----------|
| Kling | 快手可灵 | 物理真实感强 | 电影感、复杂运动 |
| Veo 3 | Google | 语义理解强 | 创意广告、动画 |
| Sora | OpenAI | 世界模拟 | 长视频、复杂场景 |
| Runway | Runway | 编辑能力强 | 视频编辑、风格化 |
| Pika | Pika Labs | 快速生成 | 社交媒体短视频 |
| Luma Dream Machine | Luma | 照片转视频 | 产品展示 |

### relay-video-gen 支持的模型

```
优先级：Gemini Veo 3.1 → Kling → Veo 3.1 → MiniMax Video → Grok Video
```

---

## 3.2 视频提示词核心要素

### 视频提示词公式

```
[主体] + [动作/运动] + [环境] + [时间/节奏] + [运镜] + [风格]
```

### 与静态图的关键区别

| 静态图 | 视频 |
|--------|------|
| 单一画面 | 时间维度 |
| 构图固定 | 运镜运动 |
| 光照稳定 | 光影变化 |
| 瞬间捕捉 | 过程展现 |

---

## 3.3 运镜专业术语

### 相机运动

| 术语 | 英文 | 说明 |
|------|------|------|
| 推轨 | Dolly | 前后移动 |
| 变焦 | Zoom | 缩放变化 |
| 摇镜 | Pan | 左右摇动 |
| 俯仰 | Tilt | 上下摇动 |
| 跟随 | Follow | 跟随主体 |
| 环绕 | Orbit/Circle | 绕主体旋转 |
| 升降 | Crane | 升降运动 |
| 手持 | Handheld | 轻微晃动 |
| 稳定 | Stable | 稳定画面 |

### 运动关键词

| 术语 | 说明 |
|------|------|
| Floating | 漂浮感 |
| Drifting | 漂移感 |
| Spinning | 旋转 |
| Rising | 上升 |
| Falling | 下降 |
| Flowing | 流动 |
| Dancing | 舞动 |
| Gliding | 滑行 |
| Soaring | 翱翔 |
| Submerged | 沉浸 |

---

## 3.4 时间与节奏控制

### 时间长度描述

| 术语 | 说明 |
|------|------|
| Shot duration | 镜头持续时间 |
| Quick cuts | 快速切换 |
| Slow motion | 慢动作 |
| Time-lapse | 延时摄影 |
| Real-time | 实时 |

### 节奏描述

| 术语 | 说明 |
|------|------|
| Energetic | 充满能量 |
| Calm | 平静 |
| Dramatic | 戏剧性 |
| Peaceful | 和平 |
| Tension | 紧张感 |
| Flowing | 流畅 |
| Rhythmic | 有节奏的 |
| Hypnotic | 催眠感 |

### 动态描述词

| 英文 | 中文 | 示例 |
|------|------|------|
| Gently swaying | 轻轻摇曳 | 树叶、花朵 |
| Cascading | 倾泻 | 水流、瀑布 |
| Swirling | 旋转流动 | 烟雾、云层 |
| Pulsating | 脉动 | 灯光、能量 |
| Rippling | 涟漪 | 水面、布料 |
| Surging | 涌动的 | 海浪、人群 |
| Drifting | 飘荡 | 气球、羽毛 |

---

## 3.5 视频风格与氛围

### 电影风格

| 术语 | 说明 |
|------|------|
| Cinematic | 电影感 |
| Shot on 35mm | 35mm胶片感 |
| Film grain | 胶片颗粒 |
| Movie scene | 电影场景 |
| Blockbuster | 大片风格 |
| Indie film | 独立电影风格 |

### 特殊效果

| 术语 | 说明 |
|------|------|
| Motion blur | 运动模糊 |
| Light trails | 光轨 |
| Particles | 粒子效果 |
| Smoke effects | 烟雾效果 |
| Fire effects | 火焰效果 |
| Water effects | 水效 |
| Dust particles | 尘埃粒子 |

---

## 3.6 视频提示词实战

### 示例1：产品展示

**需求：** 智能手机旋转展示

**提示词：**
```
smartphone floating in void, slowly rotating 360 degrees, sleek design, premium materials, subtle reflections, studio lighting, product showcase, smooth motion, cinematic lighting, commercial advertising --duration 5 --aspect 1:1
```

### 示例2：自然风景

**需求：** 日出云海

**提示词：**
```
sunrise over mountain range, time-lapse clouds flowing across peaks, golden light breaking through, volumetric god rays, epic landscape, drone view, nature documentary, 8k --duration 8 --aspect 16:9
```

### 示例3：人物动作

**需求：** 舞者优雅舞动

**提示词：**
```
professional dancer performing contemporary dance, graceful movements, flowing fabric, dramatic lighting, spotlight, dark stage, artistic expression, emotional performance, slow motion --duration 6 --aspect 9:16
```

### 示例4：科技感开场

**需求：** 科技产品展示视频

**提示词：**
```
futuristic device powering on, holographic interface glowing to life, neon light trails, cyberpunk aesthetic, particle effects, sleek metallic surface, close-up detail shots, cinematic intro --duration 5 --aspect 16:9
```

---

## 3.7 视频参数控制

### relay-video-gen 参数

| 参数 | 说明 | 范围 |
|------|------|------|
| -p | 提示词 | 必需 |
| -f | 输出文件 | 必需 |
| -d | 持续时间 | 3-15秒 |
| -a | 宽高比 | 16:9, 9:16, 1:1 |
| -m | 模型 | kling-video, veo3.1 |
| -P | 提供商 | xingjiabi |

### 常用参数组合

```bash
# 短视频（社交媒体）
-d 5 -a 9:16

# 电影感长镜头
-d 10 -a 16:9

# 产品展示
-d 8 -a 1:1
```

---

## 3.8 本轮小结

**核心要点：**
1. 视频提示词需要包含时间维度（运动、变化）
2. 运镜术语控制相机运动
3. 节奏和动态描述词影响整体氛围
4. 视频模型对物理真实性要求更高
5. 短时长需要更精准的描述

**下一步：**
- 第4轮将学习高级技巧
- 负面提示词、权重控制、混合风格
- 中英文转换技巧

---

## 参考工具

- relay-video-gen: `~/.openclaw/skills/relay-video-gen/`
- Kling 官方文档
- Google Veo 3.1 最佳实践
