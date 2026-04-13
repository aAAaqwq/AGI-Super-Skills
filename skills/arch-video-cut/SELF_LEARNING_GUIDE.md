# 🧠 自进化视频剪辑工作流

这个脚本会**学习你的剪辑偏好**，越用越懂你！

---

## 🎯 核心功能

### 1. 自动记忆偏好
每次剪辑时，脚本会记住你的设置：
- 视频目标时长（默认 20 秒）
- 横屏/竖屏字体大小
- 字幕排版方式（自动换行/单行）
- 背景音乐音量
- 淡入淡出时长

### 2. 偏好应用
下次运行时，自动应用你之前的设置，无需重复调整！

### 3. 学习历史
保留最近 20 次调整记录，方便回顾和追踪。

---

## 📖 使用指南

### 运行视频剪辑
```bash
cd ~/.openclaw/workspace/skills/doubao-skill-v2
python3 scripts/full_workflow.py
```

### 查看当前偏好
```bash
python3 scripts/manage_preferences.py show
```

**示例输出：**
```
============================================================
🧠 用户偏好配置（自进化）
============================================================

📹 视频设置:
  目标时长：20.0 秒
  竖屏比例：3:4
  竖屏分辨率：1080x1440

📝 字幕设置:
  横屏字体：14px
  竖屏字体：10px
  字体名称：STHeiti
  自动换行：是
  底部边距：30px

🎵 音频设置:
  背景音乐音量：15%
  淡入/淡出：2 秒

📊 学习记录:
  共记录 5 次调整
  最近 3 次:
    - 2026-03-18T09:45: 视频时长调整为 20 秒
    - 2026-03-18T09:48: 竖屏字体调整为 10px
    - 2026-03-18T09:55: 字幕换行设置为自动

============================================================
```

### 修改偏好（交互式）
```bash
python3 scripts/manage_preferences.py set
```

会逐项询问你要修改的设置，直接回车保持当前值。

### 重置偏好
```bash
python3 scripts/manage_preferences.py reset
```

恢复所有设置为默认值。

---

## 🔧 偏好配置文件

配置文件位置：
```
~/.openclaw/workspace/skills/doubao-skill-v2/config/user_preferences.json
```

你可以直接编辑这个 JSON 文件来批量修改偏好。

### 配置结构
```json
{
  "video": {
    "target_duration": 20.0,
    "vertical_format": "3:4",
    "vertical_resolution": "1080x1440"
  },
  "subtitles": {
    "horizontal_font_size": 14,
    "vertical_font_size": 10,
    "font_name": "STHeiti",
    "auto_wrap": true,
    "margin_v": 30
  },
  "audio": {
    "background_music_volume": 0.15,
    "background_music_style": "piano_chords",
    "fade_in_duration": 2,
    "fade_out_duration": 2
  },
  "learning": {
    "enabled": true,
    "adjustment_history": [...],
    "last_updated": "2026-03-18T09:55:00"
  }
}
```

---

## 💡 使用场景

### 场景 1：铭哥说"字体太小了"
```bash
# 交互式修改
python3 scripts/manage_preferences.py set
# 输入新的字体大小，如 18

# 下次剪辑自动使用 18px
python3 scripts/full_workflow.py
```

### 场景 2：想要 30 秒版本
```bash
# 方法 1：修改配置文件
# 编辑 config/user_preferences.json，将 target_duration 改为 30

# 方法 2：交互式修改
python3 scripts/manage_preferences.py set
# 输入目标时长 30
```

### 场景 3：查看最近调整了什么
```bash
python3 scripts/manage_preferences.py show
# 查看学习记录部分
```

---

## 🚀 进阶用法

### 快速切换偏好配置
可以创建多个配置文件，如：
- `user_preferences_short.json`（15 秒快节奏）
- `user_preferences_long.json`（60 秒详细版）

切换时复制覆盖 `user_preferences.json` 即可。

### 在脚本中动态覆盖
```python
# 在 full_workflow.py 开头添加
prefs["subtitles"]["horizontal_font_size"] = 20  # 临时覆盖
```

---

## 📝 学习记录示例

每次运行脚本都会记录：
```json
{
  "timestamp": "2026-03-18T09:55:00",
  "description": "视频剪辑完成",
  "category": "workflow",
  "changes": {
    "target_duration": 20.0,
    "horizontal_font_size": 14,
    "vertical_font_size": 10,
    "auto_wrap": true
  }
}
```

这样可以追踪你的偏好演变过程！

---

## ❓ 常见问题

**Q: 如何关闭自学习功能？**
A: 编辑 `config/user_preferences.json`，将 `learning.enabled` 设为 `false`

**Q: 偏好文件在哪里？**
A: `~/.openclaw/workspace/skills/doubao-skill-v2/config/user_preferences.json`

**Q: 可以导出偏好吗？**
A: 直接复制 JSON 文件即可分享给其他人

**Q: 脚本更新会丢失偏好吗？**
A: 不会！配置文件独立存储，脚本更新会保留你的偏好

---

_让工具适应你，而不是你适应工具。_ 🧠
