#!/usr/bin/env python3
"""Test Polymarket Relayer API - gasless on-chain operations"""

import sys
sys.path.insert(0, '/home/aa/.local/lib/python3.12/site-packages')

from dotenv import load_dotenv
import os
import json

load_dotenv('${QUANT_WORKSPACE}/.env.polymarket')

PK = os.environ['POLY_PRIVATE_KEY']
PROXY = os.environ.get('POLY_PROXY_WALLET', os.environ.get('POLY_PROXY_ADDRESS'))

# CLOB API creds (derived from PK) - these are also Builder creds
CLOB_KEY = os.environ.get('POLY_CLOB_API_KEY', '')
CLOB_SECRET = os.environ.get('POLY_CLOB_API_SECRET', '')
CLOB_PASS = os.environ.get('POLY_CLOB_API_PASSPHRASE', '')

print("=== Step 1: Initialize Relayer Client ===")
from py_builder_relayer_client.client import RelayClient
from py_builder_signing_sdk.config import BuilderConfig
from py_builder_signing_sdk.sdk_types import BuilderApiKeyCreds

# Use CLOB creds as builder creds (same key/secret/passphrase)
builder_creds = BuilderApiKeyCreds(
    key=CLOB_KEY,
    secret=CLOB_SECRET,
    passphrase=CLOB_PASS,
)

builder_config = BuilderConfig(local_builder_creds=builder_creds)

# Relayer URL - need to find correct one
# From docs: relayer is separate from CLOB
RELAYER_URL = "https://relayer.polymarket.com"
# Also try: https://tx-gateway.polymarket.com

client = RelayClient(
    relayer_url=RELAYER_URL,
    chain_id=137,  # Polygon mainnet
    private_key=PK,
    builder_config=builder_config,
)

print(f"Signer address: {client.signer.address()}")
print(f"Expected safe: {client.get_expected_safe()}")
print(f"Target proxy: {PROXY}")

print("\n=== Step 2: Check if safe is deployed ===")
try:
    deployed = client.get_deployed(PROXY)
    print(f"Proxy deployed: {deployed}")
except Exception as e:
    print(f"Deploy check failed: {e}")

print("\n=== Step 3: Get nonce ===")
try:
    from py_builder_relayer_client.models import TransactionType
    nonce = client.get_nonce(client.signer.address(), TransactionType.SAFE.value)
    print(f"Nonce: {nonce}")
except Exception as e:
    print(f"Nonce check failed: {e}")

# Also try different relayer URLs
for url in ["https://tx-gateway.polymarket.com"]:
    print(f"\n=== Step 4: Try alt URL: {url} ===")
    client2 = RelayClient(
        relayer_url=url,
        chain_id=137,
        private_key=PK,
        builder_config=builder_config,
    )
    try:
        deployed = client2.get_deployed(PROXY)
        print(f"Proxy deployed (alt): {deployed}")
    except Exception as e:
        print(f"Alt deploy check failed: {e}")
