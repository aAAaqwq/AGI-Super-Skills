# 🧠 OpenClaw Master Skills

<div align="center">

<a href="https://myclaw.ai">
  <img src="https://img.shields.io/badge/Powered%20by-MyClaw.ai-blue?style=for-the-badge" alt="Powered by MyClaw.ai" />
</a>
<img src="https://img.shields.io/badge/每周更新-green?style=for-the-badge" alt="每周更新" />

**语言：**
[English](README.md) · [中文](README.zh-CN.md) · [Français](README.fr.md) · [Deutsch](README.de.md) · [Русский](README.ru.md) · [日本語](README.ja.md) · [Italiano](README.it.md) · [Español](README.es.md)

</div>

---

## 🤖 由 [MyClaw.ai](https://myclaw.ai) 驱动

**[MyClaw.ai](https://myclaw.ai)** 是一个 AI 个人助手平台，为每位用户提供运行在独立服务器上的全功能 AI Agent。OpenClaw Master Skills 是我们精心策划、每周更新的优质 Skills 合集——从整个生态系统中精挑细选，帮助你的 AI Agent 做更多事。

> 🌐 **体验 MyClaw.ai**：[https://myclaw.ai](https://myclaw.ai)

---

## 🚀 安装方式

```bash
# 通过 ClaWHub 安装单个 skill
clawhub install openclaw-master-skills

# 或 clone 后手动复制
git clone https://github.com/LeoYeAI/openclaw-master-skills.git
cp -r openclaw-master-skills/skills/<skill-name> ~/.openclaw/workspace/skills/
```

## 📦 Skills 目录

| Skill | 说明 | 分类 | 来源 | 收录时间 |
|---|---|---|---|---|
| [`openclaw-guardian`](skills/openclaw-guardian/) | 🛡️ Gateway watchdog — auto-monitor, self-repair via `doctor --fix`, git rollback, daily snapshots, Discord alerts. Built by MyClaw.ai | DevOps | [GitHub](https://github.com/LeoYeAI/openclaw-guardian) | 2026-03-02 |

> 每周一新增。[提交你的 Skill →](../../issues/new?template=submit-skill.md)

---

## 📬 提交 Skill

[提交 Issue](../../issues/new?template=submit-skill.md) 或直接提交 Pull Request，将你的 skill 文件夹放在 `skills/` 目录下。

**审核标准：** 有效的 `SKILL.md` · 用途明确 · 无硬编码凭证 · 在标准 OpenClaw 环境可用

## 📅 每周更新

详见 [CHANGELOG.md](CHANGELOG.md)，每周一更新。

## 🔍 收集来源

每周脚本自动扫描：
- **[skills.sh](https://skills.sh)** — 排行榜 Top Skills
- **GitHub** — 带 `openclaw-skill` 标签的仓库
- **[ClaWHub](https://clawhub.ai)** — 最新发布的 Skills

经验证、测试后自动合并推送。

## 许可证

MIT © [MyClaw.ai](https://myclaw.ai)
