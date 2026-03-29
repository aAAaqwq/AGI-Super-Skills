# Relay Providers Reference — Video

## How to Add a New Provider

1. Add entry to `RELAY_PRIORITY`:
```python
RELAY_PRIORITY = [
    {"name": "xingjiabi", "enabled": True},
    {"name": "new_provider", "enabled": True},
]
```

2. Add config to `PROVIDER_CONFIG`:
```python
"new_provider": {
    "base_url": "https://api.newprovider.com/v1",
    "default_model": "video-model",
    "fallback_models": ["alt-1", "alt-2"],
    "env_key": "NEW_PROVIDER_API_KEY",
},
```

3. Add `gen_new_provider(...)` function following existing pattern.
4. Add dispatch in `main()`.

## Xingjiabi Video API

### Submit
```
POST https://xingjiabiapi.com/v1/video/generations
Authorization: Bearer <XINGJIABIAPI_KEY>
Content-Type: application/json

{"model": "kling-video", "prompt": "...", "duration": "5", "aspect_ratio": "16:9"}
```

### Response (submit)
```json
{"code": 200, "message": "", "request_id": "...",
 "data": {"task_id": "abc123", "task_status": "pending", "created_at": 1234, "updated_at": 1234}}
```

### Poll
```
GET https://xingjiabiapi.com/v1/video/generations/{task_id}
Authorization: Bearer <XINGJIABIAPI_KEY>
```

### Response (poll)
```json
{"code": 200, "data": {"task_id": "abc123", "task_status": "completed", "video_url": "https://..."}}
```

### Status values
- `pending` / `processing` → keep polling
- `completed` / `succeed` / `success` → download video_url
- `failed` / `error` / `cancelled` → abort

## Available Video Models (Xingjiabi, tested 2026-03-11)

| Model | Status | Notes |
|-------|--------|-------|
| kling-video | ✅ Supported | Often saturated ("负载已饱和") |
| veo3.1-fast | ⚠️ Listed | No channels currently |
| veo3.1 | ⚠️ Listed | No channels |
| veo3.1-pro | ⚠️ Listed | Expensive ($3.50) |
| minimax/video-01 | ❓ | Untested on endpoint |
| grok-video-3 | ❓ | SSL timeout |
| sora-2 | ❌ | "不支持的模型类型" on this endpoint |
| luma_video_api | ❌ | "不支持的模型类型" |

## Full Model List (Image + Video on Xingjiabi)

See `relay-image-gen/references/providers.md` for image models.
