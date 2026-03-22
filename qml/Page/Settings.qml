pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls.FluentWinUI3
import QtQuick.Layouts
import "../Component"

Rectangle {
    id: root

    required property var viewModel

    readonly property bool isDark: Application.styleHints.colorScheme === Qt.ColorScheme.Dark
    readonly property color backgroundColor: isDark ? "#1c1c1c" : "#f6f6f6"
    readonly property color textColor: isDark ? "#f5f5f5" : "#202020"
    readonly property color secondaryTextColor: isDark ? "#b3b3b3" : "#6b6b6b"

    function setComboByValue(combo, items, value) {
        for (let i = 0; i < items.length; ++i) {
            if (items[i].value === value) {
                combo.currentIndex = i
                return
            }
        }
        combo.currentIndex = 0
    }

    function syncFromSettings() {
        let settings = viewModel.settings
        root.setComboByValue(modelSizeCombo, viewModel.model_size_options, settings.modelSize)
        root.setComboByValue(quantizationCombo, viewModel.quantization_options, settings.quantizationMode)
        root.setComboByValue(deviceCombo, viewModel.device_options, settings.device)
        root.setComboByValue(breaklineCombo, viewModel.breakline_method_options, settings.gapDetectionMethod)
        segmentSlider.value = settings.segmentDuration
        inferenceDelaySlider.value = settings.inferenceDelay
        maxCharsSlider.value = settings.maxCharsPerLine
        maxDurationSlider.value = settings.maxDurationPerLine
        enableLimitSwitch.checked = settings.enableMemoryLimit
        systemMemorySlider.value = settings.systemMemoryPercent
        gpuMemorySlider.value = settings.gpuMemoryPercent
        lowPrioritySwitch.checked = settings.lowPriorityMode
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
                title: qsTr("运行设置")
                subtitle: qsTr("设置会自动保存，重载模型后即可应用模型和推理相关配置。")

                GridLayout {
                    Layout.fillWidth: true
                    columns: width >= 1120 ? 3 : 1
                    rowSpacing: 14
                    columnSpacing: 14

                    StatTile {
                        label: qsTr("共享模型")
                        value: viewModel.state.modelName
                        hint: viewModel.state.modelStatusText
                    }

                    StatTile {
                        label: qsTr("系统内存")
                        value: viewModel.state.hardwareSummary.systemMemoryGb + " GB"
                        hint: qsTr("CPU 核心数 ") + viewModel.state.hardwareSummary.cpuCores
                    }

                    StatTile {
                        label: qsTr("GPU")
                        value: viewModel.state.hardwareSummary.gpuName
                        hint: viewModel.state.hardwareSummary.hasGpu ? viewModel.state.hardwareSummary.gpuMemoryGb + " GB" : qsTr("未检测到 GPU")
                    }
                }

                RowLayout {
                    Layout.fillWidth: true
                    spacing: 10

                    Button {
                        text: qsTr("恢复默认")
                        onClicked: viewModel.reset_defaults()
                    }

                    Button {
                        text: qsTr("重载共享模型")
                        enabled: viewModel.state.canReloadModel
                        onClicked: viewModel.reload_model()
                    }
                }
            }

            SurfaceCard {
                Layout.fillWidth: true
                title: qsTr("模型设置")
                subtitle: qsTr("控制共享模型的规模、量化和设备。")

                GridLayout {
                    Layout.fillWidth: true
                    columns: width >= 1120 ? 3 : 1
                    rowSpacing: 16
                    columnSpacing: 16

                    ColumnLayout {
                        Layout.fillWidth: true

                        Label { text: qsTr("模型大小"); color: root.secondaryTextColor }
                        ComboBox {
                            id: modelSizeCombo
                            Layout.fillWidth: true
                            model: viewModel.model_size_options
                            textRole: "label"
                            onActivated: viewModel.update_setting("modelSize", viewModel.model_size_options[index].value)
                        }
                    }

                    ColumnLayout {
                        Layout.fillWidth: true

                        Label { text: qsTr("量化模式"); color: root.secondaryTextColor }
                        ComboBox {
                            id: quantizationCombo
                            Layout.fillWidth: true
                            model: viewModel.quantization_options
                            textRole: "label"
                            onActivated: viewModel.update_setting("quantizationMode", viewModel.quantization_options[index].value)
                        }
                    }

                    ColumnLayout {
                        Layout.fillWidth: true

                        Label { text: qsTr("推理设备"); color: root.secondaryTextColor }
                        ComboBox {
                            id: deviceCombo
                            Layout.fillWidth: true
                            model: viewModel.device_options
                            textRole: "label"
                            onActivated: viewModel.update_setting("device", viewModel.device_options[index].value)
                        }
                    }
                }
            }

            SurfaceCard {
                Layout.fillWidth: true
                title: qsTr("推理设置")
                subtitle: qsTr("控制分段长度和推理节奏。")

                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 10

                    Label {
                        text: qsTr("音频分段时长: ") + Math.round(segmentSlider.value) + qsTr(" 秒")
                        color: root.textColor
                    }

                    Slider {
                        id: segmentSlider
                        Layout.fillWidth: true
                        from: 5
                        to: 60
                        stepSize: 1
                        onMoved: viewModel.update_setting("segmentDuration", value)
                    }

                    Label {
                        text: qsTr("分段间推理延迟: ") + inferenceDelaySlider.value.toFixed(2) + qsTr(" 秒")
                        color: root.textColor
                    }

                    Slider {
                        id: inferenceDelaySlider
                        Layout.fillWidth: true
                        from: 0
                        to: 1
                        stepSize: 0.05
                        onMoved: viewModel.update_setting("inferenceDelay", value)
                    }

                    Switch {
                        id: lowPrioritySwitch
                        text: qsTr("启用低优先级模式")
                        onToggled: viewModel.update_setting("lowPriorityMode", checked)
                    }
                }
            }

            SurfaceCard {
                Layout.fillWidth: true
                title: qsTr("资源限制")
                subtitle: qsTr("在加载模型前设置内存与显存占用上限。")

                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 10

                    Switch {
                        id: enableLimitSwitch
                        text: qsTr("启用资源限制")
                        onToggled: viewModel.update_setting("enableMemoryLimit", checked)
                    }

                    Label {
                        text: qsTr("系统内存上限: ") + Math.round(systemMemorySlider.value) + "%"
                        color: root.textColor
                    }

                    Slider {
                        id: systemMemorySlider
                        Layout.fillWidth: true
                        enabled: enableLimitSwitch.checked
                        from: 10
                        to: 100
                        stepSize: 1
                        onMoved: viewModel.update_setting("systemMemoryPercent", value)
                    }

                    Label {
                        text: qsTr("GPU 显存上限: ") + Math.round(gpuMemorySlider.value) + "%"
                        color: root.textColor
                    }

                    Slider {
                        id: gpuMemorySlider
                        Layout.fillWidth: true
                        enabled: enableLimitSwitch.checked
                        from: 10
                        to: 100
                        stepSize: 1
                        onMoved: viewModel.update_setting("gpuMemoryPercent", value)
                    }
                }
            }

            SurfaceCard {
                Layout.fillWidth: true
                title: qsTr("字幕分行")
                subtitle: qsTr("控制字幕导出时的分行算法和行长度。")

                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 10

                    ComboBox {
                        id: breaklineCombo
                        Layout.fillWidth: true
                        model: viewModel.breakline_method_options
                        textRole: "label"
                        onActivated: viewModel.update_setting("gapDetectionMethod", viewModel.breakline_method_options[index].value)
                    }

                    Label {
                        text: qsTr("每行最大字符数: ") + Math.round(maxCharsSlider.value)
                        color: root.textColor
                    }

                    Slider {
                        id: maxCharsSlider
                        Layout.fillWidth: true
                        from: 6
                        to: 50
                        stepSize: 1
                        onMoved: viewModel.update_setting("maxCharsPerLine", value)
                    }

                    Label {
                        text: qsTr("每行最大时长: ") + maxDurationSlider.value.toFixed(1) + qsTr(" 秒")
                        color: root.textColor
                    }

                    Slider {
                        id: maxDurationSlider
                        Layout.fillWidth: true
                        from: 1
                        to: 12
                        stepSize: 0.5
                        onMoved: viewModel.update_setting("maxDurationPerLine", value)
                    }
                }
            }
        }
    }

    Component.onCompleted: root.syncFromSettings()

    Connections {
        target: viewModel

        function onSettingsChanged() {
            root.syncFromSettings()
        }
    }
}
