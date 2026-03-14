---
name: mcp-agent-connect
description: Connect to an AI agent via MCP using their mcp_url from CRM. Discovers capabilities via agent.json, registers MCP server, and enables tool-based communication.
allowed-tools: Read, Bash, WebFetch
---
# MCP Agent Connect

> Look up an agent's MCP endpoint from CRM, discover their capabilities, register in Claude Code, and interact via tools.

## When to use

- "Connect to [contact]'s agent"
- "What can [company]'s agent do?"
- "Book a meeting through [person]'s agent"
- A CRM contact has `mcp_url` set and user wants to interact
- User provides a new agent URL to register

## Paths

| What | Path |
|------|------|
| CRM Companies | `$CRM_PATH/contacts/companies.csv` |
| CRM People | `$CRM_PATH/contacts/people.csv` |
| Activities | `$CRM_PATH/activities.csv` |

## How to execute

### Step 1: Find mcp_url from CRM

Parse `$ARGUMENTS` for the contact name or company name.

```python
import pandas as pd

name = "$1"  # contact or company name from arguments

# Search people
people = pd.read_csv('$CRM_PATH/contacts/people.csv')
match = people[
    people['first_name'].str.contains(name, case=False, na=False) |
    people['last_name'].str.contains(name, case=False, na=False)
]

# Search companies
companies = pd.read_csv('$CRM_PATH/contacts/companies.csv')
comp_match = companies[
    companies['name'].str.contains(name, case=False, na=False)
]

# Get mcp_url
if not match.empty and pd.notna(match.iloc[0].get('mcp_url')):
    mcp_url = match.iloc[0]['mcp_url']
    contact_name = f"{match.iloc[0]['first_name']} {match.iloc[0].get('last_name', '')}"
elif not comp_match.empty and pd.notna(comp_match.iloc[0].get('mcp_url')):
    mcp_url = comp_match.iloc[0]['mcp_url']
    contact_name = comp_match.iloc[0]['name']
else:
    print(f"No mcp_url found for '{name}'. Add it to the contact's CRM record first.")
    exit()
```

If the user provided a URL directly instead of a contact name, skip CRM lookup and use the URL.

### Step 2: Discover agent capabilities

Use WebFetch to get the agent discovery endpoint:

```
URL: {base_url}/.well-known/agent.json
```

Where `base_url` = mcp_url with trailing `/mcp/` removed.

Parse the response for:
- `name` -- agent name
- `description` -- what the agent does
- `capabilities` -- dict of capability → {url, tools}

Show the user what this agent can do.

### Step 3: Register MCP server

Generate a slug from the agent name:

```python
import re
slug = re.sub(r'[^a-z0-9-]', '', name.lower().replace(' ', '-'))
```

Register in Claude Code:

```bash
claude mcp add <slug> --transport http <mcp_url>
```

Tell the user: "Agent `{name}` registered as `{slug}`. **Restart your Claude Code session** to use their tools."

### Step 4: Log activity

After any MCP interaction, log to activities.csv:

```python
import csv
from datetime import date

activity = {
    'activity_id': f'act-mcp-{date.today().isoformat()}',
    'person_id': person_id,      # if known
    'company_id': company_id,    # if known
    'type': 'message',           # or 'meeting' for bookings
    'channel': 'mcp',
    'direction': 'outbound',
    'subject': f'MCP interaction with {contact_name}',
    'notes': 'Describe what tools were called and the outcome',
    'date': str(date.today()),
    'created_by': 'ai',
}
```

Update the contact's `last_contact` and `last_updated` fields.

## Troubleshooting

| Problem | Solution |
|---------|----------|
| Tools not available after add | Restart Claude Code session |
| agent.json not found | Check URL, try `{base_url}/.well-known/agent.json` in browser |
| Connection timeout | Verify agent server is running and accessible |
| MCP URL returns 404 | Ensure URL ends with `/` (trailing slash) |
| No mcp_url in CRM | Ask user to provide the URL, then add it to the contact record |

## Related skills

- `agent-contacts` -- local agent phone book (add/list/remove without CRM)
- `log-activity` -- log any communication to activities.csv
- `query-leads` -- find CRM contacts, filter by mcp_url
