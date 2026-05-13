# Advanced Usage Guide for Agent Network

## Custom Agent Message Handlers

Register agents with custom handlers for true automation:

```python
from agent_network import get_coordinator, AgentManager

def create_smart_handler(agent_name, capabilities):
    """Create a handler that responds based on agent capabilities"""
    
    def handler(msg_dict):
        content = msg_dict.get('content', '')
        from_agent = msg_dict.get('from_agent_name', 'Unknown')
        msg_type = msg_dict.get('type', 'chat')
        
        # Check if this agent is mentioned
        if f'@{agent_name}' in content:
            print(f"[{agent_name}] I was mentioned by {from_agent}!")
            
            # Auto-respond based on message type
            if 'task' in content.lower() and 'dev' in capabilities:
                print(f"[{agent_name}] 📋 Task-related message detected")
                
            elif 'analyze' in content.lower() and 'finance' in capabilities:
                print(f"[{agent_name}] 📊 Analysis request detected")
                
            elif 'design' in content.lower() and 'design' in capabilities:
                print(f"[{agent_name}] 🎨 Design request detected")
    
    return handler

# Register with smart handlers
coord = get_coordinator()

dev_agent = AgentManager.get_by_name("小邢")
if dev_agent:
    coord.register_agent(
        dev_agent.id,
        message_handler=create_smart_handler("小邢", ["dev", "ops"])
    )

finance_agent = AgentManager.get_by_name("小金")
if finance_agent:
    coord.register_agent(
        finance_agent.id,
        message_handler=create_smart_handler("小金", ["finance", "analyze"])
    )
```

## Webhook Integration

Integrate with external systems via webhooks:

```python
import requests
from agent_network import get_coordinator

class WebhookNotifier:
    def __init__(self, webhook_url):
        self.webhook_url = webhook_url
        self.coord = get_coordinator()
    
    def notify_on_mention(self, msg_dict):
        """Send webhook when agent is mentioned"""
        content = msg_dict.get('content', '')
        
        if '@' in content:  # Someone was mentioned
            payload = {
                'event': 'agent_mentioned',
                'from': msg_dict.get('from_agent_name'),
                'content': content,
                'timestamp': msg_dict.get('created_at'),
                'group': msg_dict.get('group_name')
            }
            
            try:
                requests.post(self.webhook_url, json=payload, timeout=5)
            except Exception as e:
                print(f"Webhook failed: {e}")
    
    def register(self, agent_id):
        """Register webhook handler for an agent"""
        self.coord.register_agent(agent_id, self.notify_on_mention)

# Usage
notifier = WebhookNotifier("https://hooks.slack.com/services/...")
notifier.register(agent_id=1)
```

## Message Filtering and Routing

Custom message routing logic:

```python
from agent_network import MessageManager, AgentManager

class MessageRouter:
    """Advanced message routing with filtering"""
    
    def __init__(self):
        self.filters = []
        self.routes = {}
    
    def add_filter(self, keyword, target_agent_id):
        """Route messages containing keyword to specific agent"""
        self.filters.append((keyword, target_agent_id))
    
    def route_message(self, msg_dict):
        """Apply routing rules to message"""
        content = msg_dict.get('content', '').lower()
        
        for keyword, target_id in self.filters:
            if keyword.lower() in content:
                # Create inbox notification for target agent
                MessageManager.create_inbox_notification(
                    target_id,
                    msg_dict.get('id')
                )
                print(f"Routed message to agent {target_id} (matched: {keyword})")
    
    def auto_assign_tasks(self, msg_dict):
        """Auto-create tasks from certain message patterns"""
        content = msg_dict.get('content', '')
        
        # Pattern: "URGENT: ..." -> Create high priority task
        if content.upper().startswith('URGENT:'):
            from_agent_id = msg_dict.get('from_agent_id')
            
            # Find online DevOps agent
            online_agents = AgentManager.get_online_agents()
            dev_agent = next(
                (a for a in online_agents if 'dev' in a.role.lower()),
                None
            )
            
            if dev_agent:
                from agent_network import TaskManager
                TaskManager.create(
                    title=content[7:50],  # Remove "URGENT:" and truncate
                    assigner_id=from_agent_id,
                    assignee_id=dev_agent.id,
                    description=content,
                    priority="urgent"
                )
                print(f"Auto-created urgent task for {dev_agent.name}")

# Usage
router = MessageRouter()
router.add_filter("bug", target_agent_id=2)
router.add_filter("server down", target_agent_id=2)
router.add_filter("market crash", target_agent_id=3)
```

## Custom Workflows

Build complex multi-agent workflows:

```python
from agent_network import (
    get_coordinator, GroupManager, TaskManager,
    DecisionManager, AgentManager
)
import time

class DeploymentWorkflow:
    """Automated deployment workflow with approvals"""
    
    def __init__(self):
        self.coord = get_coordinator()
        self.group = None
    
    def setup(self):
        """Create deployment group"""
        manager = AgentManager.get_by_name("老邢")
        dev = AgentManager.get_by_name("小邢")
        
        self.group = GroupManager.create(
            "🚀 Deployment Team",
            owner_id=manager.id,
            description="Production deployment coordination"
        )
        
        GroupManager.add_member(self.group.id, dev.id)
        return self.group
    
    def start_deployment(self, version):
        """Start deployment workflow"""
        manager = AgentManager.get_by_name("老邢")
        
        # Step 1: Create decision for approval
        decision = DecisionManager.create(
            title=f"Deploy v{version} to Production?",
            description=f"Ready to deploy version {version}. All tests passed.",
            proposer_id=manager.id,
            group_id=self.group.id
        )
        
        print(f"📊 Deployment decision created: {decision.decision_id}")
        print("Waiting for votes...")
        
        return decision
    
    def on_decision_approved(self, decision_id, version):
        """Callback when deployment is approved"""
        manager = AgentManager.get_by_name("老邢")
        dev = AgentManager.get_by_name("小邢")
        
        # Step 2: Create deployment task
        task = TaskManager.create(
            title=f"Deploy v{version}",
            assigner_id=manager.id,
            assignee_id=dev.id,
            description=f"Execute production deployment for v{version}",
            group_id=self.group.id,
            priority="high"
        )
        
        print(f"📋 Deployment task created: {task.task_id}")
        
        # Step 3: Auto-start task
        TaskManager.start_task(task.id, dev.id)
        print("🚀 Deployment started!")
        
        return task
    
    def complete_deployment(self, task_id, version):
        """Mark deployment complete"""
        dev = AgentManager.get_by_name("小邢")
        
        TaskManager.complete_task(
            task_id,
            dev.id,
            result=f"v{version} successfully deployed"
        )
        
        # Broadcast success
        self.coord.broadcast_system_message(
            f"🎉 v{version} is now live!",
            group_id=self.group.id
        )

# Usage
workflow = DeploymentWorkflow()
group = workflow.setup()
decision = workflow.start_deployment("2.5.0")

# Later, when decision is approved:
# workflow.on_decision_approved(decision.id, "2.5.0")
```

## Scheduled Tasks with Cron

Integrate with cron for scheduled operations:

```python
from datetime import datetime, timedelta
from agent_network import TaskManager, AgentManager

class ScheduledTaskManager:
    """Manage recurring tasks"""
    
    def __init__(self):
        self.scheduled = []
    
    def schedule_daily_report(self, assignee_name="小金"):
        """Schedule daily market report task"""
        agent = AgentManager.get_by_name(assignee_name)
        if not agent:
            return
        
        # Create task for tomorrow morning
        tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
        
        task = TaskManager.create(
            title=f"Daily Market Report - {tomorrow}",
            assigner_id=agent.id,  # Self-assigned
            assignee_id=agent.id,
            description="Generate and distribute daily market analysis",
            due_date=tomorrow,
            priority="normal"
        )
        
        print(f"📅 Scheduled daily report: {task.task_id}")
        return task
    
    def schedule_weekly_review(self, group_id=None):
        """Schedule weekly team review"""
        manager = AgentManager.get_by_name("老邢")
        
        # Find next Friday
        today = datetime.now()
        friday = today + timedelta(days=(4 - today.weekday()) % 7)
        
        task = TaskManager.create(
            title=f"Weekly Team Review - Week {friday.isocalendar()[1]}",
            assigner_id=manager.id,
            assignee_id=manager.id,
            description="Review team progress and plan next week",
            due_date=friday.strftime("%Y-%m-%d"),
            priority="normal",
            group_id=group_id
        )
        
        print(f"📅 Scheduled weekly review: {task.task_id}")
        return task

# Usage with OpenClaw cron
# cron.add(job={...}) to schedule these daily/weekly
```

## Persistence and State Management

Handle agent state across sessions:

```python
import json
import os
from agent_network import AgentManager

class AgentStateManager:
    """Persist agent states to disk"""
    
    def __init__(self, state_dir="./agent_states"):
        self.state_dir = state_dir
        os.makedirs(state_dir, exist_ok=True)
    
    def save_state(self, agent_id, state_dict):
        """Save agent state"""
        filepath = os.path.join(self.state_dir, f"agent_{agent_id}.json")
        with open(filepath, 'w') as f:
            json.dump(state_dict, f, indent=2)
    
    def load_state(self, agent_id):
        """Load agent state"""
        filepath = os.path.join(self.state_dir, f"agent_{agent_id}.json")
        if os.path.exists(filepath):
            with open(filepath, 'r') as f:
                return json.load(f)
        return {}
    
    def restore_all_agents(self):
        """Restore all agent states from disk"""
        for filename in os.listdir(self.state_dir):
            if filename.startswith("agent_") and filename.endswith(".json"):
                agent_id = int(filename.split("_")[1].split(".")[0])
                state = self.load_state(agent_id)
                
                # Restore status
                if state.get('status') == 'online':
                    AgentManager.go_online(agent_id)
                
                print(f"Restored state for agent {agent_id}")

# Usage
state_mgr = AgentStateManager()

# Before shutdown, save states
for agent in AgentManager.get_all():
    state_mgr.save_state(agent.id, {
        'status': agent.status,
        'last_active': agent.last_active,
        'current_tasks': [...]
    })

# On startup, restore
state_mgr.restore_all_agents()
```
