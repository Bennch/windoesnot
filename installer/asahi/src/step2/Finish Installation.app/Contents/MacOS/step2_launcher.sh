#!/bin/sh
native="${0%/*}/WinDoesNotRecovery"
if [ -x "$native" ] && [ ! -f "${0%/*}/../Resources/step2.sh" ]; then
    exec "$native" --preview
fi
if [ -x "$native" ] && "$native" --probe >/dev/null 2>&1; then
    exec "$native"
fi
exec /System/Applications/Utilities/Terminal.app/Contents/MacOS/Terminal "${0%/*}/../Resources/step2.sh"
