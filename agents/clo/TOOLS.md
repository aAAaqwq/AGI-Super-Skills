# TOOLS.md — CLO

_非穷尽使用笔记；`config/team-manifest.json` 是 assignment authority。_

## Workspace 目录索引

| 路径 | 说明 |
|------|------|
| ../../skills/ | AGI Super Team 技能库 |
| ./scripts/ | 工具脚本（newsbot_send.py, model-health-check.sh 等）|
| ./workspace/content-pipeline/ | 内容管线（drafts, hotpool, topics）|
| ./projects/ | 项目（MediaClaw, super-quant-claw）|
| ./reports/ | 报告输出 |
| ./repos/awesome-skills/ | 111 个社区 skills |
| ./repos/AGI-Super-Team/ | 团队配置 |

## 推荐 Skills

### ../../skills/ (仓库)

- **contract-review**: Legal contract analysis using CUAD dataset (41 risk categories). Supports NDA, SaaS, M&A, employment, payment/merchant, and finder/broker agreements.
- **gdpr-dsgvo-expert**: GDPR and German DSGVO compliance automation. Scans codebases for privacy risks, generates DPIA documentation, tracks data subject rights requests.
- **tianyancha-cn**: 企业信息查询 - 天眼查/企查查/爱企查数据查询（Bloomberg 终端中国版）
- **auth-manager**: 网页登录态管理；仅在对应 Harness Adapter 明确支持时使用其浏览器会话能力。
- **browser-login-monitor**: 浏览器登录安全监控——监测浏览器会话状态与登录安全
- **healthcare-monitor**: 医疗行业企业融资监控系统。实时监控医疗健康企业的工商变更，识别融资信号。
- **email-manager**: 多邮箱统一管理与智能助手。支持 Gmail、QQ邮箱等 IMAP 邮箱。
- **docusign-automation**: Automate DocuSign tasks via Rube MCP: templates, envelopes, signatures, document management.
