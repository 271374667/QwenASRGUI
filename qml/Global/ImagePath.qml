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
}
