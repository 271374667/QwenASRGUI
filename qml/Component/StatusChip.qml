pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls.FluentWinUI3

Rectangle {
    id: root

    property string text: ""
    property string tone: "neutral"

    readonly property bool isDark: Application.styleHints.colorScheme === Qt.ColorScheme.Dark
    readonly property color backgroundTone: {
        switch (root.tone) {
            case "success": return isDark ? "#163b23" : "#dff6e5"
            case "warning": return isDark ? "#4d3a12" : "#fff4ce"
            case "danger": return isDark ? "#4b1d1b" : "#fde7e9"
            case "accent": return isDark ? "#12324a" : "#dbeafe"
            default: return isDark ? "#313131" : "#ededed"
        }
    }
    readonly property color foregroundTone: {
        switch (root.tone) {
            case "success": return isDark ? "#92f2b8" : "#185c37"
            case "warning": return isDark ? "#ffd98a" : "#8a5a00"
            case "danger": return isDark ? "#ffb3b3" : "#a4262c"
            case "accent": return isDark ? "#9cd4ff" : "#005a9e"
            default: return isDark ? "#d0d0d0" : "#5c5c5c"
        }
    }

    radius: 999
    color: backgroundTone
    implicitHeight: 28
    implicitWidth: chipLabel.implicitWidth + 18

    Label {
        id: chipLabel
        anchors.centerIn: parent
        text: root.text
        color: root.foregroundTone
        font.pixelSize: 12
        font.weight: Font.Medium
    }
}
