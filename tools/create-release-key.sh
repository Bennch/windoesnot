#!/usr/bin/env bash
# Interactive, separate production identity. Never accepts passphrases as arguments.
set -euo pipefail
umask 077
if [[ $# -gt 1 ]]; then echo "Usage: $0 [private-gnupg-directory]" >&2; exit 2; fi
if [[ ! -t 0 ]]; then echo 'Run locally in a terminal; enter a strong passphrase in GnuPG pinentry.' >&2; exit 2; fi
signing_home="${1:-${XDG_DATA_HOME:-$HOME/.local/share}/windoesnot-signing/gnupg}"
signing_home="$(realpath -m -- "$signing_home")"
project_root="$(cd -- "$(dirname -- "$0")/.." && pwd)"
case "$signing_home/" in "$project_root/"*|/tmp/*) echo 'Keep the permanent private key outside the source tree and /tmp.' >&2; exit 2;; esac
install -d -m 700 -- "$signing_home"
export GNUPGHOME="$signing_home" GPG_TTY="$(tty)"
if ! gpg --batch --with-colons --list-secret-keys 'WinDoesNot Release Signing' 2>/dev/null | grep -q '^sec:'; then
    gpg --quick-generate-key 'WinDoesNot Release Signing' ed25519 cert 3y
fi
key_records="$(gpg --batch --with-colons --list-secret-keys 'WinDoesNot Release Signing')"
key_count="$(printf '%s\n' "$key_records" | awk -F: '$1=="sec" {n++} END {print n+0}')"
[[ "$key_count" == 1 ]] || { echo 'Multiple release keys found; select the intended key manually.' >&2; exit 1; }
fingerprint="$(printf '%s\n' "$key_records" | awk -F: '$1=="fpr" {print $10; exit}')"
if [[ ! "$fingerprint" =~ ^[A-F0-9]{40}$ ]]; then echo 'No unique release key found.' >&2; exit 1; fi
if ! gpg --batch --with-colons --list-secret-keys "$fingerprint" | awk -F: '$1=="ssb" && $12 ~ /s/ {found=1} END {exit !found}'; then
    gpg --quick-add-key "$fingerprint" ed25519 sign 1y
fi
gpg --armor --export "$fingerprint" > "$signing_home/RELEASE-KEY.asc"
printf '%s\n' "$fingerprint" > "$signing_home/RELEASE-KEY.fingerprint"
printf 'Release key: %s\nPrivate directory: %s\n' "$fingerprint" "$signing_home"
echo 'Back up the entire private directory and its revocation certificate to encrypted offline storage.'
echo 'Only RELEASE-KEY.asc and RELEASE-KEY.fingerprint may be copied into the project.'
