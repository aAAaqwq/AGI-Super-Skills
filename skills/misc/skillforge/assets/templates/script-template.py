#!/usr/bin/env python3
"""
{{SCRIPT_NAME}}.py - {{BRIEF_DESCRIPTION}}

Part of the {{SKILL_NAME}} skill.

Responsibilities:
- {{RESPONSIBILITY_1}}
- {{RESPONSIBILITY_2}}

Usage:
    python {{SCRIPT_NAME}}.py <required_arg> [--optional-flag]
    python {{SCRIPT_NAME}}.py --help

Examples:
    python {{SCRIPT_NAME}}.py input.json
    python {{SCRIPT_NAME}}.py input.json --verbose --output result.json

Exit Codes:
    0  - Success
    1  - General failure
    2  - Invalid arguments
    3  - File not found
    10 - Validation failure
    11 - Verification failure
"""

import argparse
import json
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import List, Tuple, Optional, Any


# ===========================================================================
# RESULT TYPES
# ===========================================================================

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


# ===========================================================================
# STATE MANAGEMENT (remove if not needed)
# ===========================================================================

def get_state_dir() -> Path:
    """Get the state directory for this skill."""
    return Path.home() / ".cache" / "{{SKILL_NAME}}"


def get_state_path(project_name: str = "default") -> Path:
    """Get the state file path for a project."""
    safe_name = project_name.lower().replace(" ", "-").replace("/", "-")
    return get_state_dir() / f"{safe_name}.json"


def load_state(path: Optional[Path] = None) -> dict:
    """
    Load persisted state with graceful fallback.

    Args:
        path: State file path (default: uses default project)

    Returns:
        State dictionary, empty state if file doesn't exist
    """
    if path is None:
        path = get_state_path()

    if not path.exists():
        return {
            "version": "1.0",
            "created_at": datetime.now().isoformat(),
            "data": {}
        }

    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError:
        # Backup corrupted file and return fresh state
        backup = path.with_suffix(".json.bak")
        path.rename(backup)
        return {
            "version": "1.0",
            "created_at": datetime.now().isoformat(),
            "data": {},
            "recovered_from": str(backup)
        }


def save_state(state: dict, path: Optional[Path] = None) -> None:
    """
    Save state to disk atomically.

    Args:
        state: State dictionary to save
        path: State file path (default: uses default project)
    """
    if path is None:
        path = get_state_path()

    path.parent.mkdir(parents=True, exist_ok=True)
    state["updated_at"] = datetime.now().isoformat()

    # Write to temp file first for atomic save
    temp_path = path.with_suffix(".json.tmp")
    temp_path.write_text(json.dumps(state, indent=2))
    temp_path.rename(path)


# ===========================================================================
# CORE LOGIC
# ===========================================================================

def process(input_path: Path, options: dict) -> Result:
    """
    Main processing logic.

    Args:
        input_path: Path to input file
        options: Dictionary of options from command line

    Returns:
        Result object with success status and data
    """
    errors: List[str] = []
    warnings: List[str] = []

    # ----- Input Validation -----
    if not input_path.exists():
        return Result(
            success=False,
            message=f"Input file not found: {input_path}",
            errors=[f"File not found: {input_path}"]
        )

    # ----- Processing -----
    # TODO: Implement core logic here
    #
    # Example:
    # try:
    #     data = json.loads(input_path.read_text())
    #     result = transform(data)
    #     return Result(
    #         success=True,
    #         message="Processing complete",
    #         data=result
    #     )
    # except Exception as e:
    #     return Result(
    #         success=False,
    #         message=str(e),
    #         errors=[str(e)]
    #     )

    return Result(
        success=True,
        message="Processing complete",
        data={"processed": True},
        warnings=warnings
    )


def verify_result(result: Result) -> Tuple[bool, str]:
    """
    Self-verification of the result.

    Args:
        result: The Result object to verify

    Returns:
        Tuple of (is_valid, verification_message)
    """
    if not result.success:
        return False, f"Processing failed: {result.message}"

    # ----- Add verification logic specific to this script -----
    # TODO: Implement verification
    #
    # Example:
    # if "required_field" not in result.data:
    #     return False, "Missing required field in output"
    #
    # if result.data.get("count", 0) == 0:
    #     return False, "No items were processed"

    return True, "Verification passed"


# ===========================================================================
# CLI INTERFACE
# ===========================================================================

def main():
    parser = argparse.ArgumentParser(
        description="{{BRIEF_DESCRIPTION}}",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s input.json
  %(prog)s input.json --verbose
  %(prog)s input.json --output result.json --json
        """
    )

    # ----- Required Arguments -----
    parser.add_argument(
        "input",
        type=Path,
        help="Path to input file"
    )

    # ----- Optional Arguments -----
    parser.add_argument(
        "--output", "-o",
        type=Path,
        help="Output file path (default: stdout)"
    )

    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose output"
    )

    parser.add_argument(
        "--json",
        action="store_true",
        help="Output results as JSON"
    )

    parser.add_argument(
        "--no-verify",
        action="store_true",
        help="Skip self-verification step"
    )

    args = parser.parse_args()

    # ----- Process -----
    options = {
        "verbose": args.verbose,
    }

    if args.verbose:
        print(f"Processing: {args.input}", file=sys.stderr)

    result = process(args.input, options)

    # ----- Self-Verify -----
    if not args.no_verify and result.success:
        is_valid, verify_msg = verify_result(result)
        if not is_valid:
            if args.json:
                print(json.dumps({
                    "success": False,
                    "error": f"Verification failed: {verify_msg}"
                }))
            else:
                print(f"Verification failed: {verify_msg}", file=sys.stderr)
            sys.exit(11)  # Verification failure

    # ----- Output -----
    if args.json:
        print(json.dumps(result.to_dict(), indent=2))
    else:
        if result.success:
            print(f"Success: {result.message}")
            if args.verbose:
                for key, value in result.data.items():
                    print(f"  {key}: {value}")
        else:
            print(f"Failed: {result.message}", file=sys.stderr)
            for error in result.errors:
                print(f"  Error: {error}", file=sys.stderr)

        for warning in result.warnings:
            print(f"  Warning: {warning}", file=sys.stderr)

    # ----- Write to File -----
    if args.output and result.success:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result.data, indent=2))
        if not args.json:
            print(f"Output written to: {args.output}")

    # ----- Exit -----
    sys.exit(0 if result.success else 1)


if __name__ == "__main__":
    main()
