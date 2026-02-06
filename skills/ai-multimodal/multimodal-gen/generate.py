#!/usr/bin/env python3
"""
统一生成入口 - 自动优化 prompt 后调用生成模型
"""

import sys
import json
import subprocess
from pathlib import Path

SKILL_DIR = Path(__file__).parent

def run_script(script: str, *args) -> dict:
    """运行脚本并返回 JSON 结果"""
    cmd = ["python3", str(SKILL_DIR / script)] + list(args)
    result = subprocess.run(cmd, capture_output=True, text=True)
    try:
        return json.loads(result.stdout)
    except:
        return {"error": result.stderr or result.stdout}

def generate(prompt: str, media_type: str = "image", model: str = None, skip_optimize: bool = False) -> dict:
    """
    生成图像或视频
    1. 先优化 prompt
    2. 再调用生成模型
    """
    results = {"original_prompt": prompt}
    
    # Step 1: 优化 prompt
    if not skip_optimize:
        opt_result = run_script("prompt_optimizer.py", prompt, media_type)
        if opt_result.get("success"):
            optimized_prompt = opt_result["optimized"]
            results["optimized_prompt"] = optimized_prompt
            results["optimizer_model"] = opt_result.get("model")
        else:
            # 优化失败，使用原始 prompt
            optimized_prompt = prompt
            results["optimize_error"] = opt_result.get("error")
    else:
        optimized_prompt = prompt
    
    # Step 2: 生成
    if media_type == "image":
        model = model or "gemini"  # 默认 gemini
        gen_result = run_script("generate_image.py", optimized_prompt, model)
    else:  # video
        model = model or "veo3.1"  # 默认 veo3.1
        gen_result = run_script("generate_video.py", optimized_prompt, model)
    
    results.update(gen_result)
    return results

def main():
    if len(sys.argv) < 2:
        print("Usage: generate.py <prompt> [image|video] [model] [--no-optimize]")
        print("\nImage models: gemini (default), flux, flux-ultra, imagen, dalle, kling")
        print("Video models: veo3.1 (default), veo3, sora2, kling, hailuo")
        sys.exit(1)
    
    prompt = sys.argv[1]
    media_type = "image"
    model = None
    skip_optimize = "--no-optimize" in sys.argv
    
    for arg in sys.argv[2:]:
        if arg in ["image", "video"]:
            media_type = arg
        elif arg != "--no-optimize":
            model = arg
    
    result = generate(prompt, media_type, model, skip_optimize)
    print(json.dumps(result, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
