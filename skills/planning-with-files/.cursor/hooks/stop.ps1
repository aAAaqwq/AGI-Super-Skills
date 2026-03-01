# planning-with-files: Stop hook for Cursor (PowerShell)
# Checks if all phases in task_plan.md are complete.
# Returns followup_message to auto-continue if phases are incomplete.
# Always exits 0 — uses JSON stdout for control.

$PlanFile = "task_plan.md"

if (-not (Test-Path $PlanFile)) {
    exit 0
}

$content = Get-Content $PlanFile -Raw

$TOTAL = ([regex]::Matches($content, "### Phase")).Count

# Check for **Status:** format first
$COMPLETE = ([regex]::Matches($content, "\*\*Status:\*\* complete")).Count
$IN_PROGRESS = ([regex]::Matches($content, "\*\*Status:\*\* in_progress")).Count
$PENDING = ([regex]::Matches($content, "\*\*Status:\*\* pending")).Count

# Fallback: check for [complete] inline format
if ($COMPLETE -eq 0 -and $IN_PROGRESS -eq 0 -and $PENDING -eq 0) {
    $COMPLETE = ([regex]::Matches($content, "\[complete\]")).Count
    $IN_PROGRESS = ([regex]::Matches($content, "\[in_progress\]")).Count
    $PENDING = ([regex]::Matches($content, "\[pending\]")).Count
}

if ($COMPLETE -eq $TOTAL -and $TOTAL -gt 0) {
    exit 0
} else {
    Write-Host "{`"followup_message`": `"[planning-with-files] Task incomplete ($COMPLETE/$TOTAL phases done). Read task_plan.md and continue working on the remaining phases.`"}"
    exit 0
}
