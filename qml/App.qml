pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls.FluentWinUI3
import QtQuick.Layouts
import "./Global"

// StackView 不被 FluentWinUI3 支持，需要单独导入
import QtQuick.Controls as Controls

ApplicationWindow {
    id: window
    width: 1280
    height: 720
    minimumWidth: 960
    minimumHeight: 540
    visible: true
    title: qsTr("QwenASR")

    // 主题检测
    readonly property bool isDark: Application.styleHints.colorScheme === Qt.ColorScheme.Dark

    // Fluent 设计色彩
    readonly property color accentColor: palette.accent
    readonly property color backgroundColor: isDark ? "#1c1c1c" : "#f9f9f9"
    readonly property color sideBarColor: isDark ? "#202020" : "#f3f3f3"
    readonly property color separatorColor: isDark ? "#3d3d3d" : "#e0e0e0"
    readonly property color hoverColor: isDark ? "#3d3d3d" : "#e5e5e5"
    readonly property color pressedColor: isDark ? "#4d4d4d" : "#d5d5d5"
    readonly property color selectedColor: isDark ? "#4d4d4d" : "#dcdcdc"
    readonly property color iconColor: isDark ? "#ffffff" : "#1a1a1a"

    // 当前选中的导航索引
    property int currentNavIndex: 0
    // 上一个选中的索引（用于动画方向判断）
    property int previousNavIndex: 0

    color: backgroundColor

    RowLayout {
        anchors.fill: parent
        spacing: 0

        // 侧边导航栏 - 使用固定宽度避免布局变化
        Item {
            id: sideBarContainer
            Layout.preferredWidth: 48
            Layout.minimumWidth: 48
            Layout.maximumWidth: 48
            Layout.fillHeight: true
            clip: true  // 防止内部元素溢出影响布局

            Rectangle {
                id: sideBar
                anchors.fill: parent
                color: sideBarColor
                clip: true  // 防止子元素溢出

                // 选中背景（放在按钮下层）
                Rectangle {
                    id: selectionBackground
                    width: 40
                    height: 40
                    radius: 6
                    color: selectedColor
                    x: (sideBar.width - width) / 2
                    z: 0

                    // 计算背景的 Y 位置
                    y: {
                        let targetBtn = getNavButton(currentNavIndex)
                        if (targetBtn) {
                            return targetBtn.y + navColumn.anchors.topMargin
                        }
                        return 8
                    }

                    Behavior on y {
                        NumberAnimation {
                            duration: 200
                            easing.type: Easing.OutCubic
                        }
                    }
                }

                // 导航按钮容器
                ColumnLayout {
                    id: navColumn
                    anchors.fill: parent
                    anchors.topMargin: 8
                    anchors.bottomMargin: 8
                    spacing: 4
                    z: 1

                    // 转录
                    NavButton {
                        id: navTranscribe
                        navIndex: 0
                        iconSource: ImagePath.mic
                        toolTipText: qsTr("转录")
                        onClicked: navigateTo(0, transcribePage)
                    }

                    // 对齐
                    NavButton {
                        id: navAlign
                        navIndex: 1
                        iconSource: ImagePath.timePicker
                        toolTipText: qsTr("对齐")
                        onClicked: navigateTo(1, alignPage)
                    }

                    // 日志
                    NavButton {
                        id: navLog
                        navIndex: 2
                        iconSource: ImagePath.log
                        toolTipText: qsTr("日志")
                        onClicked: navigateTo(2, logPage)
                    }

                    // 弹性空间
                    Item {
                        Layout.fillHeight: true
                    }

                    // 设置（底部）
                    NavButton {
                        id: navSettings
                        navIndex: 3
                        iconSource: ImagePath.settings
                        toolTipText: qsTr("设置")
                        onClicked: navigateTo(3, settingsPage)
                    }
                }

                // 选中指示器（放在最上层）
                Rectangle {
                    id: selectionIndicator
                    width: 3
                    height: 20
                    radius: 1.5
                    color: accentColor
                    x: 0
                    z: 2

                    y: {
                        let targetBtn = getNavButton(currentNavIndex)
                        if (targetBtn) {
                            return targetBtn.y + navColumn.anchors.topMargin + (targetBtn.height - height) / 2
                        }
                        return 8 + 12
                    }

                    Behavior on y {
                        NumberAnimation {
                            duration: 200
                            easing.type: Easing.OutCubic
                        }
                    }

                    // 高度动画 - Fluent 风格：快速收缩 + 柔和回弹
                    SequentialAnimation on height {
                        id: indicatorHeightAnim
                        running: false

                        NumberAnimation {
                            to: 32
                            duration: 180
                            easing.type: Easing.OutExpo
                        }

                        NumberAnimation {
                            to: 20
                            duration: 30
                            easing.type: Easing.OutExpo
                        }
                    }
                }
            }
        }

        // 分隔线
        Rectangle {
            Layout.preferredWidth: 1
            Layout.fillHeight: true
            color: separatorColor
        }

        // 主内容区域
        Controls.StackView {
            id: stackView
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true  // 防止页面滑动动画溢出影响布局
            initialItem: transcribePage

            replaceEnter: Transition {
                ParallelAnimation {
                    PropertyAnimation {
                        property: "opacity"
                        from: 0
                        to: 1
                        duration: 200
                        easing.type: Easing.OutCubic
                    }
                    PropertyAnimation {
                        property: "y"
                        from: (currentNavIndex > previousNavIndex) ? 30 : -30
                        to: 0
                        duration: 200
                        easing.type: Easing.OutCubic
                    }
                }
            }

            replaceExit: Transition {
                PropertyAnimation {
                    property: "opacity"
                    from: 1
                    to: 0
                    duration: 150
                    easing.type: Easing.InCubic
                }
            }
        }
    }

    // 导航函数
    function navigateTo(index: int, page: Component) {
        if (currentNavIndex !== index) {
            previousNavIndex = currentNavIndex
            currentNavIndex = index
            indicatorHeightAnim.restart()
            stackView.replace(null, page)
        }
    }

    // 获取导航按钮引用
    function getNavButton(index: int): Item {
        switch (index) {
            case 0: return navTranscribe
            case 1: return navAlign
            case 2: return navLog
            case 3: return navSettings
            default: return navTranscribe
        }
    }

    // 页面占位符 - 之后在 Pages 目录中实现
    Component {
        id: transcribePage
        Rectangle {
            color: window.backgroundColor
            Label {
                anchors.centerIn: parent
                text: qsTr("转录页面")
                font.pixelSize: 24
            }
        }
    }

    Component {
        id: alignPage
        Rectangle {
            color: window.backgroundColor
            Label {
                anchors.centerIn: parent
                text: qsTr("对齐页面")
                font.pixelSize: 24
            }
        }
    }

    Component {
        id: logPage
        Rectangle {
            color: window.backgroundColor
            Label {
                anchors.centerIn: parent
                text: qsTr("日志页面")
                font.pixelSize: 24
            }
        }
    }

    Component {
        id: settingsPage
        Rectangle {
            color: window.backgroundColor
            Label {
                anchors.centerIn: parent
                text: qsTr("设置页面")
                font.pixelSize: 24
            }
        }
    }

    // 自定义导航按钮组件（FluentWinUI3 风格）
    component NavButton: Item {
        id: navBtn
        Layout.preferredWidth: 40
        Layout.preferredHeight: 40
        Layout.minimumWidth: 40
        Layout.maximumWidth: 40
        Layout.minimumHeight: 40
        Layout.maximumHeight: 40
        Layout.alignment: Qt.AlignHCenter
        implicitWidth: 40
        implicitHeight: 40
        clip: true  // 防止缩放溢出影响布局

        required property int navIndex
        property string iconSource: ""
        property string toolTipText: ""
        readonly property bool isSelected: window.currentNavIndex === navIndex
        signal clicked()

        // 悬停/按下背景（选中时隐藏，由外部 selectionBackground 处理）
        Rectangle {
            id: hoverBackground
            anchors.fill: parent
            radius: 6
            color: {
                if (mouseArea.pressed) return pressedColor
                if (mouseArea.containsMouse) return hoverColor
                return "transparent"
            }
            visible: !navBtn.isSelected

        }

        // 图标容器（用于缩放动画）
        Item {
            id: iconContainer
            anchors.centerIn: parent
            width: 20
            height: 20

            // 缩放动画
            scale: navBtn.isSelected ? 1.3 : 1.0

            Behavior on scale {
                NumberAnimation {
                    duration: 150
                    easing.type: Easing.OutCubic
                }
            }

            // 图标 - 直接显示，使用较大的 sourceSize 保证清晰度
            Image {
                id: icon
                anchors.fill: parent
                source: navBtn.iconSource
                sourceSize: Qt.size(40, 40)  // 2x 尺寸确保高清
                fillMode: Image.PreserveAspectFit
                smooth: true
                antialiasing: true
                // 图标颜色保持一致，不随选中状态变化
            }
        }

        MouseArea {
            id: mouseArea
            anchors.fill: parent
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            onClicked: navBtn.clicked()
        }

        ToolTip {
            visible: mouseArea.containsMouse && !navBtn.isSelected
            text: navBtn.toolTipText
            delay: 500
            timeout: 3000
        }
    }
}
