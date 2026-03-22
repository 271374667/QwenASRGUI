pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls.FluentWinUI3
import "./Component"
import "./Global"

ApplicationWindow {
    id: window
    width: 1480
    height: 920
    minimumWidth: 1180
    minimumHeight: 760
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
        minimizeIconSource: ImagePath.windowMinimize
        maximizeIconSource: ImagePath.windowMaximize
        restoreIconSource: ImagePath.windowRestore
        closeIconSource: ImagePath.windowClose
        z: 20
    }

    SidebarPageLayout {
        id: pageLayout
        anchors.fill: parent
        anchors.topMargin: titleBar.barHeight
        pageContext: ({
            "applicationService": applicationService,
            "settingsService": settingsService,
            "logService": logService,
            "transcriptionService": transcriptionService,
            "alignmentService": alignmentService
        })
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
