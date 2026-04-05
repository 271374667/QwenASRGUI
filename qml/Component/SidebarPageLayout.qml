pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls.FluentWinUI3
import QtQuick.Layouts

Item {
    id: root

    required property var pages
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
    property int displayedIndex: -1
    property int pendingIndex: -1
    property bool isPreparingPage: false
    property var pageObjectRegistry: ({})
    property var incubatorRegistry: ({})
    property var prepareRequestRegistry: ({})
    property var buttonRegistry: ({})
    property int buttonRegistryVersion: 0
    property var componentRegistry: ({})
    property int preloadCursor: 0
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
                    "key": page.key ? page.key : "",
                    "name": page.name,
                    "iconSource": page.iconSource,
                    "qmlPath": page.qmlPath,
                    "pageProps": page.pageProps ? page.pageProps : ({})
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

    function copyRegistry(sourceRegistry) {
        let updatedRegistry = ({})

        for (let key in sourceRegistry) {
            updatedRegistry[key] = sourceRegistry[key]
        }

        return updatedRegistry
    }

    function cacheComponent(index, component) {
        let updatedRegistry = root.copyRegistry(root.componentRegistry)
        updatedRegistry[index] = component
        root.componentRegistry = updatedRegistry
    }

    function cachePageObject(index, pageObject) {
        let updatedRegistry = root.copyRegistry(root.pageObjectRegistry)
        updatedRegistry[index] = pageObject
        root.pageObjectRegistry = updatedRegistry
    }

    function cacheIncubator(index, incubator) {
        let updatedRegistry = root.copyRegistry(root.incubatorRegistry)
        updatedRegistry[index] = incubator
        root.incubatorRegistry = updatedRegistry
    }

    function markPageRequested(index) {
        let updatedRegistry = root.copyRegistry(root.prepareRequestRegistry)
        updatedRegistry[index] = true
        root.prepareRequestRegistry = updatedRegistry
    }

    function clearIncubator(index) {
        if (!root.incubatorRegistry[index]) {
            return
        }

        let updatedRegistry = ({})

        for (let key in root.incubatorRegistry) {
            if (key !== String(index)) {
                updatedRegistry[key] = root.incubatorRegistry[key]
            }
        }

        root.incubatorRegistry = updatedRegistry
    }

    function clearRequestedPage(index) {
        if (!root.prepareRequestRegistry[index]) {
            return
        }

        let updatedRegistry = ({})

        for (let key in root.prepareRequestRegistry) {
            if (key !== String(index)) {
                updatedRegistry[key] = root.prepareRequestRegistry[key]
            }
        }

        root.prepareRequestRegistry = updatedRegistry
    }

    function findPageIndex(pageKey) {
        if (!root.pages || !pageKey) {
            return -1
        }

        for (let i = 0; i < root.pages.length; ++i) {
            if (root.pages[i].key === pageKey) {
                return i
            }
        }

        return -1
    }

    function getPageComponent(index, asynchronousLoad) {
        if (!root.pages || index < 0 || index >= root.pages.length) {
            return null
        }

        let page = root.pages[index]
        if (!page || !page.qmlPath) {
            return null
        }

        let cachedComponent = root.componentRegistry[index]
        if (cachedComponent) {
            return cachedComponent
        }

        let creationMode = asynchronousLoad ? Component.Asynchronous : Component.PreferSynchronous
        let component = Qt.createComponent(page.qmlPath, creationMode)

        if (component.status === Component.Error) {
            console.error("Failed to load page component:", page.qmlPath, component.errorString())
            return null
        }

        root.cacheComponent(index, component)
        return component
    }

    function getPageObject(index) {
        return root.pageObjectRegistry[index] ? root.pageObjectRegistry[index] : null
    }

    function getPageProps(index) {
        if (!root.pages || index < 0 || index >= root.pages.length) {
            return ({})
        }

        let props = ({})
        let source = root.pages[index].pageProps

        if (source) {
            for (let key in source) {
                props[key] = source[key]
            }
        }

        return props
    }

    function initializePageObject(index, pageObject) {
        if (!pageObject) {
            return
        }

        pageObject.parent = pageHost
        pageObject.x = 0
        pageObject.y = 0
        pageObject.width = Qt.binding(function() {
            return pageHost.width
        })
        pageObject.height = Qt.binding(function() {
            return pageHost.height
        })
        pageObject.visible = false
        pageObject.enabled = false
        root.cachePageObject(index, pageObject)
    }

    function showPage(index) {
        for (let key in root.pageObjectRegistry) {
            let numericKey = Number(key)
            let pageObject = root.pageObjectRegistry[key]
            let isActive = numericKey === index
            pageObject.visible = isActive
            pageObject.enabled = isActive
            pageObject.opacity = isActive ? 1 : 0
        }

        root.displayedIndex = index
    }

    function finalizeNavigation(index) {
        if (root.pendingIndex !== index) {
            return
        }

        let pageObject = root.getPageObject(index)
        if (!pageObject) {
            return
        }

        root.showPage(index)
        root.pendingIndex = -1
        root.isPreparingPage = false
    }

    function preparePage(index, showPlaceholder) {
        if (!root.pages || index < 0 || index >= root.pages.length) {
            return
        }

        if (showPlaceholder) {
            root.pendingIndex = index
            root.isPreparingPage = true
        }

        if (root.getPageObject(index)) {
            root.clearRequestedPage(index)
            root.finalizeNavigation(index)
            return
        }

        root.markPageRequested(index)
        root.processPreparationQueue()
        preparationTimer.start()
    }

    function processPreparationQueue() {
        let hasPendingWork = false

        for (let key in root.prepareRequestRegistry) {
            let index = Number(key)

            if (root.getPageObject(index)) {
                root.clearRequestedPage(index)
                root.finalizeNavigation(index)
                continue
            }

            let incubator = root.incubatorRegistry[index]
            if (incubator) {
                hasPendingWork = true

                if (incubator.status === Component.Ready && incubator.object) {
                    root.clearIncubator(index)
                    root.initializePageObject(index, incubator.object)
                    root.clearRequestedPage(index)
                    root.finalizeNavigation(index)
                } else if (incubator.status === Component.Error) {
                    console.error("Failed to incubate page object:", index)
                    root.clearIncubator(index)
                    root.clearRequestedPage(index)
                    if (root.pendingIndex === index) {
                        root.pendingIndex = -1
                        root.isPreparingPage = false
                    }
                }

                continue
            }

            let component = root.getPageComponent(index, true)
            if (!component) {
                root.clearRequestedPage(index)
                if (root.pendingIndex === index) {
                    root.pendingIndex = -1
                    root.isPreparingPage = false
                }
                continue
            }

            hasPendingWork = true

            if (component.status === Component.Ready) {
                let incubator = component.incubateObject(
                    pageHost,
                    root.getPageProps(index),
                    Qt.Asynchronous
                )
                root.cacheIncubator(index, incubator)
            } else if (component.status === Component.Error) {
                console.error("Failed to prepare page component:", root.pages[index].qmlPath, component.errorString())
                root.clearRequestedPage(index)
                if (root.pendingIndex === index) {
                    root.pendingIndex = -1
                    root.isPreparingPage = false
                }
            }
        }

        if (!hasPendingWork) {
            preparationTimer.stop()
        }
    }

    function ensureCurrentPageLoaded() {
        if (!root.pages || root.pages.length === 0) {
            return
        }

        if (root.currentIndex < 0 || root.currentIndex >= root.pages.length) {
            return
        }

        if (!root.getPageObject(root.currentIndex)) {
            let component = root.getPageComponent(root.currentIndex, false)
            if (!component || component.status === Component.Error) {
                return
            }

            let pageObject = component.createObject(pageHost, root.getPageProps(root.currentIndex))
            if (!pageObject) {
                return
            }

            root.initializePageObject(root.currentIndex, pageObject)
        }

        root.showPage(root.currentIndex)
    }

    function preloadNextPage() {
        if (!root.pages || root.pages.length === 0) {
            preloadTimer.stop()
            return
        }

        while (root.preloadCursor < root.pages.length) {
            let index = root.preloadCursor
            root.preloadCursor += 1

            if (index === root.currentIndex) {
                continue
            }

            root.preparePage(index, false)
            return
        }

        preloadTimer.stop()
    }

    function navigateTo(index) {
        if (!root.pages || index < 0 || index >= root.pages.length || root.currentIndex === index) {
            return
        }

        root.previousIndex = root.currentIndex
        root.currentIndex = index

        if (root.getPageObject(index)) {
            root.pendingIndex = -1
            root.isPreparingPage = false
            root.showPage(index)
            return
        }

        root.preparePage(index, true)
    }

    function navigateToPage(pageKey) {
        let targetIndex = root.findPageIndex(pageKey)
        if (targetIndex >= 0) {
            root.navigateTo(targetIndex)
        }
    }

    onPagesChanged: {
        if (!root.pages || root.pages.length === 0) {
            root.currentIndex = -1
            root.previousIndex = -1
            root.displayedIndex = -1
            return
        }

        if (root.currentIndex < 0 || root.currentIndex >= root.pages.length) {
            root.currentIndex = 0
            root.previousIndex = 0
        }

        root.ensureCurrentPageLoaded()
    }

    Component.onCompleted: {
        root.ensureCurrentPageLoaded()
        root.preloadCursor = 0
        preloadTimer.start()
    }

    Timer {
        id: preparationTimer
        interval: 16
        repeat: true
        running: false
        onTriggered: root.processPreparationQueue()
    }

    Timer {
        id: preloadTimer
        interval: 0
        repeat: true
        running: false
        onTriggered: root.preloadNextPage()
    }

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

                            onClicked: root.navigateTo(modelData.index)

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

                            onClicked: root.navigateTo(modelData.index)

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

        Item {
            id: pageHost
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true

            Rectangle {
                anchors.fill: parent
                visible: root.isPreparingPage
                color: root.backgroundColor
                z: 100

                ColumnLayout {
                    anchors.centerIn: parent
                    spacing: 10

                    BusyIndicator {
                        Layout.alignment: Qt.AlignHCenter
                        running: root.isPreparingPage
                    }

                    Label {
                        Layout.alignment: Qt.AlignHCenter
                        text: qsTr("正在准备页面...")
                        color: root.isDark ? "#d7d7d7" : "#5b5b5b"
                    }
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
