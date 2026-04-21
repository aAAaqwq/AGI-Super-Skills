---
name: agent-contacts
description: AI agent contacts — add, list, remove MCP contacts. Use when someone gives an agent URL, or when you need to view/remove contacts.
disable-model-invocation: true
argument-hint: "[add|list|remove] [url-or-name]"
allowed-tools: Read, Write, Bash, WebFetch
---
# Agent Contacts

> Contact book for AI agents. Add an MCP address and your Claude Code can communicate with other agents.

## When to use

- `/agent-contacts add <url>` — add a new contact
- `/agent-contacts list` — show all contacts
- `/agent-contacts remove <name>` — remove a contact
- When someone gives you an agent/bot URL

## Paths

| What | Path |
|------|------|
| Contacts DB | `~/.claude/agent-contacts.json` |

## contacts.json format

```json
[
  {
    "name": "Your Name",
    "slug": "ivan-schedule",
    "mcp_url": "https://your-agent.example.com/mcp/",
    "discovery_url": "https://your-agent.example.com/.well-known/agent.json",
    "capabilities": ["scheduling"],
    "description": "Scheduling agent for Your Name",
    "added": "2026-02-26"
  }
]
```

## How to execute

Parse `$ARGUMENTS` to determine the command: first word is the command (`add`, `list`, `remove`), the rest is the argument.

### Add: `/agent-contacts add <url>`

```python
import json, re
from datetime import date
from pathlib import Path

CONTACTS_FILE = Path.home() / ".claude" / "agent-contacts.json"

# 1. Load existing contacts
if CONTACTS_FILE.exists():
    contacts = json.loads(CONTACTS_FILE.read_text())
else:
    contacts = []

# 2. Normalize URL — $ARGUMENTS[1] is the URL
url = "$1".strip().rstrip("/")
if not url.endswith("agent.json"):
    discovery_url = url + "/.well-known/agent.json"
else:
    discovery_url = url
    url = url.rsplit("/.well-known/agent.json", 1)[0]

# 3. Use WebFetch to get agent.json content, then parse:
# - name = agent_data["name"]
# - description = agent_data.get("description", "")
# - capabilities = list(agent_data.get("capabilities", {}).keys())
# - mcp_url = agent_data["capabilities"][first_cap]["url"]
#   Ensure mcp_url ends with "/"

# 4. Generate slug
slug = re.sub(r"[^a-z0-9-]", "", name.lower().replace(" ", "-"))

# 5. Check for duplicates
if any(c["slug"] == slug for c in contacts):
    print(f"Contact '{name}' already exists.")
else:
    contacts.append({
        "name": name,
        "slug": slug,
        "mcp_url": mcp_url,
        "discovery_url": discovery_url,
        "capabilities": capabilities,
        "description": description,
        "added": str(date.today()),
    })
    CONTACTS_FILE.write_text(json.dumps(contacts, indent=2, ensure_ascii=False))
```

After saving to JSON, run:
```bash
claude mcp add <slug> --transport http <mcp_url>
```

Notify: "Contact `<name>` added. Restart Claude Code session to use their tools."

### List: `/agent-contacts list`

```python
import json
from pathlib import Path

CONTACTS_FILE = Path.home() / ".claude" / "agent-contacts.json"

if not CONTACTS_FILE.exists():
    print("No agent contacts yet. Use '/agent-contacts add <url>' to add one.")
else:
    contacts = json.loads(CONTACTS_FILE.read_text())
    if not contacts:
        print("No agent contacts yet.")
    else:
        for i, c in enumerate(contacts, 1):
            caps = ", ".join(c.get("capabilities", []))
            print(f"  {i}. {c['name']} ({c['slug']})")
            print(f"     MCP: {c['mcp_url']}")
            print(f"     Capabilities: {caps}")
            print()
```

### Remove: `/agent-contacts remove <name-or-slug>`

```python
import json
from pathlib import Path

CONTACTS_FILE = Path.home() / ".claude" / "agent-contacts.json"
target = "$1".strip().lower()  # name or slug

contacts = json.loads(CONTACTS_FILE.read_text())
match = [c for c in contacts if c["slug"] == target or c["name"].lower() == target]

if not match:
    print(f"Contact '{target}' not found.")
else:
    slug = match[0]["slug"]
    name = match[0]["name"]
    contacts = [c for c in contacts if c["slug"] != slug]
    CONTACTS_FILE.write_text(json.dumps(contacts, indent=2, ensure_ascii=False))
```

After removing from JSON, run:
```bash
claude mcp remove <slug>
```

Notify: "Contact `<name>` removed."

## How to share your address with others

Simply send the link:
```
https://your-agent.example.com/.well-known/agent.json
```

If the person has this skill:
```
/agent-contacts add https://your-agent.example.com
```

If they don't have the skill -- one command:
```bash
claude mcp add ivan-schedule --transport http https://your-agent.example.com/mcp/
```

## Important

- `agent-contacts.json` is created automatically on the first `add`
- Slug must be unique (used as MCP server name in Claude Code)
- MCP URL must end with `/` (trailing slash)
- After `add`, a **new session** of Claude Code is required for MCP tools to become available
- This skill has side effects (`claude mcp add/remove`), hence `disable-model-invocation: true`

## Related skills

- `deploy-website` — deploy page with instructions for new contacts
