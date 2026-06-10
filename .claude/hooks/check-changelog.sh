#!/bin/sh
# Stop-hook guard: refuse to end the turn if commits on a feature branch
# touch behavior-affecting paths (src/ or scripts/) but CHANGELOG.md is
# untouched. Forces the changelog to land in the same PR as the change,
# not in a forgotten follow-up.
#
# Skipped silently on:
#   - the main branch (releases bump the file separately)
#   - detached HEAD
#   - branches with no commits ahead of main
#   - branches whose only diff is in CHANGELOG.md / docs / tests / .claude
#     (pure docs/test/refactor changes don't need a changelog entry)
#
# Exit codes:
#   0   - silently pass
#   2   - block (Claude Code surfaces stderr as feedback and continues)

set -e

# Always operate inside the project root
cd "$(git rev-parse --show-toplevel 2>/dev/null)" || exit 0

branch=$(git branch --show-current 2>/dev/null || true)
[ -z "$branch" ] && exit 0      # detached HEAD
[ "$branch" = "main" ] && exit 0

# Files changed on this branch vs main (committed only — we don't want
# to nag about in-progress working-tree edits).
changed=$(git diff --name-only main...HEAD 2>/dev/null || true)
[ -z "$changed" ] && exit 0

# Has the changelog been updated?
echo "$changed" | grep -q '^CHANGELOG\.md$' && exit 0

# Are any behavior-affecting paths touched?
behavior=$(echo "$changed" | grep -E '^(src/|scripts/)' || true)
[ -z "$behavior" ] && exit 0

# Block and surface a clear message back to Claude.
{
  echo "CHANGELOG.md was not updated, but this branch ('$branch') changes:"
  echo "$behavior" | sed 's/^/  - /'
  echo
  echo "Per CLAUDE.md: add an entry under ## [Unreleased] in CHANGELOG.md"
  echo "(Added / Changed / Fixed / Removed) describing the user-visible"
  echo "behavior change *in this PR*. Then commit it before ending the turn."
} >&2
exit 2
