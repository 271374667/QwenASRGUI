pragma Singleton
import QtQml

QtObject {
    // All icon paths under qml/Images using relative URLs.
    readonly property url logo: Qt.resolvedUrl("../Images/Logo.svg")
    readonly property url cpu: Qt.resolvedUrl("../Images/Cpu.svg")
    readonly property url log: Qt.resolvedUrl("../Images/Log.svg")
    readonly property url mic: Qt.resolvedUrl("../Images/Mic.svg")
    readonly property url play: Qt.resolvedUrl("../Images/Play.svg")
    readonly property url settings: Qt.resolvedUrl("../Images/Settings.svg")
    readonly property url stop: Qt.resolvedUrl("../Images/Stop.svg")
    readonly property url timePicker: Qt.resolvedUrl("../Images/TimePicker.svg")
    readonly property url upload: Qt.resolvedUrl("../Images/Upload.svg")
    readonly property url question: Qt.resolvedUrl("../Images/Question.svg")
    readonly property url windowClose: Qt.resolvedUrl("../Images/WindowClose.svg")
    readonly property url windowMaximize: Qt.resolvedUrl("../Images/WindowMaximize.svg")
    readonly property url windowMinimize: Qt.resolvedUrl("../Images/WindowMinimize.svg")
    readonly property url windowRestore: Qt.resolvedUrl("../Images/WindowRestore.svg")
}
