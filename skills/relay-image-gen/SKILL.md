---
name: relay-image-gen
description: Multi-provider image generation with automatic priority fallback
  Multi-provider image generation with priority fallback.
  Priority: qingyun Gemini (gemini-3-pro-image) → OpenClaw image tool → relay providers (boluobao → xingjiabi).
  Supports 1K/2K/4K, multiple aspect ratios, auto fallback.
  Extensible: add custom relay/API providers to PROVIDER_CONFIG.
  Use when: creating images, generating pictures/illustrations, poster art.
  Trigger: "生成图片", "生成封面", "画一张", "generate image", "create image".
  Author: Daniel Li
---

# Relay Image Generation

Multi-provider image generation with automatic priority fallback.

## Priority Chain

```
1. qingyun Gemini (gemini-3-pro-image-preview) ← 首选，质量最佳
   ↓ 失败/不可用
2. OpenClaw image_generate tool ← 官方内置
   ↓ 失败/不可用
3. boluobao (中转API) ← relay fallback 1
   ↓ 失败/不可用
4. xingjiabi (多模型fallback) ← relay fallback 2
   ↓ 失败/不可用
5. 自定义扩展 providers ← 按需添加
```

### 1. qingyun Gemini（首选）

**推荐用于所有内容封面和高质量图片生成。**

```bash
export QINGYUN_API_KEY=$(pass show api/qingyun | head -n 1)
bash ~/clawd/skills/qingyun-api/scripts/qingyun-image-gemini.sh \
  "your prompt" \
  --ratio 3:4 \
  -o "/path/to/output"
```

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--ratio` | `1:1` / `3:4` / `4:3` / `16:9` / `9:16` | `1:1` |
| `-o` | 输出路径（由调用方指定，不写死） | 必填 |

**优点**：出图质量高、比例控制准确、支持中文提示词
**要求**：`pass show api/qingyun` 需配置 API Key

### 2. OpenClaw image_generate（官方）

直接使用 OpenClaw 内置图片生成工具：

```
image_generate(
  prompt="your prompt",
  size="1024x1024",
  aspectRatio="1:1"
)
```

**优点**：无需额外 API Key，自动路由到最佳可用 provider
**注意**：由 OpenClaw 运行时管理，不在 bash 中调用

### 3-4. Relay Providers（备选）

```bash
uv run ~/.openclaw/skills/relay-image-gen/scripts/relay_image_gen.py \
  -p "your prompt" \
  -f "/path/to/output.jpg" \
  -a "3:4" \
  -r "1k"
```

| Flag | 说明 | 默认值 |
|------|------|--------|
| `-p` | 图片提示词（英文推荐） | 必填 |
| `-f` | 输出文件路径 | 必填 |
| `-r` | 分辨率：`1k` / `2k` / `4k` | `1k` |
| `-a` | 比例：`1:1` / `16:9` / `9:16` / `3:4` 等 | `1:1` |
| `-m` | 覆盖模型名 | Provider默认 |
| `-P` | 强制 Provider：`boluobao` / `xingjiabi` | Auto |

**Relay 内部优先级**：boluobao → xingjiabi

### 各 Provider 配置

| Provider | API Key 来源 | 默认模型 | Fallback |
|----------|-------------|---------|----------|
| **boluobao** | `pass show api/boluobao` | gemini-3-pro-image-preview | — |
| **xingjiabi** | 环境变量 `XINGJIABIAPI_KEY` | dall-e-3 | gpt-image-1 → imagen-4 |

## 输出路径规范

**不写死路径**。由调用方指定，默认遵循：

```
~/clawd/projects/MediaClaw/output/articles/{YYYY-MM-DD}/{topic-slug}.{ext}
```

## 扩展自定义 Provider

添加新的中转 API 只需两步：

### Step 1: 编辑 `PROVIDER_CONFIG`

在 `~/.openclaw/skills/relay-image-gen/scripts/relay_image_gen.py` 中添加：

```python
PROVIDER_CONFIG["my-provider"] = {
    "base_url": "https://api.my-provider.com/v1",
    "default_model": "my-model-name",
    "fallback_models": ["fallback-model-1", "fallback-model-2"],
    "env_key": "MY_PROVIDER_API_KEY",       # 环境变量名
    "pass_path": "api/my-provider",          # 或 pass 路径（二选一）
}
```

### Step 2: 添加到优先级链

```python
RELAY_PRIORITY = [
    {"name": "boluobao", "enabled": True},
    {"name": "my-provider", "enabled": True},  # ← 插入
    {"name": "xingjiabi", "enabled": True},
]
```

### Provider 配置字段说明

| 字段 | 说明 | 必填 |
|------|------|------|
| `base_url` | API endpoint | ✅ |
| `default_model` | 主模型 | ✅ |
| `fallback_models` | 失败后尝试的模型列表 | 可选 |
| `env_key` | 环境变量名 | 与 `pass_path` 二选一 |
| `pass_path` | `pass show` 路径 | 与 `env_key` 二选一 |

## 调用示例

```bash
# 内容封面（首选 qingyun）
export QINGYUN_API_KEY=$(pass show api/qingyun | head -n 1)
bash ~/clawd/skills/qingyun-api/scripts/qingyun-image-gemini.sh \
  "Editorial flat illustration of AI tools comparison..." \
  --ratio 3:4 \
  -o "~/clawd/projects/MediaClaw/output/articles/2026-04-15/ai-tools-cover.png"

# 通用图片（relay fallback）
uv run ~/.openclaw/skills/relay-image-gen/scripts/relay_image_gen.py \
  -p "A serene Japanese garden with cherry blossoms" \
  -f "~/clawd/projects/MediaClaw/output/articles/2026-04-15/garden-bg.jpg" \
  -a "16:9" -r "2k"

# 强制指定 provider
uv run ~/.openclaw/skills/relay-image-gen/scripts/relay_image_gen.py \
  -p "Robot waving hello" \
  -f "robot.jpg" \
  -P xingjiabi -m gpt-image-1

# OpenClaw 内置（无bash）
image_generate(prompt="sunset over mountains", size="1792x1024", aspectRatio="16:9")
```

## 内容封面

生成内容封面时，请先读取 **content-cover-gen** skill 获取完整的视觉隐喻设计方法论和提示词模板：

```
cat ~/clawd/skills/content-cover-gen/SKILL.md
```

**核心原则**：每张封面提示词必须包含文章核心观点的视觉隐喻 + 中文文字，严禁纯风格通用提示词。

## Provider 详细信息

参见 [references/providers.md](references/providers.md) 了解 API 格式、模型列表和添加方法。
