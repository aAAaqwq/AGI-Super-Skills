# 第1轮：基础提示词结构与语法

> 学习时间：2026-03-21 05:00 - 05:40
> 主题：基础提示词结构与语法

---

## 1.1 提示词核心原则

### 黄金法则

| 原则 | 说明 | 示例 |
|------|------|------|
| **具体化** | 越具体越好 | ❌ "dog" → ✅ "golden retriever playing fetch in autumn park" |
| **顺序重要** | 前面词权重更高 | "red car" vs "car, red" (前者更强调红色) |
| **用词简洁** | 避免冗余描述 | 直接说 "sunset" 而非 "the sun is setting" |
| **英文优先** | 多数模型英文理解更好 | 尤其 Midjourney/SD |

### 提示词结构公式

```
[主体] + [环境] + [风格] + [构图] + [光照] + [参数]
```

---

## 1.2 主流生图模型提示词特点

### Midjourney

**语法特点：**
- 关键词用逗号分隔
- 支持 `--ar 16:9` 参数
- 支持 `--v 6` 版本指定
- 支持 `--iw 0.5` 图像权重
- 支持 `::` 权重语法

**示例：**
```
A majestic lion in African savanna, golden hour lighting, cinematic composition, National Geographic style --ar 16:9 --v 6 --stylize 1000
```

### DALL-E 3

**语法特点：**
- 自然语言描述
- 对长提示词支持更好
- 不支持参数语法
- 更擅长理解复杂场景

**示例：**
```
A minimalist Japanese garden with a red bridge over a koi pond, bamboo fence, cherry blossoms falling, early morning mist, zen atmosphere, soft natural lighting
```

### Stable Diffusion / Flux

**语法特点：**
- 标签/关键词系统
- 支持 LORA/embedding
- 强大的控制能力
- 权重语法：`keyword:1.5` 增强，`keyword:0.5` 减弱

**示例：**
```
masterpiece, best quality, 1girl, solo, long hair, smile, outdoor, sunset, golden hour lighting, volumetric lighting, detailed clothes, intricate details, highly detailed
```

### Google Gemini / Imagen

**语法特点：**
- 自然语言友好
- 长上下文理解能力强
- 指令跟随能力强

---

## 1.3 关键词分类模板

### 主体 (Subject)

| 类别 | 关键词 |
|------|--------|
| 人物 | portrait, full body, 1girl, 1boy, group |
| 动物 | cat, dog, bird, wildlife |
| 物品 | product, sculpture, furniture |
| 场景 | landscape, cityscape, interior |

### 环境 (Environment)

| 类别 | 关键词 |
|------|--------|
| 地点 | forest, beach, mountain, urban, studio |
| 时间 | golden hour, blue hour, night, day |
| 天气 | sunny, rainy, foggy, snowy |

### 风格 (Style)

| 类别 | 关键词 |
|------|--------|
| 艺术风格 | oil painting, watercolor, anime, photorealistic |
| 时代风格 | vintage, retro, modern, futuristic |
| 摄影师风格 | National Geographic, Ansel Adams |
| 设计风格 | minimalist, maximalist, brutalist |

### 构图 (Composition)

| 关键词 | 说明 |
|--------|------|
| wide shot | 广角/全景 |
| close-up | 特写 |
| medium shot | 中景 |
| bird's eye view | 鸟瞰 |
| worm's eye view | 仰视 |
| centered | 居中 |
| rule of thirds | 三分法 |

### 光照 (Lighting)

| 关键词 | 说明 |
|--------|------|
| cinematic lighting | 电影光照 |
| volumetric lighting | 体积光 |
| golden hour | 黄金时刻 |
| soft lighting | 柔和光照 |
| rim light | 轮廓光 |
| backlight | 背光 |
| studio lighting | 工作室光照 |

### 质量修饰词

```
masterpiece, best quality, high quality, detailed, intricate,
ultra detailed, 8k, 4k, photorealistic, RAW photo
```

---

## 1.4 实践练习

### 练习1：优化基础提示词

**原始：** "a cat"

**优化版本：**
```
orange tabby cat, fluffy fur, green eyes, sitting on windowsill, soft morning light, cozy home atmosphere, photorealistic, detailed fur texture --ar 3:4
```

### 练习2：产品摄影提示词

**要求：** 智能手表产品图

**优化版本：**
```
smart watch on marble pedestal, product photography, studio lighting, clean background, reflections, high-end tech gadget, Apple style, 8k, detailed --ar 1:1
```

### 练习3：风格迁移

**要求：** 梵高风格的星空小镇

**优化版本：**
```
starry night over small town, Vincent van Gogh style, swirling brushstrokes, bold colors, post-impressionist, oil painting texture, Starry Night inspired --ar 16:9
```

---

## 1.5 本轮小结

**核心要点：**
1. 提示词顺序影响权重，越前面的词越重要
2. 具体化 > 模糊描述
3. 英文提示词效果通常更好
4. 使用质量修饰词提升细节
5. 风格关键词决定整体基调

**下一步：**
- 第2轮将深入学习风格、构图、光影控制的专业术语
- 了解不同模型的参数语法
- 掌握中英文提示词转换技巧

---

## 参考工具

- relay-image-gen: `~/.openclaw/skills/relay-image-gen/`
- 支持模型：boluobao, Gemini, DALL-E 3, GPT-image-1, Imagen-4
