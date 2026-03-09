# agent: optimization-openclaw

**mission:** Optimize OpenClaw bot for maximum inference speed and minimum token usage by auditing workspace files, shrinking prompts, maximizing cache hits, pruning stale sessions, and cutting tool overhead.

## context

- **Config:** `~/.openclaw/openclaw.json` (runtime)
- **Workspace:** `~/clawd/` (or `~/.openclaw/workspace-*/`) — contains SOUL.md, AGENTS.md, TOOLS.md, MEMORY.md, USER.md, HEARTBEAT.md, memory/YYYY-MM-DD.md
- **Sessions:** `~/.openclaw/agents/main/sessions/*.jsonl` or `~/.clawdbot/agents.main/sessions/*.jsonl`

## goals (priority order)

1. Shrink tokens loaded on every request (system prompt, workspace files, tool schemas)
2. Maximize cache hit rate (stable prompt prefix, cacheRetention, heartbeat)
3. Reduce cold session overhead (prune stale session files, compaction)
4. Cut unnecessary tool/skill overhead (disable unused, native off)
5. Keep bot behavior and memory search fully intact

## what this covers end-to-end

| Layer | Optimization | Expected gain |
| :-- | :-- | :-- |
| Workspace files | Rewrite to bullets, archive daily memory | 500-3000 tokens/request |
| Session files | Purge stale `.jsonl` > 24h | Faster session loads, less memory overhead |
| Heartbeat | 55-min ping keeps cache warm | Eliminates cold-start cost on cache-eligible prompts |
| Config | `cacheRetention: long`, `temperature: 0.2`, compaction | 50-90% reduction on repeated prompt prefixes |
| Skills/native | `native: off`, `nativeSkills: off` | Removes detection overhead per turn |
| Cron cleanup | Daily session purge script | Prevents session bloat accumulating over weeks |

## constraints

- Do NOT remove API keys, auth profiles, gateway token, channel config, approvals, or plugin entries
- Do NOT change model IDs or provider URLs
- Maintain valid JSON throughout
- Show each Task's output as a clearly labelled section
- For file rewrites, show the new content in full in a code block

---

## Task 1 — Audit workspace files

For each file in workspace (SOUL.md, AGENTS.md, TOOLS.md, MEMORY.md, USER.md, HEARTBEAT.md, memory/YYYY-MM-DD.md):

- Estimate current token count (characters / 4)
- Identify: (a) content that belongs in a skill instead of always-loaded context, (b) outdated/redundant content, (c) verbose sections that can be rewritten in 50% fewer words
- Output a table:

| Filename | Est. tokens now | Est. tokens after | Savings | Action |
| :-- | :-- | :-- | :-- | :-- |

---

## Task 2 — Rewrite workspace files

For each file identified in Task 1 with savings > 100 tokens:

- Rewrite to declarative bullet points only
- Target: SOUL.md ≤ 500 chars, AGENTS.md ≤ 1000 chars, TOOLS.md trim unused entries, MEMORY.md keep durable facts only, daily memory files: archive anything older than 3 days
- Show full rewritten content for each file in a code block

---

## Task 3 — Stale session cleanup

Use the skill's `scripts/purge-stale-sessions.sh` or generate a similar script that:

- Deletes session `.jsonl` files older than 24 hours
- Optionally archives before deleting
- Is safe to run as a daily cron job
- Prints count of files deleted

---

## Task 4 — Generate heartbeat config snippet

Generate the JSON snippet to add a heartbeat to `openclaw.json` that:

- Fires every 55 minutes (just inside the 1-hour cache window)
- Uses a minimal prompt (e.g. "ok") with the cheapest available model
- Keeps the cache warm so models don't cold-start on user messages

---

## Task 5 — Generate deploy script

Generate a deploy script that:

- Backs up current `~/.openclaw/openclaw.json` with timestamp
- Copies updated config to runtime path
- Runs `openclaw doctor`
- Restarts gateway with `openclaw gateway restart`
- Tails gateway logs to confirm clean startup

---

## execution notes

- Run Task 1 first; use its output to drive Task 2.
- Task 3–5 produce artifacts; verify generated scripts before execution.
- Session path may be `~/.openclaw/agents/main/sessions/` or `~/.clawdbot/agents.main/sessions/` depending on install; check at runtime.
- Heartbeat config keys must match the OpenClaw version's schema; validate before deploy.

---

## companion: openclaw-audit.sh

Run before optimization to establish baseline. Path: `scripts/openclaw-audit.sh` (in this skill).

**Usage:** `/optimize` or `/audit` in chat → agent execs the audit script and returns raw output. After audit, if user approves purge, agent execs `scripts/purge-stale-sessions.sh`.
