# VectorNode API 规范

来源：[Apifox 文档](https://o1kqetbjmk.apifox.cn) · [主站](https://www.vectronode.com/)

## 1. 图片生成 (Create Image)

**Endpoint**: `POST {VECTORNODE_BASE_URL}/v1/images/generations`
**Auth**: `Authorization: Bearer {VECTORNODE_API_KEY}`
**Content-Type**: `application/json`

### Request Body

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `prompt` | string | ✅ | 图片描述，**最大 1000 字符** |
| `model` | string | ✅ | `gpt-image-2` (按Token) 或 `gpt-image-2-all` (按次) |
| `n` | int | ✅ | 张数，1-10 |
| `size` | string | ❌ | 详见下表 |
| `quality` | string | ❌ | `low` / `medium` / `high` / `auto`(默认) |
| `format` | string | ❌ | `png` / `jpeg` / `webp` |

### Response (200)

```json
{
  "created": 1700000000,
  "background": "...",
  "data": {
    "b64_json": "..."
  },
  "output_format": "png",
  "quality": "high",
  "size": "1024x1024"
}
```

---

## 2. 图片编辑 (Edit Image)

**Endpoint**: `POST {VECTORNODE_BASE_URL}/v1/images/edits`
**Auth**: `Authorization: Bearer {VECTORNODE_API_KEY}`
**Content-Type**: `multipart/form-data`

### Form Fields

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `image` | file | ✅ | 待编辑图片，**最大 50MB**，可传多张 |
| `prompt` | string | ✅ | 编辑描述 |
| `model` | string | ✅ | `gpt-image-2` / `gpt-image-2-all` / `flux-kontext-pro` / `flux-kontext-max` |
| `n` | int | ❌ | 张数 1-10，默认 1 |
| `mask` | file | ❌ | 透明遮罩 PNG，<4MB，与 image 同尺寸 |
| `quality` | string | ❌ | `low` / `medium` / `high` / `auto` |
| `size` | string | ❌ | 同 generate |
| `background` | string | ❌ | `transparent` / `opaque` / `auto`(默认) |
| `moderation` | string | ❌ | `low` / `auto`(默认) |

### Response (200)

```json
{
  "created": 1700000000,
  "background": "transparent",
  "data": {
    "b64_json": "..."
  },
  "output_format": "png",
  "quality": "high",
  "size": "1024x1536"
}
```

---

## 3. 支持的尺寸

| 尺寸 | 像素 | 分辨率等级 | 备注 |
|------|------|----------|------|
| `1024x1024` | 1,048,576 | 1K | API 标准尺寸 |
| `1536x1024` | 1,572,864 | 1K | 横版 |
| `1024x1536` | 1,572,864 | 1K | 竖版 |
| `2048x2048` | 4,194,304 | 2K | API 标准 2K |
| `2048x1152` | 2,359,296 | 2K | 横版 2K |
| `3840x2160` | 8,294,400 | 4K | |
| `2160x3840` | 8,294,400 | 4K | 竖版 4K |
| `auto` | — | — | 默认，模型自动选 |

**限制**：
- image API 出图 ≤ 3840px
- 文档说明宽高比例 ≤ 3:1
- API 出图像素范围 655,360 ~ 8,294,400

---

## 4. 支持的模型 (edit 端点)

| Model | 说明 |
|-------|------|
| `gpt-image-2` | 按 Token 计费（短 prompt 划算） |
| `gpt-image-2-all` | 按次计费（长/复杂 prompt 划算） |
| `flux-kontext-pro` | Flux 系列 |
| `flux-kontext-max` | Flux 高端 |
| `gpt-image-1` | 前代模型 |
| `gpt-image-1-all` | 前代按次 |

---

## 5. 错误码

| 状态码 | 含义 | 处理 |
|--------|------|------|
| 200 | 成功 | — |
| 400 | 参数错误（prompt 超过 1000 字符等） | 检查 prompt 长度 |
| 401 | 鉴权失败 | 检查 `VECTORNODE_API_KEY` |
| 429 | 触发限流 | 脚本自动 retry 一次 |
| 5xx | 中转站/上游故障 | 脚本自动 retry 一次 |

---

## 6. 重要注意

- **同一个 endpoint**（`/v1/images/generations`）根据 `model` 字段路由到不同计费后端
- **图片编辑**只支持 `multipart/form-data`（不能 JSON 传图）
- **多张图编辑**：`image` 字段可传多个 file
- **遮罩 mask**：PNG 透明区域 = 待编辑区域
