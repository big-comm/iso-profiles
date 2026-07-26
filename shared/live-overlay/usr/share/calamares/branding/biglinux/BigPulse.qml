import QtQuick 6.5
import QtQuick.Controls 6.5
import QtQuick.Shapes 6.5
import QtCore

// BigPulse — QML version of the Pulse game (https://pulse.talesam.org) for
// the Calamares slideshow. Single file, no external assets.
// Faithful port of the Android game (Godot): pointer runs along the shape's
// perimeter, tap inside the colored tube. Special tubes (gold / double /
// ghost / shield), hit particles and phases, same constants as the app.
// While nobody plays it runs in demo mode (plays by itself).

Item {
    id: root
    width: Math.max(700, parent ? parent.width : 700)
    height: Math.max(700, parent ? parent.height : 700)
    focus: true

    // ---- Constants (same as the Android game) ----
    readonly property var shapes: [96, 6, 5, 4, 3]      // circle, hex, penta, square, tri
    readonly property int shapeChangeEvery: 8
    readonly property int hitsPerPhase: 40
    readonly property real startLaps: 0.5
    readonly property real maxLaps: 1.0 / 0.6
    readonly property real lapsGrowth: 1.015
    readonly property real phaseSpeedStep: 1.15
    readonly property real phaseZoneStepDeg: 3.0
    readonly property real zoneStartDeg: 32.0
    readonly property real zoneMinDeg: 13.0
    readonly property real zoneShrinkPerHit: 0.18
    readonly property real tapGraceSec: 0.04
    readonly property real latComp: 0.12                // video-pipeline latency forgiveness (s)
    readonly property real perfectFraction: 0.28
    readonly property int specialAfter: 8
    readonly property real ghostVisibleSec: 0.6
    readonly property int partPool: 48

    readonly property color colBg1: "#070a18"
    readonly property color colBg2: "#131a33"
    readonly property color colRing: "#e6edf3"
    readonly property color colAccent: "#00e5ff"
    readonly property color colGold: "#ffc857"
    readonly property color colDouble: "#4ade80"
    readonly property color colGhost: "#b57bff"
    readonly property color colShield: "#7dd3fc"
    readonly property color colMiss: "#ff5570"
    readonly property color colDim: "#8a93a6"

    // ---- State ----
    property int score: 0
    property int phase: 1
    property int best: 0
    property int bestPhase: 1
    property real laps: startLaps
    property real direction: 1
    property real pointerS: 0
    property real zoneHalfS: 0
    property var targets: []            // [{c: centerS, t: type, at: clock}] — type: 0 normal, 1 gold, 2 double, 3 ghost, 4 shield
    property int targetI: 0
    property bool shield: false
    property bool wasInside: false
    property int perfectStreak: 0
    property int shapeIdx: 0
    property bool playing: false        // a person is actually playing
    property bool gameOver: false
    property real readyT: 0             // READY/GO countdown: pointer frozen
    property real overSince: 0
    property real clock: 0              // monotonic in-game time (s)
    property real flash: 0
    property real shake: 0
    property var feedbacks: []          // {text, color, t}

    Settings {
        id: store
        category: "BigPulse"
        property alias savedBest: root.best
        property alias savedBestPhase: root.bestPhase
    }

    // ---- Polygonal path (port of shape_path.gd) ----
    property var verts: []
    property var cum: []
    property real perimeter: 1
    property var outlinePts: []
    property var echo1Pts: []
    property var echo2Pts: []
    // zone tube geometry (A = current/first, B = second of a double)
    property var zoneAPts: []
    property var zoneBPts: []
    property color zoneACol: colAccent
    property color zoneBCol: colAccent
    property real zoneAAlpha: 1
    property int zoneAType: 0
    property real zoneAAt: 0

    readonly property real cx: width / 2
    readonly property real cy: height / 2 + 10
    readonly property real radius: Math.min(width, height) * 0.30

    function buildShape(idx) {
        shapeIdx = idx;
        var sides = shapes[idx];
        var v = [], c = [0];
        for (var i = 0; i < sides; i++) {
            var a = -Math.PI / 2 + i / sides * Math.PI * 2;
            v.push({x: cx + Math.cos(a) * radius, y: cy + Math.sin(a) * radius});
        }
        for (i = 0; i < sides; i++) {
            var b = v[(i + 1) % sides];
            c.push(c[i] + Math.hypot(b.x - v[i].x, b.y - v[i].y));
        }
        verts = v; cum = c; perimeter = c[sides];
        if (!isFinite(pointerS)) pointerS = 0;

        function ring(scale) {
            var pts = [];
            for (var k = 0; k < v.length; k++)
                pts.push(Qt.point(cx + (v[k].x - cx) * scale, cy + (v[k].y - cy) * scale));
            pts.push(pts[0]);
            return pts;
        }
        outlinePts = ring(1.0);
        echo1Pts = ring(1.18);
        echo2Pts = ring(1.38);
        updateZoneGeom();
    }

    function mod(a, m) { return ((a % m) + m) % m; }

    function pointAt(s) {
        s = mod(s, perimeter);
        var n = verts.length;
        for (var i = 0; i < n; i++)
            if (s < cum[i + 1]) {
                var seg = cum[i + 1] - cum[i];
                var t = seg <= 0 ? 0 : (s - cum[i]) / seg;
                var b = verts[(i + 1) % n];
                return {x: verts[i].x + (b.x - verts[i].x) * t,
                        y: verts[i].y + (b.y - verts[i].y) * t};
            }
        return verts[0];
    }

    function tangentAt(s) {
        s = mod(s, perimeter);
        var n = verts.length;
        for (var i = 0; i < n; i++)
            if (s < cum[i + 1]) {
                var b = verts[(i + 1) % n];
                var dx = b.x - verts[i].x, dy = b.y - verts[i].y;
                var len = Math.hypot(dx, dy) || 1;
                return {x: dx / len, y: dy / len};
            }
        return {x: 1, y: 0};
    }

    function distOn(a, b) {
        var d = mod(a - b, perimeter);
        return Math.min(d, perimeter - d);
    }

    function tolerance() { return zoneHalfS + perimeter * laps * tapGraceSec; }

    // Effective distance to the current tube center, forgiving on the "late"
    // side what the video pipeline (render + compositor) steals from the player.
    function lateDist() {
        var cur = targets[targetI];
        var ahead = mod((cur.c - pointerS) * direction, perimeter);
        if (ahead <= perimeter / 2) return ahead;           // still approaching
        return Math.max(0, (perimeter - ahead) - perimeter * laps * latComp);
    }

    function zoneColor(t) {
        return [colAccent, colGold, colDouble, colGhost, colShield][t];
    }

    // ---- Rules (ports of _shrink_zone / _spawn_targets from game.gd) ----
    function shrinkZone() {
        var hitsInPhase = score % hitsPerPhase;
        var start = zoneStartDeg - phaseZoneStepDeg * (phase - 1);
        var frac = Math.max(zoneMinDeg, start - hitsInPhase * zoneShrinkPerHit) / 360;
        zoneHalfS = perimeter * frac * 0.5;
        updateZoneGeom();
    }

    function spawnTargets() {
        targetI = 0;
        var kind = 0;
        if (score >= specialAfter) {
            var r = Math.random();
            if (r < 0.12) kind = 1;                                  // gold
            else if (r < 0.20 && score >= 14) kind = 2;              // double
            else if (r < 0.28 && score >= 22) kind = 3;              // ghost
            else if (r < 0.34 && !shield && score >= 10) kind = 4;   // shield
        }
        var first = mod(pointerS + direction * (0.35 + Math.random() * 0.30) * perimeter, perimeter);
        if (kind === 2) {
            var second = mod(first + direction * (0.20 + Math.random() * 0.15) * perimeter, perimeter);
            targets = [{c: first, t: 2, at: clock}, {c: second, t: 2, at: clock}];
        } else {
            targets = [{c: first, t: kind, at: clock}];
        }
        wasInside = false;
        updateZoneGeom();
    }

    function updateZoneGeom() {
        if (verts.length === 0 || targets.length === 0) return;
        function seg(centerS) {
            var pts = [];
            for (var i = 0; i <= 20; i++) {
                var p = pointAt(centerS - zoneHalfS + 2 * zoneHalfS * i / 20);
                pts.push(Qt.point(p.x, p.y));
            }
            return pts;
        }
        var a = targets[0];
        zoneAPts = seg(a.c);
        zoneACol = zoneColor(a.t);
        zoneAType = a.t;
        zoneAAt = a.at;
        zoneAAlpha = targetI > 0 ? 0.25 : 1;                // first of a double, already hit
        zoneBPts = targets.length > 1 ? seg(targets[1].c) : [];
        zoneBCol = colDouble;
    }

    // ---- Particles ("granulados", port of Hit/PerfectParticles) ----
    property var partState: []
    property int partNext: 0

    function popParticles(x, y, color, count, vmin, vmax, life) {
        for (var k = 0; k < count; k++) {
            var i = partNext; partNext = (partNext + 1) % partPool;
            var it = partRep.itemAt(i);
            if (!it) continue;
            var ang = Math.random() * Math.PI * 2;
            var sp = vmin + Math.random() * (vmax - vmin);
            partState[i] = {vx: Math.cos(ang) * sp, vy: Math.sin(ang) * sp, life: life, total: life};
            it.x = x - it.width / 2; it.y = y - it.height / 2;
            it.color = color; it.opacity = 1; it.visible = true;
        }
    }

    function burstAtPointer(color, count, vmin, vmax, life) {
        var p = pointAt(pointerS);
        popParticles(p.x, p.y, color, count, vmin, vmax, life);
    }

    function resetRun(startPlaying) {
        score = 0; phase = 1; laps = startLaps; direction = 1;
        pointerS = 0; perfectStreak = 0; flash = 0; shake = 0;
        shield = false;
        feedbacks = [];
        gameOver = false;
        playing = startPlaying;
        readyT = startPlaying ? 1.2 : 0;
        buildShape(0);
        shrinkZone();
        spawnTargets();
        if (startPlaying) addFeedback("READY...", colGold);
    }

    function addFeedback(text, color) {
        var f = feedbacks.slice();
        f.push({text: text, color: "" + color, t: 1.0});
        if (f.length > 4) f.shift();
        feedbacks = f;
    }

    function tap() {
        if (gameOver) {
            if (new Date().getTime() - overSince > 700) resetRun(true);
            return;
        }
        if (!playing) { resetRun(true); return; }   // player takes over the demo
        if (readyT > 0) return;                     // still in READY/GO
        doTap(false);
    }

    function doTap(auto) {
        var cur = targets[targetI];
        var dist = auto ? distOn(pointerS, cur.c) : lateDist();
        if (dist > tolerance()) { loseOrShield(); return; }

        // Snap the pointer back to where the player SAW it when tapping, so
        // the reversal is visually instant (like on the phone) instead of
        // "keeps going then comes back".
        if (!auto)
            pointerS = mod(pointerS - perimeter * laps * latComp * direction, perimeter);

        if (targetI < targets.length - 1) {         // first tube of a double
            targetI++;
            wasInside = false;
            addFeedback("1/2", colDouble);
            burstAtPointer(colDouble, 14, 120, 320, 0.5);
            updateZoneGeom();
            return;
        }
        finalizeHit(dist, cur);
    }

    function finalizeHit(dist, cur) {
        score++;
        var perfect = dist <= zoneHalfS * perfectFraction;
        if (perfect) {
            perfectStreak++;
            addFeedback("PERFECT ×" + Math.min(perfectStreak + 1, 9), colGold);
            burstAtPointer(colGold, 48, 180, 460, 0.7);
            shake = 7;
        } else {
            perfectStreak = 0;
            burstAtPointer(cur.t === 1 ? colGold : colAccent, 24, 120, 320, 0.5);
        }
        if (cur.t === 1) addFeedback("GOLD!", colGold);
        if (cur.t === 4 && !shield) {
            shield = true;
            addFeedback("SHIELD!", colShield);
        }

        laps = Math.min(laps * lapsGrowth, maxLaps);
        direction *= -1;
        flash = 1;

        if (score % hitsPerPhase === 0) {
            phase++;
            laps = Math.min(startLaps * Math.pow(phaseSpeedStep, phase - 1), maxLaps);
            addFeedback("PHASE " + phase + " !", colAccent);
            burstAtPointer(colAccent, 48, 180, 460, 0.7);
            shake = 12;
        }
        var nextShape = Math.floor(score / shapeChangeEvery) % shapes.length;
        if (nextShape !== shapeIdx) {
            var keep = pointerS / perimeter;
            buildShape(nextShape);
            pointerS = keep * perimeter;
        }
        shrinkZone();
        spawnTargets();
    }

    function loseOrShield() {
        if (playing && shield) {                    // shield absorbs one mistake
            shield = false;
            addFeedback("SHIELD!", colShield);
            wasInside = false;
            spawnTargets();
            return;
        }
        die();
    }

    function die() {
        if (!playing) { spawnTargets(); return; }   // demo never "dies"
        burstAtPointer(colMiss, 32, 150, 400, 0.6);
        playing = false;
        gameOver = true;
        overSince = new Date().getTime();
        shake = 14;
        if (score > best) { best = score; }
        if (phase > bestPhase) { bestPhase = phase; }
    }

    // ---- Loop (vsync-driven; state and visuals share the same frame) ----
    function step(dt) {
        if (!(perimeter > 0)) return;   // no valid layout size yet
        clock += dt;
        if (!gameOver && readyT > 0) {
            readyT -= dt;
            if (readyT <= 0) { addFeedback("GO!", colAccent); flash = 1; }
        } else if (!gameOver) {
            pointerS = mod(pointerS + perimeter * laps * direction * dt, perimeter);
            var cur = targets[targetI];
            var inside = (playing ? lateDist() : distOn(pointerS, cur.c)) <= tolerance();
            if (!playing) {
                // demo: taps by itself near the middle of the tube
                if (inside && distOn(pointerS, cur.c) < zoneHalfS * 0.6 && Math.random() < 0.35)
                    doTap(true);
                else if (wasInside && !inside)
                    spawnTargets();
            } else if (wasInside && !inside) {
                loseOrShield();
            }
            wasInside = inside && !gameOver;
        }
        flash = Math.max(flash - dt * 4, 0);
        shake = shake + (0 - shake) * Math.min(dt * 10, 1);
        if (feedbacks.length > 0) {
            var f = [];
            for (var i = 0; i < feedbacks.length; i++) {
                var it = feedbacks[i];
                it.t -= dt * 1.1;
                if (it.t > 0) f.push(it);
            }
            feedbacks = f;
        }

        // imperative visual updates (transforms only — cheap)
        scene.x = (Math.random() * 2 - 1) * shake;
        scene.y = (Math.random() * 2 - 1) * shake;
        if (verts.length > 0 && !gameOver) {
            var pp = pointAt(pointerS);
            pointerItem.x = pp.x; pointerItem.y = pp.y;
            var tg = tangentAt(pointerS);
            pointerItem.rotation = Math.atan2(tg.y, tg.x) * 180 / Math.PI + 90;
        }
        for (i = 0; i < partPool; i++) {
            var st = partState[i];
            if (!st) continue;
            var pd = partRep.itemAt(i);
            st.life -= dt;
            if (st.life <= 0 || !pd) {
                partState[i] = null;
                if (pd) pd.visible = false;
            } else {
                pd.x += st.vx * dt; pd.y += st.vy * dt;
                pd.opacity = st.life / st.total;
            }
        }
    }

    FrameAnimation {
        running: root.visible
        onTriggered: root.step(Math.min(frameTime, 0.05))
    }

    Component.onCompleted: {
        var ps = [];
        for (var i = 0; i < partPool; i++) ps.push(null);
        partState = ps;
        resetRun(false);
        forceActiveFocus();
    }
    onWidthChanged: { buildShape(shapeIdx); shrinkZone(); }
    onHeightChanged: { buildShape(shapeIdx); shrinkZone(); }

    Keys.onSpacePressed: tap()
    MouseArea { anchors.fill: parent; onPressed: root.tap() }

    // ---- Background (static; never repainted) ----
    Rectangle {
        anchors.fill: parent
        gradient: Gradient {
            GradientStop { position: 0.0; color: root.colBg1 }
            GradientStop { position: 0.55; color: root.colBg2 }
            GradientStop { position: 1.0; color: root.colBg1 }
        }
    }
    Repeater {
        model: 60
        Rectangle {
            readonly property int i: index
            x: root.mod(Math.sin(i * 127.1) * 43758.5, 1) * root.width
            y: root.mod(Math.sin(i * 311.7) * 12543.8, 1) * root.height
            width: i % 3 === 0 ? 2 : 1
            height: width
            color: Qt.rgba(0.9, 0.93, 0.95, 0.20)
        }
    }

    // ---- Game scene ----
    Item {
        id: scene
        width: parent.width; height: parent.height

        Shape {                                             // outer echoes
            preferredRendererType: Shape.CurveRenderer
            ShapePath {
                strokeColor: Qt.rgba(0, 0.9, 1, 0.07); strokeWidth: 3
                fillColor: "transparent"; joinStyle: ShapePath.RoundJoin
                PathPolyline { path: root.echo1Pts }
            }
            ShapePath {
                strokeColor: Qt.rgba(0, 0.9, 1, 0.04); strokeWidth: 2
                fillColor: "transparent"; joinStyle: ShapePath.RoundJoin
                PathPolyline { path: root.echo2Pts }
            }
        }
        Shape {                                             // main outline (game: alpha 0.35 + flash; shield tint)
            preferredRendererType: Shape.CurveRenderer
            ShapePath {
                strokeColor: root.shield
                    ? Qt.rgba(0.70, 0.88, 0.97, 0.45 + root.flash * 0.55)
                    : Qt.rgba(0.90, 0.93, 0.95, 0.35 + root.flash * 0.65)
                strokeWidth: 8
                fillColor: "transparent"; joinStyle: ShapePath.RoundJoin
                PathPolyline { path: root.outlinePts }
            }
        }
        Shape {                                             // tube A (current / first): glow + solid band
            preferredRendererType: Shape.CurveRenderer
            visible: !root.gameOver && root.zoneAPts.length > 0
                     && (root.zoneAType !== 3 || root.clock - root.zoneAAt < root.ghostVisibleSec)
            ShapePath {
                strokeColor: Qt.rgba(root.zoneACol.r, root.zoneACol.g, root.zoneACol.b, 0.28 * root.zoneAAlpha)
                strokeWidth: 34
                capStyle: ShapePath.RoundCap; fillColor: "transparent"
                PathPolyline { path: root.zoneAPts }
            }
            ShapePath {
                strokeColor: Qt.rgba(root.zoneACol.r, root.zoneACol.g, root.zoneACol.b, root.zoneAAlpha)
                strokeWidth: 16
                capStyle: ShapePath.RoundCap; fillColor: "transparent"
                PathPolyline { path: root.zoneAPts }
            }
        }
        Shape {                                             // tube B (second of a double)
            preferredRendererType: Shape.CurveRenderer
            visible: !root.gameOver && root.zoneBPts.length > 0
            ShapePath {
                strokeColor: Qt.rgba(root.zoneBCol.r, root.zoneBCol.g, root.zoneBCol.b, 0.28)
                strokeWidth: 34
                capStyle: ShapePath.RoundCap; fillColor: "transparent"
                PathPolyline { path: root.zoneBPts }
            }
            ShapePath {
                strokeColor: root.zoneBCol
                strokeWidth: 16
                capStyle: ShapePath.RoundCap; fillColor: "transparent"
                PathPolyline { path: root.zoneBPts }
            }
        }

        Repeater {                                          // particle pool
            id: partRep
            model: root.partPool
            Rectangle {
                width: 3 + (index % 4); height: width; radius: width / 2
                visible: false
            }
        }

        Item {                                              // classic pointer: bar across the ring + dot
            id: pointerItem
            visible: !root.gameOver
            Rectangle {
                anchors.centerIn: parent
                width: 52; height: 8; radius: 4
                color: root.colRing
            }
            Rectangle {
                anchors.centerIn: parent
                width: 14; height: 14; radius: 7
                color: root.colRing
            }
        }
    }

    // ---- HUD ----
    Text {
        x: 24; y: 18
        text: "PULSE"
        color: colAccent
        font.pixelSize: 26; font.bold: true; font.letterSpacing: 6
    }
    Text {
        x: 24; y: 50
        text: "best " + best
        color: colDim; font.pixelSize: 15
        visible: best > 0
    }
    Text {                                                  // shield indicator, like the app's ring tint
        x: 24; y: 72
        text: "⬡ SHIELD"
        color: colShield; font.pixelSize: 14; font.bold: true
        visible: shield
    }

    // score in the middle of the shape
    Column {
        visible: !gameOver
        x: cx - width / 2; y: cy - 46
        spacing: 0
        Text {
            anchors.horizontalCenter: parent.horizontalCenter
            text: score
            color: Qt.rgba(0.9, 0.93, 0.95, 0.95)
            font.pixelSize: 64; font.bold: true
            style: Text.Outline; styleColor: "#0a0e20"
        }
        Text {
            anchors.horizontalCenter: parent.horizontalCenter
            text: "PHASE " + phase
            color: phase > 1 ? colGold : colDim
            font.pixelSize: 17; font.letterSpacing: 3
        }
    }

    // floating feedbacks
    Column {
        anchors.horizontalCenter: parent.horizontalCenter
        y: cy - radius - 74
        spacing: 2
        Repeater {
            model: feedbacks
            Text {
                anchors.horizontalCenter: parent.horizontalCenter
                text: modelData.text
                color: modelData.color
                opacity: modelData.t
                font.pixelSize: 22; font.bold: true; font.letterSpacing: 2
            }
        }
    }

    // demo-mode invitation
    Rectangle {
        visible: !playing && !gameOver
        anchors.horizontalCenter: parent.horizontalCenter
        y: cy + root.radius + 40
        width: demoText.width + 44; height: 44; radius: 22
        color: Qt.rgba(0, 0.9, 1, 0.10)
        border.color: Qt.rgba(0, 0.9, 1, 0.45); border.width: 1
        SequentialAnimation on opacity {
            loops: Animation.Infinite
            NumberAnimation { from: 0.55; to: 1.0; duration: 900; easing.type: Easing.InOutSine }
            NumberAnimation { from: 1.0; to: 0.55; duration: 900; easing.type: Easing.InOutSine }
        }
        Text {
            id: demoText
            anchors.centerIn: parent
            text: "Click and play while installing!"
            color: "#dff8ff"; font.pixelSize: 17; font.bold: true
        }
    }

    // game over
    Rectangle {
        visible: gameOver
        anchors.fill: parent
        color: Qt.rgba(0.03, 0.04, 0.10, 0.82)
        Column {
            anchors.centerIn: parent
            spacing: 10
            Text {
                anchors.horizontalCenter: parent.horizontalCenter
                text: "GAME OVER"
                color: colMiss; font.pixelSize: 34; font.bold: true; font.letterSpacing: 6
            }
            Text {
                anchors.horizontalCenter: parent.horizontalCenter
                text: score
                color: colRing; font.pixelSize: 72; font.bold: true
            }
            Text {
                anchors.horizontalCenter: parent.horizontalCenter
                text: "phase " + phase + "  ·  best " + best
                color: colDim; font.pixelSize: 17
            }
            Item { width: 1; height: 10 }
            Rectangle {
                anchors.horizontalCenter: parent.horizontalCenter
                width: linkCol.width + 56; height: linkCol.height + 30; radius: 14
                color: Qt.rgba(1, 0.78, 0.34, 0.10)
                border.color: Qt.rgba(1, 0.78, 0.34, 0.55); border.width: 1
                Column {
                    id: linkCol
                    anchors.centerIn: parent
                    spacing: 4
                    Text {
                        anchors.horizontalCenter: parent.horizontalCenter
                        text: "Take Pulse on your Android"
                        color: colGold; font.pixelSize: 17; font.bold: true
                    }
                    Text {
                        anchors.horizontalCenter: parent.horizontalCenter
                        text: "pulse.talesam.org"
                        color: "#ffe2a8"; font.pixelSize: 21; font.bold: true; font.letterSpacing: 1
                    }
                }
            }
            Item { width: 1; height: 6 }
            Text {
                anchors.horizontalCenter: parent.horizontalCenter
                text: "tap to play again"
                color: colDim; font.pixelSize: 15
                SequentialAnimation on opacity {
                    loops: Animation.Infinite
                    NumberAnimation { from: 0.4; to: 1; duration: 800 }
                    NumberAnimation { from: 1; to: 0.4; duration: 800 }
                }
            }
        }
    }

    // permanent footer with the link
    Text {
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.bottom: parent.bottom
        anchors.bottomMargin: 12
        visible: !gameOver
        text: "Full game on Android · pulse.talesam.org"
        color: Qt.rgba(0.54, 0.58, 0.65, 0.8)
        font.pixelSize: 14
    }
}
