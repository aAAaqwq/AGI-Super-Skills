#!/bin/bash
# Legal Skill Extraction Helper
# Creates a new legal skill from a learning or legal issue entry
# Usage: ./extract-skill.sh <skill-name> [--dry-run]

set -e

SKILLS_DIR="./skills"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

usage() {
    cat << EOF
Usage: $(basename "$0") <skill-name> [options]

Create a new legal skill from a learning or legal issue entry.

Arguments:
  skill-name     Name of the skill (lowercase, hyphens for spaces)

Options:
  --dry-run      Show what would be created without creating files
  --output-dir   Relative output directory under current path (default: ./skills)
  -h, --help     Show this help message

Examples:
  $(basename "$0") liability-cap-playbook
  $(basename "$0") ccpa-deletion-checklist --dry-run
  $(basename "$0") force-majeure-review --output-dir ./skills/legal

The skill will be created in: \$SKILLS_DIR/<skill-name>/
EOF
}

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1" >&2
}

SKILL_NAME=""
DRY_RUN=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --output-dir)
            if [ -z "${2:-}" ] || [[ "${2:-}" == -* ]]; then
                log_error "--output-dir requires a relative path argument"
                usage
                exit 1
            fi
            SKILLS_DIR="$2"
            shift 2
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        -*)
            log_error "Unknown option: $1"
            usage
            exit 1
            ;;
        *)
            if [ -z "$SKILL_NAME" ]; then
                SKILL_NAME="$1"
            else
                log_error "Unexpected argument: $1"
                usage
                exit 1
            fi
            shift
            ;;
    esac
done

if [ -z "$SKILL_NAME" ]; then
    log_error "Skill name is required"
    usage
    exit 1
fi

if ! [[ "$SKILL_NAME" =~ ^[a-z0-9]+(-[a-z0-9]+)*$ ]]; then
    log_error "Invalid skill name format. Use lowercase letters, numbers, and hyphens only."
    log_error "Examples: 'liability-cap-playbook', 'ccpa-deletion-checklist', 'force-majeure-review'"
    exit 1
fi

if [[ "$SKILLS_DIR" = /* ]]; then
    log_error "Output directory must be a relative path under the current directory."
    exit 1
fi

if [[ "$SKILLS_DIR" =~ (^|/)\.\.(/|$) ]]; then
    log_error "Output directory cannot include '..' path segments."
    exit 1
fi

SKILLS_DIR="${SKILLS_DIR#./}"
SKILLS_DIR="./$SKILLS_DIR"

SKILL_PATH="$SKILLS_DIR/$SKILL_NAME"

if [ -d "$SKILL_PATH" ] && [ "$DRY_RUN" = false ]; then
    log_error "Skill already exists: $SKILL_PATH"
    log_error "Use a different name or remove the existing skill first."
    exit 1
fi

if [ "$DRY_RUN" = true ]; then
    log_info "Dry run - would create:"
    echo "  $SKILL_PATH/"
    echo "  $SKILL_PATH/SKILL.md"
    echo ""
    echo "Template content would be:"
    echo "---"
    cat << TEMPLATE
name: $SKILL_NAME
description: "[TODO: Describe the legal skill and when to use it. Include trigger conditions.]"
---

# $(echo "$SKILL_NAME" | sed 's/-/ /g' | awk '{for(i=1;i<=NF;i++) $i=toupper(substr($i,1,1)) tolower(substr($i,2))}1')

[TODO: Brief introduction explaining the legal problem this skill addresses]

## Quick Reference

| Situation | Recommended Action |
|-----------|-------------------|
| [Legal trigger] | [What to do] |

## Background

[TODO: Why this matters — what clause risk, compliance gap, or regulatory issue it addresses]

## Recommended Action

[TODO: Step-by-step process improvement with clause language or compliance steps]

## Verification

[TODO: How to verify the improvement was effective — counsel review, audit, compliance check]

## CRITICAL REMINDER

NEVER include privileged attorney-client communications, specific case strategy,
or confidential settlement terms in this skill. Abstract to process-level lessons only.

## Related Standards

- Regulation: [TODO: GDPR / CCPA / SOX / HIPAA / EU AI Act]
- Jurisdiction: [TODO: US-Federal / US-CA / EU / UK]

## Source

This skill was extracted from a legal finding.
- Entry ID: [TODO: LRN-YYYYMMDD-XXX or LEG-YYYYMMDD-XXX]
- Original File: .learnings/LEARNINGS.md or .learnings/LEGAL_ISSUES.md
TEMPLATE
    echo "---"
    exit 0
fi

log_info "Creating legal skill: $SKILL_NAME"

mkdir -p "$SKILL_PATH"

cat > "$SKILL_PATH/SKILL.md" << TEMPLATE
---
name: $SKILL_NAME
description: "[TODO: Describe the legal skill and when to use it. Include trigger conditions.]"
---

# $(echo "$SKILL_NAME" | sed 's/-/ /g' | awk '{for(i=1;i<=NF;i++) $i=toupper(substr($i,1,1)) tolower(substr($i,2))}1')

[TODO: Brief introduction explaining the legal problem this skill addresses]

## Quick Reference

| Situation | Recommended Action |
|-----------|-------------------|
| [Legal trigger] | [What to do] |

## Background

[TODO: Why this matters — what clause risk, compliance gap, or regulatory issue it addresses]

## Recommended Action

[TODO: Step-by-step process improvement with clause language or compliance steps]

## Verification

[TODO: How to verify the improvement was effective — counsel review, audit, compliance check]

## CRITICAL REMINDER

NEVER include privileged attorney-client communications, specific case strategy,
or confidential settlement terms in this skill. Abstract to process-level lessons only.

## Related Standards

- Regulation: [TODO: GDPR / CCPA / SOX / HIPAA / EU AI Act]
- Jurisdiction: [TODO: US-Federal / US-CA / EU / UK]

## Source

This skill was extracted from a legal finding.
- Entry ID: [TODO: LRN-YYYYMMDD-XXX or LEG-YYYYMMDD-XXX]
- Original File: .learnings/LEARNINGS.md or .learnings/LEGAL_ISSUES.md
TEMPLATE

log_info "Created: $SKILL_PATH/SKILL.md"

echo ""
log_info "Legal skill scaffold created."
echo ""
echo "Next steps:"
echo "  1. Edit $SKILL_PATH/SKILL.md"
echo "  2. Fill in TODO sections with content from your finding"
echo "  3. Verify NO privileged communications, case strategy, or confidential terms are included"
echo "  4. Add references/ folder for regulatory mappings"
echo "  5. Add scripts/ folder for compliance checkers or automation"
echo "  6. Update the original entry with:"
echo "     **Status**: promoted_to_skill"
echo "     **Skill-Path**: skills/$SKILL_NAME"
