# -*- coding: utf-8 -*-
"""
阶段1: 编剧智能体 - 多轮LLM交互生成结构化剧本JSON
流程: Logline → 节拍表(4幕) → 分场大纲(逐幕) → JSON结构化提取(带校验重试)
"""

import os
import re
import json
import asyncio
import logging
import string
import random
from datetime import datetime, timezone
from typing import Any, Optional, Dict

from .base_agent import AgentInterface

# 导入提示词加载器
from prompts.loader import load_prompt

logger = logging.getLogger(__name__)


# 懒加载提示词 - 优先从外部文件加载，失败则返回空
def _p(category: str, name: str, lang: str = 'zh') -> str:
    """Load prompt from external file, return empty string if not found"""
    try:
        return load_prompt(category, name, lang)
    except FileNotFoundError:
        return ""


# 从外部文件加载提示词的辅助函数
def _load_prompt(category: str, name: str, fallback: str) -> str:
    """Load prompt from external file, fallback to hardcoded string"""
    try:
        return load_prompt(category, name, 'zh')
    except FileNotFoundError:
        return fallback

# =============================================================
#  Phase 1A: Logline 生成（扩写创意 → 3 个 Logline 方案）
# =============================================================

LOGLINE_GENERATE_PROMPT_ZH = (
    "你是资深制片人。请将以下灵感扩展为 3 个不同的 Logline（故事大纲）。\n"
    "要求：\n"
    "- 明确主角（Who）、目标（Goal）、核心障碍（Conflict）和反转（Twist）\n"
    "- 确定故事的 Theme（潜在主题）\n"
    "- Logline 按照\"如果…会怎样\"的句式描述\n"
    "- 3 个 Logline 应风格各异、各有侧重\n\n"
    "输入内容：{idea}\n\n"
    "请严格按如下 JSON 数组格式输出（直接输出纯JSON，不要用```包裹，不要添加任何其他文字）：\n"
    '[{{"logline":"如果...会怎样","who":"主角描述","goal":"目标","conflict":"核心障碍","twist":"反转","theme":"潜在主题"}}]\n'
    "输出恰好 3 个元素的 JSON 数组。"
)

LOGLINE_GENERATE_PROMPT_EN = (
    "You are a senior producer. Expand the following idea into 3 different Loglines.\n"
    "Requirements:\n"
    "- Define the protagonist (Who), Goal, core Conflict, and Twist\n"
    "- Identify the story's Theme\n"
    "- Each Logline should use 'What if...' format\n"
    "- The 3 Loglines should be diverse in style and focus\n\n"
    "Input: {idea}\n\n"
    "Output ONLY a JSON array with exactly 3 elements (no code block markers, no other text):\n"
    '[{{"logline":"What if...","who":"protagonist","goal":"goal","conflict":"conflict","twist":"twist","theme":"theme"}}]'
)

# =============================================================
#  Phase 1B: Logline 检测 & 提取（未勾选扩写时）
# =============================================================

LOGLINE_CHECK_PROMPT_ZH = (
    "请判断以下文本是否包含足够的叙事要素，能够从中总结出一个完整故事的 Logline。\n"
    "（完整 Logline 需涵盖：主角、目标、核心障碍、反转和主题）\n\n"
    "文本：{idea}\n\n"
    "只回答 Yes 或 No，不要添加任何其他内容。"
)

LOGLINE_CHECK_PROMPT_EN = (
    "Determine if the following text contains enough narrative elements for a complete story Logline.\n"
    "(Needs: protagonist, goal, conflict, twist, and theme)\n\n"
    "Text: {idea}\n\n"
    "Answer only Yes or No."
)

LOGLINE_EXTRACT_PROMPT_ZH = (
    "你是资深制片人。请从以下文本中总结提取 Logline 及故事五要素。\n"
    "Logline 请使用\"如果…会怎样\"的句式。\n\n"
    "文本：{idea}\n\n"
    "请严格按如下 JSON 格式输出（直接输出纯JSON，不要用```包裹，不要添加任何其他文字）：\n"
    '{{"logline":"如果...会怎样","who":"主角描述","goal":"目标","conflict":"核心障碍","twist":"反转","theme":"潜在主题"}}'
)

LOGLINE_EXTRACT_PROMPT_EN = (
    "You are a senior producer. Extract the Logline and five story elements from the following text.\n"
    "The Logline should use 'What if...' format.\n\n"
    "Text: {idea}\n\n"
    "Output ONLY valid JSON (no code block markers, no other text):\n"
    '{{"logline":"What if...","who":"protagonist","goal":"goal","conflict":"conflict","twist":"twist","theme":"theme"}}'
)

# =============================================================
#  Phase 2A: 节拍表 (Save the Cat! Beat Sheet)
# =============================================================

BEAT_SHEET_PROMPT_ZH = (
    "你是好莱坞编剧导师。请根据以下故事线，使用 Save the Cat! 节拍表将故事拆解为四幕结构。\n\n"
    "必须包含以下四个关键节拍（起承转合）：\n"
    "第一幕 - 激励事件（Inciting Incident）：建立世界观和主角现状，发生打破平衡的事件\n"
    "第二幕 - 进入新世界（Break into Two）：主角踏上旅程，面对挑战和考验，副线展开\n"
    "第三幕 - 灵魂黑夜（Dark Night of the Soul）：主角遭受最大打击，陷入低谷\n"
    "第四幕 - 高潮决战（Finale）：主角获得顿悟，最终决战，故事收束\n\n"
    "请确保：逻辑严密、冲突逐步升级、每一幕有清晰的转折点。\n\n"
    "故事线：\n{draft}\n\n"
    "故事风格：{style}\n\n"
    "请直接输出四幕节拍表，每一幕用\"【第X幕 - 名称】\"标记开始，详细描述该幕的情节要点、角色发展和关键转折。"
)

BEAT_SHEET_PROMPT_EN = (
    "You are a Hollywood screenwriting mentor. Break down the following storyline into a 4-act structure "
    "using the Save the Cat! Beat Sheet.\n\n"
    "Must include these four key beats:\n"
    "Act 1 - Inciting Incident: Establish the world and protagonist's status quo, then a disruptive event\n"
    "Act 2 - Break into Two: Protagonist embarks on journey, faces challenges, B-story unfolds\n"
    "Act 3 - Dark Night of the Soul: Protagonist suffers the biggest blow, hits rock bottom\n"
    "Act 4 - Finale: Protagonist gains epiphany, final confrontation, story resolves\n\n"
    "Ensure: tight logic, escalating conflict, clear turning points in each act.\n\n"
    "Storyline:\n{draft}\n\n"
    "Story style: {style}\n\n"
    "Output the 4-act beat sheet directly. Start each act with '[Act X - Name]' heading. "
    "Detail the plot points, character development and key turning points for each act."
)

# =============================================================
#  Phase 2B: 分场大纲 (Step Outline, 逐幕生成)
# =============================================================

STEP_OUTLINE_PROMPT_ZH = (
    "你是分场导演。以下是完整的四幕节拍表：\n\n"
    "{beat_sheet}\n\n"
    "请将第{act_number}幕（{act_name}）转化为详细的分场大纲。\n\n"
    "格式要求（每场一段）：\n"
    "[场次编号]. [地点(室内/室外)] - [日/夜]\n"
    "[核心动作]：详细描述该场戏发生了什么，包含完整的对话、动作和表情描写。\n"
    "[情感转变]：描述主角在本场戏开始到结束的情绪变化（+/-）。\n"
    "[出场角色]：列出本场出现的所有角色。\n\n"
    "要求：\n"
    "- 每个角色都要有详细的外貌描写（发型、眼睛颜色、体型、服装颜色和款式等视觉特征）\n"
    "- **重要：外貌描写必须是静态的、贯穿全剧保持一致的特征，不要随剧情发展而变化**\n"
    "  - 例如：不要写\"他穿着破碎的衣服\"这种随情节变化的描写\n"
    "  - 应该写：\"他身穿蓝色衬衫，黑色长裤\"这种固定的服装描述\n"
    "- 每个场景都要有详细的环境、布局、色彩与氛围描写\n"
    "- 分场数量根据情节长度和节奏自行决定，确保叙事节奏合理\n"
    "- 对话用双引号标注，对话内容真实生动\n"
    "- 场次编号从 {scene_start} 开始递增\n"
    "- 故事风格：{style}\n\n"
    "请直接输出分场大纲，不要添加幕次标题或额外说明。"
)

STEP_OUTLINE_PROMPT_EN = (
    "You are a scene director. Here is the complete 4-act beat sheet:\n\n"
    "{beat_sheet}\n\n"
    "Convert Act {act_number} ({act_name}) into a detailed step outline.\n\n"
    "Format for each scene:\n"
    "[Scene number]. [Location (Indoor/Outdoor)] - [Day/Night]\n"
    "[Core Action]: Detailed description of what happens, including dialogue, actions and expressions.\n"
    "[Emotional Shift]: Describe the protagonist's emotional change from start to end (+/-).\n"
    "[Characters Present]: List all characters appearing in this scene.\n\n"
    "Requirements:\n"
    "- Each character needs detailed physical descriptions (hair, eyes, build, clothing details)\n"
    "- **IMPORTANT: Physical descriptions must be STATIC and consistent throughout the entire story - do NOT change with plot development**\n"
    "  - For example: do NOT write \"wearing torn clothes\" which changes with the plot\n"
    "  - Instead write: \"wearing a blue shirt and black pants\" which is a fixed clothing description\n"
    "- Each scene needs detailed environment, layout, color and atmosphere descriptions\n"
    "- Number of scenes based on plot length and pacing\n"
    "- Dialogue marked with double quotes, natural and vivid\n"
    "- Scene numbers start from {scene_start} and increment\n"
    "- Story style: {style}\n\n"
    "Output the step outline directly, without act headings or extra notes."
)

ACT_NAMES_ZH = {1: "激励事件", 2: "进入新世界", 3: "灵魂黑夜", 4: "高潮决战"}
ACT_NAMES_EN = {1: "Inciting Incident", 2: "Break into Two", 3: "Dark Night of the Soul", 4: "Finale"}

# =============================================================
#  Micro-film 微电影模式专用提示词
# =============================================================

MICRO_BEAT_SHEET_PROMPT_ZH = (
    "你是微电影编剧专家。请根据以下故事线，将故事压缩为一个紧凑的单幕剧情概要。\n\n"
    "要求：\n"
    "- 叙事节奏快，情节紧凑精炼，没有拖沓的铺垫\n"
    "- 全部内容在一幕内完成，不分幕\n"
    "- 保留核心冲突和情感转折，去掉多余叙事\n"
    "- 场景数量控制在 3-6 场\n"
    "- 适合 1-3 分钟的微电影\n\n"
    "故事线：\n{draft}\n\n"
    "故事风格：{style}\n\n"
    "请直接输出紧凑的剧情概要，描述场景发展、核心动作和情感转折。"
)

MICRO_BEAT_SHEET_PROMPT_EN = (
    "You are a micro-film screenwriting expert. Compress the following storyline "
    "into a compact single-act plot summary.\n\n"
    "Requirements:\n"
    "- Fast narrative pacing, concise and tight plot\n"
    "- All content in a single act, no act divisions\n"
    "- Keep core conflict and emotional turns, remove unnecessary setup\n"
    "- 3-6 scenes total\n"
    "- Suitable for a 1-3 minute short film\n\n"
    "Storyline:\n{draft}\n\n"
    "Story style: {style}\n\n"
    "Output a compact plot summary directly, describing scene progression, "
    "core actions and emotional shifts."
)

MICRO_STEP_OUTLINE_PROMPT_ZH = (
    "你是分场导演。以下是微电影剧情概要：\n\n"
    "{beat_sheet}\n\n"
    "请将其转化为详细的分场大纲。\n\n"
    "格式要求（每场一段）：\n"
    "[场次编号]. [地点(室内/室外)] - [日/夜]\n"
    "[核心动作]：详细描述该场戏发生了什么，包含完整的对话、动作和表情描写。\n"
    "[情感转变]：描述主角在本场戏开始到结束的情绪变化（+/-）。\n"
    "[出场角色]：列出本场出现的所有角色。\n\n"
    "要求：\n"
    "- 每个角色都要有详细的外貌描写（发型、眼睛颜色、体型、服装颜色和款式等视觉特征）\n"
    "- **重要：外貌描写必须是静态的、贯穿全剧保持一致的特征，不要随剧情发展而变化**\n"
    "  - 例如：不要写\"他穿着破碎的衣服\"这种随情节变化的描写\n"
    "  - 应该写：\"他身穿蓝色衬衫，黑色长裤\"这种固定的服装描述\n"
    "- 每个场景都要有详细的环境、布局、色彩与氛围描写\n"
    "- 分场数量 3-6 场，叙事紧凑快节奏\n"
    "- 对话用双引号标注，对话内容真实生动\n"
    "- 场次编号从 1 开始递增\n"
    "- 故事风格：{style}\n\n"
    "请直接输出分场大纲，不要添加额外说明。"
)

MICRO_STEP_OUTLINE_PROMPT_EN = (
    "You are a scene director. Here is the micro-film plot summary:\n\n"
    "{beat_sheet}\n\n"
    "Convert it into a detailed step outline.\n\n"
    "Format for each scene:\n"
    "[Scene number]. [Location (Indoor/Outdoor)] - [Day/Night]\n"
    "[Core Action]: Detailed description including dialogue, actions and expressions.\n"
    "[Emotional Shift]: Protagonist's emotional change from start to end (+/-).\n"
    "[Characters Present]: All characters appearing in this scene.\n\n"
    "Requirements:\n"
    "- Each character needs detailed physical descriptions (hair, eyes, build, clothing)\n"
    "- **IMPORTANT: Physical descriptions must be STATIC and consistent throughout the entire story - do NOT change with plot development**\n"
    "  - For example: do NOT write \"wearing torn clothes\" which changes with the plot\n"
    "  - Instead write: \"wearing a blue shirt and black pants\" which is a fixed clothing description\n"
    "- Each scene needs detailed environment, layout, color and atmosphere descriptions\n"
    "- 3-6 scenes total, compact and fast-paced\n"
    "- Dialogue marked with double quotes, natural and vivid\n"
    "- Scene numbers start from 1 and increment\n"
    "- Story style: {style}\n\n"
    "Output the step outline directly, without extra notes."
)

MICRO_META_EXTRACT_PROMPT_ZH = (
    "你是专业的剧本分析师。以下是微电影剧情概要：\n\n"
    "{beat_sheet}\n\n"
    "请从中提取以下信息，以纯JSON格式输出（不要用```包裹）：\n"
    '{{"title":"故事标题(2-8字)","logline":"一句话概括故事(30字以内)",'
    '"genre":["类型1","类型2"],"synopsis":"完整故事梗概(50-100字)",'
    '"mood":"影片情绪基调"}}'
)

MICRO_META_EXTRACT_PROMPT_EN = (
    "You are a professional script analyst. Here is the micro-film plot summary:\n\n"
    "{beat_sheet}\n\n"
    "Extract the following information as pure JSON (no code blocks):\n"
    '{{"title":"Story title (short)","logline":"One sentence summary",'
    '"genre":["genre1","genre2"],"synopsis":"Complete synopsis (50-100 words)",'
    '"mood":"Overall mood"}}'
)

# =============================================================
#  Phase 3A: 单幕结构化 JSON 提取
# =============================================================

ACT_EXTRACT_INTRO_ZH = (
    "你是一个专业的剧本分析师。请仔细阅读以下第{act_number}幕的分场大纲，从中提取并整理为标准JSON格式。\n\n"
    "分场大纲：\n{outline}\n\n"
    "请严格按照以下JSON结构输出（直接输出纯JSON，不要用```包裹，不要添加注释或任何其他文字）：\n\n"
)

ACT_EXTRACT_INTRO_EN = (
    "You are a professional script analyst. Read the following Act {act_number} step outline carefully "
    "and extract it into a structured JSON format.\n\n"
    "Step outline:\n{outline}\n\n"
    "Output ONLY valid JSON in the following structure (no code block markers, no comments, no other text):\n\n"
)

ACT_EXTRACT_SCHEMA_ZH = """{{
  "characters": [
    {{
      "name": "角色全名",
      "character_id": "char_加8位随机字母数字",
      "description": "外貌描写: 含发型、体型、服装颜色和款式等视觉特征, 不要描述眼睛颜色, 面部不要有文字等特殊符号, 形象要正常(可以前卫时髦但不能恐怖灵异), 50-80字, 不要用比喻",
      "personality": ["性格特征1", "性格特征2", "性格特征3"],
      "motivation": "角色核心动机",
      "arc_description": "角色成长弧线",
      "role": "主角 或 配角 或 背景",
      "age": "年龄",
      "species": "人类 或 具体动物种类"
    }}
  ],
  "settings": [
    {{
      "name": "场景名称(室内) 或 场景名称(室外)",
      "setting_id": "set_加8位随机字母数字",
      "description": "环境布局、色彩、光线、氛围等视觉细节, 80-120字, 不要包含人物或动物"
    }}
  ],
  "scenes": [
    {{
      "scene_number": {scene_start},
      "act": {act_number},
      "location": "必须是settings中已定义的场景名称",
      "characters": ["出场角色名(必须与characters中的name一致)"],
      "plot": "该场景完整详细的剧情, 含对话、动作和表情描写, 必须完整表达分场内容, 无字数限制"
    }}
  ]
}}"""

ACT_EXTRACT_SCHEMA_EN = """{{
  "characters": [
    {{
      "name": "Full name",
      "character_id": "char_ plus 8 random alphanumeric",
      "description": "Visual description: hair, eyes, build, clothing details, 50-80 words",
      "personality": ["trait1", "trait2", "trait3"],
      "motivation": "Core motivation",
      "arc_description": "Character growth arc",
      "role": "protagonist or supporting or background",
      "age": "age",
      "species": "human or specific animal"
    }}
  ],
  "settings": [
    {{
      "name": "Location name (Indoor) or Location name (Outdoor)",
      "setting_id": "set_ plus 8 random alphanumeric",
      "description": "Layout, colors, lighting, atmosphere details, 80-120 words, no people or animals"
    }}
  ],
  "scenes": [
    {{
      "scene_number": {scene_start},
      "act": {act_number},
      "location": "Must be a name defined in settings",
      "characters": ["character names matching characters array"],
      "plot": "Complete detailed scene plot with dialogue, actions and expressions, no word limit"
    }}
  ]
}}"""

ACT_EXTRACT_RULES_ZH = (
    "\n\n重要规则：\n"
    "1. characters中的name必须与scenes中的角色名完全一致\n"
    "2. scenes中的location必须是settings中已定义的场景名称之一\n"
    "3. settings的name需标注(室内)或(室外)\n"
    "4. 所有scene的act字段必须为{act_number}\n"
    "5. scene_number从{scene_start}开始递增\n"
    "6. 角色的description要有足够视觉细节用于AI图像生成\n"
    "7. setting的description要有足够视觉细节用于AI背景图生成\n"
    "8. 不要生成群体角色(如\"邻居们\")，每个角色都是独立个体\n"
    "9. scene的plot字段必须完整表达该分场的全部内容\n"
    "10. 只输出纯JSON\n"
)

ACT_EXTRACT_RULES_EN = (
    "\n\nImportant rules:\n"
    "1. Character names in scenes must exactly match names in characters array\n"
    "2. Scene locations must be names defined in settings array\n"
    "3. Setting names must include (Indoor) or (Outdoor)\n"
    "4. All scenes' act field must be {act_number}\n"
    "5. scene_number starts from {scene_start} and increments\n"
    "6. Character descriptions need enough visual detail for AI image generation\n"
    "7. Setting descriptions need enough visual detail for AI background generation\n"
    "8. No group characters, every character is an individual\n"
    "9. Scene 'plot' field must fully express all content, do not truncate\n"
    "10. Output ONLY the JSON\n"
)

# =============================================================
#  Phase 3B: 最终合并补充提示词（生成 title / logline / synopsis 等顶层字段）
# =============================================================

META_EXTRACT_PROMPT_ZH = (
    "你是专业的剧本分析师。以下是完整的四幕节拍表：\n\n"
    "{beat_sheet}\n\n"
    "请从中提取以下信息，以纯JSON格式输出（不要用```包裹）：\n"
    '{{"title":"故事标题(2-8字)","logline":"一句话概括故事(30字以内)",'
    '"genre":["类型1","类型2"],"synopsis":"完整故事梗概(100-200字)",'
    '"mood":"影片情绪基调"}}'
)

META_EXTRACT_PROMPT_EN = (
    "You are a professional script analyst. Here is the complete 4-act beat sheet:\n\n"
    "{beat_sheet}\n\n"
    "Extract the following information as pure JSON (no code blocks):\n"
    '{{"title":"Story title (short)","logline":"One sentence summary",'
    '"genre":["genre1","genre2"],"synopsis":"Complete synopsis (100-200 words)",'
    '"mood":"Overall mood"}}'
)

# =============================================================
#  Phase 4: 场景 & 角色合并（去重相似条目）
# =============================================================

CONSOLIDATE_PROMPT_ZH = (
    "你是剧本审校专家。请审查以下剧本中的场景列表和角色列表，找出可以合并的条目。\n\n"
    "合并规则：\n"
    "- 场景合并：如果两个场景在物理空间上是同一个地点（只是拍摄角度、景别不同），应合并为一个\n"
    "  例如：「车厢内」「车厢过道」「车厢全景」都是同一节车厢 → 合并为「车厢内」\n"
    "  例如：「咖啡馆吧台」「咖啡馆角落」→ 合并为「咖啡馆」\n"
    "  注意：不同物理空间不能合并（如「车厢内」和「车厢连接处」是不同空间）\n"
    "- 角色合并：如果同名角色出现多次（可能描述略有不同），合并为一个\n"
    "- 合并后保留最详细的描述\n\n"
    "当前场景列表：\n{settings_json}\n\n"
    "当前角色列表：\n{characters_json}\n\n"
    "请输出纯JSON（不要用```包裹），格式如下：\n"
    '{{\n'
    '  "setting_merges": {{"被合并的场景名": "合并到的目标场景名", ...}},\n'
    '  "character_merges": {{"被合并的角色名": "合并到的目标角色名", ...}}\n'
    '}}\n\n'
    "如果没有需要合并的条目，对应字段返回空对象 {{}}。\n"
    "只输出纯JSON，不要添加任何其他文字。"
)

CONSOLIDATE_PROMPT_EN = (
    "You are a script review expert. Review the following settings and characters lists "
    "and identify entries that should be merged.\n\n"
    "Merge rules:\n"
    "- Settings merge: If two settings are the same physical location (just different camera angles), "
    "merge them into one. E.g., 'Train interior', 'Train aisle', 'Train panorama' are all the same car.\n"
    "  Different physical spaces should NOT be merged.\n"
    "- Character merge: If the same character appears with slightly different descriptions, merge them.\n"
    "- Keep the most detailed description after merging.\n\n"
    "Current settings:\n{settings_json}\n\n"
    "Current characters:\n{characters_json}\n\n"
    "Output ONLY valid JSON (no code blocks):\n"
    '{{\n'
    '  "setting_merges": {{"merged_setting_name": "target_setting_name", ...}},\n'
    '  "character_merges": {{"merged_char_name": "target_char_name", ...}}\n'
    '}}\n\n'
    "If nothing to merge, return empty objects {{}}. Output ONLY the JSON."
)

class ScriptWriterAgent(AgentInterface):
    """编剧智能体：多轮LLM交互 → 结构化剧本JSON"""

    def __init__(self):
        super().__init__(name="ScriptWriter")

    # ─── JSON 提取 ───

    @staticmethod
    def _extract_json_from_text(text: str) -> Optional[dict]:
        """从LLM输出中提取JSON对象"""
        text = text.strip()
        text = re.sub(r'^```(?:json)?\s*', '', text)
        text = re.sub(r'\s*```$', '', text)
        text = text.strip()

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        start = text.find('{')
        end = text.rfind('}')
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(text[start:end + 1])
            except json.JSONDecodeError:
                pass
        return None

    @staticmethod
    def _extract_json_array_from_text(text: str) -> Optional[list]:
        """从LLM输出中提取JSON数组"""
        text = text.strip()
        # 去除 markdown 代码块标记（支持多行）
        text = re.sub(r'```(?:json)?\s*\n?', '', text)
        text = text.strip()

        try:
            result = json.loads(text)
            if isinstance(result, list):
                return result
            # LLM 有时返回对象而非数组，尝试包装
            if isinstance(result, dict):
                return [result]
        except json.JSONDecodeError:
            pass

        start = text.find('[')
        end = text.rfind(']')
        if start != -1 and end != -1 and end > start:
            try:
                result = json.loads(text[start:end + 1])
                if isinstance(result, list):
                    return result
            except json.JSONDecodeError:
                pass

        # 尝试匹配多个独立 JSON 对象
        objects = []
        for m in re.finditer(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', text):
            try:
                obj = json.loads(m.group())
                if isinstance(obj, dict) and 'logline' in obj:
                    objects.append(obj)
            except json.JSONDecodeError:
                continue
        if objects:
            return objects

        return None

    @staticmethod
    def _gen_id(prefix: str = "char") -> str:
        return f"{prefix}_{''.join(random.choices(string.ascii_lowercase + string.digits, k=8))}"

    # ─── 保存结果 ───

    def _save_result(self, json_data: dict, sid: str, is_zh: bool):
        """保存结构化剧本JSON到结果文件"""
        from config import settings
        script_dir = os.path.join(settings.RESULT_DIR, 'script')
        os.makedirs(script_dir, exist_ok=True)

        result_file = os.path.join(script_dir, f'script_{sid}.json')
        results = {}
        if os.path.exists(result_file) and os.path.getsize(result_file) > 0:
            with open(result_file, 'r', encoding='utf-8') as f:
                results = json.load(f)

        results.setdefault(str(sid), {})['script_json'] = json_data
        with open(result_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=4, ensure_ascii=False)

    def _save_progress(self, sid: str, phase: str, data: dict):
        """保存剧本生成的中间进度状态到结果文件"""
        from config import settings
        script_dir = os.path.join(settings.RESULT_DIR, 'script')
        os.makedirs(script_dir, exist_ok=True)

        result_file = os.path.join(script_dir, f'script_{sid}.json')
        results = {}
        if os.path.exists(result_file) and os.path.getsize(result_file) > 0:
            with open(result_file, 'r', encoding='utf-8') as f:
                results = json.load(f)

        # 初始化 progress 字段
        results.setdefault(str(sid), {}).setdefault('progress', {})

        # 保存当前阶段信息
        results[str(sid)]['progress']['current_phase'] = phase
        results[str(sid)]['progress']['updated_at'] = datetime.now(timezone.utc).isoformat()

        # 根据阶段保存对应的数据
        if phase == 'logline_check':
            # 创意检查结果
            results[str(sid)]['progress']['idea_analyzed'] = data.get('idea_analyzed', False)
            results[str(sid)]['progress']['logline_extracted'] = data.get('logline_summary')
        elif phase == 'logline_generation':
            # 生成的候选 logline
            results[str(sid)]['progress']['logline_options'] = data.get('logline_options', [])
        elif phase == 'logline_confirmed':
            # 用户选择的 logline
            results[str(sid)]['progress']['selected_logline'] = data.get('selected_logline')
        elif phase == 'mode_selection':
            # 用户选择的模式
            results[str(sid)]['progress']['selected_mode'] = data.get('selected_mode')
        elif phase == 'script_generation':
            # 完整剧本已生成
            results[str(sid)]['progress']['script_generated'] = True
            results[str(sid)]['progress']['title'] = data.get('title')

        with open(result_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=4, ensure_ascii=False)

    # ─── 核心流程 ───

    async def process(self, input_data: Any, intervention: Optional[Dict] = None) -> Dict:

        # 检查当前阶段，避免重复生成 logline
        current_phase = input_data.get("phase", "")
        selected_logline = input_data.get("selected_logline")
        selected_mode = input_data.get("selected_mode")

        # 如果已选择模式，直接生成剧本
        if selected_mode:
            # 如果 selected_logline 是索引（数字），需要转换为 logline 对象
            if isinstance(selected_logline, int):
                logline_options = input_data.get("logline_options", [])
                if 0 <= selected_logline < len(logline_options):
                    logline_data = logline_options[selected_logline]
                else:
                    logline_data = {}
            else:
                logline_data = selected_logline if isinstance(selected_logline, dict) else {}

            if selected_mode == "micro":
                return await self._phase_micro_script_gen(input_data, logline_data)
            else:
                return await self._phase_script_gen(input_data, logline_data)

        # 如果已选择 logline 但未选择模式，返回模式选择
        if selected_logline and current_phase == "mode_selection":
            return {
                "payload": {
                    "phase": "mode_selection",
                    "selected_logline": selected_logline,
                    "session_id": input_data.get("session_id", ""),
                },
                "requires_intervention": True,
                "openclaw_hint": "用户已选择情节，需要选择拍摄模式(电影模式4幕/微电影模式1幕)。请展示给用户并等待用户选择。",
            }

        # (A) 用户介入修改最终剧本
        if intervention and "modified_script" in intervention:
            modified = intervention["modified_script"]
            sid = input_data.get("session_id", "")
            if isinstance(modified, str):
                modified = self._extract_json_from_text(modified) or {}
            is_zh = any('\u4e00' <= c <= '\u9fff' for c in modified.get("title", ""))
            modified["session_id"] = sid
            self._save_result(modified, sid, is_zh)
            return {"payload": modified, "requires_intervention": False, "stage_completed": True}

        # (B1) 用户选择了创作模式 → 根据模式生成剧本
        if intervention and "selected_mode" in intervention:
            selected = input_data.get("selected_logline", {})
            mode = intervention["selected_mode"]
            sid = input_data.get("session_id", "")

            # 如果 selected_logline 是索引（数字），转换为对应的 logline 对象
            if isinstance(selected, int):
                logline_options = input_data.get("logline_options", [])
                if 0 <= selected < len(logline_options):
                    logline_data = logline_options[selected]
                else:
                    logline_data = {}
            else:
                logline_data = selected if isinstance(selected, dict) else {}

            # 保存进度状态
            self._save_progress(sid, "mode_selection", {
                "selected_mode": mode
            })

            if mode == "micro":
                return await self._phase_micro_script_gen(input_data, logline_data)
            else:
                return await self._phase_script_gen(input_data, logline_data)

        # (B2) 用户选择了一个 Logline → 显示模式选择
        if intervention and "selected_logline" in intervention:
            selected = intervention["selected_logline"]
            sid = input_data.get("session_id", "")

            # 如果 selected_logline 是索引（数字），转换为对应的 logline 对象
            if isinstance(selected, int):
                logline_options = input_data.get("logline_options", [])
                if 0 <= selected < len(logline_options):
                    logline_data = logline_options[selected]
                else:
                    logline_data = {}
            else:
                logline_data = selected if isinstance(selected, dict) else {}

            # 保存进度状态
            self._save_progress(sid, "logline_confirmed", {
                "selected_logline": logline_data
            })

            return {
                "payload": {
                    "phase": "mode_selection",
                    "selected_logline": logline_data,
                    "session_id": sid,
                },
                "requires_intervention": True,
                "openclaw_hint": "用户已选择情节，需要选择拍摄模式(电影模式4幕/微电影模式1幕)。请展示给用户并等待用户选择。",
            }

        # 首次运行：自动判断是直接提取 logline 还是进入扩写
        auto_mode = input_data.get("auto_mode", False)

        # 代理（自动）模式：跳过 Logline 选择，直接生成剧本
        if auto_mode:
            return await self._phase_direct(input_data)

        # 自动判断：创意足够则提取 logline，否则自动扩写生成 3 个选项
        return await self._phase_logline_check(input_data)

    # ─── Phase 1A: 生成 3 个 Logline 方案 ───

    async def _phase_logline_gen(self, input_data: Dict) -> Dict:
        idea = input_data.get("idea", "")
        sid = input_data.get("session_id", "")
        llm_model = input_data.get("llm_model", "qwen3.5-plus")
        web_search = input_data.get("web_search", False)
        is_zh = any('\u4e00' <= c <= '\u9fff' for c in idea)

        def run():
            from tool.llm_client import LLM
            llm = LLM()
            self._report_progress("剧本生成", "正在生成 Logline 方案...", 5)
            prompt = (LOGLINE_GENERATE_PROMPT_ZH if is_zh else LOGLINE_GENERATE_PROMPT_EN).format(idea=idea)

            for attempt in range(3):
                self._check_cancel()
                raw = self._cancellable_query(llm, prompt, model=llm_model, task_id=sid, web_search=web_search)
                logger.info(f"[ScriptWriter] Logline gen attempt {attempt + 1}, raw output ({len(raw)} chars): {raw[:500]}")
                options = self._extract_json_array_from_text(raw)
                if options and len(options) > 0:
                    # 确保每个选项包含必要字段
                    required = {"logline", "who", "goal", "conflict", "twist", "theme"}
                    valid = [o for o in options if isinstance(o, dict) and required.issubset(o.keys())]
                    if valid:
                        self._report_progress("剧本生成", "Logline 方案已生成", 20)
                        return valid[:3]

                logger.warning(f"[ScriptWriter] Logline gen attempt {attempt + 1}: parse failed")
                if is_zh:
                    prompt = (
                        "上次输出格式不正确，请严格按要求重新输出。"
                        "必须输出纯JSON数组，不要用```包裹，不要有任何多余文字。\n\n"
                        + (LOGLINE_GENERATE_PROMPT_ZH).format(idea=idea)
                    )
                else:
                    prompt = (
                        "Previous output format was incorrect. Please try again. "
                        "Output ONLY a raw JSON array, no code blocks, no extra text.\n\n"
                        + (LOGLINE_GENERATE_PROMPT_EN).format(idea=idea)
                    )

            raise Exception("Logline 生成失败：多次尝试均无法解析输出")

        loop = asyncio.get_running_loop()
        options = await loop.run_in_executor(None, run)

        # 保存进度状态
        self._save_progress(sid, "logline_generation", {
            "logline_options": options
        })

        return {
            "payload": {
                "phase": "logline_selection",
                "logline_options": options,
                "session_id": sid,
            },
            "requires_intervention": True,
            "openclaw_hint": "生成了多个情节候选(logline)，需要用户选择。请展示给用户并等待用户选择。",
        }

    # ─── Phase 1B: 检测输入是否可提取 Logline ───

    async def _phase_logline_check(self, input_data: Dict) -> Dict:
        idea = input_data.get("idea", "")
        sid = input_data.get("session_id", "")
        llm_model = input_data.get("llm_model", "qwen3.5-plus")
        web_search = input_data.get("web_search", False)
        is_zh = any('\u4e00' <= c <= '\u9fff' for c in idea)

        def run():
            from tool.llm_client import LLM
            llm = LLM()
            self._report_progress("剧本生成", "分析创意文本...", 5)
            check_prompt = (LOGLINE_CHECK_PROMPT_ZH if is_zh else LOGLINE_CHECK_PROMPT_EN).format(idea=idea)
            answer = self._cancellable_query(llm, check_prompt, model=llm_model, task_id=sid, web_search=web_search).strip()

            if answer.lower().startswith("yes"):
                self._report_progress("剧本生成", "提取 Logline...", 10)
                extract_prompt = (LOGLINE_EXTRACT_PROMPT_ZH if is_zh else LOGLINE_EXTRACT_PROMPT_EN).format(idea=idea)
                raw = self._cancellable_query(llm, extract_prompt, model=llm_model, task_id=sid, web_search=web_search)
                logger.info(f"[ScriptWriter] Logline extract raw ({len(raw)} chars): {raw[:500]}")
                logline_data = self._extract_json_from_text(raw)
                if logline_data and isinstance(logline_data, dict) and 'logline' in logline_data:
                    self._report_progress("剧本生成", "Logline 提取完成", 20)
                    return {"phase": "logline_confirm", "logline_summary": logline_data}

            return {"phase": "suggest_expand"}

        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(None, run)
        result["session_id"] = sid

        # 如果创意不够，自动进入扩写阶段，生成 3 个 logline 供选择
        if result.get("phase") == "suggest_expand":
            return await self._phase_logline_gen(input_data)

        # 保存进度状态
        phase = result.get("phase", "logline_check")
        self._save_progress(sid, "logline_check", {
            "idea_analyzed": phase == "logline_confirm",
            "logline_summary": result.get("logline_summary")
        })

        return {
            "payload": result,
            "requires_intervention": True,
            "openclaw_hint": "已提取情节概要，需要用户确认。请展示给用户并等待用户确认。",
        }

    # ─── Phase 2: 根据选定 Logline 生成完整剧本 ───

    async def _phase_script_gen(self, input_data: Dict, logline_data: Dict) -> Dict:
        idea = input_data.get("idea", "")
        sid = input_data.get("session_id", "")
        style = input_data.get("style", "anime")
        llm_model = input_data.get("llm_model", "qwen3.5-plus")
        web_search = input_data.get("web_search", False)
        is_zh = any('\u4e00' <= c <= '\u9fff' for c in idea)

        # 用 Logline 六要素构建丰富的故事概要
        if is_zh:
            draft = (
                f"故事核心 Logline：{logline_data.get('logline', '')}\n"
                f"主角：{logline_data.get('who', '')}\n"
                f"目标：{logline_data.get('goal', '')}\n"
                f"核心障碍：{logline_data.get('conflict', '')}\n"
                f"反转：{logline_data.get('twist', '')}\n"
                f"主题：{logline_data.get('theme', '')}\n\n"
                f"原始灵感：{idea}"
            )
        else:
            draft = (
                f"Story Logline: {logline_data.get('logline', '')}\n"
                f"Protagonist: {logline_data.get('who', '')}\n"
                f"Goal: {logline_data.get('goal', '')}\n"
                f"Core Conflict: {logline_data.get('conflict', '')}\n"
                f"Twist: {logline_data.get('twist', '')}\n"
                f"Theme: {logline_data.get('theme', '')}\n\n"
                f"Original idea: {idea}"
            )

        def run():
            from config import settings as app_settings
            from tool.llm_client import LLM

            os.makedirs(app_settings.TEMP_DIR, exist_ok=True)
            os.makedirs(os.path.join(app_settings.RESULT_DIR, 'script'), exist_ok=True)

            llm = LLM()

            # 逐幕生成节拍表 + 分场大纲 + 结构化提取
            json_data = self._generate_script_incremental(
                llm, draft, style, llm_model, sid, is_zh, web_search=web_search, pct_start=20
            )

            # 补充元数据
            json_data.setdefault("project_id", f"proj_{sid}")
            json_data.setdefault("version", 1)
            json_data["created_at"] = datetime.now(timezone.utc).isoformat()
            json_data["metadata"] = {
                "generation_model": llm_model,
                "generation_prompt": idea,
            }
            json_data["session_id"] = sid
            json_data["logline_data"] = logline_data

            self._save_result(json_data, sid, is_zh)
            # 保存进度状态
            self._save_progress(sid, "script_generation", {
                "title": json_data.get("title")
            })
            self._report_progress("剧本生成", "完成", 100)
            return json_data

        loop = asyncio.get_running_loop()
        script_json = await loop.run_in_executor(None, run)

        # 保存进度状态
        self._save_progress(sid, "script_generation", {
            "title": script_json.get("title")
        })

        return {
            "payload": script_json,
            "requires_intervention": False,
            "stage_completed": True,  # 明确标记阶段完成
            "openclaw_hint": "剧本生成完成。",
        }

    # ─── Phase 2-Micro: 微电影模式 - 根据选定 Logline 生成紧凑单幕剧本 ───

    async def _phase_micro_script_gen(self, input_data: Dict, logline_data: Dict) -> Dict:
        idea = input_data.get("idea", "")
        sid = input_data.get("session_id", "")
        style = input_data.get("style", "anime")
        llm_model = input_data.get("llm_model", "qwen3.5-plus")
        web_search = input_data.get("web_search", False)
        is_zh = any('\u4e00' <= c <= '\u9fff' for c in idea)

        # 用 Logline 六要素构建故事概要
        if is_zh:
            draft = (
                f"故事核心 Logline：{logline_data.get('logline', '')}\n"
                f"主角：{logline_data.get('who', '')}\n"
                f"目标：{logline_data.get('goal', '')}\n"
                f"核心障碍：{logline_data.get('conflict', '')}\n"
                f"反转：{logline_data.get('twist', '')}\n"
                f"主题：{logline_data.get('theme', '')}\n\n"
                f"原始灵感：{idea}"
            )
        else:
            draft = (
                f"Story Logline: {logline_data.get('logline', '')}\n"
                f"Protagonist: {logline_data.get('who', '')}\n"
                f"Goal: {logline_data.get('goal', '')}\n"
                f"Core Conflict: {logline_data.get('conflict', '')}\n"
                f"Twist: {logline_data.get('twist', '')}\n"
                f"Theme: {logline_data.get('theme', '')}\n\n"
                f"Original idea: {idea}"
            )

        def run():
            from config import settings as app_settings
            from tool.llm_client import LLM

            os.makedirs(app_settings.TEMP_DIR, exist_ok=True)
            os.makedirs(os.path.join(app_settings.RESULT_DIR, 'script'), exist_ok=True)

            llm = LLM()

            # 微电影模式: 单幕生成
            json_data = self._generate_micro_script_incremental(
                llm, draft, style, llm_model, sid, is_zh, web_search=web_search, pct_start=20
            )

            # 补充元数据
            json_data.setdefault("project_id", f"proj_{sid}")
            json_data.setdefault("version", 1)
            json_data["created_at"] = datetime.now(timezone.utc).isoformat()
            json_data["metadata"] = {
                "generation_model": llm_model,
                "generation_prompt": idea,
                "mode": "micro",
            }
            json_data["session_id"] = sid
            json_data["logline_data"] = logline_data

            self._save_result(json_data, sid, is_zh)
            # 保存进度状态
            self._save_progress(sid, "script_generation", {
                "title": json_data.get("title")
            })
            self._report_progress("剧本生成", "完成", 100)
            return json_data

        loop = asyncio.get_running_loop()
        script_json = await loop.run_in_executor(None, run)

        # 保存进度状态
        self._save_progress(sid, "script_generation", {
            "title": script_json.get("title")
        })

        return {
            "payload": script_json,
            "requires_intervention": False,
            "stage_completed": True,  # 明确标记阶段完成
            "openclaw_hint": "剧本生成完成。",
        }

    # ─── 代理模式（自动生成 Logline 并选择第一个） ───

    async def _phase_direct(self, input_data: Dict) -> Dict:
        """代理模式：生成 3 个 Logline → 自动选择第一个 → 生成完整剧本"""
        idea = input_data.get("idea", "")
        sid = input_data.get("session_id", "")
        style = input_data.get("style", "anime")
        llm_model = input_data.get("llm_model", "qwen3.5-plus")
        web_search = input_data.get("web_search", False)
        is_zh = any('\u4e00' <= c <= '\u9fff' for c in idea)

        def run():
            from config import settings as app_settings
            from tool.llm_client import LLM

            os.makedirs(app_settings.TEMP_DIR, exist_ok=True)
            os.makedirs(os.path.join(app_settings.RESULT_DIR, 'script'), exist_ok=True)

            llm = LLM()

            # Step 1: 生成 Logline 方案
            self._report_progress("剧本生成", "正在生成 Logline 方案...", 5)
            prompt = (LOGLINE_GENERATE_PROMPT_ZH if is_zh else LOGLINE_GENERATE_PROMPT_EN).format(idea=idea)

            logline_data = None
            for attempt in range(3):
                self._check_cancel()
                raw = self._cancellable_query(llm, prompt, model=llm_model, task_id=sid, web_search=web_search)
                logger.info(f"[ScriptWriter][auto] Logline gen attempt {attempt + 1}, raw ({len(raw)} chars): {raw[:500]}")
                options = self._extract_json_array_from_text(raw)
                if options and len(options) > 0:
                    required = {"logline", "who", "goal", "conflict", "twist", "theme"}
                    valid = [o for o in options if isinstance(o, dict) and required.issubset(o.keys())]
                    if valid:
                        logline_data = valid[0]  # 自动选择第一个
                        logger.info(f"[ScriptWriter][auto] Auto-selected logline: {logline_data.get('logline', '')[:80]}")
                        break

                logger.warning(f"[ScriptWriter][auto] Logline gen attempt {attempt + 1}: parse failed")
                if is_zh:
                    prompt = (
                        "上次输出格式不正确，请严格按要求重新输出。"
                        "必须输出纯JSON数组，不要用```包裹，不要有任何多余文字。\n\n"
                        + LOGLINE_GENERATE_PROMPT_ZH.format(idea=idea)
                    )
                else:
                    prompt = (
                        "Previous output format was incorrect. Please try again. "
                        "Output ONLY a raw JSON array, no code blocks, no extra text.\n\n"
                        + LOGLINE_GENERATE_PROMPT_EN.format(idea=idea)
                    )

            if logline_data is None:
                raise Exception("Logline 生成失败：多次尝试均无法解析输出")

            self._report_progress("剧本生成", "已自动选择 Logline，开始创作情节...", 15)

            # Step 2: 用 Logline 六要素构建故事概要
            if is_zh:
                draft = (
                    f"故事核心 Logline：{logline_data.get('logline', '')}\n"
                    f"主角：{logline_data.get('who', '')}\n"
                    f"目标：{logline_data.get('goal', '')}\n"
                    f"核心障碍：{logline_data.get('conflict', '')}\n"
                    f"反转：{logline_data.get('twist', '')}\n"
                    f"主题：{logline_data.get('theme', '')}\n\n"
                    f"原始灵感：{idea}"
                )
            else:
                draft = (
                    f"Story Logline: {logline_data.get('logline', '')}\n"
                    f"Protagonist: {logline_data.get('who', '')}\n"
                    f"Goal: {logline_data.get('goal', '')}\n"
                    f"Core Conflict: {logline_data.get('conflict', '')}\n"
                    f"Twist: {logline_data.get('twist', '')}\n"
                    f"Theme: {logline_data.get('theme', '')}\n\n"
                    f"Original idea: {idea}"
                )

            # Step 3: 逐幕生成节拍表 + 分场大纲 + 结构化提取
            json_data = self._generate_script_incremental(
                llm, draft, style, llm_model, sid, is_zh, web_search=web_search, pct_start=20
            )

            # 补充元数据
            json_data.setdefault("project_id", f"proj_{sid}")
            json_data.setdefault("version", 1)
            json_data["created_at"] = datetime.now(timezone.utc).isoformat()
            json_data["metadata"] = {
                "generation_model": llm_model,
                "generation_prompt": idea,
            }
            json_data["session_id"] = sid
            json_data["logline_data"] = logline_data

            self._save_result(json_data, sid, is_zh)
            # 保存进度状态
            self._save_progress(sid, "script_generation", {
                "title": json_data.get("title")
            })
            self._report_progress("剧本生成", "完成", 100)
            return json_data

        loop = asyncio.get_running_loop()
        script_json = await loop.run_in_executor(None, run)

        # 保存进度状态
        self._save_progress(sid, "script_generation", {
            "title": script_json.get("title")
        })

        return {
            "payload": script_json,
            "requires_intervention": False,
            "stage_completed": True,  # 明确标记阶段完成
            "openclaw_hint": "剧本生成完成。",
        }

    # ─── 公共: 逐幕生成节拍表 + 分场大纲 + 结构化提取 ───

    def _generate_script_incremental(self, llm, draft: str, style: str,
                                      llm_model: str, sid: str, is_zh: bool,
                                      web_search: bool = False,
                                      pct_start: int = 20) -> dict:
        """生成 Save the Cat! 节拍表 → 逐幕生成分场大纲 + 结构化提取，返回合并的 JSON"""

        # Step 1: 生成四幕节拍表
        self._report_progress("剧本生成", "生成节拍表...", pct_start)
        prompt = (BEAT_SHEET_PROMPT_ZH if is_zh else BEAT_SHEET_PROMPT_EN).format(draft=draft, style=style)
        beat_sheet = self._cancellable_query(llm, prompt, model=llm_model, task_id=sid, web_search=web_search)
        logger.info(f"[ScriptWriter] Beat sheet generated ({len(beat_sheet)} chars)")

        # 发送节拍表到前端
        self._report_progress("剧本生成", "节拍表生成完成", pct_start + 5,
                              data={"beat_sheet": beat_sheet})

        # Step 2: 提取顶层元数据 (title, logline, genre, synopsis, mood)
        self._report_progress("剧本生成", "提取故事元信息...", pct_start + 7)
        meta_prompt = (META_EXTRACT_PROMPT_ZH if is_zh else META_EXTRACT_PROMPT_EN).format(beat_sheet=beat_sheet)
        meta_raw = self._cancellable_query(llm, meta_prompt, model=llm_model, task_id=sid, web_search=web_search)
        meta_data = self._extract_json_from_text(meta_raw) or {}
        logger.info(f"[ScriptWriter] Meta extracted: {list(meta_data.keys())}")

        # Step 3: 逐幕生成分场大纲 + 结构化提取
        act_names = ACT_NAMES_ZH if is_zh else ACT_NAMES_EN
        all_characters = []  # 累积角色
        all_settings = []    # 累积场景
        all_scenes = []      # 累积分场
        seen_char_names = set()
        seen_setting_names = set()
        scene_start = 1

        for act_num in range(1, 5):
            self._check_cancel()
            act_name = act_names[act_num]

            # --- 生成分场大纲 ---
            pct_outline = pct_start + 8 + (act_num - 1) * 15  # 28, 43, 58, 73
            progress_msg = (f"生成第{act_num}幕分场大纲（{act_name}）..."
                            if is_zh else f"Generating Act {act_num} outline ({act_name})...")
            self._report_progress("剧本生成", progress_msg, pct_outline)

            outline_prompt = (STEP_OUTLINE_PROMPT_ZH if is_zh else STEP_OUTLINE_PROMPT_EN).format(
                beat_sheet=beat_sheet,
                act_number=act_num,
                act_name=act_name,
                scene_start=scene_start,
                style=style,
            )
            outline = self._cancellable_query(llm, outline_prompt, model=llm_model, task_id=sid, web_search=web_search)
            logger.info(f"[ScriptWriter] Act {act_num} outline generated ({len(outline)} chars)")

            # --- 结构化提取本幕 JSON ---
            pct_extract = pct_outline + 8
            progress_msg = (f"提取第{act_num}幕结构化数据..."
                            if is_zh else f"Extracting Act {act_num} structured data...")
            self._report_progress("剧本生成", progress_msg, pct_extract)

            act_json = self._extract_act_json(
                llm, outline, act_num, scene_start, style, llm_model, sid, is_zh, web_search
            )

            # 累积角色（去重）
            for c in act_json.get("characters", []):
                if c.get("name") and c["name"] not in seen_char_names:
                    if not c.get("character_id"):
                        c["character_id"] = self._gen_id("char")
                    all_characters.append(c)
                    seen_char_names.add(c["name"])

            # 累积场景（去重）
            for s in act_json.get("settings", []):
                if s.get("name") and s["name"] not in seen_setting_names:
                    if not s.get("setting_id"):
                        s["setting_id"] = self._gen_id("set")
                    all_settings.append(s)
                    seen_setting_names.add(s["name"])

            # 累积分场
            act_scenes = act_json.get("scenes", [])
            all_scenes.extend(act_scenes)

            # 计算下一幕场次起始
            if act_scenes:
                scene_start = max(s.get("scene_number", scene_start) for s in act_scenes) + 1

            # 发送本幕结果到前端
            act_label = f"第{act_num}幕 - {act_name}" if is_zh else f"Act {act_num} - {act_name}"
            self._report_progress("剧本生成",
                                  f"{act_label} 完成" if is_zh else f"{act_label} done",
                                  pct_extract + 2,
                                  data={"act_complete": {
                                      "act": act_num,
                                      "act_name": act_name,
                                      "characters": act_json.get("characters", []),
                                      "settings": act_json.get("settings", []),
                                      "scenes": act_scenes,
                                  }})

        # Step 4: 合并最终 JSON
        # 重新编号 scene_number
        for i, sc in enumerate(all_scenes):
            sc["scene_number"] = i + 1

        json_data = {
            "title": meta_data.get("title", ""),
            "logline": meta_data.get("logline", ""),
            "genre": meta_data.get("genre", []),
            "target_duration": 1800,
            "synopsis": meta_data.get("synopsis", ""),
            "characters": all_characters,
            "settings": all_settings,
            "scenes": all_scenes,
            "overall_style": style,
            "mood": meta_data.get("mood", ""),
        }

        # Step 5: 合并相似场景和角色
        self._report_progress("剧本生成",
                              "审查并合并相似场景..." if is_zh else "Consolidating similar settings...",
                              96)
        json_data = self._consolidate_script(llm, json_data, llm_model, sid, is_zh, web_search=web_search)

        return json_data

    # ─── 微电影模式: 单幕紧凑生成 ───

    def _generate_micro_script_incremental(self, llm, draft: str, style: str,
                                            llm_model: str, sid: str, is_zh: bool,
                                            web_search: bool = False,
                                            pct_start: int = 20) -> dict:
        """微电影模式：生成紧凑单幕剧情概要 → 分场大纲 → 结构化提取，返回合并的 JSON"""

        # Step 1: 生成单幕剧情概要
        self._report_progress("剧本生成", "生成微电影剧情概要...", pct_start)
        prompt = (MICRO_BEAT_SHEET_PROMPT_ZH if is_zh else MICRO_BEAT_SHEET_PROMPT_EN).format(
            draft=draft, style=style
        )
        beat_sheet = self._cancellable_query(llm, prompt, model=llm_model, task_id=sid, web_search=web_search)
        logger.info(f"[ScriptWriter][micro] Beat sheet generated ({len(beat_sheet)} chars)")

        # 发送概要到前端
        self._report_progress("剧本生成", "剧情概要生成完成", pct_start + 10,
                              data={"beat_sheet": beat_sheet})

        # Step 2: 提取顶层元数据
        self._report_progress("剧本生成", "提取故事元信息...", pct_start + 15)
        meta_prompt = (MICRO_META_EXTRACT_PROMPT_ZH if is_zh else MICRO_META_EXTRACT_PROMPT_EN).format(
            beat_sheet=beat_sheet
        )
        meta_raw = self._cancellable_query(llm, meta_prompt, model=llm_model, task_id=sid, web_search=web_search)
        meta_data = self._extract_json_from_text(meta_raw) or {}
        logger.info(f"[ScriptWriter][micro] Meta extracted: {list(meta_data.keys())}")

        # Step 3: 生成分场大纲
        self._check_cancel()
        self._report_progress("剧本生成",
                              "生成微电影分场大纲..." if is_zh else "Generating micro-film step outline...",
                              pct_start + 25)

        outline_prompt = (MICRO_STEP_OUTLINE_PROMPT_ZH if is_zh else MICRO_STEP_OUTLINE_PROMPT_EN).format(
            beat_sheet=beat_sheet, style=style
        )
        outline = self._cancellable_query(llm, outline_prompt, model=llm_model, task_id=sid, web_search=web_search)
        logger.info(f"[ScriptWriter][micro] Outline generated ({len(outline)} chars)")

        # Step 4: 结构化 JSON 提取
        self._report_progress("剧本生成",
                              "提取结构化数据..." if is_zh else "Extracting structured data...",
                              pct_start + 45)

        act_json = self._extract_act_json(
            llm, outline, act_number=1, scene_start=1,
            style=style, llm_model=llm_model, sid=sid, is_zh=is_zh,
            web_search=web_search
        )

        characters = act_json.get("characters", [])
        settings = act_json.get("settings", [])
        scenes = act_json.get("scenes", [])

        # 补全 ID
        for c in characters:
            if not c.get("character_id"):
                c["character_id"] = self._gen_id("char")
        for s in settings:
            if not s.get("setting_id"):
                s["setting_id"] = self._gen_id("set")

        # 重新编号并去掉 act 字段（微电影不分幕）
        for i, sc in enumerate(scenes):
            sc["scene_number"] = i + 1
            sc.pop("act", None)

        # 发送到前端
        act_label = "微电影" if is_zh else "Micro-film"
        self._report_progress("剧本生成",
                              f"{act_label} 分场完成" if is_zh else f"{act_label} scenes done",
                              pct_start + 60,
                              data={"act_complete": {
                                  "act": 1,
                                  "act_name": act_label,
                                  "characters": characters,
                                  "settings": settings,
                                  "scenes": scenes,
                              }})

        # Step 5: 合并最终 JSON
        json_data = {
            "title": meta_data.get("title", ""),
            "logline": meta_data.get("logline", ""),
            "genre": meta_data.get("genre", []),
            "target_duration": 180,  # 微电影默认 3 分钟
            "synopsis": meta_data.get("synopsis", ""),
            "characters": characters,
            "settings": settings,
            "scenes": scenes,
            "overall_style": style,
            "mood": meta_data.get("mood", ""),
        }

        # Step 6: 合并相似场景和角色
        self._report_progress("剧本生成",
                              "审查并合并相似场景..." if is_zh else "Consolidating similar settings...",
                              pct_start + 70)
        json_data = self._consolidate_script(llm, json_data, llm_model, sid, is_zh, web_search=web_search)

        return json_data

    # ─── 公共: 单幕结构化提取 (带校验重试) ───

    def _extract_act_json(self, llm, outline: str, act_number: int,
                          scene_start: int, style: str,
                          llm_model: str, sid: str, is_zh: bool,
                          web_search: bool = False) -> dict:
        """从单幕分场大纲提取结构化JSON，带校验重试"""
        schema = (ACT_EXTRACT_SCHEMA_ZH if is_zh else ACT_EXTRACT_SCHEMA_EN).format(
            act_number=act_number, scene_start=scene_start
        )
        intro = (ACT_EXTRACT_INTRO_ZH if is_zh else ACT_EXTRACT_INTRO_EN).format(
            act_number=act_number, outline=outline
        )
        rules = (ACT_EXTRACT_RULES_ZH if is_zh else ACT_EXTRACT_RULES_EN).format(
            act_number=act_number, scene_start=scene_start
        )
        extract_prompt = intro + schema + rules

        last_error = ""

        for attempt in range(3):
            self._check_cancel()
            raw = self._cancellable_query(llm, extract_prompt, model=llm_model, task_id=sid, web_search=web_search)
            parsed = self._extract_json_from_text(raw)

            if parsed is None:
                last_error = "LLM输出无法解析为JSON"
                logger.warning(f"[ScriptWriter] Act {act_number} extract attempt {attempt + 1}: JSON parse failed")
                extract_prompt = (
                    ("上次输出不是合法JSON，请重新输出。" if is_zh
                     else "Previous output was not valid JSON. Please try again. ")
                    + intro + schema + rules
                )
                continue

            # 基本校验: 必须有 scenes 列表
            scenes = parsed.get("scenes")
            if not isinstance(scenes, list) or len(scenes) == 0:
                last_error = "scenes 必须是非空列表"
                logger.warning(f"[ScriptWriter] Act {act_number} extract attempt {attempt + 1}: no scenes")
                extract_prompt = (
                    (f"上次输出的JSON缺少scenes。请确保scenes是非空列表。" if is_zh
                     else "Previous JSON had no scenes. Ensure scenes is a non-empty array. ")
                    + intro + schema + rules
                )
                continue

            # 校验每个 scene 的必要字段
            valid = True
            for i, sc in enumerate(scenes):
                for key in ["scene_number", "act", "location", "characters", "plot"]:
                    if key not in sc:
                        last_error = f"scenes[{i}] 缺少字段: {key}"
                        valid = False
                        break
                if not valid:
                    break

            if not valid:
                logger.warning(f"[ScriptWriter] Act {act_number} extract attempt {attempt + 1}: {last_error}")
                extract_prompt = (
                    (f"上次输出的JSON存在问题: {last_error}。请修正后重新输出。" if is_zh
                     else f"Previous JSON issue: {last_error}. Please fix and retry. ")
                    + intro + schema + rules
                )
                continue

            return parsed

        raise Exception(f"第{act_number}幕JSON提取失败 (已重试3次): {last_error}")

    # ─── 公共: 场景 & 角色合并 ───

    def _consolidate_script(self, llm, json_data: dict,
                            llm_model: str, sid: str, is_zh: bool,
                            web_search: bool = False) -> dict:
        """审查并合并重复/相似的场景和角色"""
        characters = json_data.get("characters", [])
        settings = json_data.get("settings", [])
        scenes = json_data.get("scenes", [])

        if len(settings) <= 1 and len(characters) <= 1:
            return json_data

        # 构建简洁的列表供 LLM 审查
        settings_summary = [{"name": s["name"], "description": s.get("description", "")}
                            for s in settings]
        chars_summary = [{"name": c["name"], "description": c.get("description", "")}
                         for c in characters]

        prompt = (CONSOLIDATE_PROMPT_ZH if is_zh else CONSOLIDATE_PROMPT_EN).format(
            settings_json=json.dumps(settings_summary, ensure_ascii=False, indent=2),
            characters_json=json.dumps(chars_summary, ensure_ascii=False, indent=2),
        )

        self._check_cancel()
        raw = self._cancellable_query(llm, prompt, model=llm_model, task_id=sid, web_search=web_search)
        result = self._extract_json_from_text(raw)

        if not result or not isinstance(result, dict):
            logger.warning("[ScriptWriter] Consolidation: failed to parse LLM response, skipping")
            return json_data

        setting_merges = result.get("setting_merges", {})
        char_merges = result.get("character_merges", {})

        if not setting_merges and not char_merges:
            logger.info("[ScriptWriter] Consolidation: nothing to merge")
            return json_data

        # --- 合并场景 ---
        if setting_merges:
            logger.info(f"[ScriptWriter] Merging settings: {setting_merges}")
            # 移除被合并的 settings
            merged_names = set(setting_merges.keys())
            json_data["settings"] = [s for s in settings if s["name"] not in merged_names]

            # 更新 scenes 中的 location 引用
            for sc in scenes:
                loc = sc.get("location", "")
                if loc in setting_merges:
                    sc["location"] = setting_merges[loc]

        # --- 合并角色 ---
        if char_merges:
            logger.info(f"[ScriptWriter] Merging characters: {char_merges}")
            merged_char_names = set(char_merges.keys())
            json_data["characters"] = [c for c in characters if c["name"] not in merged_char_names]

            # 更新 scenes 中的 characters 引用
            for sc in scenes:
                new_chars = []
                seen = set()
                for cn in sc.get("characters", []):
                    target = char_merges.get(cn, cn)
                    if target not in seen:
                        new_chars.append(target)
                        seen.add(target)
                sc["characters"] = new_chars

        logger.info(f"[ScriptWriter] After consolidation: "
                     f"{len(json_data['settings'])} settings, "
                     f"{len(json_data['characters'])} characters")

        # 验证 scenes 的 location 是否都在 settings 中
        settings_names = {s["name"] for s in json_data.get("settings", [])}
        for sc in json_data.get("scenes", []):
            loc = sc.get("location", "")
            if loc and loc not in settings_names:
                logger.error(f"[ScriptWriter] ERROR: Scene location '{loc}' not found in settings! available: {settings_names}")

        return json_data
