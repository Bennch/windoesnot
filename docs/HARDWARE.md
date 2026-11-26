# Hardware compatibility

This is a template that testers fill in as results arrive. Every row is
**untested** until someone reports a result. README.md lists Secure Boot and AMD
graphics as untested; that is still the case.

| CPU/GPU | Laptop or desktop | Secure Boot | Suspend/resume | Multi-monitor | Docking | Wi-Fi/Bluetooth | Installer result | Tester | WinDoesNot version | Notes |
|---|---|---|---|---|---|---|---|---|---|---|
| Intel iGPU | | untested | untested | untested | untested | untested | untested | | | |
| AMD GPU | | untested | untested | untested | untested | untested | untested | | | |
| NVIDIA (open driver) | | untested | untested | untested | untested | untested | untested | | | |
| Intel + NVIDIA laptop | laptop | untested | untested | untested | untested | untested | untested | | | |
| AMD laptop | laptop | untested | untested | untested | untested | untested | untested | | | |
| VM (QEMU/KVM) | VM | untested | untested | untested | n/a | untested | untested | | | |
| VMware | VM | untested | untested | untested | n/a | untested | untested | | | |
| VirtualBox | VM | untested | untested | untested | n/a | untested | untested | | | |

Cell values: `works`, `fails`, `untested`, or `n/a`. Put details in Notes.

## How to test

A live USB test is useful; installing is optional. Only report what you tried.

1. Start the live USB in UEFI mode (note whether Secure Boot was on).
2. Check, and note works / fails / not tested for each:
   live boot, display and scaling, keyboard and mouse, Wi-Fi or Ethernet, sound,
   Settings and Store.
3. Optional: install (back up first, use a spare disk), then check reboot and login.
4. Optional: suspend and resume, multiple monitors, docking, Bluetooth.
5. In the live or installed system open Settings > Diagnose and copy or save the
   diagnosis report. Remove anything private before sharing it.
6. Submit the result with the
   [hardware test form](https://github.com/Bennch/windoesnot/issues/new?template=hardware_test.yml)
   (`.github/ISSUE_TEMPLATE/hardware_test.yml`). English and German are welcome.
   Do not post serial numbers or private logs.
