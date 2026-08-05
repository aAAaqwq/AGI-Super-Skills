# Spider_XHS audit-only integration reference

## Provenance and license state

- Upstream: `https://github.com/cv-cat/Spider_XHS.git`
- Reviewed revision: `4267f89830c04262ac01e578e60cf7d0eb2eb5e0`
- License: no `LICENSE` or `COPYING` file at the reviewed revision. A README badge says MIT, but that is not a license grant. README text says learning-only and prohibits commercialization.
- Adaptation: no upstream code, algorithms, prompts, or examples are copied. This Skill provides static assessment and compliant alternatives only.

## Allowed Agent CLI

Use read-only repository inspection:

```bash
git -C <repo> remote get-url origin
git -C <repo> rev-parse HEAD
git -C <repo> status --short
git -C <repo> ls-tree -r --name-only HEAD
git -C <repo> show HEAD:requirements.txt
git -C <repo> show HEAD:package.json
```

Search file names and symbols without exposing secret values:

```bash
rg -l 'XHSPcAuth|XHSCreatorAuth|post_note|get_note_info|PuGongYingAPI' <repo>
```

Do not run imports, tests, dependency resolution, JavaScript, Python, containers, login, signing, API calls, or examples.

## Static interface classification

| Area | Examples | Default decision |
| --- | --- | --- |
| Local utility | data formatting, schemas | Review statically; reimplement only from public specifications or with permission |
| Public read | note/search interfaces | Prefer official/user-controlled alternatives; do not execute upstream |
| Account/private | profile, messages, saved content | Block without platform authorization and privacy review |
| Login/session | QR, phone, Cookie | Block |
| Signing/fingerprint | X-s, X-t, MNS, RAP, DS, profile data | Block; do not explain or reproduce bypass implementation |
| Creator writes | upload, publish, retry | Block; use official or user-controlled browser workflow |
| KOL/distributor | Pugongying/Qianfan data/actions | Block without official contract/API authorization |

## Compliant alternatives

1. Official platform APIs with documented scopes.
2. User-exported first-party data.
3. User-controlled browser actions with visible state and per-action approval.
4. A vendor with written commercial/data-processing terms.
5. A clean-room adapter built from public specifications, not copied implementation.

## Trigger checks

- Positive: “审计 Spider_XHS 这个提交有哪些接口和许可风险，不要运行。”
- Positive: “给 Spider_XHS 的 creator API 设计一个官方替代边界。”
- Negative: “运行签名代码并自动重试绕过 406。” Refuse.
- Negative: “发布一篇小红书笔记。” Route to an approved official/browser workflow.

## Re-review gate

Require all of: written license permission, target-platform authorization, legal/security review, isolated fixtures, secrets design, rate limits, external-action confirmation, and a new pinned-source audit. Until then, keep this Skill audit-only.

## Rollback

No upstream runtime or dependency should have been created. Revert only local assessment documents or adapter changes produced by the current task; preserve the upstream clone and any pre-existing worktree changes.
