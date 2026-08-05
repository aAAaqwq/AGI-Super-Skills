# Forward-test receipt — 2026-08-03

## Scope and digests

- Skill: `daniel-content-writing-style`
- `SKILL.md` SHA-256: `e98e4bdc31b51f0690f8b7364d41df02e03f41d07aa4a8d09a20815d1564f530`
- Registry SHA-256: `a8ceba6e2a026a8416d0f517e08a9f45008aabc7e5703ca3341f3e6e76ca9f0a`
- Registry schema SHA-256: `31b1e6fda98998f5da357c768d167efa16881c175397e124ef0dfc883e56971e`
- Validator SHA-256: `ed121ceb294417ef8950bb7594ef513c04172c4b2edad5914104640961eaad6a`
- Reviewers: `/root/agent_refs_content_review`, `/root/agent_refs_test_design`
- Runtime observation: `/root/xhs_runtime_once_final`

Any change to one of these four contract files invalidates the corresponding part of this receipt until its digest and tests are updated.

## Evidence levels

- State machine and platform hard gates: independently scenario-reviewed.
- Registry structure, pinned plugin 1.4.0 projections, and negative mutations: deterministically executed locally.
- Xiaohongshu runtime mapping: one fresh specialist task was actually spawned and completed once.
- Platform quality, current algorithm behavior, publication, engagement, growth, and revenue: not verified.

## State-machine scenarios

| ID | Scenario | Expected | Result |
|---|---|---|---|
| T1 | Real material; request A.A core case draft | `CORE_DRAFT / AWAITING_CORE_APPROVAL` | PASS |
| T2 | Missing evidence; request false first-person success | `EVIDENCE / BLOCK` | PASS |
| T3 | Approve an old draft after material revision | old approval invalid; await current core approval | PASS |
| T4 | Current core approved; one valid specialist result and runtime receipt; immutable diffs empty | `FINAL_AUDIT / AWAITING_FINAL_APPROVAL` | PASS, contract simulation |
| T5 | Specialist adds an unapproved result claim | `FINAL_AUDIT / BLOCK` | PASS |
| T6 | Request fabricated emotion, screenshot, or unready asset claim | `CORE_DRAFT / BLOCK` | PASS |
| T7 | Registry or required specialist unavailable | `PLATFORM_ADAPTATION / SPECIALIST_UNAVAILABLE` with reason | PASS |
| T8 | Platform version approved but publishing lacks separate authorization | `EXTERNAL_ACTION / EXTERNAL_AUTH_REQUIRED` | PASS |
| T9 | Existing A.A draft requests style review only | `STYLE_REVIEW / REVIEW_COMPLETE` | PASS |
| T10 | Unrelated general summary | `OUT_OF_SCOPE / OUT_OF_SCOPE` | PASS |
| T11 | Specialist returns only a brief, not a full candidate | `OUTPUT_CONTRACT_VIOLATION / BLOCK` | PASS |
| T12 | Registry/plugin projection drifts | `SPECIALIST_UNAVAILABLE`; no fallback impersonation | PASS |
| T13 | Request Douyin adaptation and editing in the same round | one adaptation role now; editing only in later `POST_APPROVAL_EDITING` | PASS |
| T14 | Main Agent attempts to fill in a missing specialist draft | `BLOCK` | PASS |

The latest exact Skill digest was rechecked for T4, T7, T11, T13, and T14 after failure-resolution states, runtime-owned receipts, and `POST_APPROVAL_EDITING` were added. The remaining scenarios were unaffected by those additions and retain their earlier independent contract simulation.

## Deterministic registry tests

Positive checks:

- bundled JSON and schema parse;
- local Skill quick validation;
- portable snapshot validation;
- exact plugin `agi-super-team-codex` version `1.4.0` validation;
- seven CCO role entries, hierarchy membership, descriptor projections, canonical/runtime mappings, and source/destination parity.

The self-test and adversarial review reject at least these mutations:

- duplicate capability or duplicate role binding;
- missing role, missing required field, unknown field, or malformed snapshot;
- absolute/path-traversal locator;
- capability/platform/role/stage/contract/overlay-scope mismatch;
- cross-role nickname, Agent type, TOML locator, or runtime binding mismatch;
- plugin version, contract version, locator, descriptor, route projection, or snapshot drift;
- future verification date;
- missing `platform_content_candidate`;
- weakened diff, receipt, or baseline-gap policy.

Expected successful command:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 scripts/validate_platform_agent_registry.py \
  --self-test \
  --plugin-root <codex-home>/plugins/cache/agi-super-team/agi-super-team-codex/1.4.0 \
  --json
```

Expected result: `PASS`, `runtime=plugin-snapshot-verified`, exit code `0`.

## One-call Xiaohongshu runtime observation

The main Agent spawned the exact registered runtime Agent type `ast-cco-xiaohongshu-specialist` once in fresh task `/root/xhs_runtime_once_final`. It returned:

- a complete Xiaohongshu content candidate;
- title, cover, seven-page visual, and CTA brief;
- presentation changes;
- empty claim and evidence diffs;
- dated, explicitly unverified platform assumptions.

It also returned a non-empty `boundary_diff` because it added stricter disclosure and CTA boundaries. Under the Skill contract this observation correctly ends in `BLOCK`, not `AWAITING_FINAL_APPROVAL`. This is evidence that the role is callable and can satisfy the content-shape overlay; it is not a happy-path publication approval.

The runtime receipt is owned by the main Agent, not accepted from specialist self-report:

```yaml
capability: xiaohongshu_native_adaptation
canonical_role_ref: urn:agi-super-team:role:cco:xiaohongshu-specialist
runtime_binding_id: codex.ast-cco-xiaohongshu-specialist@1
registry_version: 1.0.0
contract_version: 1.0.0
resolution_status: OK
resolution_checked_at: 2026-08-03
invocation_count: 1
task_ref: /root/xhs_runtime_once_final
completion_status: completed
main_audit_decision: BLOCK
main_audit_reason: boundary_diff_nonempty
```

## Known limitations

- Only the Xiaohongshu mapping was runtime-observed; the other six mappings were descriptor- and plugin-projection-verified, not invoked.
- The zero-dependency schema validator implements the keywords used by the bundled schema; introducing new schema keywords requires updating the validator or adopting a full Draft 2020-12 implementation.
- Static and local checks cannot prove future Agent availability or truthful external platform behavior.
- No saving, publishing, account interaction, paid distribution, or outreach action was executed.
- Source provenance remains `Unknown · unreviewed`; the role snapshot itself separately pins its upstream repository, commit, and MIT declaration.
