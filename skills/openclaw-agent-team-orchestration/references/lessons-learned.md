# Lessons Learned

## k2p5 Tool-Call Loop

**Symptom**: Token count stays at 0 for 5+ minutes, then times out.

**Cause**: Model tries to `read("AGENTS.md")` without required `path` parameter, enters infinite retry loop.

**Fix**: Add TOOLS.md reminders to every agent:
```markdown
1. Do NOT read AGENTS.md — it's auto-injected
2. Always provide `path` parameter
3. Tool calls must include all required parameters
```

## Spawn Permission

**Symptom**: `sessions_spawn` fails with permission error.

**Fix**: Add agent IDs to main agent's `subagents.allowAgents` in openclaw.json.

## Symlink Paths

**Symptom**: File not found errors.

**Fix**: Use absolute paths in symlinks:
```bash
ln -s /Users/.../workspace-writer/OUTPUT OUTPUT
```

## Version Naming

For multi-round pipelines:
- v1: `article.md`
- v2: `article-v2.md`
- v3: `article-v3.md`

**Critical**: When spawning round 2 reviewers, explicitly reference the new version:
```
task: "Review OUTPUT/project/article-v2.md"
```

## Agent Memory Loss After Gateway Restart

**Symptom**: After gateway restart, the main agent (orchestrator) loses all architecture information — agent list, product line configuration, workflow templates. It behaves as if the team was never set up.

**Cause**: Architecture information was stored only in MEMORY.md. The memory system depends on runtime state that may not survive a gateway restart.

**Fix**: Write all architecture information (agent roster, product line mappings, workflow templates, monitoring rules) into the orchestrator's AGENTS.md instead of MEMORY.md. AGENTS.md is auto-loaded at every session start — it does not depend on the memory system.

**Principle**: Anything the orchestrator must know to function should be in AGENTS.md (deterministic load), not MEMORY.md (best-effort load).

## Instruction File Self-Violation

**Symptom**: Agent output contains terms or patterns that the agent's own standards explicitly prohibit.

**Cause**: The human-authored instruction file (AGENTS.md or task description) itself contained the prohibited content. The agent faithfully executed the flawed instructions. For example, a brand guideline says "never use term X", but the page footer template in the same file uses term X.

**Fix**: Include compliance scanning in the reviewer's audit checklist. Let the reviewer agent catch errors in human-written instruction files — not just in generated content. This is one of the strongest arguments for the multi-agent review model: even the human operator has blind spots, and the review system can catch them.

## Performance Benchmarks

| Agent | Time | Tokens |
|-------|------|--------|
| Writer | 15-30 min | 40-60K |
| Reviewer | 5-10 min | 15-30K |
| Scorer | 2-4 min | 7-15K |
| Fixer | 10-15 min | 30-40K |

Total pipeline: ~60-90 minutes per product.