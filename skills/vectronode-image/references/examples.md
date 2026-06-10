# 使用示例

## 1. 最简生成

```bash
python3 ~/.openclaw/skills/vectronode-image/scripts/vectronode_image.py generate \
  --prompt "A cute cat" \
  --output /tmp/cat.png
```

输出：
```
🎨 Generating with gpt-image-2 — short prompt (8 chars), simple config
   prompt: 8 chars | n=1 | size=auto | quality=auto
✅ Saved: /tmp/cat.png
```

## 2. 长提示词 → 自动路由到按次

```bash
python3 ~/.openclaw/skills/vectronode-image/scripts/vectronode_image.py generate \
  --prompt "Editorial flat illustration of AI tools comparison, multiple devices arranged in a circle, each showing a different AI capability, soft pastel colors, isometric view, white background, modern design, 4K quality" \
  --output /tmp/ai-tools.png \
  --size 2048x2048 \
  --quality high
```

输出：
```
🎨 Generating with gpt-image-2-all — prompt 195 > 200 chars; size=2048x2048 (2K); quality=high
   prompt: 195 chars | n=1 | size=2048x2048 | quality=high
✅ Saved: /tmp/ai-tools.png
```

## 3. 编辑图片

```bash
python3 ~/.openclaw/skills/vectronode-image/scripts/vectronode_image.py edit \
  --image /tmp/hero.jpg \
  --prompt "Change background to sunset over mountains, keep the person in the foreground" \
  --output /tmp/hero-edited.png
```

## 4. 批量生成（4 张）

```bash
python3 ~/.openclaw/skills/vectronode-image/scripts/vectronode_image.py generate \
  --prompt "A cute cat in different poses" \
  --output /tmp/cat-batch.png \
  --n 4 \
  --format jpeg
```

输出（每张独立文件）：
```
🎨 Generating with gpt-image-2-all — n=4 > 1
   prompt: 28 chars | n=4 | size=auto | quality=auto
✅ Saved: /tmp/cat-batch_1.jpeg
✅ Saved: /tmp/cat-batch_2.jpeg
✅ Saved: /tmp/cat-batch_3.jpeg
✅ Saved: /tmp/cat-batch_4.jpeg
```

## 5. 强制按次计费

```bash
python3 ~/.openclaw/skills/vectronode-image/scripts/vectronode_image.py generate \
  --prompt "Logo" \
  --output /tmp/logo.png \
  --model gpt-image-2-all
```

## 6. 预览路由决策（不发请求）

```bash
python3 ~/.openclaw/skills/vectronode-image/scripts/vectronode_image.py generate \
  --prompt "$(cat /tmp/long-prompt.txt)" \
  --output /tmp/x.png \
  --size 4k \
  --dry-run
```

输出：
```
🔍 [DRY-RUN] Route decision:
   model:     gpt-image-2-all
   reason:    prompt 450 > 200 chars; size=3840x2160 (4K)
   prompt:    450 chars
   n:         1
   size:      3840x2160
   quality:   auto
   output:    /tmp/x.png
```

## 7. 透明背景 PNG

```bash
python3 ~/.openclaw/skills/vectronode-image/scripts/vectronode_image.py generate \
  --prompt "A cute mascot character" \
  --output /tmp/mascot.png \
  --background transparent
```

## 8. 集成到 Bash 脚本

```bash
#!/bin/bash
set -e

ARTIFACTS=~/clawd/output/articles/$(date +%Y-%m-%d)
mkdir -p "$ARTIFACTS"

# 封面图（自动路由）
python3 ~/.openclaw/skills/vectronode-image/scripts/vectronode_image.py generate \
  --prompt "Modern AI tool cover, gradient blue purple" \
  --output "$ARTIFACTS/cover.png" \
  --size 1024x1024

echo "✅ Cover saved to $ARTIFACTS/cover.png"
```

## 9. 在 Python 里调用

```python
import subprocess

result = subprocess.run([
    "python3",
    "/Users/danielli/.openclaw/skills/vectronode-image/scripts/vectronode_image.py",
    "generate",
    "--prompt", "A serene landscape",
    "--output", "/tmp/landscape.png",
    "--size", "1536x1024",
    "--quality", "high",
], capture_output=True, text=True)

print(result.stdout)
if result.returncode != 0:
    print("ERROR:", result.stderr, file=__import__("sys").stderr)
```

## 10. 与 md2wechat 联动（公众号封面）

```bash
# 1. 用 vectronode 生成封面
python3 ~/.openclaw/skills/vectronode-image/scripts/vectronode_image.py generate \
  --prompt "..." \
  --output /tmp/cover.png

# 2. 上传到微信公众号
md2wechat upload_image /tmp/cover.png

# 3. 在 draft JSON 里引用 thumb_media_id
```

## 11. 与中转站其他模型对比

| 场景 | 推荐 |
|------|------|
| 短 prompt + 标准需求 | `gpt-image-2` (按Token，省钱) |
| 长/复杂 prompt | `gpt-image-2-all` (按次，可预期) |
| Flux 风格需求 | `flux-kontext-pro` / `flux-kontext-max` |
| 高质量 4K 输出 | `gpt-image-2-all` + `3840x2160` |
| 多图同时出 | `gpt-image-2-all` + `--n 4` |
| 编辑已有图 | `gpt-image-2`（短 prompt 编辑） |
