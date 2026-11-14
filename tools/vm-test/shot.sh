#!/bin/bash
# usage: shot.sh NAME  (grim in guest, pulled into vm dir as NAME.png)
cd "$(dirname "$0")/../.."; V=inst28en-20261113-190612
python3 tools/vmctl.py --vm-name $V exec /usr/bin/bash -c ". /tmp/guest-env.sh; G grim /tmp/$1.png" >/dev/null
python3 tools/vmctl.py --vm-name $V pull /tmp/$1.png $1.png >/dev/null; echo vm/$V/$1.png
