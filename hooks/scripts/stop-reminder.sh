#!/usr/bin/env bash
# Stop hook: Reminds to verify both test streams pass and run gap analysis

set -euo pipefail

echo ""
echo "=== spec-eng reminder ==="
echo "Before pushing, verify:"
echo "  1. Acceptance tests pass:  pytest .spec-eng/generated/ -q"
echo "  2. Unit tests pass:        pytest tests/ -q"
echo "  3. Gap analysis is clean:  /spec-gaps"
echo "=========================="

exit 0
