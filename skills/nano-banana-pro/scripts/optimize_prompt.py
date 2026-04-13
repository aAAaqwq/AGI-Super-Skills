#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "requests>=2.28.0",
# ]
# ///
"""
Prompt Optimizer for Image Generation.
Takes a simple user prompt and enhances it into a professional image generation prompt.

Uses a fast/cheap LLM (boluobao or xingjiabiapi) to optimize.

Usage:
    uv run optimize_prompt.py --prompt "一只猫" [--style photo|illustration|anime|oil-painting|3d|pixel]
    uv run optimize_prompt.py --prompt "sunset" --style "oil-painting" --lang en
"""

import argparse
import json
import os
import subprocess
import sys

import requests

SYSTEM_PROMPT = """你是一个专业的 AI 图像生成提示词优化师。

用户会给你一个简短的图像描述，你需要将其扩展为一个详细、高质量的图像生成提示词。

## 优化规则：

1. **保留用户的核心意图** — 不要改变主题，只是丰富细节
2. **添加以下维度**（如果用户没有指定）：
   - 主体细节（姿态、表情、材质、纹理）
   - 构图（视角、景深、画面布局）
   - 光线（方向、色温、氛围）
   - 色彩（主色调、对比度、饱和度）
   - 风格（写实/插画/油画/3D等）
   - 背景（环境、氛围、层次）
   - 品质关键词（8K, masterpiece, ultra detailed 等）

3. **输出纯英文** — 图像生成模型对英文效果最好
4. **长度控制** — 80-200 词之间，不要太短也不要太长
5. **不要用 markdown 格式** — 只输出纯文本提示词
6. **不要写"Prompt:"前缀** — 直接输出优化后的文本

## 风格映射：
- photo → photorealistic, DSLR quality, natural lighting
- illustration → digital illustration, clean lines, vibrant
- anime → anime style, cel-shading, Japanese animation aesthetic
- oil-painting → oil painting style, visible brush strokes, rich texture
- 3d → 3D render, octane render, volumetric lighting
- pixel → pixel art, retro gaming aesthetic, 8-bit/16-bit
- cinematic → cinematic composition, dramatic lighting, movie still
- watercolor → watercolor painting, soft edges, translucent layers"""


def get_api_key(provider: str) -> str | None:
    """Get API key for the specified provider."""
    env_map = {
        "boluobao": "BOLUOBAO_API_KEY",
        "xingjiabiapi": "XINGJIABIAPI_API_KEY",
    }
    pass_map = {
        "boluobao": "api/boluobao",
        "xingjiabiapi": "api/xingjiabiapi",
    }

    # Try env first
    key = os.environ.get(env_map.get(provider, ""))
    if key:
        return key

    # Try pass
    try:
        result = subprocess.run(
            ["pass", "show", pass_map.get(provider, "")],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return None


def optimize_with_boluobao(prompt: str, style: str, api_key: str) -> str:
    """Use Boluobao API to optimize prompt."""
    user_msg = f"请优化这个图像生成提示词：「{prompt}」"
    if style:
        user_msg += f"\n风格要求：{style}"

    resp = requests.post(
        "https://apipark.boluobao.ai/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": "gemini-3-pro-preview",
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_msg},
            ],
            "max_tokens": 500,
            "temperature": 0.7,
        },
        timeout=30,
    )
    data = resp.json()
    return data["choices"][0]["message"]["content"].strip()


def optimize_with_xingjiabiapi(prompt: str, style: str, api_key: str) -> str:
    """Use xingjiabiapi API to optimize prompt."""
    user_msg = f"请优化这个图像生成提示词：「{prompt}」"
    if style:
        user_msg += f"\n风格要求：{style}"

    resp = requests.post(
        "https://api.xingjiabiapi.com/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": "gemini-2.5-flash-preview-05-20",
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_msg},
            ],
            "max_tokens": 500,
            "temperature": 0.7,
        },
        timeout=30,
    )
    data = resp.json()
    return data["choices"][0]["message"]["content"].strip()


def main():
    parser = argparse.ArgumentParser(description="Optimize image generation prompts")
    parser.add_argument("--prompt", "-p", required=True, help="User's original prompt")
    parser.add_argument("--style", "-s", default="",
                        choices=["", "photo", "illustration", "anime", "oil-painting",
                                 "3d", "pixel", "cinematic", "watercolor"],
                        help="Desired style")
    parser.add_argument("--provider", default="auto",
                        choices=["auto", "boluobao", "xingjiabiapi"],
                        help="LLM provider for optimization")

    args = parser.parse_args()

    # Try providers in order
    providers = (
        ["boluobao", "xingjiabiapi"] if args.provider == "auto"
        else [args.provider]
    )

    optimized = None
    for provider in providers:
        api_key = get_api_key(provider)
        if not api_key:
            continue
        try:
            if provider == "boluobao":
                optimized = optimize_with_boluobao(args.prompt, args.style, api_key)
            else:
                optimized = optimize_with_xingjiabiapi(args.prompt, args.style, api_key)
            if optimized:
                break
        except Exception as e:
            print(f"Warning: {provider} failed: {e}", file=sys.stderr)
            continue

    if not optimized:
        print("Error: All providers failed. Using original prompt.", file=sys.stderr)
        optimized = args.prompt

    # Output the optimized prompt
    print(optimized)


if __name__ == "__main__":
    main()
