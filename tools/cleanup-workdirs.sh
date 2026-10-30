#!/usr/bin/env bash
# Prunes old scratch output under build/, out/ and vm/ (see AGENTS.md: these
# are rebuildable scratch space, not an archive). Keeps:
#   - anything modified within --days (default 3)
#   - the target of out/latest.iso, wherever it points
#   - any vm/<name> whose running.lock is currently held (VM in use)
#   - any vm/<name> whose disk.qcow2 is a backing-file ancestor of a disk
#     that is itself being kept (qemu-img backing chains), transitively
# Usage:
#   tools/cleanup-workdirs.sh             # dry run, prints what would go
#   tools/cleanup-workdirs.sh --apply     # actually deletes
#   tools/cleanup-workdirs.sh --apply --days 7
set -euo pipefail
project=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
cd -- "$project"

days=3
apply=0
args=("$@")
for i in "${!args[@]}"; do
    case ${args[$i]} in
        --apply) apply=1 ;;
        --days) days=${args[$((i+1))]:-$days} ;;
        --days=*) days=${args[$i]#--days=} ;;
    esac
done

protected=()
if [[ -L out/latest.iso ]]; then
    target=$(readlink -f out/latest.iso)
    protected+=("$(realpath --relative-to="$project" "$(dirname "$target")")")
fi

is_protected() {
    local rel=$1
    for p in "${protected[@]}"; do
        [[ $rel == "$p" ]] && return 0
    done
    return 1
}

is_vm_running() {
    local dir=$1
    [[ -f $dir/running.lock ]] || return 1
    ! flock -n "$dir/running.lock" true 2>/dev/null
}

total=0
to_delete=()
for base in build out vm; do
    [[ -d $base ]] || continue
    while IFS= read -r -d '' entry; do
        rel=${entry#./}
        name=$(basename -- "$entry")
        [[ $name == latest.iso ]] && continue
        is_protected "$rel" && continue
        if [[ $base == vm && -d $entry ]] && is_vm_running "$entry"; then
            echo "skip (running): $rel"
            continue
        fi
        to_delete+=("$entry")
    done < <(find "$base" -maxdepth 1 -mindepth 1 ! -newermt "${days} days ago" -print0)
done

# Protect any vm/<name> that a KEPT vm disk's qcow2 backing chain depends
# on, even transitively, so pruning never orphans a backing file.
declare -A to_delete_set=()
for e in "${to_delete[@]}"; do to_delete_set["$e"]=1; done

if [[ -d vm ]]; then
    for d in vm/*/; do
        d=${d%/}
        [[ -f $d/disk.qcow2 ]] || continue
        [[ -n ${to_delete_set[$d]:-} ]] && continue   # itself already slated for removal
        cur=$d
        while :; do
            # -U can inspect a disk held open by a running VM. If inspection
            # fails, abort instead of potentially removing its backing file.
            if ! info=$(qemu-img info -U --output=json "$cur/disk.qcow2" 2>/dev/null); then
                echo "Cannot inspect backing chain of $cur; aborting cleanup." >&2
                exit 1
            fi
            backing=$(python3 -c 'import json,sys; data=json.load(sys.stdin); print(data.get("full-backing-filename") or data.get("backing-filename") or "")' <<< "$info")
            [[ -n $backing ]] || break
            [[ $backing == /* ]] || backing="$cur/$backing"
            rel=$(realpath --relative-to="$project" "$(dirname -- "$backing")")
            [[ $rel == vm/* ]] || break
            if [[ -n ${to_delete_set[$rel]:-} ]]; then
                echo "protect (backing file for $d): $rel"
                unset 'to_delete_set[$rel]'
            fi
            cur=$rel
            [[ -d $cur ]] || break
        done
    done
fi
to_delete=()
for e in "${!to_delete_set[@]}"; do to_delete+=("$e"); done

if [[ ${#to_delete[@]} -eq 0 ]]; then
    echo "Nothing older than $days days to clean."
    exit 0
fi

echo "Older than $days days (will be removed):"
for e in "${to_delete[@]}"; do
    size=$(du -sh "$e" 2>/dev/null | cut -f1)
    printf '  %-6s %s\n' "$size" "$e"
done
du -sch "${to_delete[@]}" 2>/dev/null | tail -1

if [[ $apply -eq 0 ]]; then
    echo
    echo "Dry run only. Re-run with --apply to delete."
    exit 0
fi

echo
echo "Deleting..."
failed=()
for e in "${to_delete[@]}"; do
    rm -rf -- "$e" 2>/dev/null || failed+=("$e")
done

if [[ ${#failed[@]} -gt 0 ]]; then
    echo
    echo "Could not remove (likely root-owned airootfs leftovers), run manually:"
    printf '  sudo rm -rf -- %q\n' "${failed[@]}"
fi
