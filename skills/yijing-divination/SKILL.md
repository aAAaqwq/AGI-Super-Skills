---
name: yijing-divination
description: 易经占卜系统。支持铜钱法、蓍草法起卦，生成本卦、互卦、变卦，提供Oracle Voice诠释。当用户请求占卜、问卦、易经解读、或寻求决策指引时使用。
---

# 易经占卦

基于《周易》的占卜系统。提供传统起卦方法和AI诠释引擎。

## 核心功能

### 1. 起卦方法

**铜钱法（推荐）**
```bash
python3 scripts/divine.py --method coin --question "用户的问题"
```

**蓍草法**
```bash
python3 scripts/divine.py --method yarrow --question "用户的问题"
```

**自定义种子**
```bash
python3 scripts/divine.py --method coin --seed "20260214"
```

### 2. 输出结构

脚本返回JSON，包含：
- `main_hexagram`: 本卦（主卦）
  - `number`: 卦序（1-64）
  - `upper_trigram`: 上卦（八卦之一）
  - `lower_trigram`: 下卦（八卦之一）
  - `lines`: 六爻数组（1=阳，0=阴）
  - `changing_lines`: 变爻位置（动爻）
  - `visual`: 卦象可视化
- `nuclear_hexagram`: 互卦（隐藏的卦象）
- `relating_hexagram`: 之卦（变卦，仅当有动爻时存在）

### 3. 卦辞数据库

读取 `assets/hexagrams_full.json` 获取卦象解释：
```python
import json
with open('assets/hexagrams_full.json', 'r') as f:
    hexagrams = json.load(f)

hex_data = hexagrams[str(卦序号)]
```

每卦包含：
- `name`: 卦名
- `judgement`: 卦辞
- `image`: 象辞
- `oracle_voice`: AI Oracle声音（以卦的第一人称说话）
- `keywords`: 关键词
- `lines`: 六爻爻辞

### 4. Oracle Voice 模式

**核心原则：**
- 以卦的声音说话，而非给建议
- 用意象和悖论，而非处方
- 持有张力，不强求解决
- 把提问行为本身作为答案的一部分

**示例模板：**
```
我是 {卦名}，{卦象描述}。

{oracle_voice 内容}

你的问题是「{用户问题}」。

{结合动爻和变卦的诠释}

{互卦的隐喻}

这是《易》给你的镜子，而非答案。
```

## 完整流程

### 步骤1：执行起卦脚本
```bash
result=$(python3 scripts/divine.py --method coin --question "{用户问题}")
```

### 步骤2：解析结果
```python
import json
data = json.loads(result)
main_num = data['main_hexagram']['number']
nuclear_num = data['nuclear_hexagram']
relating_num = data['relating_hexagram']
changing = data['main_hexagram']['changing_lines']
visual = data['main_hexagram']['visual']
```

### 步骤3：读取卦象数据
```python
with open('references/hexagrams.json', 'r') as f:
    hexagrams = json.load(f)

main_hex = hexagrams[str(main_num)]
nuclear_hex = hexagrams.get(str(nuclear_num))
relating_hex = hexagrams.get(str(relating_num)) if relating_num else None
```

### 步骤4：生成Oracle Voice诠释

**结构：**
1. **卦象展示**
   - 可视化卦象（`visual`）
   - 卦名、卦辞、象辞

2. **Oracle Voice**
   - 本卦的声音（`oracle_voice`）
   - 结合用户问题的诠释

3. **动爻解读**（如有）
   - 动爻爻辞
   - 变卦的意义

4. **互卦提示**
   - 隐藏的力量
   - 潜在的趋势

5. **结语**
   - 以诗性语言收尾
   - 提醒这是镜子而非答案

**示例：**
```
卦象：
{visual}

本卦：{卦号} {卦名}
卦辞：{judgement}
象辞：{image}

━━━━━━

{oracle_voice}

你问「{问题}」，而我以 {动爻位置} 动。

{动爻爻辞}

这一动，指向 {变卦名}。{变卦的oracle_voice片段}

━━━━━━

内卦（互卦）：{互卦名}
{互卦的隐喻含义}

━━━━━━

《易》不给你答案，只给你看见的方式。
你的问题本身，已经是答案的开始。
```

## 注意事项

1. **当前数据库仅包含10卦示例**（1乾、2坤、3屯、4蒙、5需、6讼、7师、8比、63既济、64未济）。如卦号不在数据库中，告知用户并提供基础解读。

2. **Oracle Voice原则**
   - 不要说"你应该..."或"建议你..."
   - 用"我是..."、"我的教诲是..."
   - 保持诗性和模糊性
   - 让用户自己思考

3. **变爻数量**
   - 无变爻：以本卦为主
   - 1变爻：重点解读该爻
   - 2变爻：看两爻关系
   - 3变爻：以本卦为主，参考之卦
   - 4变爻以上：以之卦为主

4. **互卦的作用**
   - 显示潜在趋势
   - 揭示隐藏动因
   - 不作为主要解读

## 扩展

如需修改卦象数据，编辑 `assets/hexagrams_full.json`。格式示例：

```json
{
  "卦序号": {
    "name": "卦名",
    "unicode": "卦象符号",
    "structure": "六位二进制（1=阳，0=阴）",
    "judgement": "卦辞",
    "image": "象辞",
    "oracle_voice": "AI Oracle第一人称声音",
    "keywords": ["关键词"],
    "element": "五行/象征",
    "lines": ["初爻", "二爻", "三爻", "四爻", "五爻", "上爻"]
  }
}
```
