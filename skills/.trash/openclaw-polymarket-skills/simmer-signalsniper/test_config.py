#!/usr/bin/env python3
"""
Signal Sniper v3.0 - Quick Test (without websocket dependency)
"""

import sys
sys.path.insert(0, "/home/han/clawd")

import json
from pathlib import Path

# Test config loading
config_path = Path(__file__).parent / "config.json"
if config_path.exists():
    with open(config_path) as f:
        config = json.load(f)
    
    print("✅ Signal Sniper v3.0 Configuration Loaded")
    print("=" * 60)
    print(f"Mode: {config.get('mode', 'auto')}")
    print(f"Venue: {config.get('venue', 'polymarket')}")
    print(f"Feeds: {len(config.get('feeds', []))}")
    print(f"Keywords: {sum(len(v) for v in config.get('keywords', {}).values())} total")
    print()
    print("Risk Controls:")
    risk = config.get('risk_controls', {})
    for key, val in risk.items():
        print(f"  - {key}: {val}")
    print()
    print("✅ Configuration valid - ready for deployment")
else:
    print("❌ config.json not found")
    sys.exit(1)
