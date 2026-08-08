#!/usr/bin/env bash
set -euo pipefail
echo "=== ruff check ==="
.venv/bin/ruff check .
echo "=== ty check ==="
.venv/bin/ty check .
echo "=== pytest ==="
.venv/bin/python -m pytest tests/
