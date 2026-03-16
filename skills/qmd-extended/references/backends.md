# Embedding Backends Reference

## Google AI Studio (`google`)

- **Model**: `gemini-embedding-001` (production), `gemini-embedding-2-preview` (preview)
- **Dimensions**: 3072
- **Free tier**: 1500 RPD, 100 RPM, 1M tokens/month
- **Batch API**: `batchEmbedContents` — up to 100 per request
- **Latency**: ~1s per request from China (via proxy)
- **Auth**: API key via `pass show api/google-ai-studio`

### API Endpoints

Single: `POST /v1beta/models/{model}:embedContent?key={KEY}`
```json
{"content": {"parts": [{"text": "your text"}]}}
// Response: {"embedding": {"values": [0.01, -0.02, ...]}}
```

Batch: `POST /v1beta/models/{model}:batchEmbedContents?key={KEY}`
```json
{"requests": [
  {"model": "models/gemini-embedding-001", "content": {"parts": [{"text": "text1"}]}},
  {"model": "models/gemini-embedding-001", "content": {"parts": [{"text": "text2"}]}}
]}
// Response: {"embeddings": [{"values": [...]}, {"values": [...]}]}
```

## Ollama (`ollama`)

- **Model**: `qwen3-embedding:8b` (Mac Studio M4 Max)
- **Dimensions**: 4096
- **Cost**: Free (self-hosted)
- **Batch API**: native batch support via `input` array
- **Latency**: ~100ms per request (Tailscale LAN)
- **Auth**: None required
- **⚠️ Dependency**: Mac Studio must be online

### API Endpoint

`POST {OLLAMA_URL}/api/embed`
```json
{"model": "qwen3-embedding:8b", "input": "your text"}
// or batch: {"model": "...", "input": ["text1", "text2"]}
// Response: {"embeddings": [[0.01, ...], [0.02, ...]]}
```

## Local (`local`)

- **Model**: `embeddinggemma-300M` (default GGUF)
- **Dimensions**: 768
- **Cost**: Free (CPU)
- **Latency**: ~500ms per text (CPU-only, no GPU)
- **Auth**: None
- **Pro**: Always available, no network dependency
- **Con**: Slowest, lowest quality embeddings

## Comparison

| Backend | Dim  | Latency | Cost   | Quality | Availability |
|---------|------|---------|--------|---------|-------------|
| Google  | 3072 | ~1s     | Free*  | ★★★★★  | 99.9%       |
| Ollama  | 4096 | ~100ms  | Free   | ★★★★   | Mac online   |
| Local   | 768  | ~500ms  | Free   | ★★★    | Always      |

*Google free tier: 1M tokens/month. QMD ~10k files ≈ ~5M tokens for full re-embed.

## ⚠️ Dimension Mismatch

**Switching backends requires full re-embedding** because vector dimensions differ:
```bash
qmd embed -f  # Force re-embed all documents
```

Existing vectors from one backend CANNOT be searched with another backend's query vectors.
The re-embed process for ~10k files takes:
- Google: ~10-15 min (batch API, rate limited)
- Ollama: ~5 min (GPU, fast batch)
- Local: ~30-60 min (CPU)
