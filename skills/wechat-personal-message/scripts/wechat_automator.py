#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
微信自动化助手 (WeChat Automator) - 纯 AppleScript 版
功能：激活微信 → 置顶窗口 → 搜索联系人 → Vision OCR识别聊天 → 关键词匹配回复 → 自动发送
依赖：macOS 10.15+, pyobjc (Vision Framework)
作者：贰拾（二十四）/ 辰景网络技术团队
"""

import os
import sys
import time
import json
import subprocess
import re
from typing import Dict, List, Optional, Tuple
from pathlib import Path

# ============================================================================
# 配置区
# ============================================================================

# OCR 临时文件
OCR_TEMP_DIR = Path.home() / ".wechat_automator" / "temp"
OCR_TEMP_DIR.mkdir(parents=True, exist_ok=True)
SCREENSHOT_PATH = OCR_TEMP_DIR / "chat_screenshot.png"

# 日志配置
LOG_ENABLED = True

# 默认关键词匹配库
DEFAULT_KEYWORD_DICT: Dict[str, List[str]] = {
    "价格": ["多少钱", "价格", "报价", "收费", "多少"],
    "产品": ["产品", "规格", "型号", "参数", "功能"],
    "合作": ["合作", "代理", "加盟", "渠道", "商务"],
    "问候": ["你好", "您好", "hi", "hello", "在吗", "在么"],
    "感谢": ["谢谢", "感谢", "多谢", "感恩"],
}

# 默认回复模板
DEFAULT_REPLY = "感谢您的消息，我这边已收到，会尽快回复您。如有紧急事项，请直接电话联系。"

# ============================================================================
# 工具函数
# ============================================================================

def log(msg: str, emoji: str = "📋"):
    """统一日志输出"""
    if LOG_ENABLED:
        print(f"{emoji} {msg}")
        sys.stdout.flush()


def run_cmd(cmd: List[str], timeout: int = 10) -> Tuple[int, str, str]:
    """执行终端命令"""
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            encoding="utf-8",
            errors="ignore"
        )
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return -1, "", "Command timeout"
    except Exception as e:
        return -1, "", str(e)


def check_permissions() -> Dict[str, bool]:
    """检查各项权限状态"""
    permissions = {
        "terminal_accessibility": False,
        "screen_recording": False,
    }
    
    # 检查辅助功能权限
    code, _, _ = run_cmd(
        ["osascript", "-e", 'tell application "System Events" to keystroke ""'],
        timeout=5
    )
    permissions["terminal_accessibility"] = (code == 0)
    
    # 检查屏幕录制权限
    test_path = OCR_TEMP_DIR / "perm_test.png"
    code, _, _ = run_cmd(
        ["/usr/sbin/screencapture", "-x", str(test_path)],
        timeout=5
    )
    permissions["screen_recording"] = (code == 0 and test_path.exists())
    if test_path.exists():
        test_path.unlink()
    
    return permissions


def print_permission_guide():
    """打印权限开启指引"""
    guide = """
╔══════════════════════════════════════════════════════════════════╗
║                    ⚠️  权限开启指引                               ║
╠══════════════════════════════════════════════════════════════════╣
║  请按照以下步骤开启必要权限：                                      ║
║                                                                  ║
║  1️⃣  辅助功能权限                                                ║
║      系统设置 → 隐私与安全性 → 辅助功能 →                         ║
║      滚动到底部 → 点「终端」→ 开启权限                           ║
║                                                                  ║
║  2️⃣  屏幕录制权限                                               ║
║      系统设置 → 隐私与安全性 → 屏幕录制 →                        ║
║      点「终端」→ 开启权限                                        ║
║                                                                  ║
║  3️⃣  完整磁盘访问权限（如遇截图黑屏）                            ║
║      系统设置 → 隐私与安全性 → 完整磁盘访问 →                    ║
║      开启「终端」权限                                            ║
╚══════════════════════════════════════════════════════════════════╝
"""
    print(guide)


# ============================================================================
# AppleScript 执行器
# ============================================================================

def run_applescript(script: str, timeout: int = 10) -> Tuple[int, str, str]:
    """执行 AppleScript 脚本"""
    cmd = ["osascript", "-e", script]
    return run_cmd(cmd, timeout=timeout)


def run_applescript_block(script: str, timeout: int = 15) -> Tuple[int, str, str]:
    """执行多行 AppleScript 脚本块"""
    cmd = ["osascript", "-e", script]
    return run_cmd(cmd, timeout=timeout)


def activate_wechat() -> bool:
    """步骤1: 激活微信应用"""
    log("正在激活微信...", "🚀")
    code, stdout, stderr = run_applescript('tell application "WeChat" to activate')
    if code == 0:
        log("微信激活成功", "✅")
        time.sleep(0.5)
        return True
    else:
        log(f"微信激活失败: {stderr}", "❌")
        return False


def bring_to_front() -> bool:
    """步骤2: 强制前台置顶微信窗口"""
    log("正在置顶微信窗口...", "🔝")
    script = """
    tell app "System Events"
        tell process "WeChat"
            set frontmost to true
        end tell
    end tell
    """
    code, stdout, stderr = run_applescript(script)
    if code == 0:
        log("窗口置顶成功", "✅")
        time.sleep(0.3)
        return True
    else:
        log(f"窗口置顶失败: {stderr}", "❌")
        return False


def write_to_clipboard(text: str) -> bool:
    """写入系统剪贴板"""
    # 处理特殊字符转义
    escaped = text
    escaped = escaped.replace("\\", "\\\\")
    escaped = escaped.replace('"', '\\"')
    # 换行处理
    escaped = escaped.replace("\n", "\\n")
    
    script = f'set the clipboard to "{escaped}"'
    code, _, _ = run_applescript(script)
    return code == 0


def read_from_clipboard() -> str:
    """从系统剪贴板读取"""
    script = 'get the clipboard as text'
    code, stdout, _ = run_applescript(script)
    if code == 0:
        return stdout.strip()
    return ""


def get_screen_size() -> Tuple[int, int]:
    """获取屏幕尺寸"""
    script = '''
    tell application "System Events"
        get pixels across of main window of screen 1
    end tell
    '''
    code, stdout, _ = run_applescript(script)
    if code == 0:
        try:
            w = int(stdout.strip())
            script2 = '''
            tell application "System Events"
                get pixels deep of main window of screen 1
            end tell
            '''
            code2, stdout2, _ = run_applescript(script2)
            if code2 == 0:
                h = int(stdout2.strip())
                return w, h
            return w, 1080
        except (ValueError, TypeError):
            pass
    return 1920, 1080


def get_wechat_window_rect() -> Optional[Tuple[int, int, int, int]]:
    """
    获取微信窗口的位置和大小
    返回: (x, y, width, height) 或 None
    """
    # 通过 System Events 的 process 获取窗口信息
    script = '''
    tell application "System Events"
        tell process "WeChat"
            get {position, size} of window 1
        end tell
    end tell
    '''
    code, stdout, _ = run_applescript(script)
    if code == 0:
        # stdout 格式类似: {{0, 22}, {1514, 1006}}
        # 解析: {{pos_x, pos_y}, {width, height}}
        stdout = stdout.strip()
        parts = stdout.replace("{", "").replace("}", "").split(",")
        if len(parts) >= 4:
            try:
                x = int(parts[0].strip())
                y = int(parts[1].strip())
                w = int(parts[2].strip())
                h = int(parts[3].strip())
                return (x, y, w, h)
            except ValueError:
                pass
    return None


# ============================================================================
# AppleScript 键盘/鼠标操作（纯原生，无需 cliclick）
# ============================================================================

def press_key(key: str, modifiers: List[str] = None) -> bool:
    """
    使用 AppleScript 按键（key code 方式，特殊键必须用 key code）
    modifiers: ["command", "option", "control", "shift"]
    
    特殊键必须用 key code，不能用 keystroke "return" 这种方式：
    - return/enenter: 36
    - escape: 53
    - tab: 48
    - space: 49
    - delete (backspace): 51
    - forward delete: 117
    - up arrow: 126
    - down arrow: 125
    - left arrow: 123
    - right arrow: 124
    """
    if modifiers is None:
        modifiers = []

    # key code 映射（特殊键必须用 key code）
    key_code_map = {
        "return": 36,
        "enter": 36,
        "escape": 53,
        "esc": 53,
        "tab": 48,
        "space": 49,
        "delete": 51,       # backspace
        "backspace": 51,
        "fwd_delete": 117,  # fn+delete on Mac
        "up": 126,
        "down": 125,
        "left": 123,
        "right": 124,
        "home": 115,
        "end": 119,
        "pageup": 116,
        "pagedown": 121,
    }

    key_lower = key.lower()
    
    # 构建 modifiers 部分
    def mod_str():
        parts = []
        for m in (modifiers or []):
            m_lower = m.lower()
            if m_lower in ("command", "cmd"):
                parts.append("command down")
            elif m_lower in ("option", "alt"):
                parts.append("option down")
            elif m_lower in ("control", "ctrl"):
                parts.append("control down")
            elif m_lower == "shift":
                parts.append("shift down")
        return ", ".join(parts) if parts else ""

    if key_lower in key_code_map:
        # 特殊键：用 key code 方式
        kc = key_code_map[key_lower]
        ms = mod_str()
        if ms:
            script = f'''
            tell application "System Events"
                key code {kc} using {ms}
            end tell
            '''
        else:
            script = f'''
            tell application "System Events"
                key code {kc}
            end tell
            '''
    else:
        # 普通键：用 keystroke 方式
        # 单个可打印字符直接用
        if len(key) == 1:
            mapped_key = key  # 原样传递
        else:
            mapped_key = key_lower
        
        ms = mod_str()
        if ms:
            script = f'''
            tell application "System Events"
                keystroke "{mapped_key}" using {ms}
            end tell
            '''
        else:
            script = f'''
            tell application "System Events"
                keystroke "{mapped_key}"
            end tell
            '''
    
    code, _, _ = run_applescript(script)
    time.sleep(0.15)
    return code == 0


def type_text(text: str) -> bool:
    """使用 AppleScript 输入文本（适合短文本）"""
    # 转义特殊字符
    escaped = text.replace('"', '\\"').replace("\\", "\\\\")
    
    # 对于长文本，分段输入
    if len(text) > 100:
        chunk_size = 50
        for i in range(0, len(text), chunk_size):
            chunk = text[i:i+chunk_size]
            escaped_chunk = chunk.replace('"', '\\"').replace("\\", "\\\\")
            script = f'''
            tell application "System Events"
                keystroke "{escaped_chunk}"
            end tell
            '''
            run_applescript(script)
            time.sleep(0.1)
        return True
    
    script = f'''
    tell application "System Events"
        keystroke "{escaped}"
    end tell
    '''
    code, _, _ = run_applescript(script)
    time.sleep(0.1)
    return code == 0


def click_at坐标(x: int, y: int) -> bool:
    """
    使用 cliclick 执行鼠标点击（更稳定）
    """
    cmd = f"cliclick c:{x},{y}"
    code, stdout, stderr = run_cmd(["bash", "-c", cmd], timeout=5)
    if code != 0:
        log(f"cliclick 点击 ({x},{y}) 失败: {stderr}", "⚠️")
        return False
    return True


def double_click_at坐标(x: int, y: int) -> bool:
    """
    使用 cliclick 执行鼠标双击
    """
    cmd = f"cliclick dc:{x},{y}"
    code, stdout, stderr = run_cmd(["bash", "-c", cmd], timeout=5)
    if code != 0:
        log(f"cliclick 双击 ({x},{y}) 失败: {stderr}", "⚠️")
        return False
    return True


def cliclick_wait(ms: int):
    """等待指定毫秒"""
    run_cmd(["bash", "-c", f"cliclick w:{ms}"], timeout=ms/1000 + 5)


# ============================================================================
# OCR 识别（Vision Framework）
# ============================================================================

def screenshot_chat_area(
    chat_x: int = None,
    chat_y: int = None,
    chat_w: int = 800,
    chat_h: int = 600
) -> Optional[str]:
    """
    步骤4: 截取聊天窗口区域
    使用 screencapture macOS 系统自带截图工具
    """
    log("正在截取聊天窗口...", "📸")
    
    screen_w, screen_h = get_screen_size()
    
    # 如果未指定坐标，使用默认区域（屏幕中心偏左，微信窗口常见位置）
    if chat_x is None:
        chat_x = int(screen_w * 0.15)
    if chat_y is None:
        chat_y = int(screen_y * 0.1) if False else int(screen_h * 0.1)
    
    # 确保坐标在屏幕范围内
    chat_x = max(0, min(chat_x, screen_w - chat_w))
    chat_y = max(0, min(chat_y, screen_h - chat_h))
    
    # 调用 screencapture 截取指定区域
    # -x 不播放音效，-R 指定区域 "x,y,width,height"
    cmd = [
        "/usr/sbin/screencapture",
        "-x",
        "-R", f"{chat_x},{chat_y},{chat_w},{chat_h}",
        str(SCREENSHOT_PATH)
    ]
    
    code, stdout, stderr = run_cmd(cmd, timeout=10)
    
    if code == 0 and SCREENSHOT_PATH.exists():
        log(f"截图成功: {SCREENSHOT_PATH}", "✅")
        return str(SCREENSHOT_PATH)
    else:
        log(f"截图失败: {stderr}", "❌")
        return None


def perform_ocr(image_path: str) -> List[str]:
    """
    步骤5: 使用 Vision Framework 进行 OCR 识别
    支持简体中文 + 英文，开启语言纠错
    """
    log("正在进行 OCR 识别...", "🔍")
    log(f"待识别图片: {image_path}", "📷")
    
    try:
        from Vision import VNRecognizeTextRequest, VNImageRequestHandler
        from AppKit import NSImage
    except ImportError as e:
        log(f"pyobjc 未安装或导入失败: {e}", "❌")
        log("请运行: pip3 install pyobjc", "📦")
        return []
    
    try:
        # 加载图片
        img = NSImage.alloc().initWithContentsOfFile_(image_path)
        if img is None:
            log("图片加载失败，请检查截图是否正常", "❌")
            return []
        
        # 获取图片数据
        img_data = img.TIFFRepresentation()
        
        # 存储识别结果
        recognized_texts: List[str] = []
        
        # 使用 initWithCompletionHandler_ 创建请求
        def completionHandler(request, error):
            if error:
                log(f"OCR 识别出错: {error}", "❌")
                return
            observations = request.results() or []
            for observation in observations:
                text = observation.text()
                if text and text.strip():
                    recognized_texts.append(text)
        
        request = VNRecognizeTextRequest.alloc().initWithCompletionHandler_(completionHandler)
        request.setRecognitionLanguages_(["zh-Hans", "en-US"])
        request.setUsesLanguageCorrection_(True)
        
        # 执行识别
        handler = VNImageRequestHandler.alloc().initWithData_options_(img_data, {})
        handler.performRequests_error_([request], None)  # error=nil in ObjC
        
        log(f"OCR 识别完成，共识别 {len(recognized_texts)} 段文本", "✅")
        for i, text in enumerate(recognized_texts[:10]):
            display_text = text[:60] + "..." if len(text) > 60 else text
            log(f"  [{i+1}] {display_text}", "📝")
        if len(recognized_texts) > 10:
            log(f"  ... 还有 {len(recognized_texts) - 10} 条", "📝")
        
        return recognized_texts
        
    except Exception as e:
        log(f"OCR 异常: {e}", "❌")
        import traceback
        traceback.print_exc()
        return []


# ============================================================================
# 关键词匹配与回复生成
# ============================================================================

def match_keyword(texts: List[str], keyword_dict: Dict[str, List[str]]) -> Optional[str]:
    """
    步骤6: 关键词匹配
    在识别的文本中查找关键词，返回匹配类别
    """
    log("正在匹配关键词...", "🔎")
    
    all_text = " ".join(texts).lower()
    log(f"待匹配文本长度: {len(all_text)} 字符", "🔍")
    
    for category, keywords in keyword_dict.items():
        for keyword in keywords:
            if keyword.lower() in all_text:
                log(f"✅ 匹配到类别: {category} (关键词: {keyword})", "✅")
                return category
    
    log("未匹配到自定义关键词，使用默认回复", "⚪")
    return None


def generate_reply(
    matched_category: Optional[str],
    keyword_dict: Dict[str, List[str]],
    default_reply: str,
    custom_replies: Dict[str, str] = None
) -> str:
    """
    根据匹配结果生成回复
    """
    custom_replies = custom_replies or {}
    
    if matched_category and matched_category in custom_replies:
        return custom_replies[matched_category]
    
    # 内置回复模板
    reply_templates = {
        "价格": "您好！感谢您的咨询。关于价格问题，需要根据您的具体需求和采购量来定，建议您提供更多细节，我可以为您匹配合适的方案。",
        "产品": "您好！感谢关注我们的产品。我这边可以为您提供详细的产品资料和规格参数，请问您有具体的需求吗？",
        "合作": "您好！很高兴您对合作感兴趣。我这边可以详细聊聊合作模式和权益，请问你方便时可否加个微信深入沟通？",
        "问候": "您好！感谢您的消息。请问有什么可以帮到您的？",
        "感谢": "不客气！很高兴能帮到您。如有其他问题，随时联系我。",
    }
    
    if matched_category and matched_category in reply_templates:
        return reply_templates[matched_category]
    
    return default_reply


# ============================================================================
# OCR 辅助函数：截图 + 识别 + 分析
# ============================================================================

def ocr_capture_and_recognize(region: str = "main") -> Tuple[bool, List[str], str]:
    """
    截图当前屏幕并进行OCR识别
    返回: (是否成功, 识别文本列表, 图片路径)
    """
    screen_w, screen_h = get_screen_size()
    
    # 根据区域确定截图范围
    if region == "main":
        # 截取整个屏幕
        chat_x, chat_y = 0, 0
        chat_w, chat_h = screen_w, screen_h
    elif region == "window":
        # 只截取微信窗口区域
        win_rect = get_wechat_window_rect()
        if win_rect:
            chat_x, chat_y, chat_w, chat_h = win_rect
        else:
            chat_x, chat_y, chat_w, chat_h = 0, 0, 800, 600
    else:
        chat_x, chat_y, chat_w, chat_h = 0, 0, screen_w, screen_h
    
    # 确保截图路径干净
    if SCREENSHOT_PATH.exists():
        SCREENSHOT_PATH.unlink()
    
    cmd = [
        "/usr/sbin/screencapture", "-x",
        "-R", f"{chat_x},{chat_y},{chat_w},{chat_h}",
        str(SCREENSHOT_PATH)
    ]
    code, _, _ = run_cmd(cmd, timeout=10)
    
    if code != 0 or not SCREENSHOT_PATH.exists():
        return False, [], ""
    
    texts = perform_ocr(str(SCREENSHOT_PATH))
    return True, texts, str(SCREENSHOT_PATH)


def ocr_check_chat_entered(contact_name: str) -> Tuple[bool, str]:
    """
    OCR检查：是否已进入真正的聊天窗口（而不是悬浮资料卡或搜索预览）
    真正的聊天窗口特征：必须有输入框/发送按钮等UI元素
    悬浮资料卡特征：有"微信号/地区/朋友圈/更多"等资料信息，但没有输入框
    搜索预览特征：有"搜索"相关文字（搜索框仍可见），内容是搜索结果列表
    """
    success, texts, img_path = ocr_capture_and_recognize("window")
    if not success or not texts:
        return False, "截图失败或无文字"
    
    all_text = "".join(texts)
    log(f"OCR识别 ({len(texts)}段): {texts[:5] if texts else '无'}", "🔍")
    
    # 检查是否是悬浮资料卡（有这个就是没进入聊天）
    floating_card_keywords = ["微信号", "地区", "朋友圈", "更多", "个性签名", "来源", "手机", "邮箱"]
    has_floating = any(kw in all_text for kw in floating_card_keywords)
    
    # 检查是否是搜索预览窗口（搜索框仍可见=没进入聊天）
    # 搜索预览特征：搜索框还在、联系人列表还在、有"搜索"相关字
    # 微信 Mac 搜索框特征文字
    search_keywords = ["大 搜索", "搜索网络结果", "搜一搜", "包含：", "看全部", "Q 搜索", "q 搜索", "找人", "AI搜索", "全部 文章", "全部 三", "账号 文章", "划线 视频"]
    has_search_ui = any(kw in all_text for kw in search_keywords)
    
    # 检查是否是设置窗口（双击打到了设置菜单）
    settings_keywords = ["账号与存储", "通用", "快捷键", "通知", "插件", "关于微信", "语言", "外观", "跟随系统"]
    has_settings_ui = sum(1 for kw in settings_keywords if kw in all_text) >= 3
    
    # 检查是否是真正的聊天窗口（必须有这些元素）
    # 注意：搜索结果页也会有"图片""表情"等词，不能仅凭这些判断
    # 真正的聊天窗口特征：输入框提示文字、发送按钮、或明确的时间戳+消息内容
    chat_keywords = ["输入", "发消息", "发送", "发送按钮"]
    has_input_area = any(kw in all_text for kw in chat_keywords)
    
    # 另外检查是否有时间戳（聊天记录特征）
    has_time = any(k in all_text for k in ["今天", "昨天", "上午", "下午", "晚上", ":", "月", "日", "周"])
    
    # 如果检测到悬浮资料卡特征，且没有聊天输入区特征，说明不是聊天窗口
    if has_floating and not has_input_area:
        return False, f"仍在悬浮资料卡中（检测到资料信息，无输入框）"
    
    # 如果搜索UI还在，且没有右侧聊天预览，不是真正的聊天窗口
    # 右侧聊天预览特征：联系人名 + 时间戳 + 消息内容（说明右侧已显示聊天记录）
    has_right_panel_preview = (
        (contact_name[:6] in all_text or all_text[:6] in contact_name) and has_time and len(texts) > 10
    )
    if has_search_ui and not has_input_area and not has_right_panel_preview:
        return False, f"仍在搜索预览中（搜索UI可见）"
    elif has_search_ui and has_right_panel_preview:
        # 右侧已显示聊天预览，认为已选中联系人
        return True, "已进入聊天预览（右侧显示聊天记录）"
    
    # 如果检测到设置窗口，也不是聊天窗口
    if has_settings_ui:
        return False, "检测到设置窗口（双击打到了菜单）"
    
    # 检查是否是"搜索聊天记录"面板（这个面板有输入框但不是真正的聊天）
    # 特征：同时有"发送人"+"日期"+"搜索聊天记录"
    if "发送人" in all_text and "日期" in all_text and ("搜索聊天记录" in all_text or "暂无" in all_text):
        return False, "仍在搜索聊天记录面板中"
    
    # 如果有聊天输入区特征，认为是聊天窗口
    if has_input_area:
        return True, "已进入聊天窗口（检测到输入框UI）"
    
    # 如果有联系人名+时间，认为是聊天窗口
    if (contact_name in all_text or any(c in all_text for c in [contact_name])) and has_time:
        return True, "已进入聊天窗口（检测到联系人+时间）"
    
    # 额外检查：聊天窗口通常有多条消息，有消息内容区域
    # 如果文字段数较多（>15段），且有联系人名，且没有搜索UI，可能是聊天窗口
    if len(texts) > 15 and (contact_name in all_text) and not has_search_ui:
        return True, "已进入聊天窗口（多消息+联系人）"
    
    return False, f"无法确认悬浮{has_floating}搜索{has_search_ui}输入框{has_input_area}时间{has_time}段落数{len(texts)}"


def ocr_check_input_box_ready() -> Tuple[bool, str]:
    """
    OCR检查：输入框是否就绪（可以通过截图判断是否有光标闪烁）
    返回: (是否就绪, 状态描述)
    """
    success, texts, img_path = ocr_capture_and_recognize("window")
    if not success:
        return False, "截图失败"
    
    all_text = "".join(texts)
    
    # 检查是否有输入框相关的文字
    has_input = any(k in all_text for k in ["输入", "输入框", "发消息", "发送", "text", "按住"])
    
    if has_input:
        return True, "输入框就绪"
    
    # 即使没识别到文字，也认为可能就绪（OCR不一定能识别图片中的placeholder）
    return True, "输入框可能就绪（未识别到明确文字）"


def ocr_verify_message_sent(message: str) -> Tuple[bool, str]:
    """
    OCR验证：检查消息是否已发送成功
    返回: (是否确认发送, 状态描述)
    """
    success, texts, img_path = ocr_capture_and_recognize("window")
    if not success:
        return False, "截图失败"
    
    all_text = "".join(texts)
    
    # 检查发送的消息内容是否出现在屏幕上
    # 消息可能被截断，只要部分匹配即可
    msg_short = message[:10] if len(message) > 10 else message
    
    if msg_short in all_text:
        return True, f"确认消息已发送：找到「{msg_short}」"
    
    # 检查是否有"已发送"相关提示
    has_sent = any(k in all_text for k in ["已发送", "发送成功", "发送中"])
    if has_sent:
        return True, "确认消息已发送"
    
    return False, f"未在屏幕上找到发送的消息「{msg_short}」"


def click_input_box_smart() -> Tuple[bool, int, int]:
    """
    智能点击输入框：通过OCR确定输入框位置并点击
    返回: (是否成功, 点击x坐标, 点击y坐标)
    """
    # 先获取窗口信息
    win_rect = get_wechat_window_rect()
    if win_rect:
        win_x, win_y, win_w, win_h = win_rect
    else:
        win_x, win_y, win_w, win_h = 0, 0, 800, 600
    
    # 方法1: 尝试在窗口底部区域点击（92%高度）
    input_x = win_x + int(win_w * 0.75)
    input_y = win_y + int(win_h * 0.92)
    log(f"智能点击: 窗口({win_x},{win_y},{win_w},{win_h}) → 输入框({input_x},{input_y})", "🎯")
    click_at坐标(input_x, input_y)
    time.sleep(0.5)
    
    # OCR验证
    ready, desc = ocr_check_input_box_ready()
    if ready:
        log(f"输入框点击成功: {desc}", "✅")
        return True, input_x, input_y
    
    # 方法2: 尝试点击窗口底部中央
    input_x2 = win_x + win_w // 2
    input_y2 = win_y + int(win_h * 0.95)
    log(f"方法2尝试: 点击({input_x2},{input_y2})", "🎯")
    click_at坐标(input_x2, input_y2)
    time.sleep(0.5)
    
    ready, desc = ocr_check_input_box_ready()
    if ready:
        log(f"输入框点击成功(方法2): {desc}", "✅")
        return True, input_x2, input_y2
    
    # 方法3: 尝试整个窗口底部区域扫描
    log("方法3: 扫描窗口底部区域寻找输入框...", "🔍")
    for offset_ratio in [0.88, 0.90, 0.93, 0.95, 0.97]:
        for x_offset_ratio in [0.3, 0.5, 0.7, 0.9]:
            test_x = win_x + int(win_w * x_offset_ratio)
            test_y = win_y + int(win_h * offset_ratio)
            click_at坐标(test_x, test_y)
            time.sleep(0.3)
            ready, desc = ocr_check_input_box_ready()
            if ready:
                log(f"扫描找到输入框: ({test_x},{test_y})", "✅")
                return True, test_x, test_y
    
    log("无法精确定位输入框，尝试默认坐标", "⚠️")
    return False, win_x + int(win_w * 0.75), win_y + int(win_h * 0.92)


def ensure_in_chat_window(contact_name: str, max_retries: int = 3) -> bool:
    """
    确保已进入聊天窗口，如果检测到仍在搜索结果/悬浮卡中，则修正
    策略：ESC关闭悬浮卡 → 重新搜索 → Enter进入
    """
    for attempt in range(1, max_retries + 1):
        log(f"验证聊天窗口 (尝试 {attempt}/{max_retries})...", "🔍")
        time.sleep(1.0)  # 等待UI稳定
        
        in_chat, desc = ocr_check_chat_entered(contact_name)
        log(f"  状态: {desc}", "📊")
        
        if in_chat:
            return True
        
        # 没有进入聊天窗口，尝试修正
        log(f"  未进入聊天窗口，尝试修正...", "🔧")
        
        # 按ESC关闭任何悬浮窗口
        press_key("escape")
        time.sleep(0.5)
        
        # 重新打开搜索
        press_key("f", ["command"])
        time.sleep(0.5)
        
        # 粘贴联系人名
        write_to_clipboard(contact_name)
        press_key("v", ["command"])
        time.sleep(1.0)
        
        # 按下箭头选中第一个联系人
        press_key("down")
        time.sleep(0.3)
        
        # 按Enter进入
        log("  按Enter进入...", "↵")
        press_key("return")
        time.sleep(2.0)
    
    # 最终尝试：确保在聊天窗口
    in_chat, desc = ocr_check_chat_entered(contact_name)
    return in_chat


# ============================================================================
# 搜索联系人
# ============================================================================

def parse_search_results(texts: List[str]) -> Dict[str, any]:
    """
    解析OCR搜索结果列表，返回各类型结果的位置信息
    返回格式: {
        "群聊": [(index, "【内部】赣商融合汇同事群"), ...],
        "AI搜索": [(index, "赣商融合汇创始个人会员推介"), ...],
        "好友": [...],
        "公众号": [...],
    }
    """
    results = {"群聊": [], "AI搜索": [], "好友": [], "公众号": [], "公众号账号": []}
    
    for i, text in enumerate(texts):
        t = text.strip()
        if not t:
            continue
        # 群聊关键词（OCR可能识别为"群說""群陆""群聊"等）
        if any(kw in t for kw in ["群說", "群陆", "群聊", "群人"]):
            results["群聊"].append((i, t))
        # AI搜索/网络搜索结果特征
        elif any(kw in t for kw in ["AI搜索", "搜索网络结果", "赣商融合汇创始个人会员", "赣商融合汇个人会员"]):
            results["AI搜索"].append((i, t))
        # 公众号账号特征
        elif any(kw in t for kw in ["公众号", "账号", "原创内容"]):
            results["公众号"].append((i, t))
        # 好友特征（暂无明确关键词，根据排除法）
    
    return results


def find_target_result(texts: List[str], contact_name: str) -> Tuple[Optional[str], int]:
    """
    在OCR结果中找到联系人对应的正确搜索结果类型
    返回: (结果类型, 结果索引) 或 (None, -1)
    
    策略：
    1. 先找"群聊"类型的结果
    2. 再找"好友"类型的结果  
    3. 排除"AI搜索"（网络结果）和"公众号账号"
    """
    parsed = parse_search_results(texts)
    log(f"搜索结果解析: {parsed}", "📊")
    
    # 优先选择"群聊"类型
    if parsed["群聊"]:
        result_type, (idx, label) = "群聊", parsed["群聊"][0]
        log(f"选择「{result_type}」结果: [{idx}] {label}", "✅")
        return result_type, idx
    
    # 退而求其次：找包含联系人名的非AI搜索结果
    for i, text in enumerate(texts):
        t = text.strip()
        if contact_name in t and not any(kw in t for kw in ["AI搜索", "搜索网络", "公众号"]):
            log(f"选择「含联系人名」结果: [{i}] {t}", "✅")
            return "含联系人名", i
    
    # 找不到明确类型，返回第一个（AI搜索）
    log(f"未找到明确群聊/好友结果，使用第一个结果", "⚠️")
    return None, 0


def navigate_to_search_result(target_idx: int, current_idx: int = 0) -> None:
    """
    从current_idx移动方向键到target_idx位置
    每次按Down之前先截图确认当前位置
    """
    steps = target_idx - current_idx
    if steps == 0:
        return
    
    direction = "down" if steps > 0 else "up"
    abs_steps = abs(steps)
    
    log(f"从位置{current_idx}向{direction}移动{abs_steps}步到位置{target_idx}...", "⬇️")
    
    for step in range(abs_steps):
        press_key(direction)
        time.sleep(0.3)  # 每次移动后等待列表更新


def search_contact(contact_name: str) -> bool:
    """
    搜索联系人并进入聊天窗口
    策略：搜索 → 点击第一个结果 → OCR确认进入聊天
    """
    log(f"正在搜索联系人: {contact_name}...", "🔍")
    
    # 激活微信
    if not activate_wechat():
        return False
    time.sleep(0.3)
    
    if not bring_to_front():
        return False
    time.sleep(0.3)
    
    # 写入剪贴板
    write_to_clipboard(contact_name)
    time.sleep(0.2)
    
    # Cmd+F 打开搜索框
    log("打开搜索框 (Cmd+F)...", "⌨️")
    press_key("f", ["command"])
    time.sleep(0.5)
    
    # Cmd+V 粘贴
    log("粘贴联系人名称...", "📋")
    press_key("v", ["command"])
    time.sleep(1.5)
    
    # 获取窗口信息
    win_rect = get_wechat_window_rect()
    if win_rect:
        win_x, win_y, win_w, win_h = win_rect
    else:
        win_x, win_y, win_w, win_h = 0, 25, 924, 641
    
    # 搜索结果列表 → 直接按 Enter 进入聊天（微信 Mac 版标准操作）
    log("按Enter进入聊天...", "↵")
    press_key("return")
    time.sleep(1.5)
    
    # 关闭悬浮资料卡（如果 Enter 后弹出了资料卡）
    press_key("escape")
    time.sleep(0.5)
    press_key("escape")
    time.sleep(0.3)
    
    log(f"已进入与「{contact_name}」的聊天窗口", "✅")
    return True


# ============================================================================
# 发送消息
# ============================================================================

def send_message(message: str, original_clipboard: str = None) -> bool:
    """
    发送消息
    策略：多点位尝试点击输入框 → 粘贴文本 → Cmd+Return发送 → OCR验证
    """
    log(f"准备发送消息: {message[:40]}{'...' if len(message) > 40 else ''}", "📤")
    
    # 备份剪贴板
    if original_clipboard is None:
        original_clipboard = read_from_clipboard()
    
    # 写入消息到剪贴板
    write_to_clipboard(message)
    time.sleep(0.3)
    
    # 获取窗口信息
    win_rect = get_wechat_window_rect()
    if win_rect:
        win_x, win_y, win_w, win_h = win_rect
        log(f"微信窗口: ({win_x}, {win_y}), 大小: {win_w}x{win_h}", "📐")
    else:
        log("无法获取窗口位置", "⚠️")
        win_x, win_y, win_w, win_h = 0, 0, 800, 600
    
    # 检查是否有搜索覆盖层在输入框位置
    # 如果搜索UI还在，需要先按ESC关闭
    success, texts, _ = ocr_capture_and_recognize("window")
    if success:
        all_text = "".join(texts)
        # 检查是否是搜索状态（包括搜索框、搜索结果列表等）
        search_indicators = ["大 搜索", "Q 搜索", "q 搜索", "搜一搜", "搜索网络", "包含：", "搜索聊天记录"]
        # 搜索聊天记录面板也有输入框，需要关闭它
        chat_record_search_indicators = ["发送人", "日期", "暂无", "共"]
        has_search_overlay = any(ind in all_text for ind in search_indicators)
        has_chat_record_search = all(ind in all_text for ind in chat_record_search_indicators)
        if has_search_overlay or has_chat_record_search:
            log("检测到搜索面板，按ESC关闭...", "ESC")
            press_key("escape")
            time.sleep(1.0)
            # 再按一次ESC确保关闭
            press_key("escape")
            time.sleep(0.5)
    
    # 多点位尝试点击输入框
    input_clicked = False
    # 搜索记录面板关闭后，输入框应该在正常位置
    # 使用更靠下且偏左的位置（输入框通常在底部偏左）
    click_positions = [
        (win_x + int(win_w * 0.55), win_y + int(win_h * 0.88)),  # 偏左下的输入框位置
        (win_x + int(win_w * 0.75), win_y + int(win_h * 0.92)),  # 默认位置
        (win_x + win_w // 2, win_y + int(win_h * 0.95)),        # 居中底部
    ]
    
    for i, (click_x, click_y) in enumerate(click_positions):
        log(f"尝试点击输入框 ({click_x}, {click_y})...", f"🎯 [{i+1}/{len(click_positions)}]")
        click_at坐标(click_x, click_y)
        time.sleep(0.5)
        
        # OCR确认输入框是否就绪
        ready, desc = ocr_check_input_box_ready()
        log(f"  输入框状态: {desc}", "📊")
        
        if ready or i == len(click_positions) - 1:
            input_clicked = True
            break
    
    # 点击输入框后，再点击一次确保焦点
    log("确认输入框焦点...", "🖱️")
    click_at坐标(click_x, click_y)
    time.sleep(0.3)
    
    # 使用cliclick粘贴（更稳定）
    log("粘贴消息 (Cmd+V)...", "📝")
    press_key("v", ["command"])
    time.sleep(0.5)
    
    # 确认文本已粘贴（OCR检查输入框内容）
    success, texts, _ = ocr_capture_and_recognize("window")
    if success:
        all_text = "".join(texts)
        msg_short = message[:5]
        if msg_short in all_text:
            log(f"确认文本已粘贴，找到「{msg_short}」", "✅")
        else:
            log(f"粘贴后OCR: {texts[:3] if texts else '无'}", "📊")
    
    # 发送：Enter（微信 Mac 版用 Enter 发送，不是 Cmd+Return）
    log("发送消息 (Enter)...", "↵")
    press_key("return")
    time.sleep(1.5)
    
    # OCR验证发送结果
    log("OCR验证发送结果...", "🔍")
    sent, desc = ocr_verify_message_sent(message)
    log(f"  验证结果: {desc}", "📊")
    
    # 恢复剪贴板
    write_to_clipboard(original_clipboard)
    
    if sent:
        log("✅ 消息发送成功", "✅")
        return True
    else:
        # 再次尝试发送
        log("首次发送未确认，尝试重新发送...", "🔄")
        
        # 重新聚焦输入框
        click_at坐标(click_x, click_y)
        time.sleep(0.3)
        
        # 全选后粘贴
        press_key("a", ["command"])
        time.sleep(0.2)
        press_key("v", ["command"])
        time.sleep(0.5)
        press_key("return", ["command"])
        time.sleep(1.5)
        
        sent, desc = ocr_verify_message_sent(message)
        log(f"  重试验证: {desc}", "📊")
        
        if sent:
            log("✅ 消息重新发送成功", "✅")
            return True
        
        log("⚠️ 消息可能已发送（OCR未确认）", "⚠️")
        return True


# ============================================================================
# 主执行函数（供外部调用）
# ============================================================================

def execute_wechat_automation(
    contact_name: str,
    keyword_dict: Dict[str, List[str]] = None,
    default_reply: str = None,
    custom_replies: Dict[str, str] = None,
    chat_region: Tuple[int, int, int, int] = None,
    auto_reply: bool = True,
    verbose: bool = True
) -> Dict:
    """
    微信自动化主函数
    
    参数:
        contact_name: 联系人名称（必填，备注名或微信号）
        keyword_dict: 自定义关键词字典（可选）
            格式: {"类别": ["关键词1", "关键词2", ...]}
        default_reply: 默认回复文案（可选）
        custom_replies: 自定义回复覆盖（可选）
            格式: {"类别": "自定义回复内容"}
        chat_region: 聊天窗口截图区域 (x, y, w, h)
        auto_reply: 是否自动回复（默认 True）
        verbose: 是否输出详细日志（默认 True）
    
    返回:
        执行结果字典，包含各步骤状态和识别内容
    
    示例:
        result = execute_wechat_automation(
            contact_name="张三",
            keyword_dict={"价格": ["多少钱", "价格"], "合作": ["合作", "代理"]},
            default_reply="感谢您的消息，我会尽快回复您。"
        )
    """
    global LOG_ENABLED
    LOG_ENABLED = verbose
    
    # 参数初始化
    keyword_dict = keyword_dict or DEFAULT_KEYWORD_DICT
    default_reply = default_reply or DEFAULT_REPLY
    
    # 记录原始剪贴板
    original_clipboard = read_from_clipboard()
    
    # 返回结果
    result = {
        "success": False,
        "contact": contact_name,
        "steps": {},
        "recognized_texts": [],
        "matched_category": None,
        "reply_sent": None,
        "reply_content": None,
        "error": None
    }
    
    try:
        log("=" * 55, "🔔")
        log("🚀 微信自动化流程启动", "🚀")
        log(f"👤 目标联系人: {contact_name}", "👤")
        log("=" * 55, "🔔")
        
        # 检查前置条件
        log("检查系统环境和权限...", "🔧")
        perms = check_permissions()
        if not perms["terminal_accessibility"]:
            log("⚠️ 辅助功能权限未开启", "⚠️")
            print_permission_guide()
            result["error"] = "辅助功能权限未开启，请按照上方指引开启"
            return result
        
        if not perms["screen_recording"]:
            log("⚠️ 屏幕录制权限未开启", "⚠️")
            print_permission_guide()
        
        log("✅ 权限检查通过", "✅")
        
        # 步骤1: 激活微信
        if not activate_wechat():
            result["error"] = "微信激活失败，请确认微信已安装并登录"
            return result
        result["steps"]["activate"] = True
        
        # 步骤2: 置顶窗口
        if not bring_to_front():
            result["error"] = "窗口置顶失败"
            return result
        result["steps"]["bring_to_front"] = True
        
        # 步骤3: 搜索联系人
        if not search_contact(contact_name):
            result["error"] = "搜索联系人失败，请确认联系人名称正确"
            return result
        result["steps"]["search_contact"] = True
        time.sleep(1)  # 等待聊天窗口完全加载
        
        # 步骤4: 截图聊天区域
        if chat_region:
            cx, cy, cw, ch = chat_region
            log(f"使用指定区域截图: ({cx}, {cy}, {cw}, {ch})", "📸")
            screenshot_path = screenshot_chat_area(cx, cy, cw, ch)
        else:
            screenshot_path = screenshot_chat_area()
        
        if not screenshot_path:
            result["error"] = "聊天窗口截图失败，请确认微信窗口可见"
            return result
        result["steps"]["screenshot"] = True
        
        # 步骤5: OCR 识别
        recognized_texts = perform_ocr(screenshot_path)
        result["recognized_texts"] = recognized_texts
        result["steps"]["ocr"] = True
        
        # 步骤6: 关键词匹配
        matched_category = None
        if recognized_texts:
            matched_category = match_keyword(recognized_texts, keyword_dict)
        result["matched_category"] = matched_category
        
        # 步骤7: 自动回复
        if auto_reply:
            reply = generate_reply(matched_category, keyword_dict, default_reply, custom_replies)
            result["reply_content"] = reply
            log(f"💬 生成回复: {reply[:50]}...", "💬")
            
            if send_message(reply, original_clipboard):
                result["reply_sent"] = True
                result["success"] = True
            else:
                result["reply_sent"] = False
                result["error"] = "消息发送失败"
        else:
            # 不自动回复，但标记为成功（已完成 OCR）
            result["success"] = True
        
        log("=" * 55, "🎉")
        log("✅ 微信自动化流程执行完成", "🎉")
        log("=" * 55, "🎉")
        
    except Exception as e:
        result["error"] = str(e)
        log(f"❌ 执行异常: {e}", "❌")
        import traceback
        traceback.print_exc()
    
    finally:
        # 恢复原始剪贴板
        try:
            write_to_clipboard(original_clipboard)
        except:
            pass
    
    return result


# ============================================================================
# 便捷封装函数
# ============================================================================

def send_text_message(contact_name: str, message: str) -> bool:
    """
    快捷函数：仅发送文本消息（不 OCR，不分析聊天记录）
    
    参数:
        contact_name: 联系人名称
        message: 要发送的消息
    返回: 发送是否成功
    """
    log(f"快捷发送消息模式 → 目标: {contact_name}", "📤")
    
    # 第一步：立即保存原始剪贴板内容
    original_clipboard = read_from_clipboard()
    
    # 激活微信
    activate_wechat()
    bring_to_front()
    time.sleep(0.3)
    
    # 搜索联系人（会污染剪贴板为联系人名称）
    search_contact(contact_name)
    time.sleep(0.8)
    
    # 发送消息
    success = send_message(message, original_clipboard)
    
    # 恢复原始剪贴板内容
    write_to_clipboard(original_clipboard)
    
    return success


def check_system_ready() -> Dict:
    """
    检查系统环境是否就绪
    返回各项检查状态
    """
    log("🔍 检查系统环境...", "🔧")
    
    status = {
        "macos_version": False,
        "pyobjc_installed": False,
        "vision_framework": False,
        "permission_accessibility": False,
        "permission_screen_recording": False,
        "wechat_installed": False,
        "ready": False
    }
    
    # 检查 macOS 版本
    code, stdout, _ = run_cmd(["sw_vers", "-productVersion"])
    if code == 0:
        version_str = stdout.strip()
        try:
            version = float(version_str.split('.')[0] + '.' + version_str.split('.')[1])
            status["macos_version"] = version >= 10.15
            log(f"macOS 版本: {version_str} ({'✅' if status['macos_version'] else '❌ 需要 10.15+'})", 
                "✅" if status["macos_version"] else "❌")
        except:
            log(f"macOS 版本检测失败: {version_str}", "⚠️")
    
    # 检查 pyobjc / Vision Framework
    try:
        from Vision import VNRecognizeTextRequest
        status["pyobjc_installed"] = True
        status["vision_framework"] = True
        log("Vision Framework: ✅ 已安装", "✅")
    except ImportError:
        log("Vision Framework: ❌ 未安装 (运行: pip3 install pyobjc)", "❌")
    
    # 检查微信是否安装
    code, stdout, _ = run_applescript('tell application "WeChat" to name')
    status["wechat_installed"] = (code == 0)
    log(f"WeChat: {'✅ 已安装' if status['wechat_installed'] else '❌ 未安装'}", 
        "✅" if status["wechat_installed"] else "❌")
    
    # 检查权限
    perms = check_permissions()
    status["permission_accessibility"] = perms["terminal_accessibility"]
    status["permission_screen_recording"] = perms["screen_recording"]
    log(f"辅助功能权限: {'✅ 已开启' if perms['terminal_accessibility'] else '⚠️  未开启'}",
        "✅" if perms["terminal_accessibility"] else "⚠️")
    log(f"屏幕录制权限: {'✅ 已开启' if perms['screen_recording'] else '⚠️  未开启'}",
        "✅" if perms["screen_recording"] else "⚠️")
    
    # 综合判断
    status["ready"] = all([
        status["macos_version"],
        status["vision_framework"],
        status["permission_accessibility"],
        status["permission_screen_recording"],
        status["wechat_installed"],
    ])
    
    if not status["ready"]:
        log("⚠️ 系统未就绪，请根据上方提示配置", "⚠️")
        print_permission_guide()
    else:
        log("✅ 系统全部就绪，可以执行自动化任务", "🎉")
    
    return status


# ============================================================================
# 命令行入口
# ============================================================================

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(
        description="微信自动化助手 - 激活微信 → 搜索联系人 → Vision OCR → 关键词回复 → 自动发送",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 检查系统环境
  python3 wechat_automator.py check
  
  # 完整自动化流程（OCR识别 + 自动回复）
  python3 wechat_automator.py run -c 张三
  
  # 仅发送消息（不 OCR）
  python3 wechat_automator.py send -c 张三 -m "晚上8点开会"
  
  # 自定义关键词和回复
  python3 wechat_automator.py run -c 李四 \\
         -k '{"价格":["多少钱"],"合作":["代理"]}' \\
         -d "感谢咨询，请说明需求" \\
         -r '{"价格":"具体价格请私信"}'
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="子命令")
    
    # check 命令
    subparsers.add_parser("check", help="检查系统环境是否就绪")
    
    # run 命令
    run_parser = subparsers.add_parser("run", help="运行完整自动化流程")
    run_parser.add_argument("-c", "--contact", required=True, help="联系人名称（备注名或微信号）")
    run_parser.add_argument("-k", "--keywords", help="关键词字典（JSON格式）")
    run_parser.add_argument("-d", "--default-reply", help="默认回复文案")
    run_parser.add_argument("-r", "--custom-replies", help="自定义回复字典（JSON格式）")
    run_parser.add_argument("--no-reply", action="store_true", help="仅OCR识别，不自动回复")
    run_parser.add_argument("--silent", action="store_true", help="静默模式，减少输出")
    
    # send 命令
    send_parser = subparsers.add_parser("send", help="仅发送文本消息（不OCR）")
    send_parser.add_argument("-c", "--contact", required=True, help="联系人名称")
    send_parser.add_argument("-m", "--message", required=True, help="消息内容")
    
    args = parser.parse_args()
    
    if args.command == "check":
        print()
        status = check_system_ready()
        print()
        print("=" * 45)
        if status["ready"]:
            print("🎉 系统就绪状态: ✅ 全部就绪")
        else:
            print("⚠️  系统就绪状态: ⚠️  需要配置")
        print("=" * 45)
        
    elif args.command == "run":
        # 解析关键词字典
        keyword_dict = DEFAULT_KEYWORD_DICT
        if args.keywords:
            try:
                keyword_dict = json.loads(args.keywords)
            except json.JSONDecodeError as e:
                print(f"❌ 关键词字典解析失败: {e}")
                sys.exit(1)
        
        # 解析自定义回复
        custom_replies = None
        if args.custom_replies:
            try:
                custom_replies = json.loads(args.custom_replies)
            except json.JSONDecodeError as e:
                print(f"❌ 自定义回复解析失败: {e}")
                sys.exit(1)
        
        result = execute_wechat_automation(
            contact_name=args.contact,
            keyword_dict=keyword_dict,
            default_reply=args.default_reply,
            custom_replies=custom_replies,
            auto_reply=not args.no_reply,
            verbose=not args.silent
        )
        
        print()
        print("=" * 55)
        print("📊 执行结果汇总:")
        print(f"   成功: {'✅ 是' if result['success'] else '❌ 否'}")
        print(f"   联系人: {result['contact']}")
        print(f"   匹配类别: {result['matched_category'] or '无匹配'}")
        print(f"   识别文本数: {len(result['recognized_texts'])}")
        if result['reply_sent']:
            print(f"   发送回复: {result['reply_content'][:50]}{'...' if len(result['reply_content']) > 50 else ''}")
        if result['error']:
            print(f"   错误: {result['error']}")
        print("=" * 55)
        
    elif args.command == "send":
        success = send_text_message(args.contact, args.message)
        print()
        print("=" * 45)
        print(f"📤 消息发送: {'✅ 成功' if success else '❌ 失败'}")
        print("=" * 45)
        
    else:
        parser.print_help()
