# Pi Agent Setup

How to use planning-with-files with [Pi Coding Agent](https://pi.dev).

---

## Installation

### Pi Install

```bash
pi install npm:pi-planning-with-files
```

### Manual Install

1. Navigate to your project root.
2. Create the `.pi/skills` directory if it doesn't exist.
3. Copy the `planning-with-files` skill.

```bash
# Clone the repo
git clone https://github.com/OthmanAdi/planning-with-files.git
# Copy the skill
mkdir -p ~/.pi/agent/skills
cp -r planning-with-files/.pi/skills/planning-with-files .pi/skills/
```

---

## Usage

Pi Agent automatically discovers skills in `.pi/skills`.

To use the skill, you can explicitly invoke it or let Pi discover it based on the task description.

### Explicit Invocation

```bash
/skill:planning-with-files
```

Or just ask Pi:

```
Use the planning-with-files skill to help me with this task.
```

---

## Important Limitations

> **Note:** Hooks (PreToolUse, PostToolUse, Stop) are **Claude Code specific** and are not currently supported in Pi Agent.

### What works in Pi Agent:

- Core 3-file planning pattern
- Templates (task_plan.md, findings.md, progress.md)
- All planning rules and guidelines
- The 2-Action Rule
- The 3-Strike Error Protocol
- Read vs Write Decision Matrix
- Helper scripts (via explicit invocation or skill instructions)

### What works differently:

- **Session Recovery:** You must manually run the catchup script if needed:
  ```bash
  python3 .pi/skills/planning-with-files/scripts/session-catchup.py .
  ```
  (The skill provides instructions for this)

---

## Manual Workflow

Since hooks don't run automatically, follow the pattern:

### 1. Create planning files first

The skill instructions will guide Pi to create these files.
If not, ask:
```
Start by creating task_plan.md, findings.md, and progress.md using the planning-with-files templates.
```

### 2. Re-read plan before decisions

Periodically ask:
```
Read task_plan.md to refresh our context.
```

### 3. Update files after phases

After completing a phase:
```
Update task_plan.md to mark this phase complete.
Update progress.md with what was done.
```

---

## File Structure

```
your-project/
├── .pi/
│   └── skills/
│       └── planning-with-files/
│           ├── SKILL.md
│           ├── templates/
│           ├── scripts/
│           └── ...
├── task_plan.md
├── findings.md
├── progress.md
└── ...
```

---

## Troubleshooting

If Pi doesn't seem to follow the planning rules:
1. Ensure the skill is loaded (ask "What skills do you have available?").
2. Explicitly ask it to read the `SKILL.md` file: `Read .pi/skills/planning-with-files/SKILL.md`.
3. Use the `/skill:planning-with-files` command if enabled.
