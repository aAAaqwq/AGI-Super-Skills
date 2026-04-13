#!/usr/bin/env python3
"""
建筑视频剪辑工作流 - 自进化版
功能：语音转录字幕 + 混合背景音乐 + 烧录字幕
特点：自动学习用户偏好，越用越懂你
"""

import subprocess
import sys
import os
from pathlib import Path

# 导入偏好学习器
sys.path.insert(0, str(Path(__file__).parent))
from preference_learner import load_preferences, record_adjustment

# 加载用户偏好
prefs = load_preferences()

# 配置
BASE_DIR = Path(__file__).parent.parent / "data"
TEMP_DIR = BASE_DIR / "temp_edit"
AUDIO_FILE = Path("/Users/baushua/Desktop/新录音 74.m4a")
VIDEO_DIR = BASE_DIR / "m1"
VIDEO_FILE = TEMP_DIR / "merged.mp4"
OUTPUT_FILE = BASE_DIR / "edited_video_final_with_subtitles.mp4"
OUTPUT_FILE_VERTICAL = BASE_DIR / "edited_video_final_with_subtitles_3x4.mp4"

# 从偏好中读取配置
TARGET_DURATION = prefs["video"]["target_duration"]
HORIZONTAL_FONT_SIZE = prefs["subtitles"]["horizontal_font_size"]
VERTICAL_FONT_SIZE = prefs["subtitles"]["vertical_font_size"]
FONT_NAME = prefs["subtitles"]["font_name"]
AUTO_WRAP = prefs["subtitles"]["auto_wrap"]
MARGIN_V = prefs["subtitles"]["margin_v"]
BG_MUSIC_VOLUME = prefs["audio"]["background_music_volume"]
FADE_DURATION = prefs["audio"]["fade_in_duration"]

def run_cmd(cmd, description=""):
    """运行命令并打印进度"""
    if description:
        print(f"🎬 {description}...")
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"❌ 失败：{result.stderr}")
        return False
    return True

def merge_videos():
    """合并多个视频文件并压缩到目标时长"""
    print(f"\n🎬 步骤 0: 合并视频并压缩到 {TARGET_DURATION} 秒")
    
    # 获取所有 mp4 文件并排序
    video_files = sorted(VIDEO_DIR.glob("*.mp4"))
    print(f"  找到 {len(video_files)} 个视频文件")
    
    # 创建文件列表
    list_file = TEMP_DIR / "video_list.txt"
    with open(list_file, 'w') as f:
        for vf in video_files:
            f.write(f"file '{vf}'\n")
    
    # 使用 ffmpeg 合并并加速到目标时长
    cmd = f'ffmpeg -y -f concat -safe 0 -i "{list_file}" -filter_complex "[0:v]setpts=PTS*{TARGET_DURATION}/30.25[v]" -map "[v]" -c:a aac -shortest "{VIDEO_FILE}" -loglevel error'
    if run_cmd(cmd, "合并并压缩视频"):
        print(f"  ✅ 合并完成：{VIDEO_FILE} ({TARGET_DURATION}秒)")
        return True
    return False

def transcribe_audio():
    """生成字幕（使用用户确认的文字）"""
    print("\n🎙️ 步骤 1: 生成字幕")
    
    # 用户确认的字幕内容
    subtitles_text = [
        "这六个改造项目分别是从废弃学校",
        "仿古建筑、红砖瓦房、单层厂房和乡村自建房改造而来",
        "通过极简的设计手法和低造价改造策略",
        "让老房子重获新生",
        "同时适应当下的艺术审美和市场需求",
    ]
    
    # 获取音频时长
    result = subprocess.run(
        f'ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 "{AUDIO_FILE}"',
        shell=True, capture_output=True, text=True
    )
    total_duration = float(result.stdout.strip())
    print(f"  音频时长：{total_duration:.2f}秒")
    
    # 根据字数精确分配时长（按语速比例）
    # 总字数：15+24+17+8+16 = 80 字，19.35 秒，约 4.1 字/秒
    # 每句时长：15/4.1=3.65, 24/4.1=5.85, 17/4.1=4.15, 8/4.1=1.95, 16/4.1=3.9
    timestamps = [
        (0.00, 3.65),
        (3.65, 9.50),
        (9.50, 13.65),
        (13.65, 15.60),
        (15.60, total_duration),
    ]
    
    # 生成 SRT 字幕文件
    srt_path = TEMP_DIR / "subtitles.srt"
    with open(srt_path, 'w', encoding='utf-8') as f:
        for i, (text, (start, end)) in enumerate(zip(subtitles_text, timestamps), 1):
            def format_time(t):
                hours = int(t // 3600)
                minutes = int((t % 3600) // 60)
                seconds = int(t % 60)
                millis = int((t % 1) * 1000)
                return f"{hours:02d}:{minutes:02d}:{seconds:02d},{millis:03d}"
            
            f.write(f"{i}\n")
            f.write(f"{format_time(start)} --> {format_time(end)}\n")
            f.write(f"{text}\n\n")
            print(f"  [{format_time(start)} --> {format_time(end)}] {text}")
    
    print(f"✅ 字幕已保存到：{srt_path}")
    print(f"📊 共 {len(subtitles_text)} 条字幕")
    return True

def generate_background_music():
    """生成轻音乐背景"""
    print("\n🎵 步骤 2: 生成轻音乐背景")
    
    duration = TARGET_DURATION
    print(f"  目标时长：{duration:.2f}秒")
    
    # 生成柔和的钢琴风格背景音乐（多音轨和弦）
    music_file = TEMP_DIR / "background_music.aac"
    cmd = (f'ffmpeg -y -f lavfi -i "sine=frequency=523:duration={duration}" '
           f'-f lavfi -i "sine=frequency=659:duration={duration}" '
           f'-f lavfi -i "sine=frequency=784:duration={duration}" '
           f'-filter_complex "[0:a][1:a][2:a]amix=inputs=3:duration=longest,afade=t=in:st=0:d={FADE_DURATION},afade=t=out:st={duration-FADE_DURATION}:d={FADE_DURATION},volume={BG_MUSIC_VOLUME}" '
           f'-c:a aac "{music_file}" -loglevel error')
    
    if run_cmd(cmd, "生成背景音乐"):
        print(f"  ✅ 音乐已生成：{music_file}")
        return True
    return False

def mix_audio():
    """混合录音和背景音乐"""
    print("\n🎼 步骤 3: 混合录音与背景音乐")
    
    mixed_file = TEMP_DIR / "mixed_audio.aac"
    cmd = (f'ffmpeg -y -i "{AUDIO_FILE}" -i "{TEMP_DIR}/background_music.aac" '
           f'-filter_complex "[0:a][1:a]amix=inputs=2:duration=first:dropout_transition=3" '
           f'-c:a aac -shortest "{mixed_file}" -loglevel error')
    
    if run_cmd(cmd, "混合音轨"):
        print(f"  ✅ 混合完成：{mixed_file}")
        return True
    return False

def add_subtitles_to_video():
    """添加字幕到视频（使用 ffmpeg-full + libass）"""
    print("\n📝 步骤 4: 烧录字幕到视频（横屏 16:9，720p）")
    
    # 使用 ffmpeg-full（支持 libass 字幕）
    ffmpeg_full = "/usr/local/Cellar/ffmpeg-full/8.0.1_3/bin/ffmpeg"
    
    # 字幕样式：从偏好读取，输出 720p (1280x720)
    wrap_style = "2" if not AUTO_WRAP else "0"  # 2=强制单行，0=自动换行
    cmd = (f'{ffmpeg_full} -y -i "{VIDEO_FILE}" -i "{TEMP_DIR}/mixed_audio.aac" '
           f'-vf "scale=1280:720,subtitles={TEMP_DIR}/subtitles.srt:force_style=\'FontName={FONT_NAME},FontSize={HORIZONTAL_FONT_SIZE},PrimaryColour=&HFFFFFF,SecondaryColour=&HFFFFFF,OutlineColour=&H00000000,BackColour=&H00000000,BorderStyle=1,Outline=0,Shadow=0,Alignment=2,MarginV={MARGIN_V},WrapStyle={wrap_style}\'" '
           f'-c:a copy "{OUTPUT_FILE}"')
    
    if run_cmd(cmd, "烧录字幕 (横屏 720p)"):
        print(f"  ✅ 视频已生成：{OUTPUT_FILE} (1280x720)")
        return True
    return False

def create_vertical_version():
    """创建 3:4 竖屏版本"""
    print("\n📱 步骤 5: 生成 3:4 竖屏版本（720p）")
    
    ffmpeg_full = "/usr/local/Cellar/ffmpeg-full/8.0.1_3/bin/ffmpeg"
    
    # 3:4 比例 = 720x960（720p 竖屏），从横屏 16:9 裁剪中间部分
    # 字幕样式：从偏好读取
    wrap_style = "2" if not AUTO_WRAP else "0"  # 2=强制单行，0=自动换行
    cmd = (f'{ffmpeg_full} -y -i "{VIDEO_FILE}" -i "{TEMP_DIR}/mixed_audio.aac" '
           f'-vf "crop=ih*9/16:ih, scale=720:960, subtitles={TEMP_DIR}/subtitles.srt:force_style=\'FontName={FONT_NAME},FontSize={VERTICAL_FONT_SIZE},PrimaryColour=&HFFFFFF,SecondaryColour=&HFFFFFF,OutlineColour=&H00000000,BackColour=&H00000000,BorderStyle=1,Outline=0,Shadow=0,Alignment=2,MarginV={MARGIN_V},WrapStyle={wrap_style}\'" '
           f'-c:a copy "{OUTPUT_FILE_VERTICAL}"')
    
    if run_cmd(cmd, "生成竖屏版本 (720p)"):
        print(f"  ✅ 竖屏视频已生成：{OUTPUT_FILE_VERTICAL} (720x960)")
        return True
    return False

def main():
    print("=" * 60)
    print("🏗️  铭哥的建筑视频剪辑工作流（自进化版）")
    print("=" * 60)
    
    # 显示当前偏好配置
    print(f"\n🧠 当前偏好配置:")
    print(f"  视频时长：{TARGET_DURATION}秒 | 横屏字体：{HORIZONTAL_FONT_SIZE}px | 竖屏字体：{VERTICAL_FONT_SIZE}px")
    print(f"  自动换行：{'是' if AUTO_WRAP else '否'} | 背景音乐：{BG_MUSIC_VOLUME*100:.0f}%")
    
    # 检查文件
    if not AUDIO_FILE.exists():
        print(f"❌ 找不到录音文件：{AUDIO_FILE}")
        return False
    
    if not VIDEO_DIR.exists():
        print(f"❌ 找不到视频文件夹：{VIDEO_DIR}")
        return False
    
    TEMP_DIR.mkdir(exist_ok=True)
    
    # 执行流程
    steps = [
        ("合并视频", merge_videos),
        ("语音转录", transcribe_audio),
        ("背景音乐", generate_background_music),
        ("混合音轨", mix_audio),
        ("烧录字幕 (横屏)", add_subtitles_to_video),
        ("生成竖屏版本", create_vertical_version),
    ]
    
    for step_name, step_func in steps:
        if not step_func():
            print(f"\n❌ {step_name} 失败，已停止")
            return False
    
    print("\n" + "=" * 60)
    print("✅ 全部完成！")
    print("=" * 60)
    print(f"\n📁 输出文件：{OUTPUT_FILE}")
    
    # 显示文件信息
    if OUTPUT_FILE.exists():
        size = OUTPUT_FILE.stat().st_size / 1024 / 1024
        result = subprocess.run(
            f'ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 "{OUTPUT_FILE}"',
            shell=True, capture_output=True, text=True
        )
        duration = float(result.stdout.strip())
        print(f"📊 大小：{size:.1f}MB")
        print(f"🎬 时长：{duration:.2f}秒")
    
    # 记录本次运行
    record_adjustment(
        description="视频剪辑完成",
        category="workflow",
        changes={
            "target_duration": TARGET_DURATION,
            "horizontal_font_size": HORIZONTAL_FONT_SIZE,
            "vertical_font_size": VERTICAL_FONT_SIZE,
            "auto_wrap": AUTO_WRAP,
        }
    )
    
    print("\n💡 提示：运行 `python3 scripts/preference_learner.py show` 查看偏好")
    print("   运行 `python3 scripts/preference_learner.py reset` 重置偏好")
    
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
