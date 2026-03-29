# Relay Providers Reference

## How to Add a New Provider

1. Add entry to `RELAY_PRIORITY` list (position = priority):
```python
RELAY_PRIORITY = [
    {"name": "boluobao", "enabled": True},    # highest priority
    {"name": "xingjiabi", "enabled": True},    # fallback
    {"name": "new_provider", "enabled": True}, # new!
]
```

2. Add config to `PROVIDER_CONFIG`:
```python
"new_provider": {
    "base_url": "https://api.newprovider.com/v1",
    "default_model": "model-name",
    "fallback_models": ["alt-model-1", "alt-model-2"],
    "env_key": "NEW_PROVIDER_API_KEY",
    "pass_path": "api/new-provider",  # or None
},
```

3. Add resolution mapping to `RESOLUTION_MAP`:
```python
"1k": {"boluobao": "1k", "xingjiabi": "1024x1024", "new_provider": "1024x1024"},
```

4. Add generator function `gen_new_provider(...)` following existing patterns.

5. Add dispatch in `main()`.

## Known Providers

### Boluobao (菠萝包)
- **Base URL**: `https://apipark.boluobao.ai/v1`
- **Image endpoint**: `POST /images/generations`
- **Auth**: Bearer token via `BOLUOBAO_API_KEY` or `pass show api/boluobao`
- **Models**: gemini-3-pro-image-preview
- **Request**: `{model, prompt, aspect_ratio, image_size, image[]}`
- **Response**: `{status: 200, data: [{url, revised_prompt}]}`
- **Aspect ratios**: 1:1, 2:3, 3:2, 3:4, 4:3, 4:5, 5:4, 9:16, 16:9, 21:9
- **Image sizes**: 1k, 2k, 4k

### Xingjiabi (星价币)
- **Base URL**: `https://xingjiabiapi.com/v1`
- **Image endpoint**: `POST /images/generations`
- **Auth**: Bearer token via `XINGJIABIAPI_KEY`
- **Image models**: dall-e-3, gpt-image-1, gpt-image-1.5, google/imagen-4, gemini-3-pro-image-preview
- **Request (OpenAI-compat)**: `{model, prompt, size, n}`
- **Response**: `{data: [{url?, b64_json?, revised_prompt?}]}`
- **Sizes**: 1024x1024, 1792x1024, 1024x1792, 2048x2048

### Video Models (Xingjiabi)
- **Video endpoint**: `POST /video/generations`
- **Poll endpoint**: `GET /video/generations/{task_id}`
- **Submit request**: `{model, prompt, duration, aspect_ratio}`
- **Submit response**: `{code, message, data: {task_id, task_status}}`
- **Poll response**: `{code, data: {task_id, task_status, video_url}}`
- **Working models**: kling-video (often saturated)
- **Listed models**: veo3.1-fast, veo3.1, veo3.1-pro, veo3.1-4k, sora-2, minimax/video-01, grok-video-3
