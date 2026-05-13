#!/usr/bin/env python3
"""
Agent 群聊协作系统 - 消息核心模块
负责消息的创建、发送、@提及处理等
"""

import re
import json
from datetime import datetime
from typing import Optional, List, Dict, Any, Tuple
from enum import Enum
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from database import db
    from agent_manager import AgentManager, Agent
except ImportError:
    from .database import db
    from .agent_manager import AgentManager, Agent


class MessageType(Enum):
    """消息类型枚举"""
    CHAT = "chat"           # 普通聊天
    MENTION = "mention"     # @提及
    TASK_ASSIGN = "task_assign"    # 任务指派
    TASK_COMPLETE = "task_complete"  # 任务完成
    DECISION = "decision"   # 决策提议
    SYSTEM = "system"       # 系统消息
    REPLY = "reply"         # 回复消息


class Message:
    """消息类"""
    
    def __init__(self, id: int = None, msg_id: int = None, group_id: Optional[int] = None,
                 from_agent_id: int = None, to_agent_id: Optional[int] = None,
                 content: str = "", msg_type: str = "", type: str = "",
                 reply_to: Optional[int] = None, created_at: str = "",
                 **kwargs):
        self.id = id if id is not None else msg_id
        self.group_id = group_id
        self.from_agent_id = from_agent_id
        self.to_agent_id = to_agent_id
        self.content = content
        self.type = msg_type if msg_type else type
        self.reply_to = reply_to
        self.created_at = created_at
        
        # 额外字段（通过 JOIN 查询填充）
        self.from_agent_name: Optional[str] = kwargs.get('from_agent_name')
        self.to_agent_name: Optional[str] = kwargs.get('to_agent_name')
        self.group_name: Optional[str] = kwargs.get('group_name')
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'group_id': self.group_id,
            'group_name': self.group_name,
            'from_agent_id': self.from_agent_id,
            'from_agent_name': self.from_agent_name,
            'to_agent_id': self.to_agent_id,
            'to_agent_name': self.to_agent_name,
            'content': self.content,
            'type': self.type,
            'reply_to': self.reply_to,
            'created_at': self.created_at
        }
    
    def __repr__(self):
        return f"Message({self.id}: {self.from_agent_name} -> {self.to_agent_name or 'all'}: {self.content[:30]}...)"


class MessageManager:
    """消息管理器"""
    
    # 用于匹配 @AgentName 的正则表达式
    MENTION_PATTERN = re.compile(r'@([^\s@]+)')
    
    @staticmethod
    def send_message(from_agent_id: int, content: str, group_id: Optional[int] = None,
                     to_agent_id: Optional[int] = None, msg_type: str = "chat",
                     reply_to: Optional[int] = None) -> Optional[Message]:
        """发送消息"""
        # 检测消息中的 @提及
        mentions = MessageManager.detect_mentions(content)
        
        # 如果消息包含 @提及且没有指定接收者，标记为 mention 类型
        if mentions and msg_type == "chat":
            msg_type = "mention"
        
        # 插入消息
        msg_id = db.insert(
            """INSERT INTO messages (group_id, from_agent_id, to_agent_id, content, type, reply_to, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (group_id, from_agent_id, to_agent_id, content, msg_type, reply_to, datetime.now().isoformat())
        )
        
        # 为 @提及的 Agent 创建收件箱通知
        for mentioned_agent in mentions:
            MessageManager.create_inbox_notification(mentioned_agent.id, msg_id)
        
        # 如果是私信（指定了接收者），也为接收者创建通知
        if to_agent_id:
            MessageManager.create_inbox_notification(to_agent_id, msg_id)
        
        return MessageManager.get_by_id(msg_id)
    
    @staticmethod
    def detect_mentions(content: str) -> List[Agent]:
        """检测消息中的 @提及"""
        mentioned_agents = []
        matches = MessageManager.MENTION_PATTERN.findall(content)
        
        for name in matches:
            agent = AgentManager.get_by_name(name)
            if agent:
                mentioned_agents.append(agent)
        
        return mentioned_agents
    
    @staticmethod
    def create_inbox_notification(agent_id: int, message_id: int):
        """为 Agent 创建收件箱通知"""
        db.execute(
            "INSERT INTO agent_inbox (agent_id, message_id, is_read, notified_at) VALUES (?, ?, FALSE, ?)",
            (agent_id, message_id, datetime.now().isoformat())
        )
    
    @staticmethod
    def get_by_id(msg_id: int) -> Optional[Message]:
        """通过 ID 获取消息"""
        row = db.fetch_one(
            """SELECT m.*, 
                      fa.name as from_agent_name, 
                      ta.name as to_agent_name,
                      g.name as group_name
               FROM messages m
               LEFT JOIN agents fa ON m.from_agent_id = fa.id
               LEFT JOIN agents ta ON m.to_agent_id = ta.id
               LEFT JOIN groups g ON m.group_id = g.id
               WHERE m.id = ?""",
            (msg_id,)
        )
        if row:
            msg = Message(**row)
            return msg
        return None
    
    @staticmethod
    def get_group_messages(group_id: int, limit: int = 50, offset: int = 0) -> List[Message]:
        """获取群组消息历史"""
        rows = db.fetch_all(
            """SELECT m.*, 
                      fa.name as from_agent_name, 
                      ta.name as to_agent_name,
                      g.name as group_name
               FROM messages m
               LEFT JOIN agents fa ON m.from_agent_id = fa.id
               LEFT JOIN agents ta ON m.to_agent_id = ta.id
               LEFT JOIN groups g ON m.group_id = g.id
               WHERE m.group_id = ?
               ORDER BY m.created_at DESC
               LIMIT ? OFFSET ?""",
            (group_id, limit, offset)
        )
        return [MessageManager._row_to_message(row) for row in rows]
    
    @staticmethod
    def get_agent_inbox(agent_id: int, only_unread: bool = False) -> List[Dict[str, Any]]:
        """获取 Agent 的收件箱"""
        query = """SELECT ai.*, m.content, m.type, m.created_at as msg_created_at,
                          fa.name as from_agent_name, g.name as group_name
                   FROM agent_inbox ai
                   JOIN messages m ON ai.message_id = m.id
                   LEFT JOIN agents fa ON m.from_agent_id = fa.id
                   LEFT JOIN groups g ON m.group_id = g.id
                   WHERE ai.agent_id = ?"""
        
        if only_unread:
            query += " AND ai.is_read = FALSE"
        
        query += " ORDER BY m.created_at DESC"
        
        return db.fetch_all(query, (agent_id,))
    
    @staticmethod
    def mark_as_read(agent_id: int, message_id: int) -> bool:
        """标记消息为已读"""
        affected = db.execute(
            "UPDATE agent_inbox SET is_read = TRUE, read_at = ? WHERE agent_id = ? AND message_id = ?",
            (datetime.now().isoformat(), agent_id, message_id)
        )
        return affected > 0
    
    @staticmethod
    def mark_all_as_read(agent_id: int) -> int:
        """标记所有消息为已读"""
        return db.execute(
            "UPDATE agent_inbox SET is_read = TRUE, read_at = ? WHERE agent_id = ? AND is_read = FALSE",
            (datetime.now().isoformat(), agent_id)
        )
    
    @staticmethod
    def get_unread_count(agent_id: int) -> int:
        """获取未读消息数量"""
        result = db.fetch_one(
            "SELECT COUNT(*) as count FROM agent_inbox WHERE agent_id = ? AND is_read = FALSE",
            (agent_id,)
        )
        return result['count'] if result else 0
    
    @staticmethod
    def search_messages(keyword: str, group_id: Optional[int] = None,
                        from_agent_id: Optional[int] = None) -> List[Message]:
        """搜索消息"""
        query = """SELECT m.*, 
                          fa.name as from_agent_name, 
                          ta.name as to_agent_name,
                          g.name as group_name
                   FROM messages m
                   LEFT JOIN agents fa ON m.from_agent_id = fa.id
                   LEFT JOIN agents ta ON m.to_agent_id = ta.id
                   LEFT JOIN groups g ON m.group_id = g.id
                   WHERE m.content LIKE ?"""
        params = [f"%{keyword}%"]
        
        if group_id:
            query += " AND m.group_id = ?"
            params.append(group_id)
        
        if from_agent_id:
            query += " AND m.from_agent_id = ?"
            params.append(from_agent_id)
        
        query += " ORDER BY m.created_at DESC LIMIT 100"
        
        rows = db.fetch_all(query, tuple(params))
        return [MessageManager._row_to_message(row) for row in rows]
    
    @staticmethod
    def _row_to_message(row: Dict) -> Message:
        """将数据库行转换为 Message 对象"""
        msg = Message(
            msg_id=row['id'],
            group_id=row.get('group_id'),
            from_agent_id=row['from_agent_id'],
            to_agent_id=row.get('to_agent_id'),
            content=row['content'],
            msg_type=row['type'],
            reply_to=row.get('reply_to'),
            created_at=row['created_at']
        )
        msg.from_agent_name = row.get('from_agent_name')
        msg.to_agent_name = row.get('to_agent_name')
        msg.group_name = row.get('group_name')
        return msg
    
    @staticmethod
    def format_message_for_display(msg: Message) -> str:
        """格式化消息用于显示"""
        time_str = msg.created_at[11:19] if len(msg.created_at) > 19 else msg.created_at
        from_name = msg.from_agent_name or f"Agent-{msg.from_agent_id}"
        
        if msg.group_name:
            location = f"[{msg.group_name}]"
        else:
            location = "[私信]"
        
        if msg.to_agent_name:
            target = f" @{msg.to_agent_name}"
        else:
            target = ""
        
        return f"[{time_str}] {location} {from_name}{target}: {msg.content}"


class MessageFormatter:
    """消息格式化工具"""
    
    @staticmethod
    def chat(content: str) -> str:
        """普通聊天消息"""
        return content
    
    @staticmethod
    def mention(content: str, agent_names: List[str]) -> str:
        """@提及消息"""
        mentions = " ".join([f"@{name}" for name in agent_names])
        return f"{mentions} {content}"
    
    @staticmethod
    def task_assign(assignee: str, task_title: str, description: str = "", 
                    priority: str = "normal", due_date: str = "") -> str:
        """任务指派消息"""
        lines = [f"@{assignee} 新任务指派", f"标题: {task_title}"]
        if description:
            lines.append(f"描述: {description}")
        lines.append(f"优先级: {priority}")
        if due_date:
            lines.append(f"截止日期: {due_date}")
        return "\n".join(lines)
    
    @staticmethod
    def task_complete(task_id: str, result: str = "") -> str:
        """任务完成消息"""
        lines = [f"任务 {task_id} 已完成"]
        if result:
            lines.append(f"结果: {result}")
        return "\n".join(lines)
    
    @staticmethod
    def decision_proposal(title: str, description: str, options: List[str] = None) -> str:
        """决策提议消息"""
        lines = [f"【决策提议】{title}", f"描述: {description}"]
        if options:
            lines.append("选项:")
            for i, opt in enumerate(options, 1):
                lines.append(f"  {i}. {opt}")
        return "\n".join(lines)
