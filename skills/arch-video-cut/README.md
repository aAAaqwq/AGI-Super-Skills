# 🎬 建筑视频剪辑 Skill

> 铭哥专属 - 自动剪辑建筑视频，越用越懂你

---

## 快速开始

```bash
cd ~/.openclaw/workspace/skills/arch-video-cut
python3 scripts/full_workflow.py
```

---

## 准备素材

1. **视频片段** → 放到 `data/m1/` 文件夹
2. **旁白音频** → `~/Desktop/新录音 XX.m4a`

---

## 输出

- `data/edited_video_final_with_subtitles.mp4` - 横屏版 (16:9)
- `data/edited_video_final_with_subtitles_3x4.mp4` - 竖屏版 (3:4)

---

## 管理偏好

```bash
# 查看当前配置
python3 scripts/manage_preferences.py show

# 修改配置
python3 scripts/manage_preferences.py set

# 重置配置
python3 scripts/manage_preferences.py reset
```

---

## 依赖

```bash
brew install ffmpeg-full
pip3 install faster-whisper  # 可选，用于语音转录
```

---

详细文档：`SKILL.md` + `SELF_LEARNING_GUIDE.md`
