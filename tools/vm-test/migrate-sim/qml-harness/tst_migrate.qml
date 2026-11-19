import QtQuick
import QtQuick.Controls
import QtTest

TestCase {
    id: test
    name: "MigratePage"
    width: 1100; height: 1000
    visible: true
    when: windowShown
    property string shots: Qt.resolvedUrl("../../../../out/migrate-sim/qml-shots/").toString().replace("file://", "")
    QtObject {
        id: mock
        property string manifest: ""
        property string devices: "[]"
        property string error: ""
        property bool busy: false
        property bool german: false
        property real freeBytes: -1
        property string installChoice: "alongside"
        property var calls: []
        function record() { calls.push(Array.from(arguments)) }
        function discover() { record("discover") }
        function scan(x) { record("scan", x) }
        function setLinuxLocation(x,y) { record("location",x,y) }
        function setHomeFolder(x,y,z) { record("folder",x,y,z) }
        function connectShare(x,y,z) { record("share",x,y,z) }
        function setLinuxUser(x,y) { record("user",x,y) }
        function setLinuxGroup(x,y) { record("group",x,y) }
        function setSkipped(x) { record("skip",x) }
        function setSelected(x,y,z) { record("selected",x,y,z) }
    }
    Loader { id: loader; anchors.fill: parent; source: "../../../../iso/modules/windoesnotmigrate/main.qml"; onLoaded: item.bridge = mock }
    function findText(root, text) {
        if (!root) return null
        if (root.text !== undefined && root.text === text && root.visible && root.enabled !== undefined) return root
        let children = root.children || []
        for (let c of children) { let v=findText(c,text); if (v) return v }
        return null
    }
    function placeholder(root, text) {
        if (!root) return null
        if (root.placeholderText === text) return root
        for (let c of (root.children || [])) { let v=placeholder(c,text); if(v) return v }
        return null
    }
    function shot(name) {
        let done=false
        verify(loader.item.grabToImage(function(result) { verify(result.saveToFile(shots + name + ".png")); done=true }))
        tryVerify(function() { return done }, 5000)
    }
    function setup(plan, devices, error) {
        mock.calls=[]; mock.error=error || ""; mock.devices=JSON.stringify(devices || []); mock.manifest=JSON.stringify(plan); wait(200)
    }
    function clickText(text) { let x=findText(loader.item,text); verify(x !== null, "Missing visible control: "+text); if(x) mouseClick(x) }
    function test_states() {
        setup({profiles:[{name:"Alice",items:[{kind:"Documents",bytes:1024,selected:true,warnings:[]}],warnings:[],browsers:[]}],warnings:[]},[{device:"/dev/test",filesystem:"ntfs"}]); shot("windows")
        let linux={kind:"linux",device:"/dev/test",system:"CachyOS",warnings:[],users:[{name:"Alice",bytes:3000,selected:true,folders:[{name:"Big",bytes:1000}],exclude:[],warnings:[]}],locations:[{id:"data",label:"Data",path:"/data",bytes:200,selected:true}],wlan_selected:true,package_selection:{arch_explicit:true,flatpak:true}}
        setup(linux,[{device:"/dev/test",filesystem:"ext4"}]); shot("linux")
        clickText("Big · 1000 B"); clickText("Data (/data) · 200 B")
        compare(JSON.stringify(mock.calls[0]), JSON.stringify(["folder",0,"Big",false]))
        compare(JSON.stringify(mock.calls[1]), JSON.stringify(["location","data",false]))
        let p=placeholder(loader.item,"smb://nas/umzug"); verify(p !== null); verify(!p.visible)
        clickText("Network share (SMB) …"); verify(p.visible); p.text="smb://nas/share"; shot("linux-smb")
        clickText("Connect and search"); compare(JSON.stringify(mock.calls[2]),JSON.stringify(["share","smb://nas/share","",""]))
        clickText("Search again"); compare(JSON.stringify(mock.calls[3]),JSON.stringify(["discover"]))
        linux.package="/tmp/package"; linux.users[0].bytes=0
        setup(linux,[{device:"package:/tmp/package",filesystem:"package",label:"Test package"}]); shot("package")
        verify(findText(loader.item,"Home (everything including hidden files)") === null)
        verify(findText(loader.item,"Wi-Fi connections") === null)
        verify(findText(loader.item,"Data · 200 B") !== null)
        setup({profiles:[],warnings:[]},[]); shot("no-disk")
        verify(findText(loader.item,"No suitable source found. There is nothing to bring over; click Next to continue without copying data.") !== null)
        setup({profiles:[],warnings:[]},[],"Test failure"); shot("error")
        verify(findText(loader.item,"Test failure") !== null)
    }
    function test_windows_missing_optional_browsers() {
        setup({profiles:[{name:"Alice",items:[],warnings:[]}],warnings:[]},[{device:"/dev/test",filesystem:"ntfs"}])
    }

}
