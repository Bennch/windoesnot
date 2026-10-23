import QtQuick
import QtQuick.Layouts
import "calendar_layout.js" as CalendarLayout
import "../i18n/Lang.js" as Lang

Item {
    id: calendarWidget
    width: 320
    height: 360

    property int monthShift: 0
    property var viewingDate: CalendarLayout.getDateInXMonthsTime(monthShift)
    property var calendarLayout: CalendarLayout.getCalendarLayout(viewingDate, monthShift === 0)
    property color accentColor: "#FE6F2D"
    property int borderRadius: 10
    property bool darkMode: true
    property string uiLanguage: "de"
    property var hoveredDate: null

    Timer {
        id: clearHoverTimer
        interval: 40
        repeat: false
        onTriggered: calendarWidget.hoveredDate = null
    }

    clip: true

    Rectangle {
        anchors.fill: parent
        color: darkMode ? Qt.rgba(0.125, 0.125, 0.125, 0.93) : Qt.rgba(0.95, 0.95, 0.95, 0.97)
        border.color: darkMode ? "#3a3a3f" : "#c0c0c0"
        border.width: 1
        topLeftRadius: borderRadius
        topRightRadius: borderRadius
        bottomLeftRadius: 0
        bottomRightRadius: 0
    }

    Column {
        anchors.fill: parent
        anchors.margins: 15
        spacing: 10

        // ── Header ────────────────────────────────────────────────────────
        Row {
            width: parent.width
            height: 35
            spacing: 5

            Rectangle {
                width: parent.width - 80
                height: 35
                radius: 6
                color: monthResetArea.containsMouse ? (darkMode ? "#2a2a2a" : "#e0e0e0") : "transparent"

                Text {
                    anchors.centerIn: parent
                    text: {
                        var locale = Qt.locale(Lang.get("calendar.locale", uiLanguage))
                        var dayNames = Lang.get("calendar.dayNames", uiLanguage)
                        if (hoveredDate) {
                            var full = hoveredDate.toLocaleDateString(locale, "d. MMMM yyyy")
                            return dayNames[hoveredDate.getDay()] + ", " + full
                        }
                        if (monthShift !== 0) return "• " + viewingDate.toLocaleDateString(locale, "MMMM yyyy")
                        var full = viewingDate.toLocaleDateString(locale, "d. MMMM yyyy")
                        return dayNames[viewingDate.getDay()] + ", " + full
                    }
                    font.pixelSize: 14
                    font.bold: true
                    color: darkMode ? "#fff" : "#1a1a1a"
                }

                MouseArea {
                    id: monthResetArea
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    enabled: monthShift !== 0
                    onClicked: monthShift = 0
                }
            }

            Item { width: 1; height: 1 }

            Rectangle {
                width: 35; height: 35; radius: 17.5
                color: prevArea.containsMouse ? (darkMode ? "#2a2a2a" : "#e0e0e0") : "transparent"
                Text { anchors.centerIn: parent; text: "‹"; font.pixelSize: 20; color: darkMode ? "#fff" : "#1a1a1a" }
                MouseArea { id: prevArea; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: monthShift-- }
            }

            Rectangle {
                width: 35; height: 35; radius: 17.5
                color: nextArea.containsMouse ? (darkMode ? "#2a2a2a" : "#e0e0e0") : "transparent"
                Text { anchors.centerIn: parent; text: "›"; font.pixelSize: 20; color: darkMode ? "#fff" : "#1a1a1a" }
                MouseArea { id: nextArea; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: monthShift++ }
            }
        }

        // ── Weekday header ────────────────────────────────────────────────
        Row {
            width: parent.width
            height: 30
            spacing: (parent.width - 7 * 38) / 6

            Repeater {
                model: 7
                delegate: Rectangle {
                    width: 38; height: 30
                    color: "transparent"
                    Text {
                        anchors.centerIn: parent
                        text: (Lang.get("calendar.weekDays", uiLanguage))[index]
                        font.pixelSize: 11
                        font.bold: true
                        color: darkMode ? "#999" : "#666"
                    }
                }
            }
        }

        // ── Calendar grid ─────────────────────────────────────────────────
        Column {
            width: parent.width
            spacing: 5

            Repeater {
                model: 6
                delegate: Row {
                    width: parent.width
                    height: 38
                    spacing: (parent.width - 7 * 38) / 6

                    property int weekIndex: index

                    Repeater {
                        model: 7
                        delegate: Rectangle {
                            width: 38; height: 38
                            radius: 6

                            property var dayData: calendarWidget.calendarLayout && calendarWidget.calendarLayout[weekIndex]
                                                  ? calendarWidget.calendarLayout[weekIndex][index] : null
                            property bool isToday: dayData ? dayData.today === 1 : false
                            property bool isCurrentMonth: dayData ? dayData.today >= 0 : false
                            property bool hovered: false

                            color: {
                                if (isToday) return calendarWidget.accentColor
                                if (hovered && isCurrentMonth) return darkMode ? "#2a2a2a" : "#e0e0e0"
                                return "transparent"
                            }

                            Behavior on color { ColorAnimation { duration: 150 } }

                            Text {
                                anchors.centerIn: parent
                                text: dayData ? dayData.day : ""
                                font.pixelSize: 13
                                font.bold: isToday
                                color: {
                                    if (isToday) return "#fff"
                                    if (isCurrentMonth) return darkMode ? "#ccc" : "#1a1a1a"
                                    return darkMode ? "#555" : "#aaa"
                                }
                            }

                            MouseArea {
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: isCurrentMonth ? Qt.PointingHandCursor : Qt.ArrowCursor
                                onEntered: {
                                    clearHoverTimer.stop()
                                    parent.hovered = true
                                    if (dayData && isCurrentMonth) {
                                        var vd = calendarWidget.viewingDate
                                        calendarWidget.hoveredDate = new Date(vd.getFullYear(), vd.getMonth(), dayData.day)
                                    }
                                }
                                onExited: {
                                    parent.hovered = false
                                    clearHoverTimer.restart()
                                }
                            }
                        }
                    }
                }
            }
        }
    }

    // Wheel-only — clicks pass through
    MouseArea {
        anchors.fill: parent
        acceptedButtons: Qt.NoButton
        propagateComposedEvents: true
        onWheel: function(event) {
            if (event.angleDelta.y > 0) monthShift--
            else if (event.angleDelta.y < 0) monthShift++
        }
    }
}
