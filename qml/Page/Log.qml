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
    readonly property color timeColor: isDark ? "#7ee787" : "#1a7f37"
    readonly property color sourceColor: isDark ? "#79c0ff" : "#0969da"

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

    function escapeHtml(text) {
        return String(text)
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/\"/g, "&quot;")
    }

    function levelColor(levelText) {
        switch (levelText) {
            case "TRACE": return isDark ? "#56d4dd" : "#0f766e"
            case "DEBUG": return isDark ? "#79c0ff" : "#0969da"
            case "INFO": return textColor
            case "SUCCESS": return isDark ? "#7ee787" : "#1a7f37"
            case "WARNING": return isDark ? "#ffd866" : "#9a6700"
            case "ERROR": return isDark ? "#ff7b72" : "#cf222e"
            case "CRITICAL": return isDark ? "#ff4d4f" : "#a40e26"
            default: return secondaryTextColor
        }
    }

    function formatRichEntry(item) {
        let timestamp = root.escapeHtml(item.timestamp)
        let level = root.escapeHtml(item.level)
        let source = root.escapeHtml(item.source)
        let message = root.escapeHtml(item.message.replace(/\r?\n/g, " "))
        let levelColor = root.levelColor(item.level)
        return "<span style=\"color:" + root.timeColor + ";\">[" + timestamp + "]</span> "
            + "<span style=\"color:" + levelColor + "; font-weight:600;\">[" + level + "]</span> "
            + "<span style=\"color:" + root.sourceColor + ";\">" + source + "</span> "
            + "<span style=\"color:" + levelColor + ";\">- " + message + "</span>"
    }

    function formattedEntriesRichText() {
        let entries = root.filteredEntries()
        if (entries.length === 0) {
            return "<span style=\"color:" + root.secondaryTextColor + ";\">"
                + root.escapeHtml(qsTr("当前没有匹配的日志记录。"))
                + "</span>"
        }

        let lines = []
        for (let index = 0; index < entries.length; ++index) {
            lines.push(root.formatRichEntry(entries[index]))
        }
        return "<div style=\"font-family:'Consolas'; white-space:pre;\">"
            + lines.join("<br/>")
            + "</div>"
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
                    text: root.formattedEntriesRichText()
                    textFormat: TextEdit.RichText
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
