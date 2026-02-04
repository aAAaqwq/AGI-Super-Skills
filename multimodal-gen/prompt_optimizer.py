#!/usr/bin/env python3
"""
Prompt 优化器 - 调用文本模型优化图像/视频生成提示词
"""

import sys
import json
import subprocess
import requests

API_BASE = "https://xingjiabiapi.com/v1"
OPTIMIZER_MODEL = "deepseek-v3.2"  # 性价比高，中文理解好

def get_api_key():
    result = subprocess.run(["pass", "api/xingjiabiapi"], capture_output=True, text=True)
    return result.stdout.strip()

def optimize_prompt(user_prompt: str, media_type: str = "image") -> dict:
    """优化用户提示词"""
    api_key = get_api_key()
    
    if media_type == "image":
        system_prompt = """你是一个专业的AI图像生成提示词优化专家。

用户会给你一个简单的图像描述，你需要将其优化为高质量的英文提示词。

优化原则：
1. 翻译成英文（如果是中文）
2. 添加艺术风格描述（如 digital art, oil painting, anime style 等）
3. 添加画面质量词（如 high quality, detailed, 4k, masterpiece）
4. 添加光影氛围描述（如 dramatic lighting, soft glow, golden hour）
5. 添加构图描述（如 close-up, wide shot, dynamic pose）
6. 保持核心主题不变
7. 避免敏感/违规内容：
   - 将"萝莉/loli/lolita"改为"young girl"或"little girl"或"child"
   - 避免任何可能被误解为不当内容的描述
   - 确保输出对所有AI图像生成模型都是安全的

只输出优化后的英文提示词，不要解释。"""
    else:  # video
        system_prompt = """你是一个专业的AI视频生成提示词优化专家。

用户会给你一个简单的视频描述，你需要将其优化为高质量的英文提示词。

优化原则：
1. 翻译成英文（如果是中文）
2. 描述动作和运动（如 walking slowly, camera panning, zooming in）
3. 添加时间/节奏描述（如 in slow motion, timelapse）
4. 添加环境氛围（如 cinematic, dramatic, peaceful）
5. 添加画面质量词（如 4K, high quality, professional）
6. 描述镜头运动（如 tracking shot, aerial view, first person）
7. 保持核心主题不变
8. 避免敏感/违规内容，如有需要进行适当修改

只输出优化后的英文提示词，不要解释。"""

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    data = {
        "model": OPTIMIZER_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        "max_tokens": 500,
        "temperature": 0.7
    }
    
    try:
        response = requests.post(f"{API_BASE}/chat/completions", headers=headers, json=data, timeout=30)
        result = response.json()
        
        if "error" in result:
            return {"error": result["error"], "original": user_prompt}
        
        optimized = result["choices"][0]["message"]["content"].strip()
        
        return {
            "success": True,
            "original": user_prompt,
            "optimized": optimized,
            "model": OPTIMIZER_MODEL,
            "type": media_type
        }
    except Exception as e:
        return {"error": str(e), "original": user_prompt}

def main():
    if len(sys.argv) < 2:
        print("Usage: prompt_optimizer.py <prompt> [image|video]")
        sys.exit(1)
    
    prompt = sys.argv[1]
    media_type = sys.argv[2] if len(sys.argv) > 2 else "image"
    
    result = optimize_prompt(prompt, media_type)
    print(json.dumps(result, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
