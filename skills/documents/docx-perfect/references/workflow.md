# 递增式文档美化工作流程

## 完整工作流

```
源文档 → 读取分析 → 确定章节 → 创建表格 → 应用样式 → 版本保存
   ↓         ↓         ↓         ↓         ↓         ↓
 .docx    提取文本   选择优化  定义数据  统一样式   v0.X
```

## 步骤详解

### Step 1: 读取源文档内容

```bash
python -c "
import sys; sys.stdout.reconfigure(encoding='utf-8')
from docx import Document
doc = Document('source.docx')
[p.text.strip() for p in doc.paragraphs if p.text.strip()]
"
```

### Step 2: 分析章节结构

识别需要美化的章节：
- 标题格式：`X.X 章节名称`
- 内容类型：文本列表、表格、混合

### Step 3: 定义表格数据

根据章节内容提取表格数据：
- 确定列名（表头）
- 确定行数据
- 注意：表头不包含在rows中

### Step 4: 创建并插入表格

```python
# 1. 创建表格
table = doc.add_table(rows=len(rows)+1, cols=len(headers))

# 2. 填充内容
for j, h in enumerate(headers):
    table.rows[0].cells[j].text = h
for i, row in enumerate(rows):
    for j, text in enumerate(row):
        table.rows[i+1].cells[j].text = text

# 3. 应用样式
format_table(table)

# 4. 插入到文档
table._element.getparent().insert(
    para._element.getparent().index(para._element) + 1,
    table._element
)
```

### Step 5: 版本号管理

自动递增版本号：
- `v0.1` → `v0.2` → `v0.3` → ... → `v0.9` → `v1.0`

## 章节美化优先级

建议按以下顺序美化：

1. **第4章 逻辑结构设计**（最重要）
   - 4.1 E-R图转换规则表格
   - 4.2 规范化检查表格
   - 4.3 数据表设计表格

2. **第3章 概念结构设计**
   - 3.1 实体识别表格
   - 3.2 实体间联系表格

3. **第2章 需求分析**
   - 2.2 功能需求表格
   - 2.5 技术选型表格

4. **第5章 物理结构设计**
   - 5.2 索引优化表格

## 常见问题

### Q: 中文乱码怎么办？
A: 使用 `sys.stdout.reconfigure(encoding='utf-8')` 在脚本开头。

### Q: 表格插入位置不对？
A: 检查 `insert` 的索引，使用正确的参考段落。

### Q: 样式不生效？
A: 确保 `format_table` 在填充内容**之后**调用。
