#!/usr/bin/env python3
"""
Agent 群聊协作系统 - Agent 管理模块
负责 Agent 的注册、登录、状态管理等
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
import sqlite3
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from database import db
except ImportError:
    from .database import db


class Agent:
    """Agent 类"""
    
    def __init__(self, id: int = None, agent_id: int = None, name: str = "", role: str = "", 
                 description: str = "", status: str = "offline", created_at: str = "", 
                 last_active: str = "", **kwargs):
        self.id = id if id is not None else agent_id
        self.name = name
        self.role = role
        self.description = description
        self.status = status
        self.created_at = created_at
        self.last_active = last_active
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'name': self.name,
            'role': self.role,
            'description': self.description,
            'status': self.status,
            'created_at': self.created_at,
            'last_active': self.last_active
        }
    
    def __repr__(self):
        return f"Agent({self.name} - {self.role})"


class AgentManager:
    """Agent 管理器"""
    
    @staticmethod
    def register(name: str, role: str, description: str = "") -> Optional[Agent]:
        """注册新 Agent"""
        try:
            agent_id = db.insert(
                "INSERT INTO agents (name, role, description, status, last_active) VALUES (?, ?, ?, 'offline', ?)",
                (name, role, description, datetime.now().isoformat())
            )
            return AgentManager.get_by_id(agent_id)
        except sqlite3.IntegrityError:
            print(f"Agent '{name}' 已存在")
            return None
    
    @staticmethod
    def get_by_id(agent_id: int) -> Optional[Agent]:
        """通过 ID 获取 Agent"""
        row = db.fetch_one("SELECT * FROM agents WHERE id = ?", (agent_id,))
        if row:
            return Agent(**row)
        return None
    
    @staticmethod
    def get_by_name(name: str) -> Optional[Agent]:
        """通过名称获取 Agent"""
        row = db.fetch_one("SELECT * FROM agents WHERE name = ?", (name,))
        if row:
            return Agent(**row)
        return None
    
    @staticmethod
    def get_all() -> List[Agent]:
        """获取所有 Agent"""
        rows = db.fetch_all("SELECT * FROM agents ORDER BY created_at")
        return [Agent(**row) for row in rows]
    
    @staticmethod
    def update_status(agent_id: int, status: str) -> bool:
        """更新 Agent 状态"""
        valid_status = ['online', 'offline', 'busy']
        if status not in valid_status:
            return False
        
        affected = db.execute(
            "UPDATE agents SET status = ?, last_active = ? WHERE id = ?",
            (status, datetime.now().isoformat(), agent_id)
        )
        return affected > 0
    
    @staticmethod
    def go_online(agent_id: int) -> bool:
        """Agent 上线"""
        return AgentManager.update_status(agent_id, 'online')
    
    @staticmethod
    def go_offline(agent_id: int) -> bool:
        """Agent 下线"""
        return AgentManager.update_status(agent_id, 'offline')
    
    @staticmethod
    def set_busy(agent_id: int) -> bool:
        """设置 Agent 忙碌状态"""
        return AgentManager.update_status(agent_id, 'busy')
    
    @staticmethod
    def delete(agent_id: int) -> bool:
        """删除 Agent"""
        affected = db.execute("DELETE FROM agents WHERE id = ?", (agent_id,))
        return affected > 0
    
    @staticmethod
    def get_online_agents() -> List[Agent]:
        """获取在线 Agent 列表"""
        rows = db.fetch_all("SELECT * FROM agents WHERE status = 'online' ORDER BY last_active DESC")
        return [Agent(**row) for row in rows]


# 初始化默认 Agent 列表
def init_default_agents():
    """初始化默认 Agent"""
    default_agents = [
        ("老邢", "总管", "负责整体协调和决策"),
        ("小邢", "开发运维", "负责系统开发和运维"),
        ("小金", "金融市场分析", "负责金融市场分析和研究"),
        ("小陈", "美股交易", "负责美股交易执行"),
        ("小影", "设计/短视频", "负责设计和短视频内容"),
        ("小视频", "视频制作", "负责视频制作和后期"),
    ]
    
    for name, role, desc in default_agents:
        agent = AgentManager.get_by_name(name)
        if not agent:
            AgentManager.register(name, role, desc)
            print(f"已创建 Agent: {name} ({role})")


if __name__ == "__main__":
    init_default_agents()
    print("\n所有 Agent 列表:")
    for agent in AgentManager.get_all():
        print(f"  - {agent}")
