#!/usr/bin/env bash
set -euo pipefail

METHOD="copy"
AGENTS="codex,claude,cursor"
SKILL_NAME="audit-code"
SOURCE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"

usage() {
  cat <<USAGE
Usage: $(basename "$0") [options]

Sync this skill to agent-specific global skill directories.

Options:
  --method <copy|symlink>    Sync method (default: copy)
  --agents <csv>             Agents to sync (default: codex,claude,cursor)
                             Supported aliases:
                             codex, claude, claude-code, cursor
  --skill-name <name>        Destination skill folder name (default: audit-code)
  --source <path>            Override source skill directory (default: repo root)
  -h, --help                 Show this help

Examples:
  $(basename "$0")
  $(basename "$0") --method symlink
  $(basename "$0") --agents codex,claude
USAGE
}

trim() {
  local value="$1"
  value="${value#${value%%[![:space:]]*}}"
  value="${value%${value##*[![:space:]]}}"
  printf '%s' "$value"
}

agent_root() {
  case "$1" in
    codex)
      printf '%s' "$HOME/.codex/skills"
      ;;
    claude|claude-code)
      printf '%s' "$HOME/.claude/skills"
      ;;
    cursor)
      printf '%s' "$HOME/.cursor/skills"
      ;;
    *)
      printf '%s' ""
      ;;
  esac
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --method)
      METHOD="$2"
      shift 2
      ;;
    --agents)
      AGENTS="$2"
      shift 2
      ;;
    --skill-name)
      SKILL_NAME="$2"
      shift 2
      ;;
    --source)
      SOURCE_DIR="$(cd "$2" && pwd -P)"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage
      exit 1
      ;;
  esac
done

if [[ "$METHOD" != "copy" && "$METHOD" != "symlink" ]]; then
  echo "Invalid --method: $METHOD (expected copy or symlink)" >&2
  exit 1
fi

if [[ ! -f "$SOURCE_DIR/SKILL.md" ]]; then
  echo "Source directory must contain SKILL.md: $SOURCE_DIR" >&2
  exit 1
fi

IFS=',' read -r -a agent_list <<< "$AGENTS"

for raw_agent in "${agent_list[@]}"; do
  agent="$(trim "$raw_agent")"
  if [[ -z "$agent" ]]; then
    continue
  fi

  root="$(agent_root "$agent")"
  if [[ -z "$root" ]]; then
    echo "Skipping unknown agent '$agent'" >&2
    continue
  fi

  dest="$root/$SKILL_NAME"

  if [[ "$dest" == "$SOURCE_DIR" ]]; then
    echo "[$agent] source already at target ($dest), skipping"
    continue
  fi

  mkdir -p "$root"

  if [[ "$METHOD" == "symlink" ]]; then
    if [[ -e "$dest" || -L "$dest" ]]; then
      rm -rf "$dest"
    fi
    ln -s "$SOURCE_DIR" "$dest"
    echo "[$agent] symlinked $dest -> $SOURCE_DIR"
  else
    if [[ -L "$dest" ]]; then
      rm -f "$dest"
    fi
    mkdir -p "$dest"
    rsync -a --delete \
      --exclude '.git' \
      --exclude '.git/*' \
      --exclude '.DS_Store' \
      "$SOURCE_DIR/" "$dest/"
    echo "[$agent] copied to $dest"
  fi
done
