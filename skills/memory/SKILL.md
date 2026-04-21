---
name: memory
description: Persistent memory: observations, session summaries, search
---
# Memory

> Persistent memory system: automatic capture of observations, session summaries, memory search

## When to use

- "what did I do yesterday?" / "what happened last week?"
- "remember this" / "save this decision"
- "memory stats" / "show memory"
- "search memory" / "find sessions about X"

## Architecture

```
PostToolUse hook → observations (local JSONL)
SessionEnd hook → session summary (local + git)
SessionStart hook → inject context (auto)
```

**Hybrid storage:**
- Observations (raw) → `~/.claude-memory/observations/` (local)
- Session summaries → `$PROJECT_ROOT/memory/sessions/` (git)

## Paths

| What | Path |
|------|------|
| Observations (local) | `~/.claude-memory/observations/` |
| Sessions (local) | `~/.claude-memory/sessions/` |
| Sessions (git) | `$PROJECT_ROOT/memory/sessions/` |
| Session index | `$PROJECT_ROOT/memory/index.md` |
| Search tool | `~/.claude-memory/hooks/memory-search.sh` |
| Hook scripts | `~/.claude-memory/hooks/` |
| Config | `~/.claude-memory/config.json` |

## How to execute

### Search observations

```bash
# By type
~/.claude-memory/hooks/memory-search.sh --type crm_update --days 7

# By project
~/.claude-memory/hooks/memory-search.sh --project $PROJECT_ROOT --days 30

# By tags
~/.claude-memory/hooks/memory-search.sh --tags crm,leads --days 14

# Text search
~/.claude-memory/hooks/memory-search.sh --query "Acme Corp" --days 30

# Full details
~/.claude-memory/hooks/memory-search.sh --query "Acme" --full

# By session
~/.claude-memory/hooks/memory-search.sh --session abc12345
```

### Statistics

```bash
~/.claude-memory/hooks/memory-search.sh --stats
```

### List sessions

```bash
~/.claude-memory/hooks/memory-search.sh --sessions
```

### Save a decision manually

```bash
echo '{"id":"obs-'$(date +%Y%m%d)'-'$(openssl rand -hex 4)'","timestamp":"'$(date -u +%Y-%m-%dT%H:%M:%SZ)'","session_id":"CURRENT_SESSION","type":"decision","tool":"manual","summary":"DECISION_DESCRIPTION","context":{},"project":"$PROJECT_ROOT","tags":["TAG1"]}' >> ~/.claude-memory/observations/observations-$(date +%Y-%m-%d).jsonl
```

### Read a specific session

```bash
cat $PROJECT_ROOT/memory/sessions/YYYY-MM-DD-SESSION_ID.md
```

## Observation types

| Type | When |
|------|------|
| `feature` | New functionality |
| `bugfix` | Bug fix |
| `decision` | Architectural/business decision |
| `discovery` | New knowledge about the system |
| `change` | General change (git, PR) |
| `outreach` | Communication through channels |
| `crm_update` | CRM data change |
| `config` | Configuration change |
| `skill_update` | Skill change |
| `retrospective` | Quality assessment: what worked, what didn't, what to change |

## Retrospective (convention)

At the end of a session or after a significant task, Claude records a retrospective observation:

```bash
echo '{"id":"obs-'$(date +%Y%m%d)'-'$(openssl rand -hex 4)'","timestamp":"'$(date -u +%Y-%m-%dT%H:%M:%SZ)'","session_id":"SESSION_ID","type":"retrospective","tool":"manual","summary":"RETROSPECTIVE TEXT","context":{},"project":"$PROJECT_ROOT","tags":["retro"]}' >> ~/.claude-memory/observations/observations-$(date +%Y-%m-%d).jsonl
```

**What to record:**
- What went wrong and why
- Which skill/tool didn't work or is incomplete
- What should be changed for the next session
- Important insights about the process

**Summary format:** one sentence, specific. For example:
- `"telegram-send: need to check bot access before bulk sending"`
- `"change-review was skipped before PR — add a reminder"`
- `"CSV parsing via csv.DictReader breaks on empty rows — use pandas"`

**When to record:**
- Session had errors or rework
- Found a gap in a skill or tool
- Made a decision that affects future sessions

Retrospective automatically:
- Gets included in session summary (section `## Retrospective`)
- Gets injected into the next session (section `## Last retro` in context)

## Privacy

4 layers of protection:
1. `<private>...</private>` tags → stripped before saving
2. Pattern matching (token, password, api_key, Bearer)
3. Sensitive files (.env, credentials.json, token.json) → ignored
4. Sensitive commands (export TOKEN/SECRET) → redacted

## Maintenance

### Rotation (manual, once a month)

```bash
mkdir -p ~/.claude-memory/observations/archive
find ~/.claude-memory/observations -name "observations-*.jsonl" -mtime +30 -exec mv {} ~/.claude-memory/observations/archive/ \;
```

### Disk usage

```bash
du -sh ~/.claude-memory/
du -sh $PROJECT_ROOT/memory/
```

### Commit session summaries

```bash
cd $PROJECT_ROOT
git checkout -b update/memory-sessions-$(date +%Y-%m-%d)
git add memory/
git commit -m "Add session summaries for $(date +%Y-%m-%d)"
git push -u origin update/memory-sessions-$(date +%Y-%m-%d)
gh pr create --title "Memory: session summaries $(date +%Y-%m-%d)" --body "Auto-generated session summaries"
gh pr merge --squash --delete-branch
git checkout main && git pull
```

## Hooks (automatic)

| Hook | Event | What it does |
|------|-------|--------------|
| `session-start.sh` | SessionStart | Inject context from past sessions |
| `post-tool-use.sh` | PostToolUse (Edit/Write/Bash) | Records observations |
| `session-end.sh` | SessionEnd + PreCompact | Generates session summary |

## Related skills

- `daily-briefing` — morning context (includes memory)
- `show-today` — today's tasks
- `query-leads` — CRM search
- `log-activity` — activity logging (complements observations)
