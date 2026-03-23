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

    function statusTone(statusText) {
        if (statusText === "就绪") return "success"
        if (statusText === "加载中" || statusText === "处理中") return "warning"
        if (statusText === "错误") return "danger"
        return "neutral"
    }

    function syncLanguageSelection() {
        let options = viewModel.language_options
        let value = viewModel.state.selectedLanguage
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
                title: qsTr("开始对齐")
                subtitle: qsTr("音频和文本准备好后直接开始，模型未就绪时会按需提示加载并继续。")

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
                            text: viewModel.state.selectedFilePath !== "" && viewModel.state.inputText.trim() !== ""
                                ? qsTr("材料已就绪")
                                : qsTr("等待补全材料")
                            tone: viewModel.state.selectedFilePath !== "" && viewModel.state.inputText.trim() !== ""
                                ? "accent"
                                : "neutral"
                        }

                        Label {
                            Layout.fillWidth: true
                            text: viewModel.state.modelReady
                                ? viewModel.state.modelName + " · " + viewModel.state.modelDetails
                                : qsTr("模型管理已移至设置页，开始对齐时会按需提示加载。")
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
                            : qsTr("请选择音频或视频文件作为对齐源。")
                        color: root.textColor
                        wrapMode: Text.WordWrap
                        elide: Text.ElideMiddle
                    }

                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 10

                        ColumnLayout {
                            spacing: 4

                            Label {
                                text: qsTr("对齐语言")
                                color: root.secondaryTextColor
                            }

                            ComboBox {
                                id: languageCombo
                                Layout.preferredWidth: 180
                                model: viewModel.language_options
                                textRole: "label"
                                onActivated: viewModel.update_language(viewModel.language_options[index].value)
                                Component.onCompleted: root.syncLanguageSelection()
                            }
                        }

                        Item {
                            Layout.fillWidth: true
                        }
                    }

                    Flow {
                        Layout.fillWidth: true
                        spacing: 10

                        Button {
                            text: qsTr("选择音频")
                            icon.source: ImagePath.upload
                            onClicked: viewModel.pick_input_file()
                        }

                        Button {
                            text: qsTr("开始对齐")
                            highlighted: true
                            enabled: viewModel.state.canStartAlignment
                            icon.source: ImagePath.timePicker
                            onClicked: {
                                if (!viewModel.state.modelReady) {
                                    modelLoadPrompt.openPrompt()
                                    return
                                }
                                viewModel.start_alignment()
                            }
                        }

                        Button {
                            text: qsTr("导出字幕")
                            enabled: viewModel.state.canExportSubtitle
                            onClicked: viewModel.export_subtitle_with_dialog()
                        }

                        Button {
                            text: qsTr("复制时间戳")
                            enabled: viewModel.state.hasResult
                            onClicked: viewModel.copy_raw_timestamps()
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
                        hint: qsTr("音频、文本和共享模型的综合状态")
                    }

                    StatTile {
                        label: qsTr("词级数量")
                        value: String(viewModel.state.wordCount)
                        hint: qsTr("原始对齐时间戳个数")
                    }

                    StatTile {
                        label: qsTr("字幕行数")
                        value: String(viewModel.state.lineCount)
                        hint: qsTr("聚合后的字幕行数量")
                    }
                }
            }

            SurfaceCard {
                Layout.fillWidth: true
                title: qsTr("对齐音频")
                subtitle: qsTr("选择音频或视频文件作为对齐源。")

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
                        text: qsTr("选择音频")
                        icon.source: ImagePath.upload
                        onClicked: viewModel.pick_input_file()
                    }

                    Button {
                        text: qsTr("清空结果")
                        enabled: viewModel.state.hasResult
                        onClicked: viewModel.clear_result()
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
                    text: viewModel.state.inputText
                    placeholderText: qsTr("在这里粘贴待对齐文本。")
                    onTextChanged: viewModel.update_input_text(text)
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
                        text: qsTr("音频时长 ") + viewModel.state.audioDurationText
                        tone: "accent"
                    }

                    StatusChip {
                        text: qsTr("词级时间戳 ") + viewModel.state.wordCount
                        tone: "neutral"
                    }

                    Item {
                        Layout.fillWidth: true
                    }

                    Button {
                        text: qsTr("复制字幕")
                        enabled: viewModel.state.canExportSubtitle
                        onClicked: viewModel.copy_subtitle()
                    }
                }

                TextArea {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 180
                    readOnly: true
                    wrapMode: TextEdit.Wrap
                    text: viewModel.state.subtitleText !== "" ? viewModel.state.subtitleText : qsTr("对齐字幕会显示在这里。")
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
                    text: viewModel.state.rawTimestampText !== "" ? viewModel.state.rawTimestampText : qsTr("执行对齐后，这里会显示原始时间戳。")
                }
            }
        }
    }

    ModelLoadPrompt {
        id: modelLoadPrompt
        anchors.fill: parent
        navigationHost: root.navigationHost
        actionTitle: qsTr("开始对齐前需要先加载共享模型")
        actionDescription: qsTr("当前音频和文本已经准备好。立即加载后会在模型就绪后自动继续对齐，你也可以先前往设置页初始化或重载模型。")
        onLoadRequested: viewModel.load_model_and_continue()
    }

    Connections {
        target: viewModel

        function onStateChanged() {
            root.syncLanguageSelection()
        }
    }
}
