# Active release work

## Hosting research — 21 October 2026

User requested free package/website hosting comparison. Findings recorded in
docs/HOSTING.md with official sources and actual artifact sizes. GitHub Releases
fits packages but has a <2GiB/file limit, so cannot hold the 3.47GB ISO intact.
Options: GitHub sources/releases + Pages website + SourceForge ISO (subject to
Open-Source/license eligibility), or GitHub sources + Cloudflare Pages/R2 under
free quotas (billable beyond quotas, production domain/payment setup needed).
User chose Cloudflare on21October2026 and clarified Workers Free + Static Assets
for the website (supersedes Pages); R2 for packages/ISOs. GitHub can remain
source/build hosting. User will obtain the domain and set up the static site.
No accounts/billing/uploads/site created by Codex.
docs/HOSTING.md records the decision and explains Pacman fetching signed packages
from the R2 HTTPS repository alongside normal CachyOS sources.

## Current checkpoint — package updates and ISO18 complete

- User authorized local packaging + VM upgrade tests; no publication. Host
  packages and active desktop were NOT migrated. All testing used separate VMs.
  Read-only final host query: Hyprland0.56.2-4.1, Qt6.12.0-3.1,
  qtermwidget2.4.0-1.1 differ from generic ISO target -4/-3/-1. A future host
  migration needs native builds for those host variants, not the ISO binaries.
- Four split Pacman packages version0.1.0-4 under out/packages/0.1.0-4. Matching
  source archive, PKGBUILD and hash manifest under out/sources/0.1.0-4.
  packaging/version.json is the single version source for manual and ISO builds.
- Runtime originals live under /usr/share and /usr/lib. At login, managed user
  code copies update by a hash ledger; private files/local edits remain intact,
  replaced files are backed up. No root hook writes to users' homes or restarts
  their desktop. Generated IconMap.js is user runtime data, seed now neutral.
- Explicit x86-64/generic flags override CachyOS makepkg's march=native for all
  native components. Compiler flags stored in packages and checked in build logs.
  Earlier prototype package versions1-3 are superseded and not for distribution.
- package-test-01 is an independent ISO14 disk clone. Legacy migration and signed
  repository upgrades to4 PASS; all six private-file hashes identical, 8077 code
  entries, no conflicts. Real apps, AltTab100/350/100ms and four actual geometries
  PASS. Corrupt DB signature rejected. Isolated dependency simulation rejects
  mock Hyprland9999; no fake package was installed. Evidence in vm/package-test-01.
- out/repos/signed-vm-test-4 is a PRIVATE local signed snapshot. Its ephemeral
  test key expires2026-10-22; never use it as a production release key. No upload,
  hosting account or public Pacman configuration created. Host keyring untouched.
- Exact ISO18 SHA256 6ef1172503a23edd8aed275266036f075a5c5ef54645433883c824655aae4bc7,
  3473965056 bytes, out/packaged-test-18/windoesnot-2026.10.21-x86_64.iso.
  out/latest.iso now points there. ISO17 passed offline install but used native
  CPU tuning, so18 supersedes it; ISO15 failed at build-keyring validation, fixed
  by a temporary repository-free local package transaction inside the build root.
- ISO18 real-user installer entrypoint, full offline installation(all35 jobs),
  LTS6.18.50 + primary7.2.7 boot and desktop login PASS. Package inventory complete,
  no failed services/configerrors; both plugins once, GTK dark/Win11 icons, HTTPS,
  German keyboard/English locale/NewYork timezone survive both logins/reboot.
  Actual geometry4cases and AltTab3cycles passed on EXACT installed ISO18 too.
  Evidence vm/release-packaged-18. Faint taskbar background text still cosmetic.
- All test VMs cleanly powered off, disks retained. Launch the final installation:
  ./build-and-run.sh --boot-installed --vm-name release-packaged-18
  Synthetic account vmtest / Vmtest2026.
- docs/PACKAGE-UPDATES.md describes package builds, one-time migration, private
  state, ABI guards, repo signing and GitHub/AUR choices. README/test report now
  point to18. Publication still needs license/asset/author decisions, permanent
  signing-key/bootstrap/hosting and hardware tests. No further code work pending
  in the authorized local packaging + update-test scope.
- Final source/docs/tests backup:
  ~/Backups/windoesnot-release/20261021-202001-packaging-final/project-source.tar.gz
  with checked SHA256. Excludes build/out/vm and all signing keys.

## Historical checkpoint — final candidate14 tested

- Canonical sources, host deployment and ISO preparation are complete. Preserve
  host preferences; all78 original settings remain verified (checks/settings-preservation.json).
- Exact ISO14 passed the real live-user launcher, offline Calamares installation
  (all35 jobs), installed LTS6.18.50 and primary7.2.7 boot plus both desktop logins.
  No source patches applied to that VM. VM is cleanly powered off after tests.
- SHA256 f1eec137c979a2179808e9d1cb40056dbae5563359b0ebdc248880714f7d9c83,
  out/remote-test-14/windoesnot-2026.10.21-x86_64.iso (3483959296 bytes).
- Dark native Files window + Win11 folder icons visually confirmed. German
  keyboard, English UI/locale and New York timezone survive first login/reboot.
  Both plugins exactly once, empty configerrors, zero failed services, HTTPS200.
  AltTab100/350/100ms and actual720p/1080p/125%/portrait tests all PASS.
- Global live Polkit rule absent installed; noninteractive pkcheck denies (exit1).
  No liveuser/autologin, offline package keyring, FAT /boot+Btrfs / all confirmed.
- Reports, screenshots and install log in vm/release-test-14. README and
  docs/TEST-REPORT.md point to this exact tested artifact; earlier ISOs superseded.
- Final external source/documentation archive:
  ~/Backups/windoesnot-release/20261021-172941-project-final/project-source.tar.gz
  with a checked SHA256 sidecar. Build trees/VM disks/ISO files are excluded.
- Cosmetic faint text behind transparent taskbar remains visible despite verified
  disable_splash_rendering=true; recorded rather than claiming complete cleanup.
- PUBLIC release still needs author/license/asset decisions and hardware tests.
  No publication requested or performed. No host packages/bootloader/Polkit changed.
- For a visible VM: ./build-and-run.sh --boot-installed --vm-name release-test-14
  Synthetic account vmtest / Vmtest2026. All earlier notes below are historical.

User authorized: rebuild release preparation, make paths and desktop code portable
on the actual host as well as the ISO; remove other desktop environments from the
image; provide a shell script that builds an ISO and automatically launches a VM,
including an existing-ISO fast debug path. No publication requested.

## Verified starting point

- Active Lua migration completed 21 October 2026. Hyprland 0.56.2-4.1,
  Quickshell 0.3.2-1.1. Both patched plugins loaded; error list empty.
- Prior migration backup:
  `~/.config/hypr/migration-work/lua/cutover-backups/20261021-111210-qe4lpp11`.
- Own current plugin source copies:
  `~/.config/hypr/migration-work/lua/plugins/{hyprbars,hyprdrag}`.
  Preserve corrected hash comparison, hover/inactive colors and centered icons.
- Terminal module: `~/.config/quickshell/default/terminalmodule`, output currently
  `widgets/terminalmodule/LocalTerminal`; relative QML import required.
- Additional Copilot Python helpers live in `~/.config/quickshell/copilot/`.
  Include code only; config/keys/chats are private state.
- Icon theme Win11 is present in both ~/.local/share/icons and /usr/share/icons.
  Determine selected assets and provenance; current wallpaper Bilder/fire-2.jpeg.
- Archiso 91 installed, 789 GiB free, podman and QEMU installed.

## Upstream downloaded

- `upstream/cachyos-live-iso`: official CachyOS/CachyOS-Live-ISO,
  master 3215497d2e8c5fea90e185affcf973dfa2cf790b (2026-10-03).
- `upstream/cachyos-calamares`: official CachyOS/cachyos-calamares,
  branch cachyos. Pin actual hash in sources.json.
- No upstream AGENTS.md found at discovery time.
- ISO uses archiso/packages_desktop.x86_64 + airootfs; Plasma packages/login are
  currently selected. Keep required Qt/KDE frameworks for Calamares, remove other
  desktop sessions. Generic default monitor/renderer selection required for live VM.
- Upstream util-iso.sh mutates host mkarchiso: use direct mkarchiso in isolated build.
- Calamares online settings currently offer many desktop groups and fetch a remote
  netinstall.yaml. Override with local WinDoesNot-only settings; target must receive
  the desktop too, not just live session. -c selects a configuration DIRECTORY.
- Calamares may update its package on live start: custom configuration must live
  separately and not be overwritten by the upstream launcher.

## Work sequence

1. Back up current host desktop files and record hashes before applying changes.
2. Create canonical portable desktop source + clean new-user defaults. Use executable
   wrapper names for shared IPC/state; eliminate /home/benni from runnable source.
   Preserve host personal settings and monitor data on install.
3. Add repeatable user/system packaging and component build; validate QML/Lua/Python.
4. Apply validated source to host, preserving state; check running session without
   restarting user apps unnecessarily. Ask for a manual shell restart only if needed.
5. Generate Hyprland-only live profile and Calamares target desktop selection.
6. Add build-and-run.sh, isolated build, fresh VM disk, UEFI, logs, --run-only,
   --build-only, --headless and --dry-run.
7. Validate dependency resolution in isolated DB/container and actual ISO/VM boot if
   permissions permit; do not label untested image/install paths release-ready.

## Constraints to handle

- Many absolute home paths were introduced by the just-completed IPC migration.
  Replace bridge/writer references with stable portable wrapper commands.
- Current shell PATH already includes ~/.local/bin; verify compositor/Quickshell PATH
  before applying wrapper-based changes. Ensure session startup establishes PATH.
- Super-tap root service hardcodes UID 1000 and a CHERRY keyboard; design portable
  activation rather than shipping this machine's service verbatim.
- Runtime files and defaults must be distinct. Lua state.lua embeds base64 JSON;
  use its writer to update it, rather than blindly replacing text only.
- Monitor UI/default geometry currently assumes 2560x1440 in some places. Keep the
  host layout; generate new-user/VM defaults from detected monitors.

## Current decisions and implementation

- Offline installation explicitly requested: unpack the image, no repository update during installation.
- Host backup: ~/Backups/windoesnot-release/20261021-113218 (SHA256.json).
- Current compositor and Quickshell PATH omit ~/.local/bin: global portable wrappers must precede host source deployment.
- SVG UI icons replace decorative emoji; the searchable emoji catalogue remains content.
- Snappy Switcher 2.1.2 source uses legacy raw IPC; portable source now probes Lua and uses typed focus, with legacy fallback.
- Component builds run against each target image; host rebuild is in progress.

## Remote continuation

- Benni is remote/paired; avoid local password/desktop dialogs.
- Portable command installation succeeded via desktop authentication; active source has NOT been deployed yet.
- Pending local ISO authentication was superseded by a rootless build.
- KVM is available on the host. User namespaces work outside the Codex sandbox.
- remote-test-01 downloaded ~2.5 GiB signed packages into build/package-cache.
- First install failed on pre-created Calamares module files. Fixed: keep custom files only in payload until after package install.
- Use new build IDs after failed/package-modified stages; archiso may leave completion markers after pacstrap failure.
- Host lacks GRUB; signed cached package is extracted into build/host-tools with a working module/SBAT wrapper.
- SVG component smoke test passes; full QML requires a private Wayland compositor, not Qt offscreen.

## First live VM results

- remote-test-02 ISO successfully built (3.3 GiB) and booted in QEMU/KVM with VirGL + egl-headless; VM release-test-02, own 64-GiB disk.
- QMP screendump reports no surface with egl-headless. Use guest grim + vmctl pull instead. QEMU Guest Agent is activated by its virtio channel.
- Actual desktop compiles/loads with both custom plugins and empty configerrors.
- VM exposed missing copied symlink launcher + stripped executable bits. Source fixed: new hypr/scripts/start-quickshell.sh + profile file_permissions for every executable payload source.
- Guest was temporarily patched in COW to test those fixes. ISO remote-test-02 itself still needs these fixes rebuilt.
- Full GUI tests passed at actual 1280x720, 1920x1080, 2560x1440@1.25, 1920x1080 rotated. Settings stayed within logical work areas; configerrors stayed empty. Test report /tmp/windoesnot-live-test.json inside guest; screenshots /tmp/settings-*.png.
- Also corrected defaults pinned.txt to plain app names (taskbar.txt remains pipe-separated), XDG user directories with literal $HOME, live monitor export for wallpaper editor instead of preferred/auto strings.
- Added own-VM-only tools/vmctl.py with QMP, guest exec, push/pull, screenshots. All VM socket operations require escaping Codex sandbox.
- Calamares GUI launch/test is next. Preserve host personal state; host source deployment still pending until full VM checks.

## Host deployed / corrected ISO 03

- Host source deployed: 70 files; backup `~/Backups/windoesnot-release/20261021-143338-deploy/manifest.json`.
- `tools/activate-host.py` PASS: shell loaded, no QML load failure, empty configerrors, both plugins loaded once, monitor mode/position/scale/transform unchanged.
- ~/.local/bin now has the current shared helpers and is in the restarted shell's PATH. Earlier /usr/local helpers remain as fallbacks.
- Calamares source rebuild succeeded against Python 3.14.8 / Boost 1.92 / Qt 6.12 / KPMcore 26.08.2. Source commit reports 3.4.1; original CachyOS package metadata says 3.4.2-13.
- Custom data directory is /etc/windoesnot-calamares, with qml symlink required by -c. All required modules loaded and WinDoesNot branding displayed.
- remote-test-03 ISO built and boots cleanly with no guest patching: QS, both plugins, desktop icons, pins and portable XDG user folders work.
- VM release-test-03 is open in Calamares. Selected erase ONLY its new /dev/vda 64 GiB qcow2. Synthetic username vmtest, computer windoesnotvm, test password Vmtest2026. No personal credentials.
- Installer wizard is being advanced to summary; full actual offline install and reboot still pending.
- Canonical finalize-install.sh gained offline target pacman-key init/populate AFTER image03 was prepared. Image03 lacks this new fix; the final image must include it (new build ID after collecting installer-test issues).
- Do NOT count runtime VM patches as fixes present in immutable ISO02. Image03 was booted cleanly and contains previous launcher/mode/QML/ABI/branding fixes.

## Installer / disk boot continuation

- Installer03 exposed `${USER}` vs misleading `@@USER@@` comments and a silent
  GRUB skip caused by `efiBootLoaderVar`. Both fixed in canonical generator.
- Rebuilt Calamares, private SDDM session directory, offline target keyring and
  adoption of installer keyboard/locale/timezone are included in image04.
- Prototype03 manually repaired only inside its VM; original disk preserved.
  GRUB 2.16 then reported premature EOF reading kernels from Btrfs `/@/boot`.
- Both target kernel SHA256 match the working live ISO exactly. A separate
  qcow2 overlay (`vm/boot-probe`) with the SAME GRUB and kernel on the FAT ESP
  booted kernel 7.2.7 and SDDM. This isolates the tested Btrfs loader path;
  it does not prove an upstream root cause. Prototype repair tar had changed
  directory owners: fixed only in the diagnostic overlay; fresh ISO source
  owners verified root:root, including in the build user namespace.
- Profile05 uses a 1-GiB ESP at `/boot` so kernels/initramfs stay on FAT;
  root remains Btrfs. Added profile assertion and WinDoesNot GRUB distributor.
  Installed root mode normalized to 0755. Unused networkd-wait-online disabled.
- Image05 build running (exec session 11097, checks/remote-test-05-build.log).
  release-test-04 and boot-probe VMs stopped; no host packages/bootloader touched.
  Next: clean image05 Live boot, offline install, disk-only boot, SDDM login
  and installed-session checks. Do NOT call the release tested before that.
- Final host source sync: 6 files, backup
  `~/Backups/windoesnot-release/20261021-151906-deploy/manifest.json`.
  Personal preferences preserved, remote session not restarted. Helpers now join
  the same atomic deployment/backup manifest as QML/Lua.

## Image05 passed / final candidate06

- ISO05 SHA256 cdb15cf270d28fbc37d6e225830116eb56f81bc173455b8ac2efa7fbfd970097.
  Clean Live boot: zero failed services. Clean Calamares installation with
  QMP network link OFF: all 35 jobs succeeded. Evidence `vm/release-test-05/`
  (`calamares-install.log`, `install-complete.png`, `installed-desktop.png`).
- Disk-only boot succeeded for BOTH 6.18.50 LTS and 7.2.7 primary kernels.
  SDDM login using synthetic vmtest account succeeded. Both plugins load once,
  configerrors empty; DNS/HTTPS work, target package keyring initialized offline.
  No liveuser/getty autologin, own SDDM session selected, FAT /boot and Btrfs /.
- Installer preferences adopted: en_US.UTF-8, us, America/New_York. These are
  deliberate synthetic test defaults, not Benni's own preferences.
- Installed GUI geometry tests PASS at 720p/1080p/125%/portrait and restore of
  already-open settings window. JSON `vm/release-test-05/installed-geometry.json`.
- Found final small issues: Hyprdesk read old typo `defaultsettings.txt`, ignoring
  theme/language/desktop preferences. Corrected to `default/settings.txt`.
  Disable inherited systemd-time-wait-sync on installed target: its 30s timeout
  raced initial NTP sync; regular timesyncd remains enabled.
- Root 0555 is CURRENT DISTRO POLICY (`/usr/lib/tmpfiles.d/root.conf`), not an
  installation failure. Removed our unnecessary temporary chmod override.
- Image06 is building (session 49803, checks/remote-test-06-build.log), includes
  those corrections and VM geometry tester supports --user for installed account.
- Host sync of latest source has backup
  `~/Backups/windoesnot-release/20261021-153145-deploy/manifest.json` (2 files).
  Did not restart the remote desktop. Docs include explicit asset/license items
  still to settle before PUBLIC release; no upload authorized/performed.

## Final runtime findings / candidate10

- ISO07 installed offline successfully, disk-only LTS boot, SDDM login, plugins,
  empty configerrors, four actual GUI geometries and real Ghostty/Files starts
  verified. Evidence under vm/release-test-07.
- App screenshot exposed first-login GTK light mode despite dark QS. Fixed
  startup gsettings color-scheme and icon-theme. New accounts use packaged Win11
  icons; host's saved Papirus-Dark preference remains intact. Initialize Hyprdesk
  language before labels, translate Settings heading, retain disconnected monitor
  icon positions at login/hotplug. Candidate runtime fixes verified in VM07 COW.
- Alt-Tab exposed a real focus bug: Snappy activated before releasing its layer
  keyboard grab. Fixed hide/roundtrip/focus ordering, keyboard interactivity reset,
  equal-size remap configure, and Alt release before mapping. Three consecutive
  real Alt-Tab presses (100/350/100ms) now alternate Nautilus/Ghostty correctly.
  Log vm/release-test-07/snappy-final.log. Immutable ISO07 lacks these patches.
- Candidate08/09 superseded. Candidate10 build running (session39054,
  checks/remote-test-10-build.log); repeat clean install/disk boot with10.
- Host latest backup ~/Backups/windoesnot-release/20261021-161111-deploy/manifest.json.
  activate-host.py PASS: shell loaded, no configerrors, both plugins once,
  monitor layout unchanged. Compositor/apps/remote session kept running.
- Optional author-name question sent, unanswered; existing license unchanged.
  Public asset/license checks remain in docs/RELEASE-CHECKLIST.md.

## Settings race fixed / candidate11

- Candidate10 first-login checks exposed QML save-before-load: construction-time
  signals overwrote user preferences and installer timezone with defaults.
  Fixed isLoadingSettings=true initially, and default-app loader restores the
  previous guard value rather than blindly setting false.
- Recovered host settings from the original 113218 backup; pre-recovery state
  saved in ~/Backups/windoesnot-release/20261021-162611-settings-recovery.
  Current source backup ~/Backups/windoesnot-release/20261021-162521-deploy.
  Host activate PASS, no errors, monitors unchanged. Exact dictionary comparison
  confirms ALL 78 original values survive restart and late async jobs, including
  keyboard, bars, desktop icon preferences, primary monitor and private weather.
  checks/settings-preservation.json records counts/booleans, no private values.
- VM10 COW guard test: all non-default values survive real shell restart (NY
  timezone, 48px icons, grid24, gaps7, hidden sidebar). Packaged native Snappy10
  passed asserted fast Alt-Tab cycles (100/350/100ms), vm/.../alt-tab.json.
- Candidate11 build session79713, checks/remote-test-11-build.log. No more feature
  additions. Next: clean ISO11 install/disk boot, assert first-login adoption and
  theme, native switcher, geometry, both kernels; docs + external source backup.
  Do NOT distribute earlier candidates: they lack the preference guard.

## Final installer entrypoint / candidate14

- ISO11 clean install and BOTH installed desktop logins passed; first-login
  choices and NY timezone survive first login and full reboot. Packaged Snappy
  asserted Alt-Tab100/350/100ms; four actual geometry cases passed. All evidence
  in vm/release-test-11. No source-code patches were applied to VM11.
- Identified faint text as Hyprland's random Splashes.hpp quotes, NOT a VirGL
  artifact. Canonical reference now disables splash rendering; host getter true,
  original78 preferences still unchanged. ISO12 includes that visual cleanup.
- Actual LIVE-USER pkexec launcher test exposed X11 authorization failure that
  direct root tests missed. Fixed launcher passes XDG_RUNTIME_DIR/WAYLAND_DISPLAY
  to Qt Wayland explicitly and requires the live marker. Prototype12 COW test
  proved EUID0 Calamares opens without dialog using the real launcher.
- Found upstream blanket wheel Polkit NOPASSWD rule. Generator now narrows it to
  liveuser and finalize-install removes the file from the target. Static contract
  checks added. No host Polkit rules were changed.
- Candidate13 superseded (lacks launcher fix). Candidate14 profile prepared and
  launcher + narrow rule tested in prototype BEFORE building. Build session52126,
  checks/remote-test-14-build.log. Prototype12 stopped after saving launcher log.
- Next: exactISO14 live-user launcher -> offline install -> disk-only login ->
  assert prefs/theme/plugins/geometry/AltTab + absent globalPolkit rule and pkcheck
  denies noninteractive admin. Both kernels, report/README + external source tar.


## Private project website / windoesnot.me

- Benni supplied windoesnot.me and requested a GitHub push with PRIVATE
  visibility. Website lives in website/ as a separate Git repository.
- Pushed main to https://github.com/Bennch/windoesnot.me, verified PRIVATE
  through GitHub API; local and remote commit match:
  5f6c0768517c12944625f06ddfdd6381f3eaccf3. Working tree clean.
- Original local Lichtauf project description, public desktop video and theme
  screenshots reused. Added responsive dark/orange page, own SVG W branding,
  development/release status, legal pages derived from the owner's existing
  public texts. No invented download URL or release date.
- Browser QA: Firefox157 in isolated test profile, 320/390/760/768/1024/1440px,
  no overflow; both theme images, real H.264 playback, legal navigation and
  JS-disabled content/native controls pass. No console or HTTP errors and no
  external subrequests. Evidence in website/checks/ (ignored by Git); report
  website/VALIDATION.md. Older cached Firefox149 had host codec trouble; newer
  test browser plays the original unchanged file. No host browser changes.
- Static upload: out/website/windoesnot-me-static.zip, 14,754,659 bytes, SHA256
  5a5620bec7046f45302888ec401b849147c7faebca7f2bc1035f87623a549434.
  index.html at ZIP root; all15 assets below25MiB. No ISO/package payload.
- website/README.md describes manual upload and future private GitHub/Workers
  integration. wrangler.jsonc prepared, no Cloudflare login/deploy or domain
  modification performed. Existing host desktop, installer branding and ISO
  were not modified by this website task.


## Website: two audiences, searchable docs and downloads

- Implemented requested default beginner view (/) and technical view (/technik/),
  common navigation with prominent Download link, and a CSS monitor around the
  original video. Public project attribution now uses lichtauf.me.
- Added /hilfe/ and /hilfe/technik/ plus19 static articles: onboarding, apps,
  shortcuts, taskbar, windows/workspaces, screenshots, appearance, monitors,
  input, connections/audio, updates/backups, troubleshooting, installation,
  dotfiles, architecture, Lua, plugins, packages and release/test status.
- Search runs locally over full article text, understands Win/Super aliases,
  accent/ss normalization, supports audience filtering and shared query URLs.
  No third-party search or analytics. No-JS and failed-index fallbacks tested.
- content/ holds editable fragments and metadata; stdlib-only build-site.py
  generates committed dist/. Shortcut coverage and source hash checked against
  current bindings.lua. Integrated Desktop HelpCategory.qml has stale M/S/V
  descriptions; website follows actual Lua bindings. No desktop code was changed.
- /download/ offers separate ISO and Dotfiles paths with linked guides. Both
  binary links remain unavailable until public artifact/license/release approval;
  content/releases.json supports real HTTPS URLs with SHA256 and byte size.
  No private snapshots or unfinished dotfiles were copied into the website.
- Static checks PASS:27 HTML pages,19 search entries,41 files, no broken links
  or anchors, assets all below25MiB. Firefox157 QA:30 geometry checks, six
  search cases plus ranking, filter, no results, keyboard, query links,
  HTML-as-text, video playback, themes, no-JS and failed-search fallback PASS.
  No unexpected console/HTTP errors or external requests.
- Pushed private main commit 6600f7556657061a433165c761316bfc793d3d8a; local/remote match.
- Updated static ZIP: 14833289 bytes, SHA256 7f84a297c8e6642ae768c722d55123c9177f2a0f8e5aa479574b540f638028fc.
- Source backup: /home/benni/Backups/windoesnot-release/20261021-220809-website-docs/website-source.tar.gz.
- No Cloudflare account/domain setup or direct deployment performed;
  no host package/session/ISO changes.


## Host reboot: Quickshell icon-map startup race

- User reported no taskbar or top notification bar after the first reboot.
  Boot start-quickshell.log shows IconMap.js parse failure at line7 during
  initial shell loading. Fully generated file later passed Node parsing and
  the real shell loaded successfully from it. Lua config and both plugins
  were healthy. This is consistent with generator/shell running in parallel
  while the generator truncates and rewrites an imported JS library.
- Recovered the main Quickshell profile in the active session; both 45px
  panels are registered on the primary monitor. Settings/pinned/taskbar/calendar
  file hashes remain unchanged. Hyprland configerrors empty.
- Generator now stages under the destination directory, validates JSON, then
  publishes complete JSON/JS files by atomic renames. Failed validation keeps
  prior files; staging directory is cleaned. Per-user caches have mode0600.
- extras/start-quickshell.sh now finishes generation before QML loading, uses
  explicit config and captures stderr. Removed separate generator autostart
  entry from reference.lua. Host hypr/scripts launcher is a symlink to extras;
  canonical hypr/scripts launcher is a wrapper. Both actual implementations
  match and the wrapper is covered by the regression test.
- tests/test-icon-map-startup.py PASS: concurrent reader sees only old/final
  JS, generated syntax valid, validator failure preserves both old files,
  temporary cleanup, real launcher/wrapper waits before mocked Quickshell.
  validate-desktop.py PASS:32 layouts, Python/SVG, preservation, isolated Lua.
- No forced reboot performed. A fixed-PID check briefly used an outdated PID
  after Quickshell was restarted; a dynamic layer check confirms exactly two
  panels owned by one current Quickshell process.
- Existing ISO18/pkgs0.1.0-4 remain the earlier tested artifacts and do not
  contain this source fix. Release checklist requires pkgrel bump/new build
  and cold-start/repeated-login checks before public distribution.
- Host backup and recovery evidence: /home/benni/Backups/windoesnot-release/20261021-223304-quickshell-reboot-fix.


## Host login: stable Lua positions and flush taskbar attachment

- Root cause: Hyprland 0.56.2 clears an explicit move when the center
  effect is applied, including center=false. Lua table iteration order varies
  between sessions. init.lua now removes center after merging any rule with
  explicit move, on the host and in the canonical desktop sources.
- Removed the generated eight-pixel bottom gap for all eight bottom-anchored
  panels. Horizontal margins are unchanged. Restarted only the layout watcher
  to load the corrected geometry helper; kept the desktop session running.
- Real close/reopen check: settings at [2634,1309], size [900,700]; startmenu
  at [2781,1289], size [605,720]. Both end at global y2009, exactly the
  taskbar top: zero-pixel gap. Hyprland configerrors empty.
- tests/test-lua-placement.py covers all 12 rules in 16 fresh Lua states,
  detects the original conflicting effects, and checks exact bottom attachment.
  validate-desktop.py passes all 32 geometry scenarios and preservation checks.
- No cold reboot performed. Existing ISO18/packages0.1.0-4 still need rebuilding
  with this and the icon-map startup fix before release.
- Backup: /home/benni/Backups/windoesnot-release/20261021-224349-lua-position-fix.


## Approved PNG branding and optional Start orb

- Imported all ten transparent PNG exports unchanged into standalone desktop
  assets, with dimensions/SHA256 manifest and repeatable sync-branding.py.
  Website sources were not changed by this task.
- Wired About light/dark logos, hicolor app/installer icons, Calamares
  logo/icon/slideshow, release-only SDDM theme and UEFI/BIOS boot graphics.
  The installed GRUB theme is staged onto /boot in the target before config
  generation. Upstream checkouts and the host bootloader remain untouched.
- User clarified that the original Start orb must stay. Restored it immediately
  after an initial replacement and recovered the stopped main shell. Found
  an existing launcher bug during recovery: --config expects a config name,
  whereas --path accepts the local QML file. Fixed both host/source launchers
  and the startup regression test.
- Added Appearance > Start button: original classic default, optional dot,
  optional local image imported by a shell-free Python helper. Owned copies
  use content hashes and encoded URLs; failed/missing image falls back to
  classic. No existing user setting or pin was overwritten.
- Compiled the complete shell before deployment; rendered component/import
  regression passed. Installed checked files atomically with a brief targeted
  main-shell restart. Verified one taskbar/topbar on DP-2 and fresh settings/
  startmenu each with zero-pixel gap. Hyprland configerrors empty. Personal
  settings/pins/taskbar/state/host hashes match the backup.
- Full offscreen shell smoke cannot create PanelWindow on this host; it reports
  No PanelWindow backend loaded. Component rendering and complete compile on
  Wayland passed instead; live position checks cover the actual main shell.
- Real unpacked SDDM 0.21.0-6 greeter loads/renders theme in --test-mode. No
  real authentication performed. Generated profile passes offline/branding
  checks; GRUB config syntax passes. Boot visuals/installer/login still require
  a new image VM run. No ISO was rebuilt; version 0.1.0-5 is prepared.
- Backup: /home/benni/Backups/windoesnot-release/20261021-230839-branding.


## Appearance page: dynamic component registration correction

- User reported an empty Appearance page. Actual shell log: StartOrbSettings
  is not a type. Earlier isolated tests imported the entire settings directory
  directly, bypassing the lazy Loader and Quickshell VFS used by the real page.
- Added explicit local directory import and settings/qmldir registration of
  all category types including StartOrbSettings. Also qualified one existing
  darkMode reference in the light-theme icon binding.
- New test-appearance-loader.py uses the actual dynamic setSource path and
  full Appearance page. The fixed page and Orb controls load with nonzero size
  and correct settings object. Removing import/registry reproduces the error.
- Host files installed atomically; restarted only the main shell to invalidate
  its failed component cache. Existing settings/pins/taskbar/Lua state hashes
  unchanged. Source and host fixes identical. Component branding tests pass.
- Sources corrected; earlier branding profile/source-check directories are
  intermediate checks predating this correction. No ISO built.

- User requested consistent Settings styling for Orb controls. Replaced default
  Qt Controls button presentation with the existing Appearance selector style:
  15px spacing, 120px cards, radius8, border2, accent-filled selection, matching
  light/dark colors. Image import action matches existing 36px/radius6 action
  buttons with bold13px text. Original Orb and user choices are preserved.
  Full dynamic Appearance Loader, branding and desktop validation pass.


## Installer comparison and offline app chooser — 2026-10-22

- User authorized a fresh before image/visible VM, then software chooser and
  after image/VM. Baseline before-apps-20261022 built from frozen source hashes,
  includes all recent desktop/Lua/branding fixes and version0.1.0-5.
  ISO3473965056bytes; SHA256 check passes. Visible VM boots on virtio-vga
  software mode. Initial VirGL VM booted but QMP had no surface; stopped only
  that new VM and relaunched software graphics. No installation in before VM.
- Added native Calamares apps page, custom module overlays only in generated
  vendor tree. Fourteen catalogued programs, DE/EN descriptions, profiles,
  search/category filters, strictly validated JSON import/export and summary.
  Root desktop remains mandatory. All package names resolved in isolated DB.
- New Python job installs chosen additional apps after target keyring setup
  using a signature-required local repository, never refreshed online repos.
  Build prepares dependency archives/icons and hashes; selected profile retained,
  optional archive stash removed after success in target.
- Shared widget tests and profile/install-logic tests pass. Version0.1.0-6
  after-apps-20261022 build started. Full offline VM installation still pending.
- Further community wishes (OEM/OOBE, extra bootloaders, invasive Btrfs patches)
  were not folded into this first implementation. Host packages/session/boot
  were not changed. See docs/INSTALLER-APPS.md for maintenance contract.

## Live preview feedback — 2026-10-22

- User reviewed the before VM. The after source now starts the live session in
  de_DE.UTF-8 (DE/EN locales generated); installer-selected locale still wins on
  the installed target. Lang.get respects the explicit QML language argument,
  and Settings explicitly initializes its translation library.
- Start-menu application discovery uses localized desktop-entry names, confines
  parsing to the Desktop Entry section, and respects user overrides/Hidden and
  NoDisplay. Sidebar/folder labels and custom utility names use the same DE/EN
  translations. The personal Keys launcher is excluded at the user's request.
- Calamares sidebar uses the square brand icon; the light welcome page uses the
  dark wordmark. Its application-ID desktop file maps to the WinDoesNot icon.
  Stock Install System entry is hidden and points to the configured launcher;
  the single visible installer entry is WinDoesNot installieren.
- Apps contains independent Docker/Ollama toggles, both off for new accounts.
  Disabled panels have inactive Loaders; no warmup/polling starts them. Turning
  off also closes the respective panel. Toggle changes persist. Enabling a UI
  panel does not enable a system service.
- Backups probes live marker/tool availability without privilege. Live mode
  displays a translated disabled notice; Snapper/polkit actions are guarded.
- Dynamic Apps/Backups QML tests, explicit DE/EN lookup, desktop-entry locale/
  user override tests and failed-download resolver cleanup pass. Existing
  Appearance lazy-loader and full desktop portability validation still pass.
- Build DNS: arch-chroot -N's root bind hides its earlier resolv.conf bind. Stage
  nameserver lines only in the private profile, consume/delete that staging file
  inside prepare.py, and restore the original image resolver in a finally block.
  No host search domain is copied and no build resolver belongs in the final ISO.
- Final candidate: after-apps-20261022-r2, version0.1.0-7. First packaging attempt
  deliberately stopped to include the late language helper and personal-app
  exclusion before rebuilding the package. Complete source hashes recorded in
  build/after-apps-20261022-r2/SOURCE-STATE.json. Full build/VM results pending.
- Menu cleanup of developer launchers (CMake, Qt Designer/Linguist etc.) deferred
  per user: dependencies remain installed; entries may be hidden separately.

## Live language, appearance and final boot fixes

- User reported a missing tray chevron: the referenced upstream SVGs were absent.
  Added an original project chevron, independent of icon fonts/themes.
- The real installer app_id is io.calamares.calamares, not calamares. A hidden
  matching desktop alias now resolves the branded taskbar icon. Verified in VM.
- Corrected the actual Settings initialization scope: dynamic QML cannot see the
  imported Lang namespace. It calls the enclosing Settings method instead.
  An actual guest restart now completes settings loading without ReferenceError.
  Regression fixture exercises this dynamic boundary and Settings IPC parsing.
- Added our own LiveDesktopBridge within windoesnotapps. It observes liveuser's
  existing preferences and applies a complete Fusion palette/QSS plus themed
  sidebar delegate and welcome wordmark. No upstream source patch is required.
  Program cards update colors without rebuilding or losing the chosen apps.
- Calamares language-change events update live Quickshell through a narrowly
  scoped user IPC method. A live-only root helper updates locale.conf and the
  user activation environment. DE and EN match the desktop's supported UI
  languages; other installer languages use the desktop's English fallback.
  The installed system still receives Calamares' actual chosen locale via its
  locale job and windoesnot-initialize --adopt-system, not the live helper.
- Verified in a disposable VM: Calamares English -> Quickshell English, back to
  German -> Quickshell German; loading=false, Docker/Ollama=false. The already
  open installer follows light/dark changes, including logo and sidebar.
- GRUB standalone prefix points into memdisk. Resolve the live theme against
  the actual root ISO device. A separate 480x90 derivative prevents GRUB from
  imposing the 2446x459 source image's minimum layout size. Original logo exports
  stay unchanged. Final 1280x800 boot screenshot has no error or overlap.
- New-user package candidate is 0.1.0-10. Fast native module rebuild uses the
  actual image's installed Calamares SDK; full fresh builds still compile the
  module with the generated Calamares tree. SDK compile and linkage pass.
- Intermediate ISOs are retained under out/after-apps-20261022-r2/archive-*.
  Complete final ISO/offline installation results are recorded below once done.

- A subsequent real language test found name-only Start-menu pins losing their association after translation (Files/Dateien). Added desktop-entry name aliases, kept the legacy pin file unchanged, preserved saved order and reused existing app overrides across locales. VM confirms three pins remain recognized; pin-file SHA256 unchanged. Native installer page labels now follow frontend QLocale separately from the installation target language. Final candidate packages: 0.1.0-11.

## Offline installation test of 0.1.0-11 — 22 October 2026 (resumed session)

Disposable headless VM `apps-install-test-20261022` (4 GiB, 2 vCPUs, own 64 GiB qcow2),
guest NIC carrier verified down (`set_link net0 off`) before installation.

- Summary page at 1280x800 clipped the navigation buttons. Cause: Calamares
  `windowExpanding: normal` -> `CalamaresWindow::ensureSize()` resizes up to the
  full screen height, ignoring the taskbar reserve and the Hyprland tile (696 px).
  Fix in `tools/prepare-profile.py`: `windowExpanding: noexpand` (summary scrolls
  instead); asserted in `tools/check-profile.py`. Confirmed live by forcing a
  re-tile: buttons visible, content scrollable. NOT yet verified in a rebuilt ISO.
- Installation PASS: all 36 jobs, "Alles erledigt", ~2.5 min. Only `/dev/vda`
  written. Log: `vm/apps-install-test-20261022/calamares-install.log`.
- Target (read-only mount, then booted): all 13 optional apps installed,
  `software-profile.json` exact, offline stash removed, CUPS socket+service
  enabled/active, no liveuser/autologin/global polkit rule, wheel sudo needs a
  password, bash login shell. Locale LANG=de_DE + fi_FI formats, Europe/Helsinki,
  keymap/X11 de, as selected. Four windoesnot packages 0.1.0-11, `pacman -Qk`
  0 missing files (also all selected apps). last-sync: 8094 managed, 0 conflicts.
- Installed boot: SDDM login as vmtest PASS on LTS 6.18.50 and primary 7.2.7;
  both plugins exactly once, empty configerrors, no failed units, prefer-dark/
  Win11 icons, HTTPS 200 after VM restart. Checks: `system-checks-primary.json`.
- Found: GRUB default booted LTS. The offline sequence (also upstream's
  settings_offline.conf) omits `grubcfg`, losing upstream's GRUB_TOP_LEVEL and
  GRUB_DISABLE_OS_PROBER=false. GRUB 2.16's new 31_efi_bootnext also listed 9
  firmware entries (PXE/HTTP/shell/self). Fix in our 90-windoesnot.cfg drop-in:
  GRUB_TOP_LEVEL=/boot/vmlinuz-linux-cachyos, GRUB_DISABLE_OS_PROBER=false,
  GRUB_DISABLE_BOOTNEXT=true. Applied by hand in this test VM: clean menu,
  primary kernel default, LTS under advanced options. Windows dual-boot via
  os-prober remains UNTESTED (no Windows disk in any VM).
- Found: German system got English Firefox. `packages_for` and the offline repo
  preparation skipped localizations of required apps. Now required apps keep
  their language packs (firefox-i18n-de); LibreOffice DE adds hunspell-de.
- Added optional catalogue app `usb-writer` (Impression, official repo), cf.
  CachyOS forum wish for a bundled USB creation tool. 15 catalogue entries.
- Cosmetic, not fixed: SDDM layout box shows "us" until the first key press while
  X11 is already `de` (verified by typing). German Calamares string
  "Erstelle<strong>neue</strong>" lacks a space (upstream lang/calamares_de.ts:1748).
  GRUB "Advanced options" label stays English.
- Tests after changes: test-software, apps-widget (host Qt), validate-desktop,
  icon-map, lua-placement, branding sync/tests, appearance loader, live feedback,
  prepare-profile + check-profile into build/profile-check-20261022-grub: PASS.
- Changes are profile/catalogue only (`iso/` is copied by prepare-profile.py,
  not packaged), so desktop packages stay 0.1.0-11. A new ISO build with a new
  build ID is required to verify: noexpand summary, GRUB drop-in at install
  time, firefox-i18n-de/hunspell-de/impression in the offline repo and their
  offline installation.

### ISO r3 (`after-apps-20261022-r3`, packages 0.1.0-11) — verified 22 October 2026

SHA256 df01e7c2c022709da3e819af611e3340ccddb8078ce55c02219edb284f53934f,
4094722048 bytes. Same Hyprland 0.56.2-4 / Qt 6.12.0-3 / qtermwidget 2.4.0-1 as
r2; plugins rebuilt and symbol-checked. Offline repo 280 archives incl.
impression, firefox-i18n-de, hunspell-de. Fresh VM `r3-install-test-20261022`,
NIC carrier down: Berlin/German/German keyboard, Recommended + USB-Startmedium.

- Summary at 1280x800: buttons visible, content scrolls (noexpand) — PASS.
- Offline install 36/36 jobs PASS; Firefox/LibreOffice language packs,
  hunspell-de and Impression installed, `pacman -Qk` clean, stash removed.
- Installed GRUB: three entries only, default `linux-cachyos` 7.2.7 — PASS.
- SDDM login, plugins once, no configerrors/failed units, de/Berlin — PASS.
- New findings: (1) live keyboard stays US although the installer selects
  German; passwords are typed on US layout while the target expects German.
  (2) Hostname suggestion `cachyos-x8664` (upstream users.conf template).
  (3) Location default New York (useSystemTimezone; live has no zone) — not changed.
  (4) Dark-mode checkbox/radio indicators on the partition page are faint — not changed.
- Fixes for (1)/(2) prepared for r4: Settings IPC `setKeyboardLayout`,
  live-language.py `--keyboard`, LiveDesktopBridge reacts to GlobalStorage
  keyboardLayout; users.conf hostname template `${first}-windoesnot`.
  Desktop code changed -> package release 0.1.0-12.

### ISO r4 (DEFECTIVE) and r5 (`after-apps-20261022-r5`, packages 0.1.0-12)

- r4 hung after os-prober before showing the installer window. Cause: the new
  LiveDesktopBridge handler was a direct connection to GlobalStorage::changed,
  which Calamares emits from ~WriteLock while still holding its non-recursive
  mutex; the handler's value() call deadlocked. Fixed with Qt::QueuedConnection.
  Do not use r4.
- r5 SHA256 4abf53093cac9574dc0ab989945aa64776c39a43c7ae73572f173b7153cef38e,
  4094722048 bytes; out/latest.iso now points here. VM `r5-install-test-20261022`
  (vmtest / Zyklus-test-42, typed on German layout).
- Live keyboard follows the installer: US keys `zy-/` produce `yzß-` on the
  users page; liveuser settings keyboardLayout=de. Installed with a Z/y password,
  SDDM login with the same German keystrokes PASS. Hostname suggestion
  `vm-windoesnot`. Offline install 36/36, recommended selection, 0.1.0-12,
  `pacman -Qk` clean, de/Berlin, plugins once, no configerrors/failed units,
  HTTPS 200 — PASS. Checks: vm/r5-install-test-20261022/system-checks.json.
- hyprpaper (no wallpaper since r2 in headless/software VMs) crashes in
  Hyprtoolkit::CWaylandBuffer when aquamarine cannot allocate a GBM buffer
  (kms_swrast, DRM_IOCTL_MODE_CREATE_DUMB EPERM). Same packages as ISO18; ISO18
  was tested with VirGL. Booting the r5 disk with `--graphics gl`: hyprpaper runs,
  no new coredump. Upstream hyprtoolkit null-deref; affects only systems without
  3D acceleration (VMs without VirGL, missing GPU driver) — result: plain dark
  background, desktop otherwise works. Not reported upstream (needs user OK).
- Desktop source change (Settings IPC setKeyboardLayout) is NOT deployed to the
  host session; host desktop untouched.

### Online/offline live entries, bootloader choice and Btrfs backups (Codex)

User authorized the logical implementation after reviewing r5. Keep the tested
r5/latest.iso unchanged until the new image passes its own VM checks. No host
desktop, packages or bootloader changed.

- New build ID: installer-modes-20261022 (initially 0.1.0-12; now 0.1.0-13 for
  the Super-tap service fix described below). UEFI and BIOS entries select
  Online/Offline; Offline remains default, including LTS/fallback options.
- Both modes keep the tested ISO system base/native ABI. Online fetches exact
  snapshot archives+signatures over HTTPS; it does not mean a rolling base
  upgrade. Network failure does not silently use offline cache.
- Native bootloader step: GRUB/refind/systemd-boot/Limine; UEFI-only options
  filtered on BIOS and validated again by the installation job. GRUB remains
  our tested default. rEFInd+AI SDK not offered: it requires a separate hardware
  SDK integration, not merely another name for rEFInd.
- Selected bootloader dependency packages and Snapper included in the signed
  optional snapshot repository. Preparation happens before initramfs/bootloader.
  Final job maintains boot entries and initializes Btrfs root snapshots/timers;
  other filesystems and Live retain an unavailable/disabled notice.
- Tests passed so far: software/profile/checksum rejection; new mode/transaction
  tests (network errors, no offline network, no base replacement, Btrfs-only
  snapshots); native boot widget (BIOS filtering, selection, language change);
  generated profile contract including both firmware menus.
- Design and maintenance notes: docs/INSTALLATION-MODES.md. New image build and
  real bootloader/install tests are still pending.

Update: package release is now **0.1.0-13** for the real Super-tap sandbox fix.
ProtectHome=yes hid /run/user; tmpfs + read-only runtime bind allows the session
socket while keeping private home directories hidden. Actual VM tap/Win+Q
prototype passed. GRUB offline + Snapper/D-Bus/timers installed and booted PASS.
Online VM found stale configure-time Python copy, then public mirror HTTP403
with urllib. Runtime job sync + installed-file checker added; curl transport
real archive/signature/hash test passed. ISO13 SHA1112bbe9... is now under test
in fresh online Limine and net-disconnected systemd-boot VMs; r5 remains latest.


Final boot-test checkpoint (22 October, evening):
- systemd-boot offline: 39/39 installation jobs, automatic disk boot, normal
  SDDM login and all installed-system checks PASS. Fresh package13 Windows tap
  works without patching the guest. Evidence: vm/modes-sdboot-offline-20261022/.
- Previous Limine online image completed 39/39 jobs, including actual HTTPS
  downloads. Disk boot found duplicate OS groups and an empty default heading.
  The image now preserves the machine-ID inside the single WinDoesNot group and
  sets TARGET_OS_NAME before limine-update. The corresponding transaction test
  checks the generator input, not just the resulting display name.
- Current image SHA256: 648dafd06be518d270be466f733e55dd379b57a25eb5ac6aa7fe6e15784c8886
  (4,103,503,872 bytes). Fresh current-image tests: Limine online4 and rEFInd
  offline; installation/automatic disk boot results are recorded in
  checks/INSTALLATION-MODES-TEST-20261022.md when complete.
- No store integration, public release, package-repository export or host
  desktop/package/bootloader changes are part of this checkpoint.


Final result: Limine online4 and rEFInd offline both PASS on SHA648dafd0:
39/39 installation jobs, automatic disk boot without ISO, normal SDDM login,
plugins/config/package/service/localization/Snapper checks. Limine main7.2.7;
rEFInd currently automatically selects LTS6.18.50. No manual loader selection or
guest code patch used. Both final VMs are stopped, evidence retained. latest.iso
now points to this candidate. Full precise cross-version test matrix and known
limits: checks/INSTALLATION-MODES-TEST-20261022.md; structured current-image proof:
checks/installation-modes-final-20261022.json. This work block is complete.


### Store/update-repository groundwork — 22 October 2026 (Codex)

Completed bounded source-work block; latest ISO remains package13, no deployment
or publication. Store changes are uncommitted on base9cbb18c: full native
update+install transactions, contiguous target batching, native preflight before
AUR, automatic available-helper detection, optional-manager-aware Update All,
and root-helper argument validation without nodeps/ignore bypasses. A missing
AUR helper produces a clear error before executing any part of the plan.

20 Rust unit tests and the normal offline locked release build PASS. Repo builder
now accepts one optional independently versioned windoesnot-store while keeping
all four matching desktop packages mandatory; 6 real disposable metadata/repo-add
tests PASS. No actual system upgrade or GUI/Polkit/AUR install was attempted.

Evidence and exact source hashes: checks/store-integration-20261022/.
Actionable continuation: docs/HANDOFF-CODEX-STORE.md. Search DB isolation,
new pinned source release/PKGBUILD hash, target Store package + AppStream,
signed compatible update set/trust bootstrap and fresh VM tests remain. Do not
build changed Store sources from unchanged PKGBUILD tag0.2.0. Do not replace
public0.2.0 artifacts. New desktop release must be at least0.1.0-14.

SourceForge setup separately verified read-only: windoesnot / bennch90, official
host fingerprint matched, public-key SFTP login + empty project listing PASS;
no upload or API-key use. See checks/sourceforge-access-20261022.json.


### Store integration test image r6 (`store-r6-20261022`, packages 0.1.0-14, store 0.3.0) — Claude

- Store pinned in sources.json (commit 339ec64). prepare-profile.py stages a git-archive
  of exactly that commit plus a reproducible vendored-crate archive and writes real
  SHA256 sums (no SKIP). Offline makepkg with empty CARGO_HOME: 16+7 tests PASS.
- build-image-packages.sh builds the store as nobody in the image (offline), checks it
  with `check-packages.py --store`, installs it, then removes the build-only toolchain
  from iso/packages-build-only.txt (removed: clang clang-libs compiler-rt libgit2 lld
  llhttp llvm llvm-lit rust; llvm-libs/mesa kept). appstream + archlinux-appstream-data
  added; glycin-jxl loader present.
- ISO SHA256 bdc9c55aeb320b0abbf8537617baa33dc4f5a58f1e62ef5572f19039888249bb. NOT latest.iso.
- Live VM `store-r6-test-20261022` (gl, headless; screenshots via guest grim):
  store opens from the taskbar button, running indicator OK.
- Bug found and fixed in source (needs package 0.1.0-15): Quickshell's Qt reads the icon
  theme from gsettings once at startup; Settings.qml sets it later, so a new user's first
  session resolves themed icons from the fallback (store button showed breeze boxes).
  extras/start-quickshell.sh now writes the configured iconTheme to gsettings before
  starting Quickshell. Verified live after `gsettings reset`: Win11 store bag shown.
- Open observation: faint text "How do I exit vim???" over the live taskbar centre;
  not found in project sources; absent in r5 installed screenshots. Unexplained.
- Pending: offline install (stopped at keyboard page), then store search over network,
  repo install, AUR via paru, full upgrade path, ABI-conflict abort on a 0.1.0-13 image.
  Store commits not pushed, no 0.3.0 tag.

#### r6 installed-system results (23 October, VM `store-r6-test-20261022`, GRUB, offline install)

- Offline install 39/39 jobs, Berlin/German, recommended apps; GRUB boots linux-cachyos;
  SDDM login (vmtest / Test12345); store 0.3.0-1 and desktop 0.1.0-14 installed.
- Search on the fresh offline system: user sync copy refreshed via fakeroot, system
  /var/lib/pacman/sync stayed empty; repo + AUR (paru) hits — PASS.
- Repo install htop through the store: `pacman -Syu --needed --noconfirm htop` via
  pkexec helper — PASS (upstream zlib -> zlib-ng-compat replacement included).
- AUR install: FAIL in 0.3.0@339ec64 — target `pfetch` resolved by paru to the repo
  provider pfetch-rs. Fixed (store 864c988): AUR installs use `aur/<name>`; probe build
  installed AUR pfetch 1.11.0-1 — PASS. Two polkit prompts per AUR install (helper, then
  paru's pkexec) — UX note, unchanged.
- ABI conflict (simulated: local repo with metadata-only hyprland 0.56.2-5 before
  [cachyos]): preflight -Syu refused with "installing hyprland (0.56.2-5) breaks
  dependency 'hyprland=0.56.2-4' required by windoesnot-plugins"; hyprland unchanged,
  paru never started, pfetch-git not built — PASS. Store now shows a German dialog
  explaining that matching WinDoesNot components are not available yet. Test repo removed.
- Re-login twice: hyprbars + hyprdrag loaded, no configerrors — PASS.
- Embedded terminal: FAIL (pre-existing, also on the host): QML plugin not loadable.
  Causes: (1) RUNPATH pointed at the temporary component build dir; (2) Quickshell
  0.3 serves the config as qs:@ URLs, from which Qt cannot load native plugins.
  Fixed: build-components.sh links with RUNPATH $ORIGIN and refuses other RUNPATHs;
  AgentTerminalPanel imports `LocalTerminal` by module name; start-quickshell.sh puts
  /usr/lib/windoesnot (then the per-user copy) on QML_IMPORT_PATH. Probe: panel loader
  Ready, libraries mapped from /usr/lib/windoesnot. The interactive terminal is only
  offered with an API key and was not exercised.
- "How do I exit vim???" text = Hyprland splash rendered by hyprpaper (default config
  lacked `splash = false`, which Quickshell only writes after a wallpaper change). Fixed
  in desktop/defaults hyprpaper.conf. Hyprland "updated to 0.56.2" news dialog on the
  second login: `ecosystem.no_update_news = true` in reference.lua. Both verified live.
- Other store fixes in 864c988: dialogs carry app id me.windoesnot.Store (no second
  taskbar entry), tile install button no longer opens details, remaining DE strings,
  fakeroot dependency.
- Open, not fixed: search tiles do not refresh installed state after a transaction;
  polkit agent window has a missing taskbar icon; letter tiles for htop (no AppStream
  icon match checked yet).
- Desktop release now 0.1.0-15. Store pin 864c988 (still 0.3.0, unpublished). r7 build
  `store-r7-20261023` follows; store commits remain unpushed until r7 passes.

#### r7 (`store-r7-20261023`, desktop 0.1.0-15, store 0.3.0@864c988) — VM `store-r7-test-20261023`

- ISO SHA256 43d8e093cb245af833bcc66f90b06cfa8c654b229a594549aae37e493ede11b8. Image checks:
  terminal libraries RUNPATH $ORIGIN, launcher sets QML_IMPORT_PATH, hyprpaper default
  `splash = false`; store tests 18+7 in the image build.
- Live first session: store bag icon, no splash — PASS. Offline install 39/39 (GRUB, Btrfs,
  Berlin/German, recommended apps).
- Installed first login: store bag icon, no splash, no Hyprland news dialog, plugins
  hyprbars+hyprdrag, no configerrors, no failed units, LocalTerminal libraries loaded
  from /usr/lib/windoesnot at startup — PASS.
- New finding: catalogue icons (JPEG XL) rendered as empty pictures. GTK 4.24
  Image::from_file yields an SVG paintable for .jxl; Gdk.Texture.new_from_filename decodes
  them (30 icons in 0.07 s). The host only looked fine through Flathub PNG icons. Fixed
  (store ec92e22): icons load as textures, letter tile on decode failure. Probe: GIMP
  search result and home picks (GIMP, OBS, KeePassXC) show real icons; VLC marked installed.
- Mixed queue htop (repo) + pfetch (AUR): installed, AUR via `aur/pfetch`. Found a stray
  English "Input Required" dialog (paru prompt text under --noconfirm) and a redundant
  second native -Syu. Fixed in ec92e22 (no prompt dialogs for --noconfirm commands; one
  native upgrade per plan guards later AUR builds; unit test). Probe rerun: one
  `pacman -Syu --needed --noconfirm htop`, then paru, no stray dialog — PASS.
- r8 (`store-r8-20261023`) pins ec92e22 so the image carries exactly the probed store.

#### r8 (`store-r8-20261023`, desktop 0.1.0-15, store 0.3.0@ec92e22) — VM `store-r8-test-20261023`

- ISO SHA256 13295f24f2cb2068f0dc6543ee1e66e2b79931157d6c0cc3c2a6579b5596634f; store tests 19+7
  in the image build; build-only toolchain removed again.
- Offline install 39/39 (GRUB, Btrfs, Berlin/German, recommended apps). Installed first
  login: plugins loaded, no configerrors, no failed units, terminal module loaded.
- Packaged store (no probe binary): GIMP search shows the AppStream JPEG XL icon; mixed
  queue htop (repo) + pfetch (AUR) — one `pacman -Syu --needed --noconfirm htop`, then paru
  with aur/pfetch; both installed; only the store window and its completion dialog open,
  both with class me.windoesnot.Store — PASS. System sync DBs were refreshed only by the
  helper's full upgrade.
- Not tested on r8: online install mode, rEFInd/systemd-boot/Limine (unchanged code since
  Codex's package-13 tests), interactive embedded terminal (needs API key), real
  WinDoesNot component update through a signed repository (does not exist yet).
- latest.iso deliberately unchanged (still Codex's package-13 multi-bootloader candidate).
  Store commits 235f882..ec92e22 are local only; no push, no tag.


#### r8 bootloader/mode completion (Codex, 23 October)

Same unchanged SHA13295f24... ISO tested in fresh VMs:
- modes-r8-limine-online: 39/39 jobs, recommended optional programs downloaded
  online, automatic disk boot without ISO, normal SDDM login; main7.2.7 PASS.
- modes-r8-refind-offline: NIC disconnected before installer, 39/39 jobs,
  automatic disk boot/normal login; automatically selected LTS6.18.50 PASS.
- modes-r8-sdboot-offline: actual carrier0, 39/39 jobs, automatic disk boot/normal
  login; main7.2.7 PASS. Early GUI automation initially ran before readiness;
  corrected and re-reviewed German/Berlin/keyboard/loader/disk summary before
  any installation. No image change required.
All three: desktop15, Store0.3.0-1/AppStream package files, plugins once,
configerrors/failed services empty, localization, Snapper config/snapshot/timers/
D-Bus and actual Windows tap PASS. Logs/JSON/screenshots retained, VMs stopped.

latest.iso now points to store-r8-20261023. Earlier candidate retained. Together
with Claude's r8 GRUB/offline/Store tests, this covers all four UEFI loaders and
Online, not all eight possible combinations. Precise matrix and structured
proof: checks/R8-BOOT-MODES-20261023.md and checks/r8-boot-modes-20261023.json.
No source/runtime change, no host deployment, no push/tag/upload/publication.
The signed production update repository and real components update remain open.


## Codex 23.10.2026 — signierter Komponentenupdate-Test

Privates Repo und Client-Trust-Bootstrap ergänzt und geprüft. Vier in einer
frischen r8-Overlay-VM nativ gebaute Pakete0.1.0-16 per echtem vollen pacman -Syu
installiert, inklusive regulärer Distro-Updates. Manipulierte Datenbanksignatur
und Paket vor Transaktion abgewiesen. Normale erneute Anmeldung, beide Plugins,
private Dateien, Snapper, Windows-Tipp und eingebettetes Terminal bestanden.
6 Repo-Vertragstests + 6 echte Trust-/Manipulationstests bestanden.
Nachweise: checks/repository-update-20261023/. Keine neue upstream-ABI getestet.
Nur kurzlebiger Testschlüssel, kein Produktionsschlüssel/Upload/Host-Update.
Wichtiger Vorbehalt: CachyOS-Pacman braucht beim aktuellen Hinweis eine temporäre
VM-Pfadumleitung; entfernt. Regulärer Fix und erneuter Test fehlen vor Release.
Details: docs/SIGNED-UPDATE-REPO.md.


## Codex 23.10.2026 — ruhiger Start / Plymouth

Neuer Benutzerauftrag umgesetzt: ISO-/Installer-Quellen um Plymouth, WinDoesNot-
Logo/Spinner, errors-only Bootparameter und automatischen Diagnosehandler ergänzt.
Eigene installierte systemd-boot-VM: normaler Start, absichtlich fehlgeschlagener
Dienst mit sichtbarem Journal, Esc-Detailkonsole und normale Desktopanmeldung mit
beiden Plugins/Snapper bestanden. Testverzögerungen entfernt; VM heruntergefahren.
Finales erzeugtes Profil geprüft, vier Boot-Helfertests und Installer-Modustests
bestanden. Keine neue ISO gebaut, Live-/Installerpfad mit Splash und andere Loader
noch ungetestet. Details docs/BOOT-SPLASH.md, checks/boot-splash-20261023/.
