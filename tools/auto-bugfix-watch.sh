#!/usr/bin/env bash
# Poll GitHub issues labeled "bug" and hand each new one to Codex, scoped to
# that single bug only. Small, confident fixes are pushed straight to main
# (the one narrow exception to "main/store push only at day's end" that Benni
# approved for bugfixes specifically); anything risky stays local with a
# handoff note for manual review.
set -euo pipefail
cd "$(dirname "$0")/.."
repo="Bennch/windoesnot"

state_dir="${XDG_STATE_HOME:-$HOME/.local/state}/windoesnot/auto-bugfix"
mkdir -p "$state_dir"
state_file="$state_dir/handled-issues.txt"
log_file="$state_dir/run.log"
touch "$state_file"

log() { printf '%s %s\n' "$(date -Is)" "$1" | tee -a "$log_file"; }

issues_json=$(gh issue list --repo "$repo" --label bug --state open \
  --json number,title,url,body --limit 30)

echo "$issues_json" | jq -c '.[]' | while read -r issue; do
  number=$(jq -r '.number' <<<"$issue")
  if grep -qx "$number" "$state_file"; then continue; fi

  title=$(jq -r '.title' <<<"$issue")
  url=$(jq -r '.url' <<<"$issue")
  body=$(jq -r '.body' <<<"$issue")
  log "handling #$number: $title"

  before_commit=$(git rev-parse HEAD)
  handoff="docs/dev/HANDOFF-CODEX-$(date +%Y%m%d)-ISSUE-$number.md"

  prompt=$(cat <<PROMPT
Fix exactly this one reported bug, nothing else. Read AGENTS.md first and
follow it completely, especially "Match effort to change size" and every
release-safety rule in it.

Issue #$number: $title
$url

$body

Hard rules for this run:
- No new features, no refactors beyond what fixing this specific bug needs.
- Never touch release signing keys/material, never rebuild or republish the
  ISO, never modify docs/dev/AUFTRAG-*.md or AGENTS.md itself.
- Run whatever existing check script(s) cover the code you touched (e.g.
  website/tools/check-site.py, tools/check-packages.py) before committing.
- If the fix is small, self-contained, and checks pass: commit it with
  "Fixes #$number" in the message and push directly to origin main.
- If it is risky, large, touches install/boot/package behavior, or you are
  not fully confident: do NOT push. Commit locally only (or not at all),
  write $handoff explaining what you found and what's still needed, and stop.
PROMPT
)

  if codex exec --sandbox workspace-write --approve-for-me -C "$PWD" "$prompt" \
      >>"$log_file" 2>&1; then
    log "codex exec finished for #$number"
  else
    log "codex exec FAILED for #$number (see log above)"
  fi

  echo "$number" >>"$state_file"
  after_commit=$(git rev-parse HEAD)

  if [[ "$after_commit" != "$before_commit" ]] && \
     git log --oneline "$before_commit..$after_commit" | grep -q "#$number"; then
    pushed=$(git log --oneline "@{u}.." 2>/dev/null | wc -l)
    if [[ "$pushed" == "0" ]]; then
      gh issue comment "$number" --repo "$repo" \
        --body "Automatisch bearbeitet und auf main gepusht. Details im Commit-Verlauf." || true
    else
      gh issue comment "$number" --repo "$repo" \
        --body "Automatisch bearbeitet, aber lokal committet und NICHT gepusht (wartet auf manuelle Prüfung)." || true
    fi
  elif [[ -f "$handoff" ]]; then
    gh issue comment "$number" --repo "$repo" \
      --body "Automatisch geprüft, aber als zu riskant für einen Auto-Fix eingestuft. Siehe $handoff, wartet auf manuelle Freigabe." || true
  else
    gh issue comment "$number" --repo "$repo" \
      --body "Automatischer Versuch lief durch, aber ohne erkennbaren Fix-Commit. Bitte manuell prüfen." || true
  fi
done
