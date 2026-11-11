import QtQuick
Rectangle {
    color: "#181a1c"
    function onActivate() {}
    function onLeave() {}
    Column {
        anchors.centerIn: parent
        spacing: 28
        Image {
            source: "windoesnot-logo-hell.png"
            width: Math.min(440, parent.parent.width - 64)
            height: width * 459 / 2446
            fillMode: Image.PreserveAspectFit
            anchors.horizontalCenter: parent.horizontalCenter
        }
        Text {
            text: "WinDoesNotMac"
            color: "#f4f1eb"
            font.pixelSize: 24
            anchors.horizontalCenter: parent.horizontalCenter
        }
    }
}
