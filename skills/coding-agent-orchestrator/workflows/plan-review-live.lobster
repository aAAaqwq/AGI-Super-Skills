name: plan-review-live
description: Interactive live plan review checkpoints for Architecture, Code Quality, Tests, and Performance
args:
  script_dir:
    description: Absolute path to plan-review-lobster scripts directory
  repo_path:
    description: Absolute path to target repository
  base_branch:
    description: Base branch for review context
  plan_path:
    description: Absolute path to plan markdown
  current_branch:
    description: Current git branch
  head_sha:
    description: HEAD commit sha
  system_prompt_file:
    description: Absolute path to plan-review system prompt
  section_timeout:
    description: Max seconds per section
    default: "600"
  total_deadline_epoch:
    description: Absolute epoch second deadline for whole run
  model:
    description: Optional codex model
    default: ""

steps:
  - id: architecture
    command: >-
      bash "${script_dir}/section-step.sh"
      --section "Architecture"
      --instruction "Run only Architecture review. Identify up to 4 top issues with options and explicit recommendation. End by asking for decision labels."
      --repo "${repo_path}"
      --base "${base_branch}"
      --plan "${plan_path}"
      --current-branch "${current_branch}"
      --head-sha "${head_sha}"
      --system-prompt-file "${system_prompt_file}"
      --section-timeout "${section_timeout}"
      --total-deadline-epoch "${total_deadline_epoch}"
      --model "${model}"
    approval: required

  - id: code_quality
    command: >-
      bash "${script_dir}/section-step.sh"
      --section "Code Quality"
      --instruction "Run only Code Quality review. Identify up to 4 top issues with options and explicit recommendation. End by asking for decision labels."
      --repo "${repo_path}"
      --base "${base_branch}"
      --plan "${plan_path}"
      --current-branch "${current_branch}"
      --head-sha "${head_sha}"
      --system-prompt-file "${system_prompt_file}"
      --section-timeout "${section_timeout}"
      --total-deadline-epoch "${total_deadline_epoch}"
      --model "${model}"
    approval: required

  - id: tests
    command: >-
      bash "${script_dir}/section-step.sh"
      --section "Tests"
      --instruction "Run only Test review. Include ASCII test diagram and coverage/eval gaps. End by asking for decision labels."
      --repo "${repo_path}"
      --base "${base_branch}"
      --plan "${plan_path}"
      --current-branch "${current_branch}"
      --head-sha "${head_sha}"
      --system-prompt-file "${system_prompt_file}"
      --section-timeout "${section_timeout}"
      --total-deadline-epoch "${total_deadline_epoch}"
      --model "${model}"
    approval: required

  - id: performance
    command: >-
      bash "${script_dir}/section-step.sh"
      --section "Performance"
      --instruction "Run only Performance review. Identify up to 4 top issues with options and explicit recommendation. End by asking for decision labels."
      --repo "${repo_path}"
      --base "${base_branch}"
      --plan "${plan_path}"
      --current-branch "${current_branch}"
      --head-sha "${head_sha}"
      --system-prompt-file "${system_prompt_file}"
      --section-timeout "${section_timeout}"
      --total-deadline-epoch "${total_deadline_epoch}"
      --model "${model}"
    approval: required

  - id: done
    command: echo '{"status":"ok"}'
