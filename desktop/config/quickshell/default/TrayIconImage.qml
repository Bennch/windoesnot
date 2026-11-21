import QtQuick
import QtQuick.Effects

// A system tray icon that stays visible on the taskbar. Apps ship icons made for one theme: a near-black glyph vanishes on the dark
// taskbar, a white one on the light taskbar. The icon is measured once (mean luminance of its opaque pixels, on a tiny canvas) and,
// when it would be lost against the bar, its brightness is lifted (dark bar) or lowered (light bar). Normal icons are not touched.
Item {
    id: root

    property url source
    property int iconSize: 20
    property bool darkBar: true       // the taskbar is dark (dark appearance)
    property bool autoContrast: true  // off: always show the icon as the app delivers it

    // Measured values (0..1), exposed for tests and tooltips
    property real luminance: 0.5
    property real opacityMean: 1.0
    property bool measured: false

    readonly property real darkLimit: 0.30
    readonly property real lightLimit: 0.80
    // Brightness change for the effect (-1..1); 0 leaves the icon as it is
    readonly property real adjustment: {
        if (!autoContrast || !measured || opacityMean < 0.04) return 0
        if (darkBar && luminance < darkLimit) return Math.min(0.80, (0.58 - luminance) * 1.5)
        if (!darkBar && luminance > lightLimit) return -Math.min(0.80, (luminance - 0.45) * 1.4)
        return 0
    }
    readonly property bool adjusted: adjustment !== 0

    implicitWidth: iconSize
    implicitHeight: iconSize
    width: iconSize
    height: iconSize

    Image {
        id: picture
        anchors.fill: parent
        source: root.source
        sourceSize.width: root.iconSize * 2
        sourceSize.height: root.iconSize * 2
        fillMode: Image.PreserveAspectFit
        smooth: true
        antialiasing: true
        mipmap: true
        layer.enabled: root.adjusted
        layer.smooth: true
        layer.effect: MultiEffect {
            brightness: root.adjustment
            contrast: root.adjustment > 0 ? -0.15 : 0.1
            saturation: root.adjustment > 0 ? -0.15 : 0
        }
    }

    // Measuring: draw the icon small and average its pixels, weighted by alpha
    Canvas {
        id: probe
        visible: false
        width: 16
        height: 16
        renderTarget: Canvas.Image
        renderStrategy: Canvas.Immediate

        function measure() {
            var url = String(root.source)
            if (url === "" || !isImageLoaded(url)) return
            var ctx = getContext("2d")
            ctx.clearRect(0, 0, width, height)
            ctx.drawImage(url, 0, 0, width, height)
            var data = ctx.getImageData(0, 0, width, height).data
            var weight = 0, sum = 0, alpha = 0
            for (var i = 0; i < data.length; i += 4) {
                var a = data[i + 3] / 255
                alpha += a
                weight += a
                sum += a * (0.2126 * data[i] + 0.7152 * data[i + 1] + 0.0722 * data[i + 2]) / 255
            }
            root.opacityMean = alpha / (width * height)
            root.luminance = weight > 0 ? sum / weight : 0.5
            root.measured = true
        }
        onPaint: measure()
        onImageLoaded: requestPaint()
    }

    function startMeasuring() {
        measured = false
        var url = String(root.source)
        if (url === "") return
        if (probe.isImageLoaded(url)) probe.requestPaint()
        else probe.loadImage(url)
    }
    onSourceChanged: startMeasuring()
    Component.onCompleted: startMeasuring()
}
