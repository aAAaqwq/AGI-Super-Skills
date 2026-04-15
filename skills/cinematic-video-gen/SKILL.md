---
name: cinematic-video-gen
description: "AI视频生成质量增强引擎。解决AI视频角色僵硬、表情空白、动作机械的问题。通过高级prompt工程+角色卡+运镜指令+表情库，让AI视频角色活起来。触发词：视频质量、角色僵硬、灵动、表情、动作、cinematic video、视频生成增强、MV视频、角色动画"
---

# Cinematic Video Generation — 角色灵动性增强引擎

## 问题诊断

AI视频生成（doubao-seedance / kling / sora / veo）的通病：
- ❌ 角色像蜡像，表情空白
- ❌ 动作机械，缺乏自然流畅感
- ❌ 手部僵硬，肢体不协调
- ❌ 眼神空洞，缺少情感表达
- ❌ 同一角色在不同clip间不一致

## 核心方法论：五维灵动框架

### 维度1：表情指令库 (Expression Vocabulary)

| 情绪 | 英文指令 | 中文意境 |
|------|---------|---------|
| 忧伤 | "eyes glistening with unshed tears, lips slightly trembling, a bittersweet smile forming" | 眼含泪光，唇微颤，苦笑 |
| 怅然 | "gazing into the distance with a melancholic longing, wind tousling her hair, lost in thought" | 远望含愁，风拂发丝 |
| 温柔 | "a warm gentle smile spreading across her face, eyes crinkling at the corners, radiating kindness" | 温暖微笑，眼角弯弯 |
| 坚定 | "jaw set with quiet determination, eyes blazing with inner strength, unwavering gaze" | 下巴微抬，目光坚定 |
| 惊喜 | "eyes widening with wonder, mouth forming a soft 'oh', face illuminated with sudden joy" | 眼睛一亮，嘴微张 |
| 释然 | "shoulders dropping with relief, a peaceful exhale visible, serene contentment" | 肩膀放松，释然微笑 |

**使用规则**：每个 clip 的 prompt 必须包含至少一个表情指令。

### 维度2：肢体动作指令 (Body Movement Vocabulary)

| 部位 | 微动作 | 大动作 |
|------|--------|--------|
| 手 | "fingers gracefully tracing the air" / "hands gently clasping petals" | "arms sweeping wide open" / "reaching toward the light" |
| 头 | "head tilting slightly" / "chin lifting gently" | "turning to look over her shoulder" / "head thrown back in laughter" |
| 身体 | "shoulders swaying subtly to the rhythm" / "body swaying gently" | "spinning slowly with dress flowing" / "leaning into the wind" |
| 脚 | "shifting weight from one foot to another" | "walking gracefully through the petals" / "twirling on tiptoe" |

**使用规则**：每个 clip 至少 1 个微动作 + 1 个大动作（大场景时）。

### 维度3：运镜与角色互动 (Camera-Subject Interaction)

| 运镜 | 角色配合 | 效果 |
|------|---------|------|
| slow push-in | 角色慢慢转向镜头 | 亲密感、情感拉近 |
| tracking shot | 角色漫步，镜头跟随 | 自然流畅、叙事感 |
| crane up | 角色抬头仰望，镜头上升 | 壮阔感、精神升华 |
| orbit 360° | 角色原地轻转，镜头环绕 | 空间感、梦幻感 |
| handheld close-up | 角色微表情特写 | 纪实感、情感冲击 |
| pull back reveal | 角色静止，镜头拉远 | 孤独感、渺小感 |

**使用规则**：prompt 中必须指定运镜方式 + 角色对该运镜的自然反应。

### 维度4：角色一致性锚点 (Character Consistency Anchor)

每个 MV/视频项目需要一个 **角色卡**，在所有 clip prompt 中嵌入：

```
[CHARACTER_ANCHOR]
Name: Chloe (克洛伊)
Appearance: A young woman in her early 20s, long flowing black hair with subtle cherry blossom pink tips, 
  wearing an ethereal white dress with delicate floral embroidery, slender figure, porcelain skin
Signature features: Always has a small cherry blossom hairpin on the left side, 
  eyes are deep brown with a hint of melancholy
Build: Petite, graceful, dancer-like posture
[/CHARACTER_ANCHOR]
```

**使用规则**：
- 每个 clip prompt 开头插入角色锚点（缩减版即可）
- 关键特征（发色、服装、配饰）必须每 clip 重复
- 语气可以变，外貌不能变

### 维度5：动态连贯性 (Temporal Coherence)

相邻 clip 之间的动作衔接：

| 衔接类型 | 指令 |
|---------|------|
| 延续动作 | "continuing her graceful turn from the previous moment" |
| 情绪转变 | "her expression shifts from wonder to quiet contentment" |
| 位置移动 | "having moved from the center to the edge of the frame" |
| 时间流逝 | "a moment later, petals have settled around her feet" |

## Prompt 构建模板

### 标准模板（每个 clip 必用）

```
[角色锚点: Chloe, long black hair with pink tips, white floral dress, cherry blossom hairpin]

[运镜] tracking shot following [角色] as she [动作] through [场景].

[主体动作] She [大动作], her [身体部位] [微动作]. 

[表情] [表情指令库中的具体描述].

[场景/氛围] [场景细节], [光影], [色调].

[动态连贯] [与上一个clip的衔接].

 cinematic quality, 4K, shallow depth of field, natural motion blur, film grain
```

### 实例：修复 Scene 8-1（从黑暗升起）

**Before（僵硬版）：**
> "Slowly rising from deep darkness, a dim silhouette of a young woman emerges..."

**After（灵动版）：**
> "Chloe, a young woman with long flowing black hair tipped in soft pink, wearing an ethereal white floral dress, her cherry blossom hairpin catching the first rays of light. Slow crane-up shot: she lifts her chin slowly, eyes opening with quiet wonder as warm golden light begins to illuminate her face from below. Her fingers uncurl gracefully at her sides, shoulders relaxing as if releasing a deep breath she's been holding. Her lips part slightly, a soft expression of dawning hope crossing her features. Darkness gently dissolves around her like morning mist. Cinematic chiaroscuro, warm amber and gold palette, 4K, shallow depth of field, natural motion blur."

## 模型特定优化

### doubao-seedance-1-5-pro
- ✅ 支持首帧/尾帧参考图 → 用角色一致性最强的帧作为首帧
- ⚠️ 动作描述不要太复杂，一个核心动作 + 一个表情即可
- 💡 关键词权重：`graceful` > `smooth` > `natural` > `fluid`

### sora-2
- ✅ 支持较长 prompt → 可以详细描述动作序列
- ⚠️ 角色一致性较弱 → 每次都要完整描述外貌
- 💡 运镜指令效果好，多用具体 camera movement

### kling 系列
- ✅ 人物动作生成强 → 动作描述可以大胆
- ⚠️ 表情细节弱 → 用光影和角度弥补
- 💡 `close-up` + `soft lighting` = 表情感

## 质量检查清单

生成后逐条检查：
- [ ] 角色表情是否有变化？（不是木偶脸）
- [ ] 肢体是否有自然动作？（不是站桩）
- [ ] 运镜是否和角色配合？（不是纯camera运动）
- [ ] 与上一clip是否有动作连贯性？
- [ ] 角色外貌是否一致？
- [ ] 整体氛围是否契合音乐情绪？

## 脚本

### `scripts/generate_cinematic_prompt.sh`
输入：场景描述 + 角色卡 + 上下文 → 输出：优化后的 prompt

### `scripts/quality_check.py`
输入：生成的 mp4 → 输出：质量评分（运动量/表情变化/连贯性）

---

## 与其他 Skill 协作

```
cinematic-video-gen (prompt增强 + 口型歌词)
  → qingyun-api / video_generate (实际生成)
  → video-lyrics-subtitle (字幕生成 + 烧录)
  → lyrics-video-sync (歌词卡点匹配)
  → ffmpeg-video-editor (后期合成)
  → av-sync-workflow (音视频节拍同步)
```

---

## 🎬 完整 MV 生成 Workflow（端到端）

> 以下是一首 MV 从零到成片的完整 pipeline，所有步骤使用现有 skill 工具链。

### 输入素材准备

所有素材存放在规范目录结构中：

```
~/clawd/projects/MediaClaw/output/<project-name>/
├── lyrics/lyrics.txt              # 歌词原文
├── audio/song_final.mp3           # 最终版音频
├── script/mv_script.json          # MV脚本（场景+镜头列表）
├── frames/                        # 参考帧图片
│   ├── 01_first.png               # 每个场景的首帧
│   ├── 01_last.png                # 每个场景的尾帧
│   └── ...
└── script/chloe-card.json         # 角色卡
```

### Step 1: 歌词时间轴生成

**工具**: `video-lyrics-subtitle`

```bash
python3 ~/clawd/skills/video-lyrics-subtitle/scripts/generate_srt.py \
  lyrics/lyrics.txt \
  --audio audio/song_final.mp3 \
  -o subtitles/lyrics.srt
```

输出：每句歌词的精确起止时间（SRT 格式）

### Step 1.5: Phase 音频/字幕分段提取

> **⚠️ 关键步骤！确保歌词/音频/视频三者同步。**
> 跳过此步骤将导致：音频从头播放、字幕时间轴错位、视频和音频完全不对齐。

根据 `edit_plan.json` 中每个 Phase 的时间范围，从完整素材中截取对应的分段：

```bash
python3 ~/clawd/projects/MediaClaw/skills/cinematic-video-gen/scripts/extract_phase.py \
  --audio audio/song_final.mp3 \
  --srt subtitles/lyrics.srt \
  --start 208.0 \
  --end 237.0 \
  --phase 1 \
  --outdir .
```

输出：
- `audio/phaseN_audio.m4a` — 分段音频（精确对应视频时间范围）
- `subtitles/phaseN_lyrics.srt` — 分段字幕（时间轴从 `00:00:00,000` 开始）
- `lyrics/phaseN_lyrics.txt` — 歌词文本片段

**SRT 时间轴重置逻辑：**
- 遍历 SRT 所有条目，保留与 Phase 时间范围重叠的条目
- 裁剪部分重叠条目的起止时间到 Phase 范围内
- 所有时间减去 Phase 起始偏移量（如 -208.0s），使从 `00:00:00,000` 开始

### Step 2: 场景×歌词映射

**工具**: `lyrics-video-sync`

将 MV 脚本中的场景/镜头与歌词时间轴对齐，确定：
- 每个 clip 对应哪句歌词
- 纯音乐段、间奏段的划分
- 每个 clip 的时间范围

输出：`edit_plan.json`（每clip的歌词+时间+场景）

### Step 3: Prompt 组装（六维增强 + 口型）

**工具**: `cinematic-video-gen` (本 skill)

对每个 clip，自动读取：
1. **角色锚点** — 从角色卡提取固定外貌描述
2. **首帧参考图** — `frames/XX_first.png`
3. **运镜 + 动作 + 表情** — 从 MV 脚本场景描述 + 词库匹配
4. **歌词口型** — 从 edit_plan.json 读取对应歌词行
5. **场景氛围** — 光影、色调、背景
6. **动态连贯** — 与上一个 clip 的衔接指令

输出：每个 clip 的完整 prompt

### Step 4: 视频生成（首帧参考）

**工具**: `qingyun-api` (doubao-seedance)

```bash
python3 ~/clawd/skills/qingyun-api/scripts/qingyun-video-doubao-local.py \
  --prompt "<Step 3 生成的完整prompt>" \
  --first-frame frames/01_first.png \
  --model doubao-seedance-1-5-pro-251215 \
  --output video/clips/01_scene1.mp4
```

关键：`--first-frame` 确保角色一致性（base64 本地文件）

每个 clip 约 5 秒，按场景依次生成。

### Step 5: 字幕文件生成

**工具**: `video-lyrics-subtitle`

```bash
# SRT → ASS（KTV 高亮效果）
python3 ~/clawd/skills/video-lyrics-subtitle/scripts/generate_ass.py \
  subtitles/lyrics.srt \
  --style ktv \
  -o subtitles/lyrics.ass
```

### Step 6: 编译合成（⚠️ 使用分段素材！）

**工具**: `ffmpeg-video-editor` + `video-lyrics-subtitle`

> **🔴 必须使用 Step 1.5 提取的分段素材，不是完整音频/字幕！**
> - ✅ 用 `audio/phaseN_audio.m4a`（分段音频）
> - ❌ 不要用 `audio/song_final.mp3`（完整音频）
> - ✅ 用 `subtitles/phaseN_lyrics.srt`（分段字幕，从 00:00 开始）
> - ❌ 不要用 `subtitles/lyrics.srt`（完整字幕）

```bash
# 6a. FFmpeg xfade 拼接所有 clips + 分段音频 → 无字幕版
~/tools/ffmpeg -i clip1.mp4 -i clip2.mp4 ... \
  -i audio/phase1_audio.m4a \
  -filter_complex "xfade chain..." \
  -map "[vout]" -map N:a \
  video/phase1_raw.mp4

# 6b. 生成分段 ASS 字幕（从分段 SRT 转换）
python3 ~/clawd/skills/video-lyrics-subtitle/scripts/generate_ass.py \
  subtitles/phase1_lyrics.srt \
  --style ktv \
  -o subtitles/phase1_lyrics.ass

# 6c. 用 skill 脚本烧录字幕 → 最终成片
bash ~/clawd/skills/video-lyrics-subtitle/scripts/burn_subtitles.sh \
  video/phase1_raw.mp4 \
  subtitles/phase1_lyrics.ass \
  video/phase1_final.mp4
```

### 全流程速查图

```
lyrics.txt + song.mp3
       ↓
  [Step 1] generate_srt.py → lyrics.srt (歌词时间轴)
       ↓
  [Step 1.5] extract_phase.py → phaseN_audio.m4a + phaseN_lyrics.srt + phaseN_lyrics.txt
       ↓
  [Step 2] lyrics-video-sync → edit_plan.json (场景×歌词映射)
       ↓
  [Step 3] cinematic-video-gen → 6维prompt (含口型歌词指令)
       ↓
  [Step 4] qingyun-video-doubao-local.py → clips/*.mp4 (首帧参考生成)
       ↓
  [Step 5] generate_ass.py → phaseN_lyrics.ass (从分段SRT转换)
       ↓
  [Step 6a] FFmpeg xfade → phaseN_raw.mp4 (拼接 + 分段音频)
       ↓
  [Step 6b] burn_subtitles.sh → phaseN_final.mp4 (烧录分段字幕)
       ↓
  🎬 最终成片 (歌词/音频/视频三者严格同步)
```

### 生成后质量检查

每个 clip 生成后立即检查：
- [ ] 角色外貌是否与参考帧一致？
- [ ] 表情是否有变化（不是木偶脸）？
- [ ] 肢体是否有自然运动？
- [ ] 歌唱时嘴巴是否有动作？
- [ ] 与上一个 clip 动作是否连贯？
- [ ] 整体氛围是否契合音乐？

不达标 → 调整 prompt 重生成（同一 clip 最多重试 3 次）

### 模型 fallback 顺序

```
1. doubao-seedance-1-5-pro-251215  ← 首选，支持首帧参考
2. kling (xingjiabiapi)            ← 备选，动作生成强
3. veo3.1 (Google AI Studio)       ← 备选，质量高但渠道不稳定
```

## 🔴 维度6：口型歌词指令 (Lip-Sync Lyrics)

### 问题
AI视频生成时角色唱歌但嘴巴不动，没有对上歌词，看起来像假唱。

### 解决方案：将歌词片段嵌入 prompt

每个 clip 的 prompt 必须包含对应时间段的**歌词文本+口型描述**：

```
[角色锚点 + 运镜 + 动作 + 表情]

She is singing the lyrics: "桜が散る季節に" (在樱花飘落的季节)
Her mouth forms each syllable naturally, lips moving gracefully with the melody.
She sings with emotion, her voice carrying the weight of the words.

[场景/氛围 + 质量后缀]
```

### 口型描述词库

| 歌唱状态 | 英文指令 |
|---------|----------|
| 正常演唱 | "singing softly, lips forming each syllable with gentle precision" |
| 高音爆发 | "belting out a powerful note, mouth open wide, jaw dropped slightly" |
| 气声轻唱 | "singing in a breathy whisper, lips barely parting, intimate and close" |
| 停顿换气 | "a brief pause, catching her breath, lips closing softly before the next phrase" |
| 情感爆发 | "voice cracking with emotion, singing through tears, raw and vulnerable" |
| 吟唱/哼鸣 | "humming softly with closed lips, a gentle melody vibrating through her" |

### 歌词→时间轴匹配规则

每个 clip 的时间范围必须在 `lyrics.json` 中找到对应歌词行，然后：

1. **有歌词** → prompt 中写入 `She is singing: "[原文]" ([中文翻译])`
2. **纯音乐段** → prompt 中写入 `She moves gracefully to the music, no singing in this moment`
3. **换气/间奏** → prompt 中写入 `Between phrases, she takes a breath, a moment of quiet before the next note`

### Prompt 模板（完整版）

```
[Character: Chloe, long black hair with pink tips, white floral dress, cherry blossom hairpin]

[运镜] shot of [Chloe] as she [动作] through [场景].

[主体动作] She [大动作], her [身体部位] [微动作].

[表情] [表情指令].

[歌唱] She is singing: "[对应歌词原文]" ([中文翻译]).
Her lips form each syllable naturally, [口型状态描述].
She pours emotion into every word, [情感力度].

[场景/氛围] [场景细节], [光影], [色调].

[动态连贯] [与上一个clip的衔接].

cinematic quality, 4K, shallow depth of field, natural motion blur, film grain
```

### 实例：Scene 9-1 带歌词版

```
[Character: Chloe, long black hair with pink tips, white floral dress, cherry blossom hairpin]

Slow dissolve shot: Chloe's silhouette gradually transforms into floating cherry blossom petals.
She is singing the final line: "桜が散る季節に、また逢いましょう" (在樱花飘落的季节，我们再相见)
Her lips softly form each syllable as her body dissolves, singing with bittersweet acceptance.
A gentle smile plays on her face even as she fades, eyes glistening with unshed tears.
The last words linger in the air as petals carry her voice away.
Warm golden light, soft pink and white palette, dreamy atmosphere.
Transitioning from the previous aerial dawn shot into this ethereal dissolution.
cinematic quality, 4K, shallow depth of field, natural motion blur, film grain
```

### 自动化 Pipeline

```
lyrics-video-sync (歌词时间轴)
  → cinematic-video-gen (生成带歌词的prompt)
  → qingyun-video-doubao-local.py (首帧参考 + prompt生成视频)
  → ffmpeg-video-editor (合成 + 音频混合)
```

当 `lyrics-video-sync` 输出 edit_plan.json 后，
`cinematic-video-gen` 自动读取每个 clip 对应的歌词行，
生成完整 prompt（含口型指令），然后送入视频生成 API。

*创建日期: 2026-04-10*
*更新日期: 2026-04-10 — 新增维度6：口型歌词指令*
