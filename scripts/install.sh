#!/bin/bash
# ============================================================
# Token Saver Skill — copy into detected Agent skill dirs
# Supports: Claude Code / OpenClaw / Codex / OpenCode
# Not a runtime bootstrap; Python scripts mkdir ~/.agent on first run.
# ============================================================

set -e

SKILL_NAME="token-saver"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="$(dirname "$SCRIPT_DIR")"

echo "=== Token Saver Skill install ==="
echo ""

detect_agents() {
    local agents=()
    [ -d "$HOME/.claude" ] && agents+=("claude")
    [ -d "$HOME/.openclaw" ] && agents+=("openclaw")
    [ -d "$HOME/.codex" ] && agents+=("codex")
    [ -d "$HOME/.config/opencode" ] && agents+=("opencode")
    echo "${agents[@]}"
}

AGENTS=$(detect_agents)

if [ -z "$AGENTS" ]; then
    echo "No Agent environment detected. Install Claude Code / OpenClaw / Codex / OpenCode first," >&2
    echo "or create ~/.claude (etc.) and re-run, or copy this repo manually into skills/token-saver/." >&2
    exit 1
fi

echo "Detected: $AGENTS"
echo ""

for agent in $AGENTS; do
    case $agent in
        claude)
            TARGET="$HOME/.claude/skills/$SKILL_NAME"
            mkdir -p "$TARGET"
            cp -r "$SKILL_DIR"/* "$TARGET/"
            echo "Claude Code -> $TARGET"
            ;;
        openclaw)
            TARGET="$HOME/.openclaw/workspace/skills/$SKILL_NAME"
            mkdir -p "$TARGET"
            cp -r "$SKILL_DIR"/* "$TARGET/"
            echo "OpenClaw -> $TARGET"
            ;;
        codex)
            TARGET="$HOME/.codex/skills/$SKILL_NAME"
            mkdir -p "$TARGET"
            cp -r "$SKILL_DIR"/* "$TARGET/"
            echo "Codex -> $TARGET"
            ;;
        opencode)
            TARGET="$HOME/.config/opencode/skills/$SKILL_NAME"
            mkdir -p "$TARGET"
            cp -r "$SKILL_DIR"/* "$TARGET/"
            echo "OpenCode -> $TARGET"
            ;;
    esac
done

echo ""
echo "=== Done ==="
echo "Invoke: /token-saver (Claude), /skill token-saver (OpenClaw), @token-saver (Codex)"
echo "Runtime config: ~/.agent/token-saver/ (created on first python3 scripts/*.py run)"
