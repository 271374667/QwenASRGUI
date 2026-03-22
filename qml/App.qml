pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls.FluentWinUI3
import "./Component"
import "./Global"

ApplicationWindow {
    id: window
    width: 1280
    height: 720
    minimumWidth: 960
    minimumHeight: 540
    visible: true
    title: qsTr("QwenASR")
    color: pageLayout.backgroundColor

    SidebarPageLayout {
        id: pageLayout
        anchors.fill: parent
        pages: [
            {
                "name": qsTr("转录"),
                "iconSource": ImagePath.mic,
                "qmlPath": Qt.resolvedUrl("Page/Transcription.qml")
            },
            {
                "name": qsTr("对齐"),
                "iconSource": ImagePath.timePicker,
                "qmlPath": Qt.resolvedUrl("Page/Align.qml")
            },
            {
                "name": qsTr("日志"),
                "iconSource": ImagePath.log,
                "qmlPath": Qt.resolvedUrl("Page/Log.qml")
            },
            {
                "name": qsTr("设置"),
                "iconSource": ImagePath.settings,
                "qmlPath": Qt.resolvedUrl("Page/Settings.qml"),
                "section": "bottom"
            }
        ]
    }
}
