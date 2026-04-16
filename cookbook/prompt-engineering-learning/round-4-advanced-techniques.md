# 第4轮：高级技巧

> 学习时间：2026-03-21 07:00 - 07:40
> 主题：负面提示词、权重控制、混合风格

---

## 4.1 负面提示词 (Negative Prompt)

### 适用模型

| 模型 | 支持情况 |
|------|----------|
| Stable Diffusion | ✅ 完整支持 |
| Midjourney | ✅ 支持 (--no 参数) |
| DALL-E 3 | ❌ 不支持 |
| Flux | ✅ 支持 |
| Kling/Veo (视频) | ⚠️ 有限支持 |

### 常见负面提示词模板

#### 通用负面词

```
lowres, bad anatomy, bad hands, text, error, missing fingers, 
extra digit, fewer digits, cropped, worst quality, low quality, 
normal quality, jpeg artifacts, signature, watermark, username, blurry
```

#### 人物专用

```
ugly, deformed, disfigured, mutation, mutated, 
poorly drawn face, poorly drawn hands, 
missing limb, floating limbs, disconnected limbs, 
out of frame, extra limbs, bad proportions, 
gross proportions, malformed limbs
```

#### 画质提升

```
blur, haze, deformed, extra limbs, close up, 
cropped, out of frame, poorly drawn face, 
poorly drawn hands, missing fingers, 
underexposed, overexposed, wrong settings
```

#### 风格去除

```
anime, cartoon, 3d render, artificial, synthetic
```

### Midjourney 负面提示词语法

```
--no <元素>   # 排除指定元素
```

**示例：**
```
a peaceful garden --no people cars buildings
```

### Stable Diffusion 权重语法

```
(关键词:权重)   # 增强或减弱
```

**示例：**
```
(blue eyes:1.3)      # 增强蓝色眼睛
(background:0.5)     # 减弱背景
((red)):2.0          # 双括号增强2倍
```

---

## 4.2 权重控制语法

### Midjourney 权重系统

| 语法 | 说明 | 示例 |
|------|------|------|
| `::` | 分隔词组 | `cat::dog` |
| `::权重` | 调整权重 | `cat::0.5` |
| `++` | 增强 | `cat++` = `cat::1.2` |
| `--iw` | 图像权重 | `--iw 0.5` |

### Stable Diffusion 权重系统

| 语法 | 说明 |
|------|------|
| `(word)` | 权重 1.1 |
| `(word:1.5)` | 权重 1.5 |
| `[word]` | 权重 0.9 |
| `word` | 权重 1.0 |

### Flux 权重系统

类似 SD，支持 `(word:weight)` 语法

### 权重最佳实践

1. **避免过高权重**：超过 1.5 可能导致畸变
2. **组合使用**：多个中等权重 > 单个极高权重
3. **测试迭代**：权重效果因模型而异

---

## 4.3 混合风格技巧

### 风格融合

**方法1：直接组合**

```
oil painting style + cyberpunk aesthetic + Japanese anime
```

**方法2：艺术家混合**

```
portrait in style of Rembrandt + Pixar 3D rendering
```

**方法3：时代混合**

```
1920s Art Deco design + modern minimalist aesthetic
```

### 风格参考表

| 基础风格 | 可混合风格 | 效果 |
|----------|------------|------|
| photorealistic | anime | 二次元真人感 |
| 3D render | watercolor | 3D水彩风 |
| vintage | cyberpunk | 复古赛博 |
| oil painting | digital | 数字油画 |

### Midjourney 风格参数

| 参数 | 说明 |
|------|------|
| `--s <value>` | Stylize (0-1000) |
| `--style <name>` | 指定风格 |
| `--prefer <option>` | 预设风格 |

---

## 4.4 中英文提示词转换

### 转换原则

1. **核心词翻译**：保留关键描述
2. **术语对照**：使用国际通用术语
3. **结构调整**：英文习惯顺序

### 高频转换对照

| 中文 | 英文 |
|------|------|
| 电影感 | cinematic |
| 电影级 | film-grade, movie-quality |
| 摄影级 | photography-level |
| 高清 | high definition, HD |
| 超高清 | ultra HD, 4K, 8K |
| 逼真 | realistic, photorealistic |
| 细节丰富 | detailed, intricate details |
| 氛围感 | atmospheric, moody |
| 柔和 | soft, gentle |
| 强烈 | intense, dramatic |
| 暖色调 | warm tone, warm colors |
| 冷色调 | cool tone, cool colors |
| 背景虚化 | bokeh, background blur |
| 特写 | close-up, close-up shot |
| 远景 | wide shot, long shot |
| 逆光 | backlit, against the light |
| 自然光 | natural lighting |
| 人像 | portrait, portraiture |
| 侧面 | side view, profile |
| 正面 | front view, frontal |
| 侧面光 | side lighting |
| 眼神光 | eye light |

### 转换示例

**中文：**
```
一位美丽的亚洲女孩，长发飘逸，穿白色连衣裙，在樱花盛开的公园里，阳光明媚，微风吹拂，梦幻氛围，动漫风格
```

**英文优化：**
```
beautiful Asian woman, long flowing hair, white dress, cherry blossom park, sunny day, gentle breeze, dreamy atmosphere, anime style, soft lighting, bokeh background --ar 3:4 --v 6
```

---

## 4.5 高级组合示例

### 示例1：高品质人像

**提示词：**
```
masterpiece, best quality, ultra detailed, 8k, professional portrait photography, young woman, glowing skin, detailed eyes, soft natural lighting, rim light, shallow depth of field, bokeh, cinematic color grading, Film simulation, Kodak Portra 400, (bad anatomy:0.6), (deformed:0.6), (ugly:0.6) --ar 3:4 --v 6
```

### 示例2：复杂场景合成

**提示词：**
```
epic fantasy landscape, floating islands, ancient castle, massive waterfall, dramatic sky with volumetric clouds, golden hour lighting, rays of light through clouds, mist, rainbow, concept art, matte painting, (clouds:1.3), (waterfall:1.2), --no text watermark signature --ar 16:9 --v 6
```

### 示例3：产品+风格

**提示词：**
```
luxury perfume bottle, crystal clear glass, golden liquid inside, floating petals, rose petals, elegant luxury brand aesthetic, high-end product photography, soft studio lighting, dramatic shadows, diamond sparkles, reflections on marble, (reflections:1.4), (luxury:1.3), (elegant:1.2), --ar 1:1 --v 6
```

### 示例4：视频+静态提示词增强

**提示词：**
```
dynamic superhero landing, dramatic pose, cape flowing from wind,肌肉感, intense expression, cinematic lighting, god rays, particle effects, motion blur, comic book style, Marvel movie poster aesthetic, poster frame, --ar 2:3 --v 6
```

---

## 4.6 本轮小结

**核心要点：**
1. 负面提示词是质量提升关键
2. 权重控制需要精确调整
3. 风格混合需要理解风格兼容性
4. 英文提示词效果通常更好
5. 转换时保留核心术语

**下一步：**
- 第5轮将进行实战案例拆解
- 最佳实践汇总
- 实际案例对比分析
