# Kiro Setup

How to use planning-with-files with [Kiro](https://kiro.dev).

---

## Important: Kiro Uses Steering Files

Kiro doesn't use the standard `SKILL.md` format. Instead, it uses **Steering Files** — markdown documents in `.kiro/steering/` that provide persistent project knowledge.

See: [Kiro Steering Docs](https://kiro.dev/docs/cli/steering/)

---

## What This Integration Adds

```
.kiro/
├── steering/
│   ├── planning-workflow.md   # Core workflow and quick start
│   ├── planning-rules.md      # Critical rules and error protocols
│   └── planning-templates.md  # Templates for task_plan, findings, progress
└── scripts/
    ├── init-session.sh        # Initialize planning files (Bash)
    ├── init-session.ps1       # Initialize planning files (PowerShell)
    ├── check-complete.sh      # Verify phases complete (Bash)
    └── check-complete.ps1     # Verify phases complete (PowerShell)
```

---

## Installation (Workspace)

Copy to your project:

```bash
git clone https://github.com/OthmanAdi/planning-with-files.git
cp -r planning-with-files/.kiro .kiro
rm -rf planning-with-files
```

---

## Installation (Global)

Copy to your global Kiro config:

```bash
git clone https://github.com/OthmanAdi/planning-with-files.git
mkdir -p ~/.kiro/steering ~/.kiro/scripts
cp planning-with-files/.kiro/steering/* ~/.kiro/steering/
cp planning-with-files/.kiro/scripts/* ~/.kiro/scripts/
rm -rf planning-with-files
```

Global steering applies to all your projects.

---

## Usage

1. Start Kiro in your project
2. For complex tasks, create the planning files:

```bash
# Using the init script
bash .kiro/scripts/init-session.sh

# Or manually create:
# - task_plan.md
# - findings.md
# - progress.md
```

3. The steering files automatically guide Kiro to:
   - Create plans before complex tasks
   - Update findings after research
   - Log progress and errors
   - Follow the 3-strike error protocol

---

## How Steering Works

Kiro loads steering files automatically in every interaction. The planning guidance becomes part of Kiro's project understanding without you needing to explain it each time.

| File | Purpose |
|------|---------|
| `planning-workflow.md` | Core pattern and quick start |
| `planning-rules.md` | Critical rules and error handling |
| `planning-templates.md` | Copy-paste templates |

---

## Helper Scripts

```bash
# Initialize all planning files
bash .kiro/scripts/init-session.sh

# Windows PowerShell
powershell -ExecutionPolicy Bypass -File .kiro/scripts/init-session.ps1

# Verify all phases complete
bash .kiro/scripts/check-complete.sh
```

---

## Notes

- Steering files are loaded automatically — no manual invocation needed
- Workspace steering (`.kiro/`) takes priority over global (`~/.kiro/`)
- Planning files (`task_plan.md`, etc.) go in your project root, not in `.kiro/`
