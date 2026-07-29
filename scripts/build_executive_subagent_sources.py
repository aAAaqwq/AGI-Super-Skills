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
SOURCE_FILES = {
    "cco": {
        "xiaohongshu-operator": "marketing/marketing-xiaohongshu-operator.md",
        "douyin-strategist": "marketing/marketing-douyin-strategist.md",
        "wechat-operator": "marketing/marketing-wechat-operator.md",
        "bilibili-strategist": "marketing/marketing-bilibili-strategist.md",
        "short-video-editing-coach": "marketing/marketing-short-video-editing-coach.md",
        "weixin-channels-strategist": "marketing/marketing-weixin-channels-strategist.md",
        "knowledge-commerce-strategist": "marketing/marketing-knowledge-commerce-strategist.md",
        "xiaohongshu-specialist": "marketing/marketing-xiaohongshu-specialist.md",
        "wechat-official-account-manager": "marketing/marketing-wechat-official-account.md",
        "zhihu-strategist": "marketing/marketing-zhihu-strategist.md",
        "twitter-engager": "marketing/marketing-twitter-engager.md",
        "instagram-curator": "marketing/marketing-instagram-curator.md",
        "reddit-community-operator": "marketing/marketing-reddit-community-builder.md",
        "video-optimization-specialist": "marketing/marketing-video-optimization-specialist.md",
        "growth-hacker": "marketing/marketing-growth-hacker.md",
        "seo-specialist": "marketing/marketing-seo-specialist.md",
        "ai-citation-strategist": "marketing/marketing-ai-citation-strategist.md",
        "prompt-engineer": "specialized/prompt-engineer.md",
        "content-illustration-planner": "design/design-image-prompt-engineer.md",
    },
    "cto": {
        "frontend-developer": "engineering/engineering-frontend-developer.md",
        "backend-architect": "engineering/engineering-backend-architect.md",
        "ai-engineer": "engineering/engineering-ai-engineer.md",
        "devops-automator": "engineering/engineering-devops-automator.md",
        "security-engineer": "engineering/engineering-security-engineer.md",
        "rapid-prototyper": "engineering/engineering-rapid-prototyper.md",
        "senior-developer": "engineering/engineering-senior-developer.md",
        "mobile-app-builder": "engineering/engineering-mobile-app-builder.md",
        "data-engineer": "engineering/engineering-data-engineer.md",
        "technical-writer": "engineering/engineering-technical-writer.md",
        "autonomous-optimization-architect": "engineering/engineering-autonomous-optimization-architect.md",
        "embedded-firmware-engineer": "engineering/engineering-embedded-firmware-engineer.md",
        "pc-host-engineer": "engineering/engineering-pc-host-engineer.md",
        "mechanical-design-engineer": "engineering/engineering-mechanical-design-engineer.md",
        "embedded-linux-driver-engineer": "engineering/engineering-embedded-linux-driver-engineer.md",
        "fpga-digital-design-engineer": "engineering/engineering-fpga-digital-design-engineer.md",
        "iot-solution-architect": "engineering/engineering-iot-solution-architect.md",
        "network-engineer-china": "engineering/engineering-network-engineer-china.md",
        "incident-response-commander": "engineering/engineering-incident-response-commander.md",
        "threat-detection-engineer": "engineering/engineering-threat-detection-engineer.md",
        "solidity-smart-contract-engineer": "engineering/engineering-solidity-smart-contract-engineer.md",
        "wechat-mini-program-developer": "engineering/engineering-wechat-mini-program-developer.md",
    },
    "cpo": {
        "ui-designer": "design/design-ui-designer.md",
        "ux-researcher": "design/design-ux-researcher.md",
        "ux-architect": "design/design-ux-architect.md",
    },
}


def build(root: Path) -> dict:
    entries = []
    for manager, specialists in SOURCE_FILES.items():
        for specialist_id, source_path in specialists.items():
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
