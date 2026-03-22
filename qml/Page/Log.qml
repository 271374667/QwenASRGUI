pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls.FluentWinUI3
import QtQuick.Layouts
import "../Component"

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

    function levelTone(levelText) {
        switch (levelText) {
            case "SUCCESS": return "success"
            case "WARNING": return "warning"
            case "ERROR": return "danger"
            case "INFO": return "accent"
            default: return "neutral"
        }
    }

    function filteredEntries() {
        let source = logService.entries
        let text = searchField.text.toLowerCase()
        let level = levelCombo.currentText
        return source.filter(function(item) {
            let matchedText = text === "" || item.message.toLowerCase().indexOf(text) !== -1 || item.source.toLowerCase().indexOf(text) !== -1
            let matchedLevel = level === qsTr("全部") || item.level === level
            return matchedText && matchedLevel
        })
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
                title: qsTr("运行日志")
                subtitle: qsTr("汇总模型加载、转录和对齐过程中的所有运行日志。")

                GridLayout {
                    Layout.fillWidth: true
                    columns: width >= 1120 ? 3 : 1
                    rowSpacing: 14
                    columnSpacing: 14

                    StatTile {
                        label: qsTr("日志总数")
                        value: String(logService.entry_count)
                        hint: qsTr("当前会话内保留的日志条目")
                    }

                    StatTile {
                        label: qsTr("当前任务")
                        value: applicationService.state.currentOperation !== "" ? applicationService.state.currentOperation : qsTr("空闲")
                        hint: qsTr("全局任务锁当前占用状态")
                    }

                    StatTile {
                        label: qsTr("搜索结果")
                        value: String(root.filteredEntries().length)
                        hint: qsTr("结合搜索与级别过滤后的结果")
                    }
                }

                RowLayout {
                    Layout.fillWidth: true
                    spacing: 10

                    Button {
                        text: qsTr("导出日志")
                        enabled: logService.entry_count > 0
                        onClicked: logService.export_logs_with_dialog()
                    }

                    Button {
                        text: qsTr("清空日志")
                        enabled: logService.entry_count > 0
                        onClicked: logService.clear_entries()
                    }
                }
            }

            SurfaceCard {
                Layout.fillWidth: true
                title: qsTr("过滤器")
                subtitle: qsTr("按关键字和日志级别筛选。")

                RowLayout {
                    Layout.fillWidth: true
                    spacing: 10

                    TextField {
                        id: searchField
                        Layout.fillWidth: true
                        placeholderText: qsTr("搜索日志内容或来源模块")
                    }

                    ComboBox {
                        id: levelCombo
                        Layout.preferredWidth: 140
                        model: [qsTr("全部"), "DEBUG", "INFO", "SUCCESS", "WARNING", "ERROR"]
                    }
                }
            }

            SurfaceCard {
                Layout.fillWidth: true
                title: qsTr("日志流")
                subtitle: qsTr("最新日志显示在下方。")

                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 8

                    Repeater {
                        model: root.filteredEntries()

                        delegate: Rectangle {
                            required property var modelData
                            Layout.fillWidth: true
                            radius: 10
                            color: root.isDark ? "#1f1f1f" : "#fafafa"
                            border.width: 1
                            border.color: root.isDark ? "#343434" : "#e4e4e4"
                            implicitHeight: entryColumn.implicitHeight + 18

                            ColumnLayout {
                                id: entryColumn
                                anchors.fill: parent
                                anchors.margins: 10
                                spacing: 6

                                RowLayout {
                                    Layout.fillWidth: true

                                    Label {
                                        text: modelData.timestamp
                                        color: root.secondaryTextColor
                                        font.family: "Consolas"
                                    }

                                    StatusChip {
                                        text: modelData.level
                                        tone: root.levelTone(modelData.level)
                                    }

                                    Label {
                                        text: modelData.source
                                        color: root.secondaryTextColor
                                        Layout.fillWidth: true
                                    }
                                }

                                Label {
                                    Layout.fillWidth: true
                                    wrapMode: Text.WordWrap
                                    text: modelData.message
                                    color: root.textColor
                                }
                            }
                        }
                    }

                    Label {
                        visible: root.filteredEntries().length === 0
                        text: qsTr("当前没有匹配的日志记录。")
                        color: root.secondaryTextColor
                    }
                }
            }
        }
    }
}
