import QtQuick
import "." as Tools
import "../i18n/Lang.js" as Lang

Column {
    id: page
    property var settingsMenu: null
    property int section: 0
    width: parent.width
    height: sectionTabs.height + spacing + sectionLoader.height
    spacing: 18

    Row {
        id: sectionTabs
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

    Loader {
        id: sectionLoader
        width: parent.width
        height: item ? item.height : 0
        sourceComponent: page.section === 0 ? accountPage : page.section === 1 ? maintenancePage : kernelPage
    }

    readonly property bool busy: sectionLoader.item && sectionLoader.item.busy === true
    readonly property var activeSection: sectionLoader.item

    Component { id: accountPage; Tools.AccountCategory { width: page.width; settingsMenu: page.settingsMenu } }
    Component { id: maintenancePage; Tools.MaintenanceCategory { width: page.width; settingsMenu: page.settingsMenu } }
    Component { id: kernelPage; Tools.KernelCategory { width: page.width; settingsMenu: page.settingsMenu } }

    function tr(key) { return Lang.get(key, settingsMenu ? settingsMenu.uiLanguage : "de") }
}
