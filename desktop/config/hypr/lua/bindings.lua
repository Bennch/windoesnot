-- Bindings retain their original order.
hl.bind("SUPER + Q", hl.dsp.exec_cmd("ghostty"), {}) -- legacy:272
hl.bind("SUPER + C", hl.dsp.window.close({}), {}) -- legacy:273
hl.bind("SUPER + M", hl.dsp.exit(), {}) -- legacy:274
hl.bind("SUPER + E", hl.dsp.exec_cmd("nautilus"), {}) -- legacy:275
hl.bind("SUPER + V", hl.dsp.window.float({["action"]="toggle"}), {}) -- legacy:276
hl.bind("SUPER + R", hl.dsp.global("quickshell:toggle-startmenu"), {}) -- legacy:278
hl.bind("CTRL + ALT + Delete", hl.dsp.exec_cmd("gnome-system-monitor"), {}) -- legacy:279
hl.bind("SUPER + S", hl.dsp.exec_cmd("echo 1 > /tmp/qs-search-toggle"), {}) -- legacy:281
hl.bind("SUPER + H", hl.dsp.exec_cmd("~/.config/hypr/hide_windows.sh"), {}) -- legacy:282
hl.bind("SUPER + N", hl.dsp.exec_cmd("swaync-client -t -sw"), {}) -- legacy:283
hl.bind("SUPER + P", hl.dsp.exec_cmd("hyprpicker -a -f hex"), {}) -- legacy:284
hl.bind("SUPER + F", hl.dsp.window.fullscreen({["mode"]="fullscreen"}), {}) -- legacy:285
hl.bind("SUPER + J", hl.dsp.layout("togglesplit"), {}) -- legacy:288
hl.bind("PRINT", hl.dsp.exec_cmd("hyprshot -m region"), {}) -- legacy:291
hl.bind("SUPER + PRINT", hl.dsp.exec_cmd("hyprshot -m region"), {}) -- legacy:292
hl.bind("SUPER + F12", hl.dsp.exec_cmd("windoesnot-hyprctl dispatch workspace 10 && sleep 0.3 && windoesnot-hyprctl dispatch workspace previous"), {}) -- legacy:295
hl.bind("SUPER + F11", hl.dsp.exec_cmd("windoesnot-hyprctl dispatch setfloating && sleep 0.2 && windoesnot-hyprctl dispatch settiled"), {}) -- legacy:298
hl.bind("SUPER + left", hl.dsp.focus({["direction"]="left"}), {}) -- legacy:301
hl.bind("SUPER + right", hl.dsp.focus({["direction"]="right"}), {}) -- legacy:302
hl.bind("SUPER + up", hl.dsp.focus({["direction"]="up"}), {}) -- legacy:303
hl.bind("SUPER + down", hl.dsp.focus({["direction"]="down"}), {}) -- legacy:304
hl.bind("SUPER + 1", hl.dsp.focus({["workspace"]="1"}), {}) -- legacy:307
hl.bind("SUPER + 2", hl.dsp.focus({["workspace"]="2"}), {}) -- legacy:308
hl.bind("SUPER + 3", hl.dsp.focus({["workspace"]="3"}), {}) -- legacy:309
hl.bind("SUPER + 4", hl.dsp.focus({["workspace"]="4"}), {}) -- legacy:310
hl.bind("SUPER + 5", hl.dsp.focus({["workspace"]="5"}), {}) -- legacy:311
hl.bind("SUPER + 6", hl.dsp.focus({["workspace"]="6"}), {}) -- legacy:312
hl.bind("SUPER + 7", hl.dsp.focus({["workspace"]="7"}), {}) -- legacy:313
hl.bind("SUPER + 8", hl.dsp.focus({["workspace"]="8"}), {}) -- legacy:314
hl.bind("SUPER + 9", hl.dsp.focus({["workspace"]="9"}), {}) -- legacy:315
hl.bind("SUPER + 0", hl.dsp.focus({["workspace"]="10"}), {}) -- legacy:316
hl.bind("SUPER + SHIFT + 1", hl.dsp.window.move({["workspace"]="1",["follow"]=true}), {}) -- legacy:319
hl.bind("SUPER + SHIFT + 2", hl.dsp.window.move({["workspace"]="2",["follow"]=true}), {}) -- legacy:320
hl.bind("SUPER + SHIFT + 3", hl.dsp.window.move({["workspace"]="3",["follow"]=true}), {}) -- legacy:321
hl.bind("SUPER + SHIFT + 4", hl.dsp.window.move({["workspace"]="4",["follow"]=true}), {}) -- legacy:322
hl.bind("SUPER + SHIFT + 5", hl.dsp.window.move({["workspace"]="5",["follow"]=true}), {}) -- legacy:323
hl.bind("SUPER + SHIFT + 6", hl.dsp.window.move({["workspace"]="6",["follow"]=true}), {}) -- legacy:324
hl.bind("SUPER + SHIFT + 7", hl.dsp.window.move({["workspace"]="7",["follow"]=true}), {}) -- legacy:325
hl.bind("SUPER + SHIFT + 8", hl.dsp.window.move({["workspace"]="8",["follow"]=true}), {}) -- legacy:326
hl.bind("SUPER + SHIFT + 9", hl.dsp.window.move({["workspace"]="9",["follow"]=true}), {}) -- legacy:327
hl.bind("SUPER + SHIFT + 0", hl.dsp.window.move({["workspace"]="10",["follow"]=true}), {}) -- legacy:328
hl.bind("SUPER + mouse_down", hl.dsp.focus({["workspace"]="e+1"}), {}) -- legacy:335
hl.bind("SUPER + mouse_up", hl.dsp.focus({["workspace"]="e-1"}), {}) -- legacy:336
hl.bind("SUPER + mouse:272", hl.dsp.window.drag(), {["mouse"]=true}) -- legacy:339
hl.bind("SUPER + mouse:273", hl.dsp.window.resize(), {["mouse"]=true}) -- legacy:340
hl.bind("XF86AudioRaiseVolume", hl.dsp.exec_cmd("wpctl set-mute @DEFAULT_AUDIO_SINK@ 0 && wpctl set-volume -l 1 @DEFAULT_AUDIO_SINK@ 5%+"), {["repeating"]=true,["locked"]=true}) -- legacy:343
hl.bind("XF86AudioLowerVolume", hl.dsp.exec_cmd("wpctl set-mute @DEFAULT_AUDIO_SINK@ 0 && wpctl set-volume @DEFAULT_AUDIO_SINK@ 5%-"), {["repeating"]=true,["locked"]=true}) -- legacy:344
hl.bind("XF86AudioMute", hl.dsp.exec_cmd("wpctl set-mute @DEFAULT_AUDIO_SINK@ toggle"), {["repeating"]=true,["locked"]=true}) -- legacy:345
hl.bind("XF86AudioMicMute", hl.dsp.exec_cmd("wpctl set-mute @DEFAULT_AUDIO_SOURCE@ toggle"), {["repeating"]=true,["locked"]=true}) -- legacy:346
hl.bind("XF86MonBrightnessUp", hl.dsp.exec_cmd("brightnessctl -e4 -n2 set 5%+"), {["repeating"]=true,["locked"]=true}) -- legacy:347
hl.bind("XF86MonBrightnessDown", hl.dsp.exec_cmd("brightnessctl -e4 -n2 set 5%-"), {["repeating"]=true,["locked"]=true}) -- legacy:348
hl.bind("XF86AudioNext", hl.dsp.exec_cmd("playerctl next"), {["locked"]=true}) -- legacy:351
hl.bind("XF86AudioPause", hl.dsp.exec_cmd("playerctl play-pause"), {["locked"]=true}) -- legacy:352
hl.bind("XF86AudioPlay", hl.dsp.exec_cmd("playerctl play-pause"), {["locked"]=true}) -- legacy:353
hl.bind("XF86AudioPrev", hl.dsp.exec_cmd("playerctl previous"), {["locked"]=true}) -- legacy:354
hl.bind("SUPER + TAB", hl.dsp.exec_cmd("qs ipc -c overview call overview toggle"), {}) -- legacy:356
hl.bind("ALT + Tab", hl.dsp.exec_cmd("snappy-switcher next"), {}) -- legacy:358
hl.bind("ALT + SHIFT + Tab", hl.dsp.exec_cmd("snappy-switcher prev"), {}) -- legacy:359
