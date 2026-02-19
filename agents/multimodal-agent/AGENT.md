# Multimodal Agent

专门处理多模态任务的 Agent，支持图像/视频的**理解**和**生成**。

## 能力

### 🔍 理解能力 (使用 Gemini 3 Pro)
- 🖼️ **图像理解** - 分析、描述、识别图片内容
- 📊 **图表分析** - 解读图表、数据可视化
- 📄 **文档 OCR** - 提取图片中的文字
- 🎨 **视觉问答** - 回答关于图片的问题
- 🔍 **物体识别** - 识别图片中的物体、场景、人物

### 🎨 生成能力 (使用 xingjiabiapi)
- 🖼️ **图像生成** - 根据文字描述生成图片
- 🎬 **视频生成** - 根据文字描述生成视频
- ✏️ **图像编辑** - 修改、风格迁移

## 可用模型

### 图像生成
| 模型 | 别名 | 说明 |
|------|------|------|
| `flux-pro-max` | `flux` | 高质量图像生成 |
| `flux-kontext-max` | `fluxk` | 图像编辑、风格迁移 |
| `google/imagen-4-ultra` | `imagen` | Google 最强图像 |
| `gpt-image-1` | `dalle` | DALL-E 3 |
| `doubao-seedream-4-5-251128` | `doubao` | 豆包，中式美学 |
| `kling-image` | `klingimg` | 可灵生图 |
| `gemini-3-pro-image-preview` | `xjb-g3pi` | Gemini 图像生成 |

### 视频生成
| 模型 | 别名 | 说明 |
|------|------|------|
| `veo3.1-pro-4k` | `veo4k` | Google 4K 高清视频 |
| `veo3.1-pro` | `veopro` | Google 专业版 |
| `veo3.1` | `veo` | Google 标准版 |
| `sora-2-pro-all` | `sora` | OpenAI Sora 2 Pro |
| `sora-2-all` | - | OpenAI Sora 2 |
| `kling-video` | `kling` | 可灵视频 |
| `MiniMax-Hailuo-2.3` | - | 海螺视频 |

## 使用场景

### 图像理解
当主 agent 收到图片并需要理解其内容时：
```
sessions_spawn(
  agentId="multimodal-agent",
  task="分析这张图片: [图片路径]"
)
```

### 图像生成
当用户需要生成图片时：
```
sessions_spawn(
  agentId="multimodal-agent",
  task="生成图片: 一只可爱的猫咪在草地上玩耍，使用 flux 模型"
)
```

### 视频生成
当用户需要生成视频时：
```
sessions_spawn(
  agentId="multimodal-agent",
  task="生成视频: 日落时分的海滩，海浪轻轻拍打沙滩，使用 veopro 模型"
)
```

## API 调用方式

### 图像生成 API
```python
import requests

response = requests.post(
    "https://xingjiabiapi.com/v1/images/generations",
    headers={"Authorization": f"Bearer {API_KEY}"},
    json={
        "model": "flux-pro-max",
        "prompt": "描述文字",
        "n": 1,
        "size": "1024x1024"
    }
)
```

### 视频生成 API
```python
response = requests.post(
    "https://xingjiabiapi.com/v1/videos/generations",
    headers={"Authorization": f"Bearer {API_KEY}"},
    json={
        "model": "veo3.1-pro",
        "prompt": "描述文字",
        "duration": 5
    }
)
```

## 模型选择建议

| 场景 | 推荐模型 |
|------|----------|
| 高质量图像 | `flux-pro-max` |
| 图像编辑 | `flux-kontext-max` |
| 中式风格 | `doubao` |
| 4K 视频 | `veo3.1-pro-4k` |
| 电影级视频 | `sora-2-pro-all` |
| 快速视频 | `kling-video` |

## 配置

- **Primary Model**: xingjiabiapi/gemini-3-pro-preview (理解)
- **Image Models**: xingjiabiapi/flux-pro-max, imagen-4-ultra, etc.
- **Video Models**: xingjiabiapi/veo3.1-pro, sora-2-pro-all, etc.
- **API Key**: `pass show api/xingjiabiapi`
