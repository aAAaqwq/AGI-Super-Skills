"""
Agent Network - Multi-Agent Group Chat Collaboration System

A complete multi-agent collaboration platform with group chat, @mentions,
task management, and decision voting.

Example:
    >>> from agent_network import AgentManager, GroupManager, init_default_agents
    >>> from agent_network import get_coordinator
    >>> 
    >>> # Initialize
    >>> init_default_agents()
    >>> 
    >>> # Use coordinator
    >>> coord = get_coordinator()
    >>> coord.register_agent(1)
    >>> coord.send_message(1, "Hello team!", group_id=1)
"""

__version__ = "1.0.0"
__author__ = "Agent Network Team"

# Core imports
from .database import Database, db
from .agent_manager import Agent, AgentManager, init_default_agents
from .group_manager import Group, GroupManager
from .message_manager import Message, MessageManager, MessageType, MessageFormatter
from .task_manager import Task, TaskManager
from .decision_manager import Decision, DecisionManager
from .coordinator import Coordinator, get_coordinator, AgentSession

__all__ = [
    # Version
    "__version__",
    
    # Database
    "Database",
    "db",
    
    # Agent
    "Agent",
    "AgentManager",
    "init_default_agents",
    
    # Group
    "Group",
    "GroupManager",
    
    # Message
    "Message",
    "MessageManager",
    "MessageType",
    "MessageFormatter",
    
    # Task
    "Task",
    "TaskManager",
    
    # Decision
    "Decision",
    "DecisionManager",
    
    # Coordinator
    "Coordinator",
    "get_coordinator",
    "AgentSession",
]

# Constants
DEFAULT_AGENTS = [
    ("老邢", "Manager", "Overall coordination and decision making"),
    ("小邢", "DevOps", "Development and operations"),
    ("小金", "Finance Analyst", "Financial market analysis"),
    ("小陈", "Trader", "Trading execution"),
    ("小影", "Designer", "Design and short video content"),
    ("小视频", "Video Producer", "Video production and editing"),
]
