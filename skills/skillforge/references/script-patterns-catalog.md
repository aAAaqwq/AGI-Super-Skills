# Script Patterns Catalog

Standard Python patterns for skill scripts, derived from successful implementations across the ecosystem. These patterns ensure consistency, reliability, and agentic capability.

---

## Core Patterns

### Pattern 1: Result Dataclass

Standard result object for all script operations.

```python
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Any

@dataclass
class Result:
    """
    Standard result object for script operations.

    Attributes:
        success: Whether the operation succeeded
        message: Human-readable summary
        data: Any output data from the operation
        errors: List of error messages
        warnings: List of warning messages
    """
    success: bool
    message: str
    data: dict = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def __bool__(self) -> bool:
        """Allow Result to be used in boolean context."""
        return self.success

    def to_dict(self) -> dict:
        """Serialize to dictionary for JSON output."""
        return {
            "success": self.success,
            "message": self.message,
            "data": self.data,
            "errors": self.errors,
            "warnings": self.warnings,
            "timestamp": datetime.now().isoformat()
        }

# Usage
def process_file(path: Path) -> Result:
    errors = []

    if not path.exists():
        return Result(
            success=False,
            message=f"File not found: {path}",
            errors=[f"File not found: {path}"]
        )

    # Process...
    return Result(
        success=True,
        message="Processing complete",
        data={"processed_lines": 42}
    )
```

**When to Use:** Every script that returns a status.

---

### Pattern 2: ValidationResult Class

Specialized result for validation scripts with check tracking.

```python
from dataclasses import dataclass, field
from typing import List, Tuple

@dataclass
class ValidationResult:
    """
    Result object for validation scripts with detailed check tracking.
    """
    passed: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)

    def check(self, name: str, condition: bool, message: str, warning_only: bool = False):
        """Record a validation check result."""
        if condition:
            self.passed.append(f"[PASS] {name}: {message}")
        elif warning_only:
            self.warnings.append(f"[WARN] {name}: {message}")
        else:
            self.errors.append(f"[FAIL] {name}: {message}")

    @property
    def is_valid(self) -> bool:
        """True if no errors (warnings are OK)."""
        return len(self.errors) == 0

    @property
    def summary(self) -> str:
        """Human-readable summary."""
        total = len(self.passed) + len(self.warnings) + len(self.errors)
        return f"{len(self.passed)}/{total} checks passed, {len(self.warnings)} warnings, {len(self.errors)} errors"

    def format_report(self, title: str = "Validation Report") -> str:
        """Generate formatted report."""
        lines = [
            "=" * 60,
            title.center(60),
            "=" * 60,
            "",
            f"Summary: {self.summary}",
            ""
        ]

        if self.errors:
            lines.append("ERRORS:")
            lines.extend(f"  {e}" for e in self.errors)
            lines.append("")

        if self.warnings:
            lines.append("WARNINGS:")
            lines.extend(f"  {w}" for w in self.warnings)
            lines.append("")

        if self.passed:
            lines.append("PASSED:")
            lines.extend(f"  {p}" for p in self.passed)

        lines.append("=" * 60)
        return "\n".join(lines)

# Usage
def validate_skill(path: Path) -> ValidationResult:
    result = ValidationResult()

    result.check(
        "file_exists",
        path.exists(),
        f"SKILL.md exists at {path}"
    )

    content = path.read_text() if path.exists() else ""

    result.check(
        "has_frontmatter",
        content.startswith("---"),
        "File has YAML frontmatter"
    )

    result.check(
        "has_triggers",
        "## Triggers" in content or "trigger" in content.lower(),
        "File has trigger phrases",
        warning_only=True  # Warning, not error
    )

    return result
```

**When to Use:** Validation scripts that check multiple criteria.

---

### Pattern 3: Argparse with Subcommands

Modular CLI interface for multi-operation scripts.

```python
import argparse
import sys

def cmd_init(args):
    """Handle 'init' subcommand."""
    print(f"Initializing: {args.name}")
    return 0

def cmd_run(args):
    """Handle 'run' subcommand."""
    print(f"Running with verbose={args.verbose}")
    return 0

def cmd_status(args):
    """Handle 'status' subcommand."""
    print("Status: OK")
    return 0

def main():
    parser = argparse.ArgumentParser(
        description="Multi-command script example",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s init "My Project"
  %(prog)s run --verbose
  %(prog)s status
        """
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Subcommand: init
    init_parser = subparsers.add_parser("init", help="Initialize a new project")
    init_parser.add_argument("name", help="Project name")
    init_parser.add_argument("--description", "-d", help="Project description")

    # Subcommand: run
    run_parser = subparsers.add_parser("run", help="Run the process")
    run_parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    run_parser.add_argument("--dry-run", action="store_true", help="Don't make changes")

    # Subcommand: status
    status_parser = subparsers.add_parser("status", help="Show current status")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    # Dispatch to handler
    handlers = {
        "init": cmd_init,
        "run": cmd_run,
        "status": cmd_status,
    }

    exit_code = handlers[args.command](args)
    sys.exit(exit_code)

if __name__ == "__main__":
    main()
```

**When to Use:** Scripts with multiple distinct operations (state management, trackers).

---

### Pattern 4: Simple Argparse

For single-purpose scripts.

```python
import argparse
import sys
from pathlib import Path

def main():
    parser = argparse.ArgumentParser(
        description="Validate a skill directory"
    )

    # Positional argument
    parser.add_argument(
        "path",
        type=Path,
        help="Path to skill directory"
    )

    # Optional flags
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Show detailed output"
    )

    parser.add_argument(
        "--json",
        action="store_true",
        help="Output as JSON"
    )

    parser.add_argument(
        "--strict",
        action="store_true",
        help="Treat warnings as errors"
    )

    args = parser.parse_args()

    # Validate input
    if not args.path.exists():
        print(f"Error: Path not found: {args.path}", file=sys.stderr)
        sys.exit(2)

    # Process
    result = validate(args.path, verbose=args.verbose)

    # Output
    if args.json:
        print(json.dumps(result.to_dict()))
    else:
        print(result.format_report())

    sys.exit(0 if result.is_valid else 1)

if __name__ == "__main__":
    main()
```

**When to Use:** Single-purpose scripts (validation, generation, transformation).

---

### Pattern 5: JSON State Persistence

For tracking state across sessions.

```python
from pathlib import Path
from datetime import datetime
import json
import os

def get_state_dir(skill_name: str) -> Path:
    """Get XDG-compliant state directory."""
    xdg_cache = os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")
    return Path(xdg_cache) / skill_name

def get_state_path(skill_name: str, project_name: str = "default") -> Path:
    """Get state file path for a project."""
    safe_name = project_name.lower().replace(" ", "-").replace("/", "-")
    return get_state_dir(skill_name) / f"{safe_name}.json"

def load_state(path: Path) -> dict:
    """Load state with graceful fallback on corruption."""
    if not path.exists():
        return {
            "version": "1.0",
            "created_at": datetime.now().isoformat(),
            "data": {}
        }

    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError:
        # Backup corrupted file
        backup = path.with_suffix(".json.bak")
        path.rename(backup)
        return {
            "version": "1.0",
            "created_at": datetime.now().isoformat(),
            "data": {},
            "recovered_from": str(backup)
        }

def save_state(path: Path, state: dict) -> None:
    """Save state atomically."""
    path.parent.mkdir(parents=True, exist_ok=True)
    state["updated_at"] = datetime.now().isoformat()

    # Write to temp file first (atomic save)
    temp_path = path.with_suffix(".json.tmp")
    temp_path.write_text(json.dumps(state, indent=2))
    temp_path.rename(path)

# Usage
def main():
    state_path = get_state_path("my-skill", "my-project")
    state = load_state(state_path)

    # Modify state
    state["data"]["last_run"] = datetime.now().isoformat()
    state["data"]["runs"] = state["data"].get("runs", 0) + 1

    save_state(state_path, state)
    print(f"State saved. Total runs: {state['data']['runs']}")
```

**When to Use:** Progress tracking, multi-session workflows, caching.

---

### Pattern 6: Graceful Dependency Fallback

Handle optional dependencies gracefully.

```python
# YAML parsing with fallback
def parse_yaml(text: str) -> dict:
    """Parse YAML with graceful fallback if PyYAML not installed."""
    try:
        import yaml
        return yaml.safe_load(text)
    except ImportError:
        # Fallback: basic key-value parsing for simple YAML
        result = {}
        current_key = None
        for line in text.split('\n'):
            stripped = line.strip()
            if not stripped or stripped.startswith('#'):
                continue
            if ':' in line and not line.startswith(' '):
                key, value = line.split(':', 1)
                key = key.strip()
                value = value.strip()
                if value:
                    # Remove quotes if present
                    if (value.startswith('"') and value.endswith('"')) or \
                       (value.startswith("'") and value.endswith("'")):
                        value = value[1:-1]
                    result[key] = value
                else:
                    result[key] = {}
                    current_key = key
        return result

# Rich output with fallback
def print_styled(message: str, style: str = "normal"):
    """Print with optional rich styling."""
    try:
        from rich.console import Console
        console = Console()
        styles = {
            "success": "[green]",
            "error": "[red]",
            "warning": "[yellow]",
            "normal": ""
        }
        prefix = styles.get(style, "")
        console.print(f"{prefix}{message}")
    except ImportError:
        # Fallback: plain output with emoji
        prefixes = {
            "success": "[OK] ",
            "error": "[ERROR] ",
            "warning": "[WARN] ",
            "normal": ""
        }
        print(f"{prefixes.get(style, '')}{message}")
```

**When to Use:** When using non-stdlib libraries, always provide fallback.

---

### Pattern 7: Exit Code Conventions

Consistent exit codes for script chaining.

```python
import sys
from enum import IntEnum

class ExitCode(IntEnum):
    """Standard exit codes for skill scripts."""
    SUCCESS = 0
    GENERAL_ERROR = 1
    INVALID_ARGUMENTS = 2
    FILE_NOT_FOUND = 3
    PERMISSION_DENIED = 4
    VALIDATION_FAILED = 10
    VERIFICATION_FAILED = 11
    DEPENDENCY_ERROR = 20
    NETWORK_ERROR = 21
    TIMEOUT = 30

def main():
    try:
        result = process()

        if not result.success:
            if "validation" in result.message.lower():
                sys.exit(ExitCode.VALIDATION_FAILED)
            sys.exit(ExitCode.GENERAL_ERROR)

        sys.exit(ExitCode.SUCCESS)

    except FileNotFoundError:
        sys.exit(ExitCode.FILE_NOT_FOUND)
    except PermissionError:
        sys.exit(ExitCode.PERMISSION_DENIED)
    except TimeoutError:
        sys.exit(ExitCode.TIMEOUT)
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        sys.exit(ExitCode.GENERAL_ERROR)
```

**When to Use:** All scripts should use explicit exit codes.

---

### Pattern 8: Progress Visualization

ASCII-based progress display.

```python
def render_progress_bar(current: int, total: int, width: int = 40) -> str:
    """Render ASCII progress bar."""
    if total == 0:
        return f"[{'?' * width}] 0%"

    ratio = current / total
    filled = int(ratio * width)
    empty = width - filled

    bar = "=" * filled + "-" * empty
    percent = ratio * 100

    return f"[{bar}] {percent:.1f}% ({current}/{total})"

def render_status_icon(status: str) -> str:
    """Render status as ASCII icon."""
    icons = {
        "pending": "[ ]",
        "in_progress": "[>]",
        "completed": "[x]",
        "verified": "[V]",
        "failed": "[!]",
        "skipped": "[-]",
    }
    return icons.get(status, "[?]")

def render_tree(items: list, indent: int = 0) -> str:
    """Render hierarchical tree structure."""
    lines = []
    for i, item in enumerate(items):
        is_last = i == len(items) - 1
        prefix = "  " * indent + ("'" if is_last else "|") + "-- "
        status = render_status_icon(item.get("status", "pending"))
        lines.append(f"{prefix}{status} {item['name']}")

        if item.get("children"):
            child_lines = render_tree(item["children"], indent + 1)
            lines.append(child_lines)

    return "\n".join(lines)

# Usage
print(render_progress_bar(7, 10))
# Output: [============================------------] 70.0% (7/10)

print(render_tree([
    {"name": "Phase 1", "status": "completed", "children": [
        {"name": "Step 1.1", "status": "completed"},
        {"name": "Step 1.2", "status": "completed"},
    ]},
    {"name": "Phase 2", "status": "in_progress", "children": [
        {"name": "Step 2.1", "status": "in_progress"},
        {"name": "Step 2.2", "status": "pending"},
    ]},
]))
```

**When to Use:** Progress tracking, status dashboards, visual feedback.

---

### Pattern 9: Self-Verification

Scripts that verify their own outputs.

```python
def execute_with_verification(input_data, verify_func):
    """
    Execute an operation and verify the result.

    Args:
        input_data: Input to process
        verify_func: Function that returns (is_valid, reason)

    Returns:
        Result with success based on verification
    """
    try:
        # Execute
        output = process(input_data)

        # Verify
        is_valid, reason = verify_func(output)

        if not is_valid:
            return Result(
                success=False,
                message=f"Verification failed: {reason}",
                data={"output": output, "verification": reason},
                errors=[reason]
            )

        return Result(
            success=True,
            message="Operation completed and verified",
            data={"output": output, "verified": True}
        )

    except Exception as e:
        return Result(
            success=False,
            message=f"Execution failed: {e}",
            errors=[str(e)]
        )

# Example verification functions
def verify_json_output(output):
    """Verify output is valid JSON."""
    try:
        json.loads(output)
        return True, "Valid JSON"
    except json.JSONDecodeError as e:
        return False, f"Invalid JSON: {e}"

def verify_file_exists(path):
    """Verify file was created."""
    if Path(path).exists():
        return True, f"File exists: {path}"
    return False, f"File not created: {path}"

def verify_non_empty(output):
    """Verify output is non-empty."""
    if output and len(str(output).strip()) > 0:
        return True, "Output is non-empty"
    return False, "Output is empty"
```

**When to Use:** Any script that produces output that can be verified.

---

## Category Templates

### Validation Script Template

```python
#!/usr/bin/env python3
"""
validate_<target>.py - Validates <target> against <standard>

Usage:
    python validate_<target>.py <path>
    python validate_<target>.py <path> --strict
"""

import argparse
import sys
from pathlib import Path

# ... include ValidationResult class from Pattern 2 ...

def validate(path: Path, strict: bool = False) -> ValidationResult:
    """Validate the target."""
    result = ValidationResult()

    # Add your checks here
    result.check("example", True, "Example check passed")

    return result

def main():
    parser = argparse.ArgumentParser(description="Validate <target>")
    parser.add_argument("path", type=Path, help="Path to validate")
    parser.add_argument("--strict", action="store_true", help="Treat warnings as errors")
    parser.add_argument("--json", action="store_true", help="Output as JSON")

    args = parser.parse_args()

    result = validate(args.path, args.strict)

    if args.json:
        import json
        print(json.dumps({"valid": result.is_valid, "errors": result.errors, "warnings": result.warnings}))
    else:
        print(result.format_report())

    sys.exit(0 if result.is_valid else 1)

if __name__ == "__main__":
    main()
```

### State Management Script Template

```python
#!/usr/bin/env python3
"""
<name>_tracker.py - Track progress for <purpose>

Usage:
    python <name>_tracker.py init "Project Name"
    python <name>_tracker.py add-item "Item description"
    python <name>_tracker.py update <id> --status completed
    python <name>_tracker.py status
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

# ... include state management functions from Pattern 5 ...

def cmd_init(args):
    """Initialize a new project."""
    # Implementation
    pass

def cmd_add(args):
    """Add an item."""
    # Implementation
    pass

def cmd_update(args):
    """Update an item."""
    # Implementation
    pass

def cmd_status(args):
    """Show current status."""
    # Implementation
    pass

def main():
    parser = argparse.ArgumentParser(description="Track <purpose>")
    subparsers = parser.add_subparsers(dest="command")

    # Add subparsers...

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    handlers = {"init": cmd_init, "add": cmd_add, "update": cmd_update, "status": cmd_status}
    sys.exit(handlers[args.command](args))

if __name__ == "__main__":
    main()
```

### Generation Script Template

```python
#!/usr/bin/env python3
"""
generate_<artifact>.py - Generate <artifact> from <input>

Usage:
    python generate_<artifact>.py <input> --output <output>
"""

import argparse
import sys
from pathlib import Path
from string import Template

TEMPLATE = """
# Generated ${name}
# Created: ${timestamp}

${content}
"""

def generate(input_path: Path, output_path: Path) -> bool:
    """Generate artifact from input."""
    from datetime import datetime

    # Read input
    data = input_path.read_text()

    # Transform using template
    template = Template(TEMPLATE)
    result = template.substitute(
        name=input_path.stem,
        timestamp=datetime.now().isoformat(),
        content=data
    )

    # Write output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(result)

    # Verify
    if not output_path.exists():
        return False

    return True

def main():
    parser = argparse.ArgumentParser(description="Generate <artifact>")
    parser.add_argument("input", type=Path, help="Input file")
    parser.add_argument("--output", "-o", type=Path, required=True, help="Output file")

    args = parser.parse_args()

    if not args.input.exists():
        print(f"Error: Input not found: {args.input}", file=sys.stderr)
        sys.exit(2)

    success = generate(args.input, args.output)

    if success:
        print(f"Generated: {args.output}")
        sys.exit(0)
    else:
        print("Generation failed", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
```

---

## Quick Reference

| Pattern | Use Case | Key Imports |
|---------|----------|-------------|
| Result dataclass | Return values | `dataclasses`, `typing` |
| ValidationResult | Multi-check validation | `dataclasses`, `typing` |
| Argparse subcommands | Multi-operation scripts | `argparse` |
| Simple argparse | Single-purpose scripts | `argparse` |
| JSON state | State persistence | `json`, `pathlib` |
| Graceful fallback | Optional dependencies | try/except ImportError |
| Exit codes | Script chaining | `sys`, `enum` |
| Progress bars | Visual feedback | (stdlib only) |
| Self-verification | Autonomous operation | (pattern, not import) |

---

## Related References

- [Script Integration Framework](script-integration-framework.md) - When to use scripts
- [Script Template](../assets/templates/script-template.py) - Full starter template
