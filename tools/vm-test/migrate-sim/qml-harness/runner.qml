import QtQuick
import QtQuick.Window
Window {
    visible: true; width: 1100; height: 1000
    QtObject {
        id: mock
        property string manifest: ""
        property string devices: "[]"
        property string error: ""
        property bool busy: false
        property bool german: false
        property real freeBytes: -1
        property string installChoice: "alongside"
    }
    Loader { id: loader; anchors.fill: parent; source: "../../../../iso/modules/windoesnotmigrate/main.qml"; onLoaded: item.bridge = mock }
    property int step: 0
    Timer {
        interval: 150; running: true; repeat: true
        onTriggered: {
            let plans = [
                {profiles:[{name:"Alice",items:[{kind:"Documents",bytes:1024,selected:true,warnings:[]}],warnings:[]}],warnings:[]},
                {kind:"linux",warnings:[],users:[{name:"Alice",bytes:3000,selected:true,folders:[{name:"Big",bytes:1000}],exclude:[],warnings:[]}],locations:[{id:"data",label:"Data",path:"/data",bytes:200,selected:true}]},
                {kind:"linux",package:"/tmp/package",warnings:[],users:[{name:"Alice",bytes:0,selected:true}],locations:[{id:"data",label:"Data",path:"/data",bytes:200,selected:true}]},
                {profiles:[],warnings:[]}, {profiles:[],warnings:[]}
            ]
            if (step === plans.length) { Qt.quit(); return }
            mock.devices = JSON.stringify(step < 3 ? [{device:"/dev/test",filesystem:step === 2 ? "package" : "ext4",label:"Test"}] : [])
            mock.error = step === 4 ? "Test failure" : ""
            mock.manifest = JSON.stringify(plans[step]); console.log("STATE", step); step++
        }
    }
}
