pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls.FluentWinUI3
import QtQuick.Layouts
import "../Global"

Rectangle {
    id: root

    // 主题检测
    readonly property bool isDark: Application.styleHints.colorScheme === Qt.ColorScheme.Dark

    // 颜色定义
    readonly property color backgroundColor: isDark ? "#1c1c1c" : "#f9f9f9"
    readonly property color cardColor: isDark ? "#2d2d2d" : "#ffffff"
    readonly property color borderColor: isDark ? "#3d3d3d" : "#e0e0e0"
    readonly property color textColor: isDark ? "#ffffff" : "#1a1a1a"
    readonly property color textSecondaryColor: isDark ? "#a0a0a0" : "#666666"
    readonly property color dropZoneColor: isDark ? "#252525" : "#fafafa"
    readonly property color dropZoneHoverColor: isDark ? "#333333" : "#f0f0f0"
    readonly property color accentColor: palette.accent

    // 状态属性
    property string modelName: "Qwen2-Audio-7B"
    property string taskStatus: "idle"  // idle, loading, transcribing, completed, error
    property real progress: 0.0
    property string currentFile: ""
    property bool isTranscribing: false

    color: backgroundColor

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 24
        spacing: 20

        // 顶部状态栏
        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: 60
            radius: 8
            color: cardColor
            border.width: 1
            border.color: borderColor

            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: 16
                anchors.rightMargin: 16
                spacing: 16

                // 模型信息
                RowLayout {
                    spacing: 8

                    Image {
                        source: ImagePath.cpu
                        sourceSize: Qt.size(40, 40)
                        Layout.preferredWidth: 20
                        Layout.preferredHeight: 20
                    }

                    Label {
                        text: qsTr("当前模型:")
                        color: textSecondaryColor
                        font.pixelSize: 13
                    }

                    Label {
                        text: root.modelName
                        color: textColor
                        font.pixelSize: 13
                        font.weight: Font.Medium
                    }
                }

                // 分隔线
                Rectangle {
                    Layout.preferredWidth: 1
                    Layout.preferredHeight: 24
                    color: borderColor
                }

                // 任务状态
                RowLayout {
                    spacing: 8

                    Rectangle {
                        width: 8
                        height: 8
                        radius: 4
                        color: {
                            switch (root.taskStatus) {
                                case "idle": return textSecondaryColor
                                case "loading": return "#f59e0b"
                                case "transcribing": return accentColor
                                case "completed": return "#22c55e"
                                case "error": return "#ef4444"
                                default: return textSecondaryColor
                            }
                        }
                    }

                    Label {
                        text: {
                            switch (root.taskStatus) {
                                case "idle": return qsTr("就绪")
                                case "loading": return qsTr("加载中")
                                case "transcribing": return qsTr("转录中")
                                case "completed": return qsTr("已完成")
                                case "error": return qsTr("错误")
                                default: return qsTr("未知")
                            }
                        }
                        color: textColor
                        font.pixelSize: 13
                    }
                }

                Item { Layout.fillWidth: true }

                // 当前文件
                Label {
                    visible: root.currentFile !== ""
                    text: root.currentFile
                    color: textSecondaryColor
                    font.pixelSize: 12
                    elide: Text.ElideMiddle
                    Layout.maximumWidth: 300
                }
            }
        }

        // 进度条区域
        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: 48
            radius: 8
            color: cardColor
            border.width: 1
            border.color: borderColor
            visible: root.isTranscribing || root.taskStatus === "completed"

            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: 16
                anchors.rightMargin: 16
                spacing: 12

                ProgressBar {
                    id: progressBar
                    Layout.fillWidth: true
                    from: 0
                    to: 1
                    value: root.progress
                }

                Label {
                    text: Math.round(root.progress * 100) + "%"
                    color: textColor
                    font.pixelSize: 13
                    font.weight: Font.Medium
                    Layout.preferredWidth: 45
                    horizontalAlignment: Text.AlignRight
                }
            }
        }

        // 文件拖放区域
        Rectangle {
            id: dropZone
            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.minimumHeight: 200
            radius: 12
            color: dropArea.containsDrag ? dropZoneHoverColor : dropZoneColor
            border.width: 2
            border.color: dropArea.containsDrag ? accentColor : borderColor

            Behavior on color {
                ColorAnimation { duration: 150; easing.type: Easing.OutCubic }
            }

            Behavior on border.color {
                ColorAnimation { duration: 150; easing.type: Easing.OutCubic }
            }

            DropArea {
                id: dropArea
                anchors.fill: parent

                onDropped: function(drop) {
                    if (drop.hasUrls) {
                        let url = drop.urls[0]
                        root.currentFile = url.toString().replace("file:///", "")
                        root.taskStatus = "idle"
                        console.log("File dropped:", root.currentFile)
                    }
                }
            }

            ColumnLayout {
                anchors.centerIn: parent
                spacing: 16

                // 上传图标
                Rectangle {
                    Layout.alignment: Qt.AlignHCenter
                    width: 64
                    height: 64
                    radius: 32
                    color: isDark ? "#3d3d3d" : "#e5e5e5"

                    Image {
                        anchors.centerIn: parent
                        source: ImagePath.upload
                        sourceSize: Qt.size(64, 64)
                        width: 32
                        height: 32
                    }
                }

                // 提示文字
                Label {
                    Layout.alignment: Qt.AlignHCenter
                    text: qsTr("拖放音频或视频文件到此处")
                    color: textColor
                    font.pixelSize: 16
                    font.weight: Font.Medium
                }

                Label {
                    Layout.alignment: Qt.AlignHCenter
                    text: qsTr("支持 MP3, WAV, FLAC, MP4, MKV, AVI 等格式")
                    color: textSecondaryColor
                    font.pixelSize: 13
                }

                // 或者分隔线
                RowLayout {
                    Layout.alignment: Qt.AlignHCenter
                    spacing: 12

                    Rectangle {
                        Layout.preferredWidth: 60
                        height: 1
                        color: borderColor
                    }

                    Label {
                        text: qsTr("或者")
                        color: textSecondaryColor
                        font.pixelSize: 12
                    }

                    Rectangle {
                        Layout.preferredWidth: 60
                        height: 1
                        color: borderColor
                    }
                }

                // 选择文件按钮
                Button {
                    Layout.alignment: Qt.AlignHCenter
                    text: qsTr("选择文件")
                    icon.source: ImagePath.upload
                    onClicked: {
                        // TODO: 打开文件选择对话框
                        console.log("Open file dialog")
                    }
                }
            }
        }

        // 控制按钮区域
        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: 72
            radius: 8
            color: cardColor
            border.width: 1
            border.color: borderColor

            RowLayout {
                anchors.centerIn: parent
                spacing: 16

                // 开始转录按钮
                Button {
                    id: startButton
                    text: qsTr("开始转录")
                    icon.source: ImagePath.play
                    enabled: root.currentFile !== "" && !root.isTranscribing
                    highlighted: true

                    onClicked: {
                        root.isTranscribing = true
                        root.taskStatus = "transcribing"
                        root.progress = 0
                        console.log("Start transcription:", root.currentFile)
                    }
                }

                // 停止转录按钮
                Button {
                    id: stopButton
                    text: qsTr("停止转录")
                    icon.source: ImagePath.stop
                    enabled: root.isTranscribing

                    onClicked: {
                        root.isTranscribing = false
                        root.taskStatus = "idle"
                        root.progress = 0
                        console.log("Stop transcription")
                    }
                }
            }
        }
    }
}
