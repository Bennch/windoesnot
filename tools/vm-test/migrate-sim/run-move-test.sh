#!/usr/bin/env bash
# Submit the test to a running, dedicated start-move-vm.sh guest.
set -euo pipefail
cd "$(dirname "$0")/../../.."
ctl=(tools/vmctl.py --vm-name migrate-live)
"${ctl[@]}" push desktop/lib/windoesnot/mirror.py /root/mirror.py
"${ctl[@]}" push tools/vm-test/migrate-sim/verify.py /root/verify.py
"${ctl[@]}" push tools/vm-test/migrate-sim/run-move-test-guest.sh /root/run-move-test-guest.sh
"${ctl[@]}" exec /usr/bin/bash -c 'nohup bash -c "bash /root/run-move-test-guest.sh > /root/move-test.log 2>&1; echo \$? > /root/move-test.status" </dev/null >/dev/null 2>&1 &'
printf '%s\n' 'Running: inspect /root/move-test.status and /root/move-test.log with vmctl.'
