---
name: vectronode-image
description: "VectorNode 中转站 GPT Image 图片生成与编辑（按提示词长度自动路由 gpt-image-2 Token 计费 / gpt-image-2-all 按次计费）。Use when: 画图、生图、生成图片、gpt生图、VectorNode、gpt-image、image generate、image edit、编辑图片。Requires VECTORNODE_API_KEY in ~/.openclaw/.env."
metadata:
  openclaw:
    emoji: 🎨
    requires:
      bins:
        - python3
      env:
        - VECTORNODE_API_KEY
    platforms:
      - macos
      - linux
    install: {}
author: Daniel Li
---

# VectorNode Image — GPT Image 智能生图

VectorNode 中转站（https://www.vectronode.com/）的 GPT Image 生图/编辑能力，**按提示词长度自动路由最优接口**，兼顾成本与质量。

## 两个模型，一套接口

| 模型 | 计费方式 | 适用场景 |
|------|---------|---------|
| `gpt-image-2` | **按 Token 计费** | 短提示词（≤200 字符）更划算 |
| `gpt-image-2-all` | **按次计费** | 长提示词/复杂描述/多图/高分辨率更稳 |

**两个模型都调用同一个 endpoint**：`POST {VECTORNODE_BASE_URL}/v1/images/generations`（JSON）。区别只在 `model` 字段。

## 路由策略（自动）

脚本 `vectronode_image.py` 会根据以下因素**自动选择**最优模型：

```
判断流程：
1. 用户显式指定 model？ → 使用指定的
2. prompt 长度 > 200 字符？ → gpt-image-2-all（按次，长 prompt 友好）
3. n > 1 或 size >= 2K 或 quality == "high"？ → gpt-image-2-all
4. 否则 → gpt-image-2（按 Token，节省成本）
```

## 快速使用

### 生成图片

```bash
python3 ~/.openclaw/skills/vectronode-image/scripts/vectronode_image.py generate \
  --prompt "A cute cat in a cyberpunk city" \
  --output ~/clawd/output/cat.png \
  --size 1024x1024
```

### 编辑图片

```bash
python3 ~/.openclaw/skills/vectronode-image/scripts/vectronode_image.py edit \
  --image ~/clawd/photos/hero.jpg \
  --prompt "Change background to sunset over mountains" \
  --output ~/clawd/output/hero-edited.png
```

### 强制模型

```bash
# 强制走按次计费（长/复杂任务）
python3 ~/.openclaw/skills/vectronode-image/scripts/vectronode_image.py generate \
  --prompt "..." --output out.png --model gpt-image-2-all

# 强制走按Token计费（短/简单任务）
python3 ~/.openclaw/skills/vectronode-image/scripts/vectronode_image.py generate \
  --prompt "..." --output out.png --model gpt-image-2
```

### 预览路由决策（不真发请求）

```bash
python3 ~/.openclaw/skills/vectronode-image/scripts/vectronode_image.py generate \
  --prompt "..." --output out.png --dry-run
```

## 必填环境变量

| 变量 | 来源 | 必填 |
|------|------|------|
| `VECTORNODE_API_KEY` | `~/.openclaw/.env` | ✅ |
| `VECTORNODE_BASE_URL` | `~/.openclaw/.env`（默认 `https://www.vectronode.com/`） | 可选 |

**加载顺序**：env → `~/.openclaw/.env` → 报错。

## 支持参数

| Flag | 说明 | 默认 |
|------|------|------|
| `--prompt` | 提示词（必填，generate） | — |
| `--image` | 输入图片路径（必填，edit） | — |
| `--mask` | 编辑遮罩 PNG（可选，edit） | — |
| `--output` | 输出文件路径（必填） | — |
| `--model` | `gpt-image-2` / `gpt-image-2-all` / `auto` | `auto` |
| `--n` | 张数（1-10） | `1` |
| `--size` | `1024x1024` / `1536x1024` / `1024x1536` / `2K` / `4K` / `auto` | `auto` |
| `--quality` | `low` / `medium` / `high` / `auto` | `auto` |
| `--format` | `png` / `jpeg` / `webp` | `png` |
| `--background` | `transparent` / `opaque` / `auto` | `auto` |
| `--dry-run` | 仅打印路由决策 | `false` |

## 支持的尺寸

| 尺寸 | 说明 |
|------|------|
| `1024x1024` | 默认 |
| `1536x1024` / `1024x1536` | 横竖版 |
| `2048x2048` / `2048x1152` | 2K |
| `3840x2160` / `2160x3840` | 4K（需 gpt-image-2-all） |
| `auto` | 模型自动选 |

## 路由决策示例

| Prompt 长度 | n | size | quality | → 模型 | 理由 |
|------------|---|------|---------|--------|------|
| 50 字符 | 1 | 1024x1024 | auto | `gpt-image-2` | 短，Token 计费便宜 |
| 250 字符 | 1 | 1024x1024 | auto | `gpt-image-2-all` | 长 prompt，按次更划算 |
| 50 字符 | 4 | 1024x1024 | auto | `gpt-image-2-all` | 多图，按次计费 |
| 50 字符 | 1 | 2048x2048 | auto | `gpt-image-2-all` | 2K，按次计费 |
| 50 字符 | 1 | 1024x1024 | high | `gpt-image-2-all` | high quality，按次更稳 |

## 输出格式

API 返回 `b64_json`，脚本自动解码保存到 `--output` 路径（PNG/JPEG/WebP）。

## 错误处理

- `401` → 检查 `VECTORNODE_API_KEY` 是否正确
- `429` → 触发限流，脚本自动 sleep 2s 重试一次
- `400` → 提示词超过 1000 字符或参数不合法
- `5xx` → 中转站故障，提示重试

## 相关文档

- [API 完整规范](references/api-specs.md)
- [路由逻辑与定价分析](references/routing-logic.md)
- [使用示例](references/examples.md)
