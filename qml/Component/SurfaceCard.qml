pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls.FluentWinUI3
import QtQuick.Layouts

Rectangle {
    id: root

    property string title: ""
    property string subtitle: ""
    default property alias contentData: contentColumn.data

    readonly property bool isDark: Application.styleHints.colorScheme === Qt.ColorScheme.Dark
    readonly property color cardColor: isDark ? "#242424" : "#ffffff"
    readonly property color borderColor: isDark ? "#3b3b3b" : "#dcdcdc"
    readonly property color titleColor: isDark ? "#f5f5f5" : "#202020"
    readonly property color subtitleColor: isDark ? "#b0b0b0" : "#666666"

    radius: 14
    color: cardColor
    border.width: 1
    border.color: borderColor
    implicitHeight: contentLayout.implicitHeight + 32

    ColumnLayout {
        id: contentLayout
        anchors.fill: parent
        anchors.margins: 16
        spacing: 14

        ColumnLayout {
            visible: root.title !== "" || root.subtitle !== ""
            spacing: 4
            Layout.fillWidth: true

            Label {
                visible: root.title !== ""
                text: root.title
                color: root.titleColor
                font.pixelSize: 18
                font.weight: Font.DemiBold
            }

            Label {
                visible: root.subtitle !== ""
                text: root.subtitle
                color: root.subtitleColor
                wrapMode: Text.WordWrap
                font.pixelSize: 12
            }
        }

        ColumnLayout {
            id: contentColumn
            spacing: 12
            Layout.fillWidth: true
        }
    }
}
