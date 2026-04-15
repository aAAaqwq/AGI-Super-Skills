# 第5轮：实战案例拆解与最佳实践

> 学习时间：2026-03-21 07:40 - 08:20
> 主题：实战案例拆解与最佳实践汇总

---

## 5.1 案例1：小红书封面图

### 需求分析

- 平台：小红书
- 尺寸：9:16 (竖版)
- 风格：现代、简洁、吸引眼球
- 受众：年轻女性

### 原始提示词

```
a beautiful girl
```

### 优化过程

**Step 1: 添加主体细节**
```
a beautiful young Asian woman, clear skin, natural makeup, confident smile
```

**Step 2: 添加环境和风格**
```
a beautiful young Asian woman, clear skin, natural makeup, confident smile, standing in modern coffee shop, minimalist interior, warm ambient lighting
```

**Step 3: 添加构图和画质**
```
a beautiful young Asian woman, clear skin, natural makeup, confident smile, standing in modern coffee shop, minimalist interior, warm ambient lighting, centered composition, shallow depth of field, bokeh background --ar 9:16
```

**Step 4: 添加质量修饰词**
```
masterpiece, best quality, ultra detailed, professional portrait photography, beautiful young Asian woman, clear glowing skin, natural makeup, confident smile, standing in modern coffee shop, minimalist interior, warm ambient lighting, soft window light, centered composition, shallow depth of field, bokeh background, cinematic color grading --ar 9:16 --v 6
```

### 最终版本

```
masterpiece, best quality, ultra detailed, 8k, professional portrait photography, beautiful young Asian woman, clear glowing skin, delicate facial features, natural makeup, confident smile, glossy lips, long black hair, standing in modern minimalist coffee shop, warm ambient lighting, soft golden hour light from window, centered composition, shallow depth of field, bokeh background, cinematic color grading, warm tones, (bad anatomy:0.6), (deformed:0.6), (ugly:0.6), (extra limbs:0.5) --ar 9:16 --v 6 --stylize 750
```

---

## 5.2 案例2：电商产品图

### 需求分析

- 产品：无线蓝牙耳机
- 场景：电商主图
- 风格：高端、科技感

### 优化过程

**基础版：**
```
wireless earbuds
```

**进阶版：**
```
premium wireless earbuds, sleek design, matte black finish, product photography, studio lighting, white background --ar 1:1
```

**专业版：**
```
masterpiece, best quality, product photography, premium wireless earbuds, sleek minimalist design, matte black finish, subtle metallic accents, studio lighting setup, key light with softbox, fill light, rim light, clean white background, reflections on glass surface, commercial advertising style, Apple aesthetic, high-end tech gadget --ar 1:1 --v 6
```

### 最终版本

```
ultra realistic product shot, premium wireless earbuds, sleek modern design, matte black finish with silver accents, high gloss charging case, studio lighting, three-point lighting setup, professional commercial photography, clean white background, subtle reflections, sharp focus on product details, commercial advertising, tech product showcase, Apple Sony Bose quality, 8k resolution, (case:1.2), (earbuds:1.1), --no shadow reflection person hands --ar 1:1 --v 6
```

---

## 5.3 案例3：社交媒体视频

### 需求分析

- 平台：抖音/Instagram Reels
- 内容：城市航拍
- 时长：5秒
- 风格：大气、震撼

### 提示词构建

**版本1：**
```
city aerial view
```

**版本2：**
```
aerial view of modern city at sunset, drone footage, golden hour
```

**版本3：**
```
cinematic drone aerial shot, modern city skyline at golden hour, warm orange and purple sky, buildings reflecting sunset light, cinematic motion, smooth drone movement forward, epic landscape, urban atmosphere --duration 5 --aspect 9:16
```

### 最终版本

```
cinematic drone aerial footage, modern metropolis skyline at golden hour, warm sunset sky with clouds, orange purple gradient, buildings silhouette, city lights starting to glow, epic scale, cinematic wideshot, smooth forward drone movement, atmospheric perspective, god rays breaking through clouds, epic landscape photography, national geographic style, movie scene, high budget production, 35mm film look, motion blur, time-lapse elements --duration 5 --aspect 9:16
```

---

## 5.4 案例4：品牌海报

### 需求分析

- 品牌：运动品牌
- 风格：活力、动感
- 用途：户外广告

### 提示词构建

**基础：**
```
running shoes
```

**进阶：**
```
running shoes on road, action shot, motion blur, dynamic angle
```

**专业版：**
```
epic action sports photography, premium running shoes in mid-stride, dynamic motion blur, wet road surface with reflections, urban city background at night, neon city lights, dramatic sports lighting, Nike Adidas Puma level advertising, high-speed motion capture, kinetic energy, power and movement, ultra detailed --ar 16:9 --v 6
```

### 最终版本

```
award winning sports advertisement, professional athlete running shoes in action, mid-stride dynamic pose, dramatic motion blur, wet asphalt reflecting city lights, rainy urban night street, cyberpunk neon aesthetics, blue and orange color palette, dramatic rim lighting from streetlights, cinematic action photography, extreme sports magazine cover, ultra high definition, 8k commercial photography, (motion blur:1.3), (reflections:1.2), (neon:1.1), --ar 16:9 --v 6 --stylize 1000
```

---

## 5.5 最佳实践汇总

### 提示词黄金公式

```
[质量词] + [主体] + [细节] + [环境] + [风格] + [构图] + [光照] + [参数]
```

### TOP 10 质量修饰词

1. `masterpiece` - 杰作级
2. `best quality` - 最佳质量
3. `ultra detailed` - 超细节
4. `highly detailed` - 高度细节
5. `8k` / `4k` - 超高清
6. `photorealistic` - 照片级真实
7. `professional` - 专业级
8. `cinematic` - 电影感
9. `intricate details` - 复杂细节
10. `sharp focus` - 锐利对焦

### TOP 10 构图术语

1. `centered composition` - 居中构图
2. `rule of thirds` - 三分法
3. `close-up` - 特写
4. `wide shot` - 广角
5. `bird's eye view` - 鸟瞰
6. `low angle` - 仰视
7. `depth of field` - 景深
8. `bokeh` - 散景
9. `symmetry` - 对称
10. `leading lines` - 引导线

### TOP 10 光照术语

1. `cinematic lighting` - 电影光照
2. `soft lighting` - 柔光
3. `golden hour` - 黄金时刻
4. `rim light` - 轮廓光
5. `volumetric lighting` - 体积光
6. `studio lighting` - 工作室光
7. `natural light` - 自然光
8. `dramatic lighting` - 戏剧光
9. `backlight` - 背光
10. `key light` - 主光

### 负面提示词模板

**基础版：**
```
low quality, worst quality, blurry, jpeg artifacts
```

**进阶版：**
```
lowres, bad anatomy, bad hands, text, error, missing fingers, 
extra digit, fewer digits, cropped, worst quality, 
low quality, normal quality, jpeg artifacts, signature, 
watermark, username, blurry, ugly, deformed
```

**专业版：**
```
lowres, bad anatomy, bad hands, text, error, missing fingers, 
extra digit, fewer digits, cropped, worst quality, 
low quality, normal quality, jpeg artifacts, signature, 
watermark, username, blurry, ugly, deformed, disfigured, 
mutation, mutated, poorly drawn face, poorly drawn hands, 
missing limb, floating limbs, disconnected limbs, 
out of frame, extra limbs, bad proportions, 
gross proportions, malformed limbs, duplicate
```

---

## 5.6 模型特定技巧

### Midjourney 技巧

- 使用 `--ar` 参数控制比例
- 使用 `--v` 选择版本
- 使用 `--no` 排除元素
- 使用 `::` 权重语法
- 使用 `--iw` 控制图像权重

### Stable Diffusion 技巧

- 使用 LORA 强化特定风格
- 使用 embedding 注入概念
- 使用 ControlNet 控制构图
- 使用 LoRA 权重 `(lora_name:0.8)`
- 负面提示词非常重要

### DALL-E 3 技巧

- 使用自然语言描述
- 提示词越长越好
- 不支持负面提示词
- 通过调整 ChatGPT 对话优化

### Kling/Veo 视频技巧

- 描述动作和运动
- 包含时间元素
- 指定运镜方式
- 控制时长和节奏
- 使用 `--duration` 参数

---

## 5.7 本轮小结

**5轮学习总结：**

1. **第1轮**：理解了提示词基础结构和语法
2. **第2轮**：掌握了风格、构图、光影专业术语
3. **第3轮**：学会了视频生成专属技巧
4. **第4轮**：精通了权重控制和高级技巧
5. **第5轮**：通过实战案例巩固了所有知识

**核心原则：**
- 越具体越好
- 顺序决定权重
- 质量词不能少
- 负面词是秘密武器
- 多练习多迭代

---

## 下一步行动

1. **实践出真知**：每天生成10+张图片
2. **建立提示词库**：收藏好的提示词
3. **关注AI更新**：模型能力在快速进化
4. **分享学习**：将知识传播给更多人
