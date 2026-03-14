# Claude Skills

**Modular skill registry for [Claude Code](https://docs.anthropic.com/en/docs/claude-code/overview).** Lazy-loaded, auto-discovered skills that extend your AI assistant with CRM, PM, multi-channel communication, automation agents, and more.

## How It Works

Skills are markdown files (`SKILL.md`) that Claude Code loads on demand. Each skill contains:
- **When to use** -- triggers that tell Claude when to activate the skill
- **How to execute** -- step-by-step instructions, code snippets, paths
- **Constraints** -- rate limits, validation rules, safety checks

Claude reads the skill description and decides when to load it -- no manual invocation needed.

## Quick Start

```bash
# 1. Clone
git clone https://github.com/your-org/claude-skills.git
cd claude-skills

# 2. Configure
cp setup/config.example.yaml setup/config.yaml
# Edit config.yaml with your paths

# 3. Install (creates symlinks)
bash setup/install.sh

# 4. Open your project in Claude Code
claude
# Skills are now auto-discovered!
```

## Skill Categories

| Category | Skills | What they do |
|----------|--------|-------------|
| **core/** | dispatcher, memory, timezone, agent-contacts | Multi-skill routing, persistent memory, timezone handling, AI agent contacts |
| **crm/** | add-lead, update-lead, query-leads, log-activity, crm-import, change-review | Full CRM lifecycle management |
| **pm/** | show-today, daily-briefing, weekly-review, task-prioritization, create-project, pm-done | Project and task management |
| **channels/** | telegram-send, telegram-check, email-read, email-send-bulk, whatsapp-send, mass-outreach, + more | Multi-channel communication |
| **agents/** | daily-briefing-run, email-outreach-run, telegram-inbound-run, watchers-run, process-analyst, + more | Autonomous automation agents |
| **dev/** | code-review, git-workflow | Development workflow tools |
| **finance/** | invoice, invoice-generator-agent, payment-tracker-run | Invoicing and payment tracking |
| **infra/** | google-auth, telegram-session, remote-access, deploy-website | Infrastructure and auth setup |
| **sales/** | call-prep | Sales preparation tools |

**53 skills** across 9 categories.

## Architecture

```
~/.claude/skills/                    (flat symlinks, auto-discovered)
├── telegram-send -> ~/claude-skills/skills/channels/telegram-send/
├── daily-briefing -> ~/claude-skills/skills/pm/daily-briefing/
├── add-lead -> ~/claude-skills/skills/crm/add-lead/
└── ...

~/claude-skills/skills/              (git repo, organized by category)
├── core/dispatcher/SKILL.md
├── crm/add-lead/SKILL.md
├── channels/telegram-send/SKILL.md
├── agents/daily-briefing-run/SKILL.md
└── ...
```

### Why Symlinks?

- Claude Code discovers skills from `~/.claude/skills/` (flat directory)
- The git repo organizes skills by category for maintainability
- Symlinks bridge the two: flat discovery + organized source

## Ecosystem

Claude Skills is part of a three-repo system. Each works standalone, together they form a complete business operating system:

| Repo | Purpose |
|------|---------|
| [plaintext-pm](https://github.com/your-org/plaintext-pm) | Project & task management |
| [plaintext-crm](https://github.com/your-org/plaintext-crm) | CRM: contacts, leads, deals, activities |
| **claude-skills** (this repo) | Skills framework, agents, multi-channel automation |

## Creating a New Skill

```bash
# 1. Create skill directory
mkdir -p skills/{category}/{skill-name}

# 2. Create SKILL.md from template
cp skills/TEMPLATE.md skills/{category}/{skill-name}/SKILL.md

# 3. Edit SKILL.md -- add frontmatter, instructions, code

# 4. Create symlink
ln -s ~/claude-skills/skills/{category}/{skill-name} ~/.claude/skills/{skill-name}

# 5. Commit
git checkout -b feat/{skill-name}
git add .
git commit -m "Add {skill-name} skill"
git push -u origin feat/{skill-name}
# Create PR, squash merge
```

See `skills/TEMPLATE.md` for the full template and `docs/SKILL_GUIDE.md` for detailed instructions.

## Agents

Agents are skills that run autonomously -- they execute multi-step workflows on a schedule or trigger. Examples:

- **daily-briefing-run** -- Morning report: tasks + email + CRM follow-ups
- **email-outreach-run** -- Automated email campaigns with rate limiting
- **telegram-inbound-run** -- Process incoming Telegram messages, classify, route
- **watchers-run** -- Monitor CRM triggers (stale leads, overdue payments)

See `docs/AGENT_GUIDE.md` for the agent pattern.

## Configuration

All paths are configurable via `setup/config.yaml`:

```yaml
paths:
  crm: ../plaintext-crm/sales/crm
  pm: ../plaintext-pm/pm
  google_tools: ~/google-tools
  agents: ~/agents
```

Skills reference these as `$CRM_PATH`, `$PM_PATH`, etc. Replace with your actual paths during setup.

## Requirements

- [Claude Code](https://docs.anthropic.com/en/docs/claude-code/overview) or [Cursor IDE](https://cursor.sh)
- Python 3.10+ (for CRM/PM skills)
- Node.js 18+ (for WhatsApp integration)
- Additional per-skill dependencies documented in each SKILL.md

## License

MIT

## Credits

Built by [@your-org](https://github.com/your-org).
