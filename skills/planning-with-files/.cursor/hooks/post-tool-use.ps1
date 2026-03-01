# planning-with-files: Post-tool-use hook for Cursor (PowerShell)
# Reminds the agent to update task_plan.md after file modifications.

Write-Output "[planning-with-files] File updated. If this completes a phase, update task_plan.md status."
exit 0
