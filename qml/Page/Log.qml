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

    function filteredEntries() {
        let source = viewModel.entries
        let text = searchField.text.toLowerCase()
        let level = levelCombo.currentText
        return source.filter(function(item) {
            let matchedText = text === "" || item.message.toLowerCase().indexOf(text) !== -1 || item.source.toLowerCase().indexOf(text) !== -1
            let matchedLevel = level === qsTr("全部") || item.level === level
            return matchedText && matchedLevel
        })
    }

    function formatEntry(item) {
        return "[" + item.timestamp + "] [" + item.level + "] " + item.source + " - "
            + item.message.replace(/\r?\n/g, " ")
    }

    function formattedEntriesText() {
        let entries = root.filteredEntries()
        if (entries.length === 0) {
            return qsTr("当前没有匹配的日志记录。")
        }

        let lines = []
        for (let index = 0; index < entries.length; ++index) {
            lines.push(root.formatEntry(entries[index]))
        }
        return lines.join("\n")
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
                        value: String(viewModel.entry_count)
                        hint: qsTr("当前会话内保留的日志条目")
                    }

                    StatTile {
                        label: qsTr("当前任务")
                        value: viewModel.state.currentOperation !== "" ? viewModel.state.currentOperation : qsTr("空闲")
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
                        enabled: viewModel.entry_count > 0
                        onClicked: viewModel.export_logs_with_dialog()
                    }

                    Button {
                        text: qsTr("清空日志")
                        enabled: viewModel.entry_count > 0
                        onClicked: viewModel.clear_entries()
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
                        horizontalAlignment: TextInput.AlignLeft
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

                TextArea {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 460
                    readOnly: true
                    text: root.formattedEntriesText()
                    wrapMode: TextEdit.NoWrap
                    font.family: "Consolas"
                    horizontalAlignment: TextEdit.AlignLeft
                    verticalAlignment: TextEdit.AlignTop
                    selectByMouse: true
                    padding: 12
                }
            }
        }
    }
}
