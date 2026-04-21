#!/usr/bin/env python3
"""Build a weighted decision matrix from JSON.

Input shape:
{
  "weights": {
    "business_fit": 15,
    "architecture_fit": 15
  },
  "options": [
    {
      "name": "Harness IDP",
      "scores": {
        "business_fit": 4,
        "architecture_fit": 5
      },
      "notes": {
        "business_fit": "Strong fit for managed Backstage-style IDP"
      }
    }
  ]
}
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


def load_input() -> dict:
    if len(sys.argv) > 1:
        return json.loads(Path(sys.argv[1]).read_text())
    return json.load(sys.stdin)


def main() -> int:
    payload = load_input()
    weights = payload["weights"]
    options = payload["options"]

    weight_total = sum(weights.values())
    if weight_total <= 0:
        raise SystemExit("weights must sum to a positive number")

    rows = []
    for option in options:
        weighted_total = 0.0
        score_total = 0.0
        for key, weight in weights.items():
            score = option["scores"].get(key, 0)
            weighted_total += score * weight
            score_total += score
        normalized = weighted_total / weight_total
        rows.append(
            {
                "name": option["name"],
                "weighted_total": round(weighted_total, 2),
                "normalized_score": round(normalized, 2),
                "score_total": round(score_total, 2),
            }
        )

    rows.sort(key=lambda row: row["normalized_score"], reverse=True)
    print(json.dumps({"ranked_options": rows}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
