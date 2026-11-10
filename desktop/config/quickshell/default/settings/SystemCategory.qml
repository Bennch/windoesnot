import QtQuick
import "." as Tools
import "../i18n/Lang.js" as Lang

Column {
    id: page
    property var settingsMenu: null
    property int section: 0
    readonly property bool busy: maintenanceSection.busy || kernelSection.busy
    width: parent.width
    spacing: 18

    Row {
        width: parent.width
        spacing: 8
        Repeater {
            model: [page.tr("system.account"), page.tr("system.maintenance"), page.tr("system.kernel")]
            delegate: Tools.SystemToolsButton {
                required property int index
                required property string modelData
                settingsMenu: page.settingsMenu
                width: (page.width - 16) / 3
                text: modelData
                primary: page.section === index
                onClicked: page.section = index
            }
        }
    }

    Tools.AccountCategory {
        width: parent.width
        visible: page.section === 0
        settingsMenu: page.settingsMenu
    }
    Tools.MaintenanceCategory {
        id: maintenanceSection
        width: parent.width
        visible: page.section === 1
        settingsMenu: page.settingsMenu
    }
    Tools.KernelCategory {
        id: kernelSection
        width: parent.width
        visible: page.section === 2
        settingsMenu: page.settingsMenu
    }

    function tr(key) { return Lang.get(key, settingsMenu ? settingsMenu.uiLanguage : "de") }
}
