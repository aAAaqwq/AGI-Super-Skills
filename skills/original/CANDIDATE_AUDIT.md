# 原创 Skills 候选审计

审计日期：2026-08-02

本审计用于解释首批原创分类的收录边界。它不替代 `config/skill-provenance.json`；机器索引仍只接受 `project-original + reviewed`。

## 已使用的证据

- 当前正式 provenance 合同中的已审查第一方条目。
- 创建提交 `cecc3e42…` 中明确标记为 self-built 的内容工具与三条自媒体日更链路。
- 创建提交 `02262c4e…` 中的即梦、视频合并和视频号发布链路。
- 历史保守原创清单 `50253254…:skills/docs/original-skills.md`。
- `5minbtc` 的首个创建提交 `aae3f692…` 及后续仓库内迭代历史。
- Binance Square v4 的实现、优化提交和独立验证记录。
- `daniel-x-writer` 的完整个人 Skill 目录、风格样例、长度检查器及本次规范化同步提交。

## 首批结果

- 收录 32 个强证据原创 Skills。
- 明确包含 `binance-square`、`5minbtc`、`daniel-x-writer`、`daily-gzh-content`、`daily-xhs-content`、`daily-douyin-content`。
- 原创目录是索引视图，不复制第二份 Skill 内容；规范源仍为 `skills/<skill-id>/`。

## 暂不晋级的相邻候选

| 候选 | 当前处理 | 原因 |
|---|---|---|
| `btc-5min-scalper` | 待审计 | 与 `5minbtc` 功能相邻，但尚未确认是独立原创、派生版本还是外部收集。 |
| `xhs-content-creator` | 排除 | 目录带外部 registry 来源记录，不能仅凭本地出现或作者提示改写为原创。 |
| `wechat-ai-radar` | 待审计 | 有产品相关性，但缺少创建提交、当前树摘要和明确作者链。 |
| `wechat-article-writer`、`xhs-writing-coach`、`cross-platform-poster` | 待审计 | 曾出现在更宽松的历史手写清单或带作者提示；按当前规则，这些都只是线索。 |
| 旧 Platform / Agent Operations 批次 | 待审计 | 批量添加 `author` 字段不能证明没有上游来源，需逐项核验提交前内容和许可证。 |

新增候选必须先补齐作者、创建提交、许可证、当前树摘要和来源证据，然后由生成器自动进入原创分类。不得手改 `README.md` 或 `index.json` 绕过 provenance。
