#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STRICT_MODE="${AQC_GPU_PARITY_STRICT:-0}"

# On WSL2, libcuda is often exposed via this path.
if [[ -d /usr/lib/wsl/lib ]]; then
    export LD_LIBRARY_PATH="/usr/lib/wsl/lib:${LD_LIBRARY_PATH:-}"
fi

cd "${ROOT_DIR}/backtester"
echo "[gpu-parity-gate] Running GPU parity fixtures (strict=${STRICT_MODE})..."

if ! command -v nvcc >/dev/null 2>&1; then
    echo "::warning::[gpu-parity-gate] nvcc not found on this runner; skipping GPU parity gate."
    case "${STRICT_MODE}" in
        1 | true | TRUE | yes | YES | on | ON)
            echo "[gpu-parity-gate] STRICT MODE: AQC_GPU_PARITY_STRICT=${STRICT_MODE}; failing because nvcc is unavailable."
            exit 1
            ;;
        *)
            echo "[gpu-parity-gate] Non-strict mode: continuing with warning only."
            exit 0
            ;;
    esac
fi

LOG_FILE="$(mktemp)"
GPU_RUNTIME_SKIP=0
trap 'rm -f "${LOG_FILE}"' EXIT

if ! cargo test -p bt-gpu --test gpu_runtime_parity_tiny_fixture -- --nocapture 2>&1 | tee "${LOG_FILE}"; then
    echo "[gpu-parity-gate] FAIL: tiny GPU runtime parity fixture failed."
    exit 1
fi

if grep -E -q "(\\[gpu-parity\\] SKIP: CUDA unavailable|Skipping: CUDA unavailable)" "${LOG_FILE}"; then
    echo "[gpu-parity-gate] tiny fixture is skipped: CUDA unavailable."
    GPU_RUNTIME_SKIP=1
fi

if ! cargo test -p bt-gpu --test cpu_gpu_parity_sweep_1h_3m -- --nocapture 2>&1 | tee "${LOG_FILE}"; then
    echo "[gpu-parity-gate] FAIL: synthetic CPU↔GPU parity fixture failed."
    exit 1
fi

if grep -E -q "(\\[gpu-parity\\] SKIP: CUDA unavailable|Skipping: CUDA unavailable)" "${LOG_FILE}"; then
    echo "[gpu-parity-gate] synthetic parity fixture is skipped: CUDA unavailable."
    GPU_RUNTIME_SKIP=1
fi

if [ "${GPU_RUNTIME_SKIP}" = "1" ]; then
    echo "::warning::[gpu-parity-gate] CUDA unavailable on this runner; GPU parity assertions were not fully enforced."
    case "${STRICT_MODE}" in
        1 | true | TRUE | yes | YES | on | ON)
            echo "[gpu-parity-gate] STRICT MODE: AQC_GPU_PARITY_STRICT=${STRICT_MODE}; failing because CUDA is unavailable."
            exit 1
            ;;
        *)
            echo "[gpu-parity-gate] Non-strict mode: continuing with warning only."
            ;;
    esac
    exit 0
fi

if ! "${ROOT_DIR}/scripts/ci_gpu_smoke_parity_gate.sh"; then
    echo "[gpu-parity-gate] FAIL: lane smoke parity stage failed."
    exit 1
fi

echo "[gpu-parity-gate] PASS: GPU parity assertions executed."
