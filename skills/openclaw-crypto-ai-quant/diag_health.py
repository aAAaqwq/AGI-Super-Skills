#!/usr/bin/env python3
import os, sys, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

os.environ.setdefault("AI_QUANT_WS_SOURCE", "sidecar")
os.environ.setdefault("AI_QUANT_WS_SIDECAR_SOCK", f"/run/user/{os.getuid()}/openclaw-ai-quant-ws.sock")

from exchange.sidecar import SidecarWSClient

client = SidecarWSClient()
health = client.candles_health(symbols=["BTC", "ETH"], interval="30m")
print(json.dumps(health, indent=2))
