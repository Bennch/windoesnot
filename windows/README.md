# WinDoesNot Setup for Windows: experimental companion

`WinDoesNotSetup.cmd` starts the PowerShell/WinForms companion. It is designed
for Windows 7 SP1 through Windows 11 using Windows PowerShell 2.0 or newer and
inbox .NET Framework APIs. **Only an isolated Windows 10 VM has been tested.**
Windows 7, 8, 8.1 and 11 compatibility is not yet verified, and this companion
is not a complete migration solution.

The companion requests administrator approval and records selected profile
folder kinds in `<system drive>:\WinDoesNotHandoff\manifest.json`. This is a
selection, not a backup: the files remain on the Windows partition. The Linux
importer must still read that partition. The current Calamares source-protection
guard permits a selected in-installer migration only with the "install alongside"
partitioning choice; other paths remain blocked. Never rely on this manifest to protect data
when replacing or formatting Windows.

Only canonical local paths under `Users` are offered. Reparse points are
omitted. Redirected folders, custom profiles and cloud-only files can therefore
be missing; review them and make an independent backup. An administrator
account selected at UAC may differ from the original signed-in user.

WLAN export is optional and disabled by default. With explicit selection,
`netsh` exports WLAN keys in **clear-text XML** into a restricted handoff
folder. Only WPA2/WPA3 variants supported by the Linux importer can be used;
the WLAN path has not been tested with real profiles. The Windows account
password and browser passwords are not extracted. Firefox profile portability,
including saved credentials, has not been established. Close Firefox before export;
a primary password is not detected and must not be assumed absent. Export Chrome
and Edge passwords to CSV from each browser on Windows if needed; CSV contains
plaintext secrets and must be stored securely and deleted after use. Redirected
OneDrive folders are not exported. Long Windows paths may fail in legacy tools.

New handoffs are prepared separately and replaced with backup/rollback on a
normal error. An interruption between renames may leave a `.previous-*` folder
which can include older WLAN exports; inspect it carefully after recovery.

Run synthetic, non-administrative parser and contract checks in Windows:

```powershell
powershell.exe -NoProfile -STA -ExecutionPolicy Bypass -File .\windows\tests\Test-LegacyContract.ps1
```

The check does not inspect Windows profiles or export credentials. It is not a
substitute for per-version VM, installation and recovery tests.
