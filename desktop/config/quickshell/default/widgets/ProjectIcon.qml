pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Effects
import "../i18n" as UiI

Image {
    id: icon
    property string name: "info"
    // Light grey is made for the dark panels; in light mode the default is a dark grey so the icon stands out. The theme is read from
    // the nearest ancestor that knows it (darkMode / settingsMenu.darkMode); pass `color` to override.
    readonly property bool darkTheme: {
        var p = icon.parent
        while (p) {
            if (p.darkMode !== undefined) return p.darkMode
            if (p.settingsMenu && p.settingsMenu.darkMode !== undefined) return p.settingsMenu.darkMode
            p = p.parent
        }
        return true
    }
    property color color: darkTheme ? "#cccccc" : "#333333"
    property font font: Qt.font({pixelSize: UiI.UiScale.px(20)})
    width: font.pixelSize
    height: font.pixelSize
    source: Qt.resolvedUrl("../img/project/" + name + ".svg")
    sourceSize.width: Math.ceil(width * Screen.devicePixelRatio)
    sourceSize.height: Math.ceil(height * Screen.devicePixelRatio)
    fillMode: Image.PreserveAspectFit
    layer.enabled: true
    layer.effect: MultiEffect { colorization: 1; colorizationColor: icon.color }
}
