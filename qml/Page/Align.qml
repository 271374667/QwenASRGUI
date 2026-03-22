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

    function statusTone(statusText) {
        if (statusText === "就绪") return "success"
        if (statusText === "加载中" || statusText === "处理中") return "warning"
        if (statusText === "错误") return "danger"
        return "neutral"
    }

    function syncLanguageSelection() {
        let options = alignmentService.language_options
        let value = alignmentService.state.selectedLanguage
        for (let i = 0; i < options.length; ++i) {
            if (options[i].value === value) {
                languageCombo.currentIndex = i
                return
            }
        }
        languageCombo.currentIndex = 0
    }

    color: backgroundColor

    ScrollView {
        id: scrollView
        anchors.fill: parent
        clip: true

        PageScrollContent {
            width: scrollView.availableWidth
            spacing: 24

            SurfaceCard {
                Layout.fillWidth: true
                title: qsTr("强制对齐")
                subtitle: qsTr("将已有文本与音频逐词对齐，生成精确的时间戳和字幕。")

                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 12

                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 10

                        StatusChip {
                            text: alignmentService.state.modelStatusText
                            tone: root.statusTone(alignmentService.state.modelStatusText)
                        }

                        Label {
                            text: alignmentService.state.modelName + " · " + qsTr("与转录页共享模型")
                            color: root.secondaryTextColor
                            Layout.fillWidth: true
                        }
                    }

                    Flow {
                        Layout.fillWidth: true
                        spacing: 10

                        Button {
                            text: qsTr("加载共享模型")
                            enabled: transcriptionService.state.canLoadModel
                            onClicked: transcriptionService.load_model()
                        }

                        Button {
                            text: qsTr("重载模型")
                            enabled: transcriptionService.state.canReloadModel
                            onClicked: transcriptionService.reload_model()
                        }

                        Button {
                            text: qsTr("强制停止")
                            enabled: alignmentService.state.canCancelTask || transcriptionService.state.canCancelTask
                            onClicked: {
                                if (alignmentService.state.canCancelTask) {
                                    alignmentService.cancel_current_task()
                                } else {
                                    transcriptionService.cancel_current_task()
                                }
                            }
                        }
                    }
                }

                GridLayout {
                    Layout.fillWidth: true
                    columns: width >= 1120 ? 3 : 1
                    rowSpacing: 14
                    columnSpacing: 14

                    StatTile {
                        label: qsTr("当前任务")
                        value: alignmentService.state.taskStatusText
                        hint: qsTr("音频与文本准备完成后即可执行对齐")
                    }

                    StatTile {
                        label: qsTr("词级数量")
                        value: String(alignmentService.state.wordCount)
                        hint: qsTr("原始对齐时间戳个数")
                    }

                    StatTile {
                        label: qsTr("字幕行数")
                        value: String(alignmentService.state.lineCount)
                        hint: qsTr("聚合后的字幕行数量")
                    }
                }
            }

            GridLayout {
                Layout.fillWidth: true
                columns: width >= 1120 ? 2 : 1
                rowSpacing: 24
                columnSpacing: 24

                SurfaceCard {
                    Layout.fillWidth: true
                    Layout.preferredWidth: 1
                    title: qsTr("对齐音频")
                    subtitle: qsTr("选择音频或视频文件作为对齐源。")

                    Label {
                        text: alignmentService.state.selectedFileName
                        color: root.textColor
                        font.pixelSize: 15
                        font.weight: Font.Medium
                        Layout.fillWidth: true
                        elide: Text.ElideMiddle
                    }

                    Label {
                        text: alignmentService.state.fileSuffix + " · " + alignmentService.state.fileSizeText
                        color: root.secondaryTextColor
                    }

                    Flow {
                        Layout.fillWidth: true

                        Button {
                            text: qsTr("选择音频")
                            icon.source: ImagePath.upload
                            onClicked: alignmentService.pick_input_file()
                        }

                        Button {
                            text: qsTr("清空结果")
                            enabled: alignmentService.state.hasResult
                            onClicked: alignmentService.clear_result()
                        }
                    }
                }

                SurfaceCard {
                    Layout.fillWidth: true
                    Layout.preferredWidth: 1
                    title: qsTr("对齐选项")
                    subtitle: qsTr("选择语言并执行对齐。")

                    ComboBox {
                        id: languageCombo
                        Layout.fillWidth: true
                        model: alignmentService.language_options
                        textRole: "label"
                        onActivated: alignmentService.update_language(alignmentService.language_options[index].value)
                        Component.onCompleted: root.syncLanguageSelection()
                    }

                    Flow {
                        Layout.fillWidth: true
                        spacing: 10

                        Button {
                            text: qsTr("开始对齐")
                            highlighted: true
                            enabled: alignmentService.state.canStartAlignment
                            icon.source: ImagePath.timePicker
                            onClicked: alignmentService.start_alignment()
                        }

                        Button {
                            text: qsTr("导出字幕")
                            enabled: alignmentService.state.canExportSubtitle
                            onClicked: alignmentService.export_subtitle_with_dialog()
                        }

                        Button {
                            text: qsTr("强制停止")
                            enabled: alignmentService.state.canCancelTask
                            onClicked: alignmentService.cancel_current_task()
                        }
                    }

                    Flow {
                        Layout.fillWidth: true
                        spacing: 10

                        Button {
                            text: qsTr("复制字幕")
                            enabled: alignmentService.state.canExportSubtitle
                            onClicked: alignmentService.copy_subtitle()
                        }

                        Button {
                            text: qsTr("复制时间戳")
                            enabled: alignmentService.state.hasResult
                            onClicked: alignmentService.copy_raw_timestamps()
                        }

                        BusyIndicator {
                            running: alignmentService.state.isBusy
                            visible: running
                        }
                    }

                    StatusChip {
                        visible: alignmentService.state.lastError !== ""
                        text: alignmentService.state.lastError
                        tone: "danger"
                    }
                }
            }

            SurfaceCard {
                Layout.fillWidth: true
                title: qsTr("待对齐文本")
                subtitle: qsTr("输入你已经准备好的文本内容，系统会返回词级时间戳。")

                TextArea {
                    id: inputArea
                    Layout.fillWidth: true
                    Layout.preferredHeight: 220
                    wrapMode: TextEdit.Wrap
                    text: alignmentService.state.inputText
                    placeholderText: qsTr("在这里粘贴待对齐文本。")
                    onTextChanged: alignmentService.update_input_text(text)
                }
            }

            SurfaceCard {
                Layout.fillWidth: true
                title: qsTr("字幕结果")
                subtitle: qsTr("可直接预览聚合后的字幕。")

                RowLayout {
                    Layout.fillWidth: true
                    spacing: 10

                    StatusChip {
                        text: qsTr("音频时长 ") + alignmentService.state.audioDurationText
                        tone: "accent"
                    }

                    StatusChip {
                        text: qsTr("词级时间戳 ") + alignmentService.state.wordCount
                        tone: "neutral"
                    }
                }

                TextArea {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 180
                    readOnly: true
                    wrapMode: TextEdit.Wrap
                    text: alignmentService.state.subtitleText !== "" ? alignmentService.state.subtitleText : qsTr("对齐字幕会显示在这里。")
                }
            }

            SurfaceCard {
                Layout.fillWidth: true
                title: qsTr("原始时间戳")
                subtitle: qsTr("逐词时间戳预览。")

                TextArea {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 180
                    readOnly: true
                    wrapMode: TextEdit.Wrap
                    text: alignmentService.state.rawTimestampText !== "" ? alignmentService.state.rawTimestampText : qsTr("执行对齐后，这里会显示原始时间戳。")
                }
            }
        }
    }

    Connections {
        target: alignmentService

        function onStateChanged() {
            root.syncLanguageSelection()
        }
    }
}
