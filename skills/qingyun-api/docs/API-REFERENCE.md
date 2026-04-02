# QingYun API Reference — Quick Reference for Script Development

## Base
- URL: `https://api.qingyuntop.top`
- Auth: `Authorization: Bearer $QINGYUN_API_KEY`
- Gemini native auth: `?key=$QINGYUN_API_KEY` (query param)

## 1. Embedding — gemini-embedding-2-preview
**Endpoint**: `POST /v1/embeddings` (OpenAI兼容)
```json
{"model": "gemini-embedding-2-preview", "input": "text"}
```
Response: `{"data": [{"embedding": [...], "index": 0}], "model": "...", "usage": {...}}`

## 2. Image — grok-imagine-image-pro
**Endpoint**: `POST /v1/images/generations`
```json
{"model": "grok-imagine-image-pro", "prompt": "a cat", "size": "960x960"}
```
Sizes: 960x960, 720x1280, 1280x720, 1168x784, 784x1168
Response: `{"data": [{"url": "..."}], "usage": {...}}`

## 3. Image — gemini-3-pro-image-preview
**Endpoint**: `POST /v1beta/models/gemini-3-pro-image-preview:generateContent`
Auth: `?key=$QINGYUN_API_KEY` query param
```json
{
  "contents": [{"parts": [{"text": "a cute cat"}]}],
  "generationConfig": {
    "responseModalities": ["TEXT", "IMAGE"],
    "imageConfig": {"aspectRatio": "16:9"}
  }
}
```
Response: Gemini format with base64 image in `candidates[0].content.parts[].inlineData`

**Chat兼容格式** (simpler):
**Endpoint**: `POST /v1/chat/completions`
```json
{"model": "gemini-3-pro-image-preview", "messages": [{"role": "user", "content": "generate image: a cute cat"}]}
```

## 4. Animation — andreasjansson/stable-diffusion-animation
**Endpoint**: `POST /replicate/v1/predictions`
```json
{
  "version": "andreasjansson/stable-diffusion-animation:ca1f5e306e5721e19c473e0d094e6603f0456fe759c10715fcd6c1b79242d4a5",
  "input": {
    "width": 512, "height": 512,
    "prompt_start": "a cat sitting",
    "prompt_end": "a cat standing",
    "gif_ping_pong": true,
    "output_format": "mp4",
    "guidance_scale": 7.5,
    "prompt_strength": 0.9,
    "film_interpolation": true,
    "num_inference_steps": 50,
    "num_animation_frames": 25,
    "gif_frames_per_second": 20,
    "num_interpolation_steps": 5
  }
}
```
**Query**: `GET /replicate/v1/predictions/{id}`
Response: `{"id": "...", "status": "starting|processing|succeeded|failed", "output": ["url"]}`

## 5. Video — sora-2-all / sora-2-pro-all (UNIFIED)
**Endpoint**: `POST /v1/video/create`
```json
{
  "model": "sora-2",  // or "sora-2-pro"
  "prompt": "a dog walking",
  "images": [],  // optional image URLs for image-to-video
  "orientation": "landscape",  // portrait|landscape
  "size": "small",  // small=720p, large=1080p
  "duration": 10,  // seconds
  "watermark": false,
  "private": true
}
```
**Query**: `GET /v1/video/{task_id}`
Response: `{"id": "...", "status": "pending|processing|completed|failed"}`

## 6. Video — veo_3_1-fast-4K / veo_3_1-components-4K (UNIFIED)
**Endpoint**: `POST /v1/video/create`
```json
{
  "model": "veo3.1-fast",  // or "veo3.1-4k" for 4K, or "veo3.1-fast-4k" for fast+4K
  "prompt": "sunset beach",
  "enhance_prompt": true,  // auto translate CN→EN
  "enable_upsample": true,
  "images": [],  // optional first/last frames
  "aspect_ratio": "16:9"  // only for veo3+
}
```
**Query**: `GET /v1/video/{task_id}`
Models: veo2, veo2-fast, veo2-pro, veo3, veo3-fast, veo3-pro, veo3.1, veo3.1-fast, veo3.1-pro, veo3.1-4k, veo3.1-pro-4k

## 7. Video — grok-video-3-10s (UNIFIED)
**Endpoint**: `POST /v1/video/create`
```json
{
  "model": "grok-video-3",
  "prompt": "cat eating fish",
  "aspect_ratio": "3:2",  // 2:3, 3:2, 1:1
  "size": "720P",
  "images": []  // optional reference images
}
```
**Query**: `GET /v1/video/{task_id}`

## 8. Video — doubao-seedance-1-5-pro-251215 / doubao-seedance-1-0-pro-fast-251015
**Endpoint**: `POST /volc/v1/contents/generations/tasks`
```json
{
  "model": "doubao-seedance-1-5-pro-251215",
  "content": [
    {"type": "text", "text": "a dog running"},
    {"type": "image_url", "role": "first_frame", "image_url": {"url": "https://..."}}
  ]
}
```
Roles: first_frame, last_frame, reference
**Query**: `GET /volc/v1/contents/generations/tasks/{task_id}`

## 9. Video — kling-avatar-image2video
**Endpoint**: `POST /kling/v1/videos/image2video`
```json
{
  "model_name": "kling-v2-5-turbo",
  "image": "https://...or base64",
  "image_tail": "",
  "prompt": "woman waving hello",
  "negative_prompt": "",
  "duration": "5",
  "aspect_ratio": "16:9",
  "mode": "std",  // std|pro
  "cfg_scale": 0.5
}
```
**Query**: `GET /kling/v1/videos/image2video/{task_id}`

## 10. Audio — gpt-4o-audio-preview
**Endpoint**: `POST /v1/chat/completions`
```json
{
  "model": "gpt-4o-audio-preview",
  "modalities": ["text", "audio"],
  "audio": {"voice": "alloy", "format": "wav"},
  "messages": [{"role": "user", "content": "Say hello in Chinese"}]
}
```
Voices: alloy, ash, ballad, coral, echo, fable, nova, onyx, sage, shimmer
Formats: wav, mp3, flac, opus, pcm16

## 11. TTS — gemini-2.5-flash-preview-tts / gemini-2.5-pro-preview-tts
**Endpoint**: `POST /v1beta/models/{model}:generateContent`
Auth: `?key=$QINGYUN_API_KEY`
```json
{
  "contents": [{"parts": [{"text": "说出,我是谁"}]}],
  "generationConfig": {
    "responseModalities": ["AUDIO"],
    "speechConfig": {
      "voiceConfig": {
        "prebuiltVoiceConfig": {"voiceName": "Kore"}
      }
    }
  },
  "model": "gemini-2.5-flash-preview-tts"
}
```
Response: base64 audio in `candidates[0].content.parts[].inlineData.data`

## 12. Audio — kling-audio (文生音效)
**Endpoint**: `POST /kling/v1/audio/text-to-audio`
```json
{
  "prompt": "ocean waves",
  "duration": "5"
}
```
**Query**: `GET /kling/v1/audio/text-to-audio/{task_id}`

## 13. Effects — kling-effects (视频特效)
**Endpoint**: `POST /kling/v1/videos/effects`
```json
{
  "effect_scene": "balloon_parade",
  "input": {
    "duration": "5",
    "image": "https://..."
  }
}
```
**Query**: `GET /kling/v1/videos/effects/{task_id}`

## 14. Lip Sync — kling-advanced-lip-sync
**Step 1 - Face Detect**: `POST /kling/v1/videos/lip-sync/face`
**Step 2 - Lip Sync**: `POST /kling/v1/videos/advanced-lip-sync`
```json
{
  "session_id": "from-step1",
  "face_choose": [{
    "face_id": "-1",
    "audio_id": "825451760499568680",
    "sound_start_time": 0,
    "sound_end_time": 5000,
    "sound_insert_time": 1000,
    "sound_volume": 1,
    "original_audio_volume": 1
  }]
}
```
**Query**: `GET /kling/v1/videos/advanced-lip-sync/{task_id}`

## Common Query Patterns
| Platform | Create | Query |
|----------|--------|-------|
| Sora/Veo/Grok | `POST /v1/video/create` | `GET /v1/videos/{task_id}` |
| Doubao | `POST /volc/v1/contents/generations/tasks` | `GET /volc/v1/contents/generations/tasks/{task_id}` |
| Kling | `POST /kling/v1/videos/{type}` | `GET /kling/v1/videos/{type}/{task_id}` |
| Kling Audio | `POST /kling/v1/audio/text-to-audio` | `GET /kling/v1/audio/text-to-audio/{task_id}` |
| Replicate | `POST /replicate/v1/predictions` | `GET /replicate/v1/predictions/{id}` |
