---
name: qmd-extended
description: Extended QMD knowledge base with multi-backend embedding (Google AI Studio / Ollama / local). Use when managing QMD embeddings, switching backends, testing embedding quality, re-indexing, or troubleshooting QMD vector search. Triggers on "qmd embed", "embedding backend", "切换embedding", "embedding测试", "re-embed", "知识库embedding", "qmd扩展". For general QMD queries and knowledge retrieval, use memory-router skill instead.
---

# QMD Extended — Multi-Backend Embedding Manager

## Architecture

QMD's `llm.js` is patched (v2) to support three embedding backends:

```
QMD_EMBED_BACKEND=google|ollama|local

google  → Google AI Studio gemini-embedding-001 (3072-dim, free)
ollama  → Mac Studio Ollama qwen3-embedding:8b (4096-dim, LAN)
local   → node-llama-cpp embeddinggemma-300M (768-dim, CPU)
```

Auto-detect priority: google → ollama → local

## Quick Commands

### Test current backend
```bash
bash ~/clawd/skills/qmd-extended/scripts/embed-test.sh        # test current
bash ~/clawd/skills/qmd-extended/scripts/embed-test.sh all     # test all backends
bash ~/clawd/skills/qmd-extended/scripts/embed-test.sh google "自定义文本"
```

### Switch backend
```bash
bash ~/clawd/skills/qmd-extended/scripts/embed-switch.sh google   # switch to Google
bash ~/clawd/skills/qmd-extended/scripts/embed-switch.sh ollama   # switch to Ollama
# ⚠️ After switching: qmd embed -f  (required — dimensions change)
```

### Check status
```bash
bash ~/clawd/skills/qmd-extended/scripts/embed-status.sh
```

## Environment Variables

| Var | Default | Purpose |
|-----|---------|---------|
| `QMD_EMBED_BACKEND` | auto | Force backend: `google`/`ollama`/`local` |
| `QMD_GOOGLE_EMBED_KEY` | via `pass` | Google API key (auto-read from pass store) |
| `QMD_GOOGLE_EMBED_MODEL` | `gemini-embedding-001` | Google model name |
| `QMD_OLLAMA_EMBED_URL` | — | Ollama host (e.g. `http://100.65.110.126:11434`) |
| `QMD_OLLAMA_EMBED_MODEL` | `qwen3-embedding:8b` | Ollama model name |

## Patch Location

```
/home/aa/.npm-global/lib/node_modules/@tobilu/qmd/dist/llm.js
Backup: llm.js.bak (original pre-patch)
```

⚠️ `npm update @tobilu/qmd` will overwrite the patch. Re-apply from backup or re-run the patch script.

## Backend Details

See `references/backends.md` for API docs, dimensions, rate limits, and comparison table.

## Re-Embedding Workflow

When switching backends or after fresh install:

```bash
# 1. Switch backend
export QMD_EMBED_BACKEND=google

# 2. Force re-embed all collections
qmd embed -f

# 3. Verify
qmd status
bash ~/clawd/skills/qmd-extended/scripts/embed-status.sh
```

## Troubleshooting

| Issue | Fix |
|-------|-----|
| `qmd embed` hangs at compile | First run builds node-llama-cpp. Wait ~10 min. Only affects `local` backend. |
| `Google embed error: 429` | Rate limit hit. Wait 60s or reduce batch size. |
| `Ollama embed: offline` | Mac Studio sleeping. Wake it or switch to `google`. |
| Dimension mismatch in search | Backend changed without re-embed. Run `qmd embed -f`. |
| `pass: api/google-ai-studio not found` | Set `QMD_GOOGLE_EMBED_KEY` env var directly instead. |
