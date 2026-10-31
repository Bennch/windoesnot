// qmllint disable unqualified
import QtQuick 2.15
import QtQuick.Layouts 1.15
import QtQuick.Controls 2.15
import SddmComponents 2.0 as SDDM

import "components/clock"
import "components/inputs"
import "components/buttons"
import "layouts"
import "effects"
import "ui"

Pane {
    id: root
    readonly property var systemLocale: greeterLocale
    SystemLocale { id: greeterLocale }
    height: Screen.height
    width: Screen.width
    padding: 0

    readonly property var cfg: (typeof config !== "undefined" && config) ? config : ({})
    readonly property string formPos: String(cfg.FormPosition || "center")
    readonly property var sddmApi: (typeof sddm !== "undefined" && sddm) ? sddm : null
    readonly property color startupColor: (cfg.StartupBackgroundColor && cfg.StartupBackgroundColor !== "") ? cfg.StartupBackgroundColor : "#000000"

    // SDDM creates one instance of this theme per physical screen. Only the
    // screen X11/RandR calls "primary" (set to match Hyprland's main monitor
    // by the greeter's Xsetup script) should offer the login form; the rest
    // just show the background. Falls open to "show the form" whenever the
    // screen model isn't available (e.g. a single-screen setup, or an older
    // SDDM), which is today's behavior on every screen.
    readonly property bool isPrimaryScreen: {
        if (typeof screenModel === "undefined" || !screenModel)
            return true;
        try {
            var primaryGeometry = screenModel.geometry(screenModel.primary);
            return !!primaryGeometry && Screen.virtualX === primaryGeometry.x && Screen.virtualY === primaryGeometry.y;
        } catch (e) {
            return true;
        }
    }

    LayoutMirroring.enabled: false
    LayoutMirroring.childrenInherit: true

    palette.buttonText: cfg.HoverSystemButtonsIconsColor || "#ffffff"

    background: Rectangle {
        color: root.startupColor
    }

    font {
        family: cfg.Font || font.family
        pointSize: (cfg.FontSize !== "" && typeof cfg.FontSize !== "undefined") ? parseInt(cfg.FontSize) : (parseInt(height / 80) || 13)
        weight: Font.Medium
    }

    focus: true

    // SDDM's own greeter view re-asserts focus on the root item after the
    // theme finishes loading, which can steal it back from the password
    // field's static `focus: true`. Grab it again once the event loop
    // settles, and keep a fallback so the very first Tab/Return/Space the
    // user presses always lands somewhere useful instead of being dropped.
    function focusLoginField() {
        if (typeof userModel !== "undefined" && userModel && userModel.count > 0) {
            passwordInput.password.forceActiveFocus();
        } else {
            usernameInput.username.forceActiveFocus();
        }
    }

    Component.onCompleted: {
        if (root.isPrimaryScreen)
            Qt.callLater(focusLoginField);
    }

    Keys.onPressed: function (event) {
        if (!root.isPrimaryScreen)
            return;
        if (usernameInput.username.activeFocus || passwordInput.password.activeFocus)
            return;

        if (event.key === Qt.Key_Tab || event.key === Qt.Key_Backtab || event.key === Qt.Key_Return || event.key === Qt.Key_Enter || event.key === Qt.Key_Space) {
            root.focusLoginField();
            event.accepted = true;
        }
    }

    Item {
        id: fxVisual
        anchors.fill: parent

        Background {
            id: bg
            config: root.cfg
            fallbackColor: root.startupColor
        }

        BlurEffect {
            id: blurOverlay
            sourceItem: bg.imageItem
            config: root.cfg
        }

        Rectangle {
            id: formBackground
            anchors.fill: form
            anchors.centerIn: form
            z: 0.9
            color: root.cfg.FormBackgroundColor || "transparent"
            visible: false
            opacity: 1
        }

        ColumnLayout {
            id: form
            z: 1
            visible: root.isPrimaryScreen

            anchors.top: parent.top
            anchors.bottom: parent.bottom
            y: parent.height * 0.003

            width: parent.width / 2.5

            x: {
                if (root.formPos === "left")
                    return 0;
                if (root.formPos === "right")
                    return parent.width - width;
                return (parent.width - width) / 2;
            }

            SDDM.TextConstants {
                id: textConstants
            }

            // WinDoesNot wordmark above the clock
            Image {
                Layout.alignment: Qt.AlignHCenter
                Layout.topMargin: root.font.pointSize * 3
                Layout.preferredHeight: root.font.pointSize * 3.2
                Layout.preferredWidth: root.font.pointSize * 3.2 * 5.33
                source: "../img/windoesnot-logo.png"
                fillMode: Image.PreserveAspectFit
                smooth: true
                mipmap: true
                visible: root.cfg.ShowLogo !== "false"
            }

            Clock {
                rootItem: root
                config: root.cfg
            }

            Item {
                Layout.preferredHeight: root.font.pointSize * 1
            }

            Column {
                id: inputContainer
                Layout.alignment: Qt.AlignHCenter
                Layout.preferredHeight: -1
                Layout.leftMargin: 0
                Layout.fillWidth: true
                spacing: UiTokens.spacing_xs

                UsernameInput {
                    id: usernameInput
                    nextDown: passwordInput.password
                }

                PasswordField {
                    id: passwordInput
                    nextDown: loginButton.authenticateBtn
                }

                LoginButton {
                    id: loginButton
                    usernameField: usernameInput.username
                    passwordField: passwordInput.password
                    environmentIndex: environmentButton.currentIndex
                }

                Connections {
                    target: root.sddmApi
                    function onLoginSucceeded() {
                    }
                    function onLoginFailed() {
                    }
                }
            }

            SystemButtonsLayout {}

            Item {
                Layout.preferredHeight: root.font.pointSize * 0.5
            }

            EnvironmentButton {
                id: environmentButton
            }
        }

        MouseArea {
            anchors.fill: parent
            onClicked: parent.forceActiveFocus()
        }
    }
}
