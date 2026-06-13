#!/bin/sh
# Injects the outer_heaven core profile into Claude's context at session start.
# SessionStart hooks add stdout directly to context, so no JSON is needed.
# Uses only POSIX sh + sed + cat, so it runs under Git Bash on Windows and sh on macOS/Linux.
# No jq, no node, no bash-isms: maximum portability across machines.

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PLUGIN_DIR="$SCRIPT_DIR/../.."

VERSION=$(sed -n 's/.*"version": *"\([^"]*\)".*/\1/p' "$PLUGIN_DIR/.claude-plugin/plugin.json")

echo "[outer_heaven v$VERSION core profile]"
echo ""
cat "$SCRIPT_DIR/core-profile.md"
