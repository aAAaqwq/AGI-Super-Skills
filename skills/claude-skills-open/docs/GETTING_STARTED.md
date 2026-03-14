# Getting Started

## Prerequisites

- [Claude Code](https://docs.anthropic.com/en/docs/claude-code/overview) installed
- Python 3.10+ with pandas, pyyaml
- Git

## Installation

### 1. Clone the repo

```bash
git clone https://github.com/your-org/claude-skills.git
cd claude-skills
```

### 2. Configure

```bash
cp setup/config.example.yaml setup/config.yaml
```

Edit `setup/config.yaml` with your actual paths:

```yaml
paths:
  crm: /path/to/your/plaintext-crm/sales/crm
  pm: /path/to/your/plaintext-pm/pm
  google_tools: ~/google-tools
  agents: ~/agents
```

### 3. Install symlinks

```bash
bash setup/install.sh
```

This creates symlinks in `~/.claude/skills/` pointing to each skill in this repo. Claude Code auto-discovers skills from this directory.

### 4. Verify

```bash
ls -la ~/.claude/skills/
```

You should see symlinks for all 53 skills.

### 5. Start using

Open any project with Claude Code:

```bash
claude
```

Skills are loaded on demand. Try:

- "Show my tasks for today" (loads `show-today` skill)
- "Add a new lead for Acme Corp" (loads `add-lead` skill)
- "Check my Telegram messages" (loads `telegram-check` skill)

## Paired Repos

For full functionality, clone the companion repos:

```bash
# CRM (contacts, leads, deals)
git clone https://github.com/your-org/plaintext-crm.git

# PM (projects, tasks)
git clone https://github.com/your-org/plaintext-pm.git
```

Update `setup/config.yaml` paths to point to these repos.

## Next Steps

- Read `docs/SKILL_GUIDE.md` to create your own skills
- Read `docs/AGENT_GUIDE.md` to build automation agents
- Explore `skills/TEMPLATE.md` for the skill file format
