# Security policy

## Reporting a vulnerability

Please report vulnerabilities privately. Do not open a public issue.

Use GitHub private vulnerability reporting: open the **Security** tab of
[Bennch/windoesnot](https://github.com/Bennch/windoesnot) and choose
**Report a vulnerability**. English and German are both fine.

Please include:

- the WinDoesNot version (Settings > About, or the ISO file name) and whether you
  use a live USB, an installed system or a VM
- what is affected and what an attacker could do with it
- steps to reproduce, or a proof of concept
- any suggested fix, if you have one

Leave out private data, serial numbers and API keys.

## Supported versions

Only the latest release receives security fixes. The project is an early preview.

## Scope

In scope:

- the desktop packages (`windoesnot-desktop` and related packages)
- the ISO and the installer
- the update channel and its signed packages and signatures
- polkit helpers and other privileged helper scripts

Out of scope: vulnerabilities in upstream software (CachyOS, Arch Linux, Hyprland,
Calamares and others) that are not caused by WinDoesNot. Please report those upstream.

## What to expect

The project is developed by one person. Reports are handled on a best-effort basis,
without a guaranteed response time. You will get an acknowledgement when the
report has been read, and credit in the fix notes if you want it.
