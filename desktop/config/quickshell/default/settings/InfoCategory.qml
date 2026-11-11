import QtQuick
import "." as Tools
import "../i18n/Lang.js" as Lang

Column {
    id: page
    property var settingsMenu: null
    property int section: 0
    width: parent.width
    spacing: 18

    Row {
        width: parent.width
        spacing: 8
        Repeater {
            model: [page.tr("info.about"), page.tr("info.help")]
            delegate: Tools.SystemToolsButton {
                required property int index
                required property string modelData
                width: (page.width - 8) / 2
                settingsMenu: page.settingsMenu
                text: modelData
                primary: page.section === index
                onClicked: page.section = index
            }
        }
    }
    Tools.AboutCategory {
        width: parent.width
        visible: page.section === 0
        settingsMenu: page.settingsMenu
    }
    Tools.HelpCategory {
        width: parent.width
        visible: page.section === 1
        settingsMenu: page.settingsMenu
    }
    function tr(key) { return Lang.get(key, settingsMenu ? settingsMenu.uiLanguage : "de") }
}
