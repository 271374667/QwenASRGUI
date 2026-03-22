pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts

Item {
    id: root

    property int pagePadding: 28
    property int spacing: 24
    default property alias contentData: contentColumn.data

    implicitHeight: contentColumn.implicitHeight + pagePadding * 2

    ColumnLayout {
        id: contentColumn
        x: root.pagePadding
        y: root.pagePadding
        width: root.width - root.pagePadding * 2
        spacing: root.spacing
    }
}
