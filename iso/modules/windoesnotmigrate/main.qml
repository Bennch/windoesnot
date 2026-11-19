import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15

Rectangle {
    id: page

    property var bridge: typeof migrateBridge === "undefined" ? null : migrateBridge
    property bool german: bridge ? bridge.german : false
    property var disks: bridge && bridge.devices ? JSON.parse(bridge.devices) : []
    property var plan: bridge && bridge.manifest ? JSON.parse(bridge.manifest) : ({
        "profiles": [],
        "warnings": []
    })
    readonly property bool linux: plan.kind === "linux"
    property bool skipped: false
    property real freeBytes: bridge && bridge.freeBytes !== undefined ? bridge.freeBytes : -1
    property real selectedBytes: {
        var sum = 0;
        for (var p of plan.profiles || []) for (var item of p.items || []) if (item.selected) {
            sum += item.bytes;
        }
        for (var u of plan.users || []) if (u.selected) {
            sum += u.bytes || 0;
            for (var f of u.folders || []) if ((u.exclude || []).indexOf(f.name) >= 0) sum -= f.bytes;
        }
        for (var l of plan.locations || []) if (l.selected) sum += l.bytes || 0;
        return sum;
    }

    // Name of the system the data comes from (Windows 7 ... 11), from the exporter's handoff; neutral until known.
    readonly property string systemName: linux ? (plan.system || "Linux") : plan && plan.handoff && plan.handoff.windows_version ? niceWindowsName(String(plan.handoff.windows_version)) : "Windows"

    // "Windows 10 19045" (PowerShell exporter) or "10.0.26100.0" (Setup app) -> "Windows 10" / "Windows 11".
    function niceWindowsName(raw) {
        var numeric = /^(\d+)\.(\d+)\.(\d+)/.exec(raw);
        if (numeric) {
            var major = parseInt(numeric[1]), minor = parseInt(numeric[2]), build = parseInt(numeric[3]);
            if (major === 10) return build >= 22000 ? "Windows 11" : "Windows 10";
            if (major === 6 && minor === 3) return "Windows 8.1";
            if (major === 6 && minor === 2) return "Windows 8";
            if (major === 6 && minor === 1) return "Windows 7";
            return "Windows";
        }
        return raw.replace(/^(Windows [0-9.]+).*$/, "$1");
    }

    function tr(de, en) {
        return german ? de : en;
    }

    function warningText(code) {
        var key = String(code).split(":")[0];
        var texts = {
            "separate_filesystems_not_scanned": tr("Eigene Partitionen für /home oder andere Ordner wurden nicht durchsucht.", "Separate partitions for /home or other folders were not scanned."),
            "unreadable": tr("Einige Dateien waren nicht lesbar und werden übersprungen.", "Some files were not readable and will be skipped."),
            "special_file": tr("Besondere Dateien (Sockets, Geräte) werden übersprungen.", "Special files (sockets, devices) will be skipped."),
            "home_missing": tr("Für einen Benutzer wurde kein Home-Ordner gefunden.", "No home folder was found for a user."),
            "home_unsafe": tr("Ein Home-Ordner wurde aus Sicherheitsgründen übersprungen.", "A home folder was skipped for safety."),
            "package_database_unsafe": tr("Die Paketliste konnte nicht sicher gelesen werden.", "The package list could not be read safely."),
            "arch_foreign_unknown": tr("Programme von außerhalb der Paketquellen konnten nicht erkannt werden.", "Programs from outside the package sources could not be identified."),
            "services_unreadable": tr("Dienste konnten nicht gelesen werden.", "Services could not be read.")
        };
        return texts[key] || String(code);
    }

    function size(bytes) {
        if (bytes >= 1.07374e+09) return (bytes / 1.07374e+09).toFixed(1) + " GiB";
        if (bytes >= 1.04858e+06) return (bytes / 1.04858e+06).toFixed(1) + " MiB";
        if (bytes >= 1024) return (bytes / 1024).toFixed(1) + " KiB";
        return bytes + " B";
    }

    function folderName(kind) {
        var names = {
            "Documents": "Dokumente",
            "Pictures": "Bilder",
            "Music": "Musik",
            "Videos": "Videos",
            "Downloads": "Downloads",
            "Desktop": "Desktop",
            "Firefox": "Firefox",
            "Thunderbird": "E-Mail (Thunderbird)"
        };
        return german ? (names[kind] || kind) : (kind === "Thunderbird" ? "Email (Thunderbird)" : kind);
    }

    function hasWarning(code) {
        return plan.warnings && plan.warnings.indexOf(code) >= 0;
    }

    color: "#202020"

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 24
        spacing: 12

        Rectangle {
            visible: page.bridge && page.bridge.installChoice !== "alongside" && !page.skipped
            Layout.fillWidth: true
            implicitHeight: choiceWarning.implicitHeight + 20
            color: "#382d22"; border.color: "#fe6f2d"; radius: 8
            ColumnLayout {
                id: choiceWarning
                anchors.left: parent.left; anchors.right: parent.right; anchors.top: parent.top; anchors.margins: 10
                Label {
                    Layout.fillWidth: true; wrapMode: Text.WordWrap; color: "#f3c99d"
                    text: page.tr("Der Umzug funktioniert nur mit ‚Parallel installieren‘, weil dein altes System sonst vor dem Kopieren gelöscht werden kann. Nutze ‚Zurück‘, um zur Partitionierung zurückzukehren, oder lasse den Umzug aus. Parallel braucht mindestens etwa 32 GiB freien Platz nach dem Verkleinern.", "The data move only works with ‘Install alongside’, because your old system could otherwise be deleted before copying. Use ‘Back’ to return to partitioning or skip the data move. Installing alongside needs at least about 32 GiB free after shrinking.")
                }
                Button { text: page.tr("Umzug auslassen", "Skip data move"); onClicked: { page.skipped = true; if (page.bridge) page.bridge.setSkipped(true) } }
            }
        }

        Label {
            text: page.tr("Daten aus " + page.systemName + " übernehmen", "Bring your " + page.systemName + " data")
            font.pixelSize: 24
            font.bold: true
            color: "#eeeeee"
        }

        Label {
            text: page.tr("Ordner auswählen. Beim Kopieren bleibt die Quelle unverändert; vorhandene Zieldateien können aktualisiert werden.", "Choose folders. Copying leaves the source unchanged; existing target files may be updated.")
            color: "#aaaaaa"
            wrapMode: Text.WordWrap
            Layout.fillWidth: true
        }

        RowLayout {
            Layout.fillWidth: true

            ComboBox {
                id: diskBox

                Layout.fillWidth: true
                enabled: !(page.bridge && page.bridge.busy)
                // The entry must follow the scanned source. Setting the model resets the index, so the index is
                // restored one event-loop turn later, after every property this combo depends on has settled.
                function syncIndex() {
                    var wanted = page.disks.findIndex(function(d) { return d.device === page.plan.device; })
                    if (wanted >= 0 && currentIndex !== wanted) currentIndex = wanted
                }
                onModelChanged: Qt.callLater(syncIndex)
                onCountChanged: Qt.callLater(syncIndex)
                Component.onCompleted: Qt.callLater(syncIndex)
                Connections {
                    target: page
                    function onPlanChanged() { Qt.callLater(diskBox.syncIndex) }
                    function onDisksChanged() { Qt.callLater(diskBox.syncIndex) }
                }
                textRole: "display"
                model: page.disks.map(function(d) { return { device: d.device, display: (d.system || (d.filesystem === "ntfs" || d.filesystem === "bitlocker" ? "Windows" : "Linux")) + " — " + d.device + (d.label ? " (" + d.label + ")" : "") }; })
                onActivated: {
                    if (page.bridge) {
                        page.bridge.scan(page.disks[currentIndex].device);
                    }
                }
            }

            BusyIndicator {
                running: page.bridge && page.bridge.busy
                visible: running
                implicitWidth: 32
                implicitHeight: 32
            }

        }

        Rectangle {
            visible: !!page.disks && page.disks.length === 0 && !(page.bridge && (page.bridge.busy || page.bridge.error))
            color: "#2a2a2e"; border.color: "#555555"; radius: 8
            Layout.fillWidth: true; implicitHeight: noWindowsText.implicitHeight + 20
            Label { id: noWindowsText; anchors.fill: parent; anchors.margins: 10; color: "#cccccc"; wrapMode: Text.WordWrap
                text: page.tr("Keine geeignete Quelle gefunden. Es gibt nichts zu übernehmen; mit „Weiter“ geht es ohne Datenübernahme weiter.", "No suitable source found. There is nothing to bring over; click Next to continue without copying data.") }
        }

        Rectangle {
            visible: page.bridge && !!page.bridge.error && !/hibernation|Fast Startup|Schnellstart/i.test(page.bridge.error)
            color: "#432a22"
            border.color: "#fe6f2d"
            radius: 8
            Layout.fillWidth: true
            implicitHeight: errorText.implicitHeight + 20

            Label {
                id: errorText

                anchors.fill: parent
                anchors.margins: 10
                text: page.bridge ? page.bridge.error : ""
                color: "#ffd0bc"
                wrapMode: Text.WordWrap
            }

        }

        Rectangle {
            visible: page.hasWarning("handoff_invalid")
            color: "#382d22"; border.color: "#b8804b"; radius: 8
            Layout.fillWidth: true; implicitHeight: handoffError.implicitHeight + 20
            Label { id: handoffError; anchors.fill: parent; anchors.margins: 10; color: "#f3c99d"; wrapMode: Text.WordWrap
                text: page.tr("Windows-Vorauswahl konnte nicht gelesen werden. Ordner bitte selbst auswählen.", "Windows selection could not be read. Choose folders manually.") }
        }
        Rectangle {
            visible: page.hasWarning("hibernation_possible") || (page.bridge && page.bridge.error && /hibernation|Fast Startup|Schnellstart/i.test(page.bridge.error))
            color: "#382d22"
            border.color: "#b8804b"
            radius: 8
            Layout.fillWidth: true
            implicitHeight: hibernationText.implicitHeight + 20

            Label {
                id: hibernationText

                anchors.fill: parent
                anchors.margins: 10
                color: "#f3c99d"
                wrapMode: Text.WordWrap
                text: page.tr("Die Windows-Partition kann wegen Ruhezustand oder Schnellstart möglicherweise nicht gelesen werden. Starte Windows und wähle „Neu starten“ statt „Herunterfahren“. Alternativ schalte in Windows den Schnellstart aus. Starte danach erneut vom WinDoesNot-USB-Stick.", "The Windows partition may be unreadable because of hibernation or Fast Startup. Start Windows and choose Restart instead of Shut down. Alternatively, turn off Fast Startup in Windows. Then boot from the WinDoesNot USB stick again.")
            }

        }

        Rectangle {
            visible: page.hasWarning("bitlocker_locked")
            color: "#382d22"
            border.color: "#b8804b"
            radius: 8
            Layout.fillWidth: true
            implicitHeight: lockedText.implicitHeight + 20

            Label {
                id: lockedText

                anchors.fill: parent
                anchors.margins: 10
                color: "#f3c99d"
                wrapMode: Text.WordWrap
                text: page.tr("BitLocker ist gesperrt. Zum Lesen Passwort oder Wiederherstellungsschlüssel eingeben.", "BitLocker is locked. Enter a password or recovery key to read it.")
            }

        }

        Button {
            visible: page.hasWarning("bitlocker_locked")
            text: page.tr("BitLocker entsperren", "Unlock BitLocker")
            onClicked: unlockDialog.open()
        }

        Button {
            visible: page.hasWarning("luks_locked")
            text: page.tr("Verschlüsseltes Laufwerk entsperren", "Unlock encrypted drive")
            onClicked: luksDialog.open()
        }
        Rectangle {
            visible: !!page.plan.handoff
            Layout.fillWidth: true
            color: "#141414"
            border.color: "#fe6f2d"
            radius: 8
            implicitHeight: handoffText.implicitHeight + 20
            Label { id: handoffText; anchors.fill: parent; anchors.margins: 10; color: "#eeeeee"; wrapMode: Text.WordWrap; textFormat: Text.PlainText
                text: page.plan.handoff ? page.tr("Auswahl aus ", "Selection taken over from ") + page.systemName + ". " +
                    page.tr("WLAN-Exporte: ", "WLAN exports: ") + page.plan.handoff.wlan_exports +
                    (page.plan.handoff.chromium_passwords ? page.tr(" · Chromium-Passwortexport vorhanden", " · Chromium password export available") : "") : ""
            }
        }
        TextField {
            visible: !!page.plan.handoff && !!page.plan.handoff.chromium_envelope
            enabled: !page.skipped
            Layout.fillWidth: true
            echoMode: TextInput.Password
            placeholderText: page.tr("Passwort der Browser-Passwort-Hülle (optional)", "Browser password envelope password (optional)")
            onTextChanged: if (page.bridge) page.bridge.setEnvelopeSecret(text)
            onVisibleChanged: if (!visible) text = ""
        }
        CheckBox { visible: !!page.plan.handoff && page.plan.handoff.wlan_exports > 0
            enabled: !page.skipped
            checked: !!page.plan.handoff && page.plan.handoff.wlan_selected
            text: page.tr("Gespeicherte WLAN-Verbindungen übernehmen", "Import saved Wi-Fi connections")
            contentItem: Text { text: parent.text; font: parent.font; color: "#eeeeee"; verticalAlignment: Text.AlignVCenter; leftPadding: parent.indicator.width + parent.spacing }
            onToggled: if (page.bridge) page.bridge.setWlanSelected(checked)
        }
        Rectangle {
            Layout.fillWidth: true
            color: "#141414"
            border.color: "#3a3a3a"
            radius: 10
            implicitHeight: totals.implicitHeight + 24

            RowLayout {
                id: totals

                anchors.left: parent.left
                anchors.right: parent.right
                anchors.verticalCenter: parent.verticalCenter
                anchors.margins: 12

                Label {
                    text: page.tr("Auswahl: ", "Selected: ") + page.size(page.skipped ? 0 : page.selectedBytes)
                    color: "#fe6f2d"
                    font.bold: true
                }

                Item {
                    Layout.fillWidth: true
                }

                Label {
                    text: page.freeBytes < 0 ? page.tr("Freier Platz: noch unbekannt", "Free space: not yet known") : page.tr("Frei: ", "Free: ") + page.size(page.freeBytes)
                    color: page.freeBytes >= 0 && page.selectedBytes > page.freeBytes ? "#ff9d80" : "#aaaaaa"
                }

            }

        }

        ScrollView {
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true

            ColumnLayout {
                width: parent.width
                spacing: 12

                ColumnLayout {
                    visible: page.linux && !page.hasWarning("luks_locked")
                    Layout.fillWidth: true
                    Rectangle {
                        Layout.fillWidth: true; implicitHeight: linuxNotice.implicitHeight + 20
                        color: "#382d22"; border.color: "#b8804b"; radius: 8
                        Label { id: linuxNotice; anchors.fill: parent; anchors.margins: 10; wrapMode: Text.WordWrap; color: "#f3c99d"
                            text: page.tr("Eigene Desktop-Konfiguration (z. B. ~/.config/hypr) ersetzt nicht das WinDoesNot-Aussehen. Sie landet unter ~/Umzug-<Benutzer>/original/. Separate Dateisysteme werden möglicherweise nicht erfasst.", "Your desktop configuration (e.g. ~/.config/hypr) does not replace the WinDoesNot appearance. It is saved under ~/Umzug-<user>/original/. Separate filesystems may not be included.") }
                    }
                    Label { visible: !page.plan.package; Layout.fillWidth: true; wrapMode: Text.WordWrap; color: "#aaaaaa"; text: page.tr("Ein Quellbenutzer kann übernommen werden.", "One source user can be transferred.") }
                    Label { visible: !!page.plan.package; Layout.fillWidth: true; wrapMode: Text.WordWrap; color: "#aaaaaa"; text: page.tr("Umzugspaket gefunden. Hake an, was in das neue System soll; alles wird vor dem Einspielen auf Prüfsummen geprüft.", "Transfer package found. Tick what should go into the new system; everything is checked against its checksums before it is restored.") }
                    Repeater {
                        model: page.plan.package ? [] : (page.plan.users || [])
                        delegate: Rectangle {
                            Layout.fillWidth: true; implicitHeight: linuxUser.implicitHeight + 20; radius: 8; color: "#141414"; border.color: "#3a3a3a"
                            ColumnLayout { id: linuxUser; property var userData: modelData; property int userIndex: index; anchors.left: parent.left; anchors.right: parent.right; anchors.top: parent.top; anchors.margins: 10
                                Label { color: "#eeeeee"; font.bold: true; text: modelData.name + " · " + page.size(modelData.bytes) }
                                RadioButton { checked: !!modelData.selected; enabled: !page.skipped
                                    text: page.tr("Home (alles inklusive versteckter Dateien)", "Home (everything including hidden files)")
                                    contentItem: Text { text: parent.text; font: parent.font; color: "#eeeeee"; leftPadding: parent.indicator.width + parent.spacing; verticalAlignment: Text.AlignVCenter }
                                    onClicked: if (page.bridge) page.bridge.setLinuxUser(index, true)
                                }
                                Label { visible: modelData.warnings && modelData.warnings.length > 0; color: "#f3c99d"; text: (modelData.warnings || []).join(", ") }
                                Label { visible: !!modelData.selected && (modelData.folders || []).length > 0; color: "#aaaaaa"; Layout.fillWidth: true; wrapMode: Text.WordWrap
                                    text: page.tr("Große Ordner (abwählen, was auf der alten Platte bleiben soll):", "Large folders (untick what should stay on the old disk):") }
                                Repeater {
                                    model: linuxUser.userData.selected ? (linuxUser.userData.folders || []) : []
                                    delegate: CheckBox { enabled: !page.skipped; checked: (linuxUser.userData.exclude || []).indexOf(modelData.name) < 0
                                        text: modelData.name + " · " + page.size(modelData.bytes)
                                        contentItem: Text { text: parent.text; font: parent.font; color: "#eeeeee"; leftPadding: parent.indicator.width + parent.spacing; verticalAlignment: Text.AlignVCenter }
                                        onClicked: if (page.bridge) page.bridge.setHomeFolder(linuxUser.userIndex, modelData.name, checked)
                                    }
                                }
                            }
                        }
                    }
                    Label { visible: (page.plan.locations || []).length > 0; Layout.fillWidth: true; wrapMode: Text.WordWrap; color: "#aaaaaa"
                        text: page.plan.package ? page.tr("Inhalt des Pakets:", "Contents of the package:") : page.tr("Weitere Daten der alten Installation (landen am gleichen Ort):", "More data of the old installation (copied to the same place):") }
                    Repeater {
                        model: page.plan.locations || []
                        delegate: CheckBox { enabled: !page.skipped; checked: !!modelData.selected
                            text: modelData.label + (page.plan.package ? "" : " (" + modelData.path + ")") + " · " + page.size(modelData.bytes)
                            contentItem: Text { text: parent.text; font: parent.font; color: "#eeeeee"; wrapMode: Text.WordWrap; leftPadding: parent.indicator.width + parent.spacing; verticalAlignment: Text.AlignVCenter }
                            onClicked: if (page.bridge) page.bridge.setLinuxLocation(modelData.id, checked)
                        }
                    }
                    Repeater {
                        model: page.plan.package ? [] : [
                            { key: "wlan", label: page.tr("WLAN-Verbindungen", "Wi-Fi connections"), checked: !!page.plan.wlan_selected },
                            { key: "packages", label: page.tr("Pakete (explizit installierte Pakete nach dem ersten Start nachinstallieren)", "Packages (reinstall explicitly installed packages after first boot)"), checked: !!(page.plan.package_selection && page.plan.package_selection.arch_explicit) },
                            { key: "flatpak", label: page.tr("Flatpak-Apps", "Flatpak apps"), checked: !!(page.plan.package_selection && page.plan.package_selection.flatpak) }
                        ]
                        delegate: CheckBox { enabled: !page.skipped; checked: modelData.checked; text: modelData.label
                            contentItem: Text { text: parent.text; font: parent.font; color: "#eeeeee"; wrapMode: Text.WordWrap; leftPadding: parent.indicator.width + parent.spacing; verticalAlignment: Text.AlignVCenter }
                            onClicked: if (page.bridge) page.bridge.setLinuxGroup(modelData.key, checked)
                        }
                    }
                    CheckBox { visible: !page.plan.package; checked: true; enabled: false; text: page.tr("/etc als Referenzkopie (immer)", "/etc as reference copy (always)")
                        contentItem: Text { text: parent.text; font: parent.font; color: "#aaaaaa"; leftPadding: parent.indicator.width + parent.spacing; verticalAlignment: Text.AlignVCenter }
                    }
                    Label { visible: (page.plan.warnings || []).length > 0; Layout.fillWidth: true; wrapMode: Text.WordWrap; color: "#f3c99d"; text: page.tr("Hinweise: ", "Notes: ") + (page.plan.warnings || []).map(function(w) { return page.warningText(w); }).join("; ") }
                }

                Repeater {
                    model: page.plan.profiles || []

                    delegate: Rectangle {
                        property int profileIndex: index
                        property var profile: modelData

                        Layout.fillWidth: true
                        implicitHeight: profileContent.implicitHeight + 24
                        radius: 10
                        color: "#141414"
                        border.color: "#3a3a3a"

                        ColumnLayout {
                            id: profileContent

                            anchors.left: parent.left
                            anchors.right: parent.right
                            anchors.top: parent.top
                            anchors.margins: 12
                            spacing: 8

                            RowLayout {
                                Layout.fillWidth: true

                                Label {
                                    text: profile.name
                                    font.pixelSize: 16
                                    font.bold: true
                                    color: "#eeeeee"
                                }

                                Item {
                                    Layout.fillWidth: true
                                }

                                Label {
                                    text: page.size(profile.items.reduce(function(sum, item) {
                                        return sum + item.bytes;
                                    }, 0))
                                    color: "#aaaaaa"
                                }

                            }

                            Rectangle {
                                visible: profile.warnings && profile.warnings.indexOf("onedrive_files_may_be_online_only") >= 0
                                Layout.fillWidth: true
                                color: "#382d22"
                                radius: 6
                                implicitHeight: onedriveText.implicitHeight + 16

                                Label {
                                    id: onedriveText

                                    anchors.fill: parent
                                    anchors.margins: 8
                                    color: "#f3c99d"
                                    wrapMode: Text.WordWrap
                                    text: page.tr("OneDrive: Dateien, die nur in der Cloud liegen, können nicht übernommen werden.", "OneDrive: cloud-only files cannot be copied.")
                                }

                            }
                            Label { visible: profile.items.some(function(item) { return item.kind === "Thunderbird" })
                                Layout.fillWidth: true; wrapMode: Text.WordWrap
                                text: page.tr("Thunderbird schließen. Gespeicherte Passwörter werden übernommen; ein Hauptpasswort und die Entschlüsselung können nicht geprüft werden. Serverkonten lassen sich in Thunderbird über ‚Konto hinzufügen‘ neu einrichten.", "Close Thunderbird. Saved passwords are copied; a primary password and decryption cannot be checked. Server accounts can be set up again using Add Account.") }
                            Label { visible: profile.items.some(function(item) { return item.warnings.indexOf("thunderbird_unavailable") >= 0 })
                                Layout.fillWidth: true; color: "#f3c99d"; wrapMode: Text.WordWrap
                                text: page.tr("Thunderbird-Profil nicht bereit: Thunderbird unter Windows schließen und erneut prüfen.", "Thunderbird profile unavailable: close Thunderbird in Windows and scan again.") }
                            Label { Layout.fillWidth: true; wrapMode: Text.WordWrap
                                text: page.tr("Webmail und neues Outlook: Konto in Thunderbird erneut hinzufügen. OST-Dateien lassen sich nicht direkt übernehmen; Konto erneut verbinden oder in Outlook als PST exportieren. PST-Ergebnisse müssen gegebenenfalls in Thunderbird importiert werden.", "Webmail and new Outlook: add the account again in Thunderbird. OST files cannot be imported directly; reconnect the account or export a PST in Outlook. Converted PST mailboxes may need to be imported into Thunderbird.") }
                            Label { visible: profile.items.some(function(item) { return item.kind === "Firefox" })
                                wrapMode: Text.WordWrap; Layout.fillWidth: true
                                text: page.tr("Firefox schließen. Ein Hauptpasswort wird nicht erkannt; gespeicherte Passwörter und ihre Entschlüsselung sind nicht geprüft.", "Close Firefox. A primary password is not detected; saved passwords and their decryption have not been verified.") }
                            Label { visible: profile.items.some(function(item) { return item.warnings.indexOf("firefox_unavailable") >= 0 })
                                Layout.fillWidth: true; color: "#f3c99d"; wrapMode: Text.WordWrap
                                text: page.tr("Firefox-Profil nicht bereit: Firefox unter Windows schließen und erneut prüfen.", "Firefox profile unavailable: close Firefox in Windows and scan again.") }
                            Label { visible: profile.browsers && profile.browsers.length > 0
                                Layout.fillWidth: true; color: "#f3c99d"; wrapMode: Text.WordWrap
                                text: (profile.browsers || []).join(", ") + ": " + page.tr("Passwörter werden hier nicht übernommen und können nur unter Windows exportiert werden: Chrome- und Edge-Passwörter unter Windows im jeweiligen Browser als CSV exportieren und später dort importieren. Die CSV enthält Klartext; sicher verwahren und anschließend löschen.", "Passwords are not transferred here and can only be exported in Windows: export Chrome and Edge passwords as CSV in each browser on Windows and import them later. The CSV contains plaintext; store it securely and delete it afterwards.") }

                            Repeater {
                                model: profile.items

                                delegate: Rectangle {
                                    Layout.fillWidth: true
                                    implicitHeight: 42
                                    radius: 6
                                    color: "#202020"
                                    border.color: modelData.selected ? "#fe6f2d" : "#3a3a3a"

                                    CheckBox {
                                        anchors.fill: parent
                                        anchors.margins: 4
                                        checked: modelData.selected
                                        enabled: !page.skipped
                                        text: page.folderName(modelData.kind) + (modelData.warnings.length ? "  ⚠" : "")
                                        contentItem: Text { text: parent.text; font: parent.font; color: "#eeeeee"; verticalAlignment: Text.AlignVCenter; leftPadding: parent.indicator.width + parent.spacing }
                                        onToggled: {
                                            if (page.bridge) {
                                                page.bridge.setSelected(profileIndex, index, checked);
                                            }
                                        }
                                    }

                                    Label {
                                        anchors.right: parent.right
                                        anchors.rightMargin: 12
                                        anchors.verticalCenter: parent.verticalCenter
                                        text: page.size(modelData.bytes)
                                        color: "#aaaaaa"
                                    }

                                }

                            }

                        }

                    }

                }

            }

        }

        CheckBox {
            text: page.tr("Überspringen, keine Daten kopieren", "Skip, copy no data")
            contentItem: Text { text: parent.text; font: parent.font; color: "#eeeeee"; verticalAlignment: Text.AlignVCenter; leftPadding: parent.indicator.width + parent.spacing }
            checked: page.skipped
            onToggled: {
                page.skipped = checked;
                if (page.bridge)
                    page.bridge.setSkipped(checked);

            }
        }

    }

    Dialog {
        id: unlockDialog

        modal: true
        palette.windowText: "#eeeeee"
        palette.text: "#eeeeee"
        anchors.centerIn: parent
        width: Math.min(parent.width - 48, 490)
        title: page.tr("BitLocker entsperren", "Unlock BitLocker")
        standardButtons: Dialog.Ok | Dialog.Cancel
        background: Rectangle { color: "#202020"; border.color: "#3a3a3a"; radius: 10 }
        onAccepted: {
            if (secret.text && page.bridge)
                page.bridge.unlock(secret.text);

            secret.text = "";
        }
        onRejected: secret.text = ""

        ColumnLayout {
            anchors.fill: parent
            spacing: 10

            Label {
                Layout.fillWidth: true
                wrapMode: Text.WordWrap
                color: "#eeeeee"
                text: page.tr("Passwort ODER 48-stelligen Wiederherstellungsschlüssel eingeben. Den Schlüssel finden Sie im Microsoft-Konto unter account.microsoft.com/devices/recoverykey oder in Ihrem Ausdruck.", "Enter a password OR a 48-digit recovery key. Find the key in your Microsoft account at account.microsoft.com/devices/recoverykey or on your printout.")
            }

            TextField {
                id: secret

                Layout.fillWidth: true
                echoMode: TextInput.Password
                placeholderText: page.tr("Passwort oder Wiederherstellungsschlüssel", "Password or recovery key")
            }

        }

    }

    Dialog {
        id: luksDialog
        modal: true; anchors.centerIn: parent; width: Math.min(parent.width - 48, 490)
        title: page.tr("Verschlüsseltes Laufwerk entsperren", "Unlock encrypted drive")
        standardButtons: Dialog.Ok | Dialog.Cancel
        background: Rectangle { color: "#202020"; border.color: "#3a3a3a"; radius: 10 }
        onAccepted: { if (luksSecret.text && page.bridge) page.bridge.unlock(luksSecret.text); luksSecret.text = "" }
        onRejected: luksSecret.text = ""
        TextField { id: luksSecret; width: parent.width; echoMode: TextInput.Password
            placeholderText: page.tr("Passwort des verschlüsselten Laufwerks", "Encrypted drive password") }
    }

}
