# qingyun-api Skill

青云聚合API多模态调用 Skill — 覆盖生图、生视频、语音、Embedding 等能力。

## 触发条件
- `qingyun`、`青云`、`青云API`、`qingyun-api`
- 生图/生视频/语音合成时指定 `model=gemini-3-pro-image-preview` 等青云模型ID

## API 配置
- **Base URL**: `https://api.qingyuntop.top`
- **API Key**: `pass show api/qingyun` → `QINGYUN_API_KEY` 环境变量
- **充值汇率**: 0.79元 = $1（限时特价分组再6折）
- **并发**: 无限
- **域名**: 主 `api.qingyuntop.top` / 备用 `api.qingyunjuhe.top`

## 模型档案 (18个)

### 🖼️ 图片生成 (2)
| Model ID | 名称 | 格式 | 特点 |
|----------|------|------|------|
| `gemini-3-pro-image-preview` | Gemini 3 Pro 图片 | Gemini 原生 | 支持宽高比+清晰度控制，原生图片生成最强 |
| `grok-imagine-image-pro` | Grok Image Pro | Grok 系列 | xAI 旗舰生图模型，写实/创意能力强 |

### 🎞️ 图片转动图 (1)
| Model ID | 名称 | 格式 | 特点 |
|----------|------|------|------|
| `andreasjansson/stable-diffusion-animation` | SD Animation | Replicate task | Stable Diffusion 动画生成，支持参数调节帧数/平滑度 |

### 🎬 视频生成 (7)
| Model ID | 名称 | 格式 | 特点 | 分层 |
|----------|------|------|------|------|
| `sora-2-all` | Sora 2 | Sora 统一格式 | OpenAI 旗舰视频，文/图生视频 | T0 顶级 |
| `sora-2-pro-all` | Sora 2 Pro | Sora 统一格式 | Sora增强版，更长更高质量 | T0 顶级 |
| `veo_3_1-fast-4K` | Veo 3.1 Fast 4K | Veo 统一格式 | Google 4K视频，速度快 | T1 高端 |
| `veo_3_1-components-4K` | Veo 3.1 Components | Veo 统一格式 | Veo组件化视频生成 | T1 高端 |
| `grok-video-3-10s` | Grok Video 3 | Grok 视频格式 | xAI 视频，10秒短视频 | T2 中端 |
| `doubao-seedance-1-5-pro-251215` | 豆包 Seedance 1.5 Pro | 豆包格式 | 字节跳动旗舰视频，首尾帧支持 | T1 高端 |
| `doubao-seedance-1-0-pro-fast-251015` | 豆包 Seedance 1.0 Pro Fast | 豆包格式 | Seedance快速版 | T2 中端 |

### 🔊 音频/TTS (4)
| Model ID | 名称 | 格式 | 特点 |
|----------|------|------|------|
| `gpt-4o-audio-preview` | GPT-4o Audio | OpenAI Chat | 音频输入+输出，多模态对话 |
| `gemini-2.5-flash-preview-tts` | Gemini 2.5 Flash TTS | Gemini 原生 | Google 快速TTS，多语言 |
| `gemini-2.5-pro-preview-tts` | Gemini 2.5 Pro TTS | Gemini 原生 | Google 旗舰TTS，音质最佳 |
| `kling-audio` | 可灵音效 | Kling 文生音效 | 文字生成音效 |

### 🎨 特效/高级 (4)
| Model ID | 名称 | 格式 | 特点 |
|----------|------|------|------|
| `kling-avatar-image2video` | 可灵数字人视频 | Kling 图生视频 | 图片转数字人说话视频 |
| `kling-advanced-lip-sync` | 可灵高级对口型 | Kling 对口型 | 精准视频对口型/人脸识别 |
| `kling-effects` | 可灵视频特效 | Kling 视频特效 | 视频特效滤镜/风格迁移 |
| `gemini-embedding-2-preview` | Gemini Embedding | OpenAI 兼容 | 文本向量化（embedding） |

## API 格式分类

### OpenAI 兼容格式 (可直接用 openai 库)
- `gemini-embedding-2-preview` → `POST /v1/embeddings`
- `gpt-4o-audio-preview` → `POST /v1/chat/completions` (带 audio modality)

### Chat 兼容格式 (messages → 图片base64)
- `gemini-3-pro-image-preview` → 可通过 chat 兼容格式调用
- `grok-imagine-image-pro` → Grok 系列 chat 格式

### Task 异步格式 (创建任务 → 轮询 → 获取结果)
- 视频模型: sora, veo, grok-video, doubao-seedance, kling-avatar
- Replicate: stable-diffusion-animation
- Kling 特效: kling-effects, kling-advanced-lip-sync, kling-audio

### Gemini 原生格式
- Gemini TTS: gemini-2.5-flash/pro-preview-tts
- Gemini 图片: gemini-3-pro-image-preview (原生格式更灵活)

## 脚本目录
```
scripts/
├── qingyun-common.sh        # 公共函数（API key、base URL、错误处理）
├── qingyun-embedding.sh     # gemini-embedding-2-preview
├── qingyun-image-gemini.sh  # gemini-3-pro-image-preview
├── qingyun-image-grok.sh    # grok-imagine-image-pro
├── qingyun-sd-animation.sh  # andreasjansson/stable-diffusion-animation
├── qingyun-video-sora.sh    # sora-2-all, sora-2-pro-all
├── qingyun-video-veo.sh     # veo_3_1-fast-4K, veo_3_1-components-4K
├── qingyun-video-grok.sh    # grok-video-3-10s
├── qingyun-video-doubao.sh  # doubao-seedance-*
├── qingyun-video-kling.sh   # kling-avatar-image2video
├── qingyun-audio-gpt4o.sh   # gpt-4o-audio-preview
├── qingyun-tts-gemini.sh    # gemini-2.5-flash/pro-preview-tts
├── qingyun-audio-kling.sh   # kling-audio
├── qingyun-lipsync-kling.sh # kling-advanced-lip-sync
├── qingyun-effects-kling.sh # kling-effects
└── qingyun-test-all.sh      # 全量测试脚本
```

## 使用方式
```bash
# 设置 API key（或在 .env 中配置）
export QINGYUN_API_KEY=$(pass show api/qingyun)

# 调用
bash ~/clawd/skills/qingyun-api/scripts/qingyun-embedding.sh "测试文本"
bash ~/clawd/skills/qingyun-api/scripts/qingyun-image-gemini.sh "一只可爱的猫咪" --ratio 16:9
bash ~/clawd/skills/qingyun-api/scripts/qingyun-video-sora.sh "日落时分海边漫步" --model sora-2-all
```

## 2026-04-06 实战沉淀：内容封面默认走法

### 适用场景
- 小红书封面
- 公众号头图
- 需要“内容表达准确”优先于“随机创意”的封面生成

### 推荐组合
- **提示词方法论**：先用 `content-cover-gen`
- **实际生图执行**：再用本 skill 的 `scripts/qingyun-image-gemini.sh`
- **默认模型**：`gemini-3-pro-image-preview`
- **默认取 key**：`pass show api/qingyun | head -n 1`

### 小红书封面推荐命令
```bash
export QINGYUN_API_KEY="$(pass show api/qingyun | head -n 1)"
bash ~/clawd/skills/qingyun-api/scripts/qingyun-image-gemini.sh \
  "Split-scene editorial illustration, left side active thinking with warm brain glow, right side passive AI overuse with dim blue brain, strong visual metaphor, no text overlay" \
  --ratio 3:4 \
  -o /path/to/xhs-cover
```

### 和 `xhs-smart-publisher` 的协作细节（新增）
- 出图完成后，优先把文件命名到文章目录下，例如：`cover-3-qingyun.jpg`
- 如果后续要交给 browser 上传，记得再复制到：`/tmp/openclaw/uploads/`
- 文章元数据里的 `🖼️ 封面：待生成` 要同步替换成真实文件路径
- 这一步完成后，才交给 `xhs-smart-publisher` 进入发布页

### 注意事项
- `gemini-3.1-image-pro` 是口头说法；**当前本地实际可用模型名是 `gemini-3-pro-image-preview`**
- 输出文件会根据接口返回格式落成图片（如 `.jpg`）
- 做内容封面时，先定隐喻再出图；不要上来就丢一句泛 prompt
- 如果是给小红书发文服务，默认认为下游会走 `xhs-smart-publisher`，所以输出路径、命名、比例都要为发布动作服务

## 安全
- API key 从 `pass show api/qingyun` 获取，永不明文写入脚本
- 脚本内部通过 `$QINGYUN_API_KEY` 环境变量引用

## 官方文档
- API 文档: https://qingyuntop.apifox.cn/
- 定价页: https://api.qingyuntop.top/pricing
- OpenClaw 配置教程: https://qingyuntop.apifox.cn/doc-8310795
