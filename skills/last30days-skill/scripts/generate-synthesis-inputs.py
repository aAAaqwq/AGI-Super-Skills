#!/usr/bin/env python3
"""Convert JSON result files to compact markdown using render_compact().

Reads from docs/comparison-results/json/, writes to docs/comparison-results/compact/.
Uses the current checkout's render_compact() - since version differences are in the
DATA (cross_refs, HN items, YouTube relevance), not in the render function.
"""
import json
import sys
from pathlib import Path

# Add scripts/ to path so we can import lib
sys.path.insert(0, str(Path(__file__).parent))

from lib.schema import Report
from lib.render import render_compact, render_source_status

JSON_DIR = Path(__file__).parent.parent / "docs" / "comparison-results" / "json"
COMPACT_DIR = Path(__file__).parent.parent / "docs" / "comparison-results" / "compact"
COMPACT_DIR.mkdir(parents=True, exist_ok=True)

files = sorted(JSON_DIR.glob("*.json"))
files = [f for f in files if f.name != "diagnose-baseline.json"]

print(f"Converting {len(files)} JSON files to compact markdown...\n")

for json_file in files:
    with open(json_file) as f:
        data = json.load(f)

    report = Report.from_dict(data)
    compact = render_compact(report)
    source_status = render_source_status(report)
    full_output = compact + "\n" + source_status

    md_file = COMPACT_DIR / json_file.name.replace(".json", ".md")
    md_file.write_text(full_output)

    # Summary stats
    n_reddit = len(report.reddit)
    n_x = len(report.x)
    n_yt = len(report.youtube)
    n_hn = len(report.hackernews)
    n_web = len(report.web)
    xrefs = sum(1 for r in report.reddit if r.cross_refs)
    xrefs += sum(1 for x in report.x if x.cross_refs)
    xrefs += sum(1 for y in report.youtube if y.cross_refs)
    xrefs += sum(1 for h in report.hackernews if h.cross_refs)

    print(f"  {json_file.name:40s} -> {len(full_output):5d} chars "
          f"(R:{n_reddit} X:{n_x} YT:{n_yt} HN:{n_hn} W:{n_web} xref:{xrefs})")

print(f"\nDone. {len(files)} compact files written to {COMPACT_DIR}")
