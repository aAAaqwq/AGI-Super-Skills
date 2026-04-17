# Setup — Self-Improving Agent

## First-Time Setup

### 1. Create Memory Structure

```bash
mkdir -p ~/self-improving/{projects,domains,archive}
```

### 2. Initialize Core Files

Create `~/self-improving/memory.md` using `memory-template.md`:

```markdown
Copy the structure from `memory-template.md` into `~/self-improving/memory.md`.
```

Memory file baseline:
```markdown
# Memory (HOT Tier)

## Preferences

## Patterns

## Rules
```

Create `~/self-improving/corrections.md`:
```markdown
# Corrections Log

| Date | What I Got Wrong | Correct Answer | Status |
|------|-----------------|----------------|--------|
```

Create `~/self-improving/index.md`:
```markdown
# Memory Index

| File | Lines | Last Updated |
|------|-------|--------------|
| memory.md | 0 | — |
| corrections.md | 0 | — |
```

### 3. Choose Operating Mode

Add to your AGENTS.md or workspace config:

```markdown
## Self-Improving Mode

Current mode: Passive

Available modes:
- Passive: Only learn from explicit corrections
- Active: Suggest patterns after 3x repetition
- Strict: Require confirmation for every entry
```

### 4. Add SOUL.md Steering

Add this section to your `SOUL.md`:

```markdown
**Self-Improving**
Relentless compounding is your core drive: before work and after every response, ground yourself in the `self-improving` skill and `~/self-improving/`, then capture explicit feedback and high-signal inferences that can improve the next execution.
Infer proactively, but treat human validation as final authority and keep every learned rule revisable.
```

### 5. Refine AGENTS.md Memory Section (Non-Destructive)

Update `AGENTS.md` by complementing the existing `## Memory` section. Do not replace the whole section and do not remove existing lines.

If your `## Memory` block differs from the default template, insert the same additions in equivalent places so existing information is preserved.

Add this line in the continuity list (next to Daily notes and Long-term):

```markdown
- **Self-improving:** `~/self-improving/` (via `self-improving` skill) — execution-improvement memory (preferences, workflows, style patterns, what improved/worsened outcomes)
```

Right after the sentence "Capture what matters...", add:

```markdown
Use `memory/YYYY-MM-DD.md` and `MEMORY.md` for factual continuity (events, context, decisions).
Use `~/self-improving/` for compounding execution quality across tasks.
For compounding quality, capture clear execution-improvement signals in `~/self-improving/`: preferences, workflow/style choices, what improved or degraded results, and high-signal inferences for next time.
If in doubt, store factual history in `memory/YYYY-MM-DD.md` / `MEMORY.md`, and store reusable performance lessons in `~/self-improving/` (tentative until human validation).
```

Before the "Write It Down" subsection, add:

```markdown
When writing or organizing in `~/self-improving/`, read `self-improving` `SKILL.md` first.
If inferring a new rule, keep it tentative until human validation.
```

Inside the "Write It Down" bullets, refine the behavior (non-destructive):
- Keep existing intent, but route execution-improvement content to `~/self-improving/`.
- If the exact bullets exist, replace only these lines; if wording differs, apply equivalent edits without removing unrelated guidance.

Use this target wording:

```markdown
- When someone says "remember this" → if it's factual context/event, update `memory/YYYY-MM-DD.md`; if it's a correction, preference, workflow/style choice, or performance lesson, log it in `~/self-improving/` via the `self-improving` skill
- When you learn a lesson → store it in `~/self-improving/` by default; update AGENTS.md/TOOLS.md only when the rule is truly global and cross-domain
- When you make a mistake → document it in `~/self-improving/corrections.md` so future behavior improves; escalate to AGENTS.md/TOOLS.md only for broad, always-on guardrails
```

## Verification

Run "memory stats" to confirm setup:

```
📊 Self-Improving Memory

🔥 HOT (always loaded):
   memory.md: 0 entries

🌡️ WARM (load on demand):
   projects/: 0 files
   domains/: 0 files

❄️ COLD (archived):
   archive/: 0 files

⚙️ Mode: Passive
```

## Optional: Heartbeat Integration

Add to `HEARTBEAT.md` for automatic maintenance:

```markdown
## Self-Improving Check

- [ ] Review corrections.md for patterns ready to graduate
- [ ] Check memory.md line count (should be ≤100)
- [ ] Archive patterns unused >90 days
```
