# Managing Conversation Index

Index, archive, and maintain conversations for search.

## Quick Start

**Install auto-indexing hook:**
```bash
~/.claude/skills/collaboration/remembering-conversations/tool/install-hook
```

**Index all conversations:**
```bash
~/.claude/skills/collaboration/remembering-conversations/tool/index-conversations
```

**Process unindexed only:**
```bash
~/.claude/skills/collaboration/remembering-conversations/tool/index-conversations --cleanup
```

## Features

- **Automatic indexing** via sessionEnd hook (install once, forget)
- **Semantic search** across all past conversations
- **AI summaries** (Claude Haiku with Sonnet fallback)
- **Recovery modes** (verify, repair, rebuild)
- **Permanent archive** at `~/.config/superpowers/conversation-archive/`

## Setup

### 1. Install Hook (One-Time)

```bash
cd ~/.claude/skills/collaboration/remembering-conversations/tool
./install-hook
```

Handles existing hooks gracefully (merge or replace). Runs in background after each session.

### 2. Index Existing Conversations

```bash
# Index everything
./index-conversations

# Or just unindexed (faster, cheaper)
./index-conversations --cleanup
```

## Index Modes

```bash
# Index all (first run or full rebuild)
./index-conversations

# Index specific session (used by hook)
./index-conversations --session <uuid>

# Process only unindexed (missing summaries)
./index-conversations --cleanup

# Check index health
./index-conversations --verify

# Fix detected issues
./index-conversations --repair

# Nuclear option (deletes DB, re-indexes everything)
./index-conversations --rebuild
```

## Recovery Scenarios

| Situation | Command |
|-----------|---------|
| Missed conversations | `--cleanup` |
| Hook didn't run | `--cleanup` |
| Updated conversation | `--verify` then `--repair` |
| Corrupted database | `--rebuild` |
| Index health check | `--verify` |

## Troubleshooting

**Hook not running:**
- Check: `ls -l ~/.claude/hooks/sessionEnd` (should be executable)
- Test: `SESSION_ID=test-$(date +%s) ~/.claude/hooks/sessionEnd`
- Re-install: `./install-hook`

**Summaries failing:**
- Check API key: `echo $ANTHROPIC_API_KEY`
- Check logs in ~/.config/superpowers/conversation-index/
- Try manual: `./index-conversations --session <uuid>`

**Search not finding results:**
- Verify indexed: `./index-conversations --verify`
- Try text search: `./search-conversations --text "exact phrase"`
- Rebuild if needed: `./index-conversations --rebuild`

## Excluding Projects

To exclude specific projects from indexing (e.g., meta-conversations), create:

`~/.config/superpowers/conversation-index/exclude.txt`
```
# One project name per line
# Lines starting with # are comments
-Users-yourname-Documents-some-project
```

Or set env variable:
```bash
export CONVERSATION_SEARCH_EXCLUDE_PROJECTS="project1,project2"
```

## Storage

- **Archive:** `~/.config/superpowers/conversation-archive/<project>/<uuid>.jsonl`
- **Summaries:** `~/.config/superpowers/conversation-archive/<project>/<uuid>-summary.txt`
- **Database:** `~/.config/superpowers/conversation-index/db.sqlite`
- **Exclusions:** `~/.config/superpowers/conversation-index/exclude.txt` (optional)

## Technical Details

- **Embeddings:** @xenova/transformers (all-MiniLM-L6-v2, 384 dimensions, local/free)
- **Vector search:** sqlite-vec (local/free)
- **Summaries:** Claude Haiku with Sonnet fallback (~$0.01-0.02/conversation)
- **Parser:** Handles multi-message exchanges and sidechains

## See Also

- **Searching:** See SKILL.md for search modes (vector, text, time filtering)
- **Deployment:** See DEPLOYMENT.md for production runbook
