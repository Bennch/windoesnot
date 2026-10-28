import QtQuick
import QtQuick.Layouts
import QtQuick.Controls
import Qt5Compat.GraphicalEffects
import Quickshell
import Quickshell.Io
import Quickshell.Hyprland
import Quickshell.Widgets
import "i18n/Lang.js" as Lang
import "widgets"

FloatingWindow {
    id: settingsMenu
    visible: false
    implicitWidth: Math.min(900, screen ? Math.max(1, screen.width - 16) : 900)
    implicitHeight: Math.min(700, screen ? Math.max(1, screen.height - 61) : 700)
    color: "transparent"
    title: "quickshell-settings"
    screen: {
        for (var i = 0; i < Quickshell.screens.length; i++) {
            if (Quickshell.screens[i].name === primaryMonitor) {
                return Quickshell.screens[i]
            }
        }
        return Quickshell.screens.length > 0 ? Quickshell.screens[0] : null
    }

    // External references (passed from shell.qml)
    property var workspaceContainer
    property var panelWindow

    // Track if file dialog is open to prevent auto-close
    property bool fileDialogOpen: false
    property var authentication: null
    readonly property bool backupAuthenticationActive: authentication !== null && authentication.embedded

    HyprlandFocusGrab {
        id: settingsFocusGrab
        windows: [settingsMenu]
        active: settingsMenu.visible && !settingsMenu.fileDialogOpen && !settingsMenu.backupAuthenticationActive && !settingsMenu.colorPaletteVisible
        onCleared: {
            if (!settingsMenu.fileDialogOpen && !settingsMenu.backupAuthenticationActive) {
                settingsMenu.visible = false
            }
        }
    }

    // Wenn Settings geschlossen wird, schließe auch colorPalette
    onVisibleChanged: {
        if (!visible) {
            colorPaletteVisible = false
        }
    }

    property string currentCategory: "desktop"

    // Scrollposition zurücksetzen beim Kategorie-Wechsel
    onCurrentCategoryChanged: {
        if (settingsFlickable) {
            settingsFlickable.contentY = 0
        }
    }

    property string accentColor: "#FE6F2D"
    property string inactiveBorderColor: "#595959"
    property int borderRadius: 10
    property int windowGaps: 5
    property bool workspaceToggleEnabled: true
    property bool showSearchButton: true
    property bool showSettingsButton: true
    property bool showStoreButton: true
    property string taskbarAlignmentSetting: "center"
    property string primaryMonitor: ""

    // Weather settings
    property bool showOllamaTray: false
    property bool showDockerTray: false
    property bool showNearbyTray: true
    property bool weatherEnabled: false
    property string weatherLocation: "tray"  // "tray" | "taskbar"
    property int weatherTaskbarIndex: -1  // position in taskbar model (-1 = end)
    property int weatherStartAreaSlot: -1  // -1 = in app repeater, 0/1/2 = before start / after start / after settings
    property string trayOrder: "weather,audio,bluetooth,network,docker,ollama"
    property string weatherCity: ""
    property real weatherLatitude: 0.0
    property real weatherLongitude: 0.0

    // Start menu sidebar settings
    property string startMenuSidebarPosition: "left"
    property bool startMenuShowAllApps: true
    property bool startMenuShowPersonalized: true
    property bool startMenuShowDesktop: true
    property bool startMenuShowDocuments: true
    property bool startMenuShowDownloads: true
    property bool startMenuShowPictures: true
    property bool startMenuShowMusic: true
    property bool startMenuShowVideos: true
    // Construction-time bindings emit changes before Component.onCompleted.
    // Never write defaults until the saved settings have actually been read.
    property bool isLoadingSettings: true
    property bool colorPaletteVisible: false
    property string colorPaletteTarget: "accent"  // "accent" or "inactive"

    // Desktop settings
    property int desktopIconSize: 64
    property int desktopGridSize: 16
    property bool desktopShowTrash: true
    property int desktopLabelLines: 2

    // Appearance settings
    property string startOrbStyle: "classic"
    property string startOrbCustomSource: ""
    property bool darkMode: true
    property string gtkTheme: ""  // Current active theme (auto-updated from gsettings)
    property string gtkThemeDark: "adw-gtk3-dark"  // Preferred theme for dark mode
    property string gtkThemeLight: "adw-gtk3"      // Preferred theme for light mode
    property string cursorTheme: "Adwaita"
    property string iconTheme: "Win11"
    property string windowMode: "tiling"  // "tiling" or "floating"
    property bool hyprbarsPluginEnabled: true  // Enable/disable titlebar via bar_height
    property bool hyprbarsEnabled: false
    property int hyprbarsHeight: 30
    property string hyprbarsButtonAlign: "right"  // "left" or "right"

    // Individual button toggles
    property bool hyprbarsCloseButtonEnabled: true
    property bool hyprbarsMaxButtonEnabled: true
    property bool hyprbarsMinButtonEnabled: true

    // Hyprbars Design - Windows 11 Style
    property string hyprbarsBarColor: "rgba(2B2B2BDD)"
    property bool hyprbarsBarBlur: true
    property string hyprbarsTextColor: "#cccccc"
    property string hyprbarsBarColorDark: "rgba(2B2B2BDD)"  // Dark transparent
    property string hyprbarsBarColorLight: "rgba(FFFFFFDD)"  // White transparent
    property string hyprbarsTextColorDark: "#cccccc"  // Light gray text for dark mode
    property string hyprbarsTextColorLight: "#000000"  // Black text for light mode

    property int hyprbarsTextSize: 10
    property string hyprbarsTextFont: "Sans"
    property string hyprbarsTextAlign: "center"
    property bool hyprbarsBarTitleEnabled: true
    property int hyprbarsBarPadding: 10
    property int hyprbarsButtonPadding: 2

    // Hyprbars Button Colors (transparent for Windows 11 style)
    property string hyprbarsCloseButtonColor: "rgba(00000000)"
    property string hyprbarsMaxButtonColor: "rgba(00000000)"
    property string hyprbarsMinButtonColor: "rgba(00000000)"

    // Button Text Colors - Dark Mode (light icons)
    property string hyprbarsButtonTextColorDark: "#ffffff"  // White X
    property string hyprbarsButtonTextColorNeutralDark: "#cccccc"  // Light gray for maximize/minimize

    // Button Text Colors - Light Mode (dark icons - alle gleich dunkel)
    property string hyprbarsButtonTextColorLight: "#000000"  // Black X
    property string hyprbarsButtonTextColorNeutralLight: "#000000"  // Black for maximize/minimize (same as close)

    // Current active button text colors
    property string hyprbarsButtonTextColor: "#ffffff"
    property string hyprbarsButtonTextColorNeutral: "#cccccc"

    // Input settings - Mouse
    property real mouseSensitivity: 0.0  // -1.0 to 1.0
    property string mouseAccelProfile: "flat"  // "flat" or "adaptive"
    property int followMouse: 1  // 0=disabled, 1=move, 2=move+focus, 3=focus

    // Input settings - Keyboard
    property string keyboardLayout: "us"
    property int repeatRate: 25
    property int repeatDelay: 600
    property bool numlockByDefault: true

    // Input settings - Touchpad
    property bool touchpadNaturalScroll: false
    property bool touchpadDisableWhileTyping: true
    property bool touchpadTapToClick: true

    // UI Language
    property string uiLanguage: Qt.locale().name.indexOf("de") === 0 ? "de" : "en"

    // System language & region
    property string systemLocale: Quickshell.env("LANG") || "en_US.UTF-8"

    property bool localeChangeBusy: false
    property bool localeChangeFailed: false
    property string pendingSystemLocale: ""
    property string previousUiLanguage: ""

    // Date & Time settings
    property string timeZone: "UTC"
    property bool use24HourFormat: true
    property bool ntpEnabled: true

    // Font settings
    property string fontInterface: "Cantarell 11"
    property string fontDocument: "Sans 11"
    property string fontMonospace: "Monospace 10"
    property string fontHinting: "slight"  // "none", "slight", "medium", "full"
    property string fontAntialiasing: "rgba"  // "none", "grayscale", "rgba"
    property real fontScaling: 1.0  // 0.5 to 2.0

    // Default applications
    property string defaultFileManager: "org.gnome.Nautilus.desktop"
    property string defaultTextEditor: "org.gnome.TextEditor.desktop"
    property string defaultImageViewer: "org.gnome.Loupe.desktop"
    property string defaultPdfViewer: "com.wps.Office.pdf.desktop"
    property string defaultWebBrowser: "firefox.desktop"
    property string defaultTerminal: ""

    // Model aliases for module access
    property alias iconThemesModel: _iconThemesModel
    property alias cursorThemesModel: _cursorThemesModel
    property alias keyboardLayoutsModel: _keyboardLayoutsModel
    property alias timezonesModel: _timezonesModel
    property alias systemLocalesModel: _systemLocalesModel
    property alias gtkThemesModel: _gtkThemesModel
    property alias desktopAppsModel: _desktopAppsModel
    property alias fileManagerAppsModel: _fileManagerAppsModel
    property alias textEditorAppsModel: _textEditorAppsModel
    property alias imageViewerAppsModel: _imageViewerAppsModel
    property alias pdfViewerAppsModel: _pdfViewerAppsModel
    property alias webBrowserAppsModel: _webBrowserAppsModel
    property alias terminalAppsModel: _terminalAppsModel
    property alias fontsModel: _fontsModel
    property alias monospaceFontsModel: _monospaceFontsModel

    // App override reference from shell.qml
    property var appReplace: null
    property var appReplaceLoader: null

    // Function to save app override to replace.qml
    // Merge rapid changes and serialize writes; the backend locks and commits
    // one data file, then checks the compositor's actual reload result.
    property var pendingHyprState: ({})

    function requestHyprState(group, values) {
        pendingHyprState[group] = values
        hyprStateTimer.restart()
    }

    Timer {
        id: hyprStateTimer
        interval: 120
        onTriggered: {
            if (hyprStateProc.running) {
                restart()
                return
            }
            hyprStateProc.command = ["windoesnot-settings", JSON.stringify(settingsMenu.pendingHyprState)]
            settingsMenu.pendingHyprState = ({})
            hyprStateProc.running = true
        }
    }

    Process {
        id: hyprStateProc
        stderr: StdioCollector {
            onStreamFinished: {
                if (text.trim().length > 0) console.error("Hyprland settings:", text)
            }
        }
        onExited: function(code) {
            if (code !== 0) console.error("Hyprland settings could not be applied:", code)
        }
    }

    function saveAppOverride(appName, iconPath, cmdPath, isCustomIcon) {
        console.log("=== Saving app override:", appName, iconPath, cmdPath, isCustomIcon)

        var workDir = Qt.resolvedUrl(".").toString().replace("file://", "")
        var customIconStr = isCustomIcon ? "true" : "false"

        var saveProc = Qt.createQmlObject(
            'import Quickshell.Io; Process { ' +
            'command: ["python3", "update_replace.py", "save", "' +
                     appName.replace(/"/g, '\\"') + '", "' +
                     iconPath.replace(/"/g, '\\"') + '", "' +
                     cmdPath.replace(/"/g, '\\"') + '", "' + customIconStr + '"]; ' +
            'running: true; ' +
            'workingDirectory: "' + workDir + '"; }',
            settingsMenu
        )

        saveProc.stdout = Qt.createQmlObject('import Quickshell.Io; StdioCollector { }', saveProc)
        saveProc.stderr = Qt.createQmlObject('import Quickshell.Io; StdioCollector { }', saveProc)

        saveProc.stdout.streamFinished.connect(function() {
            if (saveProc.stdout.text.trim().length > 0) {
                console.log("Save output:", saveProc.stdout.text)
            }
        })

        saveProc.stderr.streamFinished.connect(function() {
            if (saveProc.stderr.text.trim().length > 0) {
                console.error("Save error:", saveProc.stderr.text)
            }
        })

        saveProc.exited.connect(function() {
            console.log("=== Override saved, reloading replace.qml...")
            Qt.callLater(function() {
                if (appReplaceLoader) {
                    appReplaceLoader.source = ""
                    Qt.callLater(function() {
                        appReplaceLoader.source = "replace.qml"
                        console.log("=== replace.qml reloaded")
                        // Trigger reload of overrides list in GUI
                        overridesListChanged()
                    })
                }
            })
        })
    }

    signal overridesListChanged()

    // Function to delete app override from replace.qml
    function deleteAppOverride(appName) {
        console.log("=== Deleting app override:", appName)

        var workDir = Qt.resolvedUrl(".").toString().replace("file://", "")

        var deleteProc = Qt.createQmlObject(
            'import Quickshell.Io; Process { ' +
            'command: ["python3", "update_replace.py", "delete", "' + appName.replace(/"/g, '\\"') + '"]; ' +
            'running: true; ' +
            'workingDirectory: "' + workDir + '"; }',
            settingsMenu
        )

        deleteProc.stdout = Qt.createQmlObject('import Quickshell.Io; StdioCollector { }', deleteProc)
        deleteProc.stderr = Qt.createQmlObject('import Quickshell.Io; StdioCollector { }', deleteProc)

        deleteProc.stdout.streamFinished.connect(function() {
            if (deleteProc.stdout.text.trim().length > 0) {
                console.log("Delete output:", deleteProc.stdout.text)
            }
        })

        deleteProc.stderr.streamFinished.connect(function() {
            if (deleteProc.stderr.text.trim().length > 0) {
                console.error("Delete error:", deleteProc.stderr.text)
            }
        })

        deleteProc.exited.connect(function() {
            console.log("=== Override deleted, reloading replace.qml...")
            Qt.callLater(function() {
                if (appReplaceLoader) {
                    appReplaceLoader.source = ""
                    Qt.callLater(function() {
                        appReplaceLoader.source = "replace.qml"
                        console.log("=== replace.qml reloaded")
                        // Trigger reload of overrides list in GUI
                        overridesListChanged()
                    })
                }
            })
        })
    }

    // Dynamic icon themes model
    ListModel {
        id: _iconThemesModel
    }

    // Load available icon themes from system
    Process {
        id: iconThemesLoader
        command: ["bash", "-c", "find /usr/share/icons ~/.local/share/icons ~/.icons -maxdepth 1 -type d 2>/dev/null | while read dir; do [ -f \"$dir/index.theme\" ] && basename \"$dir\"; done | sort -u"]
        running: false

        stdout: StdioCollector {
            onStreamFinished: {
                try {
                    var themes = this.text.trim().split("\n").filter(function(t) { return t.length > 0; })
                    _iconThemesModel.clear()
                    for (var i = 0; i < themes.length; i++) {
                        _iconThemesModel.append({name: themes[i]})
                    }
                    console.log("Loaded", _iconThemesModel.count, "icon themes")
                } catch (e) {
                    console.error("Error loading icon themes:", e)
                }
            }
        }

        stderr: StdioCollector {
            onStreamFinished: {
                if (this.text.trim().length > 0) {
                    console.error("Icon themes loader error:", this.text.trim())
                }
            }
        }
    }

    // Dynamic cursor themes model
    ListModel {
        id: _cursorThemesModel
    }

    // Load available cursor themes from system
    Process {
        id: cursorThemesLoader
        command: ["bash", "-c", "find /usr/share/icons ~/.local/share/icons ~/.icons -maxdepth 2 -type d -name 'cursors' 2>/dev/null | while read dir; do dirname \"$dir\"; done | while read dir; do basename \"$dir\"; done | sort -u"]
        running: false

        stdout: StdioCollector {
            onStreamFinished: {
                var themes = this.text.trim().split("\n").filter(function(t) { return t.length > 0; })
                _cursorThemesModel.clear()
                for (var i = 0; i < themes.length; i++) {
                    _cursorThemesModel.append({name: themes[i]})
                }
                console.log("Loaded", _cursorThemesModel.count, "cursor themes")
            }
        }
    }

    // Dynamic keyboard layouts model
    ListModel {
        id: _keyboardLayoutsModel
    }

    // Load available keyboard layouts from system
    Process {
        id: keyboardLayoutsLoader
        command: ["bash", "-c", "awk '/^! layout/,/^! variant/' /usr/share/X11/xkb/rules/base.lst 2>/dev/null | grep -E '^\\s+\\w+\\s+' | awk '{code=$1; $1=\"\"; gsub(/^\\s+/, \"\"); print code\"|\"$0}' | sort -t'|' -k2"]
        running: false

        stdout: StdioCollector {
            onStreamFinished: {
                var lines = this.text.trim().split("\n").filter(function(l) { return l.length > 0 && l.indexOf("|") > 0; })
                _keyboardLayoutsModel.clear()
                for (var i = 0; i < lines.length; i++) {
                    var parts = lines[i].split("|")
                    if (parts.length === 2) {
                        _keyboardLayoutsModel.append({value: parts[0].trim(), text: parts[1].trim()})
                    }
                }
                console.log("Loaded", _keyboardLayoutsModel.count, "keyboard layouts")
            }
        }
    }

    // Dynamic timezones model
    ListModel {
        id: _timezonesModel
    }

    // Load available timezones from system
    Process {
        id: timezonesLoader
        command: ["bash", "-c", "timedatectl list-timezones 2>/dev/null | sort"]
        running: false

        stdout: StdioCollector {
            onStreamFinished: {
                var zones = this.text.trim().split("\n").filter(function(z) { return z.length > 0; })
                _timezonesModel.clear()
                for (var i = 0; i < zones.length; i++) {
                    var zone = zones[i].trim()
                    _timezonesModel.append({value: zone, text: zone})
                }
                console.log("Loaded", _timezonesModel.count, "timezones")
            }
        }
    }

    // Dynamic system locales model
    ListModel {
        id: _systemLocalesModel
    }

    // Load available locales from system
    Process {
        id: systemLocalesLoader
        command: ["bash", "-c", "locale -a | grep -E '\\.utf8$|\\.UTF-8$' | sed 's/\\.utf8$/.UTF-8/' | sort"]
        running: false

        stdout: StdioCollector {
            onStreamFinished: {
                var locales = this.text.trim().split("\n").filter(function(l) { return l.length > 0; })
                _systemLocalesModel.clear()
                for (var i = 0; i < locales.length; i++) {
                    var locale = locales[i].trim()
                    var info = Qt.locale(locale)
                    var label = info.nativeLanguageName || locale
                    if (info.nativeTerritoryName) label += " (" + info.nativeTerritoryName + ")"
                    _systemLocalesModel.append({value: locale, text: label})
                }
                console.log("Loaded", _systemLocalesModel.count, "system locales")
            }
        }
    }

    // Dynamic GTK themes model
    ListModel {
        id: _gtkThemesModel
    }

    // Load available GTK themes from system
    Process {
        id: gtkThemesLoader
        command: ["bash", "-c", "find /usr/share/themes ~/.local/share/themes ~/.themes -maxdepth 2 -type d \\( -name 'gtk-3.0' -o -name 'gtk-4.0' \\) 2>/dev/null | while read dir; do dirname \"$dir\"; done | while read dir; do basename \"$dir\"; done | sort -u"]
        running: false

        stdout: StdioCollector {
            onStreamFinished: {
                var themes = this.text.trim().split("\n").filter(function(t) { return t.length > 0; })
                _gtkThemesModel.clear()
                for (var i = 0; i < themes.length; i++) {
                    _gtkThemesModel.append({name: themes[i]})
                }
                console.log("Loaded", _gtkThemesModel.count, "GTK themes")
            }
        }
    }

    // Load current GTK theme from gsettings
    Process {
        id: currentGtkThemeLoader
        command: ["bash", "-c", "gsettings get org.gnome.desktop.interface gtk-theme | tr -d \"'\""]
        running: false

        stdout: StdioCollector {
            onStreamFinished: {
                var currentTheme = this.text.trim()
                if (currentTheme.length > 0) {
                    settingsMenu.gtkTheme = currentTheme
                    console.log("Loaded current GTK theme from gsettings:", currentTheme)
                }
            }
        }
    }

    // General app model (all non-game apps, for override section)
    ListModel { id: _desktopAppsModel }
    Process {
        id: desktopAppsLoader
        command: ["bash", "-c",
            "find /usr/share/applications ~/.local/share/applications /var/lib/flatpak/exports/share/applications -maxdepth 1 -name '*.desktop' 2>/dev/null | while read f; do" +
            "  grep -q '^NoDisplay=true' \"$f\" 2>/dev/null && continue;" +
            "  categories=$(grep '^Categories=' \"$f\" 2>/dev/null | head -1 | cut -d= -f2-);" +
            "  echo \"$categories\" | grep -qi 'game' && continue;" +
            "  name=$(grep '^Name=' \"$f\" 2>/dev/null | head -1 | cut -d= -f2-);" +
            "  [ -z \"$name\" ] && continue;" +
            "  grep -q '^Exec=' \"$f\" 2>/dev/null || continue;" +
            "  echo \"$name\";" +
            "done | sort -u"
        ]
        running: false
        stdout: StdioCollector {
            onStreamFinished: {
                var apps = this.text.trim().split("\n").filter(function(a) { return a.length > 0 })
                _desktopAppsModel.clear()
                for (var i = 0; i < apps.length; i++)
                    _desktopAppsModel.append({ name: apps[i] })
            }
        }
    }

    // Per-category app models
    ListModel { id: _fileManagerAppsModel }
    ListModel { id: _textEditorAppsModel }
    ListModel { id: _imageViewerAppsModel }
    ListModel { id: _pdfViewerAppsModel }
    ListModel { id: _webBrowserAppsModel }
    ListModel { id: _terminalAppsModel }
    ListModel { id: _fontsModel }
    ListModel { id: _monospaceFontsModel }

    // Helper: parse "Name|file.desktop" lines into a ListModel
    function parseAppsIntoModel(text, model) {
        var lines = text.trim().split("\n").filter(function(a) { return a.length > 0 })
        model.clear()
        for (var i = 0; i < lines.length; i++) {
            var sep = lines[i].indexOf("|")
            if (sep > 0)
                model.append({ name: lines[i].substring(0, sep), desktopFile: lines[i].substring(sep + 1) })
        }
    }

    // Build a per-MIME gio-based app lookup command
    // requireCat: grep -E pattern that must match Categories= (empty = no requirement)
    // excludeCat: grep -E pattern that must NOT match Categories= (empty = no exclusion)
    function mimeAppsCmd(mimeType, requireCat, excludeCat) {
        var catFilter = ""
        if (requireCat || excludeCat) {
            catFilter = " cats=$(grep '^Categories=' \"$f\" 2>/dev/null | head -1);"
            if (excludeCat)
                catFilter += " echo \"$cats\" | grep -qE '" + excludeCat + "' && break;"
            if (requireCat)
                catFilter += " echo \"$cats\" | grep -qE '" + requireCat + "' || break;"
        }
        return "gio mime " + mimeType + " 2>/dev/null | sed -n \"s/^\\t//p\" | while read d; do" +
               " for dir in /usr/share/applications \"$HOME/.local/share/applications\" /var/lib/flatpak/exports/share/applications; do" +
               "  f=\"$dir/$d\"; if [ -f \"$f\" ]; then" +
               catFilter +
               "   name=$(grep \"^Name=\" \"$f\" 2>/dev/null | head -1 | cut -d= -f2-);" +
               "   [ -n \"$name\" ] && echo \"$name|$d\" && break;" +
               "  fi; done; done | sort -u"
    }

    Process {
        id: fileManagerAppsLoader
        command: ["bash", "-c", settingsMenu.mimeAppsCmd("inode/directory")]
        running: false
        stdout: StdioCollector { onStreamFinished: settingsMenu.parseAppsIntoModel(this.text, _fileManagerAppsModel) }
    }
    Process {
        id: textEditorAppsLoader
        command: ["bash", "-c", settingsMenu.mimeAppsCmd("text/plain")]
        running: false
        stdout: StdioCollector { onStreamFinished: settingsMenu.parseAppsIntoModel(this.text, _textEditorAppsModel) }
    }
    Process {
        id: imageViewerAppsLoader
        // Require Viewer category, exclude browsers and PDF-only apps
        command: ["bash", "-c", settingsMenu.mimeAppsCmd("image/png", "Viewer", "WebBrowser|Office")]
        running: false
        stdout: StdioCollector { onStreamFinished: settingsMenu.parseAppsIntoModel(this.text, _imageViewerAppsModel) }
    }
    Process {
        id: pdfViewerAppsLoader
        // Require Office category (PDF viewers), exclude browsers
        command: ["bash", "-c", settingsMenu.mimeAppsCmd("application/pdf", "Office", "WebBrowser")]
        running: false
        stdout: StdioCollector { onStreamFinished: settingsMenu.parseAppsIntoModel(this.text, _pdfViewerAppsModel) }
    }
    Process {
        id: webBrowserAppsLoader
        // Only apps that register for http scheme handler
        command: ["bash", "-c", settingsMenu.mimeAppsCmd("x-scheme-handler/http", "WebBrowser", "")]
        running: false
        stdout: StdioCollector { onStreamFinished: settingsMenu.parseAppsIntoModel(this.text, _webBrowserAppsModel) }
    }
    Process {
        id: terminalAppsLoader
        command: ["bash", "-c",
            "grep -rl 'TerminalEmulator' /usr/share/applications/ \"$HOME/.local/share/applications\" 2>/dev/null | while read f; do " +
            "  grep -q '^NoDisplay=true' \"$f\" && continue; " +
            "  basename \"$f\" | grep -qiE 'server|client|preferences' && continue; " +
            "  n=$(grep '^Name=' \"$f\" | head -1 | cut -d= -f2-); " +
            "  e=$(grep '^Exec=' \"$f\" | head -1 | cut -d= -f2- | awk '{print $1}'); " +
            "  [ -n \"$n\" ] && [ -n \"$e\" ] && printf '%s (%s)|%s\\n' \"$n\" \"$e\" \"$e\"; " +
            "done | sort -u | awk -F'|' '!seen[$2]++'"]
        running: false
        stdout: StdioCollector { onStreamFinished: settingsMenu.parseAppsIntoModel(this.text, _terminalAppsModel) }
    }

    Process {
        id: fontsLoader
        command: ["bash", "-c", "fc-list --format='%{family[0]}\\n' | sort -u"]
        running: false
        stdout: StdioCollector {
            onStreamFinished: {
                var lines = this.text.trim().split("\n")
                _fontsModel.clear()
                for (var i = 0; i < lines.length; i++) {
                    var f = lines[i].trim()
                    if (f) _fontsModel.append({ name: f })
                }
            }
        }
    }
    Process {
        id: monospaceFontsLoader
        command: ["bash", "-c", "fc-list :spacing=mono --format='%{family[0]}\\n' | sort -u"]
        running: false
        stdout: StdioCollector {
            onStreamFinished: {
                var lines = this.text.trim().split("\n")
                _monospaceFontsModel.clear()
                for (var i = 0; i < lines.length; i++) {
                    var f = lines[i].trim()
                    if (f) _monospaceFontsModel.append({ name: f })
                }
            }
        }
    }

    // Load current default applications from xdg-mime
    Process {
        id: defaultAppsLoader
        command: ["bash", "-c",
            "echo \"filemanager=$(xdg-mime query default inode/directory)\" && " +
            "echo \"texteditor=$(xdg-mime query default text/plain)\" && " +
            "echo \"imageviewer=$(xdg-mime query default image/png)\" && " +
            "echo \"pdfviewer=$(xdg-mime query default application/pdf)\" && " +
            "echo \"webbrowser=$(xdg-mime query default x-scheme-handler/http)\""
        ]
        running: false

        stdout: StdioCollector {
            onStreamFinished: {
                // Guard: prevent onChange handlers from writing back to xdg-mime while loading
                var wasLoading = settingsMenu.isLoadingSettings
                settingsMenu.isLoadingSettings = true
                var lines = this.text.trim().split("\n")
                for (var i = 0; i < lines.length; i++) {
                    var eqPos = lines[i].indexOf("=")
                    if (eqPos > 0) {
                        var key = lines[i].substring(0, eqPos)
                        var value = lines[i].substring(eqPos + 1).trim()
                        if (value.length === 0) continue
                        if (key === "filemanager") settingsMenu.defaultFileManager = value
                        else if (key === "texteditor") settingsMenu.defaultTextEditor = value
                        else if (key === "imageviewer") settingsMenu.defaultImageViewer = value
                        else if (key === "pdfviewer") settingsMenu.defaultPdfViewer = value
                        else if (key === "webbrowser") settingsMenu.defaultWebBrowser = value
                    }
                }
                settingsMenu.isLoadingSettings = wasLoading
                console.log("Loaded default applications from xdg-mime")
            }
        }
    }

    Component.onCompleted: {
        Lang.setCurrent(uiLanguage)
        loadSettings()
        // Load themes with a small delay to ensure proper initialization
        Qt.callLater(function() {
            console.log("Starting theme loaders...")
            iconThemesLoader.running = true
            cursorThemesLoader.running = true
            keyboardLayoutsLoader.running = true
            timezonesLoader.running = true
            systemLocalesLoader.running = true
            gtkThemesLoader.running = true
            desktopAppsLoader.running = true
            fileManagerAppsLoader.running = true
            textEditorAppsLoader.running = true
            imageViewerAppsLoader.running = true
            pdfViewerAppsLoader.running = true
            webBrowserAppsLoader.running = true
            terminalAppsLoader.running = true
            defaultAppsLoader.running = true
            fontsLoader.running = true
            monospaceFontsLoader.running = true
        })
    }

    onInactiveBorderColorChanged: {
        if (!isLoadingSettings) {
            saveSettings()
            updateHyprlandBorders()
        }
    }

    onBorderRadiusChanged: {
        if (!isLoadingSettings) {
            saveSettings()
            updateHyprlandAppearance()
        }
    }

    onWindowGapsChanged: {
        if (!isLoadingSettings) {
            saveSettings()
            updateHyprlandAppearance()
        }
    }

    function updateHyprlandBorders() {
        requestHyprState("borders", {active: accentColor, inactive: inactiveBorderColor})
    }

    function updateHyprlandAppearance() {
        requestHyprState("appearance", {radius: borderRadius, gaps: windowGaps})
    }

    Process {
        id: updateHyprlandProc
        command: ["bash", "-c", ""]
        running: false
        onRunningChanged: {
            if (!running) {
                console.log("Hyprland borders updated")
            }
        }
    }

    Process {
        id: updateHyprlandAppearanceProc
        command: ["bash", "-c", ""]
        running: false
        onRunningChanged: {
            if (!running) {
                console.log("Hyprland appearance updated")
            }
        }
    }

    Process {
        id: localeProc
        running: false
        onExited: (code) => settingsMenu.finishLanguageChange(code)
    }

    Process {
        id: timezoneProc
        command: ["bash", "-c", ""]
        running: false
        onRunningChanged: {
            if (!running) {
                console.log("Timezone updated")
            }
        }
    }

    Process {
        id: ntpProc
        command: ["bash", "-c", ""]
        running: false
        onRunningChanged: {
            if (!running) {
                console.log("NTP settings updated")
            }
        }
    }

    function updateWindowPositions() {
        var sidebarHidden = startMenuSidebarPosition === "hidden"
        var startmenuW = sidebarHidden ? 605 : 820
        var startmenuH = Math.min(720, Math.max(300, (settingsMenu.screen ? settingsMenu.screen.height : 800) - 60))
        var startmenuX = taskbarAlignmentSetting === "left" ? 10
                       : Math.max(0, Math.round(((settingsMenu.screen ? settingsMenu.screen.width : 1280) - startmenuW) / 2))
        var settingsX = taskbarAlignmentSetting === "left" ? 10 : Math.max(0, Math.round(((settingsMenu.screen ? settingsMenu.screen.width : 1280) - 900) / 2))
        var startmenuY = Math.max(0, (settingsMenu.screen ? settingsMenu.screen.height : 800) - 45 - startmenuH)
        var settingsY = Math.max(0, (settingsMenu.screen ? settingsMenu.screen.height : 800) - 45 - 700)

        // Update the existing named rule so the size also applies on future maps.
        var startmenuSizeRuleProc = Qt.createQmlObject(
            'import Quickshell.Io; Process { ' +
            'command: ["windoesnot-hyprctl", "keyword", "windowrule[startmenu-config]:size", "' + startmenuW + ' ' + startmenuH + '"]; ' +
            'running: true; }',
            settingsMenu
        )
        // Also directly resize the existing window in case it's already mapped
        var startmenuResizeProc = Qt.createQmlObject(
            'import Quickshell.Io; Process { ' +
            'command: ["windoesnot-hyprctl", "dispatch", "resizewindowpixel", "exact ' + startmenuW + ' ' + startmenuH + ',title:quickshell-startmenu"]; ' +
            'running: true; }',
            settingsMenu
        )
        var startmenuMoveProc = Qt.createQmlObject(
            'import Quickshell.Io; Process { ' +
            'command: ["windoesnot-hyprctl", "keyword", "windowrule[startmenu-config]:move", "' + startmenuX + ' ' + startmenuY + '"]; ' +
            'running: true; }',
            settingsMenu
        )
        var settingsRuleProc = Qt.createQmlObject(
            'import Quickshell.Io; Process { ' +
            'command: ["windoesnot-hyprctl", "keyword", "windowrule[settings-config]:move", "' + settingsX + ' ' + settingsY + '"]; ' +
            'running: true; }',
            settingsMenu
        )

        console.log("Updated window positions: startmenu " + startmenuW + "x" + startmenuH + " at " + startmenuX + "," + startmenuY)
    }

    function loadSettings() {
        var configPath = Qt.resolvedUrl("settings.txt").toString().replace("file://", "")
        console.log("Loading settings from:", configPath)

        isLoadingSettings = true

        var proc = Qt.createQmlObject(
            'import Quickshell.Io; Process { ' +
            'command: ["bash", "-c", "if [ -f \'' + configPath + '\' ]; then cat \'' + configPath + '\'; fi"]; ' +
            'running: true; ' +
            'stdout: StdioCollector { ' +
            'onStreamFinished: { ' +
            'var lines = this.text.trim().split("\\n"); ' +
            'for (var i = 0; i < lines.length; i++) { ' +
            'var parts = lines[i].split("="); ' +
            'if (parts.length === 2) { ' +
            'var key = parts[0]; ' +
            'var value = parts[1]; ' +
            'if (key === "accentColor") settingsMenu.accentColor = value; ' +
            'else if (key === "inactiveBorderColor") settingsMenu.inactiveBorderColor = value; ' +
            'else if (key === "borderRadius") settingsMenu.borderRadius = parseInt(value); ' +
            'else if (key === "windowGaps") settingsMenu.windowGaps = parseInt(value); ' +
            'else if (key === "workspaceToggle") { ' +
            'settingsMenu.workspaceToggleEnabled = (value === "true"); ' +
            'workspaceContainer.visible = settingsMenu.workspaceToggleEnabled; ' +
            '} ' +
            'else if (key === "showSearchButton") settingsMenu.showSearchButton = (value === "true"); ' +
            'else if (key === "showSettingsButton") settingsMenu.showSettingsButton = (value === "true"); ' +
            'else if (key === "showStoreButton") settingsMenu.showStoreButton = (value === "true"); ' +
            'else if (key === "defaultTerminal") settingsMenu.defaultTerminal = value; ' +
            'else if (key === "taskbarAlignment") { ' +
            'settingsMenu.taskbarAlignmentSetting = value; ' +
            'panelWindow.taskbarAlignment = value; ' +
            '} ' +
            'else if (key === "startOrbStyle") settingsMenu.startOrbStyle = value; ' +
            'else if (key === "startOrbCustomSource") settingsMenu.startOrbCustomSource = value; ' +
            'else if (key === "darkMode") settingsMenu.darkMode = (value === "true"); ' +
            'else if (key === "gtkThemeDark") settingsMenu.gtkThemeDark = value; ' +
            'else if (key === "gtkThemeLight") settingsMenu.gtkThemeLight = value; ' +
            'else if (key === "cursorTheme") settingsMenu.cursorTheme = value; ' +
            'else if (key === "iconTheme") settingsMenu.iconTheme = value; ' +
            'else if (key === "windowMode") settingsMenu.windowMode = value; ' +
            'else if (key === "hyprbarsPluginEnabled") settingsMenu.hyprbarsPluginEnabled = (value === "true"); ' +
            'else if (key === "hyprbarsEnabled") settingsMenu.hyprbarsEnabled = (value === "true"); ' +
            'else if (key === "hyprbarsHeight") settingsMenu.hyprbarsHeight = parseInt(value); ' +
            'else if (key === "hyprbarsButtonAlign") settingsMenu.hyprbarsButtonAlign = value; ' +
            'else if (key === "hyprbarsCloseButtonEnabled") settingsMenu.hyprbarsCloseButtonEnabled = (value === "true"); ' +
            'else if (key === "hyprbarsMaxButtonEnabled") settingsMenu.hyprbarsMaxButtonEnabled = (value === "true"); ' +
            'else if (key === "hyprbarsMinButtonEnabled") settingsMenu.hyprbarsMinButtonEnabled = (value === "true"); ' +
            'else if (key === "hyprbarsBarColor") settingsMenu.hyprbarsBarColor = value; ' +
            'else if (key === "hyprbarsBarBlur") settingsMenu.hyprbarsBarBlur = (value === "true"); ' +
            'else if (key === "hyprbarsTextColor") settingsMenu.hyprbarsTextColor = value; ' +
            'else if (key === "hyprbarsTextSize") settingsMenu.hyprbarsTextSize = parseInt(value); ' +
            'else if (key === "hyprbarsTextFont") settingsMenu.hyprbarsTextFont = value; ' +
            'else if (key === "hyprbarsTextAlign") settingsMenu.hyprbarsTextAlign = value; ' +
            'else if (key === "hyprbarsBarTitleEnabled") settingsMenu.hyprbarsBarTitleEnabled = (value === "true"); ' +
            'else if (key === "hyprbarsCloseButtonColor") settingsMenu.hyprbarsCloseButtonColor = value; ' +
            'else if (key === "hyprbarsMaxButtonColor") settingsMenu.hyprbarsMaxButtonColor = value; ' +
            'else if (key === "hyprbarsMinButtonColor") settingsMenu.hyprbarsMinButtonColor = value; ' +
            'else if (key === "hyprbarsButtonTextColor") settingsMenu.hyprbarsButtonTextColor = value; ' +
            'else if (key === "hyprbarsButtonTextColorNeutral") settingsMenu.hyprbarsButtonTextColorNeutral = value; ' +
            'else if (key === "mouseSensitivity") settingsMenu.mouseSensitivity = parseFloat(value); ' +
            'else if (key === "mouseAccelProfile") settingsMenu.mouseAccelProfile = value; ' +
            'else if (key === "followMouse") settingsMenu.followMouse = parseInt(value); ' +
            'else if (key === "keyboardLayout") settingsMenu.keyboardLayout = value; ' +
            'else if (key === "repeatRate") settingsMenu.repeatRate = parseInt(value); ' +
            'else if (key === "repeatDelay") settingsMenu.repeatDelay = parseInt(value); ' +
            'else if (key === "numlockByDefault") settingsMenu.numlockByDefault = (value === "true"); ' +
            'else if (key === "touchpadNaturalScroll") settingsMenu.touchpadNaturalScroll = (value === "true"); ' +
            'else if (key === "touchpadDisableWhileTyping") settingsMenu.touchpadDisableWhileTyping = (value === "true"); ' +
            'else if (key === "touchpadTapToClick") settingsMenu.touchpadTapToClick = (value === "true"); ' +
            'else if (key === "uiLanguage") settingsMenu.uiLanguage = value; ' +
            'else if (key === "systemLocale") settingsMenu.systemLocale = value; ' +
            'else if (key === "timeZone") settingsMenu.timeZone = value; ' +
            'else if (key === "use24HourFormat") settingsMenu.use24HourFormat = (value === "true"); ' +
            'else if (key === "ntpEnabled") settingsMenu.ntpEnabled = (value === "true"); ' +
            'else if (key === "fontInterface") settingsMenu.fontInterface = value; ' +
            'else if (key === "fontDocument") settingsMenu.fontDocument = value; ' +
            'else if (key === "fontMonospace") settingsMenu.fontMonospace = value; ' +
            'else if (key === "fontHinting") settingsMenu.fontHinting = value; ' +
            'else if (key === "fontAntialiasing") settingsMenu.fontAntialiasing = value; ' +
            'else if (key === "fontScaling") settingsMenu.fontScaling = parseFloat(value); ' +
            'else if (key === "desktopIconSize") settingsMenu.desktopIconSize = parseInt(value); ' +
            'else if (key === "desktopGridSize") settingsMenu.desktopGridSize = parseInt(value); ' +
            'else if (key === "desktopShowTrash") settingsMenu.desktopShowTrash = (value === "true"); ' +
            'else if (key === "desktopLabelLines") settingsMenu.desktopLabelLines = parseInt(value); ' +
            'else if (key === "primaryMonitor") settingsMenu.primaryMonitor = value; ' +
            'else if (key === "showOllamaTray") settingsMenu.showOllamaTray = (value === "true"); ' +
            'else if (key === "showDockerTray") settingsMenu.showDockerTray = (value === "true"); ' +
            'else if (key === "showNearbyTray") settingsMenu.showNearbyTray = (value === "true"); ' +
            'else if (key === "weatherEnabled") settingsMenu.weatherEnabled = (value === "true"); ' +
            'else if (key === "weatherLocation") settingsMenu.weatherLocation = value; ' +
            'else if (key === "weatherTaskbarIndex") settingsMenu.weatherTaskbarIndex = parseInt(value); ' +
            'else if (key === "weatherStartAreaSlot") settingsMenu.weatherStartAreaSlot = parseInt(value); ' +
            'else if (key === "trayOrder") settingsMenu.trayOrder = value; ' +
            'else if (key === "weatherCity") settingsMenu.weatherCity = value; ' +
            'else if (key === "weatherLatitude") settingsMenu.weatherLatitude = parseFloat(value); ' +
            'else if (key === "weatherLongitude") settingsMenu.weatherLongitude = parseFloat(value); ' +
            'else if (key === "startMenuSidebarPosition") settingsMenu.startMenuSidebarPosition = value; ' +
            'else if (key === "startMenuShowAllApps") settingsMenu.startMenuShowAllApps = (value === "true"); ' +
            'else if (key === "startMenuShowPersonalized") settingsMenu.startMenuShowPersonalized = (value === "true"); ' +
            'else if (key === "startMenuShowDesktop") settingsMenu.startMenuShowDesktop = (value === "true"); ' +
            'else if (key === "startMenuShowDocuments") settingsMenu.startMenuShowDocuments = (value === "true"); ' +
            'else if (key === "startMenuShowDownloads") settingsMenu.startMenuShowDownloads = (value === "true"); ' +
            'else if (key === "startMenuShowPictures") settingsMenu.startMenuShowPictures = (value === "true"); ' +
            'else if (key === "startMenuShowMusic") settingsMenu.startMenuShowMusic = (value === "true"); ' +
            'else if (key === "startMenuShowVideos") settingsMenu.startMenuShowVideos = (value === "true"); ' +
            '} } ' +
            'settingsMenu.finishLoadingSettings(); ' +
            'settingsMenu.updateWindowPositions(); ' +
            'settingsMenu.updateHyprlandAppearance(); ' +
            'settingsMenu.updateHyprlandBorders(); ' +
            'settingsMenu.updateGtkSettingsIni(); ' +
            'settingsMenu.updateGtkColorScheme(); ' +
            'settingsMenu.updateIconTheme(); ' +
            'console.log("Settings loaded and applied to Hyprland"); ' +
            'currentGtkThemeLoader.running = true; ' +
            '} } }',
            settingsMenu
        )
    }

    IpcHandler {
        target: "windoesnot-settings"
        function setLanguage(language: string): string {
            if (language !== "de" && language !== "en") return "unsupported"
            settingsMenu.uiLanguage = language
            return settingsMenu.uiLanguage
        }
        function setKeyboardLayout(layout: string): string {
            // Plain XKB layout names only, e.g. "de" or "ru,us" from the installer.
            if (!/^[a-z]{2,8}(,[a-z]{2,8})?$/.test(layout)) return "unsupported"
            settingsMenu.keyboardLayout = layout
            return settingsMenu.keyboardLayout
        }
        function setDarkMode(enabled: bool): string {
            settingsMenu.darkMode = enabled
            return enabled ? "dark" : "light"
        }
        function state(): string {
            return JSON.stringify({language: settingsMenu.uiLanguage, dark: settingsMenu.darkMode,
                loading: settingsMenu.isLoadingSettings, docker: settingsMenu.showDockerTray,
                ollama: settingsMenu.showOllamaTray, nearby: settingsMenu.showNearbyTray})
        }
    }

    function finishLoadingSettings() {
        Lang.setCurrent(uiLanguage)
        isLoadingSettings = false
        if (panelWindow) panelWindow.rebuildTrayModel()
    }

    function saveSettings() {
        if (isLoadingSettings) {
            console.log("Skipping save during settings load")
            return
        }

        var configPath = Qt.resolvedUrl("settings.txt").toString().replace("file://", "")
        var content = "accentColor=" + accentColor + "\\n" +
                      "inactiveBorderColor=" + inactiveBorderColor + "\\n" +
                      "borderRadius=" + borderRadius + "\\n" +
                      "windowGaps=" + windowGaps + "\\n" +
                      "workspaceToggle=" + (workspaceToggleEnabled ? "true" : "false") + "\\n" +
                      "showSearchButton=" + (showSearchButton ? "true" : "false") + "\\n" +
                      "showSettingsButton=" + (showSettingsButton ? "true" : "false") + "\\n" +
                      "showStoreButton=" + (showStoreButton ? "true" : "false") + "\\n" +
                      "defaultTerminal=" + defaultTerminal + "\\n" +
                      "taskbarAlignment=" + taskbarAlignmentSetting + "\\n" +
                      "startOrbStyle=" + startOrbStyle + "\\n" +
                      "startOrbCustomSource=" + startOrbCustomSource + "\\n" +
                      "darkMode=" + (darkMode ? "true" : "false") + "\\n" +
                      "gtkThemeDark=" + gtkThemeDark + "\\n" +
                      "gtkThemeLight=" + gtkThemeLight + "\\n" +
                      "cursorTheme=" + cursorTheme + "\\n" +
                      "iconTheme=" + iconTheme + "\\n" +
                      "windowMode=" + windowMode + "\\n" +
                      "hyprbarsPluginEnabled=" + (hyprbarsPluginEnabled ? "true" : "false") + "\\n" +
                      "hyprbarsEnabled=" + (hyprbarsEnabled ? "true" : "false") + "\\n" +
                      "hyprbarsHeight=" + hyprbarsHeight + "\\n" +
                      "hyprbarsButtonAlign=" + hyprbarsButtonAlign + "\\n" +
                      "hyprbarsCloseButtonEnabled=" + (hyprbarsCloseButtonEnabled ? "true" : "false") + "\\n" +
                      "hyprbarsMaxButtonEnabled=" + (hyprbarsMaxButtonEnabled ? "true" : "false") + "\\n" +
                      "hyprbarsMinButtonEnabled=" + (hyprbarsMinButtonEnabled ? "true" : "false") + "\\n" +
                      "hyprbarsBarColor=" + hyprbarsBarColor + "\\n" +
                      "hyprbarsBarBlur=" + (hyprbarsBarBlur ? "true" : "false") + "\\n" +
                      "hyprbarsTextColor=" + hyprbarsTextColor + "\\n" +
                      "hyprbarsTextSize=" + hyprbarsTextSize + "\\n" +
                      "hyprbarsTextFont=" + hyprbarsTextFont + "\\n" +
                      "hyprbarsTextAlign=" + hyprbarsTextAlign + "\\n" +
                      "hyprbarsBarTitleEnabled=" + (hyprbarsBarTitleEnabled ? "true" : "false") + "\\n" +
                      "hyprbarsCloseButtonColor=" + hyprbarsCloseButtonColor + "\\n" +
                      "hyprbarsMaxButtonColor=" + hyprbarsMaxButtonColor + "\\n" +
                      "hyprbarsMinButtonColor=" + hyprbarsMinButtonColor + "\\n" +
                      "hyprbarsButtonTextColor=" + hyprbarsButtonTextColor + "\\n" +
                      "hyprbarsButtonTextColorNeutral=" + hyprbarsButtonTextColorNeutral + "\\n" +
                      "mouseSensitivity=" + mouseSensitivity + "\\n" +
                      "mouseAccelProfile=" + mouseAccelProfile + "\\n" +
                      "followMouse=" + followMouse + "\\n" +
                      "keyboardLayout=" + keyboardLayout + "\\n" +
                      "repeatRate=" + repeatRate + "\\n" +
                      "repeatDelay=" + repeatDelay + "\\n" +
                      "numlockByDefault=" + (numlockByDefault ? "true" : "false") + "\\n" +
                      "touchpadNaturalScroll=" + (touchpadNaturalScroll ? "true" : "false") + "\\n" +
                      "touchpadDisableWhileTyping=" + (touchpadDisableWhileTyping ? "true" : "false") + "\\n" +
                      "touchpadTapToClick=" + (touchpadTapToClick ? "true" : "false") + "\\n" +
                      "uiLanguage=" + uiLanguage + "\\n" +
                      "systemLocale=" + systemLocale + "\\n" +
                      "timeZone=" + timeZone + "\\n" +
                      "use24HourFormat=" + (use24HourFormat ? "true" : "false") + "\\n" +
                      "ntpEnabled=" + (ntpEnabled ? "true" : "false") + "\\n" +
                      "fontInterface=" + fontInterface + "\\n" +
                      "fontDocument=" + fontDocument + "\\n" +
                      "fontMonospace=" + fontMonospace + "\\n" +
                      "fontHinting=" + fontHinting + "\\n" +
                      "fontAntialiasing=" + fontAntialiasing + "\\n" +
                      "fontScaling=" + fontScaling + "\\n" +
                      "desktopIconSize=" + desktopIconSize + "\\n" +
                      "desktopGridSize=" + desktopGridSize + "\\n" +
                      "desktopShowTrash=" + (desktopShowTrash ? "true" : "false") + "\\n" +
                      "desktopLabelLines=" + desktopLabelLines + "\\n" +
                      "primaryMonitor=" + primaryMonitor + "\\n" +
                      "startMenuSidebarPosition=" + startMenuSidebarPosition + "\\n" +
                      "startMenuShowAllApps=" + (startMenuShowAllApps ? "true" : "false") + "\\n" +
                      "startMenuShowPersonalized=" + (startMenuShowPersonalized ? "true" : "false") + "\\n" +
                      "startMenuShowDesktop=" + (startMenuShowDesktop ? "true" : "false") + "\\n" +
                      "startMenuShowDocuments=" + (startMenuShowDocuments ? "true" : "false") + "\\n" +
                      "startMenuShowDownloads=" + (startMenuShowDownloads ? "true" : "false") + "\\n" +
                      "startMenuShowPictures=" + (startMenuShowPictures ? "true" : "false") + "\\n" +
                      "startMenuShowMusic=" + (startMenuShowMusic ? "true" : "false") + "\\n" +
                      "startMenuShowVideos=" + (startMenuShowVideos ? "true" : "false") + "\\n" +
                      "showOllamaTray=" + (showOllamaTray ? "true" : "false") + "\\n" +
                      "showDockerTray=" + (showDockerTray ? "true" : "false") + "\\n" +
                      "showNearbyTray=" + (showNearbyTray ? "true" : "false") + "\\n" +
                      "weatherEnabled=" + (weatherEnabled ? "true" : "false") + "\\n" +
                      "weatherLocation=" + weatherLocation + "\\n" +
                      "weatherTaskbarIndex=" + weatherTaskbarIndex + "\\n" +
                      "weatherStartAreaSlot=" + weatherStartAreaSlot + "\\n" +
                      "trayOrder=" + trayOrder + "\\n" +
                      "weatherCity=" + weatherCity + "\\n" +
                      "weatherLatitude=" + weatherLatitude + "\\n" +
                      "weatherLongitude=" + weatherLongitude

        console.log("Saving settings to:", configPath)

        var proc = Qt.createQmlObject(
            'import Quickshell.Io; Process { ' +
            'command: ["bash", "-c", "printf \'%b\' \'' + content.replace(/'/g, "'\\''") + '\\n\' > \'' + configPath + '\'"]; ' +
            'running: true; ' +
            'stdout: StdioCollector { onStreamFinished: console.log("Settings saved") } }',
            settingsMenu
        )
    }

    onAccentColorChanged: {
        saveSettings()
        if (!isLoadingSettings) {
            updateHyprlandBorders()
        }
    }
    onStartOrbStyleChanged: saveSettings()
    onStartOrbCustomSourceChanged: saveSettings()
    onWorkspaceToggleEnabledChanged: saveSettings()
    onShowSearchButtonChanged: saveSettings()
    onShowSettingsButtonChanged: saveSettings()
    onShowStoreButtonChanged: saveSettings()
    onWeatherEnabledChanged: saveSettings()
    onWeatherLocationChanged: saveSettings()
    onWeatherStartAreaSlotChanged: saveSettings()
    onWeatherCityChanged: saveSettings()
    onWeatherLatitudeChanged: saveSettings()
    onWeatherLongitudeChanged: saveSettings()
    onStartMenuSidebarPositionChanged: { saveSettings(); updateWindowPositions() }
    onStartMenuShowAllAppsChanged: saveSettings()
    onStartMenuShowPersonalizedChanged: saveSettings()
    onStartMenuShowDesktopChanged: saveSettings()
    onStartMenuShowDocumentsChanged: saveSettings()
    onStartMenuShowDownloadsChanged: saveSettings()
    onStartMenuShowPicturesChanged: saveSettings()
    onStartMenuShowMusicChanged: saveSettings()
    onStartMenuShowVideosChanged: saveSettings()
    onDefaultTerminalChanged: {
        if (!isLoadingSettings) {
            saveSettings()
            if (defaultTerminal !== "") {
                Qt.createQmlObject(
                    'import Quickshell.Io; Process { command: ["bash", "-c", ' +
                    '"printf \'%s\\n\' ' + JSON.stringify(defaultTerminal) + ' > ~/.config/xdg-terminals.list"]; running: true }',
                    settingsMenu)
            }
        }
    }
    onDesktopIconSizeChanged: saveSettings()
    onDesktopGridSizeChanged: saveSettings()
    onDesktopShowTrashChanged: saveSettings()
    onDesktopLabelLinesChanged: saveSettings()
    onTaskbarAlignmentSettingChanged: {
        console.log("=== taskbarAlignmentSetting changed to:", taskbarAlignmentSetting)
        console.log("=== isLoadingSettings:", isLoadingSettings)
        saveSettings()

        // Update window positions when alignment changes
        if (!isLoadingSettings) {
            updateWindowPositions()

            // Close and reopen settings window to apply new position
            var wasVisible = settingsMenu.visible
            if (wasVisible) {
                settingsMenu.visible = false
                alignmentReopenTimer.start()
            }
        }
    }

    Timer {
        id: alignmentReopenTimer
        interval: 100
        running: false
        repeat: false
        onTriggered: {
            settingsMenu.visible = true
        }
    }

    // Appearance settings onChange handlers
    onDarkModeChanged: {
        if (!isLoadingSettings) {
            saveSettings()
            // Auto-switch GTK theme based on dark/light mode
            var targetTheme = darkMode ? gtkThemeDark : gtkThemeLight
            gtkTheme = targetTheme
            updateGtkColorScheme()
            updateGtkSettingsIni()
            updateGhosttyColors()
            updateHyprbarsColors()
            updateSwayncStyle()
            updateSnappySwitcherTheme()
        }
    }

    onGtkThemeChanged: {
        if (!isLoadingSettings) {
            updateGtkTheme()
        }
    }

    onGtkThemeDarkChanged: {
        if (!isLoadingSettings) {
            saveSettings()
            // If currently in dark mode, apply this theme immediately
            if (darkMode) {
                gtkTheme = gtkThemeDark
            }
        }
    }

    onGtkThemeLightChanged: {
        if (!isLoadingSettings) {
            saveSettings()
            // If currently in light mode, apply this theme immediately
            if (!darkMode) {
                gtkTheme = gtkThemeLight
            }
        }
    }

    onCursorThemeChanged: {
        if (!isLoadingSettings) {
            saveSettings()
            updateCursorTheme()
        }
    }

    onIconThemeChanged: {
        if (!isLoadingSettings) {
            saveSettings()
            updateIconTheme()
        }
    }

    onWindowModeChanged: {
        if (!isLoadingSettings) {
            saveSettings()
            updateWindowMode()
        }
    }

    onHyprbarsPluginEnabledChanged: {
        if (!isLoadingSettings) {
            saveSettings()
            updateHyprbarsPlugin()
        }
    }

    onHyprbarsEnabledChanged: {
        if (!isLoadingSettings) {
            saveSettings()
            updateHyprbars()
        }
        // Trigger contentHeight update
        if (settingsFlickable) {
            settingsFlickable.contentHeight = Qt.binding(function() {
                return Math.max(settingsFlickable.height, settingsFlickable.getCurrentCategoryHeight())
            })
        }
    }

    onHyprbarsCloseButtonEnabledChanged: {
        if (!isLoadingSettings) {
            saveSettings()
            updateHyprbarsButtonToggles()
        }
    }

    onHyprbarsMaxButtonEnabledChanged: {
        if (!isLoadingSettings) {
            saveSettings()
            updateHyprbarsButtonToggles()
        }
    }

    onHyprbarsMinButtonEnabledChanged: {
        if (!isLoadingSettings) {
            saveSettings()
            updateHyprbarsButtonToggles()
        }
    }

    // Update functions for appearance settings
    function updateGtkTheme() {
        var cmd = "gsettings set org.gnome.desktop.interface gtk-theme '" + gtkTheme + "'"

        console.log("Updating GTK theme:", gtkTheme)

        var proc = Qt.createQmlObject(
            'import Quickshell.Io; Process { ' +
            'command: ["bash", "-c", "' + cmd + '"]; ' +
            'running: true; }',
            settingsMenu
        )

        updateGtkSettingsIni()
    }

    function updateGtkColorScheme() {
        var colorScheme = darkMode ? "prefer-dark" : "prefer-light"

        var cmd = "gsettings set org.gnome.desktop.interface color-scheme '" + colorScheme + "'"

        console.log("Updating GTK color-scheme:", colorScheme)

        var proc = Qt.createQmlObject(
            'import Quickshell.Io; Process { ' +
            'command: ["bash", "-c", "' + cmd + '"]; ' +
            'running: true; }',
            settingsMenu
        )
    }

    function updateGtkSettingsIni() {
        var preferDark = darkMode ? "1" : "0"
        var cmd = "printf '[Settings]\\ngtk-theme-name=" + gtkTheme + "\\ngtk-application-prefer-dark-theme=" + preferDark + "\\n' > ~/.config/gtk-3.0/settings.ini && cp ~/.config/gtk-3.0/settings.ini ~/.config/gtk-4.0/settings.ini"

        console.log("Updating GTK settings.ini for XWayland apps:", gtkTheme, "dark=" + preferDark)

        var proc = Qt.createQmlObject(
            'import Quickshell.Io; Process { ' +
            'command: ["bash", "-c", "' + cmd + '"]; ' +
            'running: true; }',
            settingsMenu
        )
    }

    function updateGhosttyColors() {
        console.log("Checking Ghostty theme configuration...")

        // Ensure Ghostty config has auto-switching theme line
        // Ghostty will automatically switch based on system theme
        var cmd = "grep -q '^theme = light:Adwaita,dark:Adwaita Dark' ~/.config/ghostty/config || " +
                  "(sed -i -e '/^theme = /d' -e '/^background = /d' -e '/^foreground = /d' " +
                  "-e '1i theme = light:Adwaita,dark:Adwaita Dark' ~/.config/ghostty/config)"

        var proc = Qt.createQmlObject(
            'import Quickshell.Io; Process { ' +
            'command: ["bash", "-c", "' + cmd + '"]; ' +
            'running: true; }',
            settingsMenu
        )
    }

    function updateSwayncStyle() {
        var styleFile = darkMode ? "style-dark.css" : "style-light.css"
        var cmd = "ln -sf ~/.config/swaync/" + styleFile + " ~/.config/swaync/style.css && swaync-client --reload-css"

        console.log("Switching swaync to:", styleFile)

        var proc = Qt.createQmlObject(
            'import Quickshell.Io; Process { ' +
            'command: ["bash", "-c", "' + cmd + '"]; ' +
            'running: true; }',
            settingsMenu
        )
    }

    function updateSnappySwitcherTheme() {
        var theme = darkMode ? "quickshell-dark.ini" : "quickshell-light.ini"
        var cmd = "sed -i 's/^name = .*/name = " + theme + "/' ~/.config/snappy-switcher/config.ini && snappy-switcher quit; sleep 0.3 && snappy-switcher --daemon &"
        console.log("Switching snappy-switcher theme to:", theme)
        Qt.createQmlObject(
            'import Quickshell.Io; Process { command: ["bash", "-c", "' + cmd + '"]; running: true; }',
            settingsMenu
        )
    }

    function updateCursorTheme() {
        var cmd = "gsettings set org.gnome.desktop.interface cursor-theme '" + cursorTheme + "'"

        console.log("Updating cursor theme:", cursorTheme)

        var proc = Qt.createQmlObject(
            'import Quickshell.Io; Process { ' +
            'command: ["bash", "-c", "' + cmd + '"]; ' +
            'running: true; }',
            settingsMenu
        )
    }

    function updateIconTheme() {
        var cmd = "gsettings set org.gnome.desktop.interface icon-theme '" + iconTheme + "'"

        console.log("Updating icon theme:", iconTheme)

        var proc = Qt.createQmlObject(
            'import Quickshell.Io; Process { ' +
            'command: ["bash", "-c", "' + cmd + '"]; ' +
            'running: true; }',
            settingsMenu
        )
    }

    function updateHyprbarsColors() {
        hyprbarsButtonTextColor = darkMode ? hyprbarsButtonTextColorDark : hyprbarsButtonTextColorLight
        hyprbarsButtonTextColorNeutral = darkMode ? hyprbarsButtonTextColorNeutralDark : hyprbarsButtonTextColorNeutralLight
        updateButtonIconColors()
    }

    function updateButtonIconColors() {
        requestHyprState("colors", {
            bar: darkMode ? hyprbarsBarColorDark : hyprbarsBarColorLight,
            text: darkMode ? hyprbarsTextColorDark : hyprbarsTextColorLight,
            inactive: darkMode ? "rgb(212125)" : "rgb(E0E0E0)",
            close: hyprbarsButtonTextColor, neutral: hyprbarsButtonTextColorNeutral
        })
    }

    function updateWindowMode() {
        requestHyprState("window_mode", windowMode)
    }

    onHyprbarsHeightChanged: {
        if (!isLoadingSettings) {
            saveSettings()
            updateHyprbarsConfig()
        }
    }

    onHyprbarsButtonAlignChanged: {
        if (!isLoadingSettings) {
            saveSettings()
            updateHyprbarsConfig()
            // Reload needed to apply button order change
            Qt.callLater(function() {
                var reloadProc = Qt.createQmlObject(
                    'import Quickshell.Io; Process { command: ["windoesnot-hyprctl", "reload"]; running: true; }',
                    settingsMenu
                )
            })
        }
    }

    onHyprbarsBarColorChanged: {
        if (!isLoadingSettings) {
            saveSettings()
            updateHyprbarsConfig()
        }
    }

    onHyprbarsBarBlurChanged: {
        if (!isLoadingSettings) {
            saveSettings()
            updateHyprbarsConfig()
        }
    }

    onHyprbarsTextColorChanged: {
        if (!isLoadingSettings) {
            saveSettings()
            updateHyprbarsConfig()
        }
    }

    onHyprbarsTextSizeChanged: {
        if (!isLoadingSettings) {
            saveSettings()
            updateHyprbarsConfig()
        }
    }

    onHyprbarsTextFontChanged: {
        if (!isLoadingSettings) {
            saveSettings()
            updateHyprbarsConfig()
        }
    }

    onHyprbarsTextAlignChanged: {
        if (!isLoadingSettings) {
            saveSettings()
            updateHyprbarsConfig()
            updateHyprbarsTextAlignLive()
        }
    }

    onHyprbarsBarTitleEnabledChanged: {
        if (!isLoadingSettings) {
            saveSettings()
            updateHyprbarsConfig()
        }
    }

    onHyprbarsCloseButtonColorChanged: {
        if (!isLoadingSettings) {
            saveSettings()
            updateHyprbarsConfig()
        }
    }

    onHyprbarsMaxButtonColorChanged: {
        if (!isLoadingSettings) {
            saveSettings()
            updateHyprbarsConfig()
        }
    }

    onHyprbarsMinButtonColorChanged: {
        if (!isLoadingSettings) {
            saveSettings()
            updateHyprbarsConfig()
        }
    }

    onHyprbarsButtonTextColorChanged: {
        if (!isLoadingSettings) {
            saveSettings()
            // SKIP updateHyprbarsConfig() - wird von updateHyprbarsColors() gesetzt
        }
    }

    onHyprbarsButtonTextColorNeutralChanged: {
        if (!isLoadingSettings) {
            saveSettings()
            // SKIP updateHyprbarsConfig() - wird von updateHyprbarsColors() gesetzt
        }
    }

    // Input onChange handlers
    onMouseSensitivityChanged: {
        if (!isLoadingSettings) {
            saveSettings()
            updateInputSettings()
        }
    }

    onMouseAccelProfileChanged: {
        if (!isLoadingSettings) {
            saveSettings()
            updateInputSettings()
        }
    }

    onFollowMouseChanged: {
        if (!isLoadingSettings) {
            saveSettings()
            updateInputSettings()
        }
    }

    onKeyboardLayoutChanged: {
        if (!isLoadingSettings) {
            saveSettings()
            updateInputSettings()
        }
    }

    onRepeatRateChanged: {
        if (!isLoadingSettings) {
            saveSettings()
            updateInputSettings()
        }
    }

    onRepeatDelayChanged: {
        if (!isLoadingSettings) {
            saveSettings()
            updateInputSettings()
        }
    }

    onNumlockByDefaultChanged: {
        if (!isLoadingSettings) {
            saveSettings()
            updateInputSettings()
        }
    }

    onTouchpadNaturalScrollChanged: {
        if (!isLoadingSettings) {
            saveSettings()
            updateInputSettings()
        }
    }

    onTouchpadDisableWhileTypingChanged: {
        if (!isLoadingSettings) {
            saveSettings()
            updateInputSettings()
        }
    }

    onTouchpadTapToClickChanged: {
        if (!isLoadingSettings) {
            saveSettings()
            updateInputSettings()
        }
    }

    onShowDockerTrayChanged: {
        if (!isLoadingSettings) {
            saveSettings()
            if (panelWindow) panelWindow.rebuildTrayModel()
        }
    }
    onShowOllamaTrayChanged: {
        if (!isLoadingSettings) {
            saveSettings()
            if (panelWindow) panelWindow.rebuildTrayModel()
        }
    }

    onUiLanguageChanged: {
        Lang.setCurrent(uiLanguage)  // Always update Lang, even during loading
        if (!isLoadingSettings) {
            saveSettings()
        }
    }

    onSystemLocaleChanged: {
        if (!isLoadingSettings) saveSettings()
    }

    onTimeZoneChanged: {
        if (!isLoadingSettings) {
            saveSettings()
            updateTimeZone()
        }
    }

    onUse24HourFormatChanged: {
        if (!isLoadingSettings) {
            saveSettings()
        }
    }

    onNtpEnabledChanged: {
        if (!isLoadingSettings) {
            saveSettings()
            updateNtpSettings()
        }
    }

    // Font onChange handlers
    onFontInterfaceChanged: {
        if (!isLoadingSettings) {
            saveSettings()
            updateFontSettings()
        }
    }

    onFontDocumentChanged: {
        if (!isLoadingSettings) {
            saveSettings()
            updateFontSettings()
        }
    }

    onFontMonospaceChanged: {
        if (!isLoadingSettings) {
            saveSettings()
            updateFontSettings()
        }
    }

    onFontHintingChanged: {
        if (!isLoadingSettings) {
            saveSettings()
            updateFontSettings()
        }
    }

    onFontAntialiasingChanged: {
        if (!isLoadingSettings) {
            saveSettings()
            updateFontSettings()
        }
    }

    onFontScalingChanged: {
        if (!isLoadingSettings) {
            saveSettings()
            updateFontSettings()
        }
    }

    // Default applications onChange handlers
    onDefaultFileManagerChanged: {
        if (!isLoadingSettings)
            updateDefaultApps(["inode/directory"], defaultFileManager)
    }

    onDefaultTextEditorChanged: {
        if (!isLoadingSettings)
            updateDefaultApps(["text/plain", "text/x-script.python", "text/x-shellscript",
                               "text/x-c", "text/x-csrc", "text/x-chdr",
                               "text/x-cmake", "text/markdown"], defaultTextEditor)
    }

    onDefaultImageViewerChanged: {
        if (!isLoadingSettings)
            updateDefaultApps(["image/png", "image/jpeg", "image/gif", "image/webp",
                               "image/svg+xml", "image/tiff", "image/bmp", "image/avif",
                               "image/heic", "image/heif"], defaultImageViewer)
    }

    onDefaultPdfViewerChanged: {
        if (!isLoadingSettings)
            updateDefaultApps(["application/pdf", "application/x-pdf"], defaultPdfViewer)
    }

    onDefaultWebBrowserChanged: {
        if (!isLoadingSettings)
            updateDefaultApps(["x-scheme-handler/http", "x-scheme-handler/https",
                               "text/html", "application/xhtml+xml",
                               "x-scheme-handler/about", "x-scheme-handler/unknown"], defaultWebBrowser)
    }

    // Set multiple MIME types to the same app in one batch process
    function updateDefaultApps(mimeTypes, desktopFile) {
        if (!desktopFile || desktopFile.length === 0) return
        var cmds = mimeTypes.map(function(m) {
            return "xdg-mime default " + desktopFile + " " + m
        }).join(" && ")
        console.log("Setting default app to:", desktopFile, "for", mimeTypes.length, "MIME types")
        var proc = Qt.createQmlObject('import Quickshell.Io; Process { }', settingsMenu)
        proc.command = ["bash", "-c", cmds]
        proc.running = true
    }

    // Process for enabling/disabling titlebar via bar_height
    Process {
        id: hyprbarsPluginProc
        running: false

        stdout: StdioCollector {
            onStreamFinished: {
                if (this.text.trim().length > 0) {
                    console.log("Titlebar toggle output:", this.text.trim())
                }
            }
        }

        stderr: StdioCollector {
            onStreamFinished: {
                if (this.text.trim().length > 0) {
                    console.error("Titlebar toggle error:", this.text.trim())
                }
            }
        }
    }

    // Process for enabling/disabling hyprbars
    Process {
        id: hyprbarsToggleProc
        running: false
    }

    // Process for toggling individual hyprbars buttons
    Process {
        id: hyprbarsButtonToggleProc
        running: false

        stdout: StdioCollector {
            onStreamFinished: {
                if (this.text.trim().length > 0) {
                    console.log("Button toggle output:", this.text.trim())
                }
            }
        }

        stderr: StdioCollector {
            onStreamFinished: {
                if (this.text.trim().length > 0) {
                    console.error("Button toggle error:", this.text.trim())
                }
            }
        }
    }

    // Process for updating hyprbars config (height/alignment)
    Process {
        id: hyprbarsConfigProc
        running: false
    }

    // Process for updating input settings
    Process {
        id: inputSettingsProc
        running: false
    }

    // Process for updating font settings
    Process {
        id: fontSettingsProc
        running: false
    }

    // Process for updating hyprbars text align live
    Process {
        id: hyprbarsTextAlignProc
        running: false

        stdout: StdioCollector {
            onStreamFinished: {
                if (this.text.trim().length > 0) {
                    console.log("Text align update output:", this.text.trim())
                }
            }
        }

        stderr: StdioCollector {
            onStreamFinished: {
                if (this.text.trim().length > 0) {
                    console.error("Text align update error:", this.text.trim())
                }
            }
        }
    }

    function updateFontSettings() {
        console.log("Updating font settings")

        // Build command to update GTK font settings via gsettings
        var cmd = "gsettings set org.gnome.desktop.interface font-name '" + fontInterface + "' && " +
                  "gsettings set org.gnome.desktop.interface document-font-name '" + fontDocument + "' && " +
                  "gsettings set org.gnome.desktop.interface monospace-font-name '" + fontMonospace + "' && " +
                  "gsettings set org.gnome.desktop.interface text-scaling-factor " + fontScaling + " && " +
                  "gsettings set org.gnome.desktop.interface font-hinting '" + fontHinting + "' && " +
                  "gsettings set org.gnome.desktop.interface font-antialiasing '" + fontAntialiasing + "'"

        fontSettingsProc.command = ["bash", "-c", cmd]
        fontSettingsProc.running = true
    }

    function updateInputSettings() {
        requestHyprState("input", {
            sensitivity: mouseSensitivity, accel_profile: mouseAccelProfile,
            follow_mouse: followMouse, kb_layout: keyboardLayout,
            repeat_rate: repeatRate, repeat_delay: repeatDelay,
            numlock_by_default: numlockByDefault,
            natural_scroll: touchpadNaturalScroll,
            disable_while_typing: touchpadDisableWhileTyping,
            tap_to_click: touchpadTapToClick
        })
    }

    function selectLanguage(locale) {
        if (localeChangeBusy) return
        pendingSystemLocale = locale
        previousUiLanguage = uiLanguage
        const language = locale.split(/[_ .@-]/)[0]
        uiLanguage = language === "de" ? "de" : "en"
        updateSystemLocale()
    }

    function updateSystemLocale() {
        localeChangeBusy = true
        localeChangeFailed = false
        fileDialogOpen = true
        localeProc.command = ["localectl", "set-locale", "LANG=" + pendingSystemLocale, "LC_MESSAGES=" + pendingSystemLocale, "LC_TIME=" + pendingSystemLocale]
        localeProc.running = true
    }

    function finishLanguageChange(code) {
        localeChangeBusy = false
        fileDialogOpen = false
        localeChangeFailed = code !== 0
        if (code === 0) systemLocale = pendingSystemLocale
        else uiLanguage = previousUiLanguage
    }

    function updateTimeZone() {
        console.log("Updating timezone to:", timeZone)

        var cmd = "timedatectl set-timezone " + timeZone
        timezoneProc.command = ["bash", "-c", cmd]
        timezoneProc.running = true
    }

    function updateNtpSettings() {
        console.log("Updating NTP to:", ntpEnabled)

        var cmd = "timedatectl set-ntp " + (ntpEnabled ? "true" : "false")
        ntpProc.command = ["bash", "-c", cmd]
        ntpProc.running = true
    }

    function updateHyprbars() {
        requestHyprState("bars", {
            plugin_enabled: hyprbarsPluginEnabled, height: hyprbarsHeight,
            alignment: hyprbarsButtonAlign, blur: hyprbarsBarBlur,
            text_size: hyprbarsTextSize, font: hyprbarsTextFont,
            text_align: hyprbarsTextAlign, title_enabled: hyprbarsBarTitleEnabled,
            buttons_enabled: hyprbarsEnabled, close: hyprbarsCloseButtonEnabled,
            max: hyprbarsMaxButtonEnabled, min: hyprbarsMinButtonEnabled
        })
    }

    function updateHyprbarsPlugin() {
        requestHyprState("bars", {
            plugin_enabled: hyprbarsPluginEnabled, height: hyprbarsHeight,
            alignment: hyprbarsButtonAlign, blur: hyprbarsBarBlur,
            text_size: hyprbarsTextSize, font: hyprbarsTextFont,
            text_align: hyprbarsTextAlign, title_enabled: hyprbarsBarTitleEnabled,
            buttons_enabled: hyprbarsEnabled, close: hyprbarsCloseButtonEnabled,
            max: hyprbarsMaxButtonEnabled, min: hyprbarsMinButtonEnabled
        })
    }

    function updateHyprbarsButtonToggles() {
        requestHyprState("bars", {
            plugin_enabled: hyprbarsPluginEnabled, height: hyprbarsHeight,
            alignment: hyprbarsButtonAlign, blur: hyprbarsBarBlur,
            text_size: hyprbarsTextSize, font: hyprbarsTextFont,
            text_align: hyprbarsTextAlign, title_enabled: hyprbarsBarTitleEnabled,
            buttons_enabled: hyprbarsEnabled, close: hyprbarsCloseButtonEnabled,
            max: hyprbarsMaxButtonEnabled, min: hyprbarsMinButtonEnabled
        })
    }

    function updateHyprbarsTextAlignLive() {
        requestHyprState("bars", {
            plugin_enabled: hyprbarsPluginEnabled, height: hyprbarsHeight,
            alignment: hyprbarsButtonAlign, blur: hyprbarsBarBlur,
            text_size: hyprbarsTextSize, font: hyprbarsTextFont,
            text_align: hyprbarsTextAlign, title_enabled: hyprbarsBarTitleEnabled,
            buttons_enabled: hyprbarsEnabled, close: hyprbarsCloseButtonEnabled,
            max: hyprbarsMaxButtonEnabled, min: hyprbarsMinButtonEnabled
        })
    }

    function updateHyprbarsConfig() {
        requestHyprState("bars", {
            plugin_enabled: hyprbarsPluginEnabled, height: hyprbarsHeight,
            alignment: hyprbarsButtonAlign, blur: hyprbarsBarBlur,
            text_size: hyprbarsTextSize, font: hyprbarsTextFont,
            text_align: hyprbarsTextAlign, title_enabled: hyprbarsBarTitleEnabled,
            buttons_enabled: hyprbarsEnabled, close: hyprbarsCloseButtonEnabled,
            max: hyprbarsMaxButtonEnabled, min: hyprbarsMinButtonEnabled
        })
    }

    Item {
        anchors.fill: parent
        clip: true

        // Schließt Color Palette bei Klick auf Settings
        MouseArea {
            anchors.fill: parent
            propagateComposedEvents: true
            onClicked: function(mouse) {
                if (settingsMenu.colorPaletteVisible) {
                    settingsMenu.colorPaletteVisible = false
                    mouse.accepted = true
                } else {
                    mouse.accepted = false
                }
            }
        }

        Rectangle {
            anchors.fill: parent
            color: darkMode ? Qt.rgba(0.125, 0.125, 0.125, 0.93) : Qt.rgba(0.95, 0.95, 0.95, 0.97)
            border.color: darkMode ? "#3a3a3f" : "#c0c0c0"
            border.width: 1
            topLeftRadius: settingsMenu.borderRadius
            topRightRadius: settingsMenu.borderRadius
            bottomLeftRadius: 0
            bottomRightRadius: 0
        }

        Row {
            anchors.fill: parent
            spacing: 0

            // Linke Navigation
            Rectangle {
                width: 250
                height: parent.height
                color: "transparent"
                clip: true

                // Main background with full radius (wird unten abgeschnitten)
                Rectangle {
                    anchors.fill: parent
                    color: darkMode ? Qt.rgba(0.09, 0.09, 0.09, 1) : Qt.rgba(0.90, 0.90, 0.90, 1)
                    topLeftRadius: settingsMenu.borderRadius
                    topRightRadius: 0
                    bottomLeftRadius: 0
                    bottomRightRadius: 0
                }

                // Cover right side to make corners square
                Rectangle {
                    anchors.right: parent.right
                    anchors.top: parent.top
                    anchors.bottom: parent.bottom
                    width: 12
                    color: darkMode ? Qt.rgba(0.09, 0.09, 0.09, 1) : Qt.rgba(0.90, 0.90, 0.90, 1)
                }

                // Cover bottom to make corners square
                Rectangle {
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.bottom: parent.bottom
                    height: 12
                    color: darkMode ? Qt.rgba(0.09, 0.09, 0.09, 1) : Qt.rgba(0.90, 0.90, 0.90, 1)
                }

                Column {
                    anchors.fill: parent
                    spacing: 0

                    Text {
                        text: Lang.get("nav.settings", settingsMenu.uiLanguage)
                        font.pixelSize: 20
                        font.bold: true
                        color: darkMode ? "#fff" : "#1a1a1a"
                        leftPadding: 20
                        topPadding: 40
                        bottomPadding: 30
                        width: parent.width
                    }

                    Flickable {
                        width: parent.width
                        height: parent.height - 110
                        contentWidth: width
                        contentHeight: navColumn.height
                        clip: true
                        boundsBehavior: Flickable.StopAtBounds

                        Column {
                            id: navColumn
                            width: parent.width
                            spacing: 8
                            topPadding: 0
                            leftPadding: 10
                            rightPadding: 10
                            bottomPadding: 30

                            // Navigation Items
                            Repeater {
                        model: ListModel {
                            ListElement { category: "desktop";    labelKey: "nav.desktop";    icon: "img/Win11-dark/places/symbolic/user-desktop-symbolic.svg" }
                            ListElement { category: "monitors";   labelKey: "nav.monitors";   icon: "img/Win11-dark/devices/symbolic/video-display-symbolic.svg" }
                            ListElement { category: "background"; labelKey: "nav.background"; icon: "img/Win11-dark/places/symbolic/folder-pictures-symbolic.svg" }
                            ListElement { category: "appearance"; labelKey: "nav.appearance"; icon: "img/Win11-dark/actions/symbolic/builder-appearance-symbolic.svg" }
                            ListElement { category: "colors";     labelKey: "nav.colors";     icon: "img/Win11-dark/actions/symbolic/color-palette-symbolic.svg" }
                            ListElement { category: "alignment";  labelKey: "nav.alignment";  icon: "img/Win11-dark/actions/symbolic/align-on-canvas-symbolic.svg" }
                            ListElement { category: "input";      labelKey: "nav.input";      icon: "img/Win11-dark/devices/symbolic/input-mouse-symbolic.svg" }
                            ListElement { category: "apps";       labelKey: "nav.apps";       icon: "img/Win11-dark/actions/symbolic/view-app-grid-symbolic.svg" }
                            ListElement { category: "maintenance"; labelKey: "nav.maintenance"; icon: "img/Win11-dark/categories/symbolic/preferences-system-symbolic.svg" }
                            ListElement { category: "kernel"; labelKey: "nav.kernel"; icon: "img/Win11-dark/devices/symbolic/computer-chip-symbolic.svg" }
                            ListElement { category: "backups";    labelKey: "nav.backups";    icon: "img/Win11-dark/places/symbolic/folder-documents-symbolic.svg" }
                            ListElement { category: "updates";    labelKey: "nav.updates";    icon: "img/Win11-dark/actions/symbolic/system-update-symbolic.svg" }
                            ListElement { category: "about";      labelKey: "nav.about";      icon: "img/Win11-dark/actions/symbolic/link-symbolic.svg" }
                            ListElement { category: "help";       labelKey: "nav.help";       icon: "img/Win11-dark/actions/symbolic/help-contents-symbolic.svg" }
                        }

                        delegate: Rectangle {
                            id: navItemRect
                            width: parent.width - 20
                            height: 45
                            radius: 6
                            property bool isActive: settingsMenu.currentCategory === category
                            color: isActive ? (darkMode ? "#2a2a2a" : "#c8c8c8")
                                           : navMouseArea.containsMouse ? (darkMode ? "#1e1e1e" : "#dedede") : "transparent"
                            anchors.left: parent.left
                            anchors.leftMargin: 10

                            // Active indicator - vertical accent line
                            Rectangle {
                                visible: navItemRect.isActive
                                width: 3
                                height: 22
                                radius: 2
                                color: settingsMenu.accentColor
                                anchors.left: parent.left
                                anchors.leftMargin: 4
                                anchors.verticalCenter: parent.verticalCenter
                            }

                            Row {
                                anchors.fill: parent
                                anchors.leftMargin: 15
                                anchors.verticalCenter: parent.verticalCenter
                                spacing: 12

                                Image {
                                    source: icon
                                    width: 20
                                    height: 20
                                    sourceSize.width: 20
                                    sourceSize.height: 20
                                    fillMode: Image.PreserveAspectFit
                                    anchors.verticalCenter: parent.verticalCenter
                                    smooth: true
                                    antialiasing: true
                                    mipmap: true
                                    layer.enabled: !darkMode
                                    layer.smooth: true
                                    layer.effect: ColorOverlay { color: "#000000" }
                                }

                                Text {
                                    text: Lang.get(labelKey, uiLanguage)
                                    font.pixelSize: 14
                                    color: darkMode ? "#aaa" : "#555"
                                    anchors.verticalCenter: parent.verticalCenter
                                }
                            }

                            MouseArea {
                                id: navMouseArea
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                onClicked: settingsMenu.currentCategory = category
                            }
                        }
                    }  // End Repeater
                }  // End Column (navColumn)
            }  // End Flickable
            }  // End outer Column
        }

            // Rechter Inhaltsbereich
            Rectangle {
                width: parent.width - 250
                height: parent.height
                color: "transparent"
                clip: true

                // Main background with full radius
                Rectangle {
                    anchors.fill: parent
                    color: darkMode ? Qt.rgba(0.125, 0.125, 0.125, 0) : Qt.rgba(0.95, 0.95, 0.95, 0)
                    radius: 12
                }

                // Cover left side to make corners square
                Rectangle {
                    anchors.left: parent.left
                    anchors.top: parent.top
                    anchors.bottom: parent.bottom
                    width: 12
                    color: "transparent"
                }

                // Cover bottom to make corners square
                Rectangle {
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.bottom: parent.bottom
                    height: 12
                    color: "transparent"
                }

                Column {
                    anchors.fill: parent
                    anchors.margins: 30
                    spacing: 20

                    // Header
                    Text {
                        text: {
                            if (settingsMenu.currentCategory === "desktop") return Lang.get("header.desktop", uiLanguage)
                            if (settingsMenu.currentCategory === "background") return Lang.get("header.background", uiLanguage)
                            if (settingsMenu.currentCategory === "appearance") return Lang.get("header.appearance", uiLanguage)
                            if (settingsMenu.currentCategory === "colors") return Lang.get("header.colors", uiLanguage)
                            if (settingsMenu.currentCategory === "alignment") return Lang.get("header.alignment", uiLanguage)
                            if (settingsMenu.currentCategory === "input") return Lang.get("header.input", uiLanguage)
                            if (settingsMenu.currentCategory === "apps") return Lang.get("header.apps", uiLanguage)
                            if (settingsMenu.currentCategory === "maintenance") return Lang.get("header.maintenance", uiLanguage)
                            if (settingsMenu.currentCategory === "kernel") return Lang.get("header.kernel", uiLanguage)
                            if (settingsMenu.currentCategory === "backups") return Lang.get("header.backups", uiLanguage)
                            if (settingsMenu.currentCategory === "monitors") return Lang.get("header.monitors", uiLanguage)
                            if (settingsMenu.currentCategory === "updates") return Lang.get("header.updates", uiLanguage)
                            if (settingsMenu.currentCategory === "about") return Lang.get("header.about", uiLanguage)
                            if (settingsMenu.currentCategory === "help") return Lang.get("header.help", uiLanguage)
                            return Lang.get("nav.settings", uiLanguage)
                        }
                        font.pixelSize: 24
                        font.bold: true
                        color: darkMode ? "#fff" : "#1a1a1a"
                    }

                    Rectangle {
                        width: parent.width
                        height: 1
                        color: darkMode ? "#3a3a3a" : "#d0d0d0"
                    }

                    // Content basierend auf Kategorie (mit Scroll)
                    Item {
                        width: parent.width
                        height: parent.height - 45  // Taskbar height

                        // Scrollable Container für alle Kategorien
                        Flickable {
                            id: settingsFlickable
                            anchors.fill: parent
                            anchors.rightMargin: 20  // Platz für Scrollbar
                            contentWidth: width
                            contentHeight: getCurrentCategoryHeight()
                            clip: true
                            boundsBehavior: Flickable.StopAtBounds

                            function getCurrentCategoryHeight() {
                                // Dynamische Höhe basierend auf tatsächlichem Inhalt + padding
                                var padding = 20
                                if (settingsMenu.currentCategory === "desktop") return desktopLoader.item ? desktopLoader.item.height + padding : height
                                if (settingsMenu.currentCategory === "appearance") return appearanceLoader.item ? appearanceLoader.item.height + padding : height
                                if (settingsMenu.currentCategory === "colors") return colorsLoader.item ? colorsLoader.item.height + padding : height
                                if (settingsMenu.currentCategory === "alignment") return alignmentLoader.item ? alignmentLoader.item.height + padding : height
                                if (settingsMenu.currentCategory === "input") return inputLoader.item ? inputLoader.item.height + padding : height
                                if (settingsMenu.currentCategory === "apps") return appsLoader.item ? appsLoader.item.height + padding : height
                                if (settingsMenu.currentCategory === "maintenance") return maintenanceLoader.item ? maintenanceLoader.item.height + padding : height
                                if (settingsMenu.currentCategory === "kernel") return kernelLoader.item ? kernelLoader.item.height + padding : height
                                if (settingsMenu.currentCategory === "backups") return backupsLoader.item ? backupsLoader.item.height + padding : height
                                if (settingsMenu.currentCategory === "monitors") return monitorsLoader.item ? monitorsLoader.item.height + padding : height
                                if (settingsMenu.currentCategory === "updates") return updatesLoader.item ? updatesLoader.item.height + padding : height
                                if (settingsMenu.currentCategory === "about") return aboutLoader.item ? aboutLoader.item.height + padding : height
                                if (settingsMenu.currentCategory === "help") return helpLoader.item ? helpLoader.item.height + padding : height
                                if (settingsMenu.currentCategory === "background") return height - 45  // Kein Scrollbar nötig
                                return height
                            }

                            Item {
                                id: contentContainer
                                width: parent.width
                                height: parent.contentHeight

                        // Desktop Settings
                        Loader {
                            id: desktopLoader
                            active: settingsMenu.currentCategory === "desktop"
                            visible: settingsMenu.currentCategory === "desktop"
                            width: parent.width
                            asynchronous: false
                            Component.onCompleted: if (active) setSource("settings/DesktopCategory.qml", {"settingsMenu": settingsMenu})
                            onActiveChanged: if (active) setSource("settings/DesktopCategory.qml", {"settingsMenu": settingsMenu})
                        }

                        // Background Settings
                        Loader {
                            id: backgroundSettingsLoader
                            visible: settingsMenu.currentCategory === "background"
                            anchors.fill: parent
                            source: "settings/BackgroundCategory.qml"

                            onLoaded: {
                                if (item) {
                                    item.accentColor = Qt.binding(function() { return settingsMenu.accentColor })
                                    item.settingsMenu = settingsMenu
                                }
                            }
                        }

                        // Aussehen Settings
                        Loader {
                            id: appearanceLoader
                            active: settingsMenu.currentCategory === "appearance"
                            visible: settingsMenu.currentCategory === "appearance"
                            width: parent.width
                            asynchronous: false
                            Component.onCompleted: if (active) setSource("settings/AppearanceCategory.qml", {"settingsMenu": settingsMenu})
                            onActiveChanged: if (active) setSource("settings/AppearanceCategory.qml", {"settingsMenu": settingsMenu})
                        }

                        // Farben Settings
                        Loader {
                            id: colorsLoader
                            active: settingsMenu.currentCategory === "colors"
                            visible: settingsMenu.currentCategory === "colors"
                            width: parent.width
                            asynchronous: false
                            Component.onCompleted: if (active) setSource("settings/ColorsCategory.qml", {"settingsMenu": settingsMenu})
                            onActiveChanged: if (active) setSource("settings/ColorsCategory.qml", {"settingsMenu": settingsMenu})
                        }

                        // Ausrichtung Settings
                        Loader {
                            id: alignmentLoader
                            active: settingsMenu.currentCategory === "alignment"
                            visible: settingsMenu.currentCategory === "alignment"
                            width: parent.width
                            asynchronous: false
                            Component.onCompleted: if (active) setSource("settings/AlignmentCategory.qml", {"settingsMenu": settingsMenu})
                            onActiveChanged: if (active) setSource("settings/AlignmentCategory.qml", {"settingsMenu": settingsMenu})
                        }

                        // Input Settings (Maus & Tastatur)
                        Loader {
                            id: inputLoader
                            active: settingsMenu.currentCategory === "input"
                            visible: settingsMenu.currentCategory === "input"
                            width: parent.width
                            asynchronous: false
                            Component.onCompleted: if (active) setSource("settings/InputCategory.qml", {"settingsMenu": settingsMenu})
                            onActiveChanged: if (active) setSource("settings/InputCategory.qml", {"settingsMenu": settingsMenu})
                        }

                        // Apps Settings
                        Loader {
                            id: appsLoader
                            active: settingsMenu.currentCategory === "apps"
                            visible: settingsMenu.currentCategory === "apps"
                            width: parent.width
                            asynchronous: false
                            Component.onCompleted: if (active) setSource("settings/AppsCategory.qml", {"settingsMenu": settingsMenu})
                            onActiveChanged: if (active) setSource("settings/AppsCategory.qml", {"settingsMenu": settingsMenu})
                        }

                        Loader {
                            id: maintenanceLoader
                            active: settingsMenu.currentCategory === "maintenance" || (item !== null && item.busy)
                            visible: settingsMenu.currentCategory === "maintenance"
                            width: parent.width
                            asynchronous: false
                            Component.onCompleted: if (active) setSource("settings/MaintenanceCategory.qml", {"settingsMenu": settingsMenu})
                            onActiveChanged: if (active && !item) setSource("settings/MaintenanceCategory.qml", {"settingsMenu": settingsMenu})
                        }

                        Loader {
                            id: kernelLoader
                            active: settingsMenu.currentCategory === "kernel" || (item !== null && item.busy)
                            visible: settingsMenu.currentCategory === "kernel"
                            width: parent.width
                            asynchronous: false
                            Component.onCompleted: if (active) setSource("settings/KernelCategory.qml", {"settingsMenu": settingsMenu})
                            onActiveChanged: if (active && !item) setSource("settings/KernelCategory.qml", {"settingsMenu": settingsMenu})
                        }

                        // Backup Settings
                        Loader {
                            id: backupsLoader
                            active: settingsMenu.currentCategory === "backups"
                            visible: settingsMenu.currentCategory === "backups"
                            width: parent.width
                            asynchronous: false
                            Component.onCompleted: if (active) setSource("settings/BackupsCategory.qml", {"settingsMenu": settingsMenu})
                            onActiveChanged: if (active) setSource("settings/BackupsCategory.qml", {"settingsMenu": settingsMenu})
                        }

                        // Hilfe Settings
                        Loader {
                            id: helpLoader
                            active: settingsMenu.currentCategory === "help"
                            visible: settingsMenu.currentCategory === "help"
                            width: parent.width
                            asynchronous: false
                            Component.onCompleted: if (active) setSource("settings/HelpCategory.qml", {"settingsMenu": settingsMenu})
                            onActiveChanged: if (active) setSource("settings/HelpCategory.qml", {"settingsMenu": settingsMenu})
                        }

                        // Monitor Settings
                        Loader {
                            id: monitorsLoader
                            active: settingsMenu.currentCategory === "monitors"
                            visible: settingsMenu.currentCategory === "monitors"
                            width: parent.width
                            asynchronous: false
                            Component.onCompleted: if (active) setSource("settings/MonitorsCategory.qml", {"settingsMenu": settingsMenu})
                            onActiveChanged: if (active) setSource("settings/MonitorsCategory.qml", {"settingsMenu": settingsMenu})
                        }

                        // Update Settings
                        Loader {
                            id: updatesLoader
                            active: settingsMenu.currentCategory === "updates"
                            visible: settingsMenu.currentCategory === "updates"
                            width: parent.width
                            asynchronous: false
                            Component.onCompleted: if (active) setSource("settings/UpdateCategory.qml", {"settingsMenu": settingsMenu})
                            onActiveChanged: if (active) setSource("settings/UpdateCategory.qml", {"settingsMenu": settingsMenu})
                        }

                        // Über Settings
                        Loader {
                            id: aboutLoader
                            active: settingsMenu.currentCategory === "about"
                            visible: settingsMenu.currentCategory === "about"
                            width: parent.width
                            asynchronous: false
                            Component.onCompleted: if (active) setSource("settings/AboutCategory.qml", {"settingsMenu": settingsMenu})
                            onActiveChanged: if (active) setSource("settings/AboutCategory.qml", {"settingsMenu": settingsMenu})
                        }
                            }  // Ende contentContainer (Item)
                        }  // Ende Flickable

                        // Custom Scrollbar Indicator - nur wenn nötig
                        Rectangle {
                            id: scrollIndicator
                            anchors.right: parent.right
                            anchors.rightMargin: 0
                            y: {
                                if (scrollIndicatorArea.drag.active) {
                                    return scrollIndicatorArea.drag.target.y
                                } else {
                                    var scrollRange = settingsFlickable.height - height - 4
                                    var maxScroll = 1 - settingsFlickable.visibleArea.heightRatio
                                    if (maxScroll <= 0) return 2
                                    var normalizedPosition = settingsFlickable.visibleArea.yPosition / maxScroll
                                    return normalizedPosition * scrollRange + 2
                                }
                            }
                            width: 6
                            height: Math.max(30, settingsFlickable.visibleArea.heightRatio * (settingsFlickable.height - 4))
                            radius: 3
                            color: settingsMenu.accentColor
                            opacity: settingsFlickable.moving || scrollIndicatorArea.containsMouse || scrollIndicatorArea.drag.active ? 0.8 : 0.4
                            visible: settingsFlickable.contentHeight > settingsFlickable.height

                            Behavior on opacity {
                                NumberAnimation { duration: 150 }
                            }

                            MouseArea {
                                id: scrollIndicatorArea
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor

                                drag.target: scrollIndicator
                                drag.axis: Drag.YAxis
                                drag.minimumY: 2
                                drag.maximumY: settingsFlickable.height - scrollIndicator.height - 2

                                onPositionChanged: {
                                    if (drag.active) {
                                        var availableHeight = settingsFlickable.height - scrollIndicator.height - 4
                                        var scrollRatio = (scrollIndicator.y - 2) / availableHeight
                                        var maxContentY = settingsFlickable.contentHeight - settingsFlickable.height
                                        settingsFlickable.contentY = scrollRatio * maxContentY
                                    }
                                }
                            }
                        }
                    }  // Ende Item (Content Container)
                }
            }
        }
    }  // Ende Item (Clip Container)

    Rectangle {
        id: backupAuthenticationOverlay
        anchors.fill: parent
        z: 10000
        visible: settingsMenu.backupAuthenticationActive
        color: "#99000000"
        MouseArea { anchors.fill: parent; onWheel: (wheel) => wheel.accepted = true }
        AuthenticationCard {
            anchors.centerIn: parent
            width: Math.min(460, parent.width - 40)
            height: implicitHeight
            settingsMenu: settingsMenu
            flow: settingsMenu.backupAuthenticationActive ? settingsMenu.authentication.flow : null
        }
    }
}
