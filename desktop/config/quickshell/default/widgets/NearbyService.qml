import QtQuick
import Quickshell.Io

Item {
    id: service
    visible: false
    property bool autoStart: true
    property var state: ({receiving:false, requestedReceiving:false, devices:[], selected:[], incoming:null, outgoing:null, history:[], error:""})
    property var pendingCommands: []
    signal incomingRequest()
    property string lastRequest: ""

    function command(data) {
        if (!worker.running) {
            pendingCommands = pendingCommands.concat([data])
            return
        }
        worker.write(JSON.stringify(data) + "\n")
    }
    function acceptState(data) {
        state = data
        if (data.incoming && data.incoming.status === "waiting" && data.incoming.id !== lastRequest) {
            lastRequest = data.incoming.id
            incomingRequest()
        }
    }
    Process {
        id: worker
        command: ["windoesnot-nearby", "serve"]
        running: service.autoStart
        stdinEnabled: true
        stdout: SplitParser {
            onRead: data => {
                try { service.acceptState(JSON.parse(data)) } catch (error) {}
            }
        }
        onRunningChanged: {
            if (running) {
                for (let data of service.pendingCommands) worker.write(JSON.stringify(data) + "\n")
                service.pendingCommands = []
            }
        }
        onExited: {
            service.acceptState({receiving:false, requestedReceiving:false, devices:[], selected:[], incoming:null, outgoing:null, history:[], error:"service"})
        }
    }
}
