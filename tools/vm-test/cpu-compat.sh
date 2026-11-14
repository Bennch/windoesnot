#!/usr/bin/env bash
# Run inside a guest that uses an old CPU model (WINDOESNOT_VM_CPU=Conroe):
# starts every program of the windoesnot-* packages and loads every shared object
# they ship; a SIGILL (exit 132) or a kernel "invalid opcode" trap is a failure.
export XDG_RUNTIME_DIR=${XDG_RUNTIME_DIR:-/run/user/1000} WAYLAND_DISPLAY=${WAYLAND_DISPLAY:-wayland-1}
fail=0
grep -m1 'model name' /proc/cpuinfo
grep -m1 '^flags' /proc/cpuinfo | tr ' ' '\n' | grep -E '^(ssse3|sse4_1|sse4_2|avx|avx2|popcnt)$' | tr '\n' ' '; echo
dmesg -C 2>/dev/null
mapfile -t pkgs < <(pacman -Qq | grep -E '^windoesnot-')
mapfile -t files < <(pacman -Ql "${pkgs[@]}" 2>/dev/null | awk '{print $2}' | grep -vE '/$' | sort -u)
elfs=(); for f in "${files[@]}"; do [[ -f $f ]] && head -c4 "$f" 2>/dev/null | grep -q $'\x7fELF' && elfs+=("$f"); done
echo "ELF files: ${#elfs[@]}"
for f in "${elfs[@]}"; do
    case $f in
        *.so|*.so.*)
            timeout 10 python3 -c 'import ctypes,sys; ctypes.CDLL(sys.argv[1])' "$f" >/dev/null 2>&1; rc=$?;;
        *) timeout 8 "$f" --version >/dev/null 2>&1 </dev/null; rc=$?
           if [[ $rc -eq 124 ]]; then rc=0; fi;;
    esac
    if [[ $rc -eq 132 || $rc -eq 139 && $f == *windoesnot* ]]; then echo "FAIL rc=$rc $f"; fail=1; fi
done
traps=$(dmesg 2>/dev/null | grep -c 'trap invalid opcode')
echo "invalid-opcode traps: $traps"; dmesg 2>/dev/null | grep 'trap invalid opcode' | head
[[ $fail -eq 0 && $traps -eq 0 ]] && echo "CPU-COMPAT: OK" || { echo "CPU-COMPAT: FAIL"; exit 1; }
