#!/bin/bash
set -e
cd "$(dirname "$0")/.."
echo "=== Running server tests ==="
python3 -m pytest tests/test_server.py -v
echo "=== Running schema tests ==="
python3 -m pytest tests/test_data_schema.py -v
echo "=== Running frontend static analysis ==="
python3 -m pytest tests/test_frontend.py -v
echo "=== All tests passed ==="
