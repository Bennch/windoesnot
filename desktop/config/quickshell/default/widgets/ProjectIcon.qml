pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Effects

Image {
    id: icon
    property string name: "info"
    property color color: "#cccccc"
    property font font: Qt.font({pixelSize: 20})
    width: font.pixelSize
    height: font.pixelSize
    source: Qt.resolvedUrl("../img/project/" + name + ".svg")
    sourceSize.width: Math.ceil(width * Screen.devicePixelRatio)
    sourceSize.height: Math.ceil(height * Screen.devicePixelRatio)
    fillMode: Image.PreserveAspectFit
    layer.enabled: true
    layer.effect: MultiEffect { colorization: 1; colorizationColor: icon.color }
}
