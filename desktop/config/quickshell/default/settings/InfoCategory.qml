import QtQuick
import "." as Tools

Column {
    id: page
    property var settingsMenu: null
    width: parent.width
    spacing: 30

    Tools.AboutCategory {
        width: parent.width
        settingsMenu: page.settingsMenu
    }

    Rectangle {
        width: parent.width
        height: 1
        color: page.settingsMenu && page.settingsMenu.darkMode ? "#3a3a3a" : "#d0d0d0"
    }

    Tools.HelpCategory {
        width: parent.width
        settingsMenu: page.settingsMenu
    }
}
