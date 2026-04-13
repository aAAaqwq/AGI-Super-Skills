# 帧设计指南 (Frame Design)

## 概述
首帧/尾帧的连续性设计是 MV 分镜脚本的核心质量指标。每个分镜的首帧必须承接上一个分镜的尾帧，确保视觉叙事流畅。

## 一、首尾帧连续性设计原则

### 核心原则：Three-Element Continuity (三要素连续性)

每个分镜的尾帧到下一分镜首帧，至少保持 **2/3** 的以下要素一致：

1. **空间连续** — 背景/环境元素一致或有逻辑过渡
2. **主体连续** — Chloe 的位置、姿态、表情有承接
3. **动态元素连续** — 飘落的花瓣、流动的水、光线方向

### 连续性检查清单

```
✅ 上一尾帧的 Chloe 姿态 = 下一首帧的起始姿态？
✅ 上一尾帧的环境元素（花瓣/光线/雾气）在下一首帧中存在？
✅ 色温/色调是否平滑过渡（除非是刻意对比）？
✅ 运镜方向是否合理承接（不能突然反向）？
✅ 光源方向是否一致（除非场景切换）？
```

### 典型连续性错误
- ❌ 上一帧在室内，下一帧突然在山顶（没有过渡）
- ❌ 上一帧是晴天，下一帧是暴风雨（没有铺垫）
- ❌ 上一帧面向左，下一帧突然面向右（没有运镜解释）
- ❌ 上一帧穿白裙，下一帧换了红裙（除非有理由）

## 二、Gemini 合成人物+场景的构图法则

### Gemini 图像合成原则

Gemini 生成首尾帧时，需要同时包含 **人物 (Chloe)** 和 **场景** 的完整描述。

### 构图类型与适用场景

#### 1. 远景 (Wide Shot) — 场景为主
- **比例**: 人物占画面 10-20%
- **适用**: Intro, Outro, 场景建立
- **Chloe 描述重点**: 剪影/轮廓，白裙的流动感
- **Prompt 模板**: 
  ```
  wide shot, [场景描述], small figure of ethereal young woman in white lace 
  embroidery dress standing [位置], [光源描述], cinematic composition, 
  [色调] color grading
  ```

#### 2. 全景 (Full Shot) — 人物+环境
- **比例**: 人物占画面 40-50%
- **适用**: Verse, 舞蹈段落
- **Chloe 描述重点**: 全身，裙摆+折伞+发饰
- **Prompt 模板**:
  ```
  full body shot, [Chloe 完整描述] in [场景描述], [动作描述], 
  [光源描述], [色调] color grading, professional photography
  ```

#### 3. 中景 (Medium Shot) — 上半身+场景
- **比例**: 人物占画面 60-70%，腰部以上
- **适用**: Pre-Chorus, 情感表达
- **Chloe 描述重点**: 表情+上半身动作+手持道具
- **Prompt 模板**:
  ```
  medium shot, waist up, [Chloe 面部+上半身描述], [场景背景虚化], 
  [情绪表达], [光源描述], shallow depth of field
  ```

#### 4. 特写 (Close-up) — 面部/细节
- **比例**: 人物占画面 80-100%
- **适用**: 高潮，情绪爆发
- **Chloe 描述重点**: 眼神、唇、泪、发丝
- **Prompt 模板**:
  ```
  extreme close-up, [Chloe 面部细节描述], [情绪], [背景完全虚化/光斑], 
  [光源在眼中的反射], cinematic portrait, 85mm lens
  ```

### Chloe 视觉描述标准模板

每个帧的 visual_prompt 必须包含以下元素（根据景别调整）：

```python
CHLOE_VISUAL = {
    "core": "ethereal 22-year-old Asian young woman",
    "skin": "porcelain skin, translucent quality",
    "hair": "long straight black hair with cherry blossom hairpin",
    "outfit": "white lace embroidery dress, Victorian-inspired collar",
    "accessories": "vintage lace parasol (held or nearby)",
    "makeup": "natural dewy makeup, soft pink lips",
    "expression": "{emotion_adaptive}",  # 根据情绪调整
    "palette": "morning white + cherry blossom pink + soft sage green"
}
```

### Gemini Composite 标记说明

```json
{
  "gemini_composite": true,   // 需要用 Gemini 生成人物+场景合成图
  "composition": "三分法构图，人物偏右",  // 构图说明
  "focus": "人物面部",          // 对焦点
  "depth_of_field": "浅景深"    // 景深
}
```

## 三、运镜基础

### 基础运镜类型

| 运镜 | 英文 | 效果 | 适用场景 | Prompt 关键词 |
|------|------|------|---------|--------------|
| 推 | Push-in / Zoom-in | 聚焦、强调、逼近 | 情绪加强、揭示 | slow push-in, gradual zoom |
| 拉 | Pull-out / Zoom-out | 揭示全貌、疏离 | 从情绪抽离、场景揭示 | pull back, zoom out revealing |
| 摇 | Pan (水平) / Tilt (垂直) | 环境展示、跟随 | 展示空间、跟随人物 | slow pan left/right, tilt up |
| 移 | Dolly / Tracking | 跟随、沉浸 | 跟拍人物行走/奔跑 | tracking shot, dolly follow |
| 跟 | Follow | 沉浸式跟随 | 第一人称感、追逐 | following shot, over-shoulder |
| 升降 | Crane / Jib | 宏大感、上帝视角 | 高潮揭示、宏大场面 | crane up, aerial reveal |
| 环绕 | Orbit / Arc | 360°展示 | 人物展示、高潮 | orbiting shot, 360 arc |
| 手持 | Handheld | 紧张、真实、动态 | 情绪激烈、冲突 | handheld, shaky cam |
| 固定 | Static | 稳定、宁静 | 空镜、冥想、对比 | static shot, locked camera |
| 升格 | Slow-mo | 慢动作、戏剧性 | 花瓣飘落、泪滴 | slow motion, 120fps |

### 运镜选择决策树

```
情绪分 < 4？
  ├─ 是 → static / slow push-in / slow pan
  └─ 否 → 情绪分 < 7？
       ├─ 是 → tracking / dolly / slow orbit
       └─ 否 → handheld / fast push-pull / crane / multi-move
```

### 运镜组合（高级）

| 组合 | 效果 | 适用 |
|------|------|------|
| 推+升 | 从近到远到高，揭示感 | Chorus 进入 |
| 拉+降 | 从高到近，聚焦感 | Bridge 结束 |
| 摇+跟 | 跟随中展示环境 | Verse 叙事 |
| 环绕+升降 | 史诗感旋转上升 | Final Chorus |
| 手持+推 | 紧迫感逼近 | 爆发点 |

## 四、首帧/尾帧设计流程

### Step 1: 确定该分镜的叙事目的
```
这个分镜要表达什么？
- 建立场景？→ 远景开始
- 展示情感？→ 中近景
- 制造冲击？→ 特写
- 过渡衔接？→ 上帧的延续
```

### Step 2: 设计首帧（承接上一尾帧）
```
上一分镜尾帧的核心元素是什么？
→ 保留至少 2 个元素进入首帧
→ 加入新的变化（推进/换角度/新元素）
```

### Step 3: 设计尾帧（为下一分镜铺路）
```
下一分镜要表达什么？
→ 尾帧需要包含过渡到下一场景的元素
→ 例如：下一场景是雨巷 → 尾帧中天空变暗/出现雨滴
```

### Step 4: 写 visual_prompt
```
将首帧/尾帧的视觉描述合并为完整的 prompt：
景别 + 人物描述 + 场景描述 + 光源 + 色调 + 构图
```

## 五、帧描述模板

### 首帧模板
```json
{
  "description": "[景别]：[场景描述]，Chloe [姿态/动作]，[关键视觉元素]，[光源描述]",
  "gemini_composite": true,
  "composition": "[构图方法]",
  "continuity_from": "承接上一分镜尾帧的 [具体元素]"
}
```

### 尾帧模板
```json
{
  "description": "[景别]：[场景描述]，Chloe [姿态/动作]，[过渡元素出现]，[光源变化]",
  "gemini_composite": true,
  "composition": "[构图方法]",
  "leads_to": "为下一分镜铺路：[过渡元素]"
}
```
