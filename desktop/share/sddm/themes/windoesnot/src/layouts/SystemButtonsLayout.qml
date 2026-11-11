// qmllint disable unqualified

import QtQuick 2.15
import QtQuick.Layouts 1.15
import SddmComponents 2.0 as SDDM
import "../components/buttons"

RowLayout {
    id: systemButtons
    Layout.alignment: Qt.AlignHCenter
    Layout.preferredHeight: root.height / 8
    Layout.maximumHeight: root.height / 8

    property string a2: config.FormPosition
    Layout.leftMargin: 0

    spacing: root.font.pointSize * 5

    SDDM.TextConstants {
        id: textConstants
    }

    property var shutdown: [root.systemLocale.text("shutdown"), sddm.canPowerOff]
    property var restart: [root.systemLocale.text("reboot"), sddm.canReboot]
    property var sleep: [root.systemLocale.text("suspend"), sddm.canSuspend]

    Repeater {
        model: [systemButtons.shutdown, systemButtons.restart, systemButtons.sleep]

        SystemButton {
            text: modelData[0]
            idx: index
            visible: modelData[1]
        }
    }
}
