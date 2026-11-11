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
    property bool skipped: false
    property real freeBytes: bridge && bridge.freeBytes !== undefined ? bridge.freeBytes : -1
    property real selectedBytes: {
        var sum = 0;
        for (var p of plan.profiles || []) for (var item of p.items || []) if (item.selected) {
            sum += item.bytes;
        }
        return sum;
    }

    function tr(de, en) {
        return german ? de : en;
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
            "Firefox": "Firefox"
        };
        return german ? (names[kind] || kind) : kind;
    }

    function hasWarning(code) {
        return plan.warnings && plan.warnings.indexOf(code) >= 0;
    }

    color: "#202020"

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 24
        spacing: 12

        Label {
            text: page.tr("Windows-Daten übernehmen", "Bring your Windows data")
            font.pixelSize: 24
            font.bold: true
            color: "#eeeeee"
        }

        Label {
            text: page.tr("Ordner auswählen. Windows bleibt unverändert; vorhandene Zieldateien können aktualisiert werden.", "Choose folders. Windows stays unchanged; existing target files may be updated.")
            color: "#aaaaaa"
            wrapMode: Text.WordWrap
            Layout.fillWidth: true
        }

        RowLayout {
            Layout.fillWidth: true

            ComboBox {
                id: diskBox

                Layout.fillWidth: true
                model: page.disks
                textRole: "device"
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
                text: page.tr("Keine Windows-Installation gefunden. Es gibt nichts zu übernehmen; mit „Weiter“ geht es ohne Datenübernahme weiter.", "No Windows installation found. There is nothing to bring over; click Next to continue without copying data.") }
        }

        Rectangle {
            visible: page.bridge && !!page.bridge.error
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
                text: page.tr("Ruhezustand / Schnellstart: Windows vollständig herunterfahren und Schnellstart deaktivieren, falls Dateien nicht gelesen werden können.", "Hibernation / Fast Startup: Shut down Windows fully and disable Fast Startup if files cannot be read.")
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

        Rectangle {
            visible: !!page.plan.handoff
            Layout.fillWidth: true
            color: "#141414"
            border.color: "#fe6f2d"
            radius: 8
            implicitHeight: handoffText.implicitHeight + 20
            Label { id: handoffText; anchors.fill: parent; anchors.margins: 10; color: "#eeeeee"; wrapMode: Text.WordWrap; textFormat: Text.PlainText
                text: page.plan.handoff ? page.tr("Windows-Vorauswahl übernommen (", "Windows selection loaded (") + page.plan.handoff.windows_version + "). " +
                    page.tr("WLAN-Exporte: ", "WLAN exports: ") + page.plan.handoff.wlan_exports +
                    (page.plan.handoff.chromium_passwords ? page.tr(" · Chromium-Passwortexport vorhanden", " · Chromium password export available") : "") : ""
            }
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
                            Label { visible: profile.items.some(function(item) { return item.warnings.indexOf("firefox_unavailable") >= 0 })
                                Layout.fillWidth: true; color: "#f3c99d"; wrapMode: Text.WordWrap
                                text: page.tr("Firefox-Profil nicht bereit: Firefox unter Windows schließen und erneut prüfen.", "Firefox profile unavailable: close Firefox in Windows and scan again.") }
                            Label { visible: profile.browsers && profile.browsers.length > 0
                                Layout.fillWidth: true; color: "#f3c99d"; wrapMode: Text.WordWrap
                                text: (profile.browsers || []).join(", ") + ": " + page.tr("Passwörter werden hier nicht übernommen und können nur unter Windows exportiert werden: Das geht separat mit unserem Umzugsprogramm „WinDoesNot Setup“ für Windows. Browserprofile werden nicht kopiert.", "Passwords are not transferred here and can only be exported in Windows: use our separate migration program “WinDoesNot Setup” for Windows. Browser profiles are not copied.") }

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

}
