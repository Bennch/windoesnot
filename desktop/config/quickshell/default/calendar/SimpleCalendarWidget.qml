import QtQuick
import QtQuick.Layouts
import QtQuick.Controls
import "calendar_layout.js" as CalendarLayout
import "Holidays.js" as Holidays
import "../i18n/Lang.js" as Lang
import "../i18n" as UiI

Item {
    id: calendarWidget
    width: 320
    height: 360

    property int monthShift: 0
    property var viewingDate: CalendarLayout.getDateInXMonthsTime(monthShift)
    property var calendarLayout: CalendarLayout.getCalendarLayout(viewingDate, monthShift === 0, firstDay)
    property var weekNumbers: CalendarLayout.getWeekNumbers(viewingDate, firstDay)
    property color accentColor: "#FE6F2D"
    property int borderRadius: 10
    property bool darkMode: true
    property string uiLanguage: "de"
    property var hoveredDate: null
    // Public holidays and well-known days of the system's region (German UI without a known region: Germany).
    property bool holidaysEnabled: true
    property string regionSetting: "auto"
    property string holidayState: "ALL"
    property bool showRegional: true
    property bool showObservances: true
    property bool showWeekNumbers: false
    property string firstDaySetting: "auto"
    // Monday-based index of the first weekday: 0 Monday, 5 Saturday, 6 Sunday. Automatic: Sunday in the US, otherwise Monday.
    readonly property int firstDay: firstDaySetting === "sun" ? 6 : firstDaySetting === "sat" ? 5 : firstDaySetting === "mon" ? 0 : (region === "US" ? 6 : 0)
    property string region: regionSetting !== "auto" ? regionSetting : Holidays.regionFor(Qt.locale().name, uiLanguage)
    property var holidayMap: holidaysEnabled
        ? Holidays.holidays(viewingDate.getFullYear(), region, { state: holidayState, regional: showRegional, observances: showObservances })
        : ({})
    // Narrower cells make room for the week number column (KW) on the left.
    readonly property int cellW: showWeekNumbers ? 33 : 38
    readonly property int cols: showWeekNumbers ? 8 : 7

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
                    width: parent.width - 12
                    horizontalAlignment: Text.AlignHCenter
                    fontSizeMode: Text.Shrink
                    minimumPixelSize: 10
                    font.pixelSize: UiI.UiScale.px(14)
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
                Text { anchors.centerIn: parent; text: "‹"; font.pixelSize: UiI.UiScale.px(20); color: darkMode ? "#fff" : "#1a1a1a" }
                MouseArea { id: prevArea; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: monthShift-- }
            }

            Rectangle {
                width: 35; height: 35; radius: 17.5
                color: nextArea.containsMouse ? (darkMode ? "#2a2a2a" : "#e0e0e0") : "transparent"
                Text { anchors.centerIn: parent; text: "›"; font.pixelSize: UiI.UiScale.px(20); color: darkMode ? "#fff" : "#1a1a1a" }
                MouseArea { id: nextArea; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: monthShift++ }
            }
        }

        // ── Weekday header ────────────────────────────────────────────────
        Row {
            width: parent.width
            height: 30
            spacing: (parent.width - calendarWidget.cols * calendarWidget.cellW) / (calendarWidget.cols - 1)

            Rectangle {
                visible: calendarWidget.showWeekNumbers
                width: calendarWidget.cellW; height: 30
                color: "transparent"
                Text {
                    anchors.centerIn: parent
                    text: Lang.get("calendar.weekShort", uiLanguage)
                    font.pixelSize: UiI.UiScale.px(10)
                    color: darkMode ? "#777" : "#999"
                }
            }

            Repeater {
                model: 7
                delegate: Rectangle {
                    width: calendarWidget.cellW; height: 30
                    color: "transparent"
                    Text {
                        anchors.centerIn: parent
                        text: (Lang.get("calendar.weekDays", uiLanguage))[(index + calendarWidget.firstDay) % 7]
                        font.pixelSize: UiI.UiScale.px(11)
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
                    spacing: (parent.width - calendarWidget.cols * calendarWidget.cellW) / (calendarWidget.cols - 1)

                    property int weekIndex: index

                    // ISO week number of this row
                    Item {
                        visible: calendarWidget.showWeekNumbers
                        width: calendarWidget.cellW; height: 38
                        Text {
                            anchors.centerIn: parent
                            text: calendarWidget.weekNumbers[weekIndex] !== undefined ? calendarWidget.weekNumbers[weekIndex] : ""
                            font.pixelSize: UiI.UiScale.px(11)
                            color: darkMode ? "#6f6f6f" : "#9a9a9a"
                        }
                    }

                    Repeater {
                        model: 7
                        delegate: Rectangle {
                            width: calendarWidget.cellW; height: 38
                            radius: 6

                            property var dayData: calendarWidget.calendarLayout && calendarWidget.calendarLayout[weekIndex]
                                                  ? calendarWidget.calendarLayout[weekIndex][index] : null
                            property bool isToday: dayData ? dayData.today === 1 : false
                            property bool isCurrentMonth: dayData ? dayData.today >= 0 : false
                            property bool hovered: false
                            // Holiday of this day (current month only): { de, en, kind } or null
                            property var holiday: (dayData && isCurrentMonth)
                                ? Holidays.lookup(calendarWidget.holidayMap, new Date(calendarWidget.viewingDate.getFullYear(), calendarWidget.viewingDate.getMonth(), dayData.day))
                                : null
                            readonly property color softAccent: Qt.rgba(calendarWidget.accentColor.r, calendarWidget.accentColor.g, calendarWidget.accentColor.b, 0.11)

                            color: {
                                if (isToday) return calendarWidget.accentColor
                                if (hovered && isCurrentMonth) return darkMode ? "#2a2a2a" : "#e0e0e0"
                                if (holiday && holiday.kind === "public") return softAccent
                                return "transparent"
                            }

                            // A small dot: filled = day off, ring = only in some regions, grey = well-known day
                            Rectangle {
                                visible: holiday !== null
                                anchors.horizontalCenter: parent.horizontalCenter
                                anchors.bottom: parent.bottom
                                anchors.bottomMargin: 4
                                width: 4; height: 4; radius: 2
                                color: !holiday ? "transparent"
                                       : holiday.kind === "observance" ? (darkMode ? "#88888866" : "#99999966")
                                       : holiday.kind === "regional" ? "transparent"
                                       : (isToday ? "#ffffffcc" : calendarWidget.accentColor)
                                border.width: holiday && holiday.kind === "regional" ? 1 : 0
                                border.color: isToday ? "#ffffffcc" : calendarWidget.accentColor
                                opacity: holiday && holiday.kind === "public" ? 0.9 : 0.75
                            }

                            ToolTip {
                                id: holidayTip
                                visible: parent.hovered && holiday !== null
                                delay: 150
                                text: holiday ? (uiLanguage === "de" ? holiday.de : holiday.en)
                                                + (holiday.kind === "regional" ? (uiLanguage === "de" ? " · in einigen Regionen" : " · some regions") : "")
                                              : ""
                                contentItem: Text {
                                    text: holidayTip.text
                                    font.pixelSize: UiI.UiScale.px(12)
                                    color: darkMode ? "#f0f0f0" : "#1a1a1a"
                                }
                                background: Rectangle {
                                    radius: 6
                                    color: darkMode ? "#2d2d30" : "#ffffff"
                                    border.width: 1
                                    border.color: darkMode ? "#4a4a4f" : "#c8c8c8"
                                }
                            }

                            Behavior on color { ColorAnimation { duration: 150 } }

                            Text {
                                anchors.centerIn: parent
                                text: dayData ? dayData.day : ""
                                font.pixelSize: UiI.UiScale.px(13)
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
