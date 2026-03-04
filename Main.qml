import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15

import "components"

ApplicationWindow {
    id: win
    width: 1280
    height: 720
    visible: true
    title: "JARVIS Offline Assistant"

    Rectangle {
        anchors.fill: parent
        color: "#0b1320"

        RowLayout {
            anchors.fill: parent
            anchors.margins: 16
            spacing: 16

            // Left commands
            Rectangle {
                Layout.preferredWidth: 260
                Layout.fillHeight: true
                radius: 10
                color: "#0e1a2b"
                border.color: "#172941"

                Column {
                    anchors.fill: parent
                    anchors.margins: 14
                    spacing: 10

                    Text { text: "S.H.A.H.E.E.N"; color: "#d7fbff"; font.pixelSize: 18 }
                    Text { text: "COMMANDS"; color: "#8fb6c0"; font.pixelSize: 12 }

                    Text {
                        text: "- open youtube\n- open linkedin\n- youtube search <query>\n- search on google <query>\n- open file <path>"
                        color: "#9cc8d4"
                        font.pixelSize: 12
                    }

                    Rectangle { height: 1; width: parent.width; color: "#172941" }

                    Button {
                        text: "Start Voice"
                        onClicked: backend.startVoice()
                    }
                    Button {
                        text: "Stop Speaking"
                        onClicked: backend.stopSpeaking()
                    }

                    Item { height: 1; Layout.fillHeight: true }

                    Text { text: "Tip: Speak or type below."; color: "#6fa8b7"; font.pixelSize: 12 }
                }
            }

            // Center ring
            Rectangle {
                Layout.fillWidth: true
                Layout.fillHeight: true
                radius: 10
                color: "#0e1a2b"
                border.color: "#172941"

                Ring {
                    id: ring
                    anchors.centerIn: parent
                    size: Math.min(parent.width, parent.height) * 0.72
                    level: backend.ringLevel
                    labelText: "J.A.R.V.I.S"
                }

                Text {
                    anchors.bottom: parent.bottom
                    anchors.horizontalCenter: parent.horizontalCenter
                    anchors.bottomMargin: 18
                    text: "Say a command or ask a question"
                    color: "#7fb7c6"
                    font.pixelSize: 13
                }
            }

            // Right panel
            Rectangle {
                Layout.preferredWidth: 340
                Layout.fillHeight: true
                radius: 10
                color: "#0e1a2b"
                border.color: "#172941"

                Column {
                    anchors.fill: parent
                    anchors.margins: 14
                    spacing: 10

                    Row {
                        width: parent.width
                        Text { text: "LIVE"; color: "#d7fbff"; font.pixelSize: 14 }
                        Item { width: 1; height: 1; anchors.horizontalCenter: parent.horizontalCenter }
                        Text { text: backend.status; color: "#7fb7c6"; font.pixelSize: 12; anchors.right: parent.right }
                    }

                    Text { text: "Transcript"; color: "#8fb6c0"; font.pixelSize: 12 }

                    TextArea {
                        text: backend.transcript
                        readOnly: true
                        wrapMode: TextArea.Wrap
                        height: 160
                    }

                    Text { text: "Assistant"; color: "#8fb6c0"; font.pixelSize: 12 }

                    TextArea {
                        text: backend.response
                        readOnly: true
                        wrapMode: TextArea.Wrap
                        Layout.fillHeight: true
                    }
                }
            }
        }

        // Bottom input
        Rectangle {
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.bottom: parent.bottom
            height: 64
            color: "#0b1320"
            border.color: "#172941"

            RowLayout {
                anchors.fill: parent
                anchors.margins: 12
                spacing: 10

                TextField {
                    id: input
                    Layout.fillWidth: true
                    placeholderText: "Type here… e.g., open youtube | search on google cats"
                    onAccepted: backend.sendText(text)
                }

                Button {
                    text: "Send"
                    onClicked: backend.sendText(input.text)
                }
            }
        }
    }
}
