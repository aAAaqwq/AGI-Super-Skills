#!/usr/bin/env python3
"""
偏好管理命令行工具
用法：
  python3 manage_preferences.py show    - 查看当前偏好
  python3 manage_preferences.py reset   - 重置偏好
  python3 manage_preferences.py set     - 交互式设置
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from preference_learner import show_preferences, reset_preferences, load_preferences, save_preferences, deep_merge

def interactive_set():
    """交互式设置偏好"""
    prefs = load_preferences()
    
    print("\n🎯 交互式偏好设置")
    print("=" * 60)
    print("直接回车保持当前值，输入新值修改\n")
    
    # 视频设置
    print("📹 视频设置:")
    new_val = input(f"  目标时长 (当前 {prefs['video']['target_duration']}秒): ")
    if new_val:
        prefs["video"]["target_duration"] = float(new_val)
    
    # 字幕设置
    print("\n📝 字幕设置:")
    new_val = input(f"  横屏字体大小 (当前 {prefs['subtitles']['horizontal_font_size']}px): ")
    if new_val:
        prefs["subtitles"]["horizontal_font_size"] = int(new_val)
    
    new_val = input(f"  竖屏字体大小 (当前 {prefs['subtitles']['vertical_font_size']}px): ")
    if new_val:
        prefs["subtitles"]["vertical_font_size"] = int(new_val)
    
    new_val = input(f"  底部边距 (当前 {prefs['subtitles']['margin_v']}px): ")
    if new_val:
        prefs["subtitles"]["margin_v"] = int(new_val)
    
    # 音频设置
    print("\n🎵 音频设置:")
    new_val = input(f"  背景音乐音量 (当前 {prefs['audio']['background_music_volume']*100:.0f}%): ")
    if new_val:
        prefs["audio"]["background_music_volume"] = float(new_val) / 100
    
    new_val = input(f"  淡入淡出时长 (当前 {prefs['audio']['fade_in_duration']}秒): ")
    if new_val:
        prefs["audio"]["fade_in_duration"] = int(new_val)
        prefs["audio"]["fade_out_duration"] = int(new_val)
    
    # 保存
    save_preferences(prefs)
    
    print("\n✅ 偏好已更新！")
    show_preferences()

if __name__ == "__main__":
    if len(sys.argv) > 1:
        cmd = sys.argv[1]
        if cmd == "show":
            show_preferences()
        elif cmd == "reset":
            reset_preferences()
        elif cmd == "set":
            interactive_set()
        else:
            print(f"❌ 未知命令：{cmd}")
            print("用法：python3 manage_preferences.py [show|reset|set]")
    else:
        show_preferences()
