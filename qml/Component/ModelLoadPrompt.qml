pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls.FluentWinUI3
import QtQuick.Layouts

Rectangle {
    id: root

    property string actionTitle: ""
    property string actionDescription: ""
    property var navigationHost: null

    signal loadRequested()

    readonly property bool isDark: Application.styleHints.colorScheme === Qt.ColorScheme.Dark
    readonly property color overlayColor: isDark ? "#9a000000" : "#72000000"
    readonly property color panelColor: isDark ? "#262626" : "#ffffff"
    readonly property color panelBorderColor: isDark ? "#404040" : "#d8d8d8"
    readonly property color titleColor: isDark ? "#f5f5f5" : "#202020"
    readonly property color bodyColor: isDark ? "#c8c8c8" : "#5c5c5c"

    anchors.fill: parent
    color: overlayColor
    visible: false
    opacity: visible ? 1 : 0
    z: 80

    function openPrompt() {
        root.visible = true
        root.forceActiveFocus()
    }

    function closePrompt() {
        root.visible = false
    }

    Behavior on opacity {
        NumberAnimation {
            duration: 160
            easing.type: Easing.OutCubic
        }
    }

    MouseArea {
        anchors.fill: parent
        onClicked: root.closePrompt()
    }

    Rectangle {
        id: panel
        width: Math.min(parent.width - 32, 460)
        radius: 16
        color: root.panelColor
        border.width: 1
        border.color: root.panelBorderColor
        anchors.centerIn: parent
        scale: root.visible ? 1 : 0.96

        Behavior on scale {
            NumberAnimation {
                duration: 180
                easing.type: Easing.OutCubic
            }
        }

        MouseArea {
            anchors.fill: parent
            onClicked: function(mouse) {
                mouse.accepted = true
            }
        }

        ColumnLayout {
            anchors.fill: parent
            anchors.margins: 20
            spacing: 16

            ColumnLayout {
                Layout.fillWidth: true
                spacing: 6

                Label {
                    Layout.fillWidth: true
                    text: root.actionTitle !== "" ? root.actionTitle : qsTr("需要先加载共享模型")
                    color: root.titleColor
                    font.pixelSize: 22
                    font.weight: Font.DemiBold
                    wrapMode: Text.WordWrap
                }

                Label {
                    Layout.fillWidth: true
                    text: root.actionDescription !== ""
                        ? root.actionDescription
                        : qsTr("当前操作依赖共享模型。你可以立即加载并继续，也可以前往设置页手动管理模型。")
                    color: root.bodyColor
                    wrapMode: Text.WordWrap
                    lineHeight: 1.25
                }
            }

            StatusChip {
                text: qsTr("共享模型按需加载")
                tone: "accent"
            }

            RowLayout {
                Layout.fillWidth: true
                spacing: 10

                Item {
                    Layout.fillWidth: true
                }

                Button {
                    text: qsTr("取消")
                    onClicked: root.closePrompt()
                }

                Button {
                    text: qsTr("前往设置")
                    onClicked: {
                        root.closePrompt()
                        if (root.navigationHost) {
                            root.navigationHost.navigateToPage("settings")
                        }
                    }
                }

                Button {
                    text: qsTr("加载并继续")
                    highlighted: true
                    onClicked: {
                        root.closePrompt()
                        root.loadRequested()
                    }
                }
            }
        }
    }

    Keys.onEscapePressed: root.closePrompt()
}
