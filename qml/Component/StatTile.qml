pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls.FluentWinUI3
import QtQuick.Layouts

Rectangle {
    id: root

    property string label: ""
    property string value: ""
    property string hint: ""

    readonly property bool isDark: Application.styleHints.colorScheme === Qt.ColorScheme.Dark
    readonly property color cardColor: isDark ? "#1f1f1f" : "#fafafa"
    readonly property color borderColor: isDark ? "#343434" : "#e3e3e3"
    readonly property color labelColor: isDark ? "#b3b3b3" : "#6a6a6a"
    readonly property color valueColor: isDark ? "#f5f5f5" : "#202020"

    radius: 12
    color: cardColor
    border.width: 1
    border.color: borderColor
    Layout.fillWidth: true
    Layout.preferredHeight: 108

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 14
        spacing: 8

        Label {
            text: root.label
            color: root.labelColor
            font.pixelSize: 12
        }

        Label {
            text: root.value
            color: root.valueColor
            font.pixelSize: 24
            font.weight: Font.DemiBold
            Layout.fillWidth: true
            elide: Text.ElideRight
        }

        Label {
            visible: root.hint !== ""
            text: root.hint
            color: root.labelColor
            wrapMode: Text.WordWrap
            font.pixelSize: 11
            Layout.fillWidth: true
        }
    }
}
