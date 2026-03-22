pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls.FluentWinUI3
import QtQuick.Layouts

import QtQuick.Controls as Controls

Item {
    id: root

    required property var pages
    property var pageContext: ({})
    readonly property int navVerticalMargin: 8

    readonly property bool isDark: Application.styleHints.colorScheme === Qt.ColorScheme.Dark
    readonly property color accentColor: palette.accent
    readonly property color backgroundColor: isDark ? "#1c1c1c" : "#f9f9f9"
    readonly property color sideBarColor: isDark ? "#202020" : "#f3f3f3"
    readonly property color separatorColor: isDark ? "#3d3d3d" : "#e0e0e0"
    readonly property color hoverColor: isDark ? "#3d3d3d" : "#e5e5e5"
    readonly property color pressedColor: isDark ? "#4d4d4d" : "#d5d5d5"
    readonly property color selectedColor: isDark ? "#4d4d4d" : "#dcdcdc"

    readonly property var topPages: normalizedPages("top")
    readonly property var bottomPages: normalizedPages("bottom")

    property int currentIndex: 0
    property int previousIndex: 0
    property var buttonRegistry: ({})
    property int buttonRegistryVersion: 0
    readonly property var currentNavButton: {
        root.buttonRegistryVersion
        return root.getNavButton(root.currentIndex)
    }
    readonly property real currentNavButtonY: root.currentNavButton
        ? navColumn.y + root.currentNavButton.y
        : root.navVerticalMargin

    function normalizedPages(section) {
        let result = []

        if (!root.pages) {
            return result
        }

        for (let i = 0; i < root.pages.length; ++i) {
            let page = root.pages[i]
            let pageSection = page.section ? page.section : "top"

            if (pageSection === section) {
                result.push({
                    "index": i,
                    "name": page.name,
                    "iconSource": page.iconSource,
                    "qmlPath": page.qmlPath
                })
            }
        }

        return result
    }

    function registerButton(index, button) {
        let updatedRegistry = ({})

        for (let key in root.buttonRegistry) {
            updatedRegistry[key] = root.buttonRegistry[key]
        }

        updatedRegistry[index] = button
        root.buttonRegistry = updatedRegistry
        root.buttonRegistryVersion += 1
    }

    function unregisterButton(index, button) {
        if (root.buttonRegistry[index] !== button) {
            return
        }

        let updatedRegistry = ({})

        for (let key in root.buttonRegistry) {
            if (key !== String(index)) {
                updatedRegistry[key] = root.buttonRegistry[key]
            }
        }

        root.buttonRegistry = updatedRegistry
        root.buttonRegistryVersion += 1
    }

    function getNavButton(index) {
        return root.buttonRegistry[index] ? root.buttonRegistry[index] : null
    }

    function createPageObject(qmlPath) {
        let component = Qt.createComponent(qmlPath)

        if (component.status === Component.Error) {
            console.error("Failed to load page:", qmlPath, component.errorString())
            return null
        }

        return component.createObject(stackView, root.pageContext)
    }

    function navigateTo(index, qmlPath) {
        if (!root.pages || index < 0 || index >= root.pages.length || root.currentIndex === index) {
            return
        }

        let pageObject = createPageObject(qmlPath)
        if (!pageObject) {
            return
        }

        root.previousIndex = root.currentIndex
        root.currentIndex = index
        stackView.replace(null, pageObject)
    }

    function ensureCurrentPageLoaded() {
        if (!root.pages || root.pages.length === 0) {
            return
        }

        if (root.currentIndex < 0 || root.currentIndex >= root.pages.length) {
            return
        }

        if (stackView.depth === 0) {
            let pageObject = createPageObject(root.pages[root.currentIndex].qmlPath)
            if (pageObject) {
                stackView.push(pageObject, {}, Controls.StackView.Immediate)
            }
        }
    }

    onPagesChanged: {
        if (!root.pages || root.pages.length === 0) {
            root.currentIndex = -1
            root.previousIndex = -1
            return
        }

        if (root.currentIndex < 0 || root.currentIndex >= root.pages.length) {
            root.currentIndex = 0
            root.previousIndex = 0
        }

        root.ensureCurrentPageLoaded()
    }

    Component.onCompleted: root.ensureCurrentPageLoaded()

    RowLayout {
        anchors.fill: parent
        spacing: 0

        Item {
            id: sideBarContainer
            Layout.preferredWidth: 48
            Layout.minimumWidth: 48
            Layout.maximumWidth: 48
            Layout.fillHeight: true
            clip: true

            Rectangle {
                id: sideBar
                anchors.fill: parent
                color: root.sideBarColor
                clip: true

                Rectangle {
                    id: selectionBackground
                    width: 40
                    height: 40
                    radius: 6
                    color: root.selectedColor
                    x: (sideBar.width - width) / 2
                    z: 0

                    y: root.currentNavButtonY

                    Behavior on y {
                        NumberAnimation {
                            duration: 200
                            easing.type: Easing.OutCubic
                        }
                    }
                }

                ColumnLayout {
                    id: navColumn
                    anchors.fill: parent
                    anchors.topMargin: root.navVerticalMargin
                    anchors.bottomMargin: root.navVerticalMargin
                    spacing: 4
                    z: 1

                    Repeater {
                        model: root.topPages

                        delegate: NavButton {
                            required property var modelData

                            navIndex: modelData.index
                            pageName: modelData.name
                            iconSource: modelData.iconSource

                            onClicked: root.navigateTo(modelData.index, modelData.qmlPath)

                            Component.onCompleted: root.registerButton(modelData.index, this)
                            Component.onDestruction: root.unregisterButton(modelData.index, this)
                        }
                    }

                    Item {
                        Layout.fillHeight: true
                    }

                    Repeater {
                        model: root.bottomPages

                        delegate: NavButton {
                            required property var modelData

                            navIndex: modelData.index
                            pageName: modelData.name
                            iconSource: modelData.iconSource

                            onClicked: root.navigateTo(modelData.index, modelData.qmlPath)

                            Component.onCompleted: root.registerButton(modelData.index, this)
                            Component.onDestruction: root.unregisterButton(modelData.index, this)
                        }
                    }
                }

                Rectangle {
                    id: selectionIndicator
                    width: 3
                    height: 16
                    radius: 1.5
                    color: root.accentColor
                    x: 4
                    z: 2

                    y: root.currentNavButton
                        ? root.currentNavButtonY + (root.currentNavButton.height - height) / 2
                        : root.navVerticalMargin + 12

                    Behavior on y {
                        NumberAnimation {
                            duration: 200
                            easing.type: Easing.OutCubic
                        }
                    }
                }
            }
        }

        Rectangle {
            Layout.preferredWidth: 1
            Layout.fillHeight: true
            color: root.separatorColor
        }

        Controls.StackView {
            id: stackView
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true

            replaceEnter: Transition {
                ParallelAnimation {
                    PropertyAnimation {
                        property: "opacity"
                        from: 0
                        to: 1
                        duration: 200
                        easing.type: Easing.OutCubic
                    }

                    PropertyAnimation {
                        property: "y"
                        from: root.currentIndex > root.previousIndex ? 30 : -30
                        to: 0
                        duration: 200
                        easing.type: Easing.OutCubic
                    }
                }
            }

            replaceExit: Transition {
                PropertyAnimation {
                    property: "opacity"
                    from: 1
                    to: 0
                    duration: 150
                    easing.type: Easing.InCubic
                }
            }
        }
    }

    component NavButton: Item {
        id: navButton
        Layout.preferredWidth: 40
        Layout.preferredHeight: 40
        Layout.minimumWidth: 40
        Layout.maximumWidth: 40
        Layout.minimumHeight: 40
        Layout.maximumHeight: 40
        Layout.alignment: Qt.AlignHCenter
        implicitWidth: 40
        implicitHeight: 40
        clip: true

        required property int navIndex
        required property string pageName
        property url iconSource
        readonly property bool isSelected: root.currentIndex === navIndex

        signal clicked()

        Rectangle {
            anchors.fill: parent
            radius: 6
            color: {
                if (mouseArea.pressed) {
                    return root.pressedColor
                }

                if (mouseArea.containsMouse) {
                    return root.hoverColor
                }

                return "transparent"
            }
            visible: !navButton.isSelected
        }

        Item {
            anchors.centerIn: parent
            width: 24
            height: 24
            scale: navButton.isSelected ? 1.2 : 1.0

            Behavior on scale {
                NumberAnimation {
                    duration: 150
                    easing.type: Easing.OutCubic
                }
            }

            Image {
                anchors.fill: parent
                source: navButton.iconSource
                sourceSize: Qt.size(parent.width * 1.2 * 2, parent.height * 1.2 * 2)
                fillMode: Image.PreserveAspectFit
                smooth: true
                antialiasing: true
            }
        }

        MouseArea {
            id: mouseArea
            anchors.fill: parent
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            onClicked: navButton.clicked()
        }

        ToolTip {
            visible: mouseArea.containsMouse && !navButton.isSelected
            text: navButton.pageName
            delay: 100
            timeout: 3000
        }
    }
}
