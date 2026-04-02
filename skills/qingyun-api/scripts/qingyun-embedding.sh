#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/home/aa/clawd/skills/qingyun-api/scripts/qingyun-common.sh
source "$SCRIPT_DIR/qingyun-common.sh"

usage() {
  cat <<'EOF'
Usage:
  ./qingyun-embedding.sh "测试文本" [--dimensions 768]

Description:
  Create embedding with model gemini-embedding-2-preview.

Options:
  --dimensions N   Optional output dimensions (positive integer)
  -h, --help       Show this help message

Output:
  - Embedding dimension
  - First 5 embedding values
EOF
}

die() {
  echo "ERROR: $*" >&2
  exit 1
}

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || die "Missing required command: $1"
}

is_positive_int() {
  [[ "$1" =~ ^[1-9][0-9]*$ ]]
}

main() {
  require_cmd jq

  local text=""
  local dimensions=""

  while [[ $# -gt 0 ]]; do
    case "$1" in
      -h|--help)
        usage
        exit 0
        ;;
      --dimensions)
        shift
        [[ $# -gt 0 ]] || die "--dimensions requires a value"
        dimensions="$1"
        is_positive_int "$dimensions" || die "--dimensions must be a positive integer"
        ;;
      --*)
        die "Unknown option: $1"
        ;;
      *)
        if [[ -z "$text" ]]; then
          text="$1"
        else
          die "Unexpected extra argument: $1"
        fi
        ;;
    esac
    shift
  done

  [[ -n "$text" ]] || { usage; die "Text is required"; }

  local payload
  if [[ -n "$dimensions" ]]; then
    payload=$(jq -n --arg input "$text" --argjson dimensions "$dimensions" '{model:"gemini-embedding-2-preview",input:$input,dimensions:$dimensions}')
  else
    payload=$(jq -n --arg input "$text" '{model:"gemini-embedding-2-preview",input:$input}')
  fi

  local response embedding dimension preview
  response=$(qy_request POST /v1/embeddings "$payload") || die "Embedding request failed"

  embedding=$(echo "$response" | jq -c '.data[0].embedding // empty')
  [[ -n "$embedding" ]] || die "No embedding returned"

  dimension=$(echo "$embedding" | jq 'length')
  preview=$(echo "$embedding" | jq -c '.[0:5]')

  echo "Embedding created successfully"
  echo "Model: gemini-embedding-2-preview"
  if [[ -n "$dimensions" ]]; then
    echo "Requested dimensions: $dimensions"
  fi
  echo "Embedding dimension: $dimension"
  echo "First 5 values: $preview"
}

main "$@"
