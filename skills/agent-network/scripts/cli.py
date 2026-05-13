#!/usr/bin/env python3
"""
Agent 群聊协作系统 - 交互式 CLI 界面
提供类似钉钉/飞书的群聊交互体验
"""

import os
import sys
import time
import readline
from typing import Optional, List
from datetime import datetime

# 添加 src 到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.database import db
from src.agent_manager import AgentManager, Agent, init_default_agents
from src.group_manager import GroupManager, Group
from src.message_manager import MessageManager, Message, MessageFormatter
from src.task_manager import TaskManager, Task
from src.decision_manager import DecisionManager, Decision


class Colors:
    """终端颜色"""
    RESET = '\033[0m'
    BOLD = '\033[1m'
    DIM = '\033[2m'
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    MAGENTA = '\033[95m'
    CYAN = '\033[96m'
    WHITE = '\033[97m'


class AgentChatCLI:
    """Agent 群聊 CLI 界面"""
    
    def __init__(self):
        self.current_agent: Optional[Agent] = None
        self.current_group: Optional[Group] = None
        self.running = True
        
    def clear_screen(self):
        """清屏"""
        os.system('clear' if os.name == 'posix' else 'cls')
    
    def print_header(self, title: str):
        """打印标题"""
        print(f"\n{Colors.CYAN}{'='*60}{Colors.RESET}")
        print(f"{Colors.BOLD}{Colors.WHITE}{title.center(60)}{Colors.RESET}")
        print(f"{Colors.CYAN}{'='*60}{Colors.RESET}\n")
    
    def print_success(self, message: str):
        """打印成功消息"""
        print(f"{Colors.GREEN}✓ {message}{Colors.RESET}")
    
    def print_error(self, message: str):
        """打印错误消息"""
        print(f"{Colors.RED}✗ {message}{Colors.RESET}")
    
    def print_info(self, message: str):
        """打印信息"""
        print(f"{Colors.BLUE}ℹ {message}{Colors.RESET}")
    
    def print_warning(self, message: str):
        """打印警告"""
        print(f"{Colors.YELLOW}⚠ {message}{Colors.RESET}")
    
    def get_input(self, prompt: str) -> str:
        """获取用户输入"""
        try:
            return input(f"{Colors.CYAN}{prompt}{Colors.RESET}").strip()
        except EOFError:
            return ""
    
    def login_menu(self):
        """登录菜单"""
        self.clear_screen()
        self.print_header("🤖 Agent Network - 群聊协作系统")
        
        print(f"{Colors.DIM}初始化默认 Agent...{Colors.RESET}")
        init_default_agents()
        
        agents = AgentManager.get_all()
        
        print(f"\n{Colors.BOLD}可用 Agent 列表:{Colors.RESET}\n")
        for i, agent in enumerate(agents, 1):
            status_color = Colors.GREEN if agent.status == 'online' else Colors.DIM
            print(f"  {Colors.YELLOW}[{i}]{Colors.RESET} {status_color}{agent.name}{Colors.RESET} - {agent.role}")
        
        print(f"\n  {Colors.YELLOW}[0]{Colors.RESET} 退出系统")
        
        choice = self.get_input("\n请选择 Agent (输入编号): ")
        
        if choice == '0':
            self.running = False
            return
        
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(agents):
                self.current_agent = agents[idx]
                AgentManager.go_online(self.current_agent.id)
                self.current_agent.status = 'online'
                self.print_success(f"欢迎, {self.current_agent.name}!")
                time.sleep(1)
            else:
                self.print_error("无效的选择")
                time.sleep(1)
        except ValueError:
            self.print_error("请输入有效的数字")
            time.sleep(1)
    
    def main_menu(self):
        """主菜单"""
        while self.running and self.current_agent:
            self.clear_screen()
            
            # 获取未读消息数
            unread_count = MessageManager.get_unread_count(self.current_agent.id)
            unread_badge = f" [{Colors.RED}{unread_count} 未读{Colors.RESET}]" if unread_count > 0 else ""
            
            group_name = f" @{self.current_group.name}" if self.current_group else ""
            self.print_header(f"🤖 {self.current_agent.name}{group_name}{unread_badge}")
            
            print(f"{Colors.BOLD}主菜单:{Colors.RESET}\n")
            print(f"  {Colors.YELLOW}[1]{Colors.RESET} 进入群组")
            print(f"  {Colors.YELLOW}[2]{Colors.RESET} 创建群组")
            print(f"  {Colors.YELLOW}[3]{Colors.RESET} 查看任务")
            print(f"  {Colors.YELLOW}[4]{Colors.RESET} 查看决策")
            print(f"  {Colors.YELLOW}[5]{Colors.RESET} 查看收件箱{unread_badge}")
            print(f"  {Colors.YELLOW}[6]{Colors.RESET} 切换 Agent")
            print(f"  {Colors.YELLOW}[0]{Colors.RESET} 退出")
            
            choice = self.get_input("\n请选择操作: ")
            
            if choice == '1':
                self.select_group()
            elif choice == '2':
                self.create_group()
            elif choice == '3':
                self.view_tasks()
            elif choice == '4':
                self.view_decisions()
            elif choice == '5':
                self.view_inbox()
            elif choice == '6':
                AgentManager.go_offline(self.current_agent.id)
                self.current_agent = None
                self.current_group = None
                return
            elif choice == '0':
                self.logout()
            else:
                self.print_error("无效的选择")
                time.sleep(1)
    
    def select_group(self):
        """选择群组"""
        groups = GroupManager.get_agent_groups(self.current_agent.id)
        
        if not groups:
            self.print_warning("你还没有加入任何群组")
            self.get_input("按回车继续...")
            return
        
        self.clear_screen()
        self.print_header("📁 选择群组")
        
        print(f"{Colors.BOLD}你的群组:{Colors.RESET}\n")
        for i, group in enumerate(groups, 1):
            member_count = len(group.members)
            online_count = len([m for m in group.members if m.status == 'online'])
            print(f"  {Colors.YELLOW}[{i}]{Colors.RESET} {group.name} ({online_count}/{member_count} 在线)")
            if group.description:
                print(f"      {Colors.DIM}{group.description}{Colors.RESET}")
        
        print(f"\n  {Colors.YELLOW}[0]{Colors.RESET} 返回")
        
        choice = self.get_input("\n请选择群组: ")
        
        if choice == '0':
            return
        
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(groups):
                self.current_group = groups[idx]
                self.enter_group_chat()
            else:
                self.print_error("无效的选择")
                time.sleep(1)
        except ValueError:
            self.print_error("请输入有效的数字")
            time.sleep(1)
    
    def enter_group_chat(self):
        """进入群组聊天"""
        if not self.current_group:
            return
        
        while self.running:
            self.clear_screen()
            
            # 获取在线成员
            online_members = GroupManager.list_online_members(self.current_group.id)
            online_names = [m.name for m in online_members]
            
            header = f"💬 {self.current_group.name} ({len(online_members)} 人在线)"
            self.print_header(header)
            
            # 显示最近消息
            messages = MessageManager.get_group_messages(self.current_group.id, limit=20)
            messages.reverse()  # 按时间正序显示
            
            if messages:
                for msg in messages:
                    self.display_message(msg)
            else:
                print(f"{Colors.DIM}暂无消息，开始聊天吧!{Colors.RESET}")
            
            print(f"\n{Colors.CYAN}{'-'*60}{Colors.RESET}")
            print(f"{Colors.DIM}在线: {', '.join(online_names) or '无'}{Colors.RESET}")
            print(f"{Colors.CYAN}{'-'*60}{Colors.RESET}")
            
            print(f"\n{Colors.BOLD}命令:{Colors.RESET} @Agent名 提及 | /task 任务 | /decision 决策 | /quit 退出")
            content = self.get_input(f"{self.current_agent.name}: ")
            
            if not content:
                continue
            
            if content == '/quit':
                # 发送离开消息
                MessageManager.send_message(
                    from_agent_id=self.current_agent.id,
                    content=f"{self.current_agent.name} 离开了群组",
                    group_id=self.current_group.id,
                    msg_type="system"
                )
                self.current_group = None
                return
            elif content == '/task':
                self.create_task_in_chat()
            elif content == '/decision':
                self.create_decision_in_chat()
            elif content.startswith('/'):
                self.handle_command(content)
            else:
                # 发送消息
                MessageManager.send_message(
                    from_agent_id=self.current_agent.id,
                    content=content,
                    group_id=self.current_group.id
                )
    
    def display_message(self, msg: Message):
        """显示消息"""
        time_str = msg.created_at[11:16] if len(msg.created_at) > 16 else msg.created_at
        from_name = msg.from_agent_name or f"Agent-{msg.from_agent_id}"
        
        # 根据消息类型使用不同颜色
        if msg.type == 'system':
            print(f"{Colors.DIM}[{time_str}] {msg.content}{Colors.RESET}")
        elif msg.type == 'task_assign':
            print(f"{Colors.YELLOW}[{time_str}] {from_name}:{Colors.RESET}")
            print(f"{Colors.YELLOW}  📝 {msg.content}{Colors.RESET}")
        elif msg.type == 'decision':
            print(f"{Colors.MAGENTA}[{time_str}] {from_name}:{Colors.RESET}")
            print(f"{Colors.MAGENTA}  📊 {msg.content}{Colors.RESET}")
        else:
            # 普通消息
            if msg.to_agent_name:
                print(f"{Colors.GREEN}[{time_str}] {from_name} -> @{msg.to_agent_name}:{Colors.RESET}")
            else:
                print(f"{Colors.GREEN}[{time_str}] {from_name}:{Colors.RESET}")
            print(f"  {msg.content}")
    
    def handle_command(self, cmd: str):
        """处理命令"""
        parts = cmd.split()
        command = parts[0].lower()
        
        if command == '/help':
            self.show_help()
        elif command == '/members':
            self.show_members()
        elif command == '/tasks':
            self.show_group_tasks()
        elif command == '/online':
            self.show_online_status()
        else:
            self.print_error(f"未知命令: {command}")
            time.sleep(1)
    
    def show_help(self):
        """显示帮助"""
        self.clear_screen()
        self.print_header("📖 命令帮助")
        
        commands = [
            ("/quit", "退出当前群组"),
            ("/task", "创建任务"),
            ("/decision", "创建决策投票"),
            ("/members", "查看群组成员"),
            ("/tasks", "查看群组任务"),
            ("/online", "查看在线状态"),
            ("/help", "显示此帮助"),
            ("@Agent名", "提及/私信某个 Agent"),
        ]
        
        for cmd, desc in commands:
            print(f"  {Colors.CYAN}{cmd.ljust(15)}{Colors.RESET} {desc}")
        
        self.get_input("\n按回车继续...")
    
    def show_members(self):
        """显示群组成员"""
        if not self.current_group:
            return
        
        members = GroupManager.get_members(self.current_group.id)
        
        self.clear_screen()
        self.print_header(f"👥 {self.current_group.name} - 成员列表")
        
        for member in members:
            status_emoji = "🟢" if member.status == 'online' else "⚪"
            print(f"  {status_emoji} {Colors.BOLD}{member.name}{Colors.RESET} - {member.role}")
            if member.description:
                print(f"      {Colors.DIM}{member.description}{Colors.RESET}")
        
        self.get_input("\n按回车继续...")
    
    def create_group(self):
        """创建群组"""
        self.clear_screen()
        self.print_header("📁 创建新群组")
        
        name = self.get_input("群组名称: ")
        if not name:
            self.print_error("群组名称不能为空")
            time.sleep(1)
            return
        
        description = self.get_input("群组描述 (可选): ")
        
        group = GroupManager.create(name, self.current_agent.id, description)
        if group:
            self.print_success(f"群组 '{name}' 创建成功!")
            
            # 发送系统消息
            MessageManager.send_message(
                from_agent_id=self.current_agent.id,
                content=f"📁 群组 '{name}' 已创建",
                group_id=group.id,
                msg_type="system"
            )
        else:
            self.print_error("创建群组失败")
        
        time.sleep(1)
    
    def create_task_in_chat(self):
        """在聊天中创建任务"""
        if not self.current_group:
            return
        
        self.clear_screen()
        self.print_header("📝 创建任务")
        
        title = self.get_input("任务标题: ")
        if not title:
            self.print_error("任务标题不能为空")
            time.sleep(1)
            return
        
        description = self.get_input("任务描述: ")
        
        # 选择指派人
        members = GroupManager.get_members(self.current_group.id)
        print(f"\n{Colors.BOLD}选择指派人:{Colors.RESET}")
        for i, member in enumerate(members, 1):
            print(f"  {Colors.YELLOW}[{i}]{Colors.RESET} {member.name}")
        
        choice = self.get_input("选择指派人 (编号): ")
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(members):
                assignee = members[idx]
                
                priority = self.get_input("优先级 (low/normal/high/urgent) [normal]: ") or "normal"
                due_date = self.get_input("截止日期 (YYYY-MM-DD, 可选): ")
                
                task = TaskManager.create(
                    title=title,
                    assigner_id=self.current_agent.id,
                    assignee_id=assignee.id,
                    description=description,
                    group_id=self.current_group.id,
                    priority=priority,
                    due_date=due_date if due_date else None
                )
                
                if task:
                    self.print_success(f"任务 '{title}' 已指派给 {assignee.name}")
                else:
                    self.print_error("创建任务失败")
            else:
                self.print_error("无效的选择")
        except ValueError:
            self.print_error("请输入有效的数字")
        
        time.sleep(1)
    
    def create_decision_in_chat(self):
        """在聊天中创建决策"""
        if not self.current_group:
            return
        
        self.clear_screen()
        self.print_header("📊 创建决策投票")
        
        title = self.get_input("决策标题: ")
        if not title:
            self.print_error("决策标题不能为空")
            time.sleep(1)
            return
        
        description = self.get_input("决策描述: ")
        
        decision = DecisionManager.create(
            title=title,
            description=description,
            proposer_id=self.current_agent.id,
            group_id=self.current_group.id
        )
        
        if decision:
            self.print_success(f"决策 '{title}' 已创建，等待投票")
        else:
            self.print_error("创建决策失败")
        
        time.sleep(1)
    
    def view_tasks(self):
        """查看任务"""
        self.clear_screen()
        self.print_header("📝 任务列表")
        
        tasks = TaskManager.get_all()
        my_tasks = TaskManager.get_agent_tasks(self.current_agent.id)
        
        if not tasks:
            print(f"{Colors.DIM}暂无任务{Colors.RESET}")
        else:
            print(f"\n{Colors.BOLD}我的任务:{Colors.RESET}\n")
            for task in my_tasks:
                print(TaskManager.format_task_for_display(task))
                print()
            
            print(f"\n{Colors.BOLD}所有任务:{Colors.RESET}\n")
            for task in tasks[:10]:  # 显示最近10个
                print(TaskManager.format_task_for_display(task))
                print()
        
        self.get_input("\n按回车继续...")
    
    def view_decisions(self):
        """查看决策"""
        self.clear_screen()
        self.print_header("📊 决策列表")
        
        decisions = DecisionManager.get_all()
        
        if not decisions:
            print(f"{Colors.DIM}暂无决策提议{Colors.RESET}")
        else:
            for decision in decisions[:10]:
                print(DecisionManager.format_decision_for_display(decision, show_votes=True))
                print()
        
        self.get_input("\n按回车继续...")
    
    def view_inbox(self):
        """查看收件箱"""
        self.clear_screen()
        self.print_header("📥 收件箱")
        
        inbox = MessageManager.get_agent_inbox(self.current_agent.id)
        
        if not inbox:
            print(f"{Colors.DIM}收件箱为空{Colors.RESET}")
        else:
            for item in inbox[:20]:
                read_status = "✓" if item['is_read'] else "●"
                status_color = Colors.DIM if item['is_read'] else Colors.GREEN
                time_str = item['msg_created_at'][11:16] if len(item['msg_created_at']) > 16 else item['msg_created_at']
                
                from_name = item['from_agent_name'] or "系统"
                group_info = f"[{item['group_name']}] " if item['group_name'] else ""
                
                content_preview = item['content'][:40] + "..." if len(item['content']) > 40 else item['content']
                
                print(f"{status_color}{read_status} [{time_str}] {group_info}{from_name}: {content_preview}{Colors.RESET}")
            
            # 标记所有为已读
            MessageManager.mark_all_as_read(self.current_agent.id)
            unread_count = MessageManager.get_unread_count(self.current_agent.id)
            if unread_count == 0:
                self.print_success("所有消息已标记为已读")
        
        self.get_input("\n按回车继续...")
    
    def show_online_status(self):
        """显示在线状态"""
        agents = AgentManager.get_all()
        
        self.clear_screen()
        self.print_header("🟢 在线状态")
        
        for agent in agents:
            status_emoji = "🟢" if agent.status == 'online' else "⚪"
            status_text = agent.status.upper()
            print(f"  {status_emoji} {Colors.BOLD}{agent.name}{Colors.RESET} - {status_text}")
        
        self.get_input("\n按回车继续...")
    
    def show_group_tasks(self):
        """显示群组任务"""
        if not self.current_group:
            return
        
        tasks = TaskManager.get_all()
        group_tasks = [t for t in tasks if t.group_id == self.current_group.id]
        
        self.clear_screen()
        self.print_header(f"📝 {self.current_group.name} - 任务列表")
        
        if not group_tasks:
            print(f"{Colors.DIM}暂无任务{Colors.RESET}")
        else:
            for task in group_tasks:
                print(TaskManager.format_task_for_display(task))
                print()
        
        self.get_input("\n按回车继续...")
    
    def logout(self):
        """退出登录"""
        if self.current_agent:
            AgentManager.go_offline(self.current_agent.id)
            self.print_info(f"再见, {self.current_agent.name}!")
        self.running = False
    
    def run(self):
        """运行 CLI"""
        while self.running:
            if not self.current_agent:
                self.login_menu()
            else:
                self.main_menu()
        
        self.clear_screen()
        self.print_header("感谢使用 Agent Network!")


def main():
    """主函数"""
    cli = AgentChatCLI()
    try:
        cli.run()
    except KeyboardInterrupt:
        print(f"\n\n{Colors.YELLOW}程序被中断{Colors.RESET}")
        if cli.current_agent:
            AgentManager.go_offline(cli.current_agent.id)


if __name__ == "__main__":
    main()
