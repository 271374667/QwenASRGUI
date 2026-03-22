pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls.FluentWinUI3
import QtQuick.Layouts
import "../Component"
import "../Global"

Rectangle {
    id: root

    property var applicationService
    property var settingsService
    property var logService
    property var transcriptionService
    property var alignmentService

    readonly property bool isDark: Application.styleHints.colorScheme === Qt.ColorScheme.Dark
    readonly property color backgroundColor: isDark ? "#1c1c1c" : "#f6f6f6"
    readonly property color textColor: isDark ? "#f5f5f5" : "#202020"
    readonly property color secondaryTextColor: isDark ? "#b3b3b3" : "#6b6b6b"
    readonly property color dropColor: isDark ? "#202020" : "#fcfcfc"
    readonly property color dropBorderColor: isDark ? "#393939" : "#d7d7d7"
    readonly property color accentColor: palette.accent

    color: backgroundColor

    function statusTone(statusText) {
        if (statusText === "就绪") return "success"
        if (statusText === "加载中" || statusText === "处理中") return "warning"
        if (statusText === "错误") return "danger"
        return "neutral"
    }

    ScrollView {
        id: scrollView
        anchors.fill: parent
        clip: true

        PageScrollContent {
            width: scrollView.availableWidth
            spacing: 24

            SurfaceCard {
                Layout.fillWidth: true
                title: qsTr("语音转录")
                subtitle: qsTr("共享模型加载后，可将音频或视频文件转为全文文本与 SRT 字幕。")

                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 12

                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 10

                        StatusChip {
                            text: transcriptionService.state.modelStatusText
                            tone: root.statusTone(transcriptionService.state.modelStatusText)
                        }

                        Label {
                            text: transcriptionService.state.modelName + " · " + transcriptionService.state.modelDetails
                            color: root.secondaryTextColor
                            Layout.fillWidth: true
                            elide: Text.ElideRight
                        }
                    }

                    Flow {
                        Layout.fillWidth: true
                        spacing: 10

                        Button {
                            text: qsTr("加载模型")
                            enabled: transcriptionService.state.canLoadModel
                            onClicked: transcriptionService.load_model()
                        }

                        Button {
                            text: qsTr("重载模型")
                            enabled: transcriptionService.state.canReloadModel
                            onClicked: transcriptionService.reload_model()
                        }

                        Button {
                            text: qsTr("卸载")
                            enabled: transcriptionService.state.canUnloadModel
                            onClicked: transcriptionService.unload_model()
                        }

                        Button {
                            text: qsTr("强制停止")
                            enabled: transcriptionService.state.canCancelTask
                            onClicked: transcriptionService.cancel_current_task()
                        }
                    }
                }

                ProgressBar {
                    visible: transcriptionService.state.isLoadingModel
                    Layout.fillWidth: true
                    from: 0
                    to: 100
                    value: transcriptionService.state.loadingProgress
                }

                GridLayout {
                    Layout.fillWidth: true
                    columns: width >= 1120 ? 3 : 1
                    rowSpacing: 14
                    columnSpacing: 14

                    StatTile {
                        label: qsTr("当前任务")
                        value: transcriptionService.state.taskStatusText
                        hint: qsTr("共享模型与当前文件的运行状态")
                    }

                    StatTile {
                        label: qsTr("字幕行数")
                        value: String(transcriptionService.state.subtitleLineCount)
                        hint: qsTr("聚合后的字幕条目数量")
                    }

                    StatTile {
                        label: qsTr("原始时间戳")
                        value: String(transcriptionService.state.timestampCount)
                        hint: qsTr("词级时间戳数量")
                    }
                }
            }

            GridLayout {
                Layout.fillWidth: true
                columns: width >= 1320 ? 2 : 1
                rowSpacing: 24
                columnSpacing: 24

                SurfaceCard {
                    Layout.fillWidth: true
                    title: qsTr("输入文件")
                    subtitle: qsTr("支持拖放和文件对话框选择。")

                    Rectangle {
                        id: dropZone
                        Layout.fillWidth: true
                        Layout.preferredHeight: 240
                        radius: 16
                        color: dropArea.containsDrag ? Qt.darker(root.dropColor, 1.04) : root.dropColor
                        border.width: 1
                        border.color: dropArea.containsDrag ? root.accentColor : root.dropBorderColor

                        DropArea {
                            id: dropArea
                            anchors.fill: parent

                            onDropped: function(drop) {
                                if (drop.hasUrls && drop.urls.length > 0) {
                                    transcriptionService.set_selected_file(drop.urls[0].toString())
                                }
                            }
                        }

                        ColumnLayout {
                            anchors.centerIn: parent
                            spacing: 12

                            Rectangle {
                                Layout.alignment: Qt.AlignHCenter
                                width: 56
                                height: 56
                                radius: 28
                                color: root.isDark ? "#313131" : "#ececec"

                                Image {
                                    anchors.centerIn: parent
                                    source: ImagePath.upload
                                    width: 28
                                    height: 28
                                    fillMode: Image.PreserveAspectFit
                                }
                            }

                            Label {
                                Layout.alignment: Qt.AlignHCenter
                                text: qsTr("拖放音频或视频文件到这里")
                                color: root.textColor
                                font.pixelSize: 16
                                font.weight: Font.Medium
                            }

                            Label {
                                Layout.alignment: Qt.AlignHCenter
                                text: qsTr("支持 MP3、WAV、FLAC、MP4、MKV、AVI 等格式")
                                color: root.secondaryTextColor
                            }
                        }
                    }

                    RowLayout {
                        Layout.fillWidth: true

                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: 4

                            Label {
                                text: transcriptionService.state.selectedFileName
                                color: root.textColor
                                font.pixelSize: 15
                                font.weight: Font.Medium
                                Layout.fillWidth: true
                                elide: Text.ElideMiddle
                            }

                            Label {
                                text: transcriptionService.state.fileSuffix + " · " + transcriptionService.state.fileSizeText
                                color: root.secondaryTextColor
                            }
                        }

                        Button {
                            text: qsTr("选择文件")
                            icon.source: ImagePath.upload
                            onClicked: transcriptionService.pick_input_file()
                        }

                        Button {
                            text: qsTr("清除")
                            enabled: transcriptionService.state.selectedFilePath !== ""
                            onClicked: transcriptionService.clear_selected_file()
                        }
                    }
                }

                SurfaceCard {
                    Layout.fillWidth: true
                    title: qsTr("输出操作")
                    subtitle: qsTr("执行转录、复制结果或导出文本。")

                    Flow {
                        Layout.fillWidth: true
                        spacing: 10

                        Button {
                            text: qsTr("开始转录")
                            highlighted: true
                            enabled: transcriptionService.state.canStartTranscription
                            icon.source: ImagePath.play
                            onClicked: transcriptionService.start_transcription()
                        }

                        Button {
                            text: qsTr("导出文本")
                            enabled: transcriptionService.state.canExportTranscript
                            onClicked: transcriptionService.export_transcript_with_dialog()
                        }

                        Button {
                            text: qsTr("导出字幕")
                            enabled: transcriptionService.state.canExportSubtitle
                            onClicked: transcriptionService.export_subtitle_with_dialog()
                        }

                        Button {
                            text: qsTr("强制停止")
                            enabled: transcriptionService.state.canCancelTask
                            onClicked: transcriptionService.cancel_current_task()
                        }
                    }

                    Flow {
                        Layout.fillWidth: true
                        spacing: 10

                        Button {
                            text: qsTr("复制全文")
                            enabled: transcriptionService.state.canExportTranscript
                            onClicked: transcriptionService.copy_transcript()
                        }

                        Button {
                            text: qsTr("复制字幕")
                            enabled: transcriptionService.state.canExportSubtitle
                            onClicked: transcriptionService.copy_subtitle()
                        }

                        BusyIndicator {
                            running: transcriptionService.state.isBusy
                            visible: running
                        }
                    }

                    StatusChip {
                        visible: transcriptionService.state.lastError !== ""
                        text: transcriptionService.state.lastError
                        tone: "danger"
                    }
                }
            }

            SurfaceCard {
                Layout.fillWidth: true
                title: qsTr("转录全文")
                subtitle: qsTr("输出完整识别文本，可直接复制或导出。")

                RowLayout {
                    Layout.fillWidth: true
                    spacing: 10

                    StatusChip {
                        text: qsTr("语言 ") + transcriptionService.state.language
                        tone: "accent"
                    }

                    StatusChip {
                        text: qsTr("时长 ") + transcriptionService.state.durationText
                        tone: "neutral"
                    }
                }

                TextArea {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 260
                    readOnly: true
                    wrapMode: TextEdit.Wrap
                    text: transcriptionService.state.transcriptText !== "" ? transcriptionService.state.transcriptText : qsTr("转录结果会显示在这里。")
                }
            }

            SurfaceCard {
                Layout.fillWidth: true
                title: qsTr("字幕时间线")
                subtitle: qsTr("基于时间戳和分行算法生成的字幕预览。")

                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 8

                    Repeater {
                        model: transcriptionService.timeline_items

                        delegate: Rectangle {
                            required property var modelData
                            Layout.fillWidth: true
                            radius: 10
                            color: root.isDark ? "#1f1f1f" : "#fafafa"
                            border.width: 1
                            border.color: root.isDark ? "#343434" : "#e4e4e4"
                            implicitHeight: lineLayout.implicitHeight + 20

                            ColumnLayout {
                                id: lineLayout
                                anchors.fill: parent
                                anchors.margins: 10
                                spacing: 6

                                RowLayout {
                                    Layout.fillWidth: true

                                    StatusChip {
                                        text: "#" + modelData.index
                                        tone: "neutral"
                                    }

                                    Label {
                                        text: modelData.startLabel + "  →  " + modelData.endLabel
                                        color: root.secondaryTextColor
                                        Layout.fillWidth: true
                                    }

                                    Label {
                                        text: modelData.durationLabel
                                        color: root.secondaryTextColor
                                    }
                                }

                                Label {
                                    Layout.fillWidth: true
                                    wrapMode: Text.WordWrap
                                    text: modelData.text
                                    color: root.textColor
                                }
                            }
                        }
                    }

                    Label {
                        visible: transcriptionService.timeline_items.length === 0
                        text: qsTr("暂无字幕时间线。加载模型并完成一次转录后，这里会显示聚合字幕。")
                        color: root.secondaryTextColor
                        wrapMode: Text.WordWrap
                    }
                }
            }
        }
    }
}
