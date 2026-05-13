# Kanxiang (Physiognomy Skill)
> *"Appearance reflects the heart, destiny is shaped by oneself. Facial features, palm lines, bone structure, and body form are all manifestations of life's trajectory."*

**Ancient wisdom of physiognomy, reflecting millennia of insight**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Claude Code](https://img.shields.io/badge/Claude%20Code-Skill-blueviolet)](https://claude.ai/code)
[![AgentSkills](https://img.shields.io/badge/AgentSkills-Standard-green)](https://agentskills.io)

**Language**：[English](README_EN.md) | [简体中文](README.md)

An image analysis skill based on traditional Chinese physiognomy, supporting four major categories: facial reading (Mianxiang), palmistry (Shouxiang), bone structure reading (Guxiang), and body physiognomy (Tixiang).

⚠️ **This analysis is for cultural reference and entertainment only. Modern science has not reached a consensus on the predictive ability of physiognomy.**

[Features](#features) · [Examples](#examples) · [Knowledge Sources](#knowledge-sources) · [Important Notes](#important-notes)

---

## Installation

### Claude Code
> **Important**: Claude Code looks for skills in `.claude/skills/` from the **git repository root**. Execute in the correct location.

```bash
# Install to current project (execute in git repository root)
mkdir -p .claude/skills
git clone https://github.com/yourusername/kanxiang .claude/skills/kanxiang

# Or install globally (available for all projects)
git clone https://github.com/yourusername/kanxiang ~/.claude/skills/kanxiang
```

### Requirements
- **Claude Code**: Free installation, requires Node.js 18+ ([Installation Guide](https://docs.anthropic.com/en/docs/claude-code))
- **Visual Analysis**: Requires a model with vision capabilities (e.g., Claude 4.6 Sonnet)
- **API Usage**: Each analysis consumes approximately 2k-5k tokens, depending on photo complexity and analysis depth
- **Payment Options** (choose one):
  - Claude Pro / Max Subscription: Use within subscription quota, no additional setup needed
  - Anthropic API Key: Pay-as-you-go, configure key in Claude Code

---

## Usage

### Basic Usage

1. **Upload a photo and specify analysis type**:
   ```
   Help me analyze this face reading [upload photo]
   ```

2. **Or simply upload a photo directly**:
   ```
   [Upload photo]
   The skill will automatically recognize the photo type and perform analysis
   ```

### Supported Analysis Types

| Type | Description | Photo Requirements |
|------|-------------|-------------------|
| **Face Reading** | Analyze features, three courts, twelve palaces, complexion | Front or side face photo |
| **Palmistry** | Analyze palm lines, finger shapes, mounts, coloration | Palm front photo |
| **Bone Reading** | Analyze skull, body bones, nine bone structures | Photo showing bone contours |
| **Body Physiognomy** | Analyze body type, posture, temperament | Full-body or half-body photo |

---

## Examples

### Example 1: Face Reading Analysis

> Input: `Help me analyze this face reading [upload face photo]`

**Scenario 1: Personality Analysis**
```
User ❯ Help me analyze this face reading
[Upload face photo]

Kanxiang Skill ❯ # Physiognomy Analysis Report

## Basic Information
- **Type**: Face Reading (Mianxiang)
- **Analysis Date**: 2026-04-19

## Feature Recognition
- Balanced three courts proportion, full and broad forehead
- Thick and neat eyebrows, gentle eyes
- Straight nose bridge, moderate nasal wings
- Clear lip contours, naturally upturned mouth corners

## Personality Traits
- Dominant personality: Externally gentle, internally determined
- Strengths: Steady and reliable, thoughtful, decisive
- Weaknesses: Occasionally overly cautious, may miss opportunities

## Ability Tendencies
- Strengths: Management, planning, analytical work
- Suitable careers: Corporate executives, project managers, analysts
```

**Scenario 2: Fortune Analysis**
```
User ❯ How is my recent fortune?

Kanxiang Skill ❯ ## Fortune Analysis

### Recent Fortune (Next 1-2 Years)
- **Career**: ⭐⭐⭐⭐ Steady rise, helpful people
- **Wealth**: ⭐⭐⭐ Stable regular income, average windfall luck
- **Relationship**: ⭐⭐⭐⭐ Strong romantic luck, likely to find true love

### Notes
- Second half of this year (July-September): Pay attention to communication, avoid misunderstandings
- Spring next year (March-May): Important career opportunities
```

---

### Example 2: Palmistry Analysis

> Input: `Analyze my palmistry [upload palm photo]`

```
User ❯ How is my palmistry?
[Upload palm photo]

Kanxiang Skill ❯ # Physiognomy Analysis Report

## Basic Information
- **Type**: Palmistry (Shouxiang)
- **Analysis Date**: 2026-04-19

## Feature Recognition
- **Life Line**: Deep, long, and clear, encircling the thumb base
- **Head Line**: Extends straight to the palm side, forked at the end
- **Heart Line**: Gracefully curved, ending between index and middle fingers
- **Fate Line**: Extends upward from the wrist, slightly interrupted midway

## Personality Traits
- **Life Line characteristics**: Energetic, strong vitality, maintain health
- **Head Line characteristics**: Strong logical thinking, rational and pragmatic, suitable for technical work
- **Heart Line characteristics**: Emotionally rich but rational, seeking stable relationships
- **Fate Line characteristics**: Life trajectory has ups and downs, stabilizes after middle age

## Ability Tendencies
- Strengths: Technology, engineering, logical analysis
- Suitable careers: Engineer, programmer, researcher
```

---

### Example 3: Body Physiognomy Analysis

> Input: `Help me analyze this photo [upload full-body photo]`

```
User ❯ Help me analyze this photo
[Upload full-body photo]

Kanxiang Skill ❯ # Physiognomy Analysis Report

## Basic Information
- **Type**: Body Physiognomy (Tixiang)
- **Analysis Date**: 2026-04-19

## Feature Recognition
- **Body Type**: Medium build, well-proportioned
- **Posture**: Upright standing, level shoulders, straight back
- **Temperament**: Calm and reserved, confident and composed

## Personality Traits
- **Main characteristic**: Strong self-discipline, focused on self-management
- **Strengths**: Steady and reliable, responsible, trustworthy
- **Weaknesses**: Slightly reserved, sometimes overly serious

## Ability Tendencies
- Strengths: Management, education, professional services
- Suitable careers: Teacher, manager, consultant

## Health Notes
- Upright posture, good skeletal structure
- Maintain moderate exercise, avoid prolonged sitting
- Recommend flexibility training
```

---

## Features

### Supported Physiognomy Types

| Type | Analysis Dimensions | Source Materials |
|------|-------------------|------------------|
| **Face Reading** | Features, three courts, twelve palaces, complexion, bones | "Mayi Shenxiang", "Lizhuang Xiangfa", "Shenxiang Quanbian" |
| **Palmistry** | Palm lines, finger shapes, mounts, coloration, patterns | "Shenxiang Quanbian", "Shuijing Shenxiang" |
| **Bone Reading** | Skull, body bones, nine bone structures | "Taiqing Shenjian", "Renlu Datong Fu" |
| **Body Physiognomy** | Body type, posture, temperament, gait | "Bingjian", "Shenxiang Quanbian" |

### Analysis Report Structure

Each analysis report includes:

1. **Basic Information**: Physiognomy type, analysis date
2. **Feature Recognition**: Key features identified from the photo
3. **Personality Traits**: Main personality tendencies, strengths and weaknesses
4. **Ability Tendencies**: Strengths, suitable careers
5. **Fortune Analysis**: Time-based or dimension-based fortune analysis
6. **Health Notes**: Health-related observations and suggestions
7. **Development Suggestions**: Practical advice based on physiognomy analysis

### Technical Principle

```
Upload photo → Identify image type → Access rule base → Extract features → Comprehensive analysis → Generate report
```

1. **Identify image type**: Automatically determine if it's face/palm/bone/body
2. **Access rule base**: Read corresponding physiognomy rule file (based on classic texts)
3. **Extract features**: Use vision analysis tools to extract key features
4. **Comprehensive analysis**: Multi-dimensional analysis combining rule knowledge
5. **Generate report**: Output structured analysis report with disclaimer

---

## Knowledge Sources

This skill's rule knowledge base is compiled from the following classic physiognomy texts:

| Classic | Author/Dynasty | Main Content |
|---------|----------------|--------------|
| **"Mayi Shenxiang" (麻衣神相)** | Mayi Taoist (Northern Song) | Foundational work of face reading, systematic face reading theory |
| **"Lizhuang Xiangfa" (柳庄相法)** | Yuan Yong (Early Ming) | Rich practical cases, focused on practical application |
| **"Shenxiang Quanbian" (神相全编)** | Yuan Zhongche (Ming Dynasty) | Comprehensive collection of physiognomy, covering face, palm, and bone reading |
| **"Shuijing Shenxiang" (水镜神相)** | Fan Li (attributed) | Concise and practical, suitable for beginners |
| **"Bingjian" (冰鉴)** | Zeng Guofan (Qing Dynasty) | Person observation art, focused on temperament and talent |
| **"Taiqing Shenjian" (太清神鉴)** | Anonymous (Song Dynasty) | Bone structure and complexion, integrating form and spirit |
| **"Renlu Datong Fu" (人伦大统赋)** | Anonymous (Jin-Yuan Dynasty) | Verse-style physiognomy, facilitating memory and transmission |

---

## Project Structure

This project follows the [AgentSkills](https://agentskills.io) open standard:

```
kanxiang/
├── SKILL.md           # Skill entry (official frontmatter)
├── README.md          # This file
└── references/         # Rule knowledge base
    ├── mianxiang.md   # Face reading rules (based on "Mayi Shenxiang", etc.)
    ├── shouxiang.md   # Palmistry rules (based on "Shenxiang Quanbian", etc.)
    ├── guxiang.md     # Bone reading rules (based on "Taiqing Shenjian", etc.)
    └── tixiang.md     # Body physiognomy rules (based on "Bingjian", etc.)
```

---

## Important Notes

### ⚠️ Important Reminders

- **This analysis is for cultural reference and entertainment only**: Physiognomy is traditional culture; modern science has not confirmed its predictive ability
- **Please view rationally**: Life path depends primarily on personal effort and choices
- **No absolute assertions**: All analyses are probabilistic references, not absolute destiny
- **Health notes are for reference only**: Consult professional doctors for health issues

### 📋 Usage Limitations

- No prediction of specific events (e.g., "when will I get married", "when will I get rich")
- No politically sensitive topics
- No promotion of superstition
- Each analysis report includes a disclaimer at the end

### 📷 Photo Requirements

- **Clarity**: Photos should be clear and visible, avoid blur or obstruction
- **Lighting**: Avoid overly dim lighting or direct strong light
- **Angle**: Front view is best, side view can also be analyzed
- **Privacy**: Do not upload photos containing others' privacy

---

## FAQ

### Q: Is the analysis accurate?
**A**: Physiognomy is part of traditional culture and can be used as a reference, but should not be superstitious. Modern science has not reached a consensus on the predictive ability of physiognomy. It is recommended to treat analysis results as entertainment and cultural reference, and view them rationally.

### Q: What types of photos can I upload?
**A**: Supports human body part photos, including face, palm, full body, etc. Photos should be clear and visible, avoiding blur, obstruction, overly dim lighting, etc.

### Q: How long does analysis take?
**A**: Typically completed within a few seconds to十几 seconds.

### Q: Can I upload photos for analysis multiple times?
**A**: Yes. Each analysis is independent, and you can upload different photos for analysis multiple times.

### Q: Will analysis results be saved?
**A**: No. Each analysis is real-time and does not save your photos or analysis results.

### Q: What physiognomy types are supported?
**A**: Currently supports four major categories: face reading, palmistry, bone reading, and body physiognomy. More types may be added in the future.

---

## Version History

### v1.0.0 (2026-04-19)
- Initial release
- Supports four major analysis categories: face, palm, bone, body
- Rule knowledge base compiled from seven classic physiognomy texts
- Complete analysis report structure
- Automatic photo type recognition

---

## Concluding Thoughts

Physiognomy is the crystallization of ancient wisdom in observing humans and nature.

It is not superstition, but a systematic summary of experience. From face reading to personality, palmistry to tendencies, bone reading to life patterns, body physiognomy to temperament—these are our ancestors' ways of understanding the complex system that is "human".

Of course, modern science tells us that destiny is never written on appearance.

Your personality, abilities, and fortune depend more on your choices, efforts, and encounters. Physiognomy analysis can serve as an interesting reference, a window to understand the charm of traditional culture, but it is never a life compass.

True "appearance transformation" lies not in external decoration, but in inner cultivation.

As "Bingjian" says: "The spirit of the whole body is embodied in the two eyes; the bone structure of the whole body is revealed in the face." Spirit and temperament are the ultimate pursuit of physiognomy.

---

MIT License © [timerzz](https://github.com/timerzz/kanxiang)

**Last Updated**: 2026-04-19
**Skill Version**: 1.0.0
