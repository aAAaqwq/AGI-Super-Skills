# Pi Planning With Files

> **Work like Manus** — Use persistent markdown files as your "working memory on disk."

A [Pi Coding Agent](https://pi.dev) skill that transforms your workflow to use persistent markdown files for planning, progress tracking, and knowledge storage.

## The Problem

Most AI agents suffer from:
- **Volatile memory** — Context resets lose history
- **Goal drift** — Long tasks lose focus
- **Hidden errors** — Failures aren't tracked

## The Solution

For every complex task, create THREE files:
- `task_plan.md` (Phases & Progress)
- `findings.md` (Research & Notes)
- `progress.md` (Session Log)

---

## Installation

### Pi Install

```bash
pi install npm:pi-planning-with-files
```

### Manual Install

1. Navigate to your project root.
2. Create the `.pi/skills` directory if it doesn't exist.
3. Copy the `planning-with-files` skill folder into `.pi/skills/`.

---

## Usage

Pi Agent automatically discovers skills in `.pi/skills` or installed via NPM.

### Start Planning

Ask Pi:
```
Use the planning-with-files skill to help me with this task.
```
Or:
```
Start by creating task_plan.md.
```

## Important Limitations

> **Note:** Hooks (PreToolUse, PostToolUse, Stop) are **Claude Code specific** and are not currently supported in Pi Agent.

### What works in Pi Agent:
- Core 3-file planning pattern
- Templates (task_plan.md, findings.md, progress.md)
- All planning rules and guidelines
- The 2-Action Rule
- The 3-Strike Error Protocol
- Session Recovery (via `session-catchup.py`)

### Session Recovery
If you clear context, recover your state:
```bash
python3 .pi/skills/planning-with-files/scripts/session-catchup.py .
```

## File Structure

When installed, the skill provides templates to create:

```
your-project/
├── task_plan.md
├── findings.md
├── progress.md
```
