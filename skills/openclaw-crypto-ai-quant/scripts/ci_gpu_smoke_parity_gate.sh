#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKTESTER_DIR="${ROOT_DIR}/backtester"
STRICT_MODE="${AQC_GPU_PARITY_STRICT:-0}"
PYTHON_BIN="${AQC_PARITY_PYTHON:-python3}"
CONFIG_PATH="${AQC_PARITY_CONFIG_PATH:-${ROOT_DIR}/config/strategy_overrides.yaml}"
BASELINE_ANY_MISMATCH_COUNT="${AQC_PARITY_BASELINE_ANY_MISMATCH_COUNT:-}"
BASELINE_MAX_ABS_PNL_DIFF="${AQC_PARITY_BASELINE_MAX_ABS_PNL_DIFF:-}"
BASELINE_MEAN_ABS_PNL_DIFF="${AQC_PARITY_BASELINE_MEAN_ABS_PNL_DIFF:-}"
BASELINE_TRADE_COUNT_MISMATCH_COUNT="${AQC_PARITY_BASELINE_TRADE_COUNT_MISMATCH_COUNT:-}"

is_strict_mode() {
    case "${STRICT_MODE}" in
        1 | true | TRUE | yes | YES | on | ON)
            return 0
            ;;
        *)
            return 1
            ;;
    esac
}

warn_or_fail() {
    local message="$1"
    if is_strict_mode; then
        echo "[gpu-smoke-parity] FAIL: ${message}"
        return 1
    fi

    echo "[gpu-smoke-parity] NON-STRICT: ${message}"
    return 0
}

if [[ -d /usr/lib/wsl/lib ]]; then
    export LD_LIBRARY_PATH="/usr/lib/wsl/lib:${LD_LIBRARY_PATH:-}"
fi

RUN_ID="gpu-smoke-parity-$(date -u +%Y%m%dT%H%M%SZ)"
OUT_DIR="${ROOT_DIR}/artifacts/${RUN_ID}"
mkdir -p "${OUT_DIR}"

run_sweep() {
    local lane_name="$1"
    local parity_mode="$2"
    local with_gpu="$3"
    local output_path="$4"
    local log_path="${OUT_DIR}/${lane_name}.log"

    echo "[gpu-smoke-parity] Running ${lane_name} sweep -> ${output_path}"

    local -a cli_args=(
        "cargo"
        "run"
        "-q"
        "--package"
        "bt-cli"
        "--features"
        "gpu"
        "--"
        "sweep"
        "--sweep-spec"
        "sweeps/smoke.yaml"
        "--interval"
        "1h"
        "--entry-interval"
        "3m"
        "--exit-interval"
        "3m"
        "--config"
        "${CONFIG_PATH}"
        "--output"
        "${output_path}"
        "--parity-mode"
        "${parity_mode}"
    )

    if [[ "${with_gpu}" == "1" ]]; then
        cli_args+=(--gpu)
    fi

    if ! (
        cd "${BACKTESTER_DIR}" && \
        "${cli_args[@]}"
    ) 2>&1 | tee "${log_path}"; then
        echo "[gpu-smoke-parity] FAIL: ${lane_name} sweep failed."
        return 1
    fi

    echo "[gpu-smoke-parity] PASS: ${lane_name} sweep completed."
}

run_comparison() {
    local report_path="${OUT_DIR}/gpu_smoke_parity_report.json"
    local cmp_cmd=(
        "${PYTHON_BIN}"
        "${ROOT_DIR}/tools/compare_sweep_outputs.py"
        "--lane-a-cpu"
        "${OUT_DIR}/lane_a_cpu.jsonl"
        "--lane-a-gpu"
        "${OUT_DIR}/lane_a_gpu.jsonl"
        "--lane-b-cpu"
        "${OUT_DIR}/lane_b_cpu.jsonl"
        "--lane-b-gpu"
        "${OUT_DIR}/lane_b_gpu.jsonl"
        "--output"
        "${report_path}"
        "--print-summary"
    )

    if is_strict_mode; then
        cmp_cmd+=(--fail-on-assert)
    fi

    if [[ -n "${BASELINE_ANY_MISMATCH_COUNT}" ]]; then
        cmp_cmd+=(--baseline-any-mismatch-count "${BASELINE_ANY_MISMATCH_COUNT}")
    fi
    if [[ -n "${BASELINE_MAX_ABS_PNL_DIFF}" ]]; then
        cmp_cmd+=(--baseline-max-abs-total-pnl-diff "${BASELINE_MAX_ABS_PNL_DIFF}")
    fi
    if [[ -n "${BASELINE_MEAN_ABS_PNL_DIFF}" ]]; then
        cmp_cmd+=(--baseline-mean-abs-total-pnl-diff "${BASELINE_MEAN_ABS_PNL_DIFF}")
    fi
    if [[ -n "${BASELINE_TRADE_COUNT_MISMATCH_COUNT}" ]]; then
        cmp_cmd+=(--baseline-trade-count-mismatch-count "${BASELINE_TRADE_COUNT_MISMATCH_COUNT}")
    fi

    set +e
    if ! "${cmp_cmd[@]}"; then
        set -e
        echo "[gpu-smoke-parity] FAIL: smoke parity comparison failed."
        return 1
    fi
    set -e

    echo "[gpu-smoke-parity] PASS: parity report written to ${report_path}"
}

OVERALL_FAIL=0

if ! run_sweep "lane_a_cpu" "identical-symbol-universe" 0 "${OUT_DIR}/lane_a_cpu.jsonl"; then
    OVERALL_FAIL=1
    if ! warn_or_fail "lane A CPU sweep failed."; then
        exit 1
    fi
fi

if ! run_sweep "lane_a_gpu" "identical-symbol-universe" 1 "${OUT_DIR}/lane_a_gpu.jsonl"; then
    OVERALL_FAIL=1
    if ! warn_or_fail "lane A GPU sweep failed."; then
        exit 1
    fi
fi

if ! run_sweep "lane_b_cpu" "production" 0 "${OUT_DIR}/lane_b_cpu.jsonl"; then
    OVERALL_FAIL=1
    if ! warn_or_fail "lane B CPU sweep failed."; then
        exit 1
    fi
fi

if ! run_sweep "lane_b_gpu" "production" 1 "${OUT_DIR}/lane_b_gpu.jsonl"; then
    OVERALL_FAIL=1
    if ! warn_or_fail "lane B GPU sweep failed."; then
        exit 1
    fi
fi

if [[ "${OVERALL_FAIL}" -eq 1 ]]; then
    warn_or_fail "one or more smoke sweeps failed; skipping comparison."
    exit 0
fi

if ! run_comparison; then
    if ! warn_or_fail "comparison stage failed."; then
        exit 1
    fi
fi

echo "[gpu-smoke-parity] PASS: lane parity sweep and comparison completed."
