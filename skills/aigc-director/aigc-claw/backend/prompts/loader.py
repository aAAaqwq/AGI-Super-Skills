# -*- coding: utf-8 -*-
"""
统一提示词加载器
从 prompts/ 目录加载提示词模板文件
"""

import os
from typing import Optional

# 获取 prompts 目录的绝对路径 (loader.py is in backend/prompts/, prompts are in backend/prompts/)
PROMPTS_DIR = os.path.dirname(os.path.abspath(__file__))


def load_prompt(category: str, name: str, lang: str = 'zh') -> str:
    """
    加载提示词文件

    Args:
        category: 提示词分类 (script, character, setting, storyboard, reference, video, logline)
        name: 提示词文件名 (不含扩展名)
        lang: 语言版本 ('zh' 或 'en')

    Returns:
        提示词内容字符串

    Example:
        prompt = load_prompt('logline', 'generate', 'zh')
    """
    # 尝试加载语言版本
    file_path = os.path.join(PROMPTS_DIR, category, f"{name}_{lang}.txt")
    if os.path.exists(file_path):
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read().strip()

    # 回退到中文版本
    file_path = os.path.join(PROMPTS_DIR, category, f"{name}.txt")
    if os.path.exists(file_path):
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read().strip()

    raise FileNotFoundError(f"Prompt not found: {category}/{name}_{lang}.txt or {category}/{name}.txt")


def load_prompt_with_fallback(category: str, name: str, lang: str = 'zh', fallback_lang: str = 'zh') -> str:
    """
    加载提示词，如果指定语言不存在则回退

    Args:
        category: 提示词分类
        name: 提示词文件名
        lang: 首选语言
        fallback_lang: 回退语言
    """
    # 先尝试首选语言
    file_path = os.path.join(PROMPTS_DIR, category, f"{name}_{lang}.txt")
    if os.path.exists(file_path):
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read().strip()

    # 回退到指定语言
    if fallback_lang != lang:
        file_path = os.path.join(PROMPTS_DIR, category, f"{name}_{fallback_lang}.txt")
        if os.path.exists(file_path):
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read().strip()

    raise FileNotFoundError(f"Prompt not found: {category}/{name}_{lang}.txt")


def format_prompt(template: str, **kwargs) -> str:
    """
    格式化提示词模板

    Args:
        template: 提示词模板字符串
        **kwargs: 格式化参数

    Returns:
        格式化后的提示词

    Example:
        prompt = format_prompt("Hello {name}, you are {age} years old", name="John", age=30)
    """
    return template.format(**kwargs)


# 风格提示词缓存
_STYLE_PROMPTS_CACHE = {}


def load_style_prompt(category: str, style: str) -> str:
    """
    加载指定风格的提示词

    Args:
        category: 提示词分类 (character, setting)
        style: 风格名称 (realistic, anime, comic-book, 3d-disney, watercolor, oil-painting, cyberpunk, chinese-ink)

    Returns:
        风格提示词模板

    Example:
        prompt = load_style_prompt('character', 'realistic')
    """
    # 先检查缓存
    cache_key = f"{category}:{style}"
    if cache_key in _STYLE_PROMPTS_CACHE:
        return _STYLE_PROMPTS_CACHE[cache_key]

    # 加载风格提示词文件
    file_path = os.path.join(PROMPTS_DIR, category, f"{style}_styles.txt")
    if not os.path.exists(file_path):
        # 回退到通用的风格文件 (character_styles.txt 或 setting_styles.txt)
        fallback_file = "character_styles.txt" if category == "character" else "setting_styles.txt"
        file_path = os.path.join(PROMPTS_DIR, category, fallback_file)

    if not os.path.exists(file_path):
        fallback_file = "character_styles.txt" if category == "character" else "setting_styles.txt"
        raise FileNotFoundError(f"Style prompt file not found: {category}/{fallback_file}")

    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # 解析风格块
    current_style = None
    style_templates = {}
    for line in content.split('\n'):
        line = line.strip()
        # Skip empty lines and comment lines
        if not line or line.startswith('#'):
            continue
        if line.startswith('[') and line.endswith(']'):
            current_style = line[1:-1]
            style_templates[current_style] = []
        elif current_style and line:
            style_templates[current_style].append(line)

    # 转换为字符串
    for s in style_templates:
        style_templates[s] = '\n'.join(style_templates[s])

    # 缓存所有风格
    _STYLE_PROMPTS_CACHE.update(style_templates)

    # 返回指定风格的提示词
    if style in style_templates:
        return style_templates[style]

    # 回退到 anime 或第一个可用风格
    if 'anime' in style_templates:
        return style_templates['anime']

    # 返回第一个可用的风格
    return list(style_templates.values())[0] if style_templates else ""
