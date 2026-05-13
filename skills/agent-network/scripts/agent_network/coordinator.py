#!/usr/bin/env python3
"""
Agent 群聊协作系统 - 中央协调器
负责系统整体协调、消息路由、Agent 调度等
"""

import os
import sys
import json
import time
import threading
from datetime import datetime
from typing import Optional, List, Dict, Any, Callable
from dataclasses import dataclass, field

# 添加父目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import Database, db
from agent_manager import AgentManager, Agent
from message_manager import MessageManager, Message, MessageFormatter
from group_manager import GroupManager, Group
from task_manager import TaskManager, TaskStatus, TaskPriority
from decision_manager import DecisionManager, DecisionStatus, VoteType


@dataclass
class AgentSession:
    """Agent 会话状态"""
    agent: Agent
    last_heartbeat: float = field(default_factory=time.time)
    is_active: bool = True
    current_group_id: Optional[int] = None
    handler: Optional[Callable] = None


class Coordinator:
    """
    Agent 群聊协作系统中央协调器
    负责：
    1. Agent 生命周期管理
    2. 消息路由和分发
    3. @提及通知处理
    4. 任务调度
    5. 决策流程管理
    """
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self._initialized = True
        self.sessions: Dict[int, AgentSession] = {}  # agent_id -> session
        self.message_handlers: Dict[int, List[Callable]] = {}  # agent_id -> handlers
        self.running = False
        self.coordinator_thread = None
        self.check_interval = 5  # 心跳检查间隔（秒）
        
        # 确保默认 Agent 存在
        self._init_default_agents()
    
    def _init_default_agents(self):
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
                print(f"[协调器] 已创建 Agent: {name} ({role})")
    
    def register_agent(self, agent_id: int, message_handler: Optional[Callable] = None) -> bool:
        """注册 Agent 到协调器"""
        agent = AgentManager.get_by_id(agent_id)
        if not agent:
            print(f"[协调器] Agent {agent_id} 不存在")
            return False
        
        # 更新状态为在线
        AgentManager.go_online(agent_id)
        
        # 创建会话
        session = AgentSession(agent=agent, handler=message_handler)
        self.sessions[agent_id] = session
        
        # 注册消息处理器
        if message_handler:
            if agent_id not in self.message_handlers:
                self.message_handlers[agent_id] = []
            self.message_handlers[agent_id].append(message_handler)
        
        print(f"[协调器] Agent '{agent.name}' 已注册并上线")
        
        # 发送系统通知
        self.broadcast_system_message(f"Agent '{agent.name}' 已上线")
        
        return True
    
    def unregister_agent(self, agent_id: int) -> bool:
        """从协调器注销 Agent"""
        if agent_id not in self.sessions:
            return False
        
        agent_name = self.sessions[agent_id].agent.name
        
        # 更新状态为离线
        AgentManager.go_offline(agent_id)
        
        # 移除会话
        del self.sessions[agent_id]
        if agent_id in self.message_handlers:
            del self.message_handlers[agent_id]
        
        print(f"[协调器] Agent '{agent_name}' 已注销")
        
        # 发送系统通知
        self.broadcast_system_message(f"Agent '{agent_name}' 已下线")
        
        return True
    
    def send_message(self, from_agent_id: int, content: str,
                     group_id: Optional[int] = None,
                     to_agent_id: Optional[int] = None,
                     msg_type: str = "chat") -> Optional[Message]:
        """发送消息"""
        # 验证发送者
        if from_agent_id not in self.sessions:
            print(f"[协调器] Agent {from_agent_id} 未注册")
            return None
        
        # 发送消息
        msg = MessageManager.send_message(
            from_agent_id=from_agent_id,
            content=content,
            group_id=group_id,
            to_agent_id=to_agent_id,
            msg_type=msg_type
        )
        
        if msg:
            # 触发消息处理
            self._route_message(msg)
        
        return msg
    
    def _route_message(self, msg: Message):
        """路由消息到相关 Agent"""
        # 获取消息中 @提及的 Agent
        mentioned_agents = MessageManager.detect_mentions(msg.content)
        
        # 通知被 @提及的 Agent
        for agent in mentioned_agents:
            if agent.id in self.sessions:
                self._notify_agent(agent.id, msg)
        
        # 如果是私信，通知接收者
        if msg.to_agent_id and msg.to_agent_id in self.sessions:
            self._notify_agent(msg.to_agent_id, msg)
        
        # 触发处理器
        handlers_to_call = []
        
        # 收集相关处理器
        for agent_id, handlers in self.message_handlers.items():
            if agent_id == msg.from_agent_id:
                continue  # 不通知发送者自己
            
            # 检查是否是目标接收者
            should_notify = False
            
            if msg.to_agent_id and msg.to_agent_id == agent_id:
                should_notify = True
            elif any(a.id == agent_id for a in mentioned_agents):
                should_notify = True
            elif msg.group_id:
                # 群组消息 - 通知所有在线的群组成员
                should_notify = True
            
            if should_notify:
                handlers_to_call.extend(handlers)
        
        # 异步调用处理器
        for handler in handlers_to_call:
            try:
                threading.Thread(target=handler, args=(msg.to_dict(),), daemon=True).start()
            except Exception as e:
                print(f"[协调器] 消息处理器错误: {e}")
    
    def _notify_agent(self, agent_id: int, msg: Message):
        """通知特定 Agent"""
        if agent_id in self.sessions:
            session = self.sessions[agent_id]
            session.last_heartbeat = time.time()
            
            # 标记消息为已读（如果 Agent 在线）
            MessageManager.mark_as_read(agent_id, msg.id)
    
    def broadcast_system_message(self, content: str, group_id: Optional[int] = None):
        """广播系统消息"""
        # 获取系统 Agent（老邢作为总管）
        system_agent = AgentManager.get_by_name("老邢")
        if not system_agent:
            return
        
        MessageManager.send_message(
            from_agent_id=system_agent.id,
            content=f"[系统] {content}",
            group_id=group_id,
            msg_type="system"
        )
    
    def create_group(self, name: str, owner_id: int, description: str = "") -> Optional[Group]:
        """创建群组"""
        return GroupManager.create(name, owner_id, description)
    
    def join_group(self, agent_id: int, group_id: int) -> bool:
        """Agent 加入群组"""
        return GroupManager.add_member(group_id, agent_id)
    
    def leave_group(self, agent_id: int, group_id: int) -> bool:
        """Agent 离开群组"""
        return GroupManager.remove_member(group_id, agent_id)
    
    def assign_task(self, title: str, description: str,
                    assigner_id: int, assignee_id: int,
                    group_id: Optional[int] = None,
                    priority: str = "normal",
                    due_date: Optional[str] = None) -> Optional[Dict]:
        """指派任务"""
        task = TaskManager.create(
            title=title,
            description=description,
            assigner_id=assigner_id,
            assignee_id=assignee_id,
            group_id=group_id,
            priority=priority,
            due_date=due_date
        )
        return task.to_dict() if task else None
    
    def complete_task(self, task_id: str, agent_id: int, result: str = "") -> bool:
        """完成任务"""
        return TaskManager.complete_task(task_id, agent_id, result)
    
    def propose_decision(self, title: str, description: str,
                         proposer_id: int,
                         group_id: Optional[int] = None) -> Optional[Dict]:
        """提出决策"""
        decision = DecisionManager.propose(title, description, proposer_id, group_id)
        return decision.to_dict() if decision else None
    
    def vote_decision(self, decision_id: str, agent_id: int,
                      vote: str, comment: str = "") -> bool:
        """投票决策"""
        return DecisionManager.vote(decision_id, agent_id, vote, comment)
    
    def finalize_decision(self, decision_id: str) -> Optional[Dict]:
        """结束决策投票"""
        decision = DecisionManager.finalize(decision_id)
        return decision.to_dict() if decision else None
    
    def get_agent_inbox(self, agent_id: int, only_unread: bool = False) -> List[Dict]:
        """获取 Agent 收件箱"""
        return MessageManager.get_agent_inbox(agent_id, only_unread)
    
    def get_unread_count(self, agent_id: int) -> int:
        """获取未读消息数"""
        return MessageManager.get_unread_count(agent_id)
    
    def get_online_agents(self) -> List[Dict]:
        """获取在线 Agent 列表"""
        agents = AgentManager.get_online_agents()
        return [a.to_dict() for a in agents]
    
    def start(self):
        """启动协调器"""
        if self.running:
            return
        
        self.running = True
        self.coordinator_thread = threading.Thread(target=self._run, daemon=True)
        self.coordinator_thread.start()
        print("[协调器] 已启动")
    
    def stop(self):
        """停止协调器"""
        self.running = False
        if self.coordinator_thread:
            self.coordinator_thread.join(timeout=5)
        print("[协调器] 已停止")
    
    def _run(self):
        """协调器主循环"""
        while self.running:
            time.sleep(self.check_interval)
            self._check_heartbeats()
    
    def _check_heartbeats(self):
        """检查 Agent 心跳"""
        current_time = time.time()
        timeout = 60  # 60秒无心跳视为离线
        
        for agent_id, session in list(self.sessions.items()):
            if current_time - session.last_heartbeat > timeout:
                print(f"[协调器] Agent '{session.agent.name}' 心跳超时，标记为离线")
                AgentManager.go_offline(agent_id)
                session.is_active = False


# 便捷函数
def get_coordinator() -> Coordinator:
    """获取协调器单例"""
    return Coordinator()


# 用于演示的示例 Agent 处理器
def demo_message_handler(agent_name: str):
    """创建示例消息处理器"""
    def handler(msg_dict: Dict):
        print(f"\n[{agent_name} 收到消息]")
        print(f"  来自: {msg_dict.get('from_agent_name', 'Unknown')}")
        print(f"  内容: {msg_dict.get('content', '')[:50]}...")
        print(f"  类型: {msg_dict.get('type', 'chat')}")
        print()
    
    return handler


if __name__ == "__main__":
    # 简单测试
    coord = get_coordinator()
    coord.start()
    
    # 获取 Agent
    lao_xing = AgentManager.get_by_name("老邢")
    xiao_xing = AgentManager.get_by_name("小邢")
    
    if lao_xing and xiao_xing:
        # 注册 Agent
        coord.register_agent(lao_xing.id, demo_message_handler("老邢"))
        coord.register_agent(xiao_xing.id, demo_message_handler("小邢"))
        
        # 发送测试消息
        coord.send_message(lao_xing.id, "@小邢 测试一下系统", msg_type="chat")
        
        # 创建任务
        task = coord.assign_task(
            title="检查服务器状态",
            description="请检查所有服务器的运行状态",
            assigner_id=lao_xing.id,
            assignee_id=xiao_xing.id,
            priority="high"
        )
        print(f"创建任务: {task}")
        
        time.sleep(2)
    
    coord.stop()
