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
    flags: Qt.Window | Qt.FramelessWindowHint
    visible: true
    title: qsTr("QwenASR")
    color: pageLayout.backgroundColor

    FluentTitleBar {
        id: titleBar
        anchors.fill: parent
        window: window
        logoSource: ImagePath.logo
        appName: window.title
        minimizeIconSource: Qt.resolvedUrl("Images/WindowMinimize.svg")
        maximizeIconSource: Qt.resolvedUrl("Images/WindowMaximize.svg")
        restoreIconSource: Qt.resolvedUrl("Images/WindowRestore.svg")
        closeIconSource: Qt.resolvedUrl("Images/WindowClose.svg")
        z: 20
    }

    SidebarPageLayout {
        id: pageLayout
        anchors.fill: parent
        anchors.topMargin: titleBar.barHeight
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
