#!/usr/bin/env bash
#
# Claude Code PreToolUse hook: block git commit when staged src/ changes
# introduce new or changed functions/constants without a README.md update.
#
# Exits 0 (allow) when:
#   - no src/ files are staged
#   - no new functions, constants, or signature changes detected
#   - README.md is also staged
#
# Outputs deny JSON when src/ has meaningful API changes and README.md
# is not in this commit.

set -euo pipefail

staged_src_diff=$(git diff --cached -- 'src/' 2>/dev/null || true)

if [ -z "$staged_src_diff" ]; then
    exit 0
fi

added_lines=$(echo "$staged_src_diff" | grep '^+' | grep -v '^+++' || true)
removed_lines=$(echo "$staged_src_diff" | grep '^-' | grep -v '^---' || true)

new_funcs=$(echo "$added_lines" \
    | grep -E '^[+][[:space:]]*(async[[:space:]]+)?def[[:space:]]+[a-zA-Z_]' \
    | sed 's/^+//' \
    | head -20 || true)

new_consts=$(echo "$added_lines" \
    | grep -E '^[+][A-Z][A-Z_0-9]{2,}[[:space:]]*[:=]' \
    | sed 's/^+//' \
    | head -10 || true)

removed_defs=$(echo "$removed_lines" \
    | grep -E '^-[[:space:]]*(async[[:space:]]+)?def[[:space:]]+[a-zA-Z_]' \
    | sed 's/^-[[:space:]]*//' \
    | sed 's/(.*//;s/async def /def /' \
    | sort -u || true)

added_defs=$(echo "$added_lines" \
    | grep -E '^[+][[:space:]]*(async[[:space:]]+)?def[[:space:]]+[a-zA-Z_]' \
    | sed 's/^+[[:space:]]*//' \
    | sed 's/(.*//;s/async def /def /' \
    | sort -u || true)

changed_sigs=""
if [ -n "$removed_defs" ] && [ -n "$added_defs" ]; then
    changed_sigs=$(comm -12 <(echo "$removed_defs") <(echo "$added_defs") || true)
fi

if [ -z "$new_funcs" ] && [ -z "$new_consts" ] && [ -z "$changed_sigs" ]; then
    exit 0
fi

if git diff --cached --name-only | grep -q '^README\.md$'; then
    exit 0
fi

details=""
if [ -n "$new_funcs" ]; then
    details+="New functions:\n$(echo "$new_funcs" | sed 's/^/  /')\n\n"
fi
if [ -n "$new_consts" ]; then
    details+="New constants:\n$(echo "$new_consts" | sed 's/^/  /')\n\n"
fi
if [ -n "$changed_sigs" ]; then
    details+="Modified function signatures:\n$(echo "$changed_sigs" | sed 's/^/  /')\n\n"
fi

context="Staged src/ changes introduce new or modified public API but README.md is not in this commit.

${details}Before committing, update README.md to document any user-facing changes at a high level. Focus on what a user of the system needs to know (new tools, changed behavior, new options). Do not add internal implementation details."

jq -n \
    --arg reason "README.md should reflect new or changed functionality in src/" \
    --arg context "$context" \
    '{
        hookSpecificOutput: {
            hookEventName: "PreToolUse",
            permissionDecision: "deny",
            permissionDecisionReason: $reason,
            additionalContext: $context
        }
    }'
