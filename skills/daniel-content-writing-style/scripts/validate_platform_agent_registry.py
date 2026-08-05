#!/usr/bin/env python3
"""Validate the A.A platform-agent registry without model or network calls."""

from __future__ import annotations

import argparse
import copy
import datetime as dt
import hashlib
import json
import re
import sys
import tomllib
from pathlib import Path
from typing import Any

OK = 0
CONTRACT_ERROR = 1
ENVIRONMENT_ERROR = 2
STALE = 3

EXPECTED_CAPABILITIES = {
    "xiaohongshu_native_adaptation",
    "wechat_official_native_adaptation",
    "douyin_native_adaptation",
    "bilibili_native_adaptation",
    "x_native_adaptation",
    "zhihu_native_adaptation",
    "short_video_editing_guidance",
}

EXPECTED_BINDINGS = {
    "xiaohongshu_native_adaptation": (
        "xiaohongshu-specialist",
        "xiaohongshu",
        "platform_adaptation",
        "platform_native_adaptation@1",
    ),
    "wechat_official_native_adaptation": (
        "wechat-official-account-manager",
        "wechat_official",
        "platform_adaptation",
        "platform_native_adaptation@1",
    ),
    "douyin_native_adaptation": (
        "douyin-strategist",
        "douyin",
        "platform_adaptation",
        "platform_native_adaptation@1",
    ),
    "bilibili_native_adaptation": (
        "bilibili-strategist",
        "bilibili",
        "platform_adaptation",
        "platform_native_adaptation@1",
    ),
    "x_native_adaptation": (
        "twitter-engager",
        "x",
        "platform_adaptation",
        "platform_native_adaptation@1",
    ),
    "zhihu_native_adaptation": (
        "zhihu-strategist",
        "zhihu",
        "platform_adaptation",
        "platform_native_adaptation@1",
    ),
    "short_video_editing_guidance": (
        "short-video-editing-coach",
        "short_video",
        "post_approval_editing",
        "short_video_editing_guidance@1",
    ),
}

EXPECTED_RECEIPT_FIELDS = {
    "capability",
    "canonical_role_ref",
    "runtime_binding_id",
    "registry_version",
    "contract_version",
    "resolution_status",
    "resolution_checked_at",
    "invocation_count",
    "task_ref",
    "completion_status",
}

EXPECTED_CONTRACT_FIELDS = {
    "platform_native_adaptation@1": {
        "inputs": {
            "approved_draft_version",
            "immutable_claims",
            "immutable_evidence",
            "public_boundaries",
            "target_platform",
            "current_date",
            "allowed_presentation_changes",
            "role_required_inputs",
        },
        "outputs": {
            "source_draft_version",
            "platform_content_candidate",
            "platform_adaptation_brief",
            "delegation_receipt",
            "presentation_changes",
            "claim_diff",
            "evidence_diff",
            "boundary_diff",
            "unresolved_questions",
            "dated_platform_assumptions",
        },
        "must_be_empty": {"claim_diff", "evidence_diff", "boundary_diff"},
        "may_be_nonempty": {"presentation_changes"},
    },
    "short_video_editing_guidance@1": {
        "inputs": {
            "approved_platform_version",
            "approved_script",
            "material_manifest",
            "target_platform",
            "duration",
            "technical_specifications",
            "immutable_claims",
            "public_boundaries",
        },
        "outputs": {
            "editing_decision_sheet",
            "timeline_recommendations",
            "subtitle_sound_export_checklist",
            "delegation_receipt",
            "claim_diff",
            "evidence_diff",
            "boundary_diff",
            "unresolved_questions",
        },
        "must_be_empty": {"claim_diff", "evidence_diff", "boundary_diff"},
        "may_be_nonempty": set(),
    },
}

EXPECTED_SNAPSHOT = {
    "package": "agi-super-team-codex",
    "verified_plugin_version": "1.4.0",
    "verified_at": "2026-08-03",
    "max_age_days": 90,
    "plugin_manifest_locator": (
        "plugin:agi-super-team-codex@1.4.0:.codex-plugin/plugin.json"
    ),
    "route_locator": (
        "plugin:agi-super-team-codex@1.4.0:"
        "skills/c-suite-team/references/routes/cco.json"
    ),
    "route_schema_version": 1,
    "route_projection_sha256": (
        "21b33e0933f8ace999fc5d1daf4f827cb5899320e0eb2a0fadb2a243603f7f7a"
    ),
    "hierarchy_locator": (
        "plugin:agi-super-team-codex@1.4.0:"
        "skills/c-suite-team/references/agent-hierarchy.json"
    ),
    "hierarchy_schema_version": 1,
    "hierarchy_projection_sha256": (
        "979f9567187e2a68b4e2b86ea065cd5e5c2f03ae8ca9185d521858055fa73f2e"
    ),
    "upstream_repository": "https://github.com/jnMetaCode/agency-agents-zh",
    "upstream_commit": "2ecfabf8e944ccdfed63ad8c44d5241290af6977",
    "upstream_license": "MIT",
}

EXPECTED_OVERLAY_SCOPES = {
    "xiaohongshu_native_adaptation": (
        "把已批准核心稿改造成完整小红书笔记候选，并附标题、封面和版式 brief；"
        "不负责达人、投放或发布。"
    ),
    "wechat_official_native_adaptation": (
        "把已批准核心稿改造成完整公众号文章候选，并附标题、摘要和图文排版 brief；"
        "不操作公众号后台。"
    ),
    "douyin_native_adaptation": (
        "把已批准核心稿改造成抖音脚本级候选，包括钩子、口播和高层镜头建议；"
        "不承担逐时间点剪辑。"
    ),
    "bilibili_native_adaptation": (
        "把已批准核心稿改造成完整 B 站单期脚本候选，并附章节、社区和复盘 brief；"
        "不上传或发布。"
    ),
    "x_native_adaptation": (
        "把已批准核心稿改造成 X 帖子、线程或回复候选；"
        "不扩展为舆情研究、付费增长或账号操作。"
    ),
    "zhihu_native_adaptation": (
        "把已批准核心稿改造成完整知乎回答候选，并附问题、引用和复用 brief；"
        "不刷赞、引流绕规或发布。"
    ),
    "short_video_editing_guidance": (
        "仅在脚本和素材已批准后生成剪辑决策、时间轴、字幕声音和导出检查；"
        "不得与平台适配同轮调用。"
    ),
}

EXPECTED_BASELINE_POLICIES = {
    "platform_native_adaptation@1": (
        "角色只返回策略、brief 或框架而没有 platform_content_candidate 时，"
        "视为 OUTPUT_CONTRACT_VIOLATION 并 BLOCK；不得由主 Agent 补写冒充专家成稿。"
    ),
    "short_video_editing_guidance@1": (
        "缺少已批准脚本或素材时 NEEDS_INPUT；本合同是后续独立工作流，"
        "不生成平台适配稿。"
    ),
}


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def digest(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def validate_json_schema_subset(
    instance: Any,
    schema: dict[str, Any],
    *,
    root_schema: dict[str, Any] | None = None,
    path: str = "$",
) -> list[str]:
    """Validate the Draft 2020-12 keywords used by this bundled schema."""
    root = root_schema or schema
    issues: list[str] = []

    ref = schema.get("$ref")
    if ref is not None:
        if not isinstance(ref, str) or not ref.startswith("#/"):
            return [f"{path}: unsupported schema reference {ref!r}"]
        target: Any = root
        try:
            for token in ref[2:].split("/"):
                target = target[token.replace("~1", "/").replace("~0", "~")]
        except (KeyError, TypeError):
            return [f"{path}: unresolved schema reference {ref}"]
        if not isinstance(target, dict):
            return [f"{path}: schema reference does not resolve to an object"]
        return validate_json_schema_subset(
            instance, target, root_schema=root, path=path
        )

    expected_type = schema.get("type")
    type_ok = {
        "object": isinstance(instance, dict),
        "array": isinstance(instance, list),
        "string": isinstance(instance, str),
        "integer": isinstance(instance, int) and not isinstance(instance, bool),
        "boolean": isinstance(instance, bool),
    }.get(expected_type, True)
    if not type_ok:
        return [f"{path}: expected {expected_type}, got {type(instance).__name__}"]

    if "const" in schema and instance != schema["const"]:
        issues.append(f"{path}: value does not match const")
    if "enum" in schema and instance not in schema["enum"]:
        issues.append(f"{path}: value is not in enum")

    if isinstance(instance, dict):
        required = schema.get("required", [])
        for key in required:
            if key not in instance:
                issues.append(f"{path}: missing required property {key}")
        min_properties = schema.get("minProperties")
        if isinstance(min_properties, int) and len(instance) < min_properties:
            issues.append(f"{path}: fewer than {min_properties} properties")
        properties = schema.get("properties", {})
        additional = schema.get("additionalProperties", True)
        for key, value in instance.items():
            child_path = f"{path}.{key}"
            if key in properties:
                issues.extend(
                    validate_json_schema_subset(
                        value,
                        properties[key],
                        root_schema=root,
                        path=child_path,
                    )
                )
            elif additional is False:
                issues.append(f"{path}: unknown property {key}")
            elif isinstance(additional, dict):
                issues.extend(
                    validate_json_schema_subset(
                        value, additional, root_schema=root, path=child_path
                    )
                )

    if isinstance(instance, list):
        min_items = schema.get("minItems")
        max_items = schema.get("maxItems")
        if isinstance(min_items, int) and len(instance) < min_items:
            issues.append(f"{path}: fewer than {min_items} items")
        if isinstance(max_items, int) and len(instance) > max_items:
            issues.append(f"{path}: more than {max_items} items")
        item_schema = schema.get("items")
        if isinstance(item_schema, dict):
            for index, value in enumerate(instance):
                issues.extend(
                    validate_json_schema_subset(
                        value,
                        item_schema,
                        root_schema=root,
                        path=f"{path}[{index}]",
                    )
                )

    if isinstance(instance, str):
        min_length = schema.get("minLength")
        if isinstance(min_length, int) and len(instance) < min_length:
            issues.append(f"{path}: shorter than {min_length} characters")
        pattern = schema.get("pattern")
        if isinstance(pattern, str) and re.search(pattern, instance) is None:
            issues.append(f"{path}: does not match required pattern")
        if schema.get("format") == "date":
            try:
                dt.date.fromisoformat(instance)
            except ValueError:
                issues.append(f"{path}: invalid ISO date")

    minimum = schema.get("minimum")
    if isinstance(instance, int) and not isinstance(instance, bool):
        if isinstance(minimum, int) and instance < minimum:
            issues.append(f"{path}: value is below minimum {minimum}")

    return issues


def duplicate_values(values: list[str]) -> set[str]:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for value in values:
        if value in seen:
            duplicates.add(value)
        seen.add(value)
    return duplicates


def safe_relative_path(value: str) -> bool:
    path = Path(value)
    return not path.is_absolute() and ".." not in path.parts


def validate_structure(registry: dict[str, Any], skill_root: Path) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []

    def add(code: str, detail: str) -> None:
        issues.append({"code": code, "detail": detail})

    expected_top = {
        "$schema",
        "schema_version",
        "registry_version",
        "registry_id",
        "canonicalization",
        "hash_algorithm",
        "source_snapshot",
        "contracts",
        "capabilities",
        "canonical_roles",
        "runtime_mappings",
        "validation_policy",
    }
    missing = expected_top - registry.keys()
    extra = registry.keys() - expected_top
    if missing:
        add("REGISTRY_INVALID", f"missing top-level fields: {sorted(missing)}")
    if extra:
        add("REGISTRY_INVALID", f"unknown top-level fields: {sorted(extra)}")
    if missing:
        return issues

    schema_ref = registry.get("$schema")
    if schema_ref != "./platform-agent-registry.schema.json":
        add("REGISTRY_INVALID", f"unexpected $schema: {schema_ref!r}")
    else:
        schema_path = skill_root / "references" / schema_ref[2:]
        if not schema_path.is_file():
            add("REGISTRY_INVALID", "local registry schema is missing")
        else:
            try:
                schema = read_json(schema_path)
                schema_issues = validate_json_schema_subset(registry, schema)
            except (OSError, ValueError, json.JSONDecodeError) as exc:
                add("REGISTRY_INVALID", f"cannot load local schema: {exc}")
            else:
                for detail in schema_issues:
                    add("REGISTRY_INVALID", detail)
                if schema_issues:
                    return issues

    if registry.get("registry_id") != "daniel-content-writing-style.platform-agents":
        add("REGISTRY_INVALID", "registry_id mismatch")
    if registry.get("canonicalization") != "sorted-json-utf8-v1":
        add("REGISTRY_INVALID", "canonicalization mismatch")
    if registry.get("hash_algorithm") != "sha256":
        add("REGISTRY_INVALID", "hash algorithm must be sha256")

    contracts = registry.get("contracts")
    capabilities = registry.get("capabilities")
    roles = registry.get("canonical_roles")
    mappings = registry.get("runtime_mappings")
    if not isinstance(contracts, dict) or not isinstance(capabilities, list):
        add("REGISTRY_INVALID", "contracts/capabilities have invalid types")
        return issues
    if not isinstance(roles, list) or not isinstance(mappings, list):
        add("REGISTRY_INVALID", "roles/mappings have invalid types")
        return issues

    for contract_ref, contract in contracts.items():
        receipt_fields = contract.get("delegation_receipt_required_fields", [])
        if set(receipt_fields) != EXPECTED_RECEIPT_FIELDS or len(
            receipt_fields
        ) != len(EXPECTED_RECEIPT_FIELDS):
            add(
                "OUTPUT_CONTRACT_VIOLATION",
                f"{contract_ref}: delegation receipt fields changed",
            )
        expected_contract = EXPECTED_CONTRACT_FIELDS.get(contract_ref)
        if expected_contract is None:
            add("OUTPUT_CONTRACT_VIOLATION", f"unexpected contract {contract_ref}")
            continue
        if contract.get("contract_version") != "1.0.0":
            add(
                "OUTPUT_CONTRACT_VIOLATION",
                f"{contract_ref}: contract version changed without revalidation",
            )
        if contract.get("overlay_evidence") != "prompt-contract-only":
            add(
                "OUTPUT_CONTRACT_VIOLATION",
                f"{contract_ref}: unsupported overlay evidence claim",
            )
        if contract.get("baseline_gap_policy") != EXPECTED_BASELINE_POLICIES.get(
            contract_ref
        ):
            add(
                "OUTPUT_CONTRACT_VIOLATION",
                f"{contract_ref}: baseline gap policy changed",
            )
        for local_key, expected_key in (
            ("required_inputs", "inputs"),
            ("required_outputs", "outputs"),
        ):
            values = contract.get(local_key, [])
            if set(values) != expected_contract[expected_key] or len(values) != len(
                expected_contract[expected_key]
            ):
                add(
                    "OUTPUT_CONTRACT_VIOLATION",
                    f"{contract_ref}: {local_key} changed",
                )
        diff_contract = contract.get("diff_contract", {})
        for local_key in ("must_be_empty", "may_be_nonempty"):
            values = diff_contract.get(local_key, [])
            if set(values) != expected_contract[local_key] or len(values) != len(
                expected_contract[local_key]
            ):
                add(
                    "OUTPUT_CONTRACT_VIOLATION",
                    f"{contract_ref}: diff policy {local_key} changed",
                )
        if diff_contract.get("on_missing_or_invalid") != "BLOCK" or diff_contract.get(
            "on_forbidden_diff"
        ) != "BLOCK":
            add("OUTPUT_CONTRACT_VIOLATION", f"{contract_ref}: BLOCK policy changed")

    snapshot_version = registry.get("source_snapshot", {}).get(
        "verified_plugin_version"
    )
    for mapping in mappings:
        if isinstance(mapping, dict) and mapping.get(
            "verified_plugin_version"
        ) != snapshot_version:
            add(
                "PLUGIN_VERSION_UNVERIFIED",
                f"{mapping.get('agent_type')}: runtime/plugin snapshot versions differ",
            )

    caps = [item.get("capability") for item in capabilities if isinstance(item, dict)]
    if len(capabilities) != 7 or set(caps) != EXPECTED_CAPABILITIES:
        add(
            "REGISTRY_INVALID",
            f"expected exactly seven capabilities, got {sorted(str(v) for v in caps)}",
        )
    for duplicate in sorted(duplicate_values([str(v) for v in caps])):
        add("REGISTRY_INVALID", f"duplicate capability: {duplicate}")

    role_refs = [
        item.get("canonical_role_ref") for item in roles if isinstance(item, dict)
    ]
    mapping_refs = [
        item.get("canonical_role_ref") for item in mappings if isinstance(item, dict)
    ]
    binding_ids = [
        item.get("runtime_binding_id") for item in mappings if isinstance(item, dict)
    ]
    agent_types = [item.get("agent_type") for item in mappings if isinstance(item, dict)]
    for label, values in (
        ("canonical role", role_refs),
        ("runtime role", mapping_refs),
        ("runtime binding", binding_ids),
        ("agent type", agent_types),
    ):
        for duplicate in sorted(duplicate_values([str(v) for v in values])):
            add("REGISTRY_INVALID", f"duplicate {label}: {duplicate}")

    role_set = set(role_refs)
    mapping_set = set(mapping_refs)
    capability_role_refs = [
        item.get("canonical_role_ref")
        for item in capabilities
        if isinstance(item, dict)
    ]
    if len(set(capability_role_refs)) != len(capability_role_refs):
        add("REGISTRY_INVALID", "capabilities must map to unique canonical roles")
    if set(capability_role_refs) != role_set:
        add("REGISTRY_INVALID", "capability/canonical role sets differ")
    for item in capabilities:
        if not isinstance(item, dict):
            add("REGISTRY_INVALID", "capability item must be an object")
            continue
        role_ref = item.get("canonical_role_ref")
        contract_ref = item.get("contract_ref")
        if role_ref not in role_set:
            add("REGISTRY_INVALID", f"capability role is missing: {role_ref}")
        if contract_ref not in contracts:
            add("REGISTRY_INVALID", f"capability contract is missing: {contract_ref}")
        expected = EXPECTED_BINDINGS.get(item.get("capability"))
        if expected is not None:
            role_id, platform, workflow_stage, expected_contract = expected
            expected_role_ref = f"urn:agi-super-team:role:cco:{role_id}"
            if role_ref != expected_role_ref:
                add(
                    "ROLE_IDENTITY_MISMATCH",
                    f"{item.get('capability')}: canonical role binding changed",
                )
            if item.get("platform") != platform:
                add(
                    "REGISTRY_INVALID",
                    f"{item.get('capability')}: platform binding changed",
                )
            if item.get("workflow_stage") != workflow_stage:
                add(
                    "REGISTRY_INVALID",
                    f"{item.get('capability')}: workflow stage changed",
                )
            if contract_ref != expected_contract:
                add(
                    "OUTPUT_CONTRACT_VIOLATION",
                    f"{item.get('capability')}: incompatible contract binding",
                )
            if item.get("skill_overlay_scope") != EXPECTED_OVERLAY_SCOPES.get(
                item.get("capability")
            ):
                add(
                    "OUTPUT_CONTRACT_VIOLATION",
                    f"{item.get('capability')}: overlay scope changed",
                )
    if role_set != mapping_set:
        add(
            "REGISTRY_INVALID",
            f"canonical/runtime role sets differ: roles={sorted(str(v) for v in role_set)} "
            f"mappings={sorted(str(v) for v in mapping_set)}",
        )

    for role in roles:
        if not isinstance(role, dict):
            add("REGISTRY_INVALID", "canonical role must be an object")
            continue
        role_id = role.get("role_id")
        expected_ref = f"urn:agi-super-team:role:cco:{role_id}"
        if role.get("canonical_role_ref") != expected_ref:
            add("ROLE_IDENTITY_MISMATCH", f"{role_id}: canonical role ref mismatch")
        source_path = role.get("provenance", {}).get("upstream_source_path")
        if not isinstance(source_path, str) or not safe_relative_path(source_path):
            add("REGISTRY_INVALID", f"{role_id}: unsafe upstream source path")

    route_fields = registry["source_snapshot"]["route_projection_fields"]
    route_projection = []
    role_projection_map = {
        "id": "role_id",
        "trigger": "trigger",
        "doNotUseWhen": "do_not_use_when",
        "requiredInputs": "role_required_inputs",
        "outputs": "baseline_outputs",
        "acceptance": "acceptance",
        "boundary": "boundary",
    }
    for role in sorted(roles, key=lambda item: item["role_id"]):
        projected: dict[str, Any] = {}
        for field in route_fields:
            if field == "sourcePath":
                projected[field] = role["provenance"]["upstream_source_path"]
            else:
                projected[field] = role[role_projection_map[field]]
        route_projection.append(projected)
    if digest(route_projection) != registry["source_snapshot"][
        "route_projection_sha256"
    ]:
        add("SOURCE_DRIFT", "registry canonical role projection changed")

    for mapping in mappings:
        if not isinstance(mapping, dict):
            add("REGISTRY_INVALID", "runtime mapping must be an object")
            continue
        agent_type = mapping.get("agent_type")
        runtime_binding_id = mapping.get("runtime_binding_id")
        descriptor = mapping.get("expected_descriptor")
        logical_path = mapping.get("logical_toml_path")
        if not isinstance(runtime_binding_id, str) or not runtime_binding_id:
            add("REGISTRY_INVALID", f"{agent_type}: runtime binding id is missing")
        if not isinstance(agent_type, str) or not agent_type.startswith("ast-cco-"):
            add("REGISTRY_INVALID", f"invalid agent type: {agent_type!r}")
        if not isinstance(logical_path, str) or not safe_relative_path(logical_path):
            add("REGISTRY_INVALID", f"{agent_type}: unsafe TOML path")
        if not isinstance(descriptor, dict):
            add("REGISTRY_INVALID", f"{agent_type}: descriptor must be an object")
        elif digest(descriptor) != mapping.get("descriptor_projection_sha256"):
            add("REGISTRY_INVALID", f"{agent_type}: descriptor digest mismatch")
        if descriptor and descriptor.get("name") != agent_type:
            add("ROLE_IDENTITY_MISMATCH", f"{agent_type}: descriptor name mismatch")
        role_ref = mapping.get("canonical_role_ref")
        role_id = str(role_ref).rsplit(":", 1)[-1]
        expected_agent_type = f"ast-cco-{role_id}"
        expected_mapping_version = mapping.get("mapping_version")
        if agent_type != expected_agent_type:
            add("ROLE_IDENTITY_MISMATCH", f"{agent_type}: role/agent type mismatch")
        if logical_path != f"payload/agents/{agent_type}.toml":
            add("ROLE_IDENTITY_MISMATCH", f"{agent_type}: TOML locator mismatch")
        expected_nicknames = [role_id]
        if mapping.get("accepted_nicknames") != expected_nicknames:
            add("AGENT_MATCH_AMBIGUOUS", f"{agent_type}: accepted nickname mismatch")
        if descriptor and descriptor.get("nickname_candidates") != expected_nicknames:
            add("ROLE_IDENTITY_MISMATCH", f"{agent_type}: descriptor nickname mismatch")
        if runtime_binding_id != f"codex.{agent_type}@{expected_mapping_version}":
            add("ROLE_IDENTITY_MISMATCH", f"{agent_type}: runtime binding id mismatch")

    snapshot = registry.get("source_snapshot")
    if not isinstance(snapshot, dict):
        add("REGISTRY_INVALID", "source_snapshot must be an object")
    else:
        for key, expected_value in EXPECTED_SNAPSHOT.items():
            if snapshot.get(key) != expected_value:
                add("SOURCE_DRIFT", f"source snapshot field changed: {key}")
        for key in ("plugin_manifest_locator", "route_locator", "hierarchy_locator"):
            locator = snapshot.get(key)
            if not isinstance(locator, str) or not locator.startswith("plugin:"):
                add("REGISTRY_INVALID", f"invalid logical locator {key}: {locator!r}")
            if isinstance(locator, str) and (locator.startswith("/") or ".." in locator):
                add("REGISTRY_INVALID", f"unsafe logical locator {key}")

    policy = registry.get("validation_policy")
    if not isinstance(policy, dict):
        add("REGISTRY_INVALID", "validation_policy must be an object")
    elif not policy.get("reject_absolute_paths") or not policy.get(
        "forbid_implicit_latest"
    ):
        add("REGISTRY_INVALID", "fail-closed path/version policy is required")

    return issues


def validate_plugin(
    registry: dict[str, Any], plugin_root: Path
) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []

    def add(code: str, detail: str) -> None:
        issues.append({"code": code, "detail": detail})

    snapshot = registry["source_snapshot"]
    manifest_path = plugin_root / ".codex-plugin/plugin.json"
    route_path = plugin_root / "skills/c-suite-team/references/routes/cco.json"
    hierarchy_path = (
        plugin_root / "skills/c-suite-team/references/agent-hierarchy.json"
    )
    for path in (manifest_path, route_path, hierarchy_path):
        if not path.is_file():
            add("PLUGIN_VERSION_UNVERIFIED", f"required plugin file missing: {path}")
    if issues:
        return issues

    manifest = read_json(manifest_path)
    if manifest.get("name") != snapshot["package"]:
        add("PLUGIN_VERSION_UNVERIFIED", "plugin package name mismatch")
    if manifest.get("version") != snapshot["verified_plugin_version"]:
        add(
            "PLUGIN_VERSION_UNVERIFIED",
            f"expected plugin {snapshot['verified_plugin_version']}, "
            f"got {manifest.get('version')}",
        )

    route = read_json(route_path)
    hierarchy = read_json(hierarchy_path)
    if route.get("schemaVersion") != snapshot["route_schema_version"]:
        add("SOURCE_DRIFT", "CCO route schema version changed")
    if hierarchy.get("schemaVersion") != snapshot["hierarchy_schema_version"]:
        add("SOURCE_DRIFT", "agent hierarchy schema version changed")

    roles = {item["role_id"]: item for item in registry["canonical_roles"]}
    route_entries = {
        item.get("id"): item
        for item in route.get("specialists", [])
        if item.get("id") in roles
    }
    if set(route_entries) != set(roles):
        add(
            "SOURCE_DRIFT",
            f"target route set changed: expected={sorted(roles)} actual={sorted(route_entries)}",
        )
        return issues

    fields = snapshot["route_projection_fields"]
    projection = [
        {key: route_entries[role_id][key] for key in fields}
        for role_id in sorted(roles)
    ]
    if digest(projection) != snapshot["route_projection_sha256"]:
        add("SOURCE_DRIFT", "target CCO route semantic projection changed")

    cco = hierarchy.get("managers", {}).get("cco", {})
    target_members = sorted(
        role_id for role_id in cco.get("subagents", []) if role_id in roles
    )
    hierarchy_projection = {
        "manager": "cco",
        "requiredMaxDepth": hierarchy.get("requiredMaxDepth"),
        "maxConcurrentChildren": cco.get("maxConcurrentChildren"),
        "members": target_members,
    }
    if digest(hierarchy_projection) != snapshot["hierarchy_projection_sha256"]:
        add("SOURCE_DRIFT", "CCO hierarchy semantic projection changed")

    route_to_role = {
        item["role_id"]: item for item in registry["canonical_roles"]
    }
    route_field_map = {
        "trigger": "trigger",
        "do_not_use_when": "doNotUseWhen",
        "role_required_inputs": "requiredInputs",
        "baseline_outputs": "outputs",
        "acceptance": "acceptance",
        "boundary": "boundary",
    }
    for role_id, role in route_to_role.items():
        entry = route_entries[role_id]
        if role["provenance"]["upstream_source_path"] != entry["sourcePath"]:
            add("SOURCE_DRIFT", f"{role_id}: upstream source path changed")
        for local_key, route_key in route_field_map.items():
            if role[local_key] != entry[route_key]:
                add("SOURCE_DRIFT", f"{role_id}: {route_key} changed")

    mappings = {
        item["canonical_role_ref"]: item for item in registry["runtime_mappings"]
    }
    for role in registry["canonical_roles"]:
        mapping = mappings[role["canonical_role_ref"]]
        path = plugin_root / mapping["logical_toml_path"]
        if not path.is_file():
            add("AGENT_UNAVAILABLE", f"{mapping['agent_type']}: TOML missing")
            continue
        try:
            parsed = tomllib.loads(path.read_text(encoding="utf-8"))
        except (OSError, tomllib.TOMLDecodeError) as exc:
            add("ROLE_IDENTITY_MISMATCH", f"{mapping['agent_type']}: {exc}")
            continue
        descriptor = {
            key: parsed.get(key)
            for key in (
                "name",
                "nickname_candidates",
                "model_reasoning_effort",
                "sandbox_mode",
            )
        }
        if descriptor != mapping["expected_descriptor"]:
            add("ROLE_IDENTITY_MISMATCH", f"{mapping['agent_type']}: descriptor changed")
        if digest(descriptor) != mapping["descriptor_projection_sha256"]:
            add(
                "ROLE_IDENTITY_MISMATCH",
                f"{mapping['agent_type']}: descriptor projection digest changed",
            )

    return issues


def offline_snapshot_expired(registry: dict[str, Any]) -> bool:
    snapshot = registry["source_snapshot"]
    verified = dt.date.fromisoformat(snapshot["verified_at"])
    expires = verified + dt.timedelta(days=int(snapshot["max_age_days"]))
    return dt.date.today() > expires


def run_self_test(registry: dict[str, Any], skill_root: Path) -> list[str]:
    failures: list[str] = []

    duplicate = copy.deepcopy(registry)
    duplicate["capabilities"][1]["capability"] = duplicate["capabilities"][0][
        "capability"
    ]
    if not validate_structure(duplicate, skill_root):
        failures.append("duplicate capability mutation was not rejected")

    absolute = copy.deepcopy(registry)
    absolute["runtime_mappings"][0]["logical_toml_path"] = "/tmp/agent.toml"
    if not validate_structure(absolute, skill_root):
        failures.append("absolute TOML path mutation was not rejected")

    missing_role = copy.deepcopy(registry)
    missing_role["capabilities"][0][
        "canonical_role_ref"
    ] = "urn:agi-super-team:role:cco:missing"
    if not validate_structure(missing_role, skill_root):
        failures.append("missing role mutation was not rejected")

    unknown_field = copy.deepcopy(registry)
    unknown_field["capabilities"][0]["unexpected"] = True
    if not validate_structure(unknown_field, skill_root):
        failures.append("unknown capability field mutation was not rejected")

    missing_required = copy.deepcopy(registry)
    del missing_required["capabilities"][0]["workflow_stage"]
    if not validate_structure(missing_required, skill_root):
        failures.append("missing required capability field was not rejected")

    version_drift = copy.deepcopy(registry)
    version_drift["runtime_mappings"][0]["verified_plugin_version"] = "9.9.9"
    if not validate_structure(version_drift, skill_root):
        failures.append("runtime/plugin version drift was not rejected")

    duplicate_role = copy.deepcopy(registry)
    duplicate_role["capabilities"][1]["canonical_role_ref"] = duplicate_role[
        "capabilities"
    ][0]["canonical_role_ref"]
    if not validate_structure(duplicate_role, skill_root):
        failures.append("duplicate capability role binding was not rejected")

    nickname_pollution = copy.deepcopy(registry)
    nickname_pollution["runtime_mappings"][0]["accepted_nicknames"] = [
        "douyin-strategist"
    ]
    if not validate_structure(nickname_pollution, skill_root):
        failures.append("cross-role nickname mutation was not rejected")

    wrong_contract = copy.deepcopy(registry)
    wrong_contract["capabilities"][0][
        "contract_ref"
    ] = "short_video_editing_guidance@1"
    if not validate_structure(wrong_contract, skill_root):
        failures.append("workflow/contract mismatch was not rejected")

    malformed_snapshot = copy.deepcopy(registry)
    malformed_snapshot["source_snapshot"] = "invalid"
    if not validate_structure(malformed_snapshot, skill_root):
        failures.append("malformed source snapshot was not rejected")

    wrong_platform = copy.deepcopy(registry)
    wrong_platform["capabilities"][0]["platform"] = "douyin"
    if not validate_structure(wrong_platform, skill_root):
        failures.append("capability/platform mismatch was not rejected")

    portable_route_drift = copy.deepcopy(registry)
    portable_route_drift["canonical_roles"][0]["trigger"] += " changed"
    if not validate_structure(portable_route_drift, skill_root):
        failures.append("portable canonical role drift was not rejected")

    missing_candidate = copy.deepcopy(registry)
    missing_candidate["contracts"]["platform_native_adaptation@1"][
        "required_outputs"
    ].remove("platform_content_candidate")
    if not validate_structure(missing_candidate, skill_root):
        failures.append("missing platform content candidate was not rejected")

    contract_version_drift = copy.deepcopy(registry)
    contract_version_drift["contracts"]["platform_native_adaptation@1"][
        "contract_version"
    ] = "2.0.0"
    if not validate_structure(contract_version_drift, skill_root):
        failures.append("contract version drift was not rejected")

    future_snapshot = copy.deepcopy(registry)
    future_snapshot["source_snapshot"]["verified_at"] = "2099-01-01"
    if not validate_structure(future_snapshot, skill_root):
        failures.append("future snapshot date was not rejected")

    locator_drift = copy.deepcopy(registry)
    locator_drift["source_snapshot"]["route_locator"] = (
        "plugin:agi-super-team-codex@1.4.0:other/cco.json"
    )
    if not validate_structure(locator_drift, skill_root):
        failures.append("source locator drift was not rejected")

    overlay_scope_drift = copy.deepcopy(registry)
    overlay_scope_drift["capabilities"][0]["skill_overlay_scope"] = (
        registry["capabilities"][2]["skill_overlay_scope"]
    )
    if not validate_structure(overlay_scope_drift, skill_root):
        failures.append("cross-platform overlay scope was not rejected")

    baseline_policy_drift = copy.deepcopy(registry)
    baseline_policy_drift["contracts"]["platform_native_adaptation@1"][
        "baseline_gap_policy"
    ] = "允许主 Agent 补写"
    if not validate_structure(baseline_policy_drift, skill_root):
        failures.append("baseline gap policy drift was not rejected")

    return failures


def emit(
    status: str,
    issues: list[dict[str, str]],
    *,
    json_output: bool,
    runtime: str,
) -> None:
    payload = {"status": status, "runtime": runtime, "issues": issues}
    if json_output:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return
    print(f"{status} runtime={runtime}")
    for issue in issues:
        print(f"{issue['code']}: {issue['detail']}")


def main() -> int:
    parser = argparse.ArgumentParser()
    default_registry = (
        Path(__file__).resolve().parent.parent
        / "references/platform-agent-registry.json"
    )
    parser.add_argument("--registry", type=Path, default=default_registry)
    parser.add_argument("--plugin-root", type=Path)
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--json", action="store_true", dest="json_output")
    args = parser.parse_args()

    try:
        registry = read_json(args.registry)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        emit(
            "ENVIRONMENT_ERROR",
            [{"code": "REGISTRY_INVALID", "detail": str(exc)}],
            json_output=args.json_output,
            runtime="not-checked",
        )
        return ENVIRONMENT_ERROR

    skill_root = Path(__file__).resolve().parent.parent
    issues = validate_structure(registry, skill_root)
    if issues:
        emit(
            "CONTRACT_ERROR",
            issues,
            json_output=args.json_output,
            runtime="not-checked",
        )
        return CONTRACT_ERROR

    if args.self_test:
        failures = run_self_test(registry, skill_root)
        if failures:
            emit(
                "CONTRACT_ERROR",
                [{"code": "SELF_TEST_FAILED", "detail": item} for item in failures],
                json_output=args.json_output,
                runtime="self-test",
            )
            return CONTRACT_ERROR

    if args.plugin_root:
        try:
            plugin_issues = validate_plugin(registry, args.plugin_root.resolve())
        except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
            emit(
                "ENVIRONMENT_ERROR",
                [{"code": "PLUGIN_VERSION_UNVERIFIED", "detail": str(exc)}],
                json_output=args.json_output,
                runtime="checked",
            )
            return ENVIRONMENT_ERROR
        if plugin_issues:
            emit(
                "STALE",
                plugin_issues,
                json_output=args.json_output,
                runtime="checked",
            )
            return STALE
        runtime = "plugin-snapshot-verified"
    else:
        if offline_snapshot_expired(registry):
            emit(
                "STALE",
                [
                    {
                        "code": "SNAPSHOT_EXPIRED",
                        "detail": "snapshot expired and no --plugin-root was supplied",
                    }
                ],
                json_output=args.json_output,
                runtime="snapshot-only",
            )
            return STALE
        runtime = "portable-snapshot-only"

    emit("PASS", [], json_output=args.json_output, runtime=runtime)
    return OK


if __name__ == "__main__":
    raise SystemExit(main())
