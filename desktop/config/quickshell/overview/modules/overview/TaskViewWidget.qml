import QtQuick
import Quickshell
import Quickshell.Hyprland
import "../../common"
import "../../services"

// Windows-style task view: live windows above, desktops below.
Item {
    id: root
    required property var panelWindow
    readonly property HyprlandMonitor monitor: Hyprland.monitorFor(panelWindow.screen)
    readonly property int workspaceId: monitor?.activeWorkspace?.id ?? 1
    readonly property var byAddress: HyprlandData.windowByAddress
    readonly property var windows: ToplevelManager.toplevels.values.filter(t => {
        const w = byAddress[`0x${t.HyprlandToplevel.address}`]
        return w && w.workspace?.id === workspaceId && !w.hidden
    })
    readonly property var desktops: HyprlandData.workspaceIds.filter(id => id >= 1).sort((a, b) => a - b)
    implicitWidth: panelWindow.screen.width
    implicitHeight: panelWindow.screen.height
    Rectangle { anchors.fill: parent; color: "#d916171b" }
    Flow {
        anchors { left: parent.left; right: parent.right; top: parent.top; bottom: strip.top; margins: 72; bottomMargin: 36; topMargin: 94 }
        spacing: 26
        Repeater { model: root.windows
            delegate: Item {
                id: card
                required property var modelData
                readonly property var client: root.byAddress[`0x${modelData.HyprlandToplevel.address}`]
                width: Math.min(420, Math.max(240, (client?.size?.[0] ?? 800) * .3))
                height: Math.min(292, Math.max(174, (client?.size?.[1] ?? 600) * .3 + 31))
                Rectangle { anchors.fill: parent; radius: 10; color: mouse.containsMouse ? "#ee25262a" : "#e91c1d20"; border.width: mouse.containsMouse ? 2 : 1; border.color: mouse.containsMouse ? WinDoesNotTheme.accentColor : "#554f5259"
                    Row { x: 12; y: 8; spacing: 8; width: parent.width - 25; height: 18
                        Image { width: 16; height: 16; source: "image://icon/" + (DesktopEntries.heuristicLookup(card.client?.class)?.icon ?? ""); fillMode: Image.PreserveAspectFit }
                        Text { width: parent.width - 24; text: card.client?.title ?? "Fenster"; color: "#f3f3f3"; font.pixelSize: 12; elide: Text.ElideRight }
                    }
                    ScreencopyView { anchors { left: parent.left; right: parent.right; top: parent.top; bottom: parent.bottom; margins: 7; topMargin: 31 }; captureSource: modelData; live: true; layer.enabled: true; layer.smooth: true }
                }
                MouseArea { id: mouse; anchors.fill: parent; hoverEnabled: true; onClicked: { GlobalStates.overviewOpen = false; HyprlandData.dispatch(`focuswindow address:${card.client?.address}`) } }
            }
        }
    }
    Rectangle { id: strip; anchors { left: parent.left; right: parent.right; bottom: parent.bottom }; height: 188; color: "#e9141519"
        Row { anchors.centerIn: parent; spacing: 16
            Repeater { model: root.desktops
                delegate: Column { required property var modelData; spacing: 7
                    Rectangle { width: 208; height: 117; radius: 9; color: "#e727282e"; border.width: modelData === root.workspaceId ? 2 : 1; border.color: modelData === root.workspaceId ? WinDoesNotTheme.accentColor : "#443f4148"; Text { anchors.centerIn: parent; text: modelData; font.pixelSize: 32; color: "#667f828a" }; MouseArea { anchors.fill: parent; onClicked: HyprlandData.dispatch(`workspace ${modelData}`) } }
                    Text { width: 208; horizontalAlignment: Text.AlignHCenter; text: "Desktop " + modelData; color: "#eeeeee"; font.pixelSize: 13 }
                }
            }
            Column { spacing: 7
                Rectangle { width: 208; height: 117; radius: 9; color: "#e727282e"; Text { anchors.centerIn: parent; text: "+"; font.pixelSize: 34; color: "#f2f2f2" }; MouseArea { anchors.fill: parent; onClicked: HyprlandData.dispatch("workspace empty") } }
                Text { width: 208; horizontalAlignment: Text.AlignHCenter; text: "Neuer Desktop"; color: "#eeeeee"; font.pixelSize: 13 }
            }
        }
    }
}
