#!/usr/bin/env python3
"""
偏好学习器 - 记录和学习用户的视频剪辑偏好
"""

import json
from pathlib import Path
from datetime import datetime

PREFERENCE_FILE = Path(__file__).parent.parent / "config" / "user_preferences.json"

# 如果配置文件不存在，使用默认值

DEFAULT_PREFERENCES = {
    "video": {
        "target_duration": 20.0,
        "vertical_format": "3:4",
        "vertical_resolution": "720x960",  # 720p 竖屏
        "horizontal_resolution": "1280x720",  # 720p 横屏
    },
    "subtitles": {
        "horizontal_font_size": 14,
        "vertical_font_size": 10,
        "font_name": "STHeiti",
        "font_color": "&HFFFFFF",
        "alignment": 2,  # 底部居中
        "margin_v": 30,
        "auto_wrap": True,
    },
    "audio": {
        "background_music_volume": 0.15,
        "background_music_style": "piano_chords",
        "fade_in_duration": 2,
        "fade_out_duration": 2,
    },
    "learning": {
        "enabled": True,
        "adjustment_history": [],
        "last_updated": None,
    }
}

def load_preferences():
    """加载用户偏好"""
    if PREFERENCE_FILE.exists():
        with open(PREFERENCE_FILE, 'r', encoding='utf-8') as f:
            prefs = json.load(f)
            # 合并默认值（防止新版本缺少字段）
            return deep_merge(DEFAULT_PREFERENCES, prefs)
    return DEFAULT_PREFERENCES.copy()

def save_preferences(prefs):
    """保存用户偏好"""
    PREFERENCE_FILE.parent.mkdir(exist_ok=True)
    prefs["learning"]["last_updated"] = datetime.now().isoformat()
    with open(PREFERENCE_FILE, 'w', encoding='utf-8') as f:
        json.dump(prefs, f, ensure_ascii=False, indent=2)
    print(f"✅ 偏好已保存：{PREFERENCE_FILE}")

def deep_merge(base, override):
    """深度合并字典"""
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    return result

def record_adjustment(description, category, changes):
    """记录一次调整"""
    prefs = load_preferences()
    
    adjustment = {
        "timestamp": datetime.now().isoformat(),
        "description": description,
        "category": category,
        "changes": changes,
    }
    
    prefs["learning"]["adjustment_history"].append(adjustment)
    
    # 只保留最近 20 次调整
    if len(prefs["learning"]["adjustment_history"]) > 20:
        prefs["learning"]["adjustment_history"] = prefs["learning"]["adjustment_history"][-20:]
    
    save_preferences(prefs)
    print(f"📝 已记录调整：{description}")

def apply_preferences_to_script():
    """将偏好应用到脚本配置"""
    prefs = load_preferences()
    
    # 生成配置代码片段
    config_code = f"""# 用户偏好配置（自动学习）
VIDEO_CONFIG = {{
    "target_duration": {prefs["video"]["target_duration"]},
    "vertical_format": "{prefs["video"]["vertical_format"]}",
    "vertical_resolution": "{prefs["video"]["vertical_resolution"]}",
}}

SUBTITLE_CONFIG = {{
    "horizontal_font_size": {prefs["subtitles"]["horizontal_font_size"]},
    "vertical_font_size": {prefs["subtitles"]["vertical_font_size"]},
    "font_name": "{prefs["subtitles"]["font_name"]}",
    "auto_wrap": {str(prefs["subtitles"]["auto_wrap"]).lower()},
    "margin_v": {prefs["subtitles"]["margin_v"]},
}}

AUDIO_CONFIG = {{
    "background_music_volume": {prefs["audio"]["background_music_volume"]},
    "fade_duration": {prefs["audio"]["fade_in_duration"]},
}}
"""
    return config_code, prefs

def show_preferences():
    """显示当前偏好"""
    prefs = load_preferences()
    
    print("\n" + "="*60)
    print("🧠 用户偏好配置（自进化）")
    print("="*60)
    
    print(f"\n📹 视频设置:")
    print(f"  目标时长：{prefs['video']['target_duration']}秒")
    print(f"  竖屏比例：{prefs['video']['vertical_format']}")
    print(f"  竖屏分辨率：{prefs['video']['vertical_resolution']}")
    
    print(f"\n📝 字幕设置:")
    print(f"  横屏字体：{prefs['subtitles']['horizontal_font_size']}px")
    print(f"  竖屏字体：{prefs['subtitles']['vertical_font_size']}px")
    print(f"  字体名称：{prefs['subtitles']['font_name']}")
    print(f"  自动换行：{'是' if prefs['subtitles']['auto_wrap'] else '否'}")
    print(f"  底部边距：{prefs['subtitles']['margin_v']}px")
    
    print(f"\n🎵 音频设置:")
    print(f"  背景音乐音量：{prefs['audio']['background_music_volume']*100:.0f}%")
    print(f"  淡入/淡出：{prefs['audio']['fade_in_duration']}秒")
    
    print(f"\n📊 学习记录:")
    history = prefs["learning"]["adjustment_history"]
    if history:
        print(f"  共记录 {len(history)} 次调整")
        print("  最近 3 次:")
        for adj in history[-3:]:
            print(f"    - {adj['timestamp'][:16]}: {adj['description']}")
    else:
        print("  暂无调整记录")
    
    print("="*60 + "\n")

def reset_preferences():
    """重置偏好"""
    save_preferences(DEFAULT_PREFERENCES.copy())
    print("✅ 偏好已重置为默认值")

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        cmd = sys.argv[1]
        if cmd == "show":
            show_preferences()
        elif cmd == "reset":
            reset_preferences()
        elif cmd == "test":
            code, prefs = apply_preferences_to_script()
            print(code)
    else:
        show_preferences()
