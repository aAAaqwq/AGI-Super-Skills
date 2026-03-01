#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${PROJECT_DIR}"

usage() {
    cat <<'USAGE'
Usage: run_factory_stage_gate.sh [options]

Run an automated stage gate: dry-run -> smoke -> real/promotion.

Options:
  --artifacts-dir DIR      Artifacts root (default: artifacts)
  --config PATH            Base strategy config (default: config/strategy_overrides.yaml)
  --run-prefix PREFIX      Prefix for stage run IDs (default: factory_stage_gate)
  --dry-profile NAME       Dry-run profile (default: smoke)
  --smoke-profile NAME     Smoke profile (default: smoke)
  --real-profile NAME      Real profile (default: daily)
  --allow-real-deploy      Permit live-paper deployment in real stage
  --help                   Show this message
  -- [args ...]            Extra arguments passed to each factory_cycle call

Examples:
  ./scripts/run_factory_stage_gate.sh --run-prefix v8_unify
  ALLOW_REAL_DEPLOY=1 ./scripts/run_factory_stage_gate.sh --run-prefix v8_unify
USAGE
}

ARTIFACTS_DIR="artifacts"
CONFIG_PATH="config/strategy_overrides.yaml"
RUN_PREFIX="factory_stage_gate"
DRY_PROFILE="smoke"
SMOKE_PROFILE="smoke"
REAL_PROFILE="daily"
ALLOW_REAL_DEPLOY="${ALLOW_REAL_DEPLOY:-0}"
EXTRA_ARGS=()

while [[ $# -gt 0 ]]; do
    case "$1" in
        --artifacts-dir)
            ARTIFACTS_DIR="${2}"
            shift 2
            ;;
        --config)
            CONFIG_PATH="${2}"
            shift 2
            ;;
        --run-prefix)
            RUN_PREFIX="${2}"
            shift 2
            ;;
        --dry-profile)
            DRY_PROFILE="${2}"
            shift 2
            ;;
        --smoke-profile)
            SMOKE_PROFILE="${2}"
            shift 2
            ;;
        --real-profile)
            REAL_PROFILE="${2}"
            shift 2
            ;;
        --allow-real-deploy)
            ALLOW_REAL_DEPLOY=1
            shift 1
            ;;
        --help)
            usage
            exit 0
            ;;
        --)
            shift
            while [[ $# -gt 0 ]]; do
                EXTRA_ARGS+=("${1}")
                shift
            done
            ;;
        *)
            EXTRA_ARGS+=("${1}")
            shift
            ;;
    esac
done

TS="$(date -u +%Y%m%dT%H%M%SZ)"
EVIDENCE_PATH="${ARTIFACTS_DIR}/${RUN_PREFIX}_${TS}.evidence.json"

run_stage() {
    local stage="$1"
    local profile="$2"
    local allow_deploy="$3"
    local run_id="${RUN_PREFIX}_${stage}_${TS}"

    local args=(
        --no-deploy
    )
    if [[ "${stage}" == "real" && "${allow_deploy}" == "1" ]]; then
        args=()
    fi

    local cmd=(
        python3 tools/factory_cycle.py
        --run-id "${run_id}"
        --artifacts-dir "${ARTIFACTS_DIR}"
        --profile "${profile}"
        --config "${CONFIG_PATH}"
        "${EXTRA_ARGS[@]}"
        "${args[@]}"
    )

    echo "[stage-gate] running ${stage}: ${cmd[*]}"
    "${cmd[@]}"
    echo "[stage-gate] ${stage} complete; run_id=${run_id}"

    local run_stage_dir
    run_stage_dir="$(python3 - "${ARTIFACTS_DIR}" "${run_id}" <<'PY'
import datetime
import json
from pathlib import Path
import sys

artifacts_root = Path(sys.argv[1]).expanduser()
run_id = str(sys.argv[2]).strip()

matches = []
if not artifacts_root.exists():
    pass
else:
    for meta_path in artifacts_root.rglob("run_metadata.json"):
        try:
            payload = json.loads(meta_path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if str(payload.get("run_id", "")).strip() == run_id:
            matches.append(meta_path.parent)

if not matches:
    for days_back in range(3):
        d = (datetime.datetime.utcnow().date() - datetime.timedelta(days=days_back)).isoformat()
        candidates = [
            artifacts_root / d / f"run_{run_id}",
            artifacts_root / f"run_{run_id}",
        ]
        for candidate in candidates:
            if candidate.exists() and candidate.is_dir():
                matches.append(candidate)
                break

if matches:
    runs = sorted({str(p.resolve()) for p in matches})
    print(runs[0])
    sys.exit(0)

print("")
PY
)"
    if [[ -z "${run_stage_dir}" ]]; then
        echo "[stage-gate] ERROR: could not locate run directory for run_id=${run_id}"
        return 1
    fi

    local selection_json="${run_stage_dir}/reports/selection.json"
    if [[ ! -f "${selection_json}" ]]; then
        echo "[stage-gate] ERROR: missing selection.json for ${stage} (${selection_json})"
        return 1
    fi

    if ! python3 - "${selection_json}" "$stage" "$allow_deploy" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
stage = sys.argv[2]
allow_deploy = sys.argv[3] in {"1", "true", "yes", "on"}

payload = json.loads(path.read_text(encoding="utf-8"))
required = {"selection_stage", "deploy_stage", "promotion_stage"}
missing = sorted(required - set(payload.keys()))
if missing:
    raise SystemExit(f"[stage-gate] ERROR: selection.json missing keys {missing}")

selection_stage = str(payload.get("selection_stage", "")).strip()
deploy_stage = str(payload.get("deploy_stage", "")).strip()
promotion_stage = str(payload.get("promotion_stage", "")).strip()

if selection_stage != "selected":
    raise SystemExit("[stage-gate] ERROR: selection_stage is not selected")

if stage in {"dry", "smoke"} or not allow_deploy:
    if deploy_stage not in {"no_deploy", "skipped"}:
        raise SystemExit("[stage-gate] ERROR: dry/smoke stages must not deploy")
    if promotion_stage not in {"skipped", ""}:
        raise SystemExit("[stage-gate] ERROR: dry/smoke stages must skip promotion")
else:
    if deploy_stage == "pending":
        raise SystemExit("[stage-gate] ERROR: real stage remains pending deployment")
    if promotion_stage == "pending":
        raise SystemExit("[stage-gate] ERROR: real stage remains pending promotion")

print("[stage-gate] verified", path.as_posix())
PY
    then
        echo "[stage-gate] ERROR: selection preconditions not met for ${stage}"
        return 1
    fi

    local summary_json="${run_stage_dir}/selection_gate_summary_${stage}.json"
    if ! python3 scripts/validate_factory_selection_gate.py \
        --selection-json "$selection_json" \
        --stage "$stage" \
        --summary-json "$summary_json" \
        --status-message "[stage-gate] selection evidence check"; then
        echo "[stage-gate] ERROR: selection evidence validation failed for ${stage}"
        return 1
    fi

python3 - "$selection_json" "$run_stage_dir" "$EVIDENCE_PATH" "$stage" "${run_id}" "$summary_json" <<'PY'
import json
import sys
from pathlib import Path

selection_path = sys.argv[1]
run_stage_dir = sys.argv[2]
evidence_path = sys.argv[3]
stage = sys.argv[4]
run_id = sys.argv[5] if len(sys.argv) > 5 else Path(run_stage_dir).name
summary_json = sys.argv[6] if len(sys.argv) > 6 else ""

selection_path = Path(selection_path)
evidence_path = Path(evidence_path)
selection_obj = json.loads(selection_path.read_text(encoding="utf-8"))
evidence = {
    "run_id": run_id,
    "stage": stage,
    "selection_stage": selection_obj.get("selection_stage"),
    "deploy_stage": selection_obj.get("deploy_stage"),
    "promotion_stage": selection_obj.get("promotion_stage"),
    "evidence_bundle_paths": selection_obj.get("evidence_bundle_paths", {}),
}
if summary_json:
    evidence["selection_gate_summary_json"] = summary_json

existing = []
if evidence_path.exists():
    try:
        existing = json.loads(evidence_path.read_text(encoding="utf-8"))
    except Exception:
        existing = []

if not isinstance(existing, list):
    existing = []
existing.append(evidence)
evidence_path.write_text(json.dumps(existing, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY
}

run_stage dry "${DRY_PROFILE}" 0
run_stage smoke "${SMOKE_PROFILE}" 0

if [[ "${ALLOW_REAL_DEPLOY}" == "1" ]]; then
    run_stage real "${REAL_PROFILE}" 1
else
    run_stage real "${REAL_PROFILE}" 0
fi

echo "[stage-gate] evidence manifest: ${EVIDENCE_PATH}"
