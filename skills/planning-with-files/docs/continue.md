# Continue Setup

How to use planning-with-files with Continue (VS Code / JetBrains).

---

## What This Integration Adds

- Project-level skill: `.continue/skills/planning-with-files/`
- Project-level slash command prompt: `.continue/prompts/planning-with-files.prompt` (Markdown)

Continue supports both **project-level** (`<repo>/.continue/...`) and **global** (`~/.continue/...`) locations.

---

## Installation (Project-level, recommended)

In your project root:

```bash
git clone https://github.com/OthmanAdi/planning-with-files.git
cp -r planning-with-files/.continue .continue
```

Restart Continue (or reload the IDE) so it picks up the new files.

---

## Installation (Global)

Copy the skill and prompt into your global Continue directory:

```bash
git clone https://github.com/OthmanAdi/planning-with-files.git
mkdir -p ~/.continue/skills ~/.continue/prompts
cp -r planning-with-files/.continue/skills/planning-with-files ~/.continue/skills/
cp planning-with-files/.continue/prompts/planning-with-files.prompt ~/.continue/prompts/
```

Restart Continue (or reload the IDE) so it picks up the new files.

---

## Usage

1. In Continue chat, run:
   - `/planning-with-files`
2. The prompt will guide you to:
   - Ensure `task_plan.md`, `findings.md`, `progress.md` exist in your repo root
   - Update these files throughout the task

---

## Helper Scripts (Optional)

From your project root:

```bash
# Create task_plan.md / findings.md / progress.md (if missing)
bash .continue/skills/planning-with-files/scripts/init-session.sh

# Verify all phases marked complete (expects task_plan.md format)
bash .continue/skills/planning-with-files/scripts/check-complete.sh

# Recover unsynced context from last Claude Code session (if you also use Claude Code)
python3 .continue/skills/planning-with-files/scripts/session-catchup.py "$(pwd)"
```

---

## Notes & Limitations

- Continue does not run Claude Code hooks (PreToolUse/PostToolUse/Stop). The workflow is manual: re-read `task_plan.md` before decisions and update it after each phase.
- The three planning files are tool-agnostic and can be used across Claude Code, Cursor, Gemini CLI, and Continue.
