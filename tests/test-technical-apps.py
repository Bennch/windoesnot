#!/usr/bin/env python3
"""Start menu: settings dialogs, monitors, console tools and helpers are 'technical' (hidden in the grid); real programs and WinDoesNot's own apps are not."""
from pathlib import Path
import os
import runpy
import tempfile

mod = runpy.run_path(str(Path(__file__).resolve().parents[1] / 'desktop/bin/windoesnot-list-apps'))
launchers = mod['launchers']

TECHNICAL = {
    'org.gnome.Settings.desktop': 'Name=Einstellungen\nCategories=GNOME;GTK;Settings;',
    'nvidia-settings.desktop': 'Name=NVIDIA X-Server-Einstellungen\nCategories=Settings;HardwareSettings;',
    'org.pulseaudio.pavucontrol.desktop': 'Name=Lautstärkeregler\nCategories=AudioVideo;Audio;Mixer;GTK;Settings;',
    'org.gnome.Usage.desktop': 'Name=Auslastung\nCategories=GNOME;GTK;System;Monitor;',
    'btop.desktop': 'Name=btop++\nCategories=System;Monitor;ConsoleOnly;\nTerminal=true',
    'vim.desktop': 'Name=Vim\nCategories=Utility;TextEditor;\nTerminal=true',
    'electron36.desktop': 'Name=Electron 36\nCategories=Development;GTK;',
    'jconsole-java-openjdk.desktop': 'Name=OpenJDK Java 27 Console\nCategories=Application;System;',
    'yad-icon-browser.desktop': 'Name=Icon Browser\nCategories=GTK;Development;',
    'nwg-icon-picker.desktop': 'Name=Icon picker\nCategories=Utility;',
    'octopi-notifier.desktop': 'Name=Octopi Notifier\nCategories=GNOME;GTK;System;',
    'octopi-cachecleaner.desktop': 'Name=Octopi CacheCleaner\nCategories=GNOME;GTK;System;',
    'org.gnome.tweaks.desktop': 'Name=Optimierungen\nCategories=GNOME;GTK;Utility;',
    'org.gnome.ColorProfileViewer.desktop': 'Name=Farbprofilbetrachter\nCategories=GNOME;GTK;System;',
    'qdbusviewer.desktop': 'Name=Qt D-Bus Viewer\nCategories=Qt;Development;',
    'blackmagicraw-speedtest.desktop': 'Name=Blackmagic RAW Speed Test\nCategories=Video',
    'org.cachyos.KernelManager.desktop': 'Name=CachyOS Kernel Manager\nCategories=Qt;System;',
    'cups.desktop': 'Name=Druckerverwaltung\nCategories=System;Printing;',
    'hplip.desktop': 'Name=HP Device Manager\nCategories=Application;Utility;',
    'gnome-nettool.desktop': 'Name=Netzwerkdiagnose\nCategories=System;Utility;GNOME;GTK;',
}
PROGRAMS = {
    'firefox.desktop': 'Name=Firefox\nCategories=GNOME;GTK;Network;WebBrowser;',
    'org.gnome.Nautilus.desktop': 'Name=Dateien\nCategories=GNOME;GTK;Utility;Core;FileManager;',
    'org.gnome.Calculator.desktop': 'Name=Taschenrechner\nCategories=GNOME;GTK;Utility;Calculator;',
    'com.mitchellh.ghostty.desktop': 'Name=Ghostty\nCategories=System;TerminalEmulator;',
    'org.videolan.VLC.desktop': 'Name=VLC Media Player\nCategories=AudioVideo;Player;Recorder;',
    'com.visualstudio.code.desktop': 'Name=Visual Studio Code\nCategories=TextEditor;Development;IDE;',
    'steam.desktop': 'Name=Steam\nCategories=Network;FileTransfer;Game;',
    'org.gimp.GIMP.desktop': 'Name=GNU Image Manipulation Program\nCategories=Graphics;2DGraphics;RasterGraphics;GTK;',
    'com.wps.Office.desktop': 'Name=WPS 2019\nCategories=Office;WordProcessor;Qt;',
    'com.obsproject.Studio.desktop': 'Name=OBS Studio\nCategories=AudioVideo;Recorder;',
    'org.gnome.Calendar.desktop': 'Name=Kalender\nCategories=GNOME;GTK;Office;Calendar;Core;',
    'DaVinciResolve.desktop': 'Name=DaVinci Resolve\nCategories=',
    # WinDoesNot's own apps, also those in the Settings category
    'windoesnot-settings.desktop': 'Name=WinDoesNot Einstellungen\nCategories=Settings;DesktopSettings;',
    'me.windoesnot.DeviceManager.desktop': 'Name=Geräte-Manager\nCategories=Settings;HardwareSettings;',
    'me.windoesnot.Bluetooth.desktop': 'Name=WinDoesNot Bluetooth\nCategories=Settings;HardwareSettings;',
    'me.windoesnot.Store.desktop': 'Name=WinDoesNot Store\nCategories=System;PackageManager;',
}
with tempfile.TemporaryDirectory(prefix='wdn-technical-') as tmp:
    base = Path(tmp)
    apps = base / 'usr'; apps.mkdir()
    for table in (TECHNICAL, PROGRAMS):
        for index, (name, body) in enumerate(table.items()):
            (apps / name).write_text(f'[Desktop Entry]\nType=Application\n{body}\nExec=app{len(list(apps.iterdir()))}\nIcon=x\n')
    # wine helper launchers made by a Windows installer land in the user's own applications folder
    home = base / 'home'; user = home / '.local/share/applications'; user.mkdir(parents=True)
    (user / 'wine-Programs-Game-Uninstall.desktop').write_text('[Desktop Entry]\nType=Application\nName=Uninstall Game\nExec=wine-uninstall\n')
    (user / 'wine-Programs-Game-Game.desktop').write_text('[Desktop Entry]\nType=Application\nName=Game\nExec=wine-game\n')
    (user / 'my-tool.desktop').write_text('[Desktop Entry]\nType=Application\nName=My uninstall helper\nExec=mytool\nTerminal=true\n')
    old = os.environ.get('HOME'); os.environ['HOME'] = str(home)
    try:
        rows = {row['id']: row for row in launchers([apps, user], 'de', True)}
    finally:
        os.environ['HOME'] = old
    wrong = [i for i in TECHNICAL if not rows[i]['technical']]
    assert not wrong, f'should be technical: {wrong}'
    wrong = [i for i in PROGRAMS if rows[i]['technical']]
    assert not wrong, f'should stay visible: {wrong}'
    assert rows['wine-Programs-Game-Uninstall.desktop']['technical'], 'wine uninstall helper'
    assert not rows['wine-Programs-Game-Game.desktop']['technical'], 'the game itself stays'
    assert not rows['my-tool.desktop']['technical'], "the user's own launchers are never hidden"
print(f'PASS: technical apps: {len(TECHNICAL)} helper/settings/console entries hidden, {len(PROGRAMS)} real programs and own apps visible')
