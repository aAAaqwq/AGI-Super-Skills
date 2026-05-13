# Legal Hook Setup Guide

Configure automatic legal self-improvement triggers for AI coding agents.

## Overview

Hooks enable proactive legal finding capture by injecting reminders at key moments:
- **UserPromptSubmit**: Reminder after each prompt to evaluate legal findings
- **PostToolUse (Bash)**: Detection when legal-relevant patterns appear in command output

## Claude Code Setup

### Option 1: Project-Level Configuration

Create `.claude/settings.json` in your project root:

```json
{
  "hooks": {
    "UserPromptSubmit": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "./skills/self-improving-legal/scripts/activator.sh"
          }
        ]
      }
    ],
    "PostToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "./skills/self-improving-legal/scripts/error-detector.sh"
          }
        ]
      }
    ]
  }
}
```

### Option 2: User-Level Configuration

Add to `~/.claude/settings.json` for global activation:

```json
{
  "hooks": {
    "UserPromptSubmit": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "~/.claude/skills/self-improving-legal/scripts/activator.sh"
          }
        ]
      }
    ]
  }
}
```

### Minimal Setup (Activator Only)

For lower overhead, use only the UserPromptSubmit hook:

```json
{
  "hooks": {
    "UserPromptSubmit": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "./skills/self-improving-legal/scripts/activator.sh"
          }
        ]
      }
    ]
  }
}
```

## Codex CLI Setup

Codex uses the same hook system. Create `.codex/settings.json`:

```json
{
  "hooks": {
    "UserPromptSubmit": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "./skills/self-improving-legal/scripts/activator.sh"
          }
        ]
      }
    ]
  }
}
```

## GitHub Copilot Setup

Copilot doesn't support hooks directly. Add guidance to `.github/copilot-instructions.md`:

```markdown
## Legal Self-Improvement

After completing tasks that involved:
- Reviewing or drafting contract language
- Working with compliance requirements or regulatory filings
- Handling privacy-related code (consent, data deletion, DSAR)
- Addressing intellectual property concerns
- Processing litigation-related documents

Consider logging the finding to `.learnings/` using the legal self-improvement skill format.

CRITICAL: NEVER include privileged attorney-client communications, specific case
strategy, or confidential settlement terms in learning entries.
Always abstract to process-level lessons.
```

## Verification

### Test Activator Hook

1. Enable the hook configuration
2. Start a new Claude Code session
3. Send any prompt
4. Verify you see `<legal-improvement-reminder>` in the context

### Test Error Detector Hook

1. Enable PostToolUse hook for Bash
2. Run a command that produces legal-relevant output: `echo "non-compliance with GDPR detected"`
3. Verify you see `<legal-finding-detected>` reminder

### Dry Run Extract Script

```bash
./skills/self-improving-legal/scripts/extract-skill.sh test-skill --dry-run
```

## Troubleshooting

### Hook Not Triggering

1. **Check script permissions**: `chmod +x scripts/*.sh`
2. **Verify path**: Use absolute paths or paths relative to project root
3. **Check settings location**: Project vs user-level settings
4. **Restart session**: Hooks are loaded at session start

### Permission Denied

```bash
chmod +x ./skills/self-improving-legal/scripts/activator.sh
chmod +x ./skills/self-improving-legal/scripts/error-detector.sh
chmod +x ./skills/self-improving-legal/scripts/extract-skill.sh
```

### Script Not Found

If using relative paths, ensure you're in the correct directory or use absolute paths:

```json
{
  "command": "/absolute/path/to/skills/self-improving-legal/scripts/activator.sh"
}
```

### Too Much Overhead

If the activator feels intrusive:

1. **Use minimal setup**: Only UserPromptSubmit, skip PostToolUse
2. **Add matcher filter**: Only trigger for legal-related prompts:

```json
{
  "matcher": "contract|compliance|regulation|litigation|GDPR|CCPA|clause|indemnity|liability",
  "hooks": [...]
}
```

## Hook Output Budget

The activator is designed to be lightweight:
- **Target**: ~80-120 tokens per activation
- **Content**: Structured reminder with legal-specific guidance
- **Format**: XML tags for easy parsing

## Privilege Protection

- Hook scripts run with the same permissions as the agent
- Scripts only output text; they do not modify files or run commands
- Error detector reads `CLAUDE_TOOL_OUTPUT` environment variable
- Treat `CLAUDE_TOOL_OUTPUT` as potentially sensitive — **never log or forward it verbatim**
- All scripts are opt-in (you must configure them explicitly)
- Recommended default: enable `UserPromptSubmit` only

## Disabling Hooks

To temporarily disable without removing configuration:

1. **Comment out in settings**:
```json
{
  "hooks": {
    // "UserPromptSubmit": [...]
  }
}
```

2. **Or delete the settings file**: Hooks won't run without configuration
