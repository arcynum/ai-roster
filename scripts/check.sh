#!/usr/bin/env bash
set -euo pipefail
echo "=== ruff check ==="
.venv/bin/ruff check .
echo "=== ty check ==="
.venv/bin/ty check . --ignore unresolved-attribute --ignore invalid-method-override --ignore invalid-type-form --ignore no-matching-overload --ignore invalid-assignment
echo "=== pytest ==="
.venv/bin/python -m pytest tests/
