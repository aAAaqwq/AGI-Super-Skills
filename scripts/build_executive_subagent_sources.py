#!/usr/bin/env python3
"""Build the provenance ledger for exact agency-agents-zh subagent copies."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import tempfile
from pathlib import Path


REPOSITORY = "https://github.com/jnMetaCode/agency-agents-zh"
COMMIT = "2ecfabf8e944ccdfed63ad8c44d5241290af6977"


def build(root: Path) -> dict:
    entries = []
    hierarchy = json.loads((root / "config/agent-hierarchy.json").read_text(encoding="utf-8"))
    for manager, settings in hierarchy["managers"].items():
        registry = json.loads((root / settings["routingFile"]).read_text(encoding="utf-8"))
        if registry["parent"] != manager:
            raise ValueError(f"routing parent mismatch: {manager}")
        specialists = registry["specialists"]
        if [item["id"] for item in specialists] != settings["subagents"]:
            raise ValueError(f"hierarchy and routing order differ: {manager}")
        for specialist in specialists:
            specialist_id = specialist["id"]
            source_path = specialist["sourcePath"]
            vendored_path = Path("agents") / manager / "subagents" / specialist_id / "AGENTS.md"
            content = (root / vendored_path).read_bytes()
            text = content.decode("utf-8")
            match = re.search(r"(?m)^name:\s*(.+?)\s*$", text)
            if not match:
                raise ValueError(f"missing frontmatter name: {vendored_path}")
            entries.append(
                {
                    "manager": manager,
                    "id": specialist_id,
                    "name": match.group(1),
                    "sourcePath": source_path,
                    "sourceUrl": f"{REPOSITORY}/blob/{COMMIT}/{source_path}",
                    "vendoredPath": vendored_path.as_posix(),
                    "sha256": hashlib.sha256(content).hexdigest(),
                    "copyMode": "verbatim",
                }
            )
    return {
        "schemaVersion": 1,
        "repository": REPOSITORY,
        "commit": COMMIT,
        "license": "MIT",
        "notice": "plugins/agi-super-team-codex/THIRD_PARTY_NOTICES.md",
        "entries": entries,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    root = args.root.resolve()
    destination = root / "config/agent-sources.lock.json"
    content = json.dumps(build(root), ensure_ascii=False, indent=2) + "\n"
    if args.check:
        if destination.is_symlink() or not destination.is_file() or destination.read_text(encoding="utf-8") != content:
            print("Executive subagent provenance ledger is stale")
            return 1
        return 0
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=destination.parent, delete=False) as handle:
        handle.write(content)
        temporary = Path(handle.name)
    temporary.replace(destination)
    print(f"Wrote {destination.relative_to(root)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
