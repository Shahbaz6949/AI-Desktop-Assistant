import QtQuick 2.15

Item {
    id: root
    property int size: 360
    property real level: 0.15
    property string labelText: "J.A.R.V.I.S"

    width: size
    height: size

    Canvas {
        id: c
        anchors.fill: parent
        onPaint: {
            var ctx = getContext("2d");
            ctx.clearRect(0,0,width,height);

            var cx = width/2;
            var cy = height/2;

            // background rings
            ctx.beginPath();
            ctx.arc(cx, cy, width*0.44, 0, Math.PI*2);
            ctx.strokeStyle = "rgba(111,246,255,0.15)";
            ctx.lineWidth = 10;
            ctx.stroke();

            function ring(r, w, alpha){
                ctx.beginPath();
                ctx.arc(cx, cy, r, 0, Math.PI*2);
                ctx.strokeStyle = "rgba(111,246,255," + alpha + ")";
                ctx.lineWidth = w;
                ctx.stroke();
            }

            ring(width*0.30, 4, 0.25);
            ring(width*0.36, 2, 0.18);
            ring(width*0.42, 3, 0.22);

            // level pulse
            var pulse = Math.max(0.05, Math.min(1.0, root.level));
            var rPulse = width*(0.24 + 0.10*pulse);
            ctx.beginPath();
            ctx.arc(cx, cy, rPulse, 0, Math.PI*2);
            ctx.strokeStyle = "rgba(111,246,255," + (0.10 + 0.25*pulse) + ")";
            ctx.lineWidth = 6;
            ctx.stroke();

            // ticks
            ctx.save();
            ctx.translate(cx, cy);
            ctx.strokeStyle = "rgba(111,246,255,0.20)";
            for (var i=0;i<72;i++){
                var ang = i*(Math.PI*2/72);
                var r1 = width*0.46;
                var r2 = r1 - (i%6===0 ? 12 : 6);
                ctx.beginPath();
                ctx.moveTo(Math.cos(ang)*r1, Math.sin(ang)*r1);
                ctx.lineTo(Math.cos(ang)*r2, Math.sin(ang)*r2);
                ctx.lineWidth = (i%6===0 ? 2 : 1);
                ctx.stroke();
            }
            ctx.restore();
        }
    }

    Timer {
        interval: 33
        running: true
        repeat: true
        onTriggered: c.requestPaint()
    }

    Text {
        anchors.centerIn: parent
        text: root.labelText
        color: "#d7fbff"
        font.pixelSize: 20
        font.letterSpacing: 4
    }
}
