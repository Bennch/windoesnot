# Overview (workspace overview) - upstream source

- Upstream: https://github.com/Shanu-Kumawat/quickshell-overview (MIT, see `LICENSE`)
- Imported commit: `b327c1adcf1cb7e0b26cce1f91e9faa0e9eac8d1` (2026-11-06, "ci: install qt6-declarative-dev-tools for qmllint")
- Imported on: 2026-11-09. Previous WinDoesNot copy was based on upstream ~`e2e4b13` ("improvements", Oct 2025).
- Taken over: `shell.qml`, `quickshell-overview.qml` (Matugen template), `assets/`, `common/`, `modules/`, `services/`, `LICENSE`, `config.example.json`.
  Not taken over: `README.md`, `hyprland_docs/`, `flake.*`, `.github/`, upstream `config.json` (it enables the
  scrolling-layout strip; we keep the normal grid by default).
- Started with `qs -c overview` (see `desktop/config/hypr/lua/reference.lua`).

## WinDoesNot changes on top of upstream

1. **Hyprland IPC via `windoesnot-hyprctl`** (`services/HyprlandData.qml`): all `hyprctl ... -j` reads use the
   desktop's adapter; actions go through the new `HyprlandData.dispatch("workspace 3")`, which calls
   `windoesnot-hyprctl dispatch <name> <args>` (the adapter maps legacy dispatcher names to Lua dispatchers).
   Every `Hyprland.dispatch(...)` / `Hyprland.usingLua` branch in `modules/overview/*.qml` was reduced to the
   legacy-name call through this function (also fixes closing via middle click on Lua configs, upstream #50).
   `HyprlandData.usingLua` is fixed to `true` (floating-window restore logic after workspace moves stays active).
2. **Live design scheme** (new `common/WinDoesNotTheme.qml`, `common/Appearance.qml`, `common/Config.qml`):
   `accentColor`, `darkMode`, `borderRadius` (+ `inactiveBorderColor`) are read from
   `~/.config/quickshell/default/settings.txt` (FileView with inotify watch + 2 s re-read as safety net),
   so changes in Settings apply to an open or running overview immediately. Defaults: `#FE6F2D`, dark, radius 6.
   - New colour source `windoesnot` (now the default of `appearance.colorSource`); upstream sources
     `default`, `matugen`, `caelestia` remain selectable in `~/.config/quickshell/overview/config.json`.
   - Palette: neutral surfaces like the desktop panels, accent as primary/secondary (active workspace frame).
   - Panel and strip frame is a 2 px accent border (`Appearance.borderWidth`, `colLayer0Border`, `colLayer2Border`).
   - All corner radii (`Appearance.rounding.*`) follow `borderRadius`.
3. No other upstream behaviour was changed; upstream defaults (special/named workspaces shown, hideEmptyRows,
   Alt-Tab style keyboard cycling) apply.

## Updating

Diff a fresh upstream checkout against this folder; re-apply points 1 and 2 (they touch `HyprlandData.qml`,
`Appearance.qml`, `Config.qml`, `qmldir`, the `Hyprland.dispatch` call sites and two `border.width` lines in
`OverviewWidget.qml` / `WorkspaceStrip.qml`).
