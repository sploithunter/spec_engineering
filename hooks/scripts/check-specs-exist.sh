#!/usr/bin/env bash
# PreToolUse hook: Warns if writing source code without .gwt specs
# This is advisory only — it does not block the operation.

set -euo pipefail

# Only check if specs/ directory doesn't exist or is empty
SPECS_DIR="specs"

if [ ! -d "$SPECS_DIR" ]; then
    echo "WARNING: No specs/ directory found. Consider writing behavioral specs (.gwt files) before implementing source code."
    echo "Run /spec-eng to start the ATDD workflow."
    exit 0
fi

GWT_COUNT=$(find "$SPECS_DIR" -name "*.gwt" -type f 2>/dev/null | wc -l | tr -d ' ')

if [ "$GWT_COUNT" -eq 0 ]; then
    echo "WARNING: No .gwt spec files found in specs/. Consider writing behavioral specs before implementing source code."
    echo "Run /spec-eng to start the ATDD workflow."
fi

exit 0
