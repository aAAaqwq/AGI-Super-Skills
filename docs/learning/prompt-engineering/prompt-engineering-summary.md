# 生图生视频提示词优化深度学习 - 汇总

> 学习完成日期：2026-03-21
> 学习轮次：5轮（每轮约40分钟）

---

## 📚 学习目录

| 轮次 | 主题 | 文件 |
|------|------|------|
| 第1轮 | 基础提示词结构与语法 | `round-1-basic-structure.md` |
| 第2轮 | 风格、构图、光影控制术语 | `round-2-style-composition-lighting.md` |
| 第3轮 | 视频生成专属技巧 | `round-3-video-generation.md` |
| 第4轮 | 高级技巧（负面提示词、权重） | `round-4-advanced-techniques.md` |
| 第5轮 | 实战案例拆解与最佳实践 | `round-5-case-studies.md` |

---

## 🎯 核心要点总结

### 提示词黄金公式

```
[质量词] + [主体] + [细节] + [环境] + [风格] + [构图] + [光照] + [参数]
```

### 关键原则

1. **越具体越好** - 具体描述 > 模糊描述
2. **顺序决定权重** - 越前面的词权重越高
3. **英文优先** - 多数模型英文理解更好
4. **质量词不能少** - masterpiece, best quality, ultra detailed
5. **负面词是秘密武器** - 排除不需要的元素

---

## 📝 常用提示词模板

### 质量修饰词 TOP 10

```
masterpiece, best quality, ultra detailed, highly detailed,
8k, 4k, photorealistic, professional, cinematic,
intricate details, sharp focus
```

### 构图术语 TOP 5

```
centered composition, rule of thirds, close-up, 
wide shot, bird's eye view, depth of field, bokeh
```

### 光照术语 TOP 5

```
cinematic lighting, soft lighting, golden hour,
rim light, volumetric lighting, studio lighting
```

### 负面提示词模板

```
lowres, bad anatomy, bad hands, text, error, 
missing fingers, cropped, worst quality, low quality,
jpeg artifacts, watermark, username, blurry, 
ugly, deformed, disfigured
```

---

## 🔧 工具使用

### relay-image-gen

```bash
uv run ~/.openclaw/skills/relay-image-gen/scripts/relay_image_gen.py \
  -p "your prompt here" -f output.jpg -r 2k -a 16:9
```

### relay-video-gen

```bash
uv run ~/.openclaw/skills/relay-video-gen/scripts/relay_video_gen.py \
  -p "your prompt here" -f output.mp4 -d 5 -a 9:16
```

---

## 📖 学习资源

- Midjourney 官方文档
- Stable Diffusion Art Prompt Guide
- Google Veo 最佳实践
- Kling 官方文档

---

## 🚀 后续行动

1. 每日生成10+张图片练习
2. 建立个人提示词库
3. 关注AI模型更新
4. 分享学习成果

---

*CCO - 把想法变成现实 🎨*
