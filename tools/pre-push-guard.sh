#!/usr/bin/env bash
# Git pre-push guard: only source goes to GitHub. Blocks pushes that add marketing drafts, reports, private docs,
# agent instructions or very large files. Install: ln -sf ../../tools/pre-push-guard.sh .git/hooks/pre-push
BLOCK='^(deliverables/|docs/(dev|archiv)/|AGENTS\.md|CLAUDE\.md|\.claude/|\.codex/)|instagram|marketing|MISSION-|BERICHT-|OFFENE-PUNKTE|PAUSE-NOTES|\.(mp4|mov|mkv|iso|qcow2)$'
zero=0000000000000000000000000000000000000000
status=0
while read -r local_ref local_sha remote_ref remote_sha; do
    [ "$local_sha" = "$zero" ] && continue
    if [ "$remote_sha" = "$zero" ]; then range="$(git merge-base "$local_sha" origin/main 2>/dev/null || echo "$local_sha")..$local_sha"; else range="$remote_sha..$local_sha"; fi
    files=$(git diff --name-only --diff-filter=AM "$range" 2>/dev/null)
    bad=$(printf '%s\n' "$files" | grep -E "$BLOCK" | grep -v '^docs/screenshots/' | head -10)
    if [ -n "$bad" ]; then echo "pre-push guard: private or non-source files in $local_ref:" >&2; printf '  %s\n' $bad >&2; status=1; fi
    count=$(printf '%s\n' "$files" | grep -c .)
    if [ "$count" -gt 600 ]; then echo "pre-push guard: $count changed files in $local_ref (suspiciously many); check git status and what was added." >&2; status=1; fi
    while read -r path; do
        [ -z "$path" ] && continue
        size=$(git cat-file -s "$local_sha:$path" 2>/dev/null || echo 0)
        if [ "$size" -gt 5000000 ]; then echo "pre-push guard: $path is $((size/1000000)) MB" >&2; status=1; fi
    done <<< "$files"
done
[ $status -ne 0 ] && echo "Push blocked. Remove the files from the commits (git rm --cached, .gitignore) and push again." >&2
exit $status
