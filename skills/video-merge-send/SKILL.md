---
name: video-merge-send
description: "合并多个分段视频为一个完整视频，并发送到飞书。使用ffmpeg拼接视频片段，支持淡入淡出转场。触发场景：用户需要合并视频片段、拼接分镜视频、视频合并后发飞书、把多个短视频合成一个、分段视频合并发送。配合 jimeng-storyboard skill 使用，完成数字人视频全流程。"
---

# 视频合并与发送

合并多个分段视频（如即梦数字人生成的分镜片段）为一个完整视频，并发送到飞书。

## 前置要求

- ffmpeg 已安装（`brew install ffmpeg`）
- 分段视频已下载到本地

## 合并视频

### 方式1：指定文件列表

```bash
python3 skills/video-merge-send/scripts/merge_videos.py \
  -i clip1.mp4 clip2.mp4 clip3.mp4 \
  -o output.mp4
```

### 方式2：指定目录（按文件名排序）

```bash
python3 skills/video-merge-send/scripts/merge_videos.py \
  -d ./clips/ \
  -o output.mp4
```

### 方式3：带淡入淡出转场

```bash
python3 skills/video-merge-send/scripts/merge_videos.py \
  -d ./clips/ \
  -o output.mp4 \
  --transition fade \
  --transition-duration 0.5
```

## 参数说明

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `-i` | 输入视频文件列表（按顺序） | - |
| `-d` | 输入视频目录 | - |
| `-o` | 输出文件路径 | 必填 |
| `--transition` | 转场类型：`fade` / `none` | `none` |
| `--transition-duration` | 转场时长（秒） | `0.5` |

## 发送到飞书

合并完成后，使用 feishu-media skill 或 message 工具将视频发送到飞书：

```
message(action=send, filePath=output.mp4)
```

## 完整工作流

1. 用户使用 jimeng-storyboard skill 生成分镜脚本
2. 用户在即梦网页逐镜头生成并下载视频（建议命名为 01.mp4, 02.mp4, ...）
3. 将下载的视频放入同一目录
4. 运行合并脚本
5. 发送到飞书

## 注意事项

- 分段视频分辨率不同时，脚本会自动统一为第一个视频的分辨率
- 建议分段视频命名带序号确保顺序正确（如 01_hook.mp4, 02_problem.mp4）
- 合并后的视频使用H.264编码，兼容性好
