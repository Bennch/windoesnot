import QtQuick

Item {
    id: orb
    property string style: "classic"
    property string customSource: ""
    readonly property url classicSource: Qt.resolvedUrl("../img/start-here.svg")
    readonly property url selectedSource: style === "dot"
        ? Qt.resolvedUrl("../img/brand/windoesnot-icon-128.png")
        : style === "custom" && customSource !== "" ? customSource : classicSource
    width: 40
    height: 40

    Image {
        id: selected
        anchors.fill: parent
        source: orb.selectedSource
        sourceSize.width: Math.ceil(orb.width * Screen.devicePixelRatio)
        sourceSize.height: Math.ceil(orb.height * Screen.devicePixelRatio)
        fillMode: Image.PreserveAspectFit
        smooth: true
        mipmap: true
        visible: status === Image.Ready
    }
    Image {
        anchors.fill: parent
        source: orb.classicSource
        sourceSize.width: Math.ceil(orb.width * Screen.devicePixelRatio)
        sourceSize.height: Math.ceil(orb.height * Screen.devicePixelRatio)
        fillMode: Image.PreserveAspectFit
        smooth: true
        mipmap: true
        visible: selected.status !== Image.Ready
    }
}
