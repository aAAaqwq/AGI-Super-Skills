#!/usr/bin/env python3
"""
飞书卡片消息构建器
"""

import json
from typing import List, Dict, Any

class CardBuilder:
    """飞书卡片消息构建器"""
    
    # 颜色模板
    COLORS = {
        "blue": "blue",
        "wathet": "wathet",  # 浅蓝
        "turquoise": "turquoise",  # 青色
        "green": "green",
        "yellow": "yellow",
        "orange": "orange",
        "red": "red",
        "carmine": "carmine",  # 深红
        "violet": "violet",
        "purple": "purple",
        "indigo": "indigo",
        "grey": "grey",
    }
    
    def __init__(self, title: str = None, color: str = "blue"):
        self.config = {"wide_screen_mode": True}
        self.header = None
        self.elements = []
        
        if title:
            self.set_header(title, color)
    
    def set_header(self, title: str, color: str = "blue") -> "CardBuilder":
        """设置标题"""
        self.header = {
            "template": self.COLORS.get(color, color),
            "title": {"content": title, "tag": "plain_text"}
        }
        return self
    
    def add_text(self, content: str, markdown: bool = True) -> "CardBuilder":
        """添加文本"""
        self.elements.append({
            "tag": "div",
            "text": {
                "content": content,
                "tag": "lark_md" if markdown else "plain_text"
            }
        })
        return self
    
    def add_divider(self) -> "CardBuilder":
        """添加分割线"""
        self.elements.append({"tag": "hr"})
        return self
    
    def add_note(self, content: str) -> "CardBuilder":
        """添加备注"""
        self.elements.append({
            "tag": "note",
            "elements": [{"tag": "plain_text", "content": content}]
        })
        return self
    
    def add_button(
        self,
        text: str,
        url: str = None,
        value: Dict = None,
        type: str = "default"
    ) -> "CardBuilder":
        """添加按钮"""
        button = {
            "tag": "button",
            "text": {"tag": "plain_text", "content": text},
            "type": type  # default, primary, danger
        }
        if url:
            button["url"] = url
        if value:
            button["value"] = value
        
        # 查找或创建 action 元素
        action_elem = None
        for elem in self.elements:
            if elem.get("tag") == "action":
                action_elem = elem
                break
        
        if action_elem:
            action_elem["actions"].append(button)
        else:
            self.elements.append({
                "tag": "action",
                "actions": [button]
            })
        return self
    
    def add_fields(self, fields: List[Dict[str, str]]) -> "CardBuilder":
        """添加字段列表"""
        field_elements = []
        for f in fields:
            field_elements.append({
                "is_short": f.get("short", True),
                "text": {
                    "tag": "lark_md",
                    "content": f"**{f['label']}**\n{f['value']}"
                }
            })
        self.elements.append({"tag": "div", "fields": field_elements})
        return self
    
    def add_image(self, image_key: str, alt: str = "") -> "CardBuilder":
        """添加图片"""
        self.elements.append({
            "tag": "img",
            "img_key": image_key,
            "alt": {"tag": "plain_text", "content": alt}
        })
        return self
    
    def build(self) -> Dict:
        """构建卡片 JSON"""
        card = {"config": self.config, "elements": self.elements}
        if self.header:
            card["header"] = self.header
        return card
    
    def to_json(self) -> str:
        """转换为 JSON 字符串"""
        return json.dumps(self.build(), ensure_ascii=False)


# ==================== 预设模板 ====================

def notification_card(title: str, content: str, color: str = "blue") -> Dict:
    """通知卡片"""
    return (CardBuilder(title, color)
            .add_text(content)
            .build())

def task_card(
    title: str,
    description: str,
    assignee: str = None,
    due_date: str = None,
    status: str = "待处理"
) -> Dict:
    """任务卡片"""
    builder = CardBuilder(f"📋 {title}", "turquoise")
    builder.add_text(description)
    
    fields = [{"label": "状态", "value": status}]
    if assignee:
        fields.append({"label": "负责人", "value": assignee})
    if due_date:
        fields.append({"label": "截止日期", "value": due_date})
    
    builder.add_fields(fields)
    return builder.build()

def alert_card(title: str, message: str, level: str = "warning") -> Dict:
    """告警卡片"""
    colors = {"info": "blue", "warning": "orange", "error": "red", "success": "green"}
    icons = {"info": "ℹ️", "warning": "⚠️", "error": "❌", "success": "✅"}
    
    return (CardBuilder(f"{icons.get(level, '📢')} {title}", colors.get(level, "blue"))
            .add_text(message)
            .build())

def progress_card(title: str, items: List[Dict]) -> Dict:
    """进度卡片"""
    builder = CardBuilder(f"📊 {title}", "green")
    
    for item in items:
        status_icon = "✅" if item.get("done") else "⏳"
        builder.add_text(f"{status_icon} {item['name']}")
    
    return builder.build()


if __name__ == "__main__":
    # 示例
    card = (CardBuilder("🎉 测试通知", "green")
            .add_text("**飞书卡片消息测试**")
            .add_text("这是一条来自小a的测试消息")
            .add_divider()
            .add_fields([
                {"label": "发送时间", "value": "2026-02-03 15:30"},
                {"label": "状态", "value": "✅ 成功"}
            ])
            .add_button("查看详情", url="https://example.com", type="primary")
            .add_note("由 OpenClaw 自动发送")
            .build())
    
    print(json.dumps(card, indent=2, ensure_ascii=False))
