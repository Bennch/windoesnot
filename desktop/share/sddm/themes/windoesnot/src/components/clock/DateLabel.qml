import QtQuick 2.15

Text {
    id: dateDisplay
    anchors.horizontalCenter: parent.horizontalCenter

    property var rootItem: null
    property var config: ({})
    readonly property var cfg: config || ({})
    readonly property int basePt: (rootItem && rootItem.font && rootItem.font.pointSize) ? rootItem.font.pointSize : 13
    readonly property string baseFamily: (rootItem && rootItem.font && rootItem.font.family) ? rootItem.font.family : (cfg.Font && cfg.Font !== "" ? cfg.Font : dateDisplay.font.family)

    color: cfg.DateTextColor || "#ffffff"

    font {
        pointSize: basePt * 2
        weight: Font.Medium
        family: baseFamily
    }

    renderType: Text.QtRendering
    horizontalAlignment: Text.AlignHCenter

    function refreshDisplay() {
        const today = new Date();
        text = today.toLocaleDateString(rootItem && rootItem.systemLocale ? rootItem.systemLocale.locale : Qt.locale(), Locale.LongFormat);
    }

    Component.onCompleted: refreshDisplay()
}
