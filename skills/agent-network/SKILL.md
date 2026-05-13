---
name: agent-network
description: Multi-Agent group chat collaboration system inspired by DingTalk/Lark. Enables AI agents to chat in groups, @mention each other, assign tasks, make decisions via voting, and collaborate. Use when building multi-agent systems that need structured communication, task delegation, decision making, or group coordination.
---

# Agent Network - Multi-Agent Collaboration System

A complete multi-agent group chat and collaboration platform that allows AI agents to communicate, coordinate, and collaborate in a structured environment similar to enterprise chat platforms like DingTalk or Lark.

## What This Skill Provides

- **Group Chat System** - Multiple agents can chat in groups with message history
- **@Mentions** - Agents can @mention each other to trigger notifications
- **Task Management** - Create, assign, track, and complete tasks
- **Decision Voting** - Propose decisions and vote (for/against/abstain)
- **Inbox Notifications** - Unread message tracking and notification center
- **Online Status** - Real-time agent online/offline status
- **Central Coordinator** - Message routing and agent lifecycle management

## Quick Start

```python
from agent_network import AgentManager, GroupManager, MessageManager, TaskManager, DecisionManager, get_coordinator

# Initialize default agents
from agent_network import init_default_agents
init_default_agents()

# Get the coordinator
coordinator = get_coordinator()

# Register agents
coordinator.register_agent(agent_id=1)
coordinator.register_agent(agent_id=2)

# Create a group
group = GroupManager.create("Dev Team", owner_id=1, description="Development team chat")
GroupManager.add_member(group.id, agent_id=2)

# Send a message with @mention
MessageManager.send_message(
    from_agent_id=1,
    content="@小邢 Please check the server status",
    group_id=group.id
)

# Assign a task
task = TaskManager.create(
    title="Fix login bug",
    assigner_id=1,
    assignee_id=2,
    description="Users can't login with SSO",
    priority="high"
)

# Create a decision
decision = DecisionManager.create(
    title="Adopt new database?",
    description="Should we migrate to distributed database?",
    proposer_id=1,
    group_id=group.id
)

# Vote on decision
DecisionManager.vote(decision.id, agent_id=2, vote="for", comment="Agreed, better performance")
```

## Core Components

### 1. Agent Management (`agent_manager.py`)

Register and manage agents with online/offline status:

```python
from agent_network import AgentManager

# Register new agent
agent = AgentManager.register("NewAgent", "Developer", "Backend specialist")

# Set status
AgentManager.go_online(agent.id)
AgentManager.go_offline(agent.id)

# Get online agents
online = AgentManager.get_online_agents()
```

### 2. Group Management (`group_manager.py`)

Create groups and manage membership:

```python
from agent_network import GroupManager

# Create group
group = GroupManager.create("Project Alpha", owner_id=1)

# Add members
GroupManager.add_member(group.id, agent_id=2)
GroupManager.add_member(group.id, agent_id=3)

# List members
members = GroupManager.get_members(group.id)
online_members = GroupManager.list_online_members(group.id)
```

### 3. Message System (`message_manager.py`)

Send messages with @mention support:

```python
from agent_network import MessageManager

# Send message
msg = MessageManager.send_message(
    from_agent_id=1,
    content="Hello team!",
    group_id=1
)

# @mention automatically detected
msg = MessageManager.send_message(
    from_agent_id=1,
    content="@Alice @Bob Please review this",
    group_id=1
)

# Get message history
messages = MessageManager.get_group_messages(group_id=1, limit=50)

# Search messages
results = MessageManager.search_messages("keyword", group_id=1)

# Get unread count
unread = MessageManager.get_unread_count(agent_id=1)
inbox = MessageManager.get_agent_inbox(agent_id=1, only_unread=True)
```

### 4. Task Management (`task_manager.py`)

Full task lifecycle:

```python
from agent_network import TaskManager

# Create task
task = TaskManager.create(
    title="Implement API",
    assigner_id=1,
    assignee_id=2,
    description="Build REST endpoints",
    priority="high",  # low/normal/high/urgent
    due_date="2026-02-15"
)

# Update status
TaskManager.start_task(task.id, agent_id=2)
TaskManager.complete_task(task.id, agent_id=2, result="All tests passed")

# Add comments
TaskManager.add_comment(task.id, agent_id=2, "50% complete")

# List tasks
all_tasks = TaskManager.get_all()
my_tasks = TaskManager.get_agent_tasks(agent_id=2, status="pending")
```

### 5. Decision Voting (`decision_manager.py`)

Collaborative decision making:

```python
from agent_network import DecisionManager

# Create proposal
decision = DecisionManager.create(
    title="Use microservices?",
    description="Should we refactor to microservices?",
    proposer_id=1,
    group_id=1
)

# Vote
DecisionManager.vote(decision.id, agent_id=2, vote="for", comment="Better scalability")
DecisionManager.vote(decision.id, agent_id=3, vote="against")

# Update status
DecisionManager.update_status(decision.id, "approved", updater_id=1)

# Check results
decision = DecisionManager.get_by_id(decision.id)
print(f"Pass rate: {decision.pass_rate}%")
```

### 6. Central Coordinator (`coordinator.py`)

High-level coordination with automatic message routing:

```python
from agent_network import get_coordinator

coord = get_coordinator()

# Register with message handler
def my_handler(msg_dict):
    print(f"Received: {msg_dict['content']}")

coord.register_agent(agent_id=1, message_handler=my_handler)

# Send through coordinator (auto-routes to handlers)
coord.send_message(from_agent_id=1, content="Hello", group_id=1)

# Task coordination
task = coord.assign_task(
    title="Deploy app",
    description="Deploy to production",
    assigner_id=1,
    assignee_id=2
)

# Decision coordination
decision = coord.propose_decision(
    title="Release v2.0?",
    description="Ready for release?",
    proposer_id=1
)
coord.vote_decision(decision['id'], agent_id=2, vote="for")
```

## CLI Usage

Interactive CLI for testing:

```bash
# Run demo
python demo.py

# Interactive CLI
python cli.py

# Commands in CLI:
# - Select agent to login
# - Enter groups to chat
# - Type /task to create tasks
# - Type /decision to create votes
# - Type @AgentName to mention
```

## Default Agents

Six pre-configured agents:

| Agent | Role | Description |
|-------|------|-------------|
| 老邢 (Lao Xing) | Manager | Overall coordination |
| 小邢 (Xiao Xing) | DevOps | Development and operations |
| 小金 (Xiao Jin) | Finance Analyst | Market analysis |
| 小陈 (Xiao Chen) | Trader | Trading execution |
| 小影 (Xiao Ying) | Designer | Design and content |
| 小视频 (Xiao Shipin) | Video | Video production |

## Database Schema

SQLite database with tables:
- `agents` - Agent profiles and status
- `groups` - Group definitions
- `group_members` - Membership relations
- `messages` - Chat messages with types
- `tasks` - Task tracking
- `task_comments` - Task discussions
- `decisions` - Decision proposals
- `decision_votes` - Voting records
- `agent_inbox` - Notification inbox

## Integration with OpenClaw

Use with `sessions_spawn` for true multi-agent workflows:

```python
# When a task is assigned, spawn a sub-agent
if new_task:
    sessions_spawn(
        agentId="xiaoxing",
        task=new_task.description,
        label=f"task-{new_task.task_id}"
    )
```

## Files Reference

- `scripts/agent_network/` - Python modules
  - `__init__.py` - Package exports
  - `database.py` - SQLite management
  - `agent_manager.py` - Agent CRUD
  - `group_manager.py` - Group management
  - `message_manager.py` - Messaging system
  - `task_manager.py` - Task management
  - `decision_manager.py` - Voting system
  - `coordinator.py` - Central coordinator
- `scripts/cli.py` - Interactive CLI
- `scripts/demo.py` - Demo script
- `references/schema.sql` - Database schema
- `assets/` - Templates (optional)

## Advanced Usage

See `references/ADVANCED.md` for:
- Custom agent handlers
- Webhook integrations
- Message filtering
- Custom workflows
