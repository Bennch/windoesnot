# WinDoesNot login screen

Based on [thyx](https://github.com/rccyx/thyx) by rccyx (MIT, `LICENSE`), commit `68a0d7d9617a`.
Changes: WinDoesNot wordmark (`img/`), absolute background paths in `src/effects/Background.qml`,
WinDoesNot palettes and presets. Removed: install scripts, Nix files and the other backgrounds.

- `theme.conf` = default (Cinder, animated). A variant is selected by copying
  `presets/<name>.conf` to `theme.conf.user` (SDDM reads it on top of `theme.conf`).
- Presets: `cinder` (video), `cinder-still`, `fire`, `glut-dunkel`.
- `backgrounds/cinder.mp4`: video by [Graphicfresh Studio](https://www.pexels.com/@graphicfresh-studio-2147859311/)
  (Pexels license); `cinder-still.jpg` is a frame of it.
- `fonts/`: Plus Jakarta Sans (SIL Open Font License, `fonts/OFL.txt`), installed system-wide by the package.
- `Xsetup`: applies the configured keyboard layout before the greeter starts (WinDoesNot).
