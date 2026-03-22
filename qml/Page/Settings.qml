pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls.FluentWinUI3

Rectangle {
    id: root

    readonly property bool isDark: Application.styleHints.colorScheme === Qt.ColorScheme.Dark
    readonly property color backgroundColor: isDark ? "#1c1c1c" : "#f9f9f9"

    color: backgroundColor

    Label {
        anchors.centerIn: parent
        text: qsTr("设置页面")
        font.pixelSize: 24
    }
}
