#!/usr/bin/env python3
"""
Agent 群聊协作系统 - 群组管理模块
负责群组的创建、成员管理等
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from database import db
    from agent_manager import AgentManager, Agent
except ImportError:
    from .database import db
    from .agent_manager import AgentManager, Agent


class Group:
    """群组类"""
    
    def __init__(self, id: int = None, group_id: int = None, name: str = "", description: str = "",
                 owner_id: Optional[int] = None, created_at: str = "", **kwargs):
        self.id = id if id is not None else group_id
        self.name = name
        self.description = description
        self.owner_id = owner_id
        self.created_at = created_at
        
        # 额外字段
        self.owner_name: Optional[str] = kwargs.get('owner_name')
        self.members: List[Agent] = []
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'owner_id': self.owner_id,
            'owner_name': self.owner_name,
            'created_at': self.created_at,
            'member_count': len(self.members),
            'members': [m.to_dict() for m in self.members]
        }
    
    def __repr__(self):
        return f"Group({self.name}, members={len(self.members)})"


class GroupManager:
    """群组管理器"""
    
    @staticmethod
    def create(name: str, owner_id: int, description: str = "") -> Optional[Group]:
        """创建新群组"""
        try:
            group_id = db.insert(
                "INSERT INTO groups (name, description, owner_id, created_at) VALUES (?, ?, ?, ?)",
                (name, description, owner_id, datetime.now().isoformat())
            )
            # 自动将创建者加入群组
            GroupManager.add_member(group_id, owner_id)
            return GroupManager.get_by_id(group_id)
        except Exception as e:
            print(f"创建群组失败: {e}")
            return None
    
    @staticmethod
    def get_by_id(group_id: int) -> Optional[Group]:
        """通过 ID 获取群组"""
        row = db.fetch_one(
            """SELECT g.*, a.name as owner_name 
               FROM groups g 
               LEFT JOIN agents a ON g.owner_id = a.id 
               WHERE g.id = ?""",
            (group_id,)
        )
        if row:
            group = Group(**row)
            group.owner_name = row.get('owner_name')
            group.members = GroupManager.get_members(group_id)
            return group
        return None
    
    @staticmethod
    def get_by_name(name: str) -> Optional[Group]:
        """通过名称获取群组"""
        row = db.fetch_one(
            """SELECT g.*, a.name as owner_name 
               FROM groups g 
               LEFT JOIN agents a ON g.owner_id = a.id 
               WHERE g.name = ?""",
            (name,)
        )
        if row:
            group = Group(**row)
            group.owner_name = row.get('owner_name')
            group.members = GroupManager.get_members(row['id'])
            return group
        return None
    
    @staticmethod
    def get_all() -> List[Group]:
        """获取所有群组"""
        rows = db.fetch_all(
            """SELECT g.*, a.name as owner_name 
               FROM groups g 
               LEFT JOIN agents a ON g.owner_id = a.id
               ORDER BY g.created_at DESC"""
        )
        groups = []
        for row in rows:
            group = Group(**row)
            group.owner_name = row.get('owner_name')
            group.members = GroupManager.get_members(row['id'])
            groups.append(group)
        return groups
    
    @staticmethod
    def get_agent_groups(agent_id: int) -> List[Group]:
        """获取 Agent 加入的所有群组"""
        rows = db.fetch_all(
            """SELECT g.*, a.name as owner_name 
               FROM groups g 
               JOIN group_members gm ON g.id = gm.group_id
               LEFT JOIN agents a ON g.owner_id = a.id
               WHERE gm.agent_id = ?
               ORDER BY g.created_at DESC""",
            (agent_id,)
        )
        groups = []
        for row in rows:
            group = Group(**row)
            group.owner_name = row.get('owner_name')
            group.members = GroupManager.get_members(row['id'])
            groups.append(group)
        return groups
    
    @staticmethod
    def add_member(group_id: int, agent_id: int) -> bool:
        """添加群组成员"""
        try:
            db.execute(
                "INSERT INTO group_members (group_id, agent_id, joined_at) VALUES (?, ?, ?)",
                (group_id, agent_id, datetime.now().isoformat())
            )
            return True
        except Exception as e:
            print(f"添加成员失败: {e}")
            return False
    
    @staticmethod
    def remove_member(group_id: int, agent_id: int) -> bool:
        """移除群组成员"""
        affected = db.execute(
            "DELETE FROM group_members WHERE group_id = ? AND agent_id = ?",
            (group_id, agent_id)
        )
        return affected > 0
    
    @staticmethod
    def get_members(group_id: int) -> List[Agent]:
        """获取群组成员列表"""
        rows = db.fetch_all(
            """SELECT a.* FROM agents a
               JOIN group_members gm ON a.id = gm.agent_id
               WHERE gm.group_id = ?
               ORDER BY gm.joined_at""",
            (group_id,)
        )
        return [Agent(**row) for row in rows]
    
    @staticmethod
    def is_member(group_id: int, agent_id: int) -> bool:
        """检查 Agent 是否在群组中"""
        result = db.fetch_one(
            "SELECT 1 FROM group_members WHERE group_id = ? AND agent_id = ?",
            (group_id, agent_id)
        )
        return result is not None
    
    @staticmethod
    def update(group_id: int, name: str = None, description: str = None) -> bool:
        """更新群组信息"""
        updates = []
        params = []
        
        if name:
            updates.append("name = ?")
            params.append(name)
        if description:
            updates.append("description = ?")
            params.append(description)
        
        if not updates:
            return False
        
        params.append(group_id)
        affected = db.execute(
            f"UPDATE groups SET {', '.join(updates)} WHERE id = ?",
            tuple(params)
        )
        return affected > 0
    
    @staticmethod
    def delete(group_id: int) -> bool:
        """删除群组（同时删除所有相关记录）"""
        # 数据库外键会处理相关记录的级联删除
        affected = db.execute("DELETE FROM groups WHERE id = ?", (group_id,))
        return affected > 0
    
    @staticmethod
    def transfer_ownership(group_id: int, new_owner_id: int) -> bool:
        """转移群组所有权"""
        # 确保新群主在群组中
        if not GroupManager.is_member(group_id, new_owner_id):
            GroupManager.add_member(group_id, new_owner_id)
        
        affected = db.execute(
            "UPDATE groups SET owner_id = ? WHERE id = ?",
            (new_owner_id, group_id)
        )
        return affected > 0
    
    @staticmethod
    def get_member_count(group_id: int) -> int:
        """获取群组成员数量"""
        result = db.fetch_one(
            "SELECT COUNT(*) as count FROM group_members WHERE group_id = ?",
            (group_id,)
        )
        return result['count'] if result else 0
    
    @staticmethod
    def list_online_members(group_id: int) -> List[Agent]:
        """获取群组在线成员"""
        rows = db.fetch_all(
            """SELECT a.* FROM agents a
               JOIN group_members gm ON a.id = gm.agent_id
               WHERE gm.group_id = ? AND a.status = 'online'
               ORDER BY a.last_active DESC""",
            (group_id,)
        )
        return [Agent(**row) for row in rows]
