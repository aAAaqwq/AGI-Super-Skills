# Conversation Search Deployment Guide

Quick reference for deploying and maintaining the conversation indexing system.

## Initial Deployment

```bash
cd ~/.claude/skills/collaboration/remembering-conversations/tool

# 1. Install hook
./install-hook

# 2. Index existing conversations (with parallel summarization)
./index-conversations --cleanup --concurrency 8

# 3. Verify index health
./index-conversations --verify

# 4. Test search
./search-conversations "test query"
```

**Expected results:**
- Hook installed at `~/.claude/hooks/sessionEnd`
- Summaries created for all conversations (50-120 words each)
- Search returns relevant results in <1 second
- No verification errors

**Performance tip:** Use `--concurrency 8` or `--concurrency 16` for 8-16x faster summarization on initial indexing. Hook uses concurrency=1 (safe for background).

## Ongoing Maintenance

### Automatic (No Action Required)

- Hook runs after every session ends
- New conversations indexed in background (<30 sec per conversation)
- Summaries generated automatically

### Weekly Health Check

```bash
cd ~/.claude/skills/collaboration/remembering-conversations/tool
./index-conversations --verify
```

If issues found:
```bash
./index-conversations --repair
```

### After System Changes

| Change | Action |
|--------|--------|
| Moved conversation archive | Update paths in code, run `--rebuild` |
| Updated CLAUDE.md | Run `--verify` to check for issues |
| Changed database schema | Backup DB, run `--rebuild` |
| Hook not running | Check executable: `chmod +x ~/.claude/hooks/sessionEnd` |

## Recovery Scenarios

| Issue | Diagnosis | Fix |
|-------|-----------|-----|
| **Missing summaries** | `--verify` shows "Missing summaries: N" | `--repair` regenerates missing summaries |
| **Orphaned DB entries** | `--verify` shows "Orphaned entries: N" | `--repair` removes orphaned entries |
| **Outdated indexes** | `--verify` shows "Outdated files: N" | `--repair` re-indexes modified files |
| **Corrupted database** | Errors during search/verify | `--rebuild` (re-indexes everything, requires confirmation) |
| **Hook not running** | No summaries for new conversations | See Troubleshooting below |
| **Slow indexing** | Takes >30 sec per conversation | Check API key, network, Haiku fallback in logs |

## Monitoring

### Health Checks

```bash
# Check hook installed and executable
ls -l ~/.claude/hooks/sessionEnd

# Check recent conversations
ls -lt ~/.config/superpowers/conversation-archive/*/*.jsonl | head -5

# Check database size
ls -lh ~/.config/superpowers/conversation-index/db.sqlite

# Full verification
./index-conversations --verify
```

### Expected Behavior Metrics

- **Hook execution:** Within seconds of session end
- **Indexing speed:** <30 seconds per conversation
- **Summary length:** 50-120 words
- **Search latency:** <1 second
- **Verification:** 0 errors when healthy

### Log Output

Normal indexing:
```
Initializing database...
Loading embedding model...
Processing project: my-project (3 conversations)
  Summary: 87 words
  Indexed conversation.jsonl: 5 exchanges
✅ Indexing complete! Conversations: 3, Exchanges: 15
```

Verification with issues:
```
Verifying conversation index...
Verified 100 conversations.

=== Verification Results ===
Missing summaries: 2
Orphaned entries: 0
Outdated files: 1
Corrupted files: 0

Run with --repair to fix these issues.
```

## Troubleshooting

### Hook Not Running

**Symptoms:** New conversations not indexed automatically

**Diagnosis:**
```bash
# 1. Check hook exists and is executable
ls -l ~/.claude/hooks/sessionEnd
# Should show: -rwxr-xr-x ... sessionEnd

# 2. Check $SESSION_ID is set during sessions
echo $SESSION_ID
# Should show: session ID when in active session

# 3. Check indexer exists
ls -l ~/.claude/skills/collaboration/remembering-conversations/tool/index-conversations
# Should show: -rwxr-xr-x ... index-conversations

# 4. Test hook manually
SESSION_ID=test-$(date +%s) ~/.claude/hooks/sessionEnd
```

**Fix:**
```bash
# Make hook executable
chmod +x ~/.claude/hooks/sessionEnd

# Reinstall if needed
./install-hook
```

### Summaries Failing

**Symptoms:** Verify shows missing summaries, repair fails

**Diagnosis:**
```bash
# Check API key
echo $ANTHROPIC_API_KEY
# Should show: sk-ant-...

# Try manual indexing with logging
./index-conversations 2>&1 | tee index.log
grep -i error index.log
```

**Fix:**
```bash
# Set API key if missing
export ANTHROPIC_API_KEY="your-key-here"

# Check for rate limits (wait and retry)
sleep 60 && ./index-conversations --repair

# Fallback uses claude-3-haiku-20240307 (cheaper)
# Check logs for: "Summary: N words" to confirm success
```

### Search Not Finding Results

**Symptoms:** `./search-conversations "query"` returns no results

**Diagnosis:**
```bash
# 1. Verify conversations indexed
./index-conversations --verify

# 2. Check database exists and has data
ls -lh ~/.config/superpowers/conversation-index/db.sqlite
# Should be > 100KB if conversations indexed

# 3. Try text search (exact match)
./search-conversations --text "exact phrase from conversation"

# 4. Check for corruption
sqlite3 ~/.config/superpowers/conversation-index/db.sqlite "SELECT COUNT(*) FROM exchanges;"
# Should show number > 0
```

**Fix:**
```bash
# If database missing or corrupt
./index-conversations --rebuild

# If specific conversations missing
./index-conversations --repair

# If still failing, check embedding model
rm -rf ~/.cache/transformers  # Force re-download
./index-conversations
```

### Database Corruption

**Symptoms:** Errors like "database disk image is malformed"

**Fix:**
```bash
# 1. Backup current database
cp ~/.config/superpowers/conversation-index/db.sqlite ~/.config/superpowers/conversation-index/db.sqlite.backup

# 2. Rebuild from scratch
./index-conversations --rebuild
# Confirms with: "Are you sure? [yes/NO]:"
# Type: yes

# 3. Verify rebuild
./index-conversations --verify
```

## Commands Reference

```bash
# Index all conversations
./index-conversations

# Index specific session (called by hook)
./index-conversations --session <session-id>

# Index only unprocessed conversations
./index-conversations --cleanup

# Verify index health
./index-conversations --verify

# Repair issues found by verify
./index-conversations --repair

# Rebuild everything (with confirmation)
./index-conversations --rebuild

# Search conversations (semantic)
./search-conversations "query"

# Search conversations (text match)
./search-conversations --text "exact phrase"

# Install/reinstall hook
./install-hook
```

## Subagent Workflow

**For searching conversations from within Claude Code sessions**, use the subagent pattern (see `skills/using-skills` for complete workflow).

**Template:** `tool/prompts/search-agent.md`

**Key requirements:**
- Synthesis must be 200-1000 words (Summary section)
- All sources must include: project, date, file path, status
- No raw conversation excerpts (synthesize instead)
- Follow-up via subagent (not direct file reads)

**Manual test checklist:**
1. ✓ Dispatch subagent with search template
2. ✓ Verify synthesis 200-1000 words
3. ✓ Verify all sources have metadata (project, date, path, status)
4. ✓ Ask follow-up → dispatch second subagent to dig deeper
5. ✓ Confirm no raw conversations in main context

## Files and Directories

```
~/.claude/
├── hooks/
│   └── sessionEnd                 # Hook that triggers indexing
└── skills/collaboration/remembering-conversations/
    ├── SKILL.md                   # Main documentation
    ├── DEPLOYMENT.md              # This file
    └── tool/
        ├── index-conversations    # Main indexer
        ├── search-conversations   # Search interface
        ├── install-hook           # Hook installer
        ├── test-deployment.sh     # End-to-end tests
        ├── src/                   # TypeScript source
        └── prompts/
            └── search-agent.md    # Subagent template

~/.config/superpowers/
├── conversation-archive/          # Archived conversations
│   └── <project>/
│       ├── <uuid>.jsonl          # Conversation file
│       └── <uuid>-summary.txt    # AI summary (50-120 words)
└── conversation-index/
    └── db.sqlite                  # SQLite database with embeddings
```

## Deployment Checklist

### Initial Setup
- [ ] Hook installed: `./install-hook`
- [ ] Existing conversations indexed: `./index-conversations`
- [ ] Verification clean: `./index-conversations --verify`
- [ ] Search working: `./search-conversations "test"`
- [ ] Subagent template exists: `ls tool/prompts/search-agent.md`

### Ongoing
- [ ] Weekly: Run `--verify` and `--repair` if needed
- [ ] After system changes: Re-verify
- [ ] Monitor: Check hook runs (summaries appear for new conversations)

### Testing
- [ ] Run end-to-end tests: `./test-deployment.sh`
- [ ] All 5 scenarios pass
- [ ] Manual subagent test (see scenario 5 in test output)
