import QtQuick
Rectangle {
    color: "#202024"
    function onActivate() {}
    function onLeave() {}
    Column {
        anchors.centerIn: parent
        spacing: 24
        Image {
            source: "windoesnot-logo-hell.png"
            width: Math.min(480, parent.parent.width - 48)
            height: width * 459 / 2446
            sourceSize.width: 960
            fillMode: Image.PreserveAspectFit
            mipmap: true
            anchors.horizontalCenter: parent.horizontalCenter
        }
        Text { text: "Hyprland · Quickshell · CachyOS"; color: "#bbbbbb"; font.pixelSize: 16; anchors.horizontalCenter: parent.horizontalCenter }
    }
}
