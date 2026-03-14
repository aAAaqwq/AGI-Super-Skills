---
name: telegram-groups
description: Posting, members, Telegram group management
---
# Telegram Groups

> Operations with Telegram groups: listing, posting, members, management

## When to use

- "show my telegram groups"
- "post in a group"
- "add users to a group"
- "list group members"
- "rename a group"
- "create a topic"

## Tool

`$TG_TOOLS_PATH/tools/tg_groups.py`

## How to run

### List groups

```bash
# Groups only
python3 $TG_TOOLS_PATH/tools/tg_groups.py list

# Groups + channels
python3 $TG_TOOLS_PATH/tools/tg_groups.py list --all
```

### Post in a group

```bash
# Text directly
python3 $TG_TOOLS_PATH/tools/tg_groups.py post "Group Name" --message "Hello!"

# From file
python3 $TG_TOOLS_PATH/tools/tg_groups.py post "Group Name" --message-file msg.txt

# In a specific topic (forum group)
python3 $TG_TOOLS_PATH/tools/tg_groups.py post "Group Name" --message "Hello!" --topic 123
```

Group Name -- search by substring (case-insensitive).

### List members

```bash
python3 $TG_TOOLS_PATH/tools/tg_groups.py members "Group Name"
```

### Add users

```bash
python3 $TG_TOOLS_PATH/tools/tg_groups.py add-users "Group Name" --input users.csv
```

CSV format: `username,name`

### Rename a group

```bash
python3 $TG_TOOLS_PATH/tools/tg_groups.py rename "Group Name" --name "New Name"
```

### Create a topic (forum group)

```bash
python3 $TG_TOOLS_PATH/tools/tg_groups.py topics "Group Name" --add "Topic Title"
python3 $TG_TOOLS_PATH/tools/tg_groups.py topics "Group Name" --add "Topic" --color 6FB9F0
```

## Limitations

- `add-users`: requires admin rights, mutual contact, privacy settings
- `rename`: requires admin rights
- `topics`: only for forum groups
- 2 sec delay between adding users (rate limit)

## Related skills

- `telegram-send` -- DM sending (not to a group)
- `telegram-scrape` -- searching channels/groups
