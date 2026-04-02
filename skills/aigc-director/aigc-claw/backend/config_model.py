"""
模型配置表 - 从 JSON 文件加载
包含每个模型的：价格、并发数、提供商、类型
"""
import os
import json
from typing import List, Optional

# 加载配置
_config = None

def _load_config():
    global _config
    if _config is None:
        config_path = os.path.join(os.path.dirname(__file__), "config_model.json")
        with open(config_path, "r", encoding="utf-8") as f:
            _config = json.load(f)
    return _config

def get_model_config(model: str) -> dict:
    """获取模型配置"""
    config = _load_config()
    models = config.get("models", {})

    # 精确匹配
    if model in models:
        return models[model]

    # 前缀匹配
    model_lower = model.lower()
    for key, value in models.items():
        if key in model_lower or model_lower in key:
            return value

    # 默认配置
    return {
        "name": model,
        "provider": "unknown",
        "type": [],
        "concurrency": 3,
    }

def get_max_concurrency(model: str, enable_concurrency: bool = False) -> int:
    """获取模型最大并发数"""
    if not enable_concurrency:
        return 1

    config = get_model_config(model)
    return config.get("concurrency", 3)

def get_models_by_type(model_type: str) -> List[dict]:
    """获取指定类型的所有模型"""
    config = _load_config()
    models = config.get("models", {})

    result = []
    for key, value in models.items():
        types = value.get("type", [])
        if model_type in types:
            result.append({
                "id": key,
                **value
            })
    return result
