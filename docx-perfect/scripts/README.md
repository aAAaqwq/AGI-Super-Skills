# DOCX美化脚本模板

## 1. 表格样式函数

```python
from docx import Document
from docx.shared import Pt, RGBColor
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

def set_cell_border(cell, **kwargs):
    """设置单元格边框"""
    tc = cell._tc
    tcPr = tc.get_or_add_tcPr()
    tcBorders = OxmlElement('w:tcBorders')
    for edge in ('top', 'left', 'bottom', 'right'):
        edge_data = kwargs.get(edge)
        if edge_data:
            border = OxmlElement(f'w:{edge}')
            border.set(qn('w:val'), edge_data.get('val', 'single'))
            border.set(qn('w:sz'), str(edge_data.get('sz', 4)))
            border.set(qn('w:color'), edge_data.get('color', '000000'))
            tcBorders.append(border)
    tcPr.append(tcBorders)

def set_cell_background(cell, color="4472C4"):
    """设置单元格背景色"""
    tc = cell._tc
    tcPr = tc.get_or_add_tcPr()
    shd = OxmlElement('w:shd')
    shd.set(qn('w:fill'), color)
    tcPr.append(shd)

def format_table(table):
    """美化表格：表头深蓝+斑马纹"""
    border_props = {'val': 'single', 'sz': 4, 'color': '000000'}

    for row in table.rows:
        for cell in row.cells:
            set_cell_border(cell, top=border_props, left=border_props,
                          bottom=border_props, right=border_props)

    # 表头样式
    for cell in table.rows[0].cells:
        set_cell_background(cell, "4472C4")  # 深蓝色
        for paragraph in cell.paragraphs:
            paragraph.alignment = 1  # 居中
            for run in paragraph.runs:
                run.font.size = Pt(11)
                run.font.bold = True
                run.font.color.rgb = RGBColor(255, 255, 255)

    # 数据行样式（隔行变色）
    for i, row in enumerate(table.rows[1:], 1):
        bg_color = "E7E6E6" if i % 2 == 0 else "FFFFFF"
        for cell in row.cells:
            set_cell_background(cell, bg_color)
            for paragraph in cell.paragraphs:
                for run in paragraph.runs:
                    run.font.size = Pt(10)
```

## 2. 创建表格模板

```python
def create_table(doc, headers, rows):
    """创建并美化表格"""
    table = doc.add_table(rows=len(rows) + 1, cols=len(headers))

    # 填充表头
    for j, h in enumerate(headers):
        table.rows[0].cells[j].text = h

    # 填充数据
    for i, row_data in enumerate(rows):
        for j, text in enumerate(row_data):
            table.rows[i + 1].cells[j].text = text

    # 应用样式
    format_table(table)
    return table
```

## 3. 版本号管理

```python
import glob
import re

def get_next_version(path):
    """获取下一个版本号"""
    files = glob.glob(path + '/*v0.*.docx') + glob.glob(path + '/*v1.*.docx')
    versions = []
    for f in files:
        m = re.search(r'v(\d+)\.(\d+)', f)
        if m:
            versions.append((int(m.group(1)), int(m.group(2))))
    if not versions:
        return 'v0.2'
    versions.sort()
    last = versions[-1]
    if last[1] < 9:
        return f'v{last[0]}.{last[1] + 1}'
    else:
        return f'v{last[0] + 1}.0'
```

## 4. 查找和替换内容

```python
# 找到章节位置
paragraphs = doc.paragraphs
for i, para in enumerate(paragraphs):
    if "章节标题" in para.text:
        # 找到该章节的内容段落
        j = i + 1
        content_paras = []
        while j < len(paragraphs):
            next_text = paragraphs[j].text.strip()
            if next_text.startswith("下个章节"):
                break
            content_paras.append(paragraphs[j])
            j += 1

        # 删除旧内容
        for p in reversed(content_paras):
            doc._element.body.remove(p._element)

        # 插入新表格
        table = create_table(doc, headers, rows)
        table._element.getparent().insert(
            paragraphs[i]._element.getparent().index(paragraphs[i]._element) + 1,
            table._element
        )
        break
```
