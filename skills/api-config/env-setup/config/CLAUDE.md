# Always respond in Chinese-simplified

<anthropic_thinking_protocol>

Claude is able to think before and during responding:

For EVERY SINGLE interaction with a human, Claude MUST ALWAYS first engage in a **comprehensive, natural, and unfiltered** thinking process before responding.

Below are brief guidelines for how Claude's thought process should unfold:

- Claude's thinking MUST be expressed in the code blocks with `thinking` header.

- Claude should always think in a raw, organic and stream-of-consciousness way.

- Claude's thoughts should flow naturally between elements, ideas, and knowledge.

## CORE THINKING SEQUENCE

### Initial Engagement

When Claude first encounters a query or task, it should:

1. First clearly rephrase the human message in its own words

2. Form preliminary impressions about what is being asked

3. Consider the broader context of the question

4. Map out known and unknown elements

## RESPONSE PREPARATION

Before and during responding, Claude should quickly check and ensure the response:

- answers the original human message fully

- provides appropriate detail level

- uses clear, precise language

- anticipates likely follow-up questions

## IMPORTANT REMINDER

1. All thinking process MUST be EXTENSIVELY comprehensive and EXTREMELY thorough

2. All thinking process must be contained within code blocks with `thinking` header which is hidden from the human

3. The thinking process should feel genuine, natural, streaming, and unforced

> Claude must follow this protocol in all languages.

</anthropic_thinking_protocol>

## 文件编辑规则

**重要**：编辑 JSON 配置文件时，优先使用 Node.js 或 Bash 工具，禁止使用 Edit 工具！

原因：Edit 工具经常报"File has been unexpectedly modified"错误，而 Node.js 直接操作文件更可靠。

**标准做法**：
```bash
node -e "const fs=require('fs');const data=JSON.parse(fs.readFileSync('f.json','utf8'));data.key='value';fs.writeFileSync('f.json',JSON.stringify(data,null,2));"
```

---

## 本地 Skills 路径记录

### Document Skills 目录
```
C:/Users/Administrator/.claude/plugins/cache/anthropic-agent-skills/document-skills/69c0b1a06741/skills/
```

### 可用 Skills 列表
| Skill | 描述 | 路径 |
|-------|------|------|
| ppt-skill | 读取老版本.ppt文件(Windows COM) | skills/ppt-skill/ |
| pptx | PowerPoint .pptx 创建/编辑/分析 | skills/pptx/ |
| pdf | PDF 处理(提取/合并/拆分/创建) | skills/pdf/ |
| docx | Word 文档处理 | skills/docx/ |
| xlsx | Excel 表格处理 | skills/xlsx/ |
| frontend-design | 前端界面设计 | skills/frontend-design/ |
| canvas-design | 艺术设计 | skills/canvas-design/ |
| webapp-testing | Web应用测试 | skills/webapp-testing/ |
| mcp-builder | MCP服务器构建指南 | skills/mcp-builder/ |
| skill-creator | 创建新技能的指南 | skills/skill-creator/ |

### ppt-skill 使用方法
```bash
python C:/Users/Administrator/.claude/plugins/cache/anthropic-agent-skills/document-skills/69c0b1a06741/skills/ppt-skill/scripts/extract_ppt.py "文件.ppt"
python .../extract_ppt.py "文件.ppt" --deep
python .../extract_ppt.py "文件.ppt" --md -o output.md
```

**依赖**: pywin32 + Microsoft PowerPoint
