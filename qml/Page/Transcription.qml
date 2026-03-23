pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls.FluentWinUI3
import QtQuick.Layouts
import "../Component"
import "../Global"

Rectangle {
    id: root

    required property var viewModel
    property var navigationHost: null

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
                title: qsTr("开始转录")
                subtitle: qsTr("先选择媒体文件再直接开始，模型未就绪时会按需提示加载并继续。")

                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 14

                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 10

                        StatusChip {
                            text: viewModel.state.modelStatusText
                            tone: root.statusTone(viewModel.state.modelStatusText)
                        }

                        StatusChip {
                            text: viewModel.state.selectedFilePath !== ""
                                ? qsTr("文件已就绪")
                                : qsTr("等待选择文件")
                            tone: viewModel.state.selectedFilePath !== "" ? "accent" : "neutral"
                        }

                        Label {
                            Layout.fillWidth: true
                            text: viewModel.state.modelReady
                                ? viewModel.state.modelName + " · " + viewModel.state.modelDetails
                                : qsTr("模型管理已移至设置页，开始转录时也会自动提示加载。")
                            color: root.secondaryTextColor
                            wrapMode: Text.WordWrap
                        }

                        BusyIndicator {
                            running: viewModel.state.isBusy
                            visible: running
                        }
                    }

                    Label {
                        Layout.fillWidth: true
                        text: viewModel.state.selectedFilePath !== ""
                            ? viewModel.state.selectedFileName + " · " + viewModel.state.fileSuffix + " · " + viewModel.state.fileSizeText
                            : qsTr("支持 MP3、WAV、FLAC、MP4、MKV、AVI 等格式。")
                        color: root.textColor
                        wrapMode: Text.WordWrap
                        elide: Text.ElideMiddle
                    }

                    Flow {
                        Layout.fillWidth: true
                        spacing: 10

                        Button {
                            text: qsTr("选择文件")
                            icon.source: ImagePath.upload
                            onClicked: viewModel.pick_input_file()
                        }

                        Button {
                            text: qsTr("开始转录")
                            highlighted: true
                            enabled: viewModel.state.canStartTranscription
                            icon.source: ImagePath.play
                            onClicked: {
                                if (!viewModel.state.modelReady) {
                                    modelLoadPrompt.openPrompt()
                                    return
                                }
                                viewModel.start_transcription()
                            }
                        }

                        Button {
                            text: qsTr("导出文本")
                            enabled: viewModel.state.canExportTranscript
                            onClicked: viewModel.export_transcript_with_dialog()
                        }

                        Button {
                            text: qsTr("导出字幕")
                            enabled: viewModel.state.canExportSubtitle
                            onClicked: viewModel.export_subtitle_with_dialog()
                        }

                        Button {
                            text: qsTr("强制停止")
                            enabled: viewModel.state.canCancelTask
                            onClicked: viewModel.cancel_current_task()
                        }
                    }

                    ProgressBar {
                        visible: viewModel.state.isLoadingModel
                        Layout.fillWidth: true
                        from: 0
                        to: 100
                        value: viewModel.state.loadingProgress
                    }

                    StatusChip {
                        visible: viewModel.state.lastError !== ""
                        text: viewModel.state.lastError
                        tone: "danger"
                    }
                }

                GridLayout {
                    Layout.fillWidth: true
                    columns: width >= 1120 ? 3 : 1
                    rowSpacing: 14
                    columnSpacing: 14

                    StatTile {
                        label: qsTr("当前任务")
                        value: viewModel.state.taskStatusText
                        hint: qsTr("共享模型与当前文件的运行状态")
                    }

                    StatTile {
                        label: qsTr("字幕行数")
                        value: String(viewModel.state.subtitleLineCount)
                        hint: qsTr("聚合后的字幕条目数量")
                    }

                    StatTile {
                        label: qsTr("原始时间戳")
                        value: String(viewModel.state.timestampCount)
                        hint: qsTr("词级时间戳数量")
                    }
                }
            }

            SurfaceCard {
                Layout.fillWidth: true
                title: qsTr("输入文件")
                subtitle: qsTr("支持拖放和文件对话框选择。")

                Rectangle {
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
                                viewModel.set_selected_file(drop.urls[0].toString())
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
                    spacing: 10

                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 4

                        Label {
                            Layout.fillWidth: true
                            text: viewModel.state.selectedFileName
                            color: root.textColor
                            font.pixelSize: 15
                            font.weight: Font.Medium
                            elide: Text.ElideMiddle
                        }

                        Label {
                            text: viewModel.state.fileSuffix + " · " + viewModel.state.fileSizeText
                            color: root.secondaryTextColor
                        }
                    }

                    Button {
                        text: qsTr("选择文件")
                        icon.source: ImagePath.upload
                        onClicked: viewModel.pick_input_file()
                    }

                    Button {
                        text: qsTr("清除")
                        enabled: viewModel.state.selectedFilePath !== ""
                        onClicked: viewModel.clear_selected_file()
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
                        text: qsTr("语言 ") + viewModel.state.language
                        tone: "accent"
                    }

                    StatusChip {
                        text: qsTr("时长 ") + viewModel.state.durationText
                        tone: "neutral"
                    }

                    Item {
                        Layout.fillWidth: true
                    }

                    Button {
                        text: qsTr("复制全文")
                        enabled: viewModel.state.canExportTranscript
                        onClicked: viewModel.copy_transcript()
                    }
                }

                TextArea {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 260
                    readOnly: true
                    wrapMode: TextEdit.Wrap
                    text: viewModel.state.transcriptText !== "" ? viewModel.state.transcriptText : qsTr("转录结果会显示在这里。")
                }
            }

            SurfaceCard {
                Layout.fillWidth: true
                title: qsTr("字幕时间线")
                subtitle: qsTr("基于时间戳和分行算法生成的字幕预览。")

                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 8

                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 10

                        Item {
                            Layout.fillWidth: true
                        }

                        Button {
                            text: qsTr("复制字幕")
                            enabled: viewModel.state.canExportSubtitle
                            onClicked: viewModel.copy_subtitle()
                        }
                    }

                    Repeater {
                        model: viewModel.timeline_items

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
                                        Layout.fillWidth: true
                                        text: modelData.startLabel + "  →  " + modelData.endLabel
                                        color: root.secondaryTextColor
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
                        visible: viewModel.timeline_items.length === 0
                        text: qsTr("暂无字幕时间线。完成一次转录后，这里会显示聚合字幕。")
                        color: root.secondaryTextColor
                        wrapMode: Text.WordWrap
                    }
                }
            }
        }
    }

    ModelLoadPrompt {
        id: modelLoadPrompt
        anchors.fill: parent
        navigationHost: root.navigationHost
        actionTitle: qsTr("开始转录前需要先加载共享模型")
        actionDescription: qsTr("当前文件已经准备好。立即加载后会在模型就绪后自动继续转录，你也可以先前往设置页初始化或重载模型。")
        onLoadRequested: viewModel.load_model_and_continue()
    }
}
